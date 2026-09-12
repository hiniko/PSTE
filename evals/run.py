#!/usr/bin/env python3
"""Rewrite every corpus document with each arm, judge the rewrites, and save a
dated result with its report page.

    python3 evals/run.py                 # judges the anchors + a rotating sample
    python3 evals/run.py --limit 2       # a quick check
    python3 evals/run.py --only runbook-postgres-failover
    python3 evals/run.py --judge-all --judge-passes 5   # the full publication run

JUDGE SAMPLING

Generation and the mechanical checker (pste_lint.py, free, local) always cover
every document. Judging is the expensive half, so by default it covers only two
fixed ANCHOR documents (loop-over-loop comparability) plus a ROTATING slice
(coverage, and a check against overfitting to the anchors). `--anchor-docs` and
`--rotating-count` change the sample; `--judge-all` bypasses it. See
`judge_sample`'s docstring for how the rotation stays deterministic.

WHAT THIS MEASURES

Every arm rewrites the SAME committed document, so the content is fixed and only
the form changes. Three texts exist for each document:

    source     the real document, committed in evals/corpus/. Nothing generates it.
    control    a rewrite, asked for plainly: "Rewrite this document to be simpler
               to read." No rules, no guidance.
    pste       a rewrite, with the skill.

The comparison that matters is `pste` against `control`. Both arms were asked for
the same outcome, so the skill is the only difference between them. A skill that
cannot beat a plain request for the same thing has not earned its complexity.

The source document is the control for accuracy. `faithfulness.py` reports what
each rewrite dropped, which is the check that guards rule PSTE-A1.

WHAT THIS REPLACED, AND WHY

An earlier version gave each arm a one-line brief and asked it to WRITE a document.
That measured nothing. Each arm invented different content, so content and form
moved together and neither could be isolated: for one brief the three arms produced
310, 239, and 741 words of different material. It also left `faithfulness.py` with
no source to compare against.

This calls the `claude` CLI, so it costs money and takes minutes. Each run writes
one self-contained file:

    evals/results/eval-2026-08-03-3f9a1b7c.json

The name carries the date and the commit that produced the run, so two results
compare directly. The file holds the outputs, the prompts that produced them, and
the provenance, so it stays readable after the repository moves on.

A RUN REFUSES ON A DIRTY TREE

The commit in the name identifies the inputs: the skill prompt, the prompt set, the
standard, and the checker. That identity holds only when the tree matches the
commit. An uncommitted edit to SKILL.md would change the result while the commit
stayed the same, so two results would carry one name and differ. `provenance.py`
refuses in that case, and the refusal is what makes the name mean something.

SPEED

Every call is independent: each starts from the same committed source and shares no
state with any other. `--jobs` runs that many at a time, and 24 is the default. A
container costs about 0.4 seconds to start and 132 MB to hold, against a call that
takes 30 to 300 seconds, so the parallelism is what decides how long a run takes.
The judging stage divides the same budget between the texts and the passes of one
text, rather than judging one text at a time.

`--passes` repeats each rewrite. A model answers differently every time, so a single
pass cannot tell a real change in the skill from ordinary variance. Every pass is
kept, so a reader sees the spread instead of trusting one draw.
"""

import argparse
import collections
import concurrent.futures
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import corpus  # noqa: E402
import faithfulness  # noqa: E402
import provenance  # noqa: E402
import pste_lint  # noqa: E402
import semantic_lint  # noqa: E402

RESULTS_DIR = os.path.join(ROOT, "evals", "results")

# The control asks for the same outcome as the skill, with no guidance on how to
# reach it. That is the comparison that matters: a skill has to beat asking plainly.
# Against no instruction at all, any instruction wins, and the result says nothing.
CONTROL_TEXT = "Rewrite this document to be simpler to read."

# Both arms receive the same task. Only the system prompt differs, so the skill is
# the single variable between them.
TASK = (
    "Rewrite the document below.\n\n"
    "Keep every fact, number, unit, identifier, warning, and step. Do not add\n"
    "information, and do not remove information. Return the rewritten document\n"
    "only, with no preamble and no commentary.\n\n"
    "--- BEGIN DOCUMENT ---\n{document}\n--- END DOCUMENT ---"
)


# THE FIX PASS. Measured on the full corpus: the skill's one-pass output had 179
# findings and 88.3% clean sentences. Handing the model its own draft plus the
# mechanical checker's findings and asking it to fix only what is named dropped
# that to 45 findings and 96.5% clean. A control experiment proved the LIST is
# what does the work, not a second look: asking for a revision with no findings
# attached moved almost nothing (179 -> 175).
#
# "do not shorten... do not summarise" is load-bearing. An earlier wording
# without it let the model summarise a 767-word document to 39 words, which
# scores perfectly on the mechanical checker while destroying the document.
FIX_PROMPT = (
    "You wrote the document below. A checker has since read it and found the "
    "faults listed after it. This is NOT a rewrite: change only what a listed "
    "fault names, and leave every other sentence exactly as it stands.\n\n"
    "Accuracy defeats every other rule. Keep every fact, number, unit, "
    "condition and warning exactly as it stands. Do not shorten the document, "
    "do not summarise it, and do not add new material. Return the complete "
    "document and nothing else.\n\n"
    "--- BEGIN DOCUMENT ---\n{document}\n--- END DOCUMENT ---\n\n"
    "--- FAULTS ---\n{faults}\n--- END FAULTS ---"
)


def format_faults(findings):
    """One line per finding, `- RULE: message`, with the excerpt indented below.

    This is the only new information the fix pass gets over the plain "revise
    this" ask, and the control experiment (179 -> 175 findings with no list)
    is what proved the list is the mechanism, not the second look.
    """
    lines = []
    for f in findings:
        lines.append(f"- {f['rule']}: {f['message']}")
        lines.append(f"    {f['excerpt']}")
    return "\n".join(lines)


# THE MODEL, PINNED. Every call here used to inherit the CLI default, which
# reads from the operator's own settings and can be anything, Fable included.
# A run that does not pin its model measures whatever the operator's machine
# happened to default to that day, and the result does not say which.
#
# Sonnet, not Opus or Fable: generation is the arm under test, and a rewrite is
# the task a normal user runs. Testing the subject on the most expensive model
# available answers a different question than "does the skill help the model a
# user actually reaches for".
MODEL_GENERATION = "claude-sonnet-5"

# Calls to run at a time. Measured at 132 MB per container, so 24 is about
# 3 GB of the 7.7 GB Docker holds. The real ceiling is the API, not the machine.
JOBS_DEFAULT = 24


# JUDGE SAMPLING. Judging is the expensive half (5 passes x 28 cells = 140+
# calls), and repeated runs during skill work exhausted the API budget.
# Generation and the mechanical checker (pste_lint.py, free, local) still cover
# every document; only the judge is rationed.
#
# Two ANCHOR documents are judged every run, so a reader can compare one run to
# the next on the same ground. `runbook-cassandra-repair` is the real document
# with the most findings and so the most headroom to improve. It replaced
# `migration-django-upgrade`, which was retired from the corpus: its opening was
# a reStructuredText title block, which made it a poor showcase, and it was the
# weakest document in the set to read a before-and-after from.
#
# The synthetic anchor was `synth-evidence`, retired along with the other four
# self-referential synth-* documents (see evals/corpus_generate.py: those five
# were all questions about this repository, one subject in one vocabulary, and
# that narrowness was confounded with AI-authorship in the eval's own numbers).
# `synth-prometheus-query-basics` replaces it: a real, external, permissively
# licensed system with plenty of concrete facts (PromQL syntax, semantics) for a
# rewrite to get right or wrong, which is what makes a document worth anchoring
# on. This is a module constant, not a hardcoded branch, so changing the anchors
# needs no code change — edit this list or pass `--anchor-docs`.
ANCHOR_DOCS_DEFAULT = ["synth-prometheus-query-basics", "runbook-cassandra-repair"]

