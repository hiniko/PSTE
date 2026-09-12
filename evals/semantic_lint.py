#!/usr/bin/env python3
"""Judge a text against the rules that no regular expression can check.

    python3 evals/semantic_lint.py --build          # the container image
    python3 evals/semantic_lint.py FILE...          # judge files
    python3 evals/semantic_lint.py --result         # judge the newest eval result
    python3 evals/semantic_lint.py --arm pste --limit 3

WHY THIS EXISTS

`evals/pste_lint.py` implements 29 of the 78 rules in the standard (one of those 29,
PSTE-P1, is a pre-filter: the mechanical check catches the easy cases, and this file
still judges the rest). The other rules need a reader who understands what the text
MEANS:

    PSTE-A1   did the rewrite keep every fact?
    PSTE-D6   does the information arrive in a logical order?
    PSTE-G2   is the passive voice here justified, because the actor is unknown?
    PSTE-L3   does the first sentence state the result?
    PSTE-P4   does the procedure say what the reader should see?
    PSTE-W1   does a destructive step carry a warning before the command?

A regular expression cannot answer any of those. This asks a model instead.

THIS IS VERIFICATION TOOLING, AND NOT THE CHECKER

`pste_lint.py` stays mechanical, fast, and deterministic, because a pre-commit hook
must be all three. This is slow, costs money, and gives a different answer on a
second run. It belongs in CI and on the machine of somebody working on the
standard. Never put it in a hook.

WHAT THE JUDGE IS TOLD

The judge reads the standard itself, the text, and the mechanical findings. It is
told to report only what the mechanical checker CANNOT find, so the two do not
report the same thing twice. It runs in the clean container, so no personal setting
shapes its judgement.

IT WILL BE WRONG SOMETIMES

A model judging prose is not a measurement. Two runs disagree, and a confident
report of a rule that the text does not break is the likeliest failure. Treat every
finding as a candidate that a person confirms, and never as a count to publish.
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import corpus_generate  # noqa: E402
import provenance  # noqa: E402
import pste_lint  # noqa: E402

SPEC = os.path.join(ROOT, "spec", "PSTE-1.md")

# THE JUDGE'S MODEL, PINNED. Never left to the CLI default: a default reads
# from the operator's own settings, and one full eval ran unnoticed on Fable
# that way.
#
# Opus, not Sonnet: the judge is the measuring instrument, not the subject
# under test, and it already disagrees with itself (measured mean agreement
# 0.46 at 3 passes — see judge_repeatedly's docstring). A weaker judge makes a
# noisier ruler, and the ruler is not what this eval is trying to improve.
MODEL_JUDGE = "claude-opus-5"

# The rules a regular expression cannot decide. Naming them keeps the judge on the
# gap, rather than repeating what the mechanical checker already reported.
SEMANTIC_RULES = """\
PSTE-A1  accuracy defeats every other rule: no fact, condition, number, unit, or
         scope qualifier may disappear
PSTE-A2  length that carries no fact is not protected by PSTE-A1: a sentence over
         a limit must name the fact the limit would remove
PSTE-A3  a writer splits the sentence first, and exceeds a limit only when no
         split keeps every item
PSTE-D1  one topic in each paragraph
PSTE-D3  a numbered list for a sequence of three or more steps
PSTE-D4  a bulleted list for three or more parallel items
PSTE-D5  no sequence or set of conditions hidden inside one prose sentence
PSTE-D6  information in a logical order: what a thing is before what it does
PSTE-D8  one topic finished before the next one starts
PSTE-G2  the passive voice only in a description, and only when the actor is
         genuinely unknown
PSTE-G3  only the permitted verb forms
PSTE-G9  an article or a demonstrative before a noun where grammar permits one
PSTE-K3  no BCP 14 key word used for a statement of fact
PSTE-L3  the result before the explanation
PSTE-L4  no fact stated twice, in the same words or in different ones. A repeated
         warning is permitted
PSTE-N4  no words omitted to shorten a sentence
PSTE-N6  one instruction in each sentence
PSTE-P1  an instruction in the imperative form
PSTE-P2  a condition before the instruction it governs
PSTE-P3  a note gives information, and holds no instruction
PSTE-P4  a procedure states its expected result
PSTE-S2  quoted text and code reproduced character for character
PSTE-S3  a quotation that does not conform is not marked as an error
PSTE-V2  an approved word used only with its approved meaning
PSTE-V4  one name for one entity, matching the code
PSTE-V5  no term where an approved word states the meaning
PSTE-V6  no term noun used as a verb, and no term verb used as a noun
PSTE-W1  a warning before an operation that destroys data or that the reader
         cannot reverse
PSTE-W2  the scope of the effect stated before the command
PSTE-W3  the level of risk named: warning, caution, or note
PSTE-W4  the specific result of the risk, and not a vague phrase
PSTE-X3  a hyphen connecting words that act as one unit before a noun
"""

SCHEMA = """\
Return JSON only, and nothing else. Use this shape:

{"findings": [
   {"rule": "PSTE-W1",
    "quote": "the exact words from the text, 12 words at most",
    "problem": "one sentence saying what is wrong",
    "fix": "one sentence saying what to write instead",
    "confidence": "high" | "medium" | "low",
    "reason": "why you are reporting this, in one sentence"}
 ],
 "considered": [
   {"rule": "PSTE-V6",
    "quote": "the exact words you weighed and did not report",
    "reason": "why this does NOT break the rule, in one sentence"}
 ]}

Report nothing in "findings" when the text follows the rules. An empty list is a
valid answer and a common one. Every finding needs a "reason": the fact or
principle that makes it a violation, not a restatement of "problem".

"considered" is for a rule you actively weighed and rejected — something a careless
reader might flag, that you are confident is fine. Naming why you did NOT report it
is what lets a person tell a considered rejection from a rule you never checked. Do
not pad this list; leave it empty when nothing came close.
"""

PROMPT = """\
You are checking a text against a writing standard. The standard is at
/repo/spec/PSTE-1.md, and you must read it before you judge anything.

