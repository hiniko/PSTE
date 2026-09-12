#!/usr/bin/env python3
"""Build an HTML page that shows an eval result to a person.

    python3 evals/report.py                      # the newest result
    python3 evals/report.py --level 3
    python3 evals/report.py --open               # write it, then open it

Pick a document from the list. The committed source and each rewrite appear side by
side, with every finding marked in the text. Click a finding to jump to it.

The source column is the document that every arm rewrote. A rewrite means nothing
without the text it started from, so the page shows them together and checks them
all the same way.

WHAT THIS PAGE SHOWS AND WHAT IT DOES NOT

Each arm shows PASS, or FAIL with every offender listed. This page is the evaluation
harness, and `pste_lint.py` is eval tooling now, not a tool this project distributes
to a writer. PSTE-1 §5.2 lets a harness report a count, a rate, or a percentage,
because its reader is a maintainer comparing a change across a corpus.

The word count beside each arm is not a score either. It is the guard that rule
PSTE-A1 needs: an arm that conforms by saying less has dropped a fact, and the short
column makes that visible.

PSTE-C6 makes fact loss a precondition of PASS, not a finding among the others: a
rewrite that drops a number, a unit, a negation, or an obligation FAILS regardless of
how clean its conformance findings are. `faithfulness.py` computes this per arm
against the committed source, and the page marks it apart from the conformance
findings so a clean-but-lossy document does not read the same as a plain pass. Read
`faithfulness.py`'s own docstring for what it can and cannot catch: it finds DROPPED
tokens, not changed meaning, so a passing fact-loss check is not proof the rewrite is
faithful.

This file only reads. It calls no API, and it writes no number back into the
snapshot. Every verdict is computed from `evals/pste_lint.py` when the page is
built, so the snapshot stays raw text and the standard stays the only source of
truth.
"""

import argparse
import bisect
import html
import json
import os
import sys
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import faithfulness  # noqa: E402
import provenance  # noqa: E402
import pste_lint  # noqa: E402

# `source` is not an arm. It is the committed document, and it appears first so a
# reader compares each rewrite against what it started from.
ARM_ORDER = ("source", "baseline", "control", "pste", "pste_fixed")

ARM_NOTE = {
    "source": "The committed document. Not generated.",
    "baseline": "No system prompt.",
    "control": "Asked plainly to simplify.",
    "pste": "Asked plainly, plus the skill.",
    "pste_fixed": "pste, then a fix pass against the checker's findings.",
}

DISCLAIMER = (
    "Conformance is not quality. This page shows whether each arm followed the "
    "rules of PSTE-1. It does not measure readability, and nobody has yet tested "
    "whether PSTE text helps a reader. Do not present this page as evidence of "
    "quality. See evals/FUTURE-WORK.md."
)


def offset_of(text, line, column):
    """Turn a 1-indexed line and column into an offset into `text`.

    This is the inverse of `pste_lint.line_col`. The finding also carries an
    `excerpt_offset`, but that counts into the excerpt, and the excerpt is a masked
    copy in which code spans became a placeholder of a different length. Only the
    line and the column point into the text that the page shows.
    """
    if not line or not column or line < 1 or column < 1:
        return None
    start = 0
    for _ in range(line - 1):
        nxt = text.find("\n", start)
        if nxt == -1:
            return None
        start = nxt + 1
    offset = start + column - 1
    return offset if offset < len(text) else None


def mark_findings(text, findings):
    """Wrap every finding in a <mark>, and return the HTML.

    Findings can overlap and can arrive in any order, so this walks the text once
    and opens a mark only when no other mark is open. The nested finding keeps its
    entry in the list beside the text, so no finding is lost from the report.
    """
    spans = []
    for index, finding in enumerate(findings):
        start = finding.get("offset")
        if start is None:
            continue
        # Mark the token, not the line, so the reader sees exactly what failed.
        length = max(1, len(finding.get("token") or "") or 1)
        spans.append((start, start + length, index))

    spans.sort()
    out, cursor, open_until = [], 0, -1
    for start, end, index in spans:
        if start < cursor or start < open_until:
            continue
        out.append(html.escape(text[cursor:start]))
        rule = html.escape(findings[index]["rule"])
        message = html.escape(findings[index]["message"])
        out.append(
            f'<mark id="f{index}" class="hit" data-i="{index}" '
            f'title="{rule}: {message}">{html.escape(text[start:end])}</mark>'
        )
        cursor, open_until = end, end
    out.append(html.escape(text[cursor:]))
    return "".join(out)


def token_of(text, start):
    """Recover the offending token, so a mark covers it and not the whole line."""
    if start is None:
        return ""
    tail = text[start : start + 60]
    # A finding points at a word, a phrase, or a single mark of punctuation. Take
    # the run of word characters, or one character when the run is empty.
    end = 0
    while end < len(tail) and (tail[end].isalnum() or tail[end] in "-_'’"):
        end += 1
    return tail[:end] if end else tail[:1]


def clean_sentence_rate(text, findings, total_sentences):
    """How many of the text's sentences carry zero findings.

    PSTE counts by the sentence already (N1/N2's word limits, D2's six-sentence
    cap), and a reader meets the text one sentence at a time, so this is the
    denominator that needs no argument for why it was picked. A finding's
    `offset` falls inside exactly one sentence: the last sentence that starts at
    or before it. `strip_non_prose` keeps every character's position, so the
    sentence starts computed from the raw `text` line up with the offsets
    `build_entry` already put on each finding.
    """
    if not total_sentences:
        return {"clean": 0, "of": 0, "rate": 0}
    # Same input check_text split: code spans and fences blanked, so a stray
    # '.' inside one never manufactures a sentence boundary that the finding
    # offsets (which point into the raw text) would not agree with.
    prose = pste_lint.strip_non_prose(text)
    starts = sorted(offset for _, _, offset in pste_lint.split_sentences(
        prose, mark_list_items=True, with_offsets=True
    ))
    # Where each line begins, so a line-and-column finding can be placed.
    line_starts = [0] + [i + 1 for i, ch in enumerate(prose) if ch == "\n"]

    dirty = set()
    located = 0
    for finding in findings:
        # `build_entry` puts a document offset on every finding before the page
        # reads it. A caller that passes `check_text`'s own findings has none,
        # and `excerpt_offset` is NOT it: that one counts from the start of the
        # excerpt, so it sits between 0 and about 100 for every finding in a
        # document and would drop them all into the first sentence. The line
        # and the column are the position, so derive the offset from those.
        offset = finding.get("offset")
        if offset is None:
            line, column = finding.get("line"), finding.get("column")
            if line is not None and column is not None:
                offset = line_starts[min(line, len(line_starts)) - 1] + column - 1
        if offset is None:
            continue
        located += 1
        # The sentence a finding belongs to is the last one that starts at or
        # before it.
        dirty.add(bisect.bisect_right(starts, offset) - 1)
    # A finding nobody could place cannot mark a sentence, so a run where none
    # of them carry a position reports every sentence clean. That is a fault in
    # the caller, not a clean document.
    if findings and not located:
        raise ValueError(
            "no finding carries a position, so every sentence would read clean"
        )
    clean = total_sentences - len(dirty)
    return {
        "clean": clean,
        "of": total_sentences,
        "rate": round(clean * 100 / total_sentences, 1),
    }


