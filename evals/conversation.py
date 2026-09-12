#!/usr/bin/env python3
"""Does the register hold across a long conversation, or decay turn by turn?

THE QUESTION THIS ANSWERS

A skill delivers its rules once, at the start of a session. The rules then compete
with everything that follows: the user's own register, the model's defaults, and a
context window that grows until something is dropped. An eight-turn sample showed
the finding rate rising from 1.04 in turns 1-3 to 2.64 in turns 4-8. Eight points
cannot separate a trend from noise, so this measures a longer session and reports a
slope with its own error.

WHY A PINNED QUESTION SET

`evals/conversations/*.json` holds the questions, committed. Two runs a month apart
answer the SAME questions, so only the prose differs. This mirrors the rule the
corpus manifest states for documents: hold the content still, and form is the only
thing left to measure.

WHY TWO ARMS

One arm reads the standard. The other never sees it. Without the second arm a rising
finding rate says nothing, because a later question may simply be harder to answer
cleanly than an early one. The control absorbs that: if both arms rise together, the
questions got harder. If only the first arm rises, the register decayed.

WHAT THIS DOES NOT MEASURE

Whether a reader understands the text better. Nothing here involves a reader. See
evals/FUTURE-WORK.md for the trial that would answer it.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LINT = os.path.join(HERE, "pste_lint.py")
CONVERSATIONS = os.path.join(HERE, "conversations")
RESULTS = os.path.join(HERE, "sessions")


def load_conversation(name):
    path = name if os.path.sep in name else os.path.join(CONVERSATIONS, f"{name}.json")
    with open(path) as fh:
        return json.load(fh)


def measure(text, workdir, tag):
    """Findings for one answer, from pste_lint.py itself.

    The checker is the single source of a count. A second implementation here would
    drift from it, and then a number on a page would not match the tool that
    produced it.
    """
    path = os.path.join(workdir, f"{tag}.md")
    with open(path, "w") as fh:
        fh.write(text)
    out = subprocess.run(
        [sys.executable, LINT, "--no-disclaimer", "--json", path],
        capture_output=True, text=True, cwd=REPO)
    if out.returncode not in (0, 1):
        raise RuntimeError(f"{tag}: the checker failed: {out.stderr[:200]}")
    res = json.loads(out.stdout)["files"][path]
    return {"words": res["words"], "sentences": res["sentences"],
            "findings": len(res["findings"]), "per_100w": res["per_100w"],
            "by_rule": res["by_rule"]}


def slope(xs, ys):
    """Least squares slope of ys against xs, in findings per 100 words per turn.

    Returned with the residual standard deviation, because a slope without a spread
    invites a reader to treat noise as a trend. That is the error this whole module
    exists to avoid.
    """
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    return {"per_turn": round(b, 4), "intercept": round(a, 3),
            "residual_sd": round(statistics.pstdev(resid), 3) if n > 2 else None}


def analyse(turns, arm):
    rows = [t["measured"][arm] for t in turns]
    xs = list(range(1, len(rows) + 1))
    ys = [r["per_100w"] for r in rows]
    words = sum(r["words"] for r in rows)
    finds = sum(r["findings"] for r in rows)
    # Thirds, not halves: a decay that flattens shows as a big first step and a
    # small second one, and halves hide that shape entirely.
    third = max(1, len(rows) // 3)

    def band(lo, hi):
        # A short run has fewer turns than bands. An empty slice would raise, so
        # fall back to the whole run rather than crash on a two-turn smoke test.
        chunk = ys[lo:hi] or ys
        return round(statistics.fmean(chunk), 2)
    return {
        "words": words, "findings": finds,
        "per_100w": round(100.0 * finds / words, 2) if words else 0.0,
        "first_third": band(0, third),
        "middle_third": band(third, 2 * third),
        "last_third": band(2 * third, len(rows)),
        "best_turn": min(ys), "worst_turn": max(ys),
        "slope": slope(xs, ys),
    }


def verdict(pste, control):
    """Did the register decay, or did the questions simply get harder?

    The control arm is the reference. A rise in both arms is a property of the
    questions. A rise in the PSTE arm alone is decay.
    """
    ps, cs = pste["slope"], control["slope"]
    if not ps or not cs:
        return "too few turns to fit a slope"
    # A slope is only meaningful against its own scatter. Below that, it is noise.
    threshold = (ps["residual_sd"] or 0) / max(1, len(str(ps)))
    rel = ps["per_turn"] - cs["per_turn"]
    if ps["per_turn"] <= 0:
        return "HELD: the rate did not rise"
    if abs(rel) < 0.01:
        return "HELD: both arms rose together, so the questions got harder"
    if rel > 0 and ps["per_turn"] > threshold:
        return (f"DRIFTED: the PSTE arm rose {rel:+.3f} per turn faster than "
                f"the control")
    return "HELD: the rise is within the scatter of the fit"


def main():
    ap = argparse.ArgumentParser(
        description="Measure whether the register holds across a long conversation.")
    ap.add_argument("--conversation", default="http-stack",
                    help="a name in evals/conversations, or a path to a json file")
    ap.add_argument("--answers",
                    help="json array of {question, answer, control}, in turn order")
    ap.add_argument("--out", help="where to write the result (default: evals/sessions)")
    ap.add_argument("--self-test", action="store_true")
    args, _ = ap.parse_known_args()

    if args.self_test:
        return self_test()

    if not args.answers:
        ap.error("--answers is required")

    conv = load_conversation(args.conversation)
    with open(args.answers) as fh:
        answers = json.load(fh)

    if len(answers) != len(conv["questions"]):
        sys.exit(f"the answer file has {len(answers)} turns and the conversation "
                 f"has {len(conv['questions'])}")

    # Pair by question text, never by position. A reordered answer file would
    # otherwise compare one arm's answer against another arm's question and report
    # a clean number for nonsense.
    for i, (q, a) in enumerate(zip(conv["questions"], answers), 1):
        if q.strip() != a["question"].strip():
            sys.exit(f"turn {i}: the answer does not match the pinned question")

    turns = []
    with tempfile.TemporaryDirectory() as work:
        for i, a in enumerate(answers, 1):
            turns.append({
                "turn": i, "question": a["question"],
                "answer": a["answer"], "control": a["control"],
                "measured": {
                    "pste": measure(a["answer"], work, f"p{i:03d}"),
                    "control": measure(a["control"], work, f"c{i:03d}"),
                },
            })

    pste, control = analyse(turns, "pste"), analyse(turns, "control")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, cwd=REPO).stdout.strip()
    result = {
        "conversation": conv["id"], "turns_count": len(turns), "commit": commit,
        "summary": {"pste": pste, "control": control},
        "verdict": verdict(pste, control),
        "turns": turns,
    }

    out = args.out or os.path.join(RESULTS, f"conversation-{conv['id']}-{commit}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    report(result)
    print(f"\nwrote {out}")


def report(r):
    p, c = r["summary"]["pste"], r["summary"]["control"]
    print(f"\n{r['conversation']}: {r['turns_count']} turns, commit {r['commit']}\n")
    print(f"{'':<16}{'with PSTE':>12}{'without':>12}")
    for label, key in (("words", "words"), ("findings", "findings"),
                       ("per 100 words", "per_100w"),
                       ("first third", "first_third"),
                       ("middle third", "middle_third"),
                       ("last third", "last_third")):
        print(f"{label:<16}{p[key]:>12}{c[key]:>12}")
    for arm, d in (("with PSTE", p), ("without", c)):
        s = d["slope"]
        if s:
            print(f"\n{arm}: {s['per_turn']:+.4f} findings per 100 words per turn "
                  f"(scatter {s['residual_sd']})")
    print(f"\n{r['verdict']}")


def self_test():
    # A flat arm must not read as drift, and a rising arm must.
    flat = [{"measured": {"pste": {"words": 100, "sentences": 8, "findings": 2,
                                   "per_100w": 2.0, "by_rule": {}}}}
            for _ in range(9)]
    a = analyse(flat, "pste")
    assert a["slope"]["per_turn"] == 0, a["slope"]
    assert a["first_third"] == a["last_third"] == 2.0

    rising = [{"measured": {"pste": {"words": 100, "sentences": 8, "findings": i,
                                     "per_100w": float(i), "by_rule": {}}}}
              for i in range(1, 10)]
    b = analyse(rising, "pste")
    assert b["slope"]["per_turn"] > 0.9, b["slope"]
    assert b["last_third"] > b["first_third"]

    # Both arms rising together is a property of the questions, not decay.
    assert "questions got harder" in verdict(b, b), verdict(b, b)
    # A rising PSTE arm against a flat control is decay.
    assert verdict(b, a).startswith("DRIFTED"), verdict(b, a)
    # A flat PSTE arm never reads as drift, whatever the control does.
    assert verdict(a, b).startswith("HELD"), verdict(a, b)

    # Fewer than three turns cannot support a slope.
    assert analyse(flat[:2], "pste")["slope"] is None

    print("conversation self-test: all checks passed")


if __name__ == "__main__":
    main()