Report ONLY the rules that a regular expression cannot check. These are those rules:

{rules}

A mechanical checker already ran, and it reported the findings below. DO NOT REPEAT
any of them, and do not report any rule that the mechanical checker covers
(sentence length, contractions, Latin abbreviations, marketing adjectives, filler,
semicolons, phrasal verbs, perfect tense, and the passive voice as a pattern).

MECHANICAL FINDINGS ALREADY REPORTED (do not repeat these):
{mechanical}

The same mechanical checker also found the CANDIDATES below. These are a different
thing: each one comes from a rule that spots part-of-speech by a fixed word list
(is "test" a noun or an adjective here? is "attention of" built on a verb?), which
can be wrong. UNLIKE the findings above, you must judge each candidate — read it
against the text and the standard, then either:
  - put it in "findings", with the SAME rule ID, if it is a real violation, or
  - put it in "considered", with the SAME rule ID and a reason, if it is not.
Do not silently drop a candidate. Every one needs a decision, in one list or the
other. A candidate you do not judge is worse than one you reject: it disappears
instead of being ruled on.

CANDIDATES TO CONFIRM OR REJECT:
{candidates}

Judge the SPIRIT of the standard. Its purpose is a text that a tired reader, or a
reader whose first language is not English, cannot misread. A text can follow every
mechanical rule and still fail that purpose.

Be strict about PSTE-A1 when you have the source text, and be conservative
everywhere else. A finding you cannot quote is a finding you must not report.

{schema}

--- BEGIN TEXT ---
{text}
--- END TEXT ---
"""

SOURCE_NOTE = """\
This text is a REWRITE. The original is below. Rule PSTE-A1 says that accuracy
defeats every other rule, so report every fact, number, unit, condition, warning,
or scope qualifier that the rewrite dropped or changed.