# Non-anchor documents judged alongside the anchors each run, for coverage and
# to catch the skill overfitting to the two anchors specifically.
ROTATING_COUNT = 3


def judge_sample(document_ids, anchors, rotating_count, rotation_offset):
    """Which documents get judged this run, and why.

    Returns a dict: `anchors` (judged every run), `rotating` (this run's
    slice), `judged` (the union, in document order), `rotation_offset` (the
    value actually used, echoed back so the result is self-describing).

    ROTATION IS DETERMINISTIC, NOT RANDOM. `rotation_offset` is not drawn from
    `random` — a random pick cannot be reproduced from the result file alone,
    and a reader could never tell whether a change in the report came from the
    skill or from a different set of documents landing in the sample. Instead
    the caller derives the offset from something stable and advancing (see
    `rotation_offset_from_commit`): the same configuration re-run against the
    same commit judges the same documents, and a later commit advances to a
    different slice, so 14 documents get covered across a handful of runs
    instead of staying frozen on whichever 3 came first.

    The rotating pool excludes the anchors, sorts what is left for a stable
    order, and takes `rotating_count` documents starting at `rotation_offset`,
    wrapping around. Slicing a sorted list, rather than hashing each id
    independently, is what makes "3 consecutive documents" an easy thing for a
    reader to audit by eye against the stored offset.
    """
    anchors = [a for a in anchors if a in document_ids]
    pool = sorted(d for d in document_ids if d not in anchors)
    if not pool or rotating_count <= 0:
        rotating = []
        offset = 0
    else:
        offset = rotation_offset % len(pool)
        rotating = [pool[(offset + i) % len(pool)] for i in range(min(rotating_count, len(pool)))]
    judged = [d for d in document_ids if d in anchors or d in rotating]
    return {
        "anchors": anchors,
        "rotating": rotating,
        "judged": judged,
        "rotation_offset": offset,
    }