def semantic_findings(semantic, text):
    """Normalise one arm's `entry["semantic"][arm]` for the page.

    `semantic` is `{"summary": [...], "runs": [...]}` from semantic_lint.py,
    `{"unjudged": True, "error": ...}` when run.py's judging stage RAN but this
    one cell's judge call failed outright (every pass errored — an API limit,
    a timeout), `{"unjudged": True, "sampled_out": True, "error": ...}` when
    this cell was never SENT to the judge at all (run.py's rotate-and-anchor
    sampling, see `judge_sample` in run.py), or None when the judge stage
    never ran at all for this arm (no credential, run predates the judge, or
    the whole stage crashed — `semantic_error` on the snapshot says which).
    The committed result this page was built against ran the judge with 2
    passes, before `status`/`reason` existed on each row, so every field is
    read with `.get()` and a safe default rather than assumed present. This
    must not crash on that older shape, and must not invent data to fill it in.

    Only a `status == "confirmed"` row may count toward a verdict: agreement
    below the gate is `low-agreement`, and a row the judge weighed and
    dismissed is `rejected` — see semantic_lint.judge_repeatedly's own
    docstring. A summary with no `status` at all (the older shape) is treated
    as unconfirmed everywhere, so it can be READ on the page but never fails
    an arm that a fresh, current-shape run would not have failed either.

    `unjudged` is returned separately (not folded into `rows`) because it is
    not a finding at all — it is the absence of one, and the one case this
    page must never render the same as "the judge ran and found nothing".

    `sampled_out` is a further split of `unjudged`, not a fourth state: a cell
    excluded by the sampler was never asked about, so it earns the same
    `pass=False` as a cell whose judge call failed (neither has been checked
    against the 52 semantic rules — see build_entry's UNJUDGED note for why
    that is a precondition of PASS regardless of cause). But "not selected by
    design" and "the judge tried and failed" are different facts about the
    run, and a reader must be able to tell them apart without guessing from
    the error string, so it is its own field on the JSON and its own label on
    the page rather than folded into the `unjudged` bit.
    """
    if semantic and "by_judge" in semantic:
        # MULTI-JUDGE. Several models each judged this text; their results stay
        # SEPARATE by model (run.py never merges them), and this is the one
        # place that separateness turns into one list a reader can scan. Each
        # row still carries its own judge's name (`judge`), so "what did judge
        # X confirm" is answerable by filtering this list — no parallel view
        # needed. See `judge_overlap` for how `judges`/`overlap` get added.
        return judge_overlap(semantic["by_judge"], text)
    if semantic and semantic.get("unjudged"):
        return [], 0, True, bool(semantic.get("sampled_out"))
    if not semantic:
        return [], 0, False, False
    rows = [_semantic_row(item, text) for item in semantic.get("summary") or []]
    confirmed = sum(1 for r in rows if r["status"] == "confirmed")
    return rows, confirmed, False, False


def _semantic_row(item, text):
    """One `summary` entry (semantic_lint.judge_repeatedly's shape) as a page row."""
    offset = offset_of(text, item.get("line"), item.get("column"))
    return {
        "rule": item.get("rule", ""),
        "quote": item.get("quote", ""),
        "problem": item.get("problem", ""),
        "fix": item.get("fix", ""),
        "reason": item.get("reason", ""),
        "confidence": item.get("confidence", ""),
        "status": item.get("status") or "low-agreement",
        "seenIn": item.get("seen_in"),
        "of": item.get("of"),
        "agreement": item.get("agreement"),
        "located": bool(item.get("located")),
        "line": item.get("line"),
        "column": item.get("column"),
        "offset": offset,
    }


def judge_overlap(by_judge, text):
    """Merge several judges' results into rows, and mark WHICH judges agree.

    WHY THIS SHAPE. Two judges on the same text overlap 43-50% on which
    findings they confirm (measured: both found PSTE-A1 in every document,
    half the rest was judge-specific). A finding two independent judges
    confirm is worth more than the same judge confirming it twice — that is
    the whole reason to run more than one. So this groups CONFIRMED rows by
    rule and asks how many judges' "by_judge" entries confirmed it:

        judges == every judge passed in     -> status "overlap" (the
            trustworthy set: both/all judges independently confirmed it)
        judges == a strict subset           -> status stays "confirmed", but
            `judges` names which one(s) found it, so "only one judge saw
            this" is visible rather than silently merged into the same mark
            a real overlap gets.

    A judge's own low-agreement/rejected rows, and a judge that failed
    outright (`unjudged`), are kept too — per judge, never merged across
    judges — so "what did judge X confirm" stays answerable by filtering on
    `judge`/`judges`, same as a single-judge row already answers "what did
    the judge confirm".

    Returns (rows, confirmed, unjudged, sampled_out) — the same 4-tuple
    shape `semantic_findings` already returns for one judge, so `build_entry`
    needs no branch for multi-judge: `semanticConfirmed` and `pass` read the
    same fields either way.
    """
    judge_names = list(by_judge)
    per_judge_rows = {}
    any_judged = False
    all_sampled_out = True
    for judge_model, cell in by_judge.items():
        if cell and cell.get("unjudged"):
            per_judge_rows[judge_model] = None  # this judge has no rows to offer
            all_sampled_out = all_sampled_out and bool(cell.get("sampled_out"))
            continue
        any_judged = True
        all_sampled_out = False
        per_judge_rows[judge_model] = [
            _semantic_row(item, text) for item in (cell or {}).get("summary") or []
        ]

    if not any_judged:
        # Every judge failed (or was sampled out) for this cell — no judge
        # produced a single row, so this cell is UNJUDGED exactly like the
        # single-judge case, not "judged and clean".
        return [], 0, True, all_sampled_out

    # Group CONFIRMED rows by rule, across judges, to find the overlap — the
    # rule is the stable key (a quote differs between judges for the same
    # offence, same reasoning as judge_repeatedly's own grouping).
    confirmed_by_rule = {}
    rows = []
    for judge_model, judge_rows in per_judge_rows.items():
        if judge_rows is None:
            continue
        for row in judge_rows:
            row = dict(row, judge=judge_model)
            rows.append(row)
            if row["status"] == "confirmed":
                confirmed_by_rule.setdefault(row["rule"], []).append(judge_model)

    judged_names = {m for m, r in per_judge_rows.items() if r is not None}
    for row in rows:
        if row["status"] != "confirmed":
            continue
        agreeing = confirmed_by_rule.get(row["rule"], [])
        row["judges"] = agreeing
        # OVERLAP: every judge that actually ran for this cell confirmed this
        # rule. A judge that failed outright does not count against overlap —
        # "both judges that answered agreed" is the trustworthy claim, not
        # "every judge we tried to run happened to succeed AND agreed".
        if len(set(agreeing)) >= len(judged_names) and len(judged_names) > 1:
            row["status"] = "overlap"

    # One offence, one row. Every judge that confirmed a rule contributed a row
    # of its own above, so a rule three judges agreed on arrived three times and
    # counted three times. The stronger the agreement, the worse the count got.
    # An overlap row now appears once and names every judge that agreed.
    first = {}
    collapsed = []
    for row in rows:
        if row["status"] != "overlap":
            collapsed.append(row)
            continue
        kept = first.get(row["rule"])
        if kept is None:
            row["quotes"] = {row["judge"]: row.get("quote", "")}
            first[row["rule"]] = row
            collapsed.append(row)
            continue
        # A reader still needs what each judge said, so the row that stays
        # carries every judge's own words for the same offence.
        kept["quotes"][row["judge"]] = row.get("quote", "")
    rows = collapsed

    confirmed = sum(1 for r in rows if r["status"] in ("confirmed", "overlap"))
    return rows, confirmed, False, False