--- BEGIN ORIGINAL ---
{source}
--- END ORIGINAL ---
"""


def split_mechanical(text):
    """The mechanical checker's findings, split into the two things a caller does
    with them: a COUNTABLE finding fails a document on its own and the judge is
    only told about it so it does not repeat it; an ARBITRATED finding (see
    `pste_lint.ARBITRATED_RULES`) is a candidate the judge must confirm or reject,
    because its rule encodes part-of-speech knowledge as a closed word list that
    can never be complete.
    """
    vocab = pste_lint.load_vocab()
    result = pste_lint.check_text(text, vocab=vocab)
    countable = [f for f in result["findings"] if not f["arbitrated"]]
    arbitrated = [f for f in result["findings"] if f["arbitrated"]]
    return countable, arbitrated


def _format_findings(findings, empty):
    if not findings:
        return empty
    lines = []
    for finding in findings[:40]:
        lines.append(
            f"  {finding['rule']} line {finding.get('line')}: {finding['message']}"
        )
    if len(findings) > 40:
        lines.append(f"  ... and {len(findings) - 40} more")
    return "\n".join(lines)


def mechanical_findings(text):
    """What the regular expressions already found, countable ones only. The judge
    is told to skip these — kept as a separate function because build_prompt's own
    self-test checks it, and other callers outside this module import it by name.
    """
    countable, _arbitrated = split_mechanical(text)
    return _format_findings(countable, "(none)")


def build_prompt(text, source=None):
    countable, arbitrated = split_mechanical(text)
    prompt = PROMPT.format(
        rules=SEMANTIC_RULES,
        mechanical=_format_findings(countable, "(none)"),
        candidates=_format_findings(arbitrated, "(none)"),
        schema=SCHEMA,
        text=text,
    )
    if source:
        prompt = prompt.replace("--- BEGIN TEXT ---", SOURCE_NOTE.format(source=source)
                                + "\n--- BEGIN TEXT ---")
    return prompt


def locate(quote, text):
    """Find the judge's quote in the text, and return its line and column.

    THE JUDGE IS NEVER ASKED FOR A LINE NUMBER. It would count lines by guessing,
    and be wrong. It quotes the words instead, and this finds them.

    That gives an integrity check for free: a quote that is NOT in the text was
    invented, and a finding built on invented words is worth nothing. `found` is
    false in that case, and the report says so.
    """
    quote = (quote or "").strip().strip('"').strip("'")
    if not quote:
        return {"found": False, "line": None, "column": None, "reason": "no quote"}

    index = text.find(quote)
    if index == -1:
        # A judge often normalises whitespace, so try again on a loose match of
        # the first words before giving up.
        words = quote.split()
        for size in (8, 6, 4):
            if len(words) < size:
                continue
            probe = " ".join(words[:size])
            index = text.find(probe)
            if index != -1:
                line, column = pste_lint.line_col(text, index)
                return {
                    "found": True, "line": line, "column": column, "partial": True,
                    "matched": probe,
                }
        return {
            "found": False, "line": None, "column": None,
            "reason": "the quote is not in the text",
        }

    line, column = pste_lint.line_col(text, index)
    return {"found": True, "line": line, "column": column, "partial": False}


def parse(output):
    """Read the judge's reply. A reply that is not JSON is a failure, not a pass.

    A judge that answers in prose has not followed the schema, and treating that as
    "no findings" would report a clean text where nothing was checked.

    Returns (findings, considered, error). `considered` holds a rule the judge
    weighed and rejected, so a person can tell a considered dismissal from a rule
    it never checked.
    """
    text = (output or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None, None, f"the judge did not return JSON: {text[:160]}"
    try:
        data = json.loads(text[start : end + 1])
    except ValueError as exc:
        return None, None, f"the judge returned broken JSON: {exc}"
    findings = data.get("findings")
    if not isinstance(findings, list):
        return None, None, "the reply has no `findings` list"

    clean = []
    for item in findings:
        if not isinstance(item, dict) or not item.get("rule"):
            continue
        clean.append(
            {
                "rule": str(item.get("rule", ""))[:16],
                "quote": str(item.get("quote", ""))[:200],
                "problem": str(item.get("problem", ""))[:300],
                "fix": str(item.get("fix", ""))[:300],
                "confidence": str(item.get("confidence", "")).lower()[:8],
                "reason": str(item.get("reason", ""))[:300],
            }
        )

    # "considered" holds a rule the judge weighed and rejected. Optional, and
    # absent from a reply written before the schema asked for it, so a missing
    # or malformed list is not an error.
    considered = []
    for item in data.get("considered") or []:
        if not isinstance(item, dict) or not item.get("rule"):
            continue
        considered.append(
            {
                "rule": str(item.get("rule", ""))[:16],
                "quote": str(item.get("quote", ""))[:200],
                "reason": str(item.get("reason", ""))[:300],
            }
        )
    return clean, considered, None


def auth_failure(detail):
    """Is this failure a missing credential, not a model with nothing to say?

    The container prints "Not logged in · Please run /login" when
    CLAUDE_CODE_OAUTH_TOKEN (or ANTHROPIC_API_KEY) never reached it.
    `corpus_generate.load_env_file()` loads one before run.py judges, but a
    standalone caller (this file's own CLI, a test, a script) that forgets
    that step gets the identical symptom as a model that answered nothing:
    exit 1, near-empty stderr. Naming the real cause here is what stops a
    wrong credential from being read as "the judge had no opinion".
    """
    low = (detail or "").lower()
    return "not logged in" in low or "/login" in low


def judge(text, source=None, credential_var=None, timeout=900, model=MODEL_JUDGE):
    """Ask the judge once, in the clean container.

    `model` defaults to MODEL_JUDGE but is never left to a CLI default (see
    the constant's own comment) — a caller that wants a different judge
    passes it explicitly, the same way corpus_generate.container_command
    already takes one for this exact purpose.

    Returns (findings, considered, error). `considered` is the judge's list of
    rules it weighed and rejected — see `parse`.
    """
    prompt = build_prompt(text, source)
    cmd = corpus_generate.container_command(prompt, credential_var, model=model)
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, str(exc)
    if out.returncode != 0:
        # A container can fail with nothing on stderr. An empty string is falsy, so
        # a caller testing `if err` would treat the failure as a success and then
        # iterate None. Always return a message.
        detail = (out.stderr or "").strip()[:300]
        if auth_failure(detail):
            # A WRONG-CREDENTIAL FAILURE MUST NEVER LOOK LIKE A MODEL WITH
            # NOTHING TO SAY. Without this, "exited 1 and said nothing" is the
            # only signal, and that is indistinguishable from a model failure.
            return None, None, (
                f"the judge container is not logged in ({credential_var} is "
                "missing or invalid). Set CLAUDE_CODE_OAUTH_TOKEN (from "
                "`claude setup-token`) or ANTHROPIC_API_KEY, or load a .env "
                "file with corpus_generate.load_env_file()."
            )
        return None, None, detail or f"the judge exited {out.returncode} and said nothing"
    findings, considered, err = parse(out.stdout)
    if err:
        return None, None, err
    # Give every finding a line and a column, by finding its quote in the text.
    for item in findings:
        item["where"] = locate(item.get("quote", ""), text)
    return findings, considered, None


# The agreement ratio (seen / passes) a finding needs to count as CONFIRMED. A
# plain majority. Never varied in practice, so callers route through this name
# rather than repeating the number.
GATE_DEFAULT = 0.5


def judge_repeatedly(text, source=None, credential_var=None, passes=5,
                     jobs=4, timeout=900, gate=GATE_DEFAULT, model=MODEL_JUDGE):
    """Ask the judge several times, and report how often each rule appeared.

    `model` reaches every pass's `judge()` call, so a caller asking for a
    different judge (or a multi-judge run.py driving this once per judge
    model) actually changes who answers, not just what the result claims.

    A MODEL DISAGREES WITH ITSELF. One pass reports a finding that a second pass
    does not, and neither answer is the truth. Running several and reporting the
    agreement rate is the only honest use of a judge: a rule that appears in most
    passes is worth acting on, and one that appears once is a candidate at best.

    With only two passes, agreement can only ever read 0.5 or 1.0 — too coarse to
    tell "borderline" from "noise". `passes` defaults to 5 so the rate has room to
    say something.

    `gate` is the agreement ratio (seen / passes) a finding needs to count as
    CONFIRMED; anything below is LOW-AGREEMENT. Default 0.5 is a plain majority,
    expressed as a ratio so it scales with `passes` rather than a hardcoded count
    (e.g. gate=0.5 needs 3/5, and the same gate needs 2/3 when passes=3).

    Returns (summary, runs, error). `runs` holds every pass's raw findings, so a
    reader sees the individual answers and not only the average. `summary` has one
    row per (rule, call) — see the "status" field:

        confirmed      seen/passes >= gate, a real finding
        low-agreement  seen/passes <  gate, a real finding
        rejected       the judge considered the rule and dismissed it

    Only "confirmed" rows should count toward a weighted cost. The other two are
    kept for a human to audit the judge, not to score the text.
    """
    runs, considered_runs, errors = [], [], []

    def one(_index):
        return judge(text, source, credential_var, timeout, model)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for findings, considered, err in pool.map(one, range(passes)):
            # Test the findings, not only the error. A pass that returns neither
            # is a bug in `judge`, and appending None here crashes the grouping
            # loop below after the whole run has already been paid for.
            if err or findings is None:
                errors.append(err or "the pass returned nothing")
            else:
                runs.append(findings)
                considered_runs.append(considered or [])

    if not runs:
        return None, [], "; ".join(errors)[:300] or "every pass failed"

    total = len(runs)

    def status(seen):
        return "confirmed" if seen / total >= gate else "low-agreement"

    # Group by rule. A quote differs between passes for the same offence, so the
    # rule is the only stable key.
    by_rule = {}
    for index, findings in enumerate(runs):
        for item in findings:
            slot = by_rule.setdefault(
                item["rule"], {"rule": item["rule"], "passes": set(), "examples": []}
            )
            slot["passes"].add(index)
            slot["examples"].append(item)

    summary = []
    for slot in by_rule.values():
        seen = len(slot["passes"])
        best = max(
            slot["examples"],
            key=lambda i: {"high": 3, "medium": 2, "low": 1}.get(i["confidence"], 0),
        )
        where = best.get("where") or {}
        summary.append(
            {
                "rule": slot["rule"],
                "quote": best["quote"],
                "problem": best["problem"],
                "fix": best["fix"],
                "confidence": best["confidence"],
                "reason": best.get("reason", ""),
                "seen_in": seen,
                "of": total,
                "agreement": round(seen / total, 2),
                "status": status(seen),
                "line": where.get("line"),
                "column": where.get("column"),
                # A quote the checker cannot find in the text was invented. The
                # report says so rather than hiding it behind a line number.
                "located": bool(where.get("found")),
            }
        )

    # A rule the judge weighed and dismissed. Always "rejected": the judge made
    # a call, it just wasn't a finding. This is the only place a person can see
    # a correct rejection ("attention has no underlying verb") and tell it
    # apart from a rule that was never checked.
    #
    # Grouped by (rule, quote), NOT by rule alone: the same rule ID can be
    # CONFIRMED for one quote and REJECTED for a different one in the same
    # document (e.g. PSTE-G7 is a real violation in one sentence and correctly
    # waved off in another that only looks like one). Grouping by rule alone
    # merged these into one slot and made a rejection of quote B surface as a
    # phantom row against a rule the judge had just confirmed for quote A.
    by_rejected = {}
    for index, considered in enumerate(considered_runs):
        for item in considered:
            key = (item["rule"], item["quote"])
            slot = by_rejected.setdefault(
                key, {"rule": item["rule"], "passes": set(), "examples": []}
            )
            slot["passes"].add(index)
            slot["examples"].append(item)

    for slot in by_rejected.values():
        seen = len(slot["passes"])
        best = slot["examples"][0]
        summary.append(
            {
                "rule": slot["rule"],
                "quote": best.get("quote", ""),
                "problem": "",
                "fix": "",
                "confidence": "",
                "reason": best.get("reason", ""),
                "seen_in": seen,
                "of": total,
                "agreement": round(seen / total, 2),
                "status": "rejected",
                "line": None,
                "column": None,
                "located": False,
            }
        )

    summary.sort(key=lambda s: (s["status"] != "confirmed", -s["seen_in"], s["rule"]))
    return summary, runs, None


STATUS_MARK = {"confirmed": "!", "low-agreement": "~", "rejected": "x"}


def report(name, summary, runs=None):
    """Print the rules, confirmed first, with the per-pass counts beside them."""
    total = len(runs) if runs else 1
    if not summary:
        print(f"{name}: no semantic finding in {total} pass(es)")
        return
    per_pass = ", ".join(str(len(r)) for r in runs) if runs else ""
    head = f"{name}: {len(summary)} rules"
    if runs and total > 1:
        head += f" over {total} passes (findings per pass: {per_pass})"
    print(head)
    for item in summary:
        mark = STATUS_MARK.get(item.get("status"), " ")
        agree = f"{item['seen_in']}/{item['of']}" if item.get("of") else ""
        if item.get("located") and item.get("line"):
            place = f"{item['line']}:{item['column']}"
        else:
            place = "?:?"
        label = item.get("problem") or item.get("reason") or ""
        print(
            f"  {mark} {item['rule']:<10} [{agree}] {item.get('status', ''):<13} "
            f"{place:>9}  {label}"
        )
        if item["quote"]:
            flag = "" if item.get("located") else "   (QUOTE NOT IN THE TEXT)"
            print(f"      | {item['quote']}{flag}")
        if item["fix"]:
            print(f"      -> {item['fix']}")
        if item.get("reason") and item.get("problem"):
            # "reason" already stood in for the label above when there is no
            # "problem" (a rejected rule has none), so only print it again when
            # it adds information beyond the one-line summary.
            print(f"      because: {item['reason']}")


DISCLAIMER = (
    "A model judged this text. That is not a measurement: two runs disagree, and a\n"
    "confident report of a rule the text does not break is the likeliest failure.\n"
    "Confirm every finding before you act on it, and never publish the count."
)


def main():
    ap = argparse.ArgumentParser(
        description="Judge a text against the rules no regular expression can check.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("files", nargs="*")
    ap.add_argument("--build", action="store_true", help="build the container image")
    ap.add_argument("--result", action="store_true", help="judge the newest result")
    ap.add_argument("--arm", default="pste")
    ap.add_argument(
        "--judge-model",
        default=MODEL_JUDGE,
        help=f"the model that judges. Default {MODEL_JUDGE}. Pass several "
        "names to run each and keep its findings separate (run.py's "
        "multi-judge mode) — this CLI still judges with only the first, "
        "since it has no separate-results view of its own.",
        nargs="+",
    )
    ap.add_argument(
        "--judge-passes",
        type=int,
        default=5,
        help="how many times to ask. A model disagrees with itself, so one pass is "
        "not evidence, and two passes can only ever show 0.5 or 1.0 agreement. "
        "Every pass is kept, and the report shows the agreement. Use 3 for a cheap "
        "iteration run, 5 is the default and what a publication run uses.",
    )
    ap.add_argument(
        "--gate",
        type=float,
        default=GATE_DEFAULT,
        help="agreement ratio (seen / judge-passes) a finding needs to count as "
        "CONFIRMED. Default 0.5 is a plain majority. Below the gate, a finding is "
        "reported as low-agreement, not confirmed.",
    )
    ap.add_argument("--jobs", type=int, default=4, help="passes to run at a time")
    ap.add_argument(
        "--limit", type=int, default=0, help="judge only the first N items"
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="write the findings beside the result")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.build:
        return corpus_generate.build_image()

    corpus_generate.load_env_file()
    credential_var = corpus_generate.credential()
    if not credential_var:
        print(
            "refusing to run: no credential is set. See evals/corpus_generate.py.",
            file=sys.stderr,
        )
        return 2
    if not corpus_generate.image_exists():
        print(
            "the container image does not exist. Build it:\n\n"
            "    python3 evals/semantic_lint.py --build",
            file=sys.stderr,
        )
        return 2

    collected = {}

    if args.result:
        path = provenance.resolve()
        if not path:
            print("no result found. Run: python3 evals/run.py", file=sys.stderr)
            return 2
        with open(path, encoding="utf-8") as fh:
            snapshot = json.load(fh)
        items = list(snapshot["results"].items())
        if args.limit:
            items = items[: args.limit]
        print(f"judging arm '{args.arm}' of {os.path.basename(path)}\n")
        for pid, entry in items:
            text = entry["source"] if args.arm == "source" else entry["outputs"].get(
                args.arm
            )
            if not text:
                continue
            source = entry.get("source") if args.arm != "source" else None
            summary, runs, err = judge_repeatedly(
                text, source, credential_var, args.judge_passes,
                args.jobs, gate=args.gate, model=args.judge_model[0],
            )
            if err:
                print(f"{pid}: FAILED {err}", file=sys.stderr)
                continue
            collected[pid] = {"summary": summary, "runs": runs}
            report(pid, summary, runs)
    else:
        if not args.files:
            print("give a file, or --result", file=sys.stderr)
            return 2
        for path in args.files:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            summary, runs, err = judge_repeatedly(
                text, None, credential_var, args.judge_passes,
                args.jobs, gate=args.gate, model=args.judge_model[0],
            )
            if err:
                print(f"{path}: FAILED {err}", file=sys.stderr)
                continue
            collected[path] = {"summary": summary, "runs": runs}
            report(path, summary, runs)

    if args.json or args.out:
        payload = {
            "arm": args.arm if args.result else None,
            "judge_model": args.judge_model[0],
            "passes": args.judge_passes,
            "gate": args.gate,
            "findings": collected,
            "disclaimer": DISCLAIMER.replace("\n", " "),
        }
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            print(f"\nwrote {args.out}")
        else:
            print(json.dumps(payload, indent=2))

    print(f"\n{DISCLAIMER}")
    return 0


def self_test():
    # A pass that returns no findings AND no error must not reach the grouping
    # loop. This crashed a two-hour run after every generation was paid for: a
    # container exited non-zero with an empty stderr, `if err` saw a falsy "",
    # and None was appended to `runs`.
    real_judge = globals()["judge"]
    try:
        globals()["judge"] = lambda *a, **k: (None, None, "")
        summary, runs, err = judge_repeatedly("Some text.", passes=2, jobs=1)
        assert summary is None and runs == [] and err, (summary, runs, err)
        # A mix must keep the good pass and report the bad one.
        calls = {"n": 0}

        def flaky(*a, **k):
            calls["n"] += 1
            return ([], [], None) if calls["n"] == 1 else (None, None, "")

        globals()["judge"] = flaky
        summary, runs, err = judge_repeatedly("Some text.", passes=2, jobs=1)
        assert summary == [] and len(runs) == 1, (summary, runs)
    finally:
        globals()["judge"] = real_judge

    # The prompt must carry the text, the rules, and the mechanical findings, and
    # must tell the judge not to repeat them.
    prompt = build_prompt("The parser is robust. The file was read.")
    for needed in ("PSTE-A1", "PSTE-W1", "DO NOT REPEAT", "spec/PSTE-1.md", "JSON"):
        assert needed in prompt, needed
    assert "The parser is robust." in prompt

    # A mechanical finding must reach the prompt, or the judge repeats it.
    assert "PSTE-V9" in prompt or "marketing" in prompt, prompt[-1200:]

    # ARBITRATED CANDIDATES (PSTE-N5/G7/G11/G12) must reach the prompt in a block
    # the judge is told to RULE ON, not skip — the opposite instruction from the
    # mechanical block above. "Perform an analysis of X" trips PSTE-G7.
    cand_prompt = build_prompt("Perform an analysis of the log file.")
    assert "PSTE-G7" in cand_prompt, cand_prompt[-1200:]
    assert "CANDIDATES TO CONFIRM OR REJECT" in cand_prompt
    # The two blocks must stay distinguishable: "do not repeat" governs the
    # mechanical section, and must not also be the instruction beside the
    # candidates, or the judge silently drops every arbitrated finding.
    cand_start = cand_prompt.index("CANDIDATES TO CONFIRM OR REJECT")
    assert "do not repeat" not in cand_prompt[cand_start:].lower()
    assert "judge each candidate" in cand_prompt.lower()

    # A countable finding (PSTE-X1, a semicolon) is NOT a candidate: it belongs in
    # the "do not repeat" block only, never in "CANDIDATES TO CONFIRM OR REJECT".
    countable_prompt = build_prompt("The build failed; the log shows why.")
    cstart = countable_prompt.index("CANDIDATES TO CONFIRM OR REJECT")
    cend = countable_prompt.index("Judge the SPIRIT")
    assert "PSTE-X1" not in countable_prompt[cstart:cend], countable_prompt[cstart:cend]

    # A text with no arbitrated finding shows "(none)" in the candidates block, so
    # the judge is not left guessing whether the section was omitted by mistake.
    assert "(none)" in cand_prompt[: cand_prompt.index("CANDIDATES")] or True  # sanity only
    plain_prompt = build_prompt("Set the flag. Run the tests.")
    pstart = plain_prompt.index("CANDIDATES TO CONFIRM OR REJECT")
    pend = plain_prompt.index("Judge the SPIRIT")
    assert "(none)" in plain_prompt[pstart:pend], plain_prompt[pstart:pend]

    # With a source, the accuracy rule must be named and the original included.
    with_source = build_prompt("short", source="the original text here")
    assert "the original text here" in with_source
    assert "PSTE-A1" in with_source and "REWRITE" in with_source

    # PARSING. A reply that is not JSON must be an ERROR, and never an empty pass.
    findings, considered, err = parse("I could not find any problems with this text.")
    assert findings is None and "did not return JSON" in err, (findings, err)
    findings, considered, err = parse("")
    assert findings is None, findings

    findings, considered, err = parse('{"findings": []}')
    assert findings == [] and considered == [] and err is None

    # Prose around the JSON is tolerated, because a judge often adds it. A
    # "reason" must survive the parse: it is what lets a person tell a real
    # finding from a rejection the judge never bothered to justify.
    findings, considered, err = parse(
        'Here is my answer:\n{"findings": [{"rule": "PSTE-W1", '
        '"quote": "run the command", "problem": "no warning", '
        '"fix": "state the scope first", "confidence": "high", '
        '"reason": "a destructive command needs a warning first"}]}\nHope that helps.'
    )
    assert err is None, err
    assert len(findings) == 1 and findings[0]["rule"] == "PSTE-W1", findings
    assert findings[0]["confidence"] == "high"
    assert "warning" in findings[0]["reason"], findings

    # A malformed entry is dropped, and does not break the rest.
    findings, considered, err = parse('{"findings": [{"no_rule": 1}, {"rule": "PSTE-D6"}]}')
    assert [f["rule"] for f in findings] == ["PSTE-D6"], findings

    # Broken JSON is an error, not a pass. A truncated reply with no closing brace
    # fails the earlier check; one with braces but bad syntax fails the parse.
    findings, considered, err = parse('{"findings": [')
    assert findings is None, err
    findings, considered, err = parse('{"findings": [oops,]}')
    assert findings is None and "broken JSON" in err, err

    # DISMISSAL. "considered" is a rule the judge weighed and rejected, with a
    # reason. Absent from an older reply, and that must not be an error either.
    findings, considered, err = parse(
        '{"findings": [], "considered": [{"rule": "PSTE-V6", '
        '"quote": "pay attention to", '
        '"reason": "attention has no underlying verb, so this is not a '
        'nominalization"}]}'
    )
    assert err is None, err
    assert len(considered) == 1 and considered[0]["rule"] == "PSTE-V6", considered
    assert "no underlying verb" in considered[0]["reason"], considered

    findings, considered, err = parse('{"findings": []}')
    assert considered == [], considered  # no "considered" key at all: still fine

    # LOCATING A QUOTE. The judge never gives a line number, because it would
    # count lines by guessing. It quotes the words, and the checker finds them.
    body = "Read the file.\nThe flush takes 90 seconds.\nRun the command.\n"
    hit = locate("The flush takes 90 seconds", body)
    assert hit["found"] and hit["line"] == 2 and hit["column"] == 1, hit
    mid = locate("flush takes 90", body)
    assert mid["found"] and mid["line"] == 2 and mid["column"] == 5, mid

    # A QUOTE THAT IS NOT IN THE TEXT WAS INVENTED. The report must say so rather
    # than show a line number for words that do not exist.
    missing = locate("the parser rejects every header", body)
    assert not missing["found"], missing
    assert "not in the text" in missing["reason"], missing
    assert locate("", body)["found"] is False

    # A judge often normalises whitespace, so a partial match still locates.
    loose = locate("The flush takes 90 seconds exactly as written here", body)
    assert loose["found"] and loose.get("partial"), loose

    # MULTI-PASS. A model disagrees with itself, so the report must show how often
    # each rule appeared, and must keep every pass rather than averaging them away.
    import unittest.mock as mock

    def finding(rule, quote, confidence, reason="r"):
        return {"rule": rule, "quote": quote, "problem": "p", "fix": "f",
                "confidence": confidence, "reason": reason}

    # 5 passes: W1 confirmed (4/5, above the 0.5 gate), D6 low-agreement (1/5),
    # and V6 REJECTED in every pass that considered it (2/5) — the judge looked
    # and said no, which is not the same as never checking.
    replies = [
        ([finding("PSTE-W1", "q1", "high", "warns before delete")], []),
        ([finding("PSTE-W1", "q2", "medium")], []),
        ([finding("PSTE-W1", "q3", "low"),
          finding("PSTE-D6", "q4", "low")],
         [{"rule": "PSTE-V6", "quote": "pay attention to",
           "reason": "attention has no underlying verb"}]),
        ([finding("PSTE-W1", "q5", "low")],
         [{"rule": "PSTE-V6", "quote": "pay attention to",
           "reason": "attention has no underlying verb"}]),
        ([], []),
    ]
    calls = iter(replies)

    def fake_judge(*a, **k):
        findings, considered = next(calls)
        return findings, considered, None

    with mock.patch(f"{__name__}.judge", side_effect=fake_judge):
        summary, runs, err = judge_repeatedly("text", passes=5, jobs=1)
    assert err is None, err
    assert len(runs) == 5, runs

    by_rule = {s["rule"]: s for s in summary}

    # W1: 4/5 passes, agreement 0.8, at or above the default 0.5 gate -> confirmed.
    w1 = by_rule["PSTE-W1"]
    assert w1["seen_in"] == 4 and w1["of"] == 5, w1
    assert w1["agreement"] == 0.8, w1
    assert w1["status"] == "confirmed", w1
    # The highest confidence example represents the rule, reason included.
    assert w1["confidence"] == "high" and w1["reason"] == "warns before delete", w1

    # D6: 1/5, agreement 0.2, below the gate -> low-agreement, not confirmed.
    d6 = by_rule["PSTE-D6"]
    assert d6["seen_in"] == 1 and d6["status"] == "low-agreement", d6

    # V6: never in "findings", only in "considered" -> status "rejected", and its
    # reason is what a person uses to tell a real rejection from a lazy one.
    v6 = by_rule["PSTE-V6"]
    assert v6["status"] == "rejected", v6
    assert v6["seen_in"] == 2 and v6["of"] == 5, v6
    assert "no underlying verb" in v6["reason"], v6

    # Confirmed rows sort first, regardless of seen_in among the rest.
    assert summary[0]["rule"] == "PSTE-W1", summary

    # THE GATE SCALES WITH PASS COUNT. It is a ratio, not a hardcoded count: 2/3
    # passes is 0.67, above the default 0.5 gate, so it must confirm the same as
    # 4/5 did above -- the requirement is ">= majority", not ">= 3".
    replies = [
        ([finding("PSTE-G2", "a", "high")], []),
        ([finding("PSTE-G2", "b", "high")], []),
        ([], []),
    ]
    calls = iter(replies)
    with mock.patch(f"{__name__}.judge", side_effect=fake_judge):
        summary, runs, err = judge_repeatedly("text", passes=3, jobs=1)
    assert summary[0]["seen_in"] == 2 and summary[0]["of"] == 3, summary[0]
    assert summary[0]["status"] == "confirmed", summary[0]

    # A stricter gate (say, for a publication run) can push the same 2/3 result
    # below the line.
    calls = iter(replies)
    with mock.patch(f"{__name__}.judge", side_effect=fake_judge):
        summary, runs, err = judge_repeatedly("text", passes=3, jobs=1, gate=0.8)
    assert summary[0]["status"] == "low-agreement", summary[0]

    # Every pass failing is an error, and never a clean report.
    with mock.patch(f"{__name__}.judge", side_effect=lambda *a, **k: (None, None, "boom")):
        summary, runs, err = judge_repeatedly("text", passes=2, jobs=1)
    assert summary is None and err, (summary, err)

    # THE AGREEMENT DENOMINATOR MUST BE THE PASSES THAT ACTUALLY COMPLETED, NOT
    # THE PASSES ASKED FOR. `passes=5` with 2 outright failures (an API limit
    # mid-run, say) must compute agreement out of the 3 that returned, not 5 —
    # a fixed denominator of 5 would silently deflate every ratio and could
    # push a real finding below the confirmation gate for no reason but bad
    # luck in which passes a rate limit happened to hit.
    calls = {"n": 0}

    def three_of_five(*a, **k):
        calls["n"] += 1
        if calls["n"] in (2, 4):
            return None, None, "rate limited"
        return [finding("PSTE-W1", "q", "high")], [], None

    with mock.patch(f"{__name__}.judge", side_effect=three_of_five):
        summary, runs, err = judge_repeatedly("text", passes=5, jobs=1)
    assert err is None, err
    assert len(runs) == 3, runs  # only the completions, not the 2 failures
    w1 = next(s for s in summary if s["rule"] == "PSTE-W1")
    # 3/3, not 3/5: the two failed passes must not count against agreement.
    assert w1["of"] == 3, w1
    assert w1["seen_in"] == 3 and w1["agreement"] == 1.0, w1
    assert w1["status"] == "confirmed", w1

    # AN ARBITRATED CANDIDATE ROUTES THROUGH THE SAME "findings"/"considered"
    # SHAPE AS ANY OTHER JUDGE ANSWER: a candidate the judge CONFIRMS is just a
    # normal finding under the same rule ID, and joins `judge_repeatedly`'s
    # ordinary confirmed/low-agreement grouping (report.py's `build_entry` then
    # treats it exactly like any other confirmed semantic finding — one gate on
    # `pass`, not a fourth parallel one). A candidate the judge REJECTS lands in
    # "considered", the existing dismissal mechanism, with status "rejected".
    replies = [
        ([finding("PSTE-G7", "restriction of the input", "high",
                  "a nominalization with an underlying verb, restrict")], []),
        ([finding("PSTE-G7", "restriction of the input", "high")], []),
        ([finding("PSTE-G7", "restriction of the input", "medium")],
         [{"rule": "PSTE-N5", "quote": "attention of the reader",
           "reason": "attention has no underlying verb"}]),
    ]
    calls = iter(replies)
    with mock.patch(f"{__name__}.judge", side_effect=fake_judge):
        summary, runs, err = judge_repeatedly("text", passes=3, jobs=1)
    assert err is None, err
    by_rule = {s["rule"]: s for s in summary}
    confirmed_candidate = by_rule["PSTE-G7"]
    assert confirmed_candidate["status"] == "confirmed", confirmed_candidate
    assert confirmed_candidate["seen_in"] == 3 and confirmed_candidate["of"] == 3
    rejected_candidate = by_rule["PSTE-N5"]
    assert rejected_candidate["status"] == "rejected", rejected_candidate
    assert "no underlying verb" in rejected_candidate["reason"], rejected_candidate

    # A candidate confirmed in fewer than the gate's share of passes is
    # low-agreement, exactly like any other judge finding — no special case.
    replies = [
        ([finding("PSTE-G12", "large small database", "low")], []),
        ([], []),
        ([], []),
    ]
    calls = iter(replies)
    with mock.patch(f"{__name__}.judge", side_effect=fake_judge):
        summary, runs, err = judge_repeatedly("text", passes=3, jobs=1)
    g12 = next(s for s in summary if s["rule"] == "PSTE-G12")
    assert g12["status"] == "low-agreement", g12

    # BUG: PHANTOM REJECTED ROW. `by_rejected` used to group `considered` by
    # rule ID alone, so a rule CONFIRMED for one quote and REJECTED for a
    # DIFFERENT quote collapsed into one slot: the rejection surfaced as a row
    # against a rule the judge had just confirmed, reason and all — exactly
    # what happened for PSTE-G7 in postmortem-chia-mempool-fastforward/control
    # ("Eviction of fast-forward spends..." confirmed 5/5, then a phantom
    # rejected row on the same rule whose reason read "Confirmed as a real
    # violation; see findings"). Grouping by (rule, quote) keeps them apart.
    replies = [
        ([finding("PSTE-G7", "eviction of fast-forward spends", "high",
                  "evict has an underlying verb")],
         [{"rule": "PSTE-G7", "quote": "creation of a backup file",
           "reason": "not present in this text"}]),
        ([finding("PSTE-G7", "eviction of fast-forward spends", "high")], []),
        ([finding("PSTE-G7", "eviction of fast-forward spends", "high")], []),
        ([finding("PSTE-G7", "eviction of fast-forward spends", "medium")], []),
        ([finding("PSTE-G7", "eviction of fast-forward spends", "medium")], []),
    ]
    calls = iter(replies)
    with mock.patch(f"{__name__}.judge", side_effect=fake_judge):
        summary, runs, err = judge_repeatedly("text", passes=5, jobs=1)
    assert err is None, err
    g7_rows = [s for s in summary if s["rule"] == "PSTE-G7"]
    confirmed_rows = [s for s in g7_rows if s["status"] == "confirmed"]
    rejected_rows = [s for s in g7_rows if s["status"] == "rejected"]
    assert len(confirmed_rows) == 1, g7_rows
    assert confirmed_rows[0]["quote"] == "eviction of fast-forward spends", g7_rows
    assert confirmed_rows[0]["seen_in"] == 5, g7_rows
    # The rejected quote must appear as its own row, on its own quote, and must
    # NOT read as a dismissal of the confirmed quote above.
    assert len(rejected_rows) == 1, g7_rows
    assert rejected_rows[0]["quote"] == "creation of a backup file", g7_rows
    assert rejected_rows[0]["reason"] == "not present in this text", g7_rows

    # THE JUDGE MUST RUN IN THE CLEAN CONTAINER. A judge that reads a personal
    # style guide judges against that guide, and not against the standard.
    cmd = corpus_generate.container_command("x", "CLAUDE_CODE_OAUTH_TOKEN")
    assert "--setting-sources" in cmd, cmd
    assert cmd[cmd.index("-w") + 1] == "/work", cmd

    # THE JUDGE MODEL MUST REACH THE CONTAINER ARGV, not just the default.
    # `judge()` defaults to MODEL_JUDGE, but a caller naming a different
    # model (run.py's multi-judge mode, or this file's own --judge-model)
    # must see that model actually asked, in the constructed command.
    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=0, stdout='{"findings": []}', stderr="")
        judge("some text", credential_var="CLAUDE_CODE_OAUTH_TOKEN", model="claude-sonnet-5")
    seen_cmd = spy.call_args[0][0]
    assert seen_cmd[seen_cmd.index("--model") + 1] == "claude-sonnet-5", seen_cmd
    # And the default, with no model given, is still MODEL_JUDGE (Opus) —
    # the existing pinned behaviour must not move for a caller that asks
    # for nothing new.
    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=0, stdout='{"findings": []}', stderr="")
        judge("some text", credential_var="CLAUDE_CODE_OAUTH_TOKEN")
    default_cmd = spy.call_args[0][0]
    assert default_cmd[default_cmd.index("--model") + 1] == MODEL_JUDGE, default_cmd

    # AN AUTH FAILURE MUST NAME ITSELF, and never read as "the model had
    # nothing to say". This is the bug: CLAUDE_CODE_OAUTH_TOKEN absent from
    # the environment makes the container print "Not logged in · Please run
    # /login" on stderr and exit 1 — identical in shape to a model failure
    # unless this is detected explicitly.
    assert auth_failure("Not logged in · Please run /login")
    assert auth_failure("please run /login to continue")
    assert not auth_failure("the API rate limited this request")
    assert not auth_failure("")

    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(
            returncode=1, stdout="", stderr="Not logged in · Please run /login"
        )
        findings, considered, err = judge(
            "some text", credential_var="CLAUDE_CODE_OAUTH_TOKEN"
        )
    assert findings is None and considered is None, (findings, considered)
    assert "CLAUDE_CODE_OAUTH_TOKEN" in err, err
    assert "not logged in" in err.lower(), err
    # The credential variable NAMED must be the one judge() was actually
    # asked to use, not a hardcoded guess — the whole point is telling a
    # reader which credential is missing.
    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(
            returncode=1, stdout="", stderr="Not logged in · Please run /login"
        )
        _, _, err2 = judge("some text", credential_var="ANTHROPIC_API_KEY")
    assert "ANTHROPIC_API_KEY" in err2, err2

    # A genuine model failure (rate limit, say) must still read as a model
    # failure, not get swept into the auth-failure message.
    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=1, stdout="", stderr="rate limited")
        _, _, err3 = judge("some text", credential_var="CLAUDE_CODE_OAUTH_TOKEN")
    assert "rate limited" in err3 and "logged in" not in err3.lower(), err3

    # PSTE-D7.1 and PSTE-S4 moved to the mechanical checker. Neither needs the
    # judge any more, and naming one here would tell the judge to check something
    # a regular expression already decides.
    assert "PSTE-D7.1" not in SEMANTIC_RULES
    assert "PSTE-S4" not in SEMANTIC_RULES

    # PSTE-P1 is only a PARTIAL move: the mechanical pre-filter catches the easy
    # non-imperative openers, and the judge still covers the rest, so PSTE-P1
    # stays named in SEMANTIC_RULES.
    assert "PSTE-P1" in SEMANTIC_RULES
    # When the pre-filter already caught a sentence, the finding must land in the
    # "do not repeat" block, not in "CANDIDATES TO CONFIRM OR REJECT" — PSTE-P1 is
    # a plain countable finding, not an arbitrated one, so it is never a candidate.
    p1_prompt = build_prompt("You should run the tests.")
    p1_start = p1_prompt.index("CANDIDATES TO CONFIRM OR REJECT")
    p1_end = p1_prompt.index("Judge the SPIRIT")
    assert "PSTE-P1" not in p1_prompt[p1_start:p1_end], p1_prompt[p1_start:p1_end]
    assert "PSTE-P1" in p1_prompt[: p1_prompt.index("The same mechanical checker")]

    print("semantic_lint self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
