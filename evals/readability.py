#!/usr/bin/env python3
"""Measure two properties of prose that the rule checker cannot measure.

    python3 evals/readability.py FILE...
    python3 evals/readability.py --json FILE...
    python3 evals/readability.py --self-test

WHY THIS EXISTS, AND WHY IT IS NOT THE RULE CHECKER

`evals/pste_lint.py` counts the things that PSTE-1 forbids. The skill prompt tells a
model to avoid those same things, so a good score there shows that the model followed
the instruction. It cannot show that the result is easier to read.

This script measures two properties that no PSTE rule states, so a writer cannot
satisfy them by obeying the standard alone.

    1. VOCABULARY COVERAGE (the main measure)

       The share of content words that fall inside a core word list. Nation (2006)
       and Laufer and Ravenhorst-Kalovski (2010) measured this against real
       comprehension scores, not against another metric, and found two thresholds
       for readers whose first language is not English:

           95 percent  reading with support
           98 percent  independent reading

       This is the strongest evidence in the field, and it points at the readers
       that this project most wants to help.

    2. REPEATED TERMS

       Whether the text names one thing one way. This tests the effect of rule
       PSTE-V3 from the outside: it counts how often the text uses two words where
       one would do, measured by clusters that the standard's own word list defines.

WHAT THIS DOES NOT DO

It does not measure comprehension. Comprehension needs a reader who answers
questions about the text, and this script has no reader in it. See
`evals/FUTURE-WORK.md` for what a real test needs.

MEASURES THIS SCRIPT DELIBERATELY OMITS

Flesch-Kincaid, Gunning Fog, SMOG, Coleman-Liau, ARI, LIX, RIX, and Linsear Write
are all functions of word length and sentence length. PSTE-1 sets limits on word
length and sentence length. Reporting them here would restate the rule checker in
another form and would look like independent support when it is not.

Tanprasert and Kauchak (2021) showed that a writer raises the Flesch-Kincaid score
by cutting sentences mechanically, with no gain for a reader. `--include-circular`
prints them for comparison with other work, under a label that says what they are.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import pste_lint  # noqa: E402

CORE_LIST = os.path.join(ROOT, "evals", "core-vocabulary.txt")

# Nation (2006); Laufer and Ravenhorst-Kalovski (2010).
THRESHOLD_SUPPORTED = 95.0
THRESHOLD_INDEPENDENT = 98.0

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def load_core(path=CORE_LIST):
    """Read the core word list. Lines starting with # are comments."""
    words = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip().lower()
                if line:
                    words.add(line)
    except OSError:
        return set()
    return words


def _known(word, core, approved, terms):
    """A word counts as covered when a reader can be expected to know it.

    Three sources count: the core list, the words that PSTE-1 approves, and the
    term categories that PSTE-1 defines. The last two matter because a technical
    reader knows `commit` and `container`, and a general frequency list does not
    record that.
    """
    w = word.lower().strip("'-")
    if not w:
        return True
    if w in core or w in approved or w in terms:
        return True
    # Regular inflections of a known word.
    for suffix, base in (
        ("s", ""), ("es", ""), ("ed", ""), ("d", ""), ("ing", ""),
        ("ies", "y"), ("ied", "y"), ("er", ""), ("est", ""), ("ly", ""),
    ):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            stem = w[: -len(suffix)] + base
            if stem in core or stem in approved or stem in terms:
                return True
            if suffix in ("ing", "ed") and stem + "e" in (core | approved | terms):
                return True
            # running -> run, stopped -> stop
            if len(stem) > 2 and stem[-1] == stem[-2] and stem[:-1] in (
                core | approved | terms
            ):
                return True
    return False