def rotation_offset_from_commit(commit):
    """Turn a commit hash into a stable, advancing rotation offset.

    WHY THE COMMIT. It is already the thing that names a result (see
    `result_path`), it changes every time the code under test changes, and it
    needs no extra bookkeeping file to stay in sync. Hashing it into an integer
    gives an offset that is fixed for any one commit (so re-running the same
    commit reproduces the same sample — required for `judge_sample`'s
    contract) and different for the next one (so the rotation actually moves
    instead of parking on the same 3 documents forever). This is simpler than
    a counter file, which would need its own persistence and could drift from
    the results directory it is meant to describe.
    """
    digest = hashlib.sha256((commit or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def judge_workers(jobs, targets):
    """Split the worker budget between the texts and the passes of one text.

    Two pools nest here: the texts judged at the same time, and inside each of
    those, the passes of that text. Giving both pools `jobs` workers would start
    `jobs * jobs` containers. Returns (texts at a time, passes at a time), whose
    product never exceeds `jobs`.

    One text still gets the whole budget for its passes, so judging a single file
    is as parallel as it ever was.
    """
    text_jobs = max(1, min(jobs, targets))
    return text_jobs, max(1, jobs // text_jobs)


def result_path(info, directory=RESULTS_DIR):
    """Name a result after the day it ran and the commit that produced it.

    The date comes from the commit and not from the clock, so the same commit
    always produces the same name, and a result stays reproducible.
    """
    day = (info.get("committed") or "")[:10]
    if not day:
        day = datetime.date.today().isoformat()
    return os.path.join(directory, f"eval-{day}-{info['short']}.json")


def load_skill():
    with open(os.path.join(ROOT, "skill", "SKILL.md"), encoding="utf-8") as fh:
        text = fh.read()
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :].lstrip()
    return text


def arms():
    """The two arms. The source document is the third text, and nothing generates it.

    There is no `baseline` arm any more. An arm with no instruction measured the
    difference between asking and not asking, which is not the question. The skill
    has to beat a plain request for the same outcome.
    """
    skill = load_skill()
    return {
        "control": CONTROL_TEXT,
        "pste": f"{CONTROL_TEXT}\n\n{skill}",
    }


def gate_fix(draft, fixed):
    """THE FIDELITY GATE. Keep the fix only if it did not cost a fact.

    PSTE-A1: accuracy defeats every other rule. Measured ungated, 2 of 14
    documents lost a fact (a dropped negation, a missing `0`) while scoring
    better on form — the exact failure the standard most fears, and the
    mechanical checker cannot see it (fewer words break fewer of ITS rules).
    `faithfulness.compare` can.

    Compares the FIX against the DRAFT, not against the source: the draft is
    already the thing under test (it may itself have dropped a fact the source
    had), and the fix pass promises only to leave everything but the named
    faults untouched. A critical finding here means the fix pass broke that
    promise.

    Returns (text, fired): `text` is `fixed` when nothing critical happened,
    else `draft`; `fired` says whether the gate discarded the fix, so the
    result JSON can show a reader exactly which documents it caught.
    """
    result = faithfulness.compare(draft, fixed)
    if result["critical"] > 0:
        return draft, True
    return fixed, False


# An eval subject with tool access edits the repository instead of answering. In an
# earlier run, two of three arms wrote a runbook to disk: one into the repository
# root, and one into the home directory of the person running the eval. Deny the
# tools that touch the filesystem, so the subject returns text and changes nothing.
DENIED_TOOLS = "Write,Edit,NotebookEdit,Bash"


def run_one(prompt, system, cwd=None, model=None):
    cmd = ["claude", "-p", "--model", model or MODEL_GENERATION,
           "--disallowedTools", DENIED_TOOLS]
    if system:
        cmd += ["--system-prompt", system]
    # `--` ends the options. Without it the CLI reads a prompt that begins with a
    # word like "Rewrite" as more values for `--disallowedTools`, and the run fails
    # with a permission error for every word in the prompt.
    cmd += ["--", prompt]
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            # Run outside the repository, so a subject that finds a way to write
            # cannot touch the standard, the checker, or a result.
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or "").strip()[:200]
    text = out.stdout.strip()
    # A call that exits 0 and says nothing is a failed call. It reached the model
    # and came back empty, which every caller here would otherwise read as an
    # answer: one crashed a run after twenty-four generations were already paid
    # for, because a progress line called .split() on nothing.
    if not text:
        return None, "the model returned no text"
    return text, None


def cli_version():
    """Which CLI ran. A later run on another version is not the same run.

    This is the version, never the model: a CLI update and a model default
    move independently, and `MODEL_GENERATION` is pinned explicitly so only
    the CLI itself can still drift between two runs.
    """
    try:
        out = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True,
            timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return out.stdout.strip() or "unknown"


def main():
    ap = argparse.ArgumentParser(
        description="Rewrite every corpus document with each arm.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="run only the first N documents"
    )
    ap.add_argument("--only", nargs="*", default=None, help="document ids to run")
    ap.add_argument(
        "--jobs",
        type=int,
        default=JOBS_DEFAULT,
        help="calls to run at a time. Every call is independent, so they "
        "parallelise cleanly. Lower it if the API rate limits the run.",
    )
    ap.add_argument(
        "--passes",
        type=int,
        default=3,
        help="rewrites per document per arm. A model answers differently every "
        "time, so one pass cannot tell a real change from ordinary variance. "
        "Three is the default. Costs that many times as much.",
    )
    ap.add_argument(
        "--judge-passes",
        type=int,
        default=3,
        help="judgements per text. A judge disagrees with itself, so the report "
        "records how often each rule appeared. With only 2 passes agreement can "
        "only read 0.5 or 1.0, too coarse to trust; 3 is the default for an "
        "iteration run, 5 is what a publication run uses (--judge-passes 5).",
    )
    ap.add_argument(
        "--anchor-docs",
        nargs="*",
        default=ANCHOR_DOCS_DEFAULT,
        help="document ids judged every run, for loop-over-loop comparability. "
        f"Default: {' '.join(ANCHOR_DOCS_DEFAULT)}.",
    )
    ap.add_argument(
        "--rotating-count",
        type=int,
        default=ROTATING_COUNT,
        help="non-anchor documents judged this run, for coverage and to catch "
        "the skill overfitting to the anchors specifically.",
    )
    ap.add_argument(
        "--judge-all",
        action="store_true",
        help="bypass sampling and judge every document. Full cost (~5x a "
        "sampled run at the default counts). Use for a publication run.",
    )
    ap.add_argument(
        "--fix-pass",
        dest="fix_pass",
        action="store_true",
        default=True,
        help="add a third arm, `pste_fixed`: the pste draft, fed back to the "
        "model with the local checker's findings and asked to fix only what "
        "is named. Gated by faithfulness.py — a fix that drops a fact is "
        "discarded in favour of the original draft. One extra generation "
        "call per document with findings; no extra judge calls beyond the "
        "third arm being sampled like the other two. On by default.",
    )
    ap.add_argument("--no-fix-pass", dest="fix_pass", action="store_false")
    ap.add_argument(
        "--generation-model",
        default=MODEL_GENERATION,
        help="the model that writes. The judge is pinned separately and does "
        "not move, so a run that changes this measures the writer against one "
        f"ruler. Default {MODEL_GENERATION}.",
    )
    ap.add_argument(
        "--judge-model",
        nargs="+",
        default=[semantic_lint.MODEL_JUDGE],
        help="the model that judges. Default semantic_lint.MODEL_JUDGE "
        f"({semantic_lint.MODEL_JUDGE}). Give two or more names to judge "
        "every sampled text with EACH one and keep their findings separate "
        "(MULTI-JUDGE MODE): a finding both judges confirm is worth more "
        "than one judge confirming it twice, and the report shows the "
        "overlap. Costs one full judging pass per model named.",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    # Check the tree BEFORE calling the model. A run costs money, and a result
    # that no commit identifies cannot be compared with another one.
    try:
        info = provenance.require_clean_tree()
    except provenance.DirtyTree as exc:
        print(exc, file=sys.stderr)
        return 2

    # Verify the corpus before spending anything. Rewriting a document that this
    # project may not redistribute is worse than a failed eval, and a document that
    # changed since somebody recorded it is not the document the manifest names.
    problems = corpus.check()
    if problems:
        print("refusing to run: the corpus does not match its manifest.\n",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 2

    documents = corpus.load()
    if not documents:
        print(
            "refusing to run: the corpus is empty.\n\n"
            "The eval rewrites real documents. Add one to evals/corpus/ and record\n"
            "it in MANIFEST.yaml. See evals/corpus/README.md.",
            file=sys.stderr,
        )
        return 2

    if args.only:
        documents = [d for d in documents if d["id"] in args.only]
    if args.limit:
        documents = documents[: args.limit]

    selected = arms()

    out_path = result_path(info)
    if os.path.exists(out_path):
        print(
            f"refusing to run: {out_path} exists.\n\n"
            "This commit already has a result. Delete it to run again, or make a\n"
            "commit, so the two results keep separate names.",
            file=sys.stderr,
        )
        return 2

    # BUILD THE WHOLE WORK LIST FIRST.
    #
    # One unit of work is one document, one arm, one pass. Every unit is
    # independent: each starts from the same committed source and shares no state
    # with any other, so they run in any order and in parallel without affecting
    # each other's result.
    results = {}
    work = []
    for doc in documents:
        with open(corpus.path_of(doc), encoding="utf-8") as fh:
            source = fh.read()

        results[doc["id"]] = {
            "type": doc["type"],
            "title": doc["title"],
            # The source travels with its outputs. It is the control, and
            # `faithfulness.py` needs it to report what a rewrite dropped.
            "source": source,
            "licence": doc["licence"],
            "licence_url": corpus.LICENCE_URLS.get(doc["licence"], ""),
            # The licence that covers the REWRITES below. A share-alike source
            # makes its rewrites share-alike too, whatever the repository
            # licence says, so the result records it rather than leaving a
            # reader to work it out per document.
            "derived_licence": corpus.derived_licence(doc),
            "url": doc["url"],
            "author": doc["author"],
            "attribution": corpus.attribution(doc),
            "outputs": {},
        }
        prompt = TASK.format(document=source)
        for arm, system in selected.items():
            for attempt in range(args.passes):
                work.append(
                    {
                        "document": doc["id"],
                        "arm": arm,
                        "pass": attempt,
                        "prompt": prompt,
                        "system": system,
                        "source_words": len(source.split()),
                    }
                )

    print(f"{len(work)} calls, {args.jobs} at a time\n")
    failures = 0
    # Names a failed cell rather than just counting it: "4 failures" in the
    # console tells nobody which document/arm to re-judge. Generation failures
    # and judging failures share this one list, so a reader sees both kinds of
    # gap in one place instead of two separately-tracked counters that drift.
    judged_failures = []
    done = 0
    collected = collections.defaultdict(dict)
    lock = threading.Lock()

    # PER-STAGE METERING. A full loop burns the API budget somewhere, and
    # "somewhere" is not actionable. This counts the actual model calls each
    # stage makes (one `run_one` per unit here — the code has no retry today,
    # but the counter lives beside the call so a retry added later is counted
    # for free) and times the stage wall-clock, so the console and the result
    # JSON both say which half to cut before guessing again.
    stage_calls = {"generation": 0, "judging": 0}
    generation_start = time.monotonic()

    with tempfile.TemporaryDirectory() as sandbox:

        def execute(unit):
            # Each unit gets its own directory inside the sandbox, so two workers
            # writing at once cannot meet. The container mounts nothing from here,
            # but a host run shares this working directory.
            cell = os.path.join(sandbox, f"{unit['document']}-{unit['arm']}-{unit['pass']}")
            os.makedirs(cell, exist_ok=True)
            text, err = run_one(unit["prompt"], unit["system"], cwd=cell,
                                model=args.generation_model)
            with lock:
                stage_calls["generation"] += 1
            return unit, text, err

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for unit, text, err in pool.map(execute, work):
                with lock:
                    done += 1
                    label = f"{unit['document']}/{unit['arm']}"
                    if args.passes > 1:
                        label += f" pass {unit['pass'] + 1}"
                    if err:
                        failures += 1
                        judged_failures.append(label)
                        print(f"  [{done}/{len(work)}] {label}: FAILED {err}",
                              file=sys.stderr)
                    else:
                        print(
                            f"  [{done}/{len(work)}] {label}: "
                            f"{unit['source_words']} -> {len(text.split())} words"
                        )
                        collected[unit["document"]].setdefault(unit["arm"], {})[
                            unit["pass"]
                        ] = text

        stage_elapsed = {"generation": time.monotonic() - generation_start}

        # A subject that ignored the denied tools would leave a file behind.
        leaked = [
            name
            for name in sorted(os.listdir(sandbox))
            if os.listdir(os.path.join(sandbox, name))
        ]
        if leaked:
            print(
                f"\nWARNING: an arm wrote into {len(leaked)} working "
                f"director(ies) despite the denied tools: {', '.join(leaked[:5])}",
                file=sys.stderr,
            )

    # ORDER THE PASSES BY THEIR INDEX, NOT BY WHEN THEY FINISHED.
    #
    # Workers finish out of order, so a result assembled in completion order would
    # differ between runs of the same inputs. Sorting by the pass index keeps the
    # file stable.
    for document, by_arm in collected.items():
        for arm, by_pass in by_arm.items():
            ordered = [by_pass[i] for i in sorted(by_pass)]
            # `outputs` holds the first pass, so every reader keeps working
            # whatever the pass count. `passes` holds all of them.
            results[document]["outputs"][arm] = ordered[0] if ordered else None
            if args.passes > 1:
                results[document].setdefault("passes", {})[arm] = ordered

    # THE FIX PASS. A third arm, `pste_fixed`: take the pste draft, run it
    # through the free local checker, and if it has findings, hand the model
    # back its own draft plus the fault list. See FIX_PROMPT's comment for the
    # measured numbers and why "do not shorten" is load-bearing.
    #
    # Runs after generation and before judging, on the same document/arm/pass
    # shape as generation, so it reuses run_one and the ThreadPoolExecutor
    # pattern rather than inventing a second way to call the model.
    fix_start = time.monotonic()
    stage_calls["fix_pass"] = 0
    if args.fix_pass and "pste" in selected:
        vocab = pste_lint.load_vocab()
        fix_work = []
        for document in results:
            draft = results[document]["outputs"].get("pste")
            if not draft:
                continue  # generation failed for this cell; nothing to fix
            checked = pste_lint.check_text(draft, vocab=vocab)
            if not checked["findings"]:
                # No findings, no call. This is the common case once the skill
                # itself is good, and it is what keeps the fix pass cheap.
                results[document]["pste_fixed_gate"] = {"fired": False, "skipped": True}
                results[document]["outputs"]["pste_fixed"] = draft
                continue
            fix_work.append((document, draft, format_faults(checked["findings"])))

        with tempfile.TemporaryDirectory() as fix_sandbox:

            def fix_one(item):
                document, draft, faults = item
                cell = os.path.join(fix_sandbox, document)
                os.makedirs(cell, exist_ok=True)
                prompt = FIX_PROMPT.format(document=draft, faults=faults)
                text, err = run_one(prompt, selected["pste"], cwd=cell,
                                    model=args.generation_model)
                with lock:
                    stage_calls["fix_pass"] += 1
                return document, draft, text, err

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.jobs
            ) as pool:
                for document, draft, text, err in pool.map(fix_one, fix_work):
                    if err:
                        # NEVER let a failed fix call end the run. Generation is
                        # already paid for, so a failed fix keeps the draft.
                        results[document]["pste_fixed_gate"] = {
                            "fired": False, "error": err,
                        }
                        results[document]["outputs"]["pste_fixed"] = draft
                        print(f"  {document}/pste_fixed: FAILED {err}",
                              file=sys.stderr)
                        continue
                    # THE FIDELITY GATE. A fix that reads better on the checker
                    # but drops a fact has made the failure PSTE-A1 most fears.
                    # gate_fix keeps the fix only when nothing critical was
                    # lost against the draft it started from.
                    final, fired = gate_fix(draft, text)
                    results[document]["pste_fixed_gate"] = {"fired": fired}
                    results[document]["outputs"]["pste_fixed"] = final
                    if fired:
                        print(f"  {document}/pste_fixed: GATE FIRED, kept the draft")
        selected["pste_fixed"] = selected["pste"]
    stage_elapsed["fix_pass"] = time.monotonic() - fix_start

    # SEMANTIC JUDGEMENT, IN THE SAME FILE.
    #
    # The mechanical checker implements 29 of the 78 rules. The rest need a reader
    # that understands what the text means, and `semantic_lint.py` asks a model.
    # Its findings belong beside the text they judge, so a result stays one file
    # that holds everything about the run.
    #
    # JUDGE SAMPLING. A full loop is ~420 judge calls, and that alone exhausted
    # the API budget. The mechanical checker already covers every document for
    # free (pste_lint.check_text runs in report.py regardless of what was
    # judged — see build_entry). Judging is what gets rationed: by default only
    # the anchors plus a rotating slice are judged, and every other document's
    # cell is marked `sampled_out`, never silently absent. `--judge-all`
    # bypasses this for a publication run.
    # A THIRD JUDGED ARM (pste_fixed) COSTS 1.5x. `judge_sample` rations
    # documents, not arms, so a third arm judged over the same document count
    # raises calls by half. Rather than accept that rise silently, shrink the
    # rotating slice by the same ratio the arm count grew — 2 arms -> 3 arms
    # is *1.5, so the rotating count divides by 1.5 — when the fix pass added
    # a third arm AND the user left `--rotating-count` at its default. An
    # explicit `--rotating-count` is a deliberate choice and is left alone.
    rotating_count = args.rotating_count
    if "pste_fixed" in selected and args.rotating_count == ROTATING_COUNT:
        rotating_count = max(1, round(ROTATING_COUNT * 2 / 3))
    sample = judge_sample(
        sorted(results),
        args.anchor_docs,
        0 if args.judge_all else rotating_count,
        rotation_offset_from_commit(info["commit"]),
    )
    judged_docs = set(results) if args.judge_all else set(sample["judged"])

    def semantic_stage():
        semantic_lint.corpus_generate.load_env_file()
        credential_var = semantic_lint.corpus_generate.credential()
        if not credential_var:
            print(
                "\nskipping the semantic judgement: no credential is set.",
                file=sys.stderr,
            )
        elif not semantic_lint.corpus_generate.image_exists():
            print(
                "\nskipping the semantic judgement: the container image is absent.\n"
                "    python3 evals/semantic_lint.py --build",
                file=sys.stderr,
            )
        else:
            targets = [
                (document, arm)
                for document in results
                for arm in selected
                if results[document]["outputs"].get(arm)
                and document in judged_docs
            ]
            skipped = [
                (document, arm)
                for document in results
                for arm in selected
                if results[document]["outputs"].get(arm)
                and document not in judged_docs
            ]
            for document, arm in skipped:
                # SAMPLED_OUT is not a failure. Nothing was asked of the judge
                # for this cell, so nothing failed — this is a deliberate
                # sampling decision, and must read differently from `unjudged`
                # (a judge call that WAS made and came back with nothing). Both
                # share the same `unjudged` bit, because report.py's
                # `build_entry` already forces `pass=False` for anything the
                # judge has not actually looked at — see the note on
                # `judge_sample` in the module docstring for why an excluded
                # cell still can't register as clean. `sampled_out` is what
                # tells the two apart on the JSON and the page.
                results[document].setdefault("semantic", {})[arm] = {
                    "unjudged": True,
                    "sampled_out": True,
                    "error": "not selected for judging this run "
                    f"(anchors: {', '.join(sample['anchors'])}; "
                    f"rotating: {', '.join(sample['rotating'])})",
                }
            print(
                f"\njudging {len(targets)} texts, {args.judge_passes} passes each "
                f"({len(skipped)} cells sampled out)"
            )

            # Judge the texts together, not one after another. `judge_repeatedly`
            # already runs the passes of ONE text at the same time, so nesting the
            # two pools naively would ask for `jobs` texts times `jobs` passes
            # containers at once. Divide the budget instead: each text gets a share
            # of the workers, and the product stays at `jobs`.
            #
            # Judging every text one at a time made this stage the slow half of the
            # run. Generation already worked this way; this stage did not.
            text_jobs, pass_jobs = judge_workers(args.jobs, len(targets))

            judge_models = args.judge_model
            multi_judge = len(judge_models) > 1

            def judge(target):
                document, arm, judge_model = target
                try:
                    return target, semantic_lint.judge_repeatedly(
                        results[document]["outputs"][arm],
                        source=results[document]["source"],
                        credential_var=credential_var,
                        passes=args.judge_passes,
                        jobs=pass_jobs,
                        gate=semantic_lint.GATE_DEFAULT,
                        model=judge_model,
                    )
                except Exception as exc:  # noqa: BLE001
                    # NEVER let one text end the run. The generation phase is the
                    # expensive half and it is already paid for by this point, so
                    # an exception here must cost one judgement and not all of
                    # them. A crash in this stage once discarded 84 completed
                    # generations.
                    return target, (None, [], f"{type(exc).__name__}: {exc}")

            # One unit of work per (document, arm, judge model). With one judge
            # model this is exactly today's `targets` list — byte-identical
            # work, byte-identical result shape below. With several, every
            # sampled text is judged once per model, and kept separate rather
            # than merged, so a reader can see what EACH judge said.
            judge_targets = [
                (document, arm, judge_model)
                for document, arm in targets
                for judge_model in judge_models
            ]

            nonlocal failures
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=text_jobs
            ) as pool:
                for (document, arm, judge_model), (summary, judged, err) in pool.map(
                    judge, judge_targets
                ):
                    # `results` is only touched here, in the loop that reads the
                    # pool, so the worker threads never write it.
                    cell_label = f"{document}/{arm}"
                    if multi_judge:
                        cell_label += f" [{judge_model}]"
                    if err:
                        # A cell with no judge output is a FAILURE, not silence.
                        # Recording it in `results` (rather than only printing
                        # and skipping) is what makes the JSON file itself
                        # self-describing: a reader of the file alone, with no
                        # console log, must be able to see that this cell was
                        # never judged and why. `unjudged` distinguishes this
                        # from "the judge ran and found nothing" (an absent
                        # `semantic[arm]` key on an older result, before this
                        # fix existed, still means "never judged" too — see
                        # report.py's semantic_findings).
                        failures += 1
                        judged_failures.append(cell_label)
                        cell = {"unjudged": True, "error": err}
                    else:
                        cell = {"summary": summary, "runs": judged}
                        confirmed = sum(1 for s in summary if s["status"] == "confirmed")
                        print(f"  {cell_label}: {len(summary)} rules, {confirmed} confirmed")
                    if err:
                        print(f"  {cell_label}: FAILED {err}", file=sys.stderr)
                    if multi_judge:
                        # MULTI-JUDGE: keep every judge's result SEPARATE, under
                        # its own model name, rather than merging them into one
                        # blob. report.py computes the overlap from this shape.
                        slot = results[document].setdefault("semantic", {}).setdefault(
                            arm, {"by_judge": {}}
                        )
                        slot["by_judge"][judge_model] = cell
                    else:
                        # SINGLE JUDGE: the existing shape, unchanged. This is
                        # what keeps a default run byte-identical to today.
                        results[document].setdefault("semantic", {})[arm] = cell
            # `judge_repeatedly` makes exactly `judge_passes` calls per target —
            # it has no retry, so every pass in `range(passes)` is one call,
            # whether it succeeds or fails (see semantic_lint.judge_repeatedly).
            # A live counter would count the identical number; this stays
            # arithmetic until a retry actually exists to miscount. Multi-judge
            # multiplies by the judge count, since each model repeats the work.
            stage_calls["judging"] = len(judge_targets) * args.judge_passes

    # The generation phase is the expensive half, and it is finished by now. A
    # failure in the judgement must cost the judgement only: the run still writes
    # its file, and a reader sees which stage was lost.
    semantic_error = None
    judging_start = time.monotonic()
    try:
        semantic_stage()
    except Exception as exc:  # noqa: BLE001
        semantic_error = f"{type(exc).__name__}: {exc}"
        print(f"\nthe semantic judgement failed: {semantic_error}",
              file=sys.stderr)
        print("the generated text is kept, and the file is still written.",
              file=sys.stderr)
    stage_elapsed["judging"] = time.monotonic() - judging_start

    # PER-STAGE METERING, IN THE CONSOLE AND THE FILE. Repeated runs exhausted
    # the API budget mid-loop, and "generation vs judging" is the split that
    # decides what to cut next. Calls, not documents: `stage_calls` counts
    # every actual model call the stage made (including a retry, were one ever
    # added — see the comments beside each counter), so this is a budget
    # reading and not a rerun of the document count already printed elsewhere.
    print(
        f"\n  generation: {stage_calls['generation']} calls, "
        f"{stage_elapsed['generation']:.0f}s"
    )
    print(
        f"  fix pass:   {stage_calls['fix_pass']} calls, "
        f"{stage_elapsed['fix_pass']:.0f}s"
    )
    print(
        f"  judging:    {stage_calls['judging']} calls, "
        f"{stage_elapsed['judging']:.0f}s"
    )

    payload = {
        "schema": 2,
        "git": info,
        # WHICH MODEL PRODUCED THIS RESULT. A result that does not say what
        # produced it cannot be compared with another one. `cli` is the CLI
        # version, not the model: the two drift independently, so both are
        # recorded.
        "models": {
            "generation": args.generation_model,
            "fix_pass": args.generation_model if args.fix_pass else None,
            # A string when one judge ran (today's shape, unchanged), a list
            # when several did (MULTI-JUDGE MODE) — either way this says which
            # model(s) actually judged, not the module default that may differ.
            "judging": (
                args.judge_model[0] if len(args.judge_model) == 1 else list(args.judge_model)
            ),
        },
        "cli": cli_version(),
        "arms": list(selected),
        "control_text": CONTROL_TEXT,
        "task": TASK,
        "document_count": len(documents),
        "passes": args.passes,
        "jobs": args.jobs,
        "semantic_passes": args.judge_passes,
        "semantic_gate": semantic_lint.GATE_DEFAULT,
        # Absent when the judgement ran, so a reader can tell a stage that was
        # lost from one that was never asked for.
        "semantic_error": semantic_error,
        # PER-STAGE METERING (PART 1). Which half actually burns the budget,
        # from data rather than a guess. `calls` is the count of actual model
        # calls the stage made; `seconds` is its wall-clock. See the comments
        # beside `stage_calls`/`stage_elapsed` above for how each is counted.
        "stages": {
            "generation": {
                "calls": stage_calls["generation"],
                "seconds": round(stage_elapsed["generation"], 1),
            },
            "fix_pass": {
                "calls": stage_calls["fix_pass"],
                "seconds": round(stage_elapsed["fix_pass"], 1),
            },
            "judging": {
                "calls": stage_calls["judging"],
                "seconds": round(stage_elapsed["judging"], 1),
            },
        },
        # JUDGE SAMPLING (PART 2). Which documents were judged this run, and
        # why, so a reader of the JSON alone — no console log — can tell a
        # deliberate sampling decision from a run that happened to judge
        # everything. `judge_all` says whether sampling was bypassed;
        # `rotation_offset` is the value `judge_sample` actually used, derived
        # from the commit (see `rotation_offset_from_commit`), so re-running
        # this exact commit reproduces this exact sample.
        "judge_sample": {
            "judge_all": args.judge_all,
            "anchor_docs": sample["anchors"],
            "rotating_docs": sample["rotating"],
            "judged_docs": sorted(judged_docs),
            "rotation_offset": sample["rotation_offset"],
        },
        "failures": failures,
        # Which document/arm cells failed — generation or judging. An eval run
        # that hit API limits once reported `failures: 0` with 4 of 28 cells
        # silently unjudged, because a failed judge call was printed to
        # stderr and then dropped rather than counted. The file must be able
        # to say what is missing on its own, without the console log that
        # produced it.
        "judged_failures": judged_failures,
        "results": results,
    }

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"\nwrote {out_path}")
    print(f"  {len(documents)} documents, {len(selected)} arms, {failures} failures")
    print(f"  commit {info['short']} on {info['branch']}")

    # Build the page here. A result nobody reads is a result nobody checked, and
    # asking a person to run a second command every time is how that happens. The
    # page is a build product of the run, so it is written beside the JSON.
    try:
        import report

        # A page is built from the stored text by the local checker, so it
        # costs no model call.
        for path in report.write_pages(payload, out_path):
            print(f"  report {path}")
    except Exception as exc:  # noqa: BLE001
        # The measurement is in the JSON, which is already on disk. A page
        # that fails to build must not fail the run that produced the data.
        print(f"  the report failed to build: {exc}", file=sys.stderr)
    if failures:
        print(
            f"\n{failures} cell(s) FAILED and are missing from this result "
            "(generation or judging): " + ", ".join(judged_failures),
            file=sys.stderr,
        )
        print(
            "This run is INCOMPLETE. Read the result before you compare it — "
            "report.py marks every failed cell UNJUDGED rather than clean.",
            file=sys.stderr,
        )
    return 1 if failures else 0