def build_entry(text, level, vocab, source=None, semantic=None):
    """Check one output, and return everything the page needs to draw it.

    `source` is the committed document this text rewrote. When given, and this
    text is not the source column itself, faithfulness.py compares the two:
    PSTE-A1 says accuracy defeats every other rule, so fact loss fails the
    verdict regardless of how clean the conformance findings are (PSTE-C6.3).

    `semantic` is this arm's judge output (see `semantic_findings`). Only its
    CONFIRMED rows may affect `pass`: low-agreement and rejected rows are audit
    material for a human, never a verdict input (semantic_lint.py's own
    docstring: "Treat every finding as a candidate that a person confirms, and
    never as a count to publish").

    A finding is COUNTABLE unless `pste_lint` marked it "arbitrated" (PSTE-N5,
    G7, G11, G12: rules that guess part of speech from a closed word list, which
    is never complete — see `pste_lint.ARBITRATED_RULES`). A countable finding
    fails `pass` on its own, same as always. An arbitrated one is only ever a
    CANDIDATE: it is still shown in `findings`, so a reader sees what the linter
    flagged, but it fails `pass` only when the judge confirms it — which, when
    the run judged this arm, arrives as a normal row in `semantic` under the
    same rule ID (semantic_lint.build_prompt asks the judge to confirm or
    reject each candidate through the existing "findings"/"considered" shape).
    That keeps this to the three existing gates rather than adding a fourth:
    an arbitrated finding gates through the semantic-confirmed path, not a
    parallel one.

    UNJUDGED is a fourth state, and the dangerous one: a cell whose judging
    call failed outright (run.py's semantic stage ran, but every pass for
    THIS cell errored — an API limit, most often) must never render, or
    verdict, the same as a cell the judge looked at and found clean. `pass`
    is forced False here, unconditionally, regardless of what the mechanical
    checker and faithfulness found — an unjudged cell has not earned a PASS,
    it has simply not been checked by 49 of the standard's 78 rules yet.

    SAMPLED_OUT is a cause of UNJUDGED, not a separate verdict: run.py's
    rotate-and-anchor sampling (see `judge_sample`) may deliberately never
    send this cell to the judge at all. `pass` is forced False here for the
    same reason as any other unjudged cell — this text has not been checked
    against the 52 semantic rules, so it cannot be claimed to PASS them,
    whether the gap is an error or a budget decision. What sampling changes is
    only how the reason reads: `sampledOut` marks this as "excluded by
    design," distinct from "the judge tried and failed," so a reader of the
    JSON or the page never mistakes a rationed run for a broken one.
    """
    if not text:
        return {"missing": True}
    result = pste_lint.check_text(text, level=level, vocab=vocab)
    findings = sorted(
        result["findings"], key=lambda f: (f.get("line") or 0, f.get("column") or 0)
    )
    for finding in findings:
        finding["offset"] = offset_of(text, finding.get("line"), finding.get("column"))
        finding["token"] = token_of(text, finding["offset"])
    countable = [f for f in findings if not f.get("arbitrated")]
    # spec/PSTE-1.md §15: a dropped fact (weight 1.0) and a missing hyphen
    # (weight 0.1) are not the same fault. Sum what pste_lint.add() already
    # attached to every finding, so the page never re-derives a weight.
    weighted = round(sum(f["weight"] for f in findings), 1)

    fidelity = None
    if source is not None and text is not source:
        fidelity = faithfulness.compare(source, text)

    clean_sentences = clean_sentence_rate(text, findings, result["sentences"])

    fact_loss = bool(fidelity) and not fidelity["faithful"]
    semantic_rows, semantic_confirmed, unjudged, sampled_out = semantic_findings(
        semantic, text
    )
    return {
        "missing": False,
        "unjudged": unjudged,
        "sampledOut": sampled_out,
        "pass": (
            not unjudged and not countable and not fact_loss
            and not semantic_confirmed
        ),
        "words": result["words"],
        "weighted": weighted,
        # A sentence is the unit PSTE itself counts (N1/N2 word limits, D2's six
        # sentences) and the unit a reader meets one at a time. Per-100-words has
        # no basis in the standard; this does.
        "sentences": result["sentences"],
        "cleanSentences": clean_sentences,
        "findings": findings,
        "html": mark_findings(text, findings),
        # Kept apart from `findings`: PSTE-A1 fact loss is a different failure
        # mode than a conformance rule, and the report shows it as its own
        # column so a clean-but-lossy doc reads differently from a
        # lossy-and-non-conforming one. See faithfulness.py's own limits note
        # (docstring) — this detects DROPPED tokens, not changed meaning.
        "factLoss": fact_loss,
        "fidelity": fidelity,
        # From the LLM judge (semantic_lint.py), kept apart from `findings`:
        # different origin (a model's read, not a regular expression) and
        # different reliability. Only `semanticConfirmed` counts toward `pass`;
        # every row, confirmed or not, is shown so a human can audit the judge.
        "semantic": semantic_rows,
        "semanticConfirmed": semantic_confirmed,
    }


def pass_stats(passes, level, vocab):
    """Findings for every pass of every arm, and the share that passed.

    Returns {arm: {"findings": [n, n, n], "passed": k, "of": 3, "rate": pct}}.
    `rate` is the share of PASSES that conform, and not a grade for the text.
    PSTE-1 §5.2 says a conformance count is not a measure of quality even where,
    as here, the harness is allowed to show one; a reader must read the work list
    rather than this number.
    """
    out = {}
    for arm, texts in passes.items():
        counts = [
            pste_lint.check_text(t, level=level, vocab=vocab)["total"] for t in texts
        ]
        if not counts:
            continue
        passed = sum(1 for n in counts if n == 0)
        out[arm] = {
            "findings": counts,
            "passed": passed,
            "of": len(counts),
            "rate": round(passed * 100 / len(counts)),
            "mean": round(sum(counts) / len(counts), 1),
        }
    return out


def run_identity(snapshot):
    """Everything that says WHICH run this page shows.

    Two results differ by the commit, the model, the pass count, and the corpus.
    A reader comparing two pages needs all of them, because a number that moved
    between runs means nothing until you know which input moved with it.
    """
    git = snapshot.get("git") or {}
    models = sorted(
        {
            (entry.get("author") or "").split(",")[0]
            for entry in snapshot["results"].values()
            if (entry.get("author") or "").startswith("claude")
        }
    )
    return {
        "commit": git.get("short", ""),
        "branch": git.get("branch", ""),
        "committed": (git.get("committed") or "")[:10],
        "subject": git.get("subject", ""),
        "documents": snapshot.get("document_count", len(snapshot["results"])),
        "passes": snapshot.get("passes", 1),
        "jobs": snapshot.get("jobs"),
        "failures": snapshot.get("failures", 0),
        "sourceModels": models,
        "controlText": snapshot.get("control_text", ""),
        # Per-stage call counts and wall-clock (run.py PART 1). Absent on a
        # result written before this existed; the page must not crash reading
        # a missing key on an older file, so this defaults to an empty dict.
        "stages": snapshot.get("stages") or {},
    }


def is_synthetic(pid):
    """A document generated about this project, rather than found in the wild.

    The corpus carries no dedicated field for this (see MANIFEST.yaml,
    corpus_generate.py): the `synth-` id prefix is the only marker, and
    corpus_generate.py's own self-test asserts every generated id has it. So the
    prefix is not a fallback guess, it is the existing contract.
    """
    return pid.startswith("synth-")