def coverage(text, core=None, vocab=None):
    """Share of words that a reader can be expected to know.

    Code, identifiers, and quoted text are removed first: PSTE-1 section 4 puts
    them outside the rules, and a reader reads them as symbols, not as prose.
    """
    core = core if core is not None else load_core()
    vocab = vocab if vocab is not None else pste_lint.load_vocab()

    prose = pste_lint.strip_non_prose(text)
    prose = re.sub(r"\bCODE\b|\bURL\b|\bEXAMPLE\b", " ", prose)

    approved = {w.lower() for w in vocab["approved"]}
    terms = {t.lower() for t in vocab["term_verbs"]}
    terms |= _term_nouns()

    words = WORD_RE.findall(prose)
    if not words:
        return {"words": 0, "covered": 0, "coverage": 100.0, "unknown": []}

    unknown = []
    covered = 0
    for w in words:
        if _known(w, core, approved, terms):
            covered += 1
        else:
            unknown.append(w.lower())

    pct = round(covered * 100 / len(words), 2)
    counts = {}
    for u in unknown:
        counts[u] = counts.get(u, 0) + 1
    return {
        "words": len(words),
        "covered": covered,
        "coverage": pct,
        "meets_supported": pct >= THRESHOLD_SUPPORTED,
        "meets_independent": pct >= THRESHOLD_INDEPENDENT,
        "unknown": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
    }


_TERM_NOUN_CACHE = None


def _term_nouns():
    """The common domain nouns from terms.yaml.

    A flat list now, and not fifteen categories with example words. The categories
    read as though membership were a lookup, and PSTE-V1 leaves that judgement to
    the writer, because no list reaches the tail of a domain. This list holds only
    the vocabulary every programmer shares, so a tool does not report `cache` or
    `latency` as unusual.
    """
    global _TERM_NOUN_CACHE
    if _TERM_NOUN_CACHE is not None:
        return _TERM_NOUN_CACHE
    out = set()
    path = os.path.join(ROOT, "spec", "terms.yaml")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        _TERM_NOUN_CACHE = out
        return out
    section = None
    for line in raw.splitlines():
        stripped = pste_lint._strip_comment(line).strip()
        if not stripped:
            continue
        if not line.startswith((" ", "\t")) and stripped.endswith(":"):
            section = stripped[:-1]
            continue
        if section == "common_nouns" and stripped.startswith("- "):
            for part in WORD_RE.findall(stripped[2:]):
                out.add(part.lower())
    # The verbs still live in a flow list under `term_verbs`.
    for m in re.finditer(r"verbs:\s*(\[[^\]]*\])", raw, re.DOTALL):
        for w in pste_lint._flow_list(" ".join(m.group(1).split())):
            for part in WORD_RE.findall(w):
                out.add(part.lower())
    _TERM_NOUN_CACHE = out
    return out


def term_consistency(text, vocab=None):
    """Count places where the text names one action with two words.

    For every cluster in the standard's word list, count how many distinct members
    of that cluster the text uses. A cluster with more than one member in use is a
    place where a reader must decide whether the second word means something new.
    """
    vocab = vocab if vocab is not None else pste_lint.load_vocab()
    prose = pste_lint.strip_non_prose(text).lower()
    words = set(WORD_RE.findall(prose))

    clusters = {}
    for bad, good in vocab["instead_of"].items():
        if good and " " not in bad:
            clusters.setdefault(good, set()).add(bad)

    split = []
    for head, members in clusters.items():
        used = {w for w in members | {head} if w in words}
        if len(used) > 1:
            split.append({"cluster": head, "used": sorted(used)})

    return {
        "clusters_in_use": sum(
            1 for h, m in clusters.items() if (m | {h}) & words
        ),
        "split_clusters": len(split),
        "detail": sorted(split, key=lambda d: d["cluster"])[:10],
    }


# ---------------------------------------------------------------------------
# The circular measures, printed only when asked, and labeled.
# ---------------------------------------------------------------------------

def _syllables(word):
    w = word.lower().strip("'-")
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ee", "ye")):
        n -= 1
    return max(1, n)


def circular_scores(text):
    """Flesch-Kincaid and friends. Reported only for comparison with other work.

    These are functions of word length and sentence length, which PSTE-1 already
    constrains. A better score here does not show that a reader understands more.
    """
    prose = pste_lint.strip_non_prose(text)
    sentences = pste_lint.split_sentences(prose)
    words = WORD_RE.findall(prose)
    if not sentences or not words:
        return None
    syl = sum(_syllables(w) for w in words)
    wps = len(words) / len(sentences)
    spw = syl / len(words)
    return {
        "flesch_kincaid_grade": round(0.39 * wps + 11.8 * spw - 15.59, 2),
        "flesch_reading_ease": round(206.835 - 1.015 * wps - 84.6 * spw, 2),
        "words_per_sentence": round(wps, 2),
        "syllables_per_word": round(spw, 2),
        "WARNING": (
            "These restate the length rules that PSTE-1 already sets. They are not "
            "independent evidence of readability."
        ),
    }


