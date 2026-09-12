#!/usr/bin/env python3
"""Report which rules the skill still breaks, so the next edit has a target.

    python3 evals/diagnose.py
    python3 evals/diagnose.py --arm control     # what the plain ask leaves behind
    python3 evals/diagnose.py --rule PSTE-G1    # every instance of one rule
    python3 evals/diagnose.py --level 3
    python3 evals/diagnose.py --corpus --level 3      # diagnose the CHECKER, not the skill
    python3 evals/diagnose.py --corpus --words        # which words fire the vocabulary rules

WHAT THIS IS FOR

`measure.py` answers "did the arm conform?" and the answer is usually no, because
one finding fails a document. That verdict is correct and useless for improving
anything: it cannot say WHICH rule the skill fails to teach.

This ranks the rules that survive a PSTE pass. The rule at the top of the list is
the one the skill prompt explains worst, and it is where the next edit belongs.

`--corpus` reads the committed corpus sources instead of an eval result. Use it
when the checker itself is the suspect, not the skill: a source document breaks
no rule by hand-editing, so a finding against it means pste_lint.py is wrong.

`--words` breaks PSTE-V3 and PSTE-L2 down by word instead of by rule. A single
example message cannot say whether a word is a real miss or one document's
artefact. The frequency table can.

READ IT AS A WORK LIST, NOT AS A SCORE

PSTE-1 §5.2 says a conformance result is not a measure of quality, and that holds
here too. These counts say where the skill is weak. They do not say the text is
good, or bad, or better than anything else.

A NUMBER THAT FALLS BECAUSE THE SKILL IMPROVED IS GOOD. A NUMBER THAT FALLS
BECAUSE SOMEBODY RELAXED A RULE IS A LIE. Change the skill, never the standard, in
response to what this prints.
"""

import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import corpus  # noqa: E402
import provenance  # noqa: E402
import pste_lint  # noqa: E402

DISCLAIMER = (
    "This is a work list for the skill, and not a measure of quality. A count that\n"
    "falls because the skill improved is progress. A count that falls because\n"
    "somebody relaxed a rule is not. See evals/FUTURE-WORK.md."
)


def collect(snapshot, arm, level):
    """Every finding for one arm, with the document it came from."""
    vocab = pste_lint.load_vocab()
    findings = []
    per_document = {}

    for pid, entry in snapshot["results"].items():
        if arm == "source":
            every = [entry.get("source")]
        else:
            # Use every pass when the run made more than one. A rule that breaks
            # in one pass out of three is a different problem from one that breaks
            # every time, and a single pass cannot tell them apart.
            every = (entry.get("passes") or {}).get(arm)
            if not every:
                every = [entry["outputs"].get(arm)]

        counts = []
        for index, text in enumerate(every):
            if not text:
                continue
            result = pste_lint.check_text(text, level=level, vocab=vocab)
            counts.append(len(result["findings"]))
            for finding in result["findings"]:
                findings.append({**finding, "document": pid, "pass": index + 1})

        if counts:
            per_document[pid] = {
                "findings": counts[0],
                "passes": counts,
                "words": len(every[0].split()),
                "type": entry.get("type", ""),
            }
    return findings, per_document


def collect_corpus(level, manifest=corpus.MANIFEST, directory=corpus.CORPUS_DIR):
    """Every finding against the corpus SOURCE documents, with no eval result.

    `collect` diagnoses a rewrite. This diagnoses the CHECKER: it runs
    `pste_lint.check_text` straight over the committed sources, so a parser bug or a
    vocabulary rule that never fires shows up without a skill run in the way. Same
    shape as `collect`'s return, so the rest of this tool cannot tell the two apart.
    """
    vocab = pste_lint.load_vocab()
    findings = []
    per_document = {}

    for doc in corpus.load(manifest):
        with open(corpus.path_of(doc, directory), encoding="utf-8") as fh:
            text = fh.read()
        result = pste_lint.check_text(text, level=level, vocab=vocab)
        for finding in result["findings"]:
            findings.append({**finding, "document": doc["id"], "pass": 1})
        per_document[doc["id"]] = {
            "findings": result["total"],
            "passes": [result["total"]],
            "words": result["words"],
            "type": doc.get("type", ""),
        }
    return findings, per_document