def overview(data, arms, anchor_docs=(), rotating_docs=()):
    """The matrix a reader wants at a glance: per document, per arm.

    For each cell: did it pass, how many findings, and how many DISTINCT rules it
    broke. The last one matters on its own. Twelve findings of one rule is a single
    lesson the skill failed to teach, and three findings of three rules is three.

    Totals are kept separately for real documents and synthetic ones. A synthetic
    document is a model's unconstrained answer about THIS project, and folding it
    into the headline number would measure this project's own prose alongside the
    real-world technical writing the eval exists to check. Real is the number that
    generalises, so it is reported as "totals"; synthetic stays visible as
    "totalsSynth" rather than hidden.

    `anchor_docs`/`rotating_docs` (from the snapshot's `judge_sample`, empty
    for an older result or a `--judge-all` run with no rotation) name a SECOND,
    independent split: which documents the judge actually looked at this run,
    and why. This crosses the real/synthetic axis rather than nesting inside
    it — `synth-evidence` is a default anchor AND synthetic at once — so it is
    kept as its own pair of totals ("totalsAnchor"/"totalsRotating") rather
    than folded into `totals`/`totalsSynth` as a third dimension of the same
    table. The two splits answer different questions: real/synthetic asks
    whether a finding generalises past this project's own prose; anchor/
    rotating asks whether the skill is improving everywhere or only on the
    two documents graded every single run — the definition of overfitting to
    the anchors. A row can and does appear in both breakdowns.
    """
    rows, totals, totals_synth, rule_counts = [], {}, {}, {}
    totals_anchor, totals_rotating = {}, {}
    anchor_docs, rotating_docs = set(anchor_docs), set(rotating_docs)
    for pid, entry in data.items():
        row = {"id": pid, "type": entry["category"], "cells": {},
               "synthetic": is_synthetic(pid),
               "anchor": pid in anchor_docs,
               "rotating": pid in rotating_docs}
        totals_for = totals_synth if row["synthetic"] else totals
        # A row lands in at most one of the two judging buckets: an anchor is
        # never also counted as rotating (run.py's `judge_sample` keeps the
        # sets disjoint by construction), and a document neither judged this
        # run contributes to neither — there is no semantic verdict to compare.
        judge_bucket = (
            totals_anchor if row["anchor"]
            else totals_rotating if row["rotating"]
            else None
        )
        for arm in arms:
            cell = entry["arms"].get(arm) or {}
            if cell.get("missing", True):
                row["cells"][arm] = None
                continue
            findings = cell.get("findings", [])
            rules = sorted({f["rule"] for f in findings})
            fact_loss = cell.get("factLoss", False)
            semantic_confirmed = cell.get("semanticConfirmed", 0)
            stats = (entry.get("passes") or {}).get(arm) or {}
            row["cells"][arm] = {
                # PSTE-C6.3: no fact loss is a precondition of PASS, not a
                # finding among the others. A clean-but-lossy cell must not
                # read the same as a plain pass. A CONFIRMED semantic finding
                # (from the LLM judge) fails the verdict the same way; a
                # low-agreement or rejected one never does. Read from `cell`
                # rather than recomputed here: build_entry already excludes an
                # unconfirmed ARBITRATED finding (PSTE-N5/G7/G11/G12) from the
                # verdict, and redoing the logic against the raw `findings`
                # count would silently drop that exclusion in this second copy.
                "pass": cell.get("pass", False),
                # UNJUDGED cells are the dangerous confusion this exists to
                # prevent: a document the judge never reached must render
                # differently from one it judged and found clean, or an
                # incomplete run reads as a perfect one. `pass` above is
                # already False for these (build_entry), so this only
                # controls how the cell is drawn.
                "unjudged": cell.get("unjudged", False),
                # A cell excluded by run.py's rotate-and-anchor sampling, not
                # one whose judge call failed. Both are `unjudged` (see
                # build_entry), but only this tells a reader the gap was a
                # deliberate budget decision rather than an error.
                "sampledOut": cell.get("sampledOut", False),
                "findings": len(findings),
                # spec/PSTE-1.md §15: not a quality score, a conformance count
                # weighted by what the standard says matters. A dropped fact
                # (1.0) and a missing hyphen (0.1) are not the same fault, and
                # this is the number that says so beside the raw count.
                "weighted": cell.get("weighted", 0),
                "rules": len(rules),
                "words": cell.get("words", 0),
                # PSTE counts by the sentence already (N1/N2, D2); this is the
                # same "clean sentences %" already used in conversation about
                # this eval, not a new metric invented for the page.
                "cleanSentences": cell.get("cleanSentences") or {"clean": 0, "of": 0, "rate": 0},
                # Kept separate from `findings`/`rules` on purpose: fact loss is
                # PSTE-A1 (accuracy), conformance findings are everything else.
                # The tradeoff the owner wants visible would collapse if this
                # were folded into the finding count.
                "factLoss": fact_loss,
                # Kept apart for the same reason: a different checker (a model,
                # not a regular expression) with different reliability. Only
                # the confirmed count is shown here; the full audit list (every
                # status, with its reason) lives on the document view.
                "semantic": len(cell.get("semantic") or []),
                "semanticConfirmed": semantic_confirmed,
                # Every pass of this document in this arm, and the share of them
                # that conform. Absent when the run made a single pass.
                "runs": stats.get("findings") or [],
                "passed": stats.get("passed"),
                "of": stats.get("of"),
                "rate": stats.get("rate"),
                "mean": stats.get("mean"),
            }
            cleanSentences = cell.get("cleanSentences") or {}

            def _tally(bucket):
                bucket["total"] += 1
                bucket["pass"] += 1 if cell.get("pass") else 0
                bucket["findings"] += len(findings)
                bucket["weighted"] += cell.get("weighted", 0)
                bucket["words"] += cell.get("words", 0)
                bucket["factLoss"] += 1 if fact_loss else 0
                bucket["semanticConfirmed"] += semantic_confirmed
                bucket["unjudged"] += 1 if cell.get("unjudged") else 0
                bucket["sampledOut"] += 1 if cell.get("sampledOut") else 0
                # Count every pass, so the footer rate rests on 42 runs, not 14.
                bucket["runPass"] += stats.get("passed") or 0
                bucket["runTotal"] += stats.get("of") or 0
                # Sentences, not documents: the rate the overview shows is
                # clean sentences over every sentence in the bucket, the same
                # unit PSTE itself counts in (N1/N2, D2), not an average of
                # per-document percentages.
                bucket["sentClean"] += cleanSentences.get("clean", 0)
                bucket["sentTotal"] += cleanSentences.get("of", 0)

            new_bucket = lambda: {
                "pass": 0, "total": 0, "findings": 0, "weighted": 0, "words": 0,
                "runPass": 0, "runTotal": 0, "factLoss": 0,
                "semanticConfirmed": 0, "unjudged": 0, "sampledOut": 0,
                "sentClean": 0, "sentTotal": 0,
            }
            bucket = totals_for.setdefault(arm, new_bucket())
            _tally(bucket)
            if judge_bucket is not None:
                jbucket = judge_bucket.setdefault(arm, new_bucket())
                _tally(jbucket)
            for finding in findings:
                per_rule = rule_counts.setdefault(finding["rule"], {})
                per_rule.setdefault(arm, 0)
                per_rule[arm] += 1
                per_rule.setdefault("message", finding["message"])
        rows.append(row)

    # Rank the rules by how often the LAST arm breaks them. That arm is the skill
    # under test, and the rule at the top is where the next edit belongs.
    target = arms[-1] if arms else ""
    ranked = sorted(
        (
            {
                "rule": rule,
                "message": counts.get("message", ""),
                "counts": {a: counts.get(a, 0) for a in arms},
            }
            for rule, counts in rule_counts.items()
        ),
        key=lambda r: (-r["counts"].get(target, 0), r["rule"]),
    )
    return {
        "rows": rows,
        "totals": totals,
        "totalsSynth": totals_synth,
        # The anchor/rotating split, independent of real/synthetic (see the
        # docstring). Empty dicts, not absent keys, when the snapshot carries
        # no `judge_sample` (an older result, or every arg empty) — the page
        # already handles an empty totals bucket the same way it handles a
        # zero-total real/synthetic one.
        "totalsAnchor": totals_anchor,
        "totalsRotating": totals_rotating,
        "rules": ranked,
        "target": target,
    }


def _semantic_for(entry, arm, texts, stage_ran):
    """`entry["semantic"][arm]` as `build_entry` expects it, with one backfill.

    A cell whose judge call failed outright has no key in `entry["semantic"]`
    at all — indistinguishable, on that one cell alone, from a run where the
    judging stage never happened (no credential, an older result). The
    difference only shows up by looking at the cell's SIBLINGS: `source` is
    never judged, but a cell with GENERATED text (`texts.get(arm)`), in a
    snapshot where the stage ran for other cells, and that still has no
    `semantic[arm]` entry, was judged for and came back with nothing. That is
    `unjudged`, not `None`. Real result: eval-2026-08-09-ae1315c4.json, where
    4 of 28 generated cells sat silent inside an otherwise-judged run.
    """
    semantic = (entry.get("semantic") or {}).get(arm)
    if semantic is not None:
        return semantic
    if arm != "source" and stage_ran and texts.get(arm):
        return {"unjudged": True, "error": "no judge output recorded"}
    return None


def render(snapshot, level, source=""):
    vocab = pste_lint.load_vocab()

    # Schema 2 carries the committed document beside its rewrites. Show it as the
    # first column: a rewrite means nothing without the text it rewrote.
    has_source = any(e.get("source") for e in snapshot["results"].values())
    columns = ["source"] if has_source else []
    columns += [a for a in ARM_ORDER if a != "source" and a in snapshot["arms"]]
    columns += [a for a in snapshot["arms"] if a not in columns]

    # Did the judging stage run for this snapshot at all? True when at least
    # one cell anywhere in the run carries judge output. Needed to backfill
    # `unjudged` for a result written BEFORE run.py recorded a failed judge
    # call as `{"unjudged": True}` (fixed alongside this check): in that older
    # shape a cell whose call failed outright has no `semantic[arm]` key at
    # all, identical to a cell from a run where judging never happened. The
    # two cases differ only by whether the STAGE ran for the surrounding run,
    # which sibling cells reveal even when this one cell stayed silent about
    # it.
    stage_ran = any(
        (e.get("semantic") or {}) for e in snapshot["results"].values()
    )

    data = {}
    for pid, entry in snapshot["results"].items():
        texts = dict(entry["outputs"])
        if entry.get("source"):
            texts["source"] = entry["source"]
        data[pid] = {
            "category": entry.get("type") or entry.get("category", ""),
            "title": entry.get("title", ""),
            "prompt": entry.get("prompt", ""),
            "attribution": entry.get("attribution", ""),
            "url": entry.get("url", ""),
            "author": entry.get("author", ""),
            "licence": entry.get("licence", ""),
            "licenceUrl": entry.get("licence_url", ""),
            "derivedLicence": entry.get("derived_licence", ""),
            "arms": {
                arm: build_entry(
                    texts.get(arm), level, vocab, source=entry.get("source"),
                    semantic=_semantic_for(entry, arm, texts, stage_ran),
                )
                for arm in columns
            },
            # Every pass, not only the one `outputs` kept. A model answers
            # differently each time, so one draw cannot tell a real change from
            # ordinary variance. `postmortem-chia-mempool` reached zero findings on
            # its second pass and not on the other two: a single number hides that
            # the arm can pass this document at all.
            "passes": pass_stats(entry.get("passes") or {}, level, vocab),
        }
    arms = columns

    git = snapshot.get("git") or {}
    payload = json.dumps(
        {
            "level": level,
            "arms": arms,
            "armNote": ARM_NOTE,
            "controlText": snapshot.get("control_text", ""),
            "source": source,
            "git": git,
            "run": run_identity(snapshot),
            "judgeSample": snapshot.get("judge_sample") or {},
            "overview": overview(
                data, arms,
                anchor_docs=(snapshot.get("judge_sample") or {}).get("anchor_docs", []),
                rotating_docs=(snapshot.get("judge_sample") or {}).get("rotating_docs", []),
            ),
            "results": data,
        }
    )
    # Name the tab after the result. A browser with several results open must not
    # show the same title on every tab.
    title = f"PSTE eval level {level}"
    if source:
        title += f" — {os.path.splitext(source)[0]}"

    return (
        page_template()
        .replace("__DATA__", payload)
        .replace("__DISCLAIMER__", html.escape(DISCLAIMER))
        .replace("__TITLE__", html.escape(title))
    )

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "report-template.html")