def analyze(text, include_circular=False):
    core, vocab = load_core(), pste_lint.load_vocab()
    out = {
        "vocabulary_coverage": coverage(text, core, vocab),
        "term_consistency": term_consistency(text, vocab),
    }
    if include_circular:
        out["circular_do_not_cite"] = circular_scores(text)
    return out


def format_report(path, res):
    cov = res["vocabulary_coverage"]
    tc = res["term_consistency"]
    lines = [f"{path}"]

    mark = "independent" if cov.get("meets_independent") else (
        "supported" if cov.get("meets_supported") else "below both thresholds"
    )
    lines.append(
        f"  vocabulary coverage : {cov['coverage']}%  "
        f"({cov['covered']}/{cov['words']} words) -> {mark}"
    )
    lines.append(
        f"                        95% = reading with support, "
        f"98% = independent reading"
    )
    if cov["unknown"]:
        top = ", ".join(f"{w} x{n}" if n > 1 else w for w, n in cov["unknown"][:8])
        lines.append(f"  outside the core list: {top}")

    lines.append(
        f"  split clusters      : {tc['split_clusters']} of "
        f"{tc['clusters_in_use']} in use"
    )
    for d in tc["detail"][:4]:
        lines.append(f"      {d['cluster']}: uses {', '.join(d['used'])}")

    if res.get("circular_do_not_cite"):
        c = res["circular_do_not_cite"]
        lines.append(
            f"  [circular, do not cite] FK grade {c['flesch_kincaid_grade']}, "
            f"reading ease {c['flesch_reading_ease']}"
        )
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Measure vocabulary coverage and term consistency.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("files", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--include-circular",
        action="store_true",
        help="also print Flesch-Kincaid, labeled as not independent",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.files:
        ap.print_help()
        return 2

    results = {}
    for path in args.files:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"{path}: cannot read: {exc}", file=sys.stderr)
            continue
        res = analyze(text, args.include_circular)
        results[path] = res
        if not args.json:
            print(format_report(path, res))
    if args.json:
        print(json.dumps(results, indent=2))
    return 0


def self_test():
    core = load_core()
    assert len(core) > 800, f"core list looks too small: {len(core)}"
    vocab = pste_lint.load_vocab()

    # Plain prose made of common words scores high.
    plain = "The service reads the file and writes the result to the log."
    c = coverage(plain, core, vocab)
    assert c["coverage"] == 100.0, c

    # Rare Latinate vocabulary scores lower, even in short sentences. This is the
    # property that separates this measure from the rule checker: the sentence is
    # short and would pass every length rule.
    rare = "The apparatus facilitates the requisite juxtaposition of heterogeneous constituents."
    c2 = coverage(rare, core, vocab)
    assert c2["coverage"] < 70, c2
    assert not c2["meets_supported"], c2

    # Technical terms that PSTE-1 defines do not count against coverage.
    tech = "The container starts and the deployment writes a log."
    c3 = coverage(tech, core, vocab)
    assert c3["coverage"] == 100.0, c3

    # Code and identifiers are outside the rules, so they are outside this measure.
    coded = "Run `kubectl apply -f zzz_unknown_thing.yaml` and read the log."
    c4 = coverage(coded, core, vocab)
    assert c4["coverage"] == 100.0, c4

    # Term consistency notices a text that uses two words for one action.
    split = "Check the file. Then verify the header and validate the schema."
    t = term_consistency(split, vocab)
    assert t["split_clusters"] >= 1, t
    consistent = "Check the file. Then check the header and check the schema."
    t2 = term_consistency(consistent, vocab)
    assert t2["split_clusters"] == 0, t2

    # The circular measures must never appear unless the caller asks.
    assert "circular_do_not_cite" not in analyze(plain)
    assert "circular_do_not_cite" in analyze(plain, include_circular=True)

    # This measure must be independent of sentence length. Two texts with the same
    # short sentences but different vocabulary must score differently.
    assert coverage("Use the thing.", core, vocab)["coverage"] == 100.0
    assert coverage("Utilize the apparatus.", core, vocab)["coverage"] < 100.0

    print("readability self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