def word_table(findings):
    """How often each word fires PSTE-V3 or PSTE-L2, and across how many documents.

    One example message per rule hides the thing a spec edit needs: whether a word
    is a real cross-domain miss or one document's artefact. Document count says
    that better than the raw count does, so both are printed and the message itself
    is the only source for the word — never a hardcoded list.
    """
    WORD_RE = re.compile(r"^'([^']+)' (?:is not approved; use '([^']*)'|carries no information; delete it)")
    counts = collections.Counter()
    docs = collections.defaultdict(set)
    replacement = {}
    for f in findings:
        if f["rule"] not in ("PSTE-V3", "PSTE-L2"):
            continue
        m = WORD_RE.match(f["message"])
        if not m:
            continue
        word = m.group(1)
        counts[word] += 1
        docs[word].add(f["document"])
        replacement[word] = m.group(2) or "delete"
    rows = [
        (word, counts[word], len(docs[word]), replacement[word])
        for word in counts
    ]
    rows.sort(key=lambda r: -r[1])
    return rows


def compare(snapshot, level):
    """How each arm scored on each document, so a reader sees the movement."""
    vocab = pste_lint.load_vocab()
    rows = []
    for pid, entry in snapshot["results"].items():
        texts = {"source": entry.get("source"), **entry["outputs"]}
        row = {"document": pid}
        repeats = entry.get("passes") or {}
        for arm, text in texts.items():
            if not text:
                continue
            every = repeats.get(arm) or [text]
            counts = [
                len(pste_lint.check_text(t, level=level, vocab=vocab)["findings"])
                for t in every
                if t
            ]
            row[arm] = counts[0] if counts else 0
            if len(counts) > 1:
                row[f"{arm}_spread"] = (min(counts), max(counts))
            row[f"{arm}_words"] = len(text.split())
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="Report which rules an arm still breaks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--snapshot", default=None)
    ap.add_argument(
        "--corpus",
        action="store_true",
        help="diagnose the corpus SOURCE documents, with no eval result",
    )
    ap.add_argument(
        "--words",
        action="store_true",
        help="a frequency table for the vocabulary rules (PSTE-V3, PSTE-L2)",
    )
    ap.add_argument("--arm", default="pste")
    ap.add_argument("--level", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--rule", default=None, help="show every instance of one rule")
    ap.add_argument("--limit", type=int, default=6, help="examples per rule")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.corpus and args.snapshot:
        print("--corpus and --snapshot are mutually exclusive.", file=sys.stderr)
        return 2

    if args.corpus:
        path, snapshot = None, None
        findings, per_document = collect_corpus(args.level)
    else:
        path = provenance.resolve(args.snapshot)
        if not path or not os.path.exists(path):
            print("no result found. Run: python3 evals/run.py", file=sys.stderr)
            return 2
        with open(path, encoding="utf-8") as fh:
            snapshot = json.load(fh)
        findings, per_document = collect(snapshot, args.arm, args.level)

    by_rule = collections.Counter(f["rule"] for f in findings)
    # spec/PSTE-1.md §15: the consequence of a finding, not just its count. A
    # weight is already on every finding pste_lint.check_text returns (see
    # pste_lint.load_weights), so this sums what is already there rather than
    # looking anything up again.
    weighted_total = sum(f["weight"] for f in findings)
    weighted_by_rule = collections.Counter()
    for f in findings:
        weighted_by_rule[f["rule"]] += f["weight"]

    if args.json:
        print(
            json.dumps(
                {
                    "result": "corpus" if args.corpus else os.path.basename(path),
                    "arm": "corpus" if args.corpus else args.arm,
                    "level": args.level,
                    "by_rule": dict(by_rule),
                    "weighted_total": round(weighted_total, 2),
                    "weighted_by_rule": {
                        r: round(w, 2) for r, w in weighted_by_rule.items()
                    },
                    "per_document": per_document,
                    "words": word_table(findings) if args.words else None,
                    "disclaimer": DISCLAIMER.replace("\n", " "),
                },
                indent=2,
            )
        )
        return 0

    # One rule in detail: every instance, with the text that broke it.
    if args.rule:
        hits = [f for f in findings if f["rule"].upper() == args.rule.upper()]
        arm_label = "corpus" if args.corpus else args.arm
        print(f"{args.rule.upper()} in arm '{arm_label}': {len(hits)} findings\n")
        for hit in hits:
            print(f"  {hit['document']}:{hit['line']}:{hit['column']}")
            print(f"    {hit['message']}")
            excerpt = (hit.get("excerpt") or "").strip()
            if excerpt:
                print(f"    | {excerpt[:100]}")
        print(f"\n{DISCLAIMER}")
        return 0

    if args.corpus:
        print(f"PSTE diagnosis, corpus source documents, level {args.level}\n")
        header = f"{'document':<36}{'findings':>9}{'words':>9}"
        print(header)
        print("-" * len(header))
        total = 0
        for pid, entry in sorted(per_document.items(), key=lambda kv: -kv[1]["findings"]):
            print(f"{pid:<36}{entry['findings']:>9}{entry['words']:>9}")
            total += entry["findings"]
        print("-" * len(header))
        print(f"{'TOTAL':<36}{total:>9}")
        print(f"\nWeighted total (spec/PSTE-1.md §15): {weighted_total:.1f} "
              f"of {total} findings counted at full weight.")

        conforming = sum(1 for e in per_document.values() if e["findings"] == 0)
        print(f"\n{conforming}/{len(per_document)} documents conform.")
        if conforming < len(per_document):
            print("A document fails on one finding, so read the work list, not the count.")
    else:
        print(f"PSTE diagnosis, arm '{args.arm}', level {args.level}")
        print(f"{provenance.describe_result(snapshot, path)}\n")

        # The movement between arms. This is what says whether the skill did
        # anything, and a verdict alone cannot show it.
        rows = compare(snapshot, args.level)
        arms = [a for a in ("source", "control", "pste", "pste_fixed") if a in rows[0]]
        header = f"{'document':<36}" + "".join(f"{a:>9}" for a in arms)
        print(header)
        print("-" * len(header))
        totals = collections.Counter()
        for row in sorted(rows, key=lambda r: -r.get("source", 0)):
            line = f"{row['document']:<36}"
            for arm in arms:
                line += f"{row.get(arm, '-'):>9}"
                totals[arm] += row.get(arm, 0)
            print(line)
        print("-" * len(header))
        print(f"{'TOTAL':<36}" + "".join(f"{totals[a]:>9}" for a in arms))
        print(f"\nWeighted total for arm '{args.arm}' (spec/PSTE-1.md §15): "
              f"{weighted_total:.1f} of {totals.get(args.arm, 0)} findings "
              f"counted at full weight.")

        conforming = sum(1 for r in rows if r.get(args.arm) == 0)
        print(f"\n{conforming}/{len(rows)} documents conform in arm '{args.arm}'.")
        if conforming < len(rows):
            print("A document fails on one finding, so read the work list, not the count.")

    arm_label = "corpus" if args.corpus else args.arm
    print(f"\nWhat the '{arm_label}' arm still breaks, worst first by raw count:\n")
    print(f"  {'rule':<10} {'count':>5} {'weighted':>8}  {'documents':>9}   message")
    for rule, count in by_rule.most_common():
        hits = [f for f in findings if f["rule"] == rule]
        documents = len({h["document"] for h in hits})
        print(f"  {rule:<10} {count:>5} {weighted_by_rule[rule]:>8.1f}  "
              f"{documents:>9}   {hits[0]['message'][:58]}")
    print(
        "\n  Raw count and weighted count rank rules differently on purpose.\n"
        "  Many trivial findings and few serious ones are different situations,\n"
        "  and the raw count alone cannot say which one a rule is in."
    )

    if args.words:
        # PSTE-V3 and PSTE-L2 share one shape: "word is not approved" or "word
        # carries no information". One example message hides which words drive the
        # count, and that is the thing a spec edit needs.
        words = word_table(findings)
        if words:
            print("\nVocabulary findings by word, worst first:\n")
            print(f"  {'word':<20} {'count':>6} {'documents':>10}   replace with")
            for word, count, docs, repl in words:
                print(f"  {word:<20} {count:>6} {docs:>10}   {repl}")
            print(
                "\n  Document spread matters more than the count. A word in many\n"
                "  documents is a real cross-domain term; a word in one is more\n"
                "  likely an artefact of that document's subject.\n"
                "  Remove a word from a collapse because the collapse is WRONG for\n"
                "  the sense software uses. Never remove it because it is frequent."
            )

    # THE SEMANTIC FINDINGS, WHEN THE RUN RECORDED THEM. Corpus source documents
    # carry no eval result, so there is nothing here to read.
    #
    # These come from a model, so they carry an agreement rate rather than a
    # count. A rule that every pass reported is worth acting on. A rule that one
    # pass reported is a candidate that a person confirms.
    semantic = collections.Counter()
    stable = collections.Counter()
    examples = {}
    if not args.corpus:
        for entry in snapshot["results"].values():
            block = (entry.get("semantic") or {}).get(args.arm)
            if not block:
                continue
            for item in block.get("summary", []):
                semantic[item["rule"]] += 1
                if item["seen_in"] == item["of"]:
                    stable[item["rule"]] += 1
                examples.setdefault(item["rule"], item)

    if semantic:
        print(
            f"\nWhat a judge found that no regular expression can, arm "
            f"'{args.arm}':\n"
        )
        print(f"  {'rule':<10} {'documents':>9} {'every pass':>11}   problem")
        for rule, count in semantic.most_common():
            item = examples[rule]
            print(
                f"  {rule:<10} {count:>9} {stable[rule]:>11}   "
                f"{item['problem'][:52]}"
            )
        print(
            "\n  A judge disagrees with itself. Read the 'every pass' column: a rule\n"
            "  that every pass reported is worth acting on, and a rule that one pass\n"
            "  reported is a candidate that a person confirms."
        )

    if by_rule:
        top = by_rule.most_common(1)[0][0]
        print(
            f"\nStart with {top}. Read every instance:\n"
            f"    python3 evals/diagnose.py --rule {top}"
        )

    print(f"\n{DISCLAIMER}")
    return 0


def self_test():
    snapshot = {
        "arms": ["control", "pste"],
        "results": {
            "d1": {
                "type": "runbook",
                "source": "The parser is robust. The file was read by the tool.",
                "outputs": {
                    "control": "The parser is robust.",
                    "pste": "The tool reads the file.",
                },
            }
        },
    }

    findings, per_document = collect(snapshot, "pste", 2)
    assert "d1" in per_document, per_document
    assert per_document["d1"]["words"] > 0

    # Every finding must name the document it came from, or the work list cannot
    # be followed back to a text.
    for finding in findings:
        assert finding["document"] == "d1", finding

    # The source must be scored too. A rewrite means nothing without the before.
    source_findings, _ = collect(snapshot, "source", 2)
    assert len(source_findings) > len(findings), (
        "the source should break more rules than the rewrite in this fixture"
    )

    # spec/PSTE-1.md §15: every finding pste_lint.check_text returns already
    # carries a weight, so the weighted total is a straight sum and never looks
    # a rule up twice.
    for finding in source_findings:
        assert isinstance(finding["weight"], float), finding
    weighted_total = sum(f["weight"] for f in source_findings)
    assert weighted_total > 0
    # A raw count of 1 per finding must never equal the weighted sum here: the
    # fixture's findings are not all weight 1.0, so the two numbers diverge.
    assert weighted_total != len(source_findings), (
        weighted_total, len(source_findings)
    )

    rows = compare(snapshot, 2)
    assert rows[0]["document"] == "d1", rows
    for arm in ("source", "control", "pste"):
        assert arm in rows[0], (arm, rows[0])
        assert f"{arm}_words" in rows[0], rows[0]

    # An arm that is absent must not raise.
    empty = {"results": {"d": {"source": "Set the flag.", "outputs": {}}}}
    got, _ = collect(empty, "pste", 2)
    assert got == [], got

    # --corpus: same finding and per_document shape as --snapshot, built from
    # files on disk rather than a result. Use a throwaway manifest so this never
    # depends on what the committed corpus happens to hold.
    import tempfile

    manifest = """
documents:
  - id: fixture-doc
    type: runbook
    title: "Fixture"
    url: https://example.org/f.md
    author: "Fixture author"
    licence: MIT
    retrieved: 2026-08-03
    sha256: PLACEHOLDER
    words: 12
"""
    with tempfile.TemporaryDirectory() as tmp:
        body = "# Fixture\n\nThe file was read by the tool. The setup is seamless.\n"
        doc_path = os.path.join(tmp, "fixture-doc.md")
        with open(doc_path, "w", encoding="utf-8") as fh:
            fh.write(body)
        man_path = os.path.join(tmp, "MANIFEST.yaml")
        with open(man_path, "w", encoding="utf-8") as fh:
            fh.write(manifest.replace("PLACEHOLDER", corpus.sha256_of(doc_path)))

        corpus_findings, corpus_per_document = collect_corpus(2, man_path, tmp)

        assert "fixture-doc" in corpus_per_document, corpus_per_document
        assert corpus_per_document["fixture-doc"]["words"] > 0
        for finding in corpus_findings:
            assert finding["document"] == "fixture-doc", finding

    # --words: extracts the word from the message, never from a hardcoded list,
    # and counts documents separately from raw count.
    fixture_findings = [
        {"rule": "PSTE-V3", "message": "'utilize' is not approved; use 'use'",
         "document": "d1"},
        {"rule": "PSTE-V3", "message": "'utilize' is not approved; use 'use'",
         "document": "d2"},
        {"rule": "PSTE-L2", "message": "'basically' carries no information; delete it",
         "document": "d1"},
        {"rule": "PSTE-G1", "message": "passive voice 'was read'; name the actor",
         "document": "d1"},
    ]
    words = word_table(fixture_findings)
    by_word = {w: (count, docs, repl) for w, count, docs, repl in words}
    assert by_word["utilize"] == (2, 2, "use"), by_word
    assert by_word["basically"] == (1, 1, "delete"), by_word
    assert "passive" not in by_word and len(by_word) == 2, by_word
    # Ranked by count, worst first.
    assert words[0][0] == "utilize", words

    print("diagnose self-test: all checks passed")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main())