def page_template():
    """The page, as a file rather than a string in this module.

    Keeping the markup here made every edit to the page a diff against Python,
    and the page is not Python. `report-template.html` holds it, and this reads
    it at build time, so a change to the page needs no change to this file.
    """
    with open(TEMPLATE, encoding="utf-8") as fh:
        return fh.read()


def self_test():
    """Check the parts that can go wrong without an obvious symptom."""

    # A caller that passes `check_text`'s own findings has no `offset`, only a
    # line and a column. Reading `excerpt_offset` instead looks right and is
    # not: it counts from the start of the excerpt, so every finding in a
    # document lands in the first sentence and the rest read clean.
    _vocab = pste_lint.load_vocab()
    _text = "You should utilize the cache.\nThis sentence is fine.\n"
    _found = pste_lint.check_text(_text, level=3, vocab=_vocab)["findings"]
    assert _found, "the first sentence must break a rule for this test to mean anything"
    assert not any("offset" in f for f in _found), \
        "check_text does not place a finding in the document; if it now does, " \
        "this test is checking nothing"
    _prose = pste_lint.strip_non_prose(_text)
    _n = len(pste_lint.split_sentences(_prose, mark_list_items=True))
    _rate = clean_sentence_rate(_text, _found, _n)
    assert _rate["rate"] < 100, f"every sentence read clean: {_rate}"
    assert _rate["clean"] < _n, _rate
    # A finding nobody can place is a fault in the caller, not a clean document.
    try:
        clean_sentence_rate(_text, [{"rule": "PSTE-A1"}], _n)
    except ValueError:
        pass
    else:
        raise AssertionError("an unplaceable finding must not read as clean")

    # One offence, one row. A rule every judge confirmed arrived once per judge
    # and counted once per judge, so agreement inflated the total: the stronger
    # the agreement, the worse the count.
    for names in (("opus", "sonnet"), ("opus", "sonnet", "haiku")):
        many = {
            name: {"summary": [{"rule": "PSTE-A1", "status": "confirmed",
                                "quote": "x", "seen_in": 3, "of": 3}]}
            for name in names
        }
        rows, confirmed, _unjudged, _sampled = judge_overlap(many, "x")
        assert len(rows) == 1, f"{len(names)} judges agreeing gave {len(rows)} rows"
        assert confirmed == 1, f"{len(names)} judges agreeing counted {confirmed}"
        assert set(rows[0]["judges"]) == set(names), rows[0]
    vocab = pste_lint.load_vocab()

    # The template is a plain file now, and a plain file has no Python escapes.
    # Extracting it from a string literal turned `\\u2014` into a real em dash and
    # then into a stray backslash, and neither shows up until a person reads the
    # page. Every placeholder must survive, and the markup must still be a page.
    template = page_template()
    for placeholder in ("__DATA__", "__DISCLAIMER__", "__TITLE__"):
        assert placeholder in template, placeholder
    assert template.startswith("<!doctype html>"), template[:40]
    assert template.rstrip().endswith("</html>"), template[-40:]
    # A literal backslash followed by a character that a Python escape would have
    # eaten means the extraction mangled the file.
    for bad in ("\\—", "\\·"):
        assert bad not in template, f"mangled escape near {bad!r}"

    # A finding marks its own token, not the whole line.
    text = "The parser is robust."
    entry = build_entry(text, 3, vocab)
    assert not entry["pass"], entry
    assert "<mark" in entry["html"], entry["html"]
    assert "robust</mark>" in entry["html"], entry["html"]

    # Clean text carries no mark, and reports a pass.
    clean = build_entry("Set the flag. The parser reads the file.", 2, vocab)
    assert clean["pass"], clean["findings"]
    assert "<mark" not in clean["html"]
    # A clean document's weighted total is 0, and every one of its sentences
    # counts as clean.
    assert clean["weighted"] == 0, clean["weighted"]
    assert clean["cleanSentences"] == {"clean": 2, "of": 2, "rate": 100.0}, clean

    # WEIGHTED TOTAL (spec/PSTE-1.md §15): a straight sum of what pste_lint
    # already attached to each finding, never a second lookup. "robust" alone
    # trips one rule with a known, non-1.0 weight — this is a regression on
    # the sum itself, not on pste_lint's table.
    one_rule = entry["findings"][0]
    assert entry["weighted"] == round(one_rule["weight"], 1), (entry["weighted"], one_rule)
    assert entry["weighted"] > 0, entry["weighted"]

    # CLEAN SENTENCES: one sentence breaks a rule, the other does not, so
    # exactly one of the two counts as clean — never a fractional blend, and
    # never "both dirty" just because the document as a whole fails.
    two_sentence = "The parser is robust. Set the flag."
    mixed = build_entry(two_sentence, 3, vocab)
    assert mixed["cleanSentences"]["of"] == 2, mixed["cleanSentences"]
    assert mixed["cleanSentences"]["clean"] == 1, mixed["cleanSentences"]
    assert mixed["cleanSentences"]["rate"] == 50.0, mixed["cleanSentences"]

    # Overlapping findings must not produce nested marks, which would break the
    # page. Every mark opens after the last one closed.
    many = build_entry(
        "Going forward, we will be leveraging a very robust solution; "
        "it should utilize the cache.",
        3,
        vocab,
    )
    depth = 0
    for piece in many["html"].split("<mark")[1:]:
        depth += 1
        assert depth == 1, "nested mark"
        depth -= piece.count("</mark>")
    assert many["html"].count("<mark") >= 3, many["html"]

    # Text that a reader supplies must not become markup.
    hostile = build_entry("<script>alert(1)</script> is robust.", 3, vocab)
    assert "<script>" not in hostile["html"], hostile["html"]
    assert "&lt;script&gt;" in hostile["html"]

    # A missing arm draws a note, and does not raise.
    assert build_entry(None, 2, vocab)["missing"]

    # PSTE-C6.3: fact loss FAILS the verdict even when conformance is clean.
    # "3 attempts" dropping to no count at all is a lost number, and the rest
    # of the sentence has nothing else pste_lint would flag.
    src = "The client retries 3 times. Wait 30 seconds between attempts."
    lossy = build_entry("The client retries. Wait between attempts.", 2, vocab, source=src)
    assert not lossy["pass"], lossy
    assert lossy["factLoss"], lossy
    assert not lossy["findings"], "this case must be clean but lossy, not both"

    # A faithful rewrite of the same source, even a shorter one, still passes.
    faithful = build_entry("The client makes 3 attempts. Wait 30 seconds between.", 2, vocab, source=src)
    assert faithful["pass"], faithful
    assert not faithful["factLoss"], faithful

    # The source column is never compared against itself.
    self_cmp = build_entry(src, 2, vocab, source=src)
    assert self_cmp["fidelity"] is None, self_cmp

    # SEMANTIC FINDINGS. Only a CONFIRMED row may fail the verdict; a
    # low-agreement or rejected row is audit material and must still appear.
    clean_mech = "Set the flag. The parser reads the file."
    sem_confirmed = build_entry(
        clean_mech, 2, vocab,
        semantic={"summary": [
            {"rule": "PSTE-A1", "quote": "x", "problem": "dropped a fact",
             "fix": "say it", "confidence": "high", "reason": "the count vanished",
             "seen_in": 4, "of": 5, "agreement": 0.8, "status": "confirmed",
             "line": 1, "column": 1, "located": True},
            {"rule": "PSTE-V6", "quote": "pay attention to", "problem": "",
             "fix": "", "confidence": "", "reason": "attention has no underlying verb",
             "seen_in": 2, "of": 5, "agreement": 0.4, "status": "rejected",
             "line": None, "column": None, "located": False},
        ]},
    )
    assert not sem_confirmed["pass"], sem_confirmed  # mechanically clean, judge fails it
    assert sem_confirmed["semanticConfirmed"] == 1, sem_confirmed
    assert len(sem_confirmed["semantic"]) == 2, "rejected rows must still be reported"
    statuses = {r["rule"]: r["status"] for r in sem_confirmed["semantic"]}
    assert statuses == {"PSTE-A1": "confirmed", "PSTE-V6": "rejected"}, statuses
    rejected_row = next(r for r in sem_confirmed["semantic"] if r["rule"] == "PSTE-V6")
    assert "no underlying verb" in rejected_row["reason"], rejected_row

    # A low-agreement row alone must not fail the verdict.
    sem_low = build_entry(
        clean_mech, 2, vocab,
        semantic={"summary": [
            {"rule": "PSTE-D6", "quote": "x", "problem": "p", "fix": "f",
             "confidence": "low", "reason": "r", "seen_in": 1, "of": 5,
             "agreement": 0.2, "status": "low-agreement", "line": 1, "column": 1,
             "located": True},
        ]},
    )
    assert sem_low["pass"], sem_low
    assert sem_low["semanticConfirmed"] == 0, sem_low

    # MULTI-JUDGE OVERLAP. Two judges on the same text: PSTE-A1 confirmed by
    # BOTH (the trustworthy set) and PSTE-D6 confirmed by only one. Built from
    # two small fixed inputs, no model call — this is the overlap arithmetic
    # itself, not a live judge run.
    def made(rule, quote, status, seen=3, of=5):
        return {"rule": rule, "quote": quote, "problem": "p", "fix": "f",
                "confidence": "high", "reason": "r", "seen_in": seen, "of": of,
                "agreement": round(seen / of, 2), "status": status,
                "line": 1, "column": 1, "located": True}

    two_judges = build_entry(
        clean_mech, 2, vocab,
        semantic={"by_judge": {
            "claude-opus-5": {"summary": [
                made("PSTE-A1", "a dropped fact", "confirmed"),
                made("PSTE-D6", "out of order", "confirmed"),
            ]},
            "claude-sonnet-5": {"summary": [
                made("PSTE-A1", "a missing number", "confirmed"),
            ]},
        }},
    )
    rows = {r["rule"]: r for r in two_judges["semantic"]}
    a1 = rows["PSTE-A1"]
    d6 = rows["PSTE-D6"]
    # Both judges confirmed PSTE-A1 independently: OVERLAP, the trustworthy
    # set, named by every judge that agreed. ONE row, because one offence is
    # one offence however many judges saw it.
    assert a1["status"] == "overlap", a1
    assert set(a1["judges"]) == {"claude-opus-5", "claude-sonnet-5"}, a1
    assert len([r for r in two_judges["semantic"]
                if r["rule"] == "PSTE-A1"]) == 1, two_judges["semantic"]
    # Only one judge confirmed PSTE-D6: stays plain "confirmed", not overlap.
    assert d6["status"] == "confirmed", d6
    assert d6["judges"] == ["claude-opus-5"], d6
    # A reader still needs what EACH judge said about the same offence, so the
    # row that stays carries every judge's own words.
    assert a1["quotes"]["claude-opus-5"] == "a dropped fact", a1
    assert a1["quotes"]["claude-sonnet-5"] == "a missing number", a1
    # Overlap rows count toward the verdict the same as plain confirmed ones.
    # Two offences, not three. A1 is one finding two judges agreed on, and D6
    # is one finding a single judge confirmed. Counting A1 once per judge made
    # agreement look like more faults.
    assert two_judges["semanticConfirmed"] == 2, two_judges
    assert not two_judges["pass"], two_judges

    # A judge that FAILED OUTRIGHT must not count against overlap: "both
    # judges that answered agreed" stays true even when a third named model
    # never produced a row at all.
    one_failed = build_entry(
        clean_mech, 2, vocab,
        semantic={"by_judge": {
            "claude-opus-5": {"summary": [made("PSTE-A1", "x", "confirmed")]},
            "claude-sonnet-5": {"summary": [made("PSTE-A1", "y", "confirmed")]},
            "claude-haiku-5": {"unjudged": True, "error": "rate limited"},
        }},
    )
    a1_rows = [r for r in one_failed["semantic"] if r["rule"] == "PSTE-A1"]
    assert all(r["status"] == "overlap" for r in a1_rows), a1_rows
    assert all(set(r["judges"]) == {"claude-opus-5", "claude-sonnet-5"} for r in a1_rows)

    # EVERY judge failing must read as UNJUDGED, the same as a single-judge
    # cell whose one call failed — never as "judged and clean".
    all_failed = build_entry(
        clean_mech, 2, vocab,
        semantic={"by_judge": {
            "claude-opus-5": {"unjudged": True, "error": "rate limited"},
            "claude-sonnet-5": {"unjudged": True, "error": "timed out"},
        }},
    )
    assert all_failed["unjudged"] is True, all_failed
    assert not all_failed["pass"], all_failed

    # SINGLE-JUDGE OUTPUT MUST RENDER EXACTLY AS IT DOES TODAY. `by_judge`
    # absent entirely (the flat `{"summary": [...]}` shape) must produce rows
    # with no `judge`/`judges` key at all, so the page's existing single-judge
    # rendering needs no branch.
    single = build_entry(
        clean_mech, 2, vocab,
        semantic={"summary": [made("PSTE-A1", "x", "confirmed")]},
    )
    assert "judge" not in single["semantic"][0], single["semantic"][0]
    assert "judges" not in single["semantic"][0], single["semantic"][0]
    assert single["semantic"][0]["status"] == "confirmed", single["semantic"][0]

    # No semantic data at all (judge never ran) must not crash, and must not
    # fabricate a verdict-affecting finding.
    no_sem = build_entry(clean_mech, 2, vocab, semantic=None)
    assert no_sem["pass"] and no_sem["semantic"] == [], no_sem

    # UNJUDGED. run.py's judging stage ran, but this one cell's judge call
    # failed outright (an API limit) and produced no result. This is a
    # different thing from `semantic=None` above: the stage ran, this cell
    # just never got an answer. Regression for the incomplete run that
    # reported `failures: 0` while 4 of 28 cells sat empty and silent — a
    # cell like this must FAIL, must say so with its own `unjudged` flag, and
    # must not be confusable with a clean pass on the mechanically-perfect
    # text it wraps.
    unjudged = build_entry(
        clean_mech, 2, vocab,
        semantic={"unjudged": True, "error": "rate limited"},
    )
    assert unjudged["unjudged"] is True, unjudged
    assert not unjudged["pass"], "an unjudged cell must never register as PASS"
    assert unjudged["semantic"] == [] and unjudged["semanticConfirmed"] == 0, unjudged
    # And the matrix (overview) must carry the same flag through per-cell, not
    # just the document-detail shape above.
    ov = overview({"d": {
        "category": "c", "arms": {"control": unjudged}, "passes": {},
    }}, ["control"])
    assert ov["rows"][0]["cells"]["control"]["unjudged"] is True, ov
    assert ov["rows"][0]["cells"]["control"]["pass"] is False, ov
    assert ov["totals"]["control"]["unjudged"] == 1, ov["totals"]

    # SAMPLED_OUT (run.py's rotate-and-anchor judge sampling). A cell that was
    # never SENT to the judge — a deliberate coverage decision — must still be
    # `unjudged` (it has not been checked against the 52 semantic rules, so it
    # cannot claim PASS), but must carry its own `sampledOut` flag so it is
    # never confused with a cell whose judge call was made and failed. That
    # confusion is exactly the bug commit 85fe062 fixed for the other case;
    # sampling must not reopen the same hole with a different cause.
    sampled_out = build_entry(
        clean_mech, 2, vocab,
        semantic={"unjudged": True, "sampled_out": True,
                  "error": "not selected for judging this run"},
    )
    assert sampled_out["unjudged"] is True, sampled_out
    assert sampled_out["sampledOut"] is True, sampled_out
    assert not sampled_out["pass"], "a sampled-out cell must never register as PASS"

    # A judge-call FAILURE must NOT be mislabelled sampledOut. The two causes
    # of `unjudged` must stay distinguishable, not just presentable.
    assert unjudged["sampledOut"] is False, unjudged

    # The matrix carries `sampledOut` through per-cell, same as `unjudged`,
    # and totals it separately from a genuine judge failure.
    ov2 = overview({"d": {
        "category": "c",
        "arms": {"control": sampled_out, "pste": unjudged},
        "passes": {},
    }}, ["control", "pste"])
    assert ov2["rows"][0]["cells"]["control"]["sampledOut"] is True, ov2
    assert ov2["rows"][0]["cells"]["pste"]["sampledOut"] is False, ov2
    assert ov2["totals"]["control"]["sampledOut"] == 1, ov2["totals"]
    assert ov2["totals"]["pste"]["sampledOut"] == 0, ov2["totals"]
    # Both still count toward `unjudged`, since neither was actually checked.
    assert ov2["totals"]["control"]["unjudged"] == 1, ov2["totals"]
    assert ov2["totals"]["pste"]["unjudged"] == 1, ov2["totals"]

    # ANCHOR/ROTATING TOTALS, independent of and crosscutting real/synthetic.
    # `synth-evidence` is both a default anchor AND synthetic, so this checks
    # a document can land in both breakdowns without one overwriting the
    # other, and that a document judged by neither sampling bucket (here,
    # "other-doc" was not selected this run) contributes to neither total.
    judged_entry = {
        "category": "c",
        "arms": {"control": build_entry(clean_mech, 2, vocab)},
        "passes": {},
    }
    other_entry = {
        "category": "c",
        "arms": {"control": build_entry(clean_mech, 2, vocab)},
        "passes": {},
    }
    ov3 = overview(
        {"synth-evidence": judged_entry, "other-doc": other_entry},
        ["control"],
        anchor_docs=["synth-evidence"],
        rotating_docs=[],
    )
    anchor_row = next(r for r in ov3["rows"] if r["id"] == "synth-evidence")
    other_row = next(r for r in ov3["rows"] if r["id"] == "other-doc")
    assert anchor_row["anchor"] is True and anchor_row["synthetic"] is True, anchor_row
    assert other_row["anchor"] is False, other_row
    assert ov3["totalsAnchor"]["control"]["total"] == 1, ov3["totalsAnchor"]
    # "synth-evidence" is synthetic, so it totals under `totalsSynth`, not
    # `totals` — the real/synthetic split does not change because a document
    # is also an anchor. "other-doc" is real, and was not sampled: it counts
    # in `totals` but in neither `totalsAnchor` nor `totalsRotating` — the
    # sampling split is independent of the real/synthetic one, not nested
    # inside it.
    assert ov3["totalsSynth"]["control"]["total"] == 1, ov3["totalsSynth"]
    assert ov3["totals"]["control"]["total"] == 1, ov3["totals"]
    assert "control" not in ov3["totalsRotating"] or \
        ov3["totalsRotating"]["control"]["total"] == 0

    # OVERVIEW TOTALS CARRY THE WEIGHTED SUM AND THE SENTENCE COUNT THROUGH,
    # per cell and summed into the bucket — not just the raw finding count.
    # Two documents, one dirty ("robust", weight below 1.0) and one clean, so
    # the bucket's weighted total is exactly the dirty one's weight, and the
    # sentence total is exactly 2 + 2 with only 3 of the 4 clean.
    dirty_entry = {
        "category": "c",
        "arms": {"control": build_entry("The parser is robust.", 2, vocab)},
        "passes": {},
    }
    clean_entry = {
        "category": "c",
        "arms": {"control": build_entry(clean_mech, 2, vocab)},
        "passes": {},
    }
    ov4 = overview({"dirty": dirty_entry, "clean": clean_entry}, ["control"])
    dirty_cell = next(r for r in ov4["rows"] if r["id"] == "dirty")["cells"]["control"]
    assert dirty_cell["weighted"] == dirty_entry["arms"]["control"]["weighted"], dirty_cell
    assert dirty_cell["weighted"] > 0, dirty_cell
    assert dirty_cell["cleanSentences"]["of"] == 1, dirty_cell
    bucket = ov4["totals"]["control"]
    assert bucket["weighted"] == dirty_cell["weighted"], bucket
    assert bucket["sentTotal"] == 1 + 2, bucket  # 1 sentence + 2 sentences
    assert bucket["sentClean"] == 0 + 2, bucket  # the dirty one's sentence is not clean

    # ARBITRATED FINDINGS (PSTE-N5/G7/G11/G12). Unconfirmed, a candidate must NOT
    # fail the verdict on its own — it is still visible in "findings" for a human
    # to read, but "pass" ignores it until the judge confirms it.
    arb_text = "Perform an analysis of the log file."  # trips PSTE-G7 only
    arb_unconfirmed = build_entry(arb_text, 2, vocab)
    assert any(f["rule"] == "PSTE-G7" for f in arb_unconfirmed["findings"]), \
        arb_unconfirmed["findings"]
    assert arb_unconfirmed["pass"], \
        "an unconfirmed arbitrated finding must not fail the verdict"

    # The SAME finding, but the judge confirmed it under the same rule ID: now it
    # must fail, through the ordinary semantic-confirmed gate and not a new one.
    arb_confirmed = build_entry(
        arb_text, 2, vocab,
        semantic={"summary": [
            {"rule": "PSTE-G7", "quote": "Perform an analysis", "problem": "p",
             "fix": "f", "confidence": "high", "reason": "analysis has an "
             "underlying verb, analyze", "seen_in": 3, "of": 5, "agreement": 0.6,
             "status": "confirmed", "line": 1, "column": 1, "located": True},
        ]},
    )
    assert not arb_confirmed["pass"], arb_confirmed
    assert arb_confirmed["semanticConfirmed"] == 1, arb_confirmed

    # A COUNTABLE finding (PSTE-X1, a semicolon) fails the verdict directly, with
    # no judge involved at all — the routing must not have touched this path.
    countable_text = "The build failed; the log shows why."
    countable = build_entry(countable_text, 2, vocab)
    assert any(f["rule"] == "PSTE-X1" for f in countable["findings"]), countable
    assert not countable["pass"], "a countable finding must fail directly"

    # NO DOUBLE-COUNTING. A confirmed arbitrated candidate is one entry in
    # `semantic` (from the judge) plus its one mechanical entry in `findings`
    # (from pste_lint) — never two independent semantic rows for the same hit.
    # PSTE-N5/G7/G11/G12 do not appear in semantic_lint.SEMANTIC_RULES, so the
    # judge cannot invent a second, unrelated report under the same rule ID
    # through its normal semantic-rule reasoning.
    import re as _re
    import semantic_lint as _semantic_lint
    semantic_ids = set(_re.findall(r"PSTE-[A-Z0-9.]+", _semantic_lint.SEMANTIC_RULES))
    assert not (pste_lint.ARBITRATED_RULES & semantic_ids), \
        "an arbitrated rule ID must never also be a SEMANTIC_RULES entry"
    assert arb_confirmed["semanticConfirmed"] == 1, \
        "one confirmation must not be double-counted"

    # THE OLDER SHAPE. The committed result this page ships with ran the judge
    # before `status`/`reason` existed on each row (2-3 passes, no gate). Those
    # rows must still render — as unconfirmed, since there is no `status` to
    # trust — and must never crash the build.
    old_shape = build_entry(
        clean_mech, 2, vocab,
        semantic={"summary": [
            {"rule": "PSTE-A1", "quote": "x", "seen_in": 2, "of": 2,
             "agreement": 1.0, "problem": "p", "fix": "f", "confidence": "high",
             "line": 1, "column": 1, "located": True},
        ]},
    )
    assert old_shape["pass"], "an old-shape row with no status must not fail the verdict"
    assert old_shape["semantic"][0]["status"] == "low-agreement", old_shape["semantic"]

    # THE MARK MUST LAND ON THE OFFENDING WORD.
    #
    # A finding carries `excerpt_offset`, which counts into the excerpt, and the
    # excerpt is a masked copy in which a code span became a placeholder of another
    # length. Using it against the real text puts every mark in the wrong place, and
    # a single-line example hides the fault because the two offsets agree there.
    # These cases use several lines and a code span, so they disagree.
    multi = (
        "Set the flag in `configure_the_cache_backend(x)` first.\n"
        "\n"
        "The parser is robust.\n"
    )
    entry = build_entry(multi, 3, vocab)
    hit = [f for f in entry["findings"] if f["token"] == "robust"]
    assert hit, [(f["rule"], f["token"]) for f in entry["findings"]]
    assert offset_of(multi, hit[0]["line"], hit[0]["column"]) == multi.index("robust")
    assert "<mark" in entry["html"] and "robust</mark>" in entry["html"]

    # Every mark must cover the word the offender list names, on every line.
    for finding in entry["findings"]:
        token = finding["token"]
        if token:
            assert f">{html.escape(token)}</mark>" in entry["html"], finding

    # A column past the end of a line must not silently mark a later line.
    assert offset_of("ab\ncd\n", 9, 1) is None
    assert offset_of("ab\ncd\n", 2, 1) == 3

    # This page is the evaluation harness. PSTE-1 §5.2 permits it to carry a rate,
    # unlike the distributed checker (PSTE-C8), so there is nothing left to ban
    # here — the old assertion banned literal substrings ("per_100w", "% conform")
    # that this page never emitted even under the withdrawn rule; it passed by
    # accident, not by testing anything real. What is real and worth guarding:
    # the not-a-quality-measure disclaimer must survive into the page, since §5.2
    # requires the harness to keep carrying that notice even while it shows a rate.
    page = render(
        {
            "arms": ["control", "pste"],
            "control_text": "x",
            "git": {"short": "abc12345", "branch": "main"},
            "results": {
                "t": {
                    "category": "c",
                    "prompt": "Write a thing.",
                    "outputs": {"control": text, "pste": "Set it."},
                }
            },
        },
        2,
        "eval-2026-08-03-abc12345.json",
    )
    assert "Conformance is not quality" in page, page
    assert "PSTE eval" in page
    for placeholder in ("__DATA__", "__DISCLAIMER__", "__TITLE__"):
        assert placeholder not in page, placeholder
    # Two results must not produce the same tab title.
    assert "<title>PSTE eval level 2 — eval-2026-08-03-abc12345</title>" in page
    # The page must say which result it came from, so a screenshot stays traceable.
    assert "abc12345" in page and "eval-2026-08-03" in page
    assert "Write a thing." in page

    # SCHEMA 2: the committed document appears as the first column, and the
    # licence notice travels with it. A rewrite shown without its source cannot
    # be judged, and a CC-BY rewrite shown without its notice breaks the licence.
    two = render(
        {
            "arms": ["control", "pste"],
            "control_text": "x",
            "document_count": 1,
            "git": {"short": "abc12345", "branch": "main"},
            "results": {
                "runbook-x": {
                    "type": "runbook",
                    "title": "A Runbook",
                    "source": "The parser is robust. Set the flag.",
                    "licence": "CC-BY-4.0",
                    "licence_url": "https://creativecommons.org/licenses/by/4.0/",
                    "url": "https://example.org/x",
                    "author": "Someone",
                    "attribution": "Rewritten from \"A Runbook\" by Someone, "
                    "used under CC-BY-4.0. This text is a modification.",
                    "outputs": {"control": "Set it.", "pste": "Set the flag."},
                }
            },
        },
        2,
        "eval-2026-08-03-abc12345.json",
    )
    data = json.loads(two.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert data["arms"][0] == "source", data["arms"]
    assert data["arms"] == ["source", "control", "pste"], data["arms"]
    entry = data["results"]["runbook-x"]
    assert entry["arms"]["source"]["words"] > 0, entry["arms"]["source"]
    assert entry["category"] == "runbook", entry
    assert "modification" in entry["attribution"], entry

    # The reader must be able to reach the original and the licence text. A
    # licence name with no link is a weaker credit than the licence asks for.
    for field, value in (
        ("url", "https://example.org/x"),
        ("licenceUrl", "https://creativecommons.org/licenses/by/4.0/"),
        ("author", "Someone"),
    ):
        assert entry[field] == value, (field, entry.get(field))

    # A SHARE-ALIKE SOURCE MUST MARK ITS REWRITES.
    #
    # A rewrite of a CC-BY-SA document is CC-BY-SA, not the licence of this
    # repository. The page has to say so on the column, because that is where
    # somebody copies the text from.
    sa = render(
        {
            "arms": ["control", "pste"],
            "control_text": "x",
            "git": {"short": "abc12345", "branch": "main"},
            "results": {
                "d": {
                    "type": "runbook",
                    "title": "T",
                    "source": "Set the flag.",
                    "licence": "CC-BY-SA-4.0",
                    "derived_licence": "CC-BY-SA-4.0",
                    "url": "https://example.org/x",
                    "author": "A",
                    "attribution": "... published under CC-BY-SA-4.0.",
                    "outputs": {"control": "Set it.", "pste": "Set the flag."},
                }
            },
        },
        2,
        "r.json",
    )
    sa_data = json.loads(sa.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert sa_data["results"]["d"]["derivedLicence"] == "CC-BY-SA-4.0", sa_data
    assert "licenceTag" in sa, "the page must tag each column with its licence"
    # The source is checked like any other text, so its findings are visible.
    assert not entry["arms"]["source"]["pass"], entry["arms"]["source"]

    # A result from before provenance existed must still render.
    old = render(
        {
            "arms": ["control"],
            "control_text": "x",
            "results": {"t": {"category": "c", "outputs": {"control": "Set it."}}},
        },
        2,
        "results.json",
    )
    assert "no provenance recorded" in old

    # BACKFILLING UNJUDGED FOR AN OLDER RESULT SHAPE. A result written before
    # run.py recorded a failed judge call as `{"unjudged": True}` has no
    # `semantic[arm]` key at all for a cell whose judge call failed outright —
    # the exact shape of eval-2026-08-09-ae1315c4.json. `render` must infer
    # `unjudged` from context: the stage ran for OTHER cells in the same
    # snapshot, this cell has generated text, and still has no judge entry.
    # A document with NO output for an arm (never generated) must not be
    # mislabelled `unjudged` — it stays `missing`, the existing state.
    incomplete = render(
        {
            "arms": ["control", "pste"],
            "control_text": "x",
            "git": {"short": "ae1315c4", "branch": "main"},
            "results": {
                # This document's judge calls both failed silently (the bug).
                "synth-pr-description": {
                    "category": "synth",
                    "outputs": {"control": "Set the flag.", "pste": "Set it."},
                    # No "semantic" key at all for this document.
                },
                # A sibling document in the SAME run judged normally, which is
                # what makes the silence above inferable as a failure and not
                # "the stage never ran".
                "runbook-x": {
                    "category": "runbook",
                    "outputs": {"control": "Set the flag.", "pste": "Set it."},
                    "semantic": {
                        "control": {"summary": [], "runs": [[], [], [], [], []]},
                        "pste": {"summary": [], "runs": [[], [], [], [], []]},
                    },
                },
            },
        },
        2,
        "eval-2026-08-09-ae1315c4.json",
    )
    inc_data = json.loads(incomplete.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    silent = inc_data["results"]["synth-pr-description"]["arms"]
    assert silent["control"]["unjudged"] is True, silent["control"]
    assert not silent["control"]["pass"], silent["control"]
    assert silent["pste"]["unjudged"] is True, silent["pste"]
    judged = inc_data["results"]["runbook-x"]["arms"]
    assert judged["control"]["unjudged"] is False, judged["control"]
    assert judged["control"]["pass"], judged["control"]  # a real, clean judge result

    # A run where the judging stage never happened at all (no sibling has
    # semantic data) must NOT be inferred as unjudged — that is the existing,
    # pre-judge-stage state, and must not now start failing every arm.
    never_judged = render(
        {
            "arms": ["control"],
            "control_text": "x",
            "results": {"t": {"category": "c", "outputs": {"control": "Set it."}}},
        },
        2,
        "results.json",
    )
    nj_data = json.loads(never_judged.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert nj_data["results"]["t"]["arms"]["control"]["unjudged"] is False, \
        nj_data["results"]["t"]["arms"]["control"]

    print("report.py self-test: ok")
    return 0


def write_pages(snapshot, result_path, levels=(2,)):
    """Write a page for each level beside the result, and return the paths.

    `run.py` calls this so a run produces its page without a second command.
    """
    written = []
    for level in levels:
        out = os.path.splitext(result_path)[0] + f"-level{level}.html"
        page = render(snapshot, level, os.path.basename(result_path))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(page)
        written.append(out)
    return written


def main():
    ap = argparse.ArgumentParser(
        description="Build an HTML page that shows the eval snapshot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--snapshot", default=None, help="a result file. Defaults to the newest."
    )
    ap.add_argument("--out", default=None, help="defaults to the result name, .html")
    ap.add_argument("--level", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    path = provenance.resolve(args.snapshot)
    if not path or not os.path.exists(path):
        print("no result found. Run: python3 evals/run.py", file=sys.stderr)
        return 2

    with open(path, encoding="utf-8") as fh:
        snapshot = json.load(fh)

    # The page sits beside the result it came from, and carries its name, so a
    # directory of results produces a directory of pages that still match.
    out = args.out or os.path.splitext(path)[0] + f"-level{args.level}.html"

    page = render(snapshot, args.level, os.path.basename(path))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"wrote {out}")
    print(f"  {provenance.describe_result(snapshot, path)}, level {args.level}")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
