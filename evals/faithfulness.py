#!/usr/bin/env python3
"""Check that a rewrite keeps every fact from its source.

    python3 evals/faithfulness.py SOURCE REWRITE
    python3 evals/faithfulness.py --json SOURCE REWRITE
    python3 evals/faithfulness.py --self-test

WHY THIS MATTERS MORE THAN ANY OTHER CHECK HERE

Rule PSTE-A1 says that accuracy defeats every other rule in the standard. Nothing
enforced it until now, and the rule checker makes the problem worse: a rewrite that
drops a condition or a number scores BETTER there, because it has fewer words to
break a rule with. The checker rewards the failure that the standard most fears.

This script is the guard. It compares a source with its rewrite and reports what
the rewrite lost or changed.

WHAT IT CHECKS, AND WHY EACH CHECK IS DETERMINISTIC

    numbers      every number, with its unit, must survive
    units        a unit must not change (30 seconds must not become 30 minutes)
    identifiers  every code span, path, flag, and symbol must survive
    negation     a negated statement must not lose its negation
    modals       an obligation must not weaken into a suggestion
    conditions   an "if", "unless", or "when" clause must not disappear
    quantifiers  "every" must not become "some"

Research on entailment models records that they score a rewrite as faithful even
after a number changes (Park 2019, "Breaking Numerical Reasoning in NLI"). A
rewrite that turns "30 seconds" into "300 seconds" is exactly the error this
project must catch, so every check here is a deterministic comparison and not a
model. The checks are cheap, they need no network, and they never disagree with
themselves between runs.

WHAT IT DOES NOT DO

It does not understand meaning. A rewrite can keep every number and still say
something false. A model that checks entailment would catch more, at the cost of a
large dependency and a documented blind spot for numbers. See
`evals/FUTURE-WORK.md`.

It reports what the rewrite LOST. It does not report what the rewrite ADDED, other
than a changed unit or a changed number.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import pste_lint  # noqa: E402

# A number, with an optional unit attached. Keeps the pair together so that a
# changed unit is visible.
UNITS = (
    r"ms|s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|"
    r"day|days|week|weeks|month|months|year|years|"
    r"b|kb|mb|gb|tb|byte|bytes|kib|mib|gib|"
    r"%|percent|x|times|attempt|attempts|retry|retries|"
    r"request|requests|row|rows|item|items|char|chars|character|characters|"
    r"node|nodes|pod|pods|replica|replicas|thread|threads|connection|connections"
)
NUMBER_RE = re.compile(
    rf"(?<![\w.])(\d+(?:[.,]\d+)*)\s*({UNITS})?(?![\w])", re.IGNORECASE
)

# Spelled-out numbers one to ten, folded to their digit so "three bugs" equals
# "3 bugs". A rewrite that spells out a number has not dropped it. Kept small on
# purpose: past ten, a spelled-out number is rare in the kind of technical prose
# this project checks, and a wider list is more surface for a false match (e.g.
# "second" as an ordinal, not a count).
NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}
NUMBER_WORD_RE = re.compile(
    rf"\b({'|'.join(NUMBER_WORDS)})\s*({UNITS})?(?![\w])", re.IGNORECASE
)

# An identifier span pairs backticks three ways, tried in this order:
#   :role:`...`   an RST cross-reference. Sphinx wraps these across a line break
#                 (":doc:`install the new Django version\n</topics/install>`"),
#                 so this branch allows a newline inside the span.
#   ``...``       an RST literal (double backtick). Also allowed to span lines.
#   `...`         a plain backtick identifier, the common case. Kept to one line:
#                 without a role or a doubled backtick to bound it, letting this
#                 branch cross a newline means one stray unpaired backtick
#                 swallows everything up to the next backtick in the document.
#
# The double- and single-backtick branches exclude a third adjacent backtick
# (the `(?<!`)...(?!`)` guards) so a markdown ``` fenced code block is never
# read as a pair: without the guard, the double-backtick branch consumes two
# of the three fence backticks and treats the whole code block body — fence
# language tag included — as one "identifier" the rewrite can never match
# verbatim, even when it reproduces the command exactly.
IDENT_RE = re.compile(
    r":[a-zA-Z][\w-]*:`([^`]+)`|(?<!`)``([^`]+)``(?!`)|(?<!`)`([^`\n]+)`(?!`)"
)
BARE_IDENT_RE = re.compile(
    r"(?<![\w`])((?:--?[a-zA-Z][\w-]*)|(?:[\w./-]+\.(?:py|js|ts|go|rs|java|rb|yaml|yml|json|toml|md|sh|sql))|(?:[A-Z][A-Z0-9_]{2,}))(?![\w`])"
)

NEGATION_RE = re.compile(
    r"\b(?:not|never|no|none|cannot|must not|do not|does not|will not|without)\b",
    re.IGNORECASE,
)
OBLIGATION_RE = re.compile(r"\b(?:must|required|shall|mandatory|always|never)\b", re.IGNORECASE)
SUGGESTION_RE = re.compile(r"\b(?:should|may|might|can|could|consider|optionally)\b", re.IGNORECASE)
CONDITION_RE = re.compile(r"\b(?:if|unless|when|whenever|before|after|until|while|once)\b", re.IGNORECASE)
UNIVERSAL_RE = re.compile(r"\b(?:every|all|each|any|always|entire|whole)\b", re.IGNORECASE)
PARTIAL_RE = re.compile(r"\b(?:some|several|many|most|few|often|usually|sometimes)\b", re.IGNORECASE)


def _show(value, unit):
    """Render a number with its unit for a message, pluralised so it reads right."""
    if not unit:
        return value
    if unit in ("percent", "ms", "kb", "mb", "gb", "times"):
        return f"{value} {unit}"
    plural = value not in ("1", "1.0")
    return f"{value} {unit}s" if plural else f"{value} {unit}"


def _numbers(text):
    """Every number in the text, paired with its unit where one follows.

    Includes spelled-out numbers one to ten (NUMBER_WORDS), folded to their
    digit form: "wait three minutes" and "wait 3 minutes" both produce
    ("3", "minute"), so a rewrite that spells out a number is not a dropped
    fact, and one that spells it out AND changes the unit still gets caught.
    """
    out = []
    for m in NUMBER_RE.finditer(text):
        value = m.group(1).replace(",", "")
        unit = (m.group(2) or "").lower()
        out.append((value, _canonical_unit(unit)))
    for m in NUMBER_WORD_RE.finditer(text):
        value = NUMBER_WORDS[m.group(1).lower()]
        unit = (m.group(2) or "").lower()
        out.append((value, _canonical_unit(unit)))
    return out


def _canonical_unit(unit):
    """Fold spellings of one unit together, so `30 s` equals `30 seconds`."""
    u = unit.lower().rstrip(".")
    groups = {
        "ms": {"ms"},
        "second": {"s", "sec", "secs", "second", "seconds"},
        "minute": {"m", "min", "mins", "minute", "minutes"},
        "hour": {"h", "hr", "hrs", "hour", "hours"},
        "day": {"day", "days"},
        "week": {"week", "weeks"},
        "month": {"month", "months"},
        "year": {"year", "years"},
        "byte": {"b", "byte", "bytes"},
        "kb": {"kb", "kib"},
        "mb": {"mb", "mib"},
        "gb": {"gb", "gib"},
        "percent": {"%", "percent"},
        # "3 times", "3 attempts", and "3 retries" state the same count. Folding
        # them together stops a legitimate paraphrase from reading as a lost fact.
        "times": {"x", "times", "attempt", "attempts", "retry", "retries"},
        "request": {"request", "requests"},
        "row": {"row", "rows"},
        "item": {"item", "items"},
    }
    for name, members in groups.items():
        if u in members:
            return name
    return u


def _identifiers(text):
    out = set()
    for m in IDENT_RE.finditer(text):
        span = next(g for g in m.groups() if g is not None)
        out.add(span.strip())
    out |= set(m.group(1).strip() for m in BARE_IDENT_RE.finditer(text))
    return {i for i in out if i}


def _normalise_ident(ident):
    """Collapse internal whitespace, including a hard-wrapped newline, to one space.

    A `:role:`...`` or ``...`` span is allowed to CAPTURE a line break, because
    Sphinx wraps them (see IDENT_RE's comment). But the source and the rewrite
    do not wrap at the same column, so comparing the captured spans verbatim
    makes a reflowed line read as a dropped identifier when every word survived.
    Normalising here, at compare time, keeps the raw captured span (with its
    newline) available to any caller that wants it — only the comparison folds
    the whitespace.
    """
    return re.sub(r"\s+", " ", ident)


def _strip_frontmatter(text):
    """Drop a leading YAML front matter block, so its fields are not compared.

    Matches the idiom already used for `evals/run.py`'s `load_skill()` and
    `evals/corpus_add.py`'s `strip_site_machinery()`: a document opens with a
    bare `---` line, and the block ends at the next line that is just `---`.

    A real document can legitimately open with `---` as a markdown horizontal
    rule, so this only strips when a matching closing `---` line follows; a
    lone leading `---` with no close is left alone.
    """
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def _counts(text, pattern):
    return len(pattern.findall(text))


def compare(source, rewrite):
    """Report what the rewrite lost or changed. Empty findings means nothing lost."""
    # A synthetic corpus document stores its generation prompt as YAML front
    # matter in `source` (see evals/corpus/MANIFEST.yaml: "the question is in
    # the front matter"). That block carries a build version, a date, and
    # other machinery the rewrite was never asked to repeat, so comparing it
    # manufactures fact loss out of the prompt rather than the document.
    source = _strip_frontmatter(source)
    rewrite = _strip_frontmatter(rewrite)
    findings = []

    def add(kind, severity, message):
        findings.append({"kind": kind, "severity": severity, "message": message})

    # Numbers. Compare as a multiset so a repeated value must repeat.
    src_nums, rw_nums = _numbers(source), _numbers(rewrite)
    from collections import Counter

    src_c, rw_c = Counter(src_nums), Counter(rw_nums)

    for pair, n in src_c.items():
        missing = n - rw_c.get(pair, 0)
        if missing <= 0:
            continue
        value, unit = pair
        shown = _show(value, unit)
        # Did the same value survive with a different unit?
        same_value = [u for (v, u) in rw_nums if v == value and u != unit]
        if same_value:
            add(
                "unit",
                "critical",
                f"'{shown}' became '{_show(value, same_value[0])}'. "
                "The unit changed.",
            )
        else:
            near = [v for (v, u) in rw_nums if u == unit and v != value]
            if near:
                add(
                    "number",
                    "critical",
                    f"'{shown}' is missing. The rewrite has "
                    f"'{_show(near[0], unit)}'.",
                )
            else:
                add("number", "critical", f"'{shown}' is missing from the rewrite.")

    # Identifiers. Compared with internal whitespace collapsed, so a
    # hard-wrapped `:role:`...`` or ``...`` span that reflows to one line in
    # the rewrite (or vice versa) is not read as a dropped fact — see
    # _normalise_ident.
    src_ids, rw_ids = _identifiers(source), _identifiers(rewrite)
    rw_norm = {_normalise_ident(i) for i in rw_ids}
    for ident in sorted(src_ids):
        if ident in rw_ids or _normalise_ident(ident) in rw_norm:
            continue
        add("identifier", "critical", f"`{ident}` is missing from the rewrite.")

    # Negation. Losing a "not" reverses the meaning.
    s_neg, r_neg = _counts(source, NEGATION_RE), _counts(rewrite, NEGATION_RE)
    if r_neg < s_neg:
        add(
            "negation",
            "critical",
            f"the source negates {s_neg} times, the rewrite {r_neg}. "
            "A lost negation reverses the meaning.",
        )

    # Obligation weakened into suggestion.
    s_ob, r_ob = _counts(source, OBLIGATION_RE), _counts(rewrite, OBLIGATION_RE)
    s_sg, r_sg = _counts(source, SUGGESTION_RE), _counts(rewrite, SUGGESTION_RE)
    if r_ob < s_ob and r_sg > s_sg:
        add(
            "modal",
            "critical",
            f"an obligation weakened into a suggestion "
            f"(must/shall {s_ob} -> {r_ob}, should/may {s_sg} -> {r_sg}).",
        )

    # Conditions.
    s_cond, r_cond = _counts(source, CONDITION_RE), _counts(rewrite, CONDITION_RE)
    if r_cond < s_cond:
        add(
            "condition",
            "warning",
            f"the source states {s_cond} conditions, the rewrite {r_cond}. "
            "Check that no condition was dropped.",
        )

    # Scope: every -> some.
    s_all, r_all = _counts(source, UNIVERSAL_RE), _counts(rewrite, UNIVERSAL_RE)
    s_part, r_part = _counts(source, PARTIAL_RE), _counts(rewrite, PARTIAL_RE)
    if r_all < s_all and r_part > s_part:
        add(
            "scope",
            "critical",
            f"a statement about all cases became one about some cases "
            f"(every/all {s_all} -> {r_all}, some/most {s_part} -> {r_part}).",
        )

    critical = sum(1 for f in findings if f["severity"] == "critical")
    return {
        "source_words": len(re.findall(r"\w+", source)),
        "rewrite_words": len(re.findall(r"\w+", rewrite)),
        "findings": findings,
        "critical": critical,
        "warnings": len(findings) - critical,
        "faithful": critical == 0,
    }


def format_report(res, src_name, rw_name):
    lines = [
        f"{src_name} -> {rw_name}",
        f"  {res['source_words']} words -> {res['rewrite_words']} words",
    ]
    if not res["findings"]:
        lines.append("  no fact lost. The rewrite keeps every number, unit, "
                     "identifier, negation, and condition.")
        return "\n".join(lines)
    for f in res["findings"]:
        mark = "LOST" if f["severity"] == "critical" else "check"
        lines.append(f"  [{mark}] {f['kind']}: {f['message']}")
    lines.append(
        f"  {res['critical']} critical, {res['warnings']} to check. "
        "Rule PSTE-A1: accuracy defeats every other rule."
    )
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check that a rewrite keeps every fact from its source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("source", nargs="?")
    ap.add_argument("rewrite", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.source or not args.rewrite:
        ap.print_help()
        return 2

    try:
        with open(args.source, encoding="utf-8") as fh:
            source = fh.read()
        with open(args.rewrite, encoding="utf-8") as fh:
            rewrite = fh.read()
    except OSError as exc:
        print(f"cannot read: {exc}", file=sys.stderr)
        return 2

    res = compare(source, rewrite)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(format_report(res, args.source, args.rewrite))
    return 0 if res["faithful"] else 1


def self_test():
    # A faithful rewrite loses nothing.
    src = "The client retries 3 times. If the request fails, wait 30 seconds."
    good = "The client makes 3 attempts. If the request fails, the client waits 30 seconds."
    r = compare(src, good)
    assert r["faithful"], r["findings"]

    # A changed number is critical. This is the case that entailment models miss.
    bad_num = "The client retries 3 times. If the request fails, wait 300 seconds."
    r = compare(src, bad_num)
    assert not r["faithful"], r
    assert any(f["kind"] == "number" for f in r["findings"]), r["findings"]

    # A changed unit is critical.
    bad_unit = "The client retries 3 times. If the request fails, wait 30 minutes."
    r = compare(src, bad_unit)
    assert not r["faithful"], r
    assert any(f["kind"] == "unit" for f in r["findings"]), r["findings"]

    # A dropped number is critical.
    dropped = "The client retries. If the request fails, wait 30 seconds."
    r = compare(src, dropped)
    assert not r["faithful"], r

    # A dropped identifier is critical.
    s2 = "Set `--timeout` in `config.yaml` before you start."
    r = compare(s2, "Set the timeout in the configuration file before you start.")
    assert not r["faithful"], r
    assert any(f["kind"] == "identifier" for f in r["findings"]), r["findings"]

    # A lost negation reverses the meaning.
    s3 = "Do not run this on the main branch."
    r = compare(s3, "Run this on the main branch.")
    assert not r["faithful"], r
    assert any(f["kind"] == "negation" for f in r["findings"]), r["findings"]

    # An obligation must not weaken into a suggestion.
    s4 = "You must run the backup first."
    r = compare(s4, "You should run the backup first.")
    assert not r["faithful"], r
    assert any(f["kind"] == "modal" for f in r["findings"]), r["findings"]

    # A statement about all cases must not narrow to some.
    s5 = "This deletes every row in the table."
    r = compare(s5, "This deletes some rows in the table.")
    assert not r["faithful"], r
    assert any(f["kind"] == "scope" for f in r["findings"]), r["findings"]

    # A dropped condition is a warning, not a failure: a rewrite may legitimately
    # restructure one, so a human decides.
    s6 = "If the build fails, read the log. When the log is empty, run it again."
    r = compare(s6, "Read the log after a failed build.")
    assert any(f["kind"] == "condition" for f in r["findings"]), r["findings"]

    # Unit spellings fold together: 30 s equals 30 seconds.
    r = compare("Wait 30 seconds.", "Wait 30 s.")
    assert r["faithful"], r["findings"]
    r = compare("The limit is 100 requests per minute.", "The limit is 100 requests each minute.")
    assert r["faithful"], r["findings"]

    # A shorter faithful rewrite passes. Brevity is not the failure; loss is.
    r = compare(
        "It is important to note that the timeout value is set to 30 seconds.",
        "The timeout is 30 seconds.",
    )
    assert r["faithful"], r["findings"]

    # DEFECT 1: a synthetic corpus document stores its generation prompt as YAML
    # front matter in `source` (build version, date, an "isolation" note that
    # names CLAUDE.md). None of that is a fact the rewrite owes back.
    synth_source = (
        "---\n"
        "generated_by: 2.1.220 (Claude Code)\n"
        "generated_on: 2026-08-03\n"
        "isolation: |\n"
        "  No CLAUDE.md, no plugin, no hook, no memory.\n"
        "---\n"
        "The client retries 3 times.\n"
    )
    r = compare(synth_source, "The client makes 3 attempts.")
    assert r["faithful"], r["findings"]
    # A real document that legitimately opens with a markdown horizontal rule
    # (a lone leading "---" with no closing "---") must not lose content: only
    # a CLOSED front-matter block is stripped.
    hr_source = "---\n\nThe client retries 3 times.\n"
    r = compare(hr_source, "The client retries 3 times.")
    assert r["faithful"], r["findings"]
    r = compare(hr_source, "The client retries.")
    assert not r["faithful"], r["findings"]

    # DEFECT 2: an RST role reference wraps across a line break, and a second
    # role follows in the same paragraph. The prose BETWEEN the two must not
    # read as a fake identifier that can never appear in the rewrite.
    rst_source = (
        "Once you're ready, it is time to :doc:`install the new Django version\n"
        "</topics/install>`. If you are using a :mod:`virtual environment <venv>` "
        "and it is a major upgrade, set up a new environment."
    )
    rst_rewrite = (
        "Install the new Django version. If you use a virtual environment and it "
        "is a major upgrade, set up a new environment."
    )
    ids = _identifiers(rst_source)
    assert "install the new Django version\n</topics/install>" in ids, ids
    assert "virtual environment <venv>" in ids, ids
    assert not any(". If you are using a :mod:" in i for i in ids), ids
    # The rewrite drops both real identifiers, which IS a loss the check must
    # still catch — this defect is about not inventing a THIRD, fake one.
    r = compare(rst_source, rst_rewrite)
    assert not r["faithful"], r
    kinds = [f["kind"] for f in r["findings"]]
    assert kinds.count("identifier") == 2, r["findings"]
    # A double-backtick RST literal must pair correctly too, and not bleed into
    # the role reference that follows it in the same sentence.
    rst_source2 = "Use the ``-Wa`` flag or the :envvar:`PYTHONWARNINGS` variable."
    ids2 = _identifiers(rst_source2)
    assert "-Wa" in ids2, ids2
    assert "PYTHONWARNINGS" in ids2, ids2
    assert not any("flag or the" in i for i in ids2), ids2

    # BUG: IDENT_RE captures a hard-wrapped role target VERBATIM, newline
    # included, and the rewrite reflows the line. Both sides keep every word,
    # but a literal string compare of the captured spans still reported a
    # critical fact loss (a migration guide, both arms). The fix is at
    # compare time, not capture time: _identifiers keeps the raw newline (a
    # caller may want it), but compare() collapses whitespace on both sides
    # before it decides an identifier is missing.
    wrapped_source = (
        "See :doc:`guide\non the different release processes "
        "</internals/release-process>` before you install the new Django "
        "version. Then run `pytest` and check https://docs.pytest.org."
    )
    wrapped_rewrite = (
        "See the guide on the different release processes before you install "
        "the new Django version. Then run `pytest` and check "
        "https://docs.pytest.org."
    )
    # The raw capture still spans the newline (capture layer unchanged).
    ids = _identifiers(wrapped_source)
    assert any("\n" in i for i in ids), ids
    # But the rewrite dropped the role target's URL entirely (no
    # "release-process" anywhere), so this must legitimately fail...
    r = compare(wrapped_source, wrapped_rewrite)
    assert not r["faithful"], r
    # ...for the URL, and NOT for a reflow artifact: `pytest` (unwrapped in
    # both) must not itself trip a phantom finding.
    assert not any("pytest" in f["message"] and "`pytest`" in f["message"]
                   for f in r["findings"] if f["kind"] == "identifier"), r["findings"]
    # A rewrite that reflows the SAME role target onto one line, losing
    # nothing, must be faithful — this is the direct regression check.
    reflow_only_source = (
        ":doc:`guide\non the different release processes "
        "</internals/release-process>` explains this."
    )
    reflow_only_rewrite = (
        ":doc:`guide on the different release processes "
        "</internals/release-process>` explains this."
    )
    r = compare(reflow_only_source, reflow_only_rewrite)
    assert r["faithful"], r["findings"]

    # DEFECT 3: a spelled-out number equals its digit. Not a fact loss.
    r = compare("The build found 3 bugs.", "The build found three bugs.")
    assert r["faithful"], r["findings"]
    r = compare("Wait 2 minutes before you retry.", "Wait two minutes before you retry.")
    assert r["faithful"], r["findings"]
    # A spelled-out number with a changed unit is still caught.
    r = compare("Wait 2 minutes before you retry.", "Wait two hours before you retry.")
    assert not r["faithful"], r["findings"]

    # REGRESSION: a genuine fact loss must still fail after all three fixes.
    # migration-etcd-3-5 in the real corpus states "3.5" five times; a rewrite
    # that consolidates one real instance away must still be caught.
    etcd_source = (
        "This guide describes restoring an etcd 3.5 cluster. etcd 3.5 introduces "
        "a new snapshot format. Back up etcd 3.5 data before you start. Confirm "
        "the etcd 3.5 binary matches your cluster. Restart etcd 3.5 last."
    )
    etcd_rewrite = (
        "This guide describes restoring an etcd 3.5 cluster. etcd 3.5 introduces "
        "a new snapshot format. Back up etcd 3.5 data before you start. Confirm "
        "the binary matches your cluster. Restart etcd 3.5 last."
    )
    r = compare(etcd_source, etcd_rewrite)
    assert not r["faithful"], "a consolidated-away '3.5' must still fail"
    assert any(f["kind"] == "number" for f in r["findings"]), r["findings"]

    print("faithfulness self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
