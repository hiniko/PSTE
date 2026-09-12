#!/usr/bin/env python3
"""Score the eval snapshot with the PSTE checker. Reads offline, calls no API.

    python3 evals/measure.py
    python3 evals/measure.py --level 3
    python3 evals/measure.py --json
    python3 evals/measure.py --counts     # finer detail, for finding a regression

Reports the share of outputs in each arm that conform at a given level.

WHY A SHARE AND NOT A SCORE

§5.2 of the spec says a conformance result is not a measure of quality, even here
where the harness is allowed to report one. A number invites a reader to treat it
as a grade, to compare one document with another, and to quote it as proof that
the text is good. A conformance count supports none of that.

What this answers: did the arm produce text that follows the rules?
What this cannot answer: is that text easier to read?

The second question needs readers. `--counts` keeps the finer numbers for a
developer who watches for a regression between runs. Those numbers stay inside this
directory. See FUTURE-WORK.md.

WHAT THIS DOES NOT MEASURE

The checker counts the things the rules forbid, and the skill prompt tells the model
to avoid those same things. A high pass rate shows that the model followed the
instruction. It does not show that a reader understands more.

An arm that replied with one word to every prompt would pass every check. Read the
outputs, not only the table.
"""

import argparse
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import provenance  # noqa: E402
import pste_lint  # noqa: E402

# `source` first: it is the committed document, and the figure each rewrite
# has to be read against. It is not an arm, and nothing generates it.
ARM_ORDER = ("source", "baseline", "control", "pste", "pste_fixed")

DISCLAIMER = (
    "PSTE-1 §5.2: a conformance result is not a measure of quality.\n"
    "This table shows whether each arm followed the rules. Nobody has yet tested\n"
    "whether the result helps a reader. See evals/FUTURE-WORK.md."
)


def score(snapshot, level):
    """Check every output. Returns the pass counts, and the raw detail."""
    vocab = pste_lint.load_vocab()
    passes, findings, words = {}, {}, {}

    for _pid, entry in snapshot["results"].items():
        # A run with several passes holds every one. Score them all, so the share
        # reflects the spread and not one lucky or unlucky draw.
        repeats = entry.get("passes") or {}
        texts = {arm: [t] for arm, t in entry["outputs"].items()}
        for arm, every in repeats.items():
            if every:
                texts[arm] = every
        # Score the committed document too. It is what each rewrite started from,
        # so it is the only honest "before" figure on the table.
        if entry.get("source"):
            texts["source"] = [entry["source"]]

        for arm, every in texts.items():
            for text in every:
                if not text:
                    continue
                res = pste_lint.check_text(text, level=level, vocab=vocab)
                passes.setdefault(arm, {"passed": 0, "total": 0})
                passes[arm]["total"] += 1
                if not res["findings"]:
                    passes[arm]["passed"] += 1
                findings.setdefault(arm, []).append(res["per_100w"])
                words.setdefault(arm, []).append(res["words"])
    return passes, findings, words


def summarize(values):
    if not values:
        return None
    return {
        "n": len(values),
        "median": round(statistics.median(values), 2),
        "mean": round(statistics.fmean(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def main():
    ap = argparse.ArgumentParser(
        description="Report the share of outputs that conform, per arm.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--snapshot", default=None, help="a result file. Defaults to the newest."
    )
    ap.add_argument("--level", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--counts",
        action="store_true",
        help="also print findings per 100 words, to find a regression between runs. "
        "Never publish these numbers, and never compare them with another project.",
    )
    args = ap.parse_args()

    path = provenance.resolve(args.snapshot)
    if not path or not os.path.exists(path):
        print("no result found. Run: python3 evals/run.py", file=sys.stderr)
        return 2

    with open(path, encoding="utf-8") as fh:
        snapshot = json.load(fh)

    passes, findings, words = score(snapshot, args.level)
    word_stats = {arm: summarize(v) for arm, v in words.items() if v}

    report = {
        "level": args.level,
        "result": os.path.basename(path),
        "git": snapshot.get("git"),
        "disclaimer": DISCLAIMER.replace("\n", " "),
        "conforming": passes,
        "median_words": {a: s["median"] for a, s in word_stats.items()},
    }
    if args.counts:
        report["findings_per_100w"] = {
            arm: summarize(v) for arm, v in findings.items() if v
        }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    count = snapshot.get("document_count") or snapshot.get("prompt_count", 0)
    unit = "documents" if snapshot.get("document_count") else "prompts"
    print(f"PSTE eval, level {args.level}, {count} {unit}")
    print(f"{provenance.describe_result(snapshot, path)}\n")
    print(f"{'arm':<10} {'conforming':>12} {'median words':>14}")
    for arm in ARM_ORDER:
        p = passes.get(arm)
        if not p:
            continue
        share = f"{p['passed']}/{p['total']}"
        w = word_stats.get(arm, {}).get("median", 0)
        print(f"{arm:<10} {share:>12} {w:>14}")

    print("\nShare of outputs in each arm that follow the rules at this level.")

    # The word column is the guard against a false win. PSTE-A1 forbids dropping a
    # fact to satisfy a rule, and an arm that conforms by saying less has broken
    # that rule while looking better here.
    print(
        "\nRead the word column beside the share. An arm that conforms by saying\n"
        "less has not written better prose. Check it with evals/faithfulness.py."
    )

    if args.counts:
        print("\n  [development detail, not for publication]")
        for arm in ARM_ORDER:
            s = report["findings_per_100w"].get(arm)
            if s:
                print(
                    f"  {arm:<10} findings/100w median {s['median']:>6} "
                    f"min {s['min']:>6} max {s['max']:>6}"
                )

    print(f"\n{DISCLAIMER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