def self_test():
    info = {
        "commit": "3f9a1b7c" + "0" * 32,
        "short": "3f9a1b7c",
        "branch": "main",
        "committed": "2026-08-03T11:20:00+01:00",
        "subject": "x",
    }
    # The name carries the day of the commit, and the commit itself.
    assert result_path(info, "/d") == "/d/eval-2026-08-03-3f9a1b7c.json", result_path(
        info, "/d"
    )
    # The two judging pools nest, so their product is what starts containers.
    # It must never exceed the budget the user asked for.
    for jobs in (1, 2, 3, 4, 8, 16):
        for targets in (1, 2, 3, 8, 28, 100):
            texts, passes = judge_workers(jobs, targets)
            assert texts >= 1 and passes >= 1, (jobs, targets)
            assert texts * passes <= jobs, (jobs, targets, texts, passes)
            assert texts <= targets, (jobs, targets, texts)
    # More texts than workers: every worker takes one text, and the passes of a
    # text wait rather than doubling the container count.
    assert judge_workers(8, 28) == (8, 1)
    # The default must actually raise the parallelism, or a run takes hours. The
    # judging stage is the slow half, so a low default is what made a run take two.
    assert JOBS_DEFAULT >= 16, f"jobs default {JOBS_DEFAULT} is too low"
    # One text: the whole budget goes to its passes, as it did before.
    assert judge_workers(8, 1) == (1, 8)

    # A commit with no date still produces a usable name.
    assert result_path({"short": "abc", "committed": None}, "/d").startswith(
        "/d/eval-2"
    )

    # Two arms, and neither is unprompted. An arm with no instruction measures the
    # difference between asking and not asking, which is not the question.
    got = arms()
    assert set(got) == {"control", "pste"}, got
    assert all(v for v in got.values()), got
    # The skill arm must contain the control ask, so the two differ only by the
    # skill. If the control text drifts out, the arms stop being comparable.
    assert got["pste"].startswith(CONTROL_TEXT), got["pste"][:80]
    assert len(got["pste"]) > len(got["control"]), "the skill did not load"

    # The task must carry the document and demand that facts survive.
    filled = TASK.format(document="THE-DOCUMENT")
    assert "THE-DOCUMENT" in filled
    for demand in ("Keep every fact", "do not remove information"):
        assert demand in filled, demand

    # The filesystem tools must stay denied. An eval subject with tool access
    # writes files instead of answering, and two arms once did.
    for tool in ("Write", "Edit", "Bash"):
        assert tool in DENIED_TOOLS, tool

    # The prompt must sit after `--`. Without it the CLI reads a prompt that starts
    # with an ordinary word as more values for `--disallowedTools`, and every word
    # comes back as "matches no known tool".
    import unittest.mock as mock

    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=0, stdout="x", stderr="")
        run_one("Rewrite this document.", "sys")
    argv = spy.call_args[0][0]
    assert "--" in argv, argv
    assert argv[argv.index("--") + 1] == "Rewrite this document.", argv
    assert argv.index("--") > argv.index("--disallowedTools"), argv

    # THE MODEL MUST BE PINNED, NEVER LEFT TO THE CLI DEFAULT. A default reads
    # from the operator's own settings, and one full eval ran unnoticed on
    # Fable that way. `--model` names Sonnet or Opus and never Fable.
    assert "--model" in argv, argv
    pinned = argv[argv.index("--model") + 1]
    assert pinned == MODEL_GENERATION, argv
    assert "sonnet" in pinned or "opus" in pinned, \
        f"generation must run on Sonnet or Opus, not {pinned}"
    assert "fable" not in pinned, f"generation must never run on Fable: {pinned}"

    # PASSES MUST BE ORDERED BY INDEX, NOT BY COMPLETION.
    #
    # Workers finish out of order. A result assembled in completion order would
    # differ between runs of the same inputs, and two results of one commit would
    # not match. This mirrors the ordering step in main().
    by_pass = {2: "third", 0: "first", 1: "second"}
    ordered = [by_pass[i] for i in sorted(by_pass)]
    assert ordered == ["first", "second", "third"], ordered

    # A gap in the passes must not raise: a failed call leaves its index absent.
    holed = {0: "first", 2: "third"}
    assert [holed[i] for i in sorted(holed)] == ["first", "third"]

    # JUDGE SAMPLING (PART 2).
    #
    # The default anchors must be the two the user chose, and they must be
    # configurable without touching the sampling logic — a module constant a
    # caller can override, not a name baked into `judge_sample`.
    assert ANCHOR_DOCS_DEFAULT == [
        "synth-prometheus-query-basics", "runbook-cassandra-repair",
    ], ANCHOR_DOCS_DEFAULT
    docs = sorted(corpus.load(), key=lambda d: d["id"])
    doc_ids = [d["id"] for d in docs]
    assert len(doc_ids) >= 6, "the self-test corpus assumption needs headroom"

    sample = judge_sample(doc_ids, ANCHOR_DOCS_DEFAULT, ROTATING_COUNT, 0)
    # Sampling selects the anchors, plus exactly ROTATING_COUNT rotating docs.
    assert set(sample["anchors"]) == set(ANCHOR_DOCS_DEFAULT), sample
    assert len(sample["rotating"]) == ROTATING_COUNT, sample
    # The two sets never overlap: an anchor is never also drawn into rotation.
    assert not (set(sample["anchors"]) & set(sample["rotating"])), sample
    assert set(sample["judged"]) == set(sample["anchors"]) | set(sample["rotating"])

    # ROTATION IS DETERMINISTIC FOR A GIVEN CONFIGURATION: the same document
    # list, anchors, count, and offset must reproduce the same rotating set
    # every time it is computed — this is what "reproducible from the result
    # file" means. No call here touches `random`.
    again = judge_sample(doc_ids, ANCHOR_DOCS_DEFAULT, ROTATING_COUNT, 0)
    assert again["rotating"] == sample["rotating"], (again, sample)
    assert again["rotation_offset"] == sample["rotation_offset"]

    # A different offset must move the rotating slice (proving it is not
    # accidentally constant), and must still wrap cleanly at the end of the
    # pool rather than raising or truncating short.
    moved = judge_sample(doc_ids, ANCHOR_DOCS_DEFAULT, ROTATING_COUNT, 1)
    assert moved["rotating"] != sample["rotating"], "the offset had no effect"
    assert len(moved["rotating"]) == ROTATING_COUNT, moved
    pool_size = len(doc_ids) - len(ANCHOR_DOCS_DEFAULT)
    wrapped = judge_sample(doc_ids, ANCHOR_DOCS_DEFAULT, ROTATING_COUNT, pool_size - 1)
    assert len(wrapped["rotating"]) == ROTATING_COUNT, wrapped

    # THE OFFSET COMES FROM THE COMMIT, NOT FROM `random`. The same commit
    # must always produce the same offset (reproducible), and two different
    # commits should usually produce different offsets (the rotation actually
    # advances rather than parking on one slice forever).
    off_a = rotation_offset_from_commit("a" * 40)
    off_b = rotation_offset_from_commit("a" * 40)
    off_c = rotation_offset_from_commit("b" * 40)
    assert off_a == off_b, "the same commit must give the same offset"
    assert off_a != off_c, "a different commit should move the offset"
    assert isinstance(off_a, int) and off_a >= 0, off_a

    # An anchor absent from the (filtered, e.g. --only) document set must not
    # appear in the sample, and must not shrink the rotating count silently —
    # it simply is not judged, same as any other document `--only` excluded.
    partial = judge_sample(
        ["synth-prometheus-query-basics", "runbook-etcd-restore", "howto-k8s-debug-pods"],
        ANCHOR_DOCS_DEFAULT, ROTATING_COUNT, 0,
    )
    assert partial["anchors"] == ["synth-prometheus-query-basics"], partial
    assert set(partial["rotating"]) <= {"runbook-etcd-restore", "howto-k8s-debug-pods"}

    # --judge-all (rotating_count=0 is how main() expresses the bypass) must
    # judge nothing EXTRA via rotation — the caller unions in every document
    # itself when the flag is set (see main()), not `judge_sample`.
    bypassed = judge_sample(doc_ids, ANCHOR_DOCS_DEFAULT, 0, 0)
    assert bypassed["rotating"] == [], bypassed
    assert set(bypassed["judged"]) == set(ANCHOR_DOCS_DEFAULT), bypassed
    # And main() must actually union in every document when `--judge-all` is
    # set, not just skip rotation: `judged_docs = set(results) if
    # args.judge_all else set(sample["judged"])` is the line that matters,
    # checked here at the source level so a future refactor of that line
    # cannot silently narrow --judge-all back down to the sample.
    import inspect

    main_source = inspect.getsource(main)
    assert 'set(results) if args.judge_all else set(sample["judged"])' in main_source, \
        "--judge-all must judge every document, bypassing the sample entirely"

    # MECHANICAL SCORING COVERS THE FULL CORPUS REGARDLESS OF JUDGE SAMPLING.
    # Judging is what gets rationed; pste_lint.check_text is free and local,
    # and report.py's build_entry calls it UNCONDITIONALLY on `text` — the
    # `semantic=` argument only ever adds judge findings on top, it never
    # gates whether the mechanical check runs. So sampling some documents out
    # of judging cannot also sample them out of mechanical scoring: proven
    # here by calling build_entry with `semantic=None` (the "never judged"
    # case, which is what every sampled-out document gets) for one document
    # from each real corpus document's actual source text, and checking the
    # mechanical `findings`/`words` still come back — the same call report.py
    # makes for every arm of every document, judged or not.
    import report as _report

    vocab = _report.pste_lint.load_vocab()
    for doc in docs[:3]:  # a few real documents is enough to prove the path
        with open(corpus.path_of(doc), encoding="utf-8") as fh:
            source = fh.read()
        entry = _report.build_entry(source, vocab, semantic=None)
        assert entry["missing"] is False, doc["id"]
        assert "findings" in entry and "words" in entry, doc["id"]

    # JUDGE-PASSES DEFAULT: the user found 5 too expensive. Reading main()'s
    # actual source (rather than a second, re-declared parser that could
    # silently drift from the real one) is what catches the default moving
    # back to 5 by accident; 5 must stay reachable via the flag for a
    # publication run.
    import inspect

    main_source = inspect.getsource(main)
    flag_start = main_source.index('"--judge-passes"')
    flag_block = main_source[flag_start : main_source.index(")", flag_start)]
    assert "default=3" in flag_block, \
        "the --judge-passes default must be 3 (the user found 5 too expensive)"

    # PSTE has one level: every rule applies, and the vocabulary rules are
    # MUST. There is no per-level flag left to reach the judge or the result,
    # and `write_pages` writes a single page. A flag reappearing in this file
    # would mean the old branch crept back in.
    src = open(__file__, encoding="utf-8").read()
    level_flag = "-" + "-level"
    level_kwarg = "level" + "="
    assert level_flag not in src, "the level flag must not come back"
    assert level_kwarg not in src, "no call in this file should take a level again"
    assert "write_pages(payload, out_path)" in src, \
        "a page is written once, with no levels tuple"

    # THE MODEL MUST REACH THE RESULT JSON. A result that does not say what
    # produced it cannot be compared with another one. Checked at the source
    # level: the payload must carry a `models` block naming the generation model and
    # the judge model(s) actually used (args.judge_model, defaulting to
    # semantic_lint.MODEL_JUDGE — see the --judge-model flag), plus the CLI
    # version.
    assert '"models": {' in src, "the result must record which model ran each stage"
    assert "MODEL_GENERATION," in src or "args.generation_model," in src, \
        "the generation model must reach the payload"
    # A flag recorded but never passed reports one model and runs another.
    assert src.count("model=args.generation_model") >= 2, \
        "--generation-model must reach both the rewrite and the fix pass"
    assert "args.judge_model" in src, "the judge model(s) must reach the payload"
    assert "default=[semantic_lint.MODEL_JUDGE]" in src, \
        "--judge-model must default to semantic_lint.MODEL_JUDGE"
    assert '"cli": cli_version(),' in src, "the CLI version must reach the payload"

    # --JUDGE-MODEL MUST REACH THE ACTUAL judge_repeatedly CALL, not just the
    # payload. Checked at the source level: judge()'s call inside
    # semantic_stage must pass `model=judge_model`, the loop variable drawn
    # from `args.judge_model`, the same pattern --generation-model already
    # uses for run_one.
    stage_start = src.index("def semantic_stage")
    semantic_stage_src = src[stage_start : src.index("semantic_error = None", stage_start)]
    assert "model=judge_model," in semantic_stage_src, \
        "--judge-model must reach the judge_repeatedly call, not just the payload"

    # THE `models` PAYLOAD FIELD: a string with one judge (today's shape,
    # unchanged), a list with several — and it must name the model(s)
    # ACTUALLY asked, not the module default.
    one = ["claude-opus-5"]
    many = ["claude-opus-5", "claude-sonnet-5"]
    judging_field = lambda judge_model: (  # mirrors the payload expression
        judge_model[0] if len(judge_model) == 1 else list(judge_model)
    )
    assert judging_field(one) == "claude-opus-5"
    assert judging_field(many) == ["claude-opus-5", "claude-sonnet-5"]

    # MULTI-JUDGE STORES RESULTS SEPARATELY, NEVER MERGED. `semantic_stage` is
    # a closure inside main() (it needs `results`, `selected`, `sample` from
    # the run it judges), so it cannot be called standalone without a live
    # corpus and a real judge — the same reason this file's other
    # closure-only logic (--judge-all's union, the judge-passes default) is
    # checked at the source level rather than by calling it. This proves the
    # STORAGE rule directly, against two small fixed inputs, with no model
    # call: one judge writes the flat shape `{"summary":.., "runs":..}`
    # (today's shape, byte-identical); two or more write
    # `{"by_judge": {model: {...}}}`, one slot per model, never overwriting
    # a sibling.
    def store(multi_judge, results_semantic, judge_model, cell):
        if multi_judge:
            slot = results_semantic.setdefault("by_judge", {})
            slot[judge_model] = cell
        else:
            results_semantic.clear()
            results_semantic.update(cell)
        return results_semantic

    single = store(False, {}, "claude-opus-5", {"summary": ["a"], "runs": [[]]})
    assert single == {"summary": ["a"], "runs": [[]]}, single  # unchanged shape

    multi = {}
    store(True, multi, "claude-opus-5", {"summary": ["a"], "runs": [[]]})
    store(True, multi, "claude-sonnet-5", {"summary": ["b"], "runs": [[]]})
    assert set(multi["by_judge"]) == {"claude-opus-5", "claude-sonnet-5"}, multi
    # Each judge's own findings survive untouched, proving the second judge's
    # write never clobbered the first's.
    assert multi["by_judge"]["claude-opus-5"]["summary"] == ["a"], multi
    assert multi["by_judge"]["claude-sonnet-5"]["summary"] == ["b"], multi

    # The actual storage code in semantic_stage must follow this same shape:
    # `by_judge` only when multi_judge, the flat shape otherwise.
    assert 'slot["by_judge"][judge_model] = cell' in semantic_stage_src, \
        "multi-judge results must be stored under by_judge, keyed by model"
    assert 'multi_judge = len(judge_models) > 1' in semantic_stage_src, \
        "multi-judge mode must trigger on 2+ judge models, not a hardcoded flag"
    assert "fable" not in MODEL_GENERATION.lower(), \
        f"generation must never pin Fable: {MODEL_GENERATION}"

    # THE FIX PASS.
    #
    # The prompt must carry both load-bearing instructions: "do not shorten"
    # (without it, an earlier version summarised a 767-word document to 39
    # words and scored well on the metric) and "NOT a rewrite" (the framing
    # that keeps the model from touching anything the fault list did not
    # name).
    filled_fix = FIX_PROMPT.format(document="THE-DOCUMENT", faults="- PSTE-N1: x")
    assert "Do not shorten" in filled_fix, filled_fix
    assert "NOT a rewrite" in filled_fix, filled_fix
    assert "THE-DOCUMENT" in filled_fix
    assert "PSTE-N1: x" in filled_fix

    # format_faults: one line per finding, `- RULE: message`, excerpt indented
    # below it — this is the only new information the fix pass gets over a
    # plain "revise this" ask.
    faults_text = format_faults(
        [{"rule": "PSTE-N1", "message": "too long", "excerpt": "a long sentence"}]
    )
    assert "- PSTE-N1: too long" in faults_text, faults_text
    assert "    a long sentence" in faults_text, faults_text

    # THE FIDELITY GATE.
    #
    # A critical faithfulness finding (a dropped fact) must discard the fix
    # and keep the draft — PSTE-A1 says accuracy defeats every other rule, so
    # a fixed text that reads better on the checker but loses a fact must
    # lose to the original draft.
    draft = "The client retries 3 times. Do not run this on the main branch."
    fixed_lossy = "The client retries 3 times. Run this on the main branch."
    text, fired = gate_fix(draft, fixed_lossy)
    assert fired is True, "a dropped negation must fire the gate"
    assert text == draft, "the gate must keep the draft when the fix loses a fact"

    # A faithful fix (same facts, cleaner prose) must pass through untouched.
    fixed_ok = "The client makes 3 attempts. Do not run this on the main branch."
    text, fired = gate_fix(draft, fixed_ok)
    assert fired is False, "a faithful fix must not fire the gate"
    assert text == fixed_ok, "the gate must return the fix when nothing critical was lost"

    # A document with no findings must skip the call entirely: this is what
    # keeps the fix pass cheap once the skill itself is clean. Proven at the
    # source level (rather than a live call) because run_one talks to a real
    # subprocess and self-test must stay free and offline.
    fix_pass_source = src[src.index("# THE FIX PASS. A third arm"):
                           src.index("# SEMANTIC JUDGEMENT, IN THE SAME FILE.")]
    assert "if not checked[\"findings\"]:" in fix_pass_source, \
        "a clean draft must skip the fix call, not spend one on nothing to fix"
    assert "continue" in fix_pass_source.split(
        'if not checked["findings"]:', 1)[1].split("fix_work.append", 1)[0], \
        "the skip must happen before the call is queued into fix_work"

    # A call that exits 0 and returns nothing is a failure, not an answer. The
    # run recorded it as an answer once, and a progress line called .split() on
    # it after twenty-four generations were already paid for.
    import subprocess as _sp
    class _Empty:
        returncode, stdout, stderr = 0, "   \n ", ""
    _real = _sp.run
    _sp.run = lambda *a, **k: _Empty()
    try:
        _text, _err = run_one("anything", None)
    finally:
        _sp.run = _real
    assert _text is None, "an empty answer is not text"
    assert _err, "an empty answer carries a reason"

    print("run.py self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
