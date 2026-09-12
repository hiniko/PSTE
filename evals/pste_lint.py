#!/usr/bin/env python3
"""PSTE-1 conformance checker.

Checks prose against the rules in spec/PSTE-1.md and reports findings by rule ID.
Reads the vocabulary from spec/wordlist.yaml and spec/terms.yaml — no word lists
are duplicated here.

Usage:
    pste_lint.py FILE...              check files, table output
    pste_lint.py --json FILE...       machine-readable
    pste_lint.py --level 3 FILE...    enforce vocabulary (default 2)
    pste_lint.py --self-test          run the conformance cases

Exit status is 1 when findings exist, so this works as a pre-commit hook.

This measures rule conformance, not readability and not quality. A clean score is
necessary, not sufficient: it cannot tell you the text is true or useful.
"""

import argparse
import csv
import functools
import json
import os
import re
import sys

SPEC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spec")

# A caller may set this to a JSON string to bypass spec/ and supply the vocabulary
# directly. None means "read spec/wordlist.yaml and spec/terms.yaml".
EMBEDDED_VOCAB = None


def _rehydrate(blob):
    """Turn the embedded JSON vocabulary back into the sets and dicts used below."""
    data = json.loads(blob) if isinstance(blob, str) else blob
    return {
        "instead_of": data.get("instead_of", {}),
        "marketing": set(data.get("marketing", [])),
        "phrasal": data.get("phrasal", {}),
        "latin": data.get("latin", {}),
        "british": data.get("british", {}),
        "hedges": set(data.get("hedges", [])),
        "frames": set(data.get("frames", [])),
        "term_verbs": set(data.get("term_verbs", [])),
        "term_nouns": set(data.get("term_nouns", [])),
        "approved": set(data.get("approved", [])),
    }

# ponytail: hand-rolled YAML reader. The subset here is flat scalars, lists, and
# `key: value` maps under known top-level keys — a PyYAML dependency for that is not
# worth it. Swap to PyYAML if the schema grows nested structures.


def _strip_comment(line):
    """Remove a trailing # comment not inside quotes."""
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _flow_list(s):
    """Parse an inline [a, b, c] list, possibly multi-line already joined."""
    s = s.strip()
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    return [_unquote(x) for x in s.split(",") if x.strip()]


def load_vocab(spec_dir=SPEC_DIR):
    """Extract the lists the linter needs from wordlist.yaml and terms.yaml.

    Returns a dict of plain Python structures. Deliberately tolerant: an entry the
    reader does not understand is skipped rather than raising, so a spec edit cannot
    break the linter at commit time.

    A caller may set EMBEDDED_VOCAB to skip the spec/ read entirely.
    """
    if EMBEDDED_VOCAB is not None and spec_dir is SPEC_DIR:
        return _rehydrate(EMBEDDED_VOCAB)
    vocab = {
        "instead_of": {},        # not-approved word -> approved word
        "marketing": set(),
        "phrasal": {},           # phrase -> replacement
        "latin": {},
        "british": {},           # British spelling -> American spelling
        "hedges": set(),
        "frames": set(),
        "term_verbs": set(),
        "term_nouns": set(),
        "approved": set(),
    }

    wl_path = os.path.join(spec_dir, "wordlist.yaml")
    if os.path.exists(wl_path):
        with open(wl_path, encoding="utf-8") as fh:
            raw = fh.read()
        section = None
        current_word = None
        pending_instead = False
        for line in raw.splitlines():
            line = _strip_comment(line)
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()

            if indent == 0 and stripped.endswith(":"):
                section = stripped[:-1]
                current_word, pending_instead = None, False
                continue

            if section == "words":
                if stripped.startswith("- word:"):
                    current_word = _unquote(stripped.split(":", 1)[1])
                    if current_word == "null":
                        current_word = None
                    elif current_word:
                        vocab["approved"].add(current_word.lower())
                    pending_instead = False
                elif stripped.startswith("instead_of:"):
                    rest = stripped.split(":", 1)[1].strip()
                    if rest.startswith("["):
                        for w in _flow_list(rest):
                            vocab["instead_of"][w.lower()] = current_word
                        pending_instead = False
                    else:
                        pending_instead = True
                elif pending_instead and stripped.startswith("- "):
                    vocab["instead_of"][_unquote(stripped[2:]).lower()] = current_word
                elif stripped.startswith(("example:", "note:", "meaning:", "forms:",
                                          "pos:", "counter_example:")):
                    pending_instead = False

            elif section == "marketing_adjectives" and stripped.startswith("- "):
                vocab["marketing"].add(_unquote(stripped[2:]).lower())

            elif (section in ("phrasal_verbs", "latin_abbreviations", "american_british")
                  and ":" in stripped):
                k, v = stripped.split(":", 1)
                key = _unquote(k).lower()
                val = _unquote(v)
                target = {
                    "phrasal_verbs": "phrasal",
                    "latin_abbreviations": "latin",
                    "american_british": "british",
                }[section]
                if key and val:
                    vocab[target][key] = val

            elif section == "hedges" and stripped.startswith("- "):
                vocab["hedges"].add(_unquote(stripped[2:]).lower())

            elif section == "response_frames" and stripped.startswith("- "):
                vocab["frames"].add(_unquote(stripped[2:]).lower())

    # A word that is approved in its own right must never be reported as
    # not-approved, even when another entry lists it as a synonym to avoid. These
    # are part-of-speech splits: `call` is an approved verb and an avoided noun,
    # `once` an approved adverb and an avoided conjunction. The checker cannot tell
    # the senses apart, so it defers to the approved sense and stays silent.
    # ponytail: a sense-aware checker needs a POS tagger. Not worth it for ~5 words.
    for word in list(vocab["instead_of"]):
        if word in vocab["approved"]:
            del vocab["instead_of"][word]

    tm_path = os.path.join(spec_dir, "terms.yaml")
    if os.path.exists(tm_path):
        with open(tm_path, encoding="utf-8") as fh:
            raw = fh.read()
        in_verbs = False
        in_nouns = False
        buf = None
        for line in raw.splitlines():
            line = _strip_comment(line)
            if not line.strip():
                continue
            stripped = line.strip()
            if stripped.startswith("term_verbs:"):
                in_verbs, in_nouns = True, False
                continue
            # `common_nouns` is a block list of the domain nouns every programmer
            # shares. PSTE-V5 permits them, so a vocabulary finding must not fire
            # on one: `flag`, `model` and `mode` all sat in this list and were
            # reported anyway, because nothing read it.
            if stripped.startswith("common_nouns:"):
                in_nouns, in_verbs = True, False
                continue
            if not line[:1].isspace() and stripped.endswith(":"):
                in_verbs = in_nouns = False
                continue
            if in_nouns:
                if stripped.startswith("- "):
                    vocab["term_nouns"].add(_unquote(stripped[2:]).lower())
                continue
            if not in_verbs:
                continue
            if buf is not None:
                buf += " " + stripped
                if "]" in stripped:
                    vocab["term_verbs"].update(w.lower() for w in _flow_list(buf))
                    buf = None
                continue
            if stripped.startswith("verbs:"):
                rest = stripped.split(":", 1)[1].strip()
                if "]" in rest:
                    vocab["term_verbs"].update(w.lower() for w in _flow_list(rest))
                else:
                    buf = rest
    return vocab


def load_weights(spec_dir=SPEC_DIR):
    """Read the rule-weight table from spec/rule_weights.csv.

    PSTE-1.md §15.5 is the normative table; this file is `lib/build_appendix.py`'s
    generated copy, read here so a caller never needs to parse markdown to get a
    weight. A caller who wants to check the spec and the CSV agree reads both and
    compares, the same way `evals/pste_lint.py --self-test` does (see §15.6).
    """
    weights = {}
    path = os.path.join(spec_dir, "rule_weights.csv")
    if not os.path.exists(path):
        return weights
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rule = row.get("rule", "").strip()
            raw = row.get("weight", "").strip()
            if not rule or raw == "N/A":
                continue
            weights[rule] = float(raw)
    return weights


# ---------------------------------------------------------------------------
# Text preparation
# ---------------------------------------------------------------------------

# A document can open with YAML front matter, and none of it is author prose: it
# records where the document came from and, for a generated one, the prompt that
# produced it. That prompt mentions a "writing standard" and a document's
# "structure", and both reported as unapproved vocabulary until this blanked it.
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
URL_RE = re.compile(r"https?://\S+")
BLOCKQUOTE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)


def _blank(match, keep=""):
    """Replace a span with spaces, keeping its length and its newlines.

    Every replacement here preserves length, so an offset into the stripped text is
    also an offset into the original. That is what lets a finding carry a line and a
    column that point at the real file.
    """
    span = match.group(0)
    filler = "".join("\n" if c == "\n" else " " for c in span)
    if keep and len(keep) + 2 <= len(span):
        # Leave a marker word so word counts and sentence splits stay right.
        return " " + keep + filler[len(keep) + 1 :]
    return filler


def strip_non_prose(text, keep_quotes=False):
    """Remove targets T2 and T3 before analysis, without moving anything.

    PSTE-S1: the rules apply to author prose only. Code, identifiers, and quoted
    text must never generate findings.

    The result has the same length as the input. Removed spans become spaces, so
    the position of every remaining word is unchanged.
    """
    text = FRONT_MATTER_RE.sub(_blank, text)
    text = FENCE_RE.sub(_blank, text)
    if not keep_quotes:
        text = BLOCKQUOTE_RE.sub(_blank, text)
    text = URL_RE.sub(lambda m: _blank(m, "URL"), text)
    # Each code span counts as one word (PSTE-N7) and its contents are exempt.
    text = INLINE_CODE_RE.sub(lambda m: _blank(m, "CODE"), text)

    # Blank the opted-out lines, then the counter-examples a rule quotes to show
    # what breaks it. Both are target T3, not author prose.
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if IGNORE_RE.search(ln):
            lines[i] = "".join("\n" if c == "\n" else " " for c in ln)
    text = "".join(lines)

    source = text

    def _drop_counter_example(m):
        # Keep the quoted text only if the words just before it do not negate it.
        if NEGATION_BEFORE_RE.search(source[: m.start()]):
            return _blank(m, "EXAMPLE")
        return m.group(0)

    return QUOTED_SPAN_RE.sub(_drop_counter_example, source)


HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
TABLE_RE = re.compile(r"^\s*\|")

# A document that teaches the rules must be able to show what breaks them. A line
# containing `pste-lint: ignore` is skipped, and so is any run of text in double
# quotes that follows the word `not` — the shape of "write X, not Y".
IGNORE_RE = re.compile(r"pste-lint:\s*ignore")
# A quoted span is a counter-example when the text immediately before it says "not"
# (or "never"/"do not write"). Matching the quoted span itself — rather than starting
# from the word `not` — avoids anchoring to a `not` that sits inside an earlier quote.
QUOTED_SPAN_RE = re.compile(r"[\"“]([^\"”\n]{3,})[\"”]")
NEGATION_BEFORE_RE = re.compile(r"(?:\bnot\b|\bnever\b|\binstead of\b)[\s,:]*$",
                                re.IGNORECASE)


def split_paragraphs(text):
    paras, cur = [], []
    for line in text.splitlines():
        if not line.strip():
            if cur:
                paras.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        paras.append("\n".join(cur))
    return paras


SENT_SPLIT_RE = re.compile(r"(?<=[.!?:])\s+")


def split_sentences(text, mark_list_items=False, with_offsets=False):
    """Split into sentences. A list item is its own sentence (PSTE-N7 / rule 8.4).

    mark_list_items adds a flag so a caller can relax rules that do not apply to a
    label-and-definition list entry. with_offsets adds the character offset of each
    sentence in `text`, which the caller turns into a line and a column.
    """
    out = []
    pos = 0
    for line in text.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        bare = line.strip()
        if not bare or HEADING_RE.match(bare) or TABLE_RE.match(bare):
            continue

        # Offset of the first non-space character on this line.
        indent = len(line) - len(line.lstrip())
        is_item = bool(LIST_RE.match(bare))
        marker = LIST_RE.match(bare)
        body_start = line_start + indent + (marker.end() if marker else 0)
        body = LIST_RE.sub("", bare)

        cursor = 0
        for part in SENT_SPLIT_RE.split(body):
            raw_len = len(part)
            lead = len(part) - len(part.lstrip())
            stripped = part.strip()
            if stripped:
                offset = body_start + cursor + lead
                item = [stripped]
                if mark_list_items:
                    item.append(is_item)
                if with_offsets:
                    item.append(offset)
                out.append(tuple(item) if len(item) > 1 else stripped)
            # +1 for the separator that split consumed.
            cursor += raw_len + 1
    return out


def line_col(text, offset):
    """Turn a character offset into a 1-indexed line and column."""
    if offset is None or offset < 0:
        return None, None
    head = text[:offset]
    line = head.count("\n") + 1
    col = offset - (head.rfind("\n") + 1) + 1
    return line, col


# PSTE-D7.1. A list that must be exhaustive is exempt from PSTE-D7, and the writer
# states that it is complete. The window is the 200 characters before the list: far
# enough to reach the sentence or heading right above it, never far enough to reach
# an unrelated marker earlier in the document.
COMPLETENESS_RE = re.compile(
    r"\b(complete|exhaustive|every|all)\b", re.IGNORECASE
)
D7_WINDOW = 200

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def count_words(sentence):
    """Word count under PSTE-N7: numbers with units, code spans, and hyphenated
    words each count as one."""
    return len(WORD_RE.findall(sentence))


# ---------------------------------------------------------------------------
# Checks. Each returns a list of (rule_id, message, excerpt).
# ---------------------------------------------------------------------------

IMPERATIVE_HINT = re.compile(
    r"^(run|add|remove|check|make|set|open|close|start|stop|use|write|read|install|"
    r"delete|copy|move|create|call|send|update|change|replace|do|go|see|note|click|"
    r"select|enter|press|type|save|find|test|build|deploy|merge|commit|push|pull)\b",
    re.IGNORECASE,
)

# PSTE-P1. An enumerable opener that turns an instruction into a request or a
# recommendation, instead of the imperative form the rule requires. This is a
# pre-filter for the easy, literal cases; the judge (PSTE-P1 in SEMANTIC_RULES)
# still covers a non-imperative instruction with none of these markers. The
# passive form ("the tests should be run") is already PSTE-G1's job, not this
# one's, so it is not matched here.
# PSTE-P1 names "you should run the tests" as the fault: an instruction dressed
# as a suggestion. "You can" is excluded, and so is "you need to". Neither one
# gives an instruction: "you can tune the interval" states that tuning is
# possible, and a command says the reader must do it. PSTE-A1 defeats P1 here,
# because the rewrite would change what the sentence says.
# The opener starts a clause, and a clause starts after an opening parenthesis
# or a comma as well as at the start of a sentence. PSTE-X4 permits a
# parenthesis and does not exempt what sits inside one, so an instruction
# dressed as a suggestion breaks the rule wherever it stands.
NON_IMPERATIVE_OPENER_RE = re.compile(
    r"(?:^|[(\[,;]\s*(?:and |or |then )?)(you should|you must|please|it is necessary to)\b",
    re.IGNORECASE,
)

# A trailing 's is far more often a possessive ("the writer's own actions") than a
# contraction, so `'s` is excluded. "it's" is the one case worth catching explicitly.
CONTRACTION_RE = re.compile(
    r"(?:\b\w+['’](?:t|re|ve|ll|m)\b)|(?:\bit['’]s\b)|(?:\blet['’]s\b)", re.IGNORECASE
)

IRREGULAR_PP = (
    r"done|made|sent|read|built|kept|held|set|put|run|written|shown|given|taken|"
    r"found|got|gotten|seen|known|thrown|drawn|left|lost|meant|paid|said|told"
)
BE_VERB = r"(?:am|is|are|was|were|be|been|being)"
PASSIVE_RE = re.compile(rf"\b{BE_VERB}\s+(?:\w+ed|{IRREGULAR_PP})\b", re.IGNORECASE)
PERFECT_RE = re.compile(
    rf"\b(?:have|has|had)\s+(?:been\s+)?(?:\w+ed|{IRREGULAR_PP})\b", re.IGNORECASE
)
AUX_STACK_RE = re.compile(
    r"\b(?:would|could|should|might|may|must|will|can)\s+(?:have|be)\s+"
    r"(?:been|being)\b",
    re.IGNORECASE,
)
# Some `-ing` words after a be-verb are adjectives describing a state, not
# progressive main verbs. "The service is running" states a condition; "the worker
# is processing the queue" describes an action in progress. Only the second breaks
# PSTE-G3. Treat the known state words as adjectives.
# ponytail: a fixed list beats a POS tagger for the handful that matter.
ING_ADJECTIVES = {
    "running", "missing", "pending", "outstanding", "existing", "remaining",
    "following", "leading", "trailing", "matching", "corresponding", "resulting",
    "interesting", "surprising", "confusing", "misleading", "willing", "boring",
}
ING_MAIN_RE = re.compile(rf"\b{BE_VERB}\s+(\w+ing)\b", re.IGNORECASE)
NOMINALIZATION_RE = re.compile(
    r"\b(?:perform(?:s|ed)?|conduct(?:s|ed)?|carr(?:y|ies|ied)\s+out|"
    r"make[s]?\s+use\s+of|provide[s]?)\s+(?:a|an|the)?\s*\w+"
    r"(?:tion|ment|ance|ence|sis|ing)\b",
    re.IGNORECASE,
)
# "<noun> of" only counts when the noun is a nominalized VERB — "the creation of",
# "the validation of". Ordinary nouns that happen to end in these letters ("sentence
# of", "sequence of", "substance of", "Association of") are not nominalizations.
# ponytail: explicit stoplist beats a morphology library for a few dozen cases.
# PSTE-G12. The order that English puts adjectives in before a noun. A native
# reader applies it without thinking, and a wrong order reads as wrong even when the
# reader cannot say why. A reader whose first language is not English has no such
# instinct, so a wrong order costs that reader time.
#
# This list holds only the words this checker can identify as adjectives WITHOUT a
# part of speech tagger. Most English words change class with context: "backup" is a
# noun in "restore the backup" and an adjective in "the backup file". A word that is
# not here is not checked, and a rule that checks nothing is better than one that
# reports a finding against correct text.
ADJECTIVE_ORDER = {
    # 1 opinion
    "useful": 1, "correct": 1, "safe": 1, "unsafe": 1, "wrong": 1, "valid": 1,
    "invalid": 1,
    # 2 size
    "large": 2, "small": 2, "short": 2, "tiny": 2, "huge": 2, "wide": 2,
    "narrow": 2,
    # 3 age
    "new": 3, "old": 3, "current": 3, "legacy": 3, "previous": 3, "recent": 3,
    "original": 3,
    # 4 shape
    "round": 4, "flat": 4, "square": 4,
    # 5 colour
    "red": 5, "green": 5, "blue": 5, "black": 5, "white": 5, "grey": 5,
    "gray": 5, "yellow": 5,
    # 6 origin
    "remote": 6, "local": 6, "upstream": 6, "downstream": 6, "external": 6,
    "internal": 6,
    # 7 material
    "binary": 7, "digital": 7, "physical": 7, "virtual": 7, "plastic": 7,
    "metal": 7, "wooden": 7,
    # 8 purpose
    "backup": 8, "debug": 8, "test": 8, "staging": 8, "production": 8,
    "temporary": 8,
}

ADJECTIVE_CATEGORY = {
    1: "opinion", 2: "size", 3: "age", 4: "shape",
    5: "colour", 6: "origin", 7: "material", 8: "purpose",
}

WORD_WITH_POSITION_RE = re.compile(r"[A-Za-z][A-Za-z-]*")


def adjective_runs(text):
    """Every run of two or more known adjectives, with where it starts.

    Walks the words and collects consecutive adjectives from ADJECTIVE_ORDER. A
    word that is not in that table breaks the run, so an unknown word never joins
    one and never produces a finding.
    """
    runs = []
    current = []
    for match in WORD_WITH_POSITION_RE.finditer(text):
        word = match.group(0).lower()
        if word in ADJECTIVE_ORDER:
            current.append((word, match.start()))
            continue
        if len(current) >= 2:
            runs.append(current)
        current = []
    if len(current) >= 2:
        runs.append(current)
    return runs

NOT_NOMINALIZATIONS = {
    "sentence", "sequence", "substance", "association", "instance", "reference",
    "difference", "evidence", "experience", "audience", "presence", "absence",
    "consequence", "importance", "distance", "balance", "chance", "science",
    "convenience", "confidence", "influence", "maintenance", "performance",
    "appliance", "compliance", "relevance", "occurrence", "preference",
    "moment", "element", "document", "argument", "comment", "component",
    "environment", "equipment", "department", "instrument", "increment", "segment",
    "fragment", "statement", "agreement", "requirement", "assessment",
    "question", "portion", "section", "fraction", "position", "condition",
    "version", "option", "function", "action", "connection", "collection",
    "direction", "solution", "relation", "proportion", "station", "nation",
}
NOMINAL_OF_RE = re.compile(r"\b(\w{4,}(?:tion|ment|ance|ence))\s+of\b", re.IGNORECASE)
SEMICOLON_RE = re.compile(r";")
EM_DASH_RE = re.compile(r"[—–]")
# PSTE-N5. A multi-word noun is a run of modifiers before a head noun. Anything that
# can start a new grammatical role — a verb, a preposition, a relative pronoun, an
# article — ends the run. Without this the pattern matches whole clauses.
NOUN_RUN_BREAK = {
    # articles and determiners
    "the", "a", "an", "this", "that", "these", "those", "its", "their", "his", "her",
    "our", "your", "my", "each", "every", "any", "some", "all", "no", "both",
    # prepositions and conjunctions
    "of", "to", "for", "with", "in", "on", "at", "by", "from", "as", "into", "over",
    "under", "before", "after", "and", "or", "but", "than", "when", "if", "so",
    "because", "while", "not", "only", "then", "also",
    "during", "between", "through", "until", "within", "without", "against",
    "across", "about", "above", "below", "since", "upon", "per", "via",
    # relative pronouns
    "which", "who", "whom", "whose", "where",
    # common verbs and auxiliaries that end a noun run
    "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "do", "does", "did", "can", "cannot", "may", "must",
    "will", "would", "should", "could", "might", "shall",
    "use", "uses", "used", "make", "makes", "made", "set", "sets", "run", "runs", "ran",
    "state", "states", "stated", "write", "writes", "wrote", "written",
    "give", "gives", "gave", "given", "keep", "keeps", "kept", "put", "puts",
    "check", "checks", "checked", "read", "reads", "start", "starts", "started",
    "stop", "stops", "stopped",
    "show", "shows", "shown", "showed", "add", "adds", "added",
    "remove", "removes", "removed", "change", "changes", "changed",
    "measure", "measures", "measured", "report", "reports", "reported",
    "apply", "applies", "applied", "carry", "carries", "carried",
    "create", "creates", "created",
    "exist", "exists", "existed", "fail", "fails", "failed", "return", "returns", "returned",
    "come", "comes", "came", "go", "goes", "went", "gone",
    "take", "takes", "took", "taken", "know", "knows", "knew", "known",
}

MULTIWORD_NOUN_RE = re.compile(r"\b(?:the|a|an)\s+((?:[a-z][a-z\-]*\s+){2,}[a-z][a-z\-]*)\b")

# In a real noun cluster only the head (the last word) may be plural: "the queue
# priority setting handler". A word ending in `s` INSIDE the run is nearly always a
# verb ("the readability claim needs human readers") or the end of one noun phrase
# before another begins. Either way the run is not a single cluster, so stop there.
# ponytail: heuristic, not a POS tagger. Upgrade only if real use shows misses.
INTERIOR_S_RE = re.compile(r"^[a-z][a-z\-]*(?<![su])s$")

# PSTE-V10. Lowercase `should` only. Uppercase SHOULD is an RFC 2119 conformance
# keyword, which is precisely the unambiguous usage this rule asks for.
SHOULD_RE = re.compile(r"(?<![A-Za-z])should(?:n['’]t)?(?![A-Za-z])")

# PSTE-S4. An identifier has a SHAPE: camelCase or snake_case. Ordinary English
# prose does not produce a token in either shape, and `strip_non_prose` already
# blanks a code span, so a surviving one is bare in prose. The rule is about
# INFLECTING an identifier, not about the bare identifier itself — that is a lesser,
# different problem (PSTE-S5) — so this matches only a camelCase/snake_case token
# that also carries an English inflectional suffix.
CAMEL_CASE_RE = r"[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+"
SNAKE_CASE_RE = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+"
IDENTIFIER_RE = re.compile(rf"\b(?:{CAMEL_CASE_RE}|{SNAKE_CASE_RE})\b")
# `ing`/`ed` only. A trailing `s` cannot be told apart from a plural-noun identifier
# name (`mempoolItems`, `chia_rs`) without knowing whether the identifier names a
# verb or a noun — the exact part-of-speech guess this file's checks must avoid.
# `ing`/`ed` have no such reading: no ordinary identifier segment ends that way by
# coincidence of naming, only by inflection.
INFLECTION_RE = re.compile(r"(?:ing|ed)$")

# PSTE-G10. A word match cannot tell a person whose pronouns are unknown from a
# quotation, or from a named person whose pronouns ARE known: that needs a reader,
# not a regular expression. This stays mechanical anyway, at SHOULD rather than the
# spec's MUST, and the message names the uncertainty rather than asserting a
# violation — a gendered pronoun is common and often correct (a quotation, a named
# person), so a MUST-severity word match would be a false-positive machine. SHOULD
# flags it for a human to confirm without failing a document on a hit alone.
GENDERED_PRONOUN_RE = re.compile(
    r"(?<![A-Za-z])(he|him|his|she|her|hers)(?![A-Za-z])", re.IGNORECASE
)



# PSTE-K1..K3. BCP 14 key words negate only with NOT, bind a named actor, and state a
# requirement rather than a fact. These checks run only on a document that already uses
# the key words, so ordinary prose never trips them.
KEYWORD = r"MUST|SHALL|SHOULD|REQUIRED|RECOMMENDED|MAY|OPTIONAL"
# The five that take a modal shape ("a writer MUST keep"). REQUIRED, RECOMMENDED, and
# OPTIONAL take an adjectival shape ("is REQUIRED to"), which needs its own pattern.
MODAL_KEYWORD = r"MUST|SHALL|SHOULD|MAY"
ADJ_KEYWORD = r"REQUIRED|RECOMMENDED|OPTIONAL"
KEYWORD_ANY_RE = re.compile(rf"\b(?:{KEYWORD})\b")

# PSTE-K1. A key word negates only with the word NOT, in capitals. Every other form
# below reads as an obligation to act rather than an obligation to avoid.
BAD_NEGATION_RE = re.compile(
    # `never`, `rarely`, and `no longer` are adverbs of negation: they modify the key
    # word itself, which BCP 14 does not allow. `omit`, `avoid`, and `refrain` are
    # ordinary verbs, and "A writer MAY omit the heading" is a valid permission, so
    # they are flagged only after MUST and SHALL, where they duplicate MUST NOT.
    rf"\b({KEYWORD})\s+(never|NEVER|rarely|seldom|no longer|not\b)"
)
# "MUST avoid" and "SHALL refrain" say what MUST NOT says, in a form a reader has to
# translate. A permission ("MAY omit") is left alone.
REDUNDANT_AVOIDANCE_RE = re.compile(
    r"\b(MUST|SHALL|SHOULD)\s+(avoid|avoids|refrain|refrains|abstain|abstains)\b"
)
# A PROHIBITION HIDDEN IN THE PREDICATE.
#
# "A writer MUST write no more than 20 words" forbids something, so it takes the
# negative key word: "A writer MUST NOT write more than 20 words". The positive key
# word with a limiting quantifier reads as an obligation to act, and a reader has to
# work out that it is really a prohibition.
#
# `only` is excluded on purpose. "A writer MUST use only these verb forms" is a
# positive requirement over a bounded set, and it is correct.
HIDDEN_PROHIBITION_RE = re.compile(
    rf"\b({MODAL_KEYWORD})\s+(?!NOT\b)(\w+)\s+((?:no more than|no fewer than|no less "
    rf"than|not more than)\b)"
)
# "nobody MUST", "no writer MUST", "neither writer SHALL".
NEGATED_SUBJECT_RE = re.compile(
    rf"\b(nobody|no one|no \w+|none|nothing|neither|never)\b[^.]{{0,24}}?"
    rf"\b({KEYWORD})\b",
    re.IGNORECASE,
)
# "is NOT REQUIRED to", which negates an adjectival key word with the wrong shape.
NEGATED_ADJ_RE = re.compile(rf"\bNOT\s+({ADJ_KEYWORD})\b")

# BCP 14 lists no `MAY NOT`. The form is ambiguous: a reader cannot tell whether it
# denies a permission or states that an action is unnecessary. `MUST NOT` says the
# first, and `MAY` on the alternative says the second.
MAY_NOT_RE = re.compile(r"\bMAY\s+NOT\b")

# PSTE-K2. A key word in the passive voice names no actor.
KEYWORD_PASSIVE_RE = re.compile(
    rf"\b({MODAL_KEYWORD})(?:\s+NOT)?\s+(?:be|been)\b"
)
# "is REQUIRED to be named", "is RECOMMENDED", "It is REQUIRED that".
ADJ_NO_ACTOR_RE = re.compile(
    rf"\b(?:is|are|was|were|it is|It is)\s+({ADJ_KEYWORD})\b"
)

# Cached: the vocabulary check asks for the same few hundred phrases once per
# word of prose, and compiling each one fresh cost 16 of the 17 seconds a level 3
# check took on a 400 word document. The set of phrases is bounded by the word
# list, so the cache cannot grow without bound.
@functools.lru_cache(maxsize=None)
def _word_re(phrase):
    return re.compile(r"(?<![A-Za-z])" + re.escape(phrase) + r"(?![A-Za-z])",
                      re.IGNORECASE)


# RFC-2119 severity per rule, baked in rather than parsed from spec/PSTE-1.md at
# runtime, so a caller never needs spec/PSTE-1.md on disk to get a severity, only
# spec/wordlist.yaml and spec/terms.yaml for the vocabulary. Each rule is
# `**PSTE-XX**: A writer MUST|SHOULD|MUST NOT|SHOULD NOT ...` in the spec; this
# is that keyword, by hand, for every rule ID `add()` can emit. PSTE-D7's spec
# sentence is compound (MUST NOT >7, SHOULD NOT >5) but the code only implements
# the >7 threshold, so it is a MUST finding.
RULE_SEVERITY = {
    "PSTE-N1": "MUST",
    "PSTE-N2": "MUST",
    "PSTE-N3": "MUST",
    "PSTE-N5": "MUST",
    "PSTE-X1": "MUST",
    "PSTE-X5": "SHOULD",
    "PSTE-G1": "MUST",
    "PSTE-G4": "MUST",
    "PSTE-G5": "MUST",
    "PSTE-G6": "MUST",
    "PSTE-G7": "MUST",
    "PSTE-G8": "MUST",
    "PSTE-G11": "MUST",
    "PSTE-G12": "MUST",
    "PSTE-V3": "MUST",
    "PSTE-V8": "MUST",
    "PSTE-V9": "MUST",
    "PSTE-V10": "MUST",
    "PSTE-K1": "MUST",
    "PSTE-K2": "MUST",
    "PSTE-L1": "MUST",
    "PSTE-L2": "MUST",
    "PSTE-L5": "MUST",
    "PSTE-D2": "MUST",
    "PSTE-D7": "MUST",
    "PSTE-S4": "MUST",
    "PSTE-G10": "SHOULD",
    "PSTE-V7": "MUST",
    "PSTE-P1": "MUST",
}

# These four encode part-of-speech knowledge as a closed word list, which can never
# be complete: N5's NOUN_RUN_BREAK and G7's NOT_NOMINALIZATIONS are stoplists over
# an open class of English words, and G11/G12's ADJECTIVE_ORDER table must classify
# every prenominal adjective while entries like "test" and "backup" are also
# ordinary nouns (see the "THE SAME WORDS AS NOUNS MUST NOT FIRE" cases in
# self_test). Measured false-positive rates: N5 75%, G7 30% (7 of 10 G7 findings in
# one eval were genuine — "restriction of", "deployment of" — so the rule stays on,
# it is only routed to a second opinion). G11/G12 share the identical defect with no
# corpus findings yet to measure.
#
# A finding from one of these rules is not wrong often enough to suppress, and not
# right often enough to fail a document on its own. `check_text` still reports it
# (a person reading the table wants every hit), but `add` marks it so a caller can
# route it to the judge instead of the verdict. See evals/semantic_lint.py, which
# asks the judge to confirm or reject each one before it counts.
ARBITRATED_RULES = {"PSTE-N5", "PSTE-G7", "PSTE-G11", "PSTE-G12"}


def check_text(text, level=2, vocab=None, kind="auto"):
    """Check prose. Returns a dict with findings, counts, and the word total."""
    vocab = vocab if vocab is not None else load_vocab()
    weights = load_weights()
    prose = strip_non_prose(text)
    findings = []

    # Set for each sentence, so `add` can report a position without every call
    # site passing one.
    current = {"offset": None, "sentence": ""}

    def add(rule, msg, excerpt, at=None):
        """Record a finding.

        `at` is an offset within the current sentence, from a match object, so the
        column points at the offending word and not merely at the sentence.
        """
        base = current["offset"]
        offset = None if base is None else base + (at or 0)
        line, col = line_col(text, offset)
        # Fail loudly on an unknown rule ID: a missing severity is a bug in this
        # table, not something a finding should paper over with a silent default.
        assert rule in RULE_SEVERITY, f"no RFC-2119 severity for {rule!r}"
        # Same stance as RULE_SEVERITY above: a rule this code can emit and the
        # weight table does not cover is a bug in the table (spec/PSTE-1.md
        # §15.5), not a finding that should carry a silent default weight.
        assert rule in weights, f"no weight for {rule!r} (see spec/PSTE-1.md §15.5)"
        findings.append(
            {
                "rule": rule,
                "message": msg,
                "excerpt": excerpt[:90],
                "line": line,
                "column": col,
                # Where the token sits inside the excerpt, for a caret under it.
                "excerpt_offset": at or 0,
                "severity": RULE_SEVERITY[rule],
                # True for a rule that encodes part-of-speech knowledge as a closed
                # word list (see ARBITRATED_RULES above). A caller that routes
                # findings to the judge uses this to tell a countable finding,
                # which fails a document on its own, from a candidate the judge
                # must confirm first.
                "arbitrated": rule in ARBITRATED_RULES,
                # Normalized 0-1 consequence of one violation (spec/PSTE-1.md
                # §15), from spec/rule_weights.csv. Lets a caller sum consequence
                # instead of counting every finding as one fault.
                "weight": weights[rule],
            }
        )

    marked = split_sentences(prose, mark_list_items=True, with_offsets=True)
    sentences = [s for s, _, _ in marked]
    total_words = sum(count_words(s) for s in sentences)

    for s, in_list_item, _offset in marked:
        current["offset"] = _offset
        current["sentence"] = s
        n = count_words(s)
        is_instruction = bool(IMPERATIVE_HINT.match(s.strip()))
        if kind == "instruction":
            is_instruction = True
        elif kind == "description":
            is_instruction = False

        # PSTE-N1 / PSTE-N2 sentence length
        if is_instruction and n > 20:
            add("PSTE-N1", f"instruction is {n} words, limit 20", s)
        elif not is_instruction and n > 25:
            add("PSTE-N2", f"description is {n} words, limit 25", s)

        # PSTE-N3 contractions
        for m in CONTRACTION_RE.finditer(s):
            add("PSTE-N3", f"contraction '{m.group(0)}'", s, m.start())

        # PSTE-P1 non-imperative opener. A pre-filter for the easy cases only; the
        # judge still covers a non-imperative instruction that opens some other way.
        m = NON_IMPERATIVE_OPENER_RE.search(s.strip())
        if m:
            add("PSTE-P1", f"'{m.group(1)}' is not the imperative form; "
                "write the instruction as a command", s, m.start())

        # PSTE-S4 inflected identifier. `strip_non_prose` already blanked every code
        # span, so a camelCase or snake_case token still here is bare in prose. The
        # rule is about INFLECTION, so a bare identifier alone is not reported here
        # (that is PSTE-S5, a lesser problem) — only one carrying ing/ed/s.
        for m in IDENTIFIER_RE.finditer(s):
            if INFLECTION_RE.search(m.group(0)):
                add("PSTE-S4", f"identifier '{m.group(0)}' is inflected; "
                    "use a code span and keep the identifier as written",
                    s, m.start())

        # PSTE-G10 gendered pronoun. A word match cannot tell an unknown-pronoun
        # person from a quotation or a named person whose pronouns are known, so
        # this reports at SHOULD and names the uncertainty rather than asserting
        # a violation.
        m = GENDERED_PRONOUN_RE.search(s)
        if m:
            add("PSTE-G10", f"gendered pronoun '{m.group(0)}'; confirm this names "
                "a person whose pronouns are known, or use 'they'", s, m.start())

        # PSTE-X1 semicolon
        m = SEMICOLON_RE.search(s)
        if m:
            add("PSTE-X1", "semicolon; write two sentences", s, m.start())

        # PSTE-X5 em dash joining clauses. In a list item a dash usually separates a
        # label from its definition, which the rule permits.
        m = EM_DASH_RE.search(s)
        if m and n > 8 and not in_list_item:
            add("PSTE-X5", "em dash joining clauses; write two sentences", s, m.start())

        # PSTE-G1 passive voice, in an INSTRUCTION only. PSTE-G2 permits the passive
        # in a description, so reporting every passive contradicts the standard the
        # checker exists to enforce.
        #
        # This was 35 of 113 findings in one eval, and 34 of those 35 were in
        # descriptions: "the singleton was melted", "the blockchain is decentralized".
        # Every one conforms. A checker that reports conforming text teaches a writer
        # to ignore it, which costs more than the rule gains.
        #
        # Whether the actor is GENUINELY unknown, the other half of G2, needs a
        # reader. `evals/semantic_lint.py` judges that. This half is mechanical.
        if is_instruction:
            for m in PASSIVE_RE.finditer(s):
                add("PSTE-G1", f"passive voice '{m.group(0)}'; name the actor",
                    s, m.start())

        # PSTE-G4 perfect tense
        for m in PERFECT_RE.finditer(s):
            add("PSTE-G4", f"perfect tense '{m.group(0)}'; use simple past", s, m.start())

        # PSTE-G5 stacked auxiliaries
        for m in AUX_STACK_RE.finditer(s):
            add("PSTE-G5", f"stacked auxiliaries '{m.group(0)}'", s, m.start())

        # PSTE-G6 -ing main verb
        for m in ING_MAIN_RE.finditer(s):
            if m.group(1).lower() in ING_ADJECTIVES:
                continue  # a state, not an action in progress
            add("PSTE-G6", f"'-ing' main verb '{m.group(0)}'", s, m.start())

        # PSTE-G7 nominalization
        for m in NOMINALIZATION_RE.finditer(s):
            add("PSTE-G7", f"nominalization '{m.group(0)}'; use a verb", s, m.start())
        for m in NOMINAL_OF_RE.finditer(s):
            if m.group(1).lower() not in NOT_NOMINALIZATIONS:
                add("PSTE-G7", f"nominalization '{m.group(0)}'; use a verb", s, m.start())

        # PSTE-G11 and PSTE-G12: how many adjectives, and in what order.
        for run in adjective_runs(s):
            words = [w for w, _ in run]
            if len(run) > 2:
                add(
                    "PSTE-G11",
                    f"{len(run)} adjectives before a noun: "
                    f"'{' '.join(words)}'; write no more than two",
                    s,
                    run[0][1],
                )
            # Check the order whatever the count, so a writer who keeps three
            # still learns which pair sits the wrong way round.
            for (first, offset), (second, _) in zip(run, run[1:]):
                rank_first = ADJECTIVE_ORDER[first]
                rank_second = ADJECTIVE_ORDER[second]
                if rank_first > rank_second:
                    add(
                        "PSTE-G12",
                        f"adjective order '{first} {second}': "
                        f"{ADJECTIVE_CATEGORY[rank_second]} comes before "
                        f"{ADJECTIVE_CATEGORY[rank_first]}, so write "
                        f"'{second} {first}'",
                        s,
                        offset,
                    )

        # PSTE-G8 phrasal verbs
        for phrase, repl in vocab["phrasal"].items():
            m = _word_re(phrase).search(s)
            if m:
                add("PSTE-G8", f"phrasal verb '{phrase}'; use '{repl}'", s, m.start())

        # PSTE-V8 Latin abbreviations. Match on a word boundary, never as a
        # substring: `ie` sits inside "client" and `sic` inside "basic". A bare
        # `re.search` was safe only while every entry ended in a period, and the
        # first unpunctuated entry reported a finding against correct text.
        # An all-caps, period-free hit is an acronym wearing a Latin abbreviation's
        # letters, not the abbreviation itself: "VS Code", "IE" (the browser), a
        # "SIC code", "NB" (New Brunswick). A genuine Latin abbreviation is either
        # lowercase, sentence-initial title case ("E.g."), or all-caps only with
        # its periods ("N.B."), so gate on caps-without-periods rather than caps
        # alone.
        for abbr, repl in vocab["latin"].items():
            m = _word_re(abbr).search(s)
            if m and m.group().isupper() and "." not in m.group():
                continue
            if m:
                add("PSTE-V8", f"Latin abbreviation '{abbr}'; use '{repl}'",
                    s, m.start())

        # PSTE-V7 American English spelling. Same shape as PSTE-V8: a literal list
        # sourced from spec/wordlist.yaml, matched on a word boundary.
        for british, american in vocab["british"].items():
            m = _word_re(british).search(s)
            if m:
                add("PSTE-V7", f"British spelling '{british}'; use '{american}'",
                    s, m.start())

        # PSTE-V9 marketing adjectives
        for word in vocab["marketing"]:
            m = _word_re(word).search(s)
            if m:
                add("PSTE-V9", f"marketing adjective '{word}'", s, m.start())

        # PSTE-V10 modal ambiguity
        m = SHOULD_RE.search(s)
        if m:
            add("PSTE-V10", "'should' is ambiguous; use can/may/must/is likely to",
                s, m.start())

        # PSTE-N5 multi-word nouns. Truncate the candidate run at the first word that
        # starts a new grammatical role, then measure what is left.
        for m in MULTIWORD_NOUN_RE.finditer(s):
            run = []
            for index, w in enumerate(m.group(1).split()):
                lw = w.lower()
                # A past participle straight after the article is an adjective, and
                # PSTE-G3 permits it: "the failed database connection retry" opens a
                # chain. The same word later in the run is a verb, and ends it:
                # "the file failed the check". Position tells the two apart.
                adjectival = index == 0 and lw.endswith("ed")
                if lw in NOUN_RUN_BREAK and not adjectival:
                    break
                run.append(w)
                # Only the head of a cluster may be plural; an interior `s` word ends it.
                if INTERIOR_S_RE.match(lw):
                    break
            if len(run) > 3:
                add("PSTE-N5", f"multi-word noun '{' '.join(run)}' over 3 words",
                    s, m.start())


        # PSTE-K1..K3, for a document that states rules with BCP 14 key words.
        if KEYWORD_ANY_RE.search(s):
            m = BAD_NEGATION_RE.search(s)
            if m:
                add("PSTE-K1", f"'{m.group(1)} {m.group(2)}' is not a BCP 14 form; "
                    f"use '{m.group(1)} NOT'", s, m.start())
            m = HIDDEN_PROHIBITION_RE.search(s)
            if m:
                add(
                    "PSTE-K1",
                    f"'{m.group(1)} {m.group(2)} {m.group(3)}' hides a prohibition; "
                    f"write '{m.group(1)} NOT {m.group(2)} more than'",
                    s,
                    m.start(),
                )

            m = REDUNDANT_AVOIDANCE_RE.search(s)
            if m:
                add("PSTE-K1", f"'{m.group(1)} {m.group(2)}' is not a BCP 14 form; "
                    f"use '{m.group(1)} NOT'", s, m.start())
            m = NEGATED_SUBJECT_RE.search(s)
            if m:
                add("PSTE-K1", f"'{m.group(1)}' negates '{m.group(2)}'; "
                    f"use '{m.group(2)} NOT' with a named actor", s, m.start())
            m = MAY_NOT_RE.search(s)
            if m:
                add("PSTE-K1", "'MAY NOT' is not a BCP 14 form and is ambiguous; "
                    "use 'MUST NOT' to forbid, or 'MAY' on the alternative",
                    s, m.start())
            m = NEGATED_ADJ_RE.search(s)
            if m:
                add("PSTE-K1", f"'NOT {m.group(1)}' is not a BCP 14 form; "
                    f"state the requirement with MUST NOT or MAY", s, m.start())
            m = KEYWORD_PASSIVE_RE.search(s)
            if m:
                add("PSTE-K2", f"'{m.group(0)}' names no actor; "
                    "put the actor before the key word", s, m.start())
            m = ADJ_NO_ACTOR_RE.search(s)
            if m:
                add("PSTE-K2", f"'{m.group(0).strip()}' names no actor; "
                    f"write 'A writer MUST ...' instead of '{m.group(1)}'",
                    s, m.start())

        # PSTE-V3 / vocabulary, Level 3 only. Report the longest match at a given
        # position only: "going forward" must not also report "forward".
        if level >= 3:
            spans = []  # (start, end, rule, message)
            for bad, good in vocab["instead_of"].items():
                for m in _word_re(bad).finditer(s):
                    if good:
                        spans.append((m.start(), m.end(), "PSTE-V3",
                                      f"'{bad}' is not approved; use '{good}'"))
                    else:
                        spans.append((m.start(), m.end(), "PSTE-L2",
                                      f"'{bad}' carries no information; delete it"))
            # Longest first, then keep a match only if it overlaps nothing kept.
            spans.sort(key=lambda sp: (sp[0], -(sp[1] - sp[0])))
            kept = []
            for sp in sorted(spans, key=lambda sp: -(sp[1] - sp[0])):
                if any(sp[0] < k[1] and k[0] < sp[1] for k in kept):
                    continue
                kept.append(sp)
            for sp in sorted(kept):
                # A marketing adjective already reported under PSTE-V9 is one
                # problem, not two.
                word = sp[3].split("'")[1] if "'" in sp[3] else ""
                if word.lower() in vocab["marketing"]:
                    continue
                # A term from spec/terms.yaml names something in software that
                # plain English cannot name accurately, and PSTE-V5 permits it.
                # `flag` collapsed to `warn` and `drop` to `fall` on prose about
                # a command line switch and a dropped table, which is wrong in
                # every software sense of the word.
                if (word.lower() in vocab["term_nouns"]
                        or word.lower() in vocab["term_verbs"]):
                    continue
                add(sp[2], sp[3], s, sp[0])

        # PSTE-L1 stacked hedging
        hits = [h for h in vocab["hedges"] if _word_re(h).search(s)]
        if len(hits) > 1:
            add("PSTE-L1", f"stacked hedging: {', '.join(sorted(hits)[:3])}", s)

    # PSTE-D2 paragraph length. A block of list items is not a paragraph, so skip a
    # block where any line is an item.
    # `split_paragraphs` returns text and not offsets, so find each paragraph in the
    # prose to report the line it starts on. Without this the finding lands wherever
    # the sentence loop above stopped, which is the end of the document.
    para_at = 0
    for para in split_paragraphs(prose):
        head = para.strip()
        found = prose.find(head[:40], para_at) if head else -1
        if found >= 0:
            para_at = found + 1
        if HEADING_RE.match(head) or TABLE_RE.match(head):
            continue
        if any(LIST_RE.match(ln.strip()) for ln in para.splitlines()):
            continue
        sents = split_sentences(para)
        if len(sents) > 6:
            current["offset"] = found if found >= 0 else None
            add("PSTE-D2", f"paragraph has {len(sents)} sentences, limit 6", head)

    # PSTE-D7 list length. Count the items of one run of list lines. A blank line or
    # any non-item line ends the run, so two short lists never merge into one long
    # one. Only top-level items count: an indented item belongs to its parent, and
    # counting nested items would report a short list with sub-points as a long list.
    run, run_head, run_at = 0, "", None
    line_at = 0
    for line in prose.splitlines() + [""]:
        m = LIST_RE.match(line)
        nested = m and (len(line) - len(line.lstrip())) > 0
        if m and not nested:
            run += 1
            if run == 1:
                run_head, run_at = line.strip(), line_at
        elif not line.strip() or not m:
            # A run only ends on a blank line or a non-item line. A nested item
            # keeps the run open without adding to the count.
            if not nested:
                if run > 7:
                    # PSTE-D7.1: a list stated as complete is exempt. Look at the
                    # text right before the list, not the whole document, so a
                    # completeness marker on an earlier, unrelated list cannot
                    # excuse this one.
                    before = prose[max(0, run_at - D7_WINDOW):run_at]
                    if not COMPLETENESS_RE.search(before):
                        # Report at the first item of the run, not wherever the
                        # sentence loop happened to stop.
                        current["offset"] = run_at
                        add("PSTE-D7", f"list has {run} items, limit 7", run_head)
                run, run_head, run_at = 0, "", None
        line_at += len(line) + 1

    # PSTE-L5 frame phrases. A frame is only a frame at the edge of the text, so a
    # match in the middle is left alone: "of course" inside a paragraph can carry
    # meaning, and the same words as an opener never do. The edge is the first and
    # the last sentence of the whole text, and nothing between them.
    edges = []
    if marked:
        edges.append(("opener", marked[0]))
        if len(marked) > 1:
            edges.append(("closer", marked[-1]))
    for where, (s, _in_list, at) in edges:
        low = s.lower()
        hit = max((f for f in vocab["frames"] if f in low), key=len, default=None)
        if hit:
            current["offset"] = at + low.index(hit)
            add("PSTE-L5", f"{where} frame '{hit}' states no fact; delete it", s)

    by_rule = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1

    return {
        "words": total_words,
        "sentences": len(sentences),
        "findings": findings,
        "by_rule": by_rule,
        "total": len(findings),
        "per_100w": round(len(findings) * 100 / total_words, 2) if total_words else 0.0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "Conformance is not quality. This tool reports whether text follows the rules "
    "of PSTE-1.\nIt does not measure readability, and nobody has yet tested whether "
    "PSTE text helps a\nreader. Do not present this result as evidence of quality. "
    "See evals/FUTURE-WORK.md."
)


def format_table(path, result, verbose):
    """A verdict, and when it fails, what failed.

    The output gives a verdict rather than a score. A count invites a reader to
    treat it as a grade, to compare one document with another, and to quote it as
    evidence that the text is good. It cannot support any of that: it counts the
    rules that the text breaks, and nothing more.

    A failure lists every offender, because a verdict with no detail helps nobody
    fix anything. The detail is there to be acted on, not to be totalled.
    """
    if not result["findings"]:
        return f"{path}: PASS"

    lines = [f"{path}: FAIL"]
    # In file order, so a writer can work down the file rather than jump about.
    ordered = sorted(
        result["findings"],
        key=lambda f: (f.get("line") or 0, f.get("column") or 0, f["rule"]),
    )
    for f in ordered:
        where = f"{path}:{f['line']}:{f['column']}" if f.get("line") else path
        lines.append(f"  {where}: {f['rule']} {f['message']}")
        if verbose and f.get("excerpt"):
            lines.append(f"      {f['excerpt']}")
            caret = f.get("excerpt_offset")
            if caret is not None and 0 <= caret < len(f["excerpt"]):
                lines.append(f"      {' ' * caret}^")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="PSTE-1 conformance checker")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--level", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument(
        "--json",
        action="store_true",
        help="machine-readable output, with counts, for tooling",
    )
    ap.add_argument(
        "-v", "--verbose", action="store_true", help="show the text of each finding"
    )
    ap.add_argument(
        "--no-disclaimer",
        action="store_true",
        help="omit the note that conformance is not quality (for a pre-commit hook, "
        "where the note repeats on every run)",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.files:
        ap.print_help()
        return 2

    vocab = load_vocab()
    results, failed = {}, 0
    for path in args.files:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"{path}: cannot read: {exc}", file=sys.stderr)
            continue
        res = check_text(text, level=args.level, vocab=vocab)
        results[path] = res
        if res["findings"]:
            failed += 1
        if not args.json:
            print(format_table(path, res, args.verbose), flush=True)

    if args.json:
        # The counts stay here on purpose. A program that consumes this output can
        # track a regression without a person reading a number as a grade. The
        # disclaimer travels with the data.
        print(
            json.dumps(
                {
                    "level": args.level,
                    "disclaimer": DISCLAIMER.replace("\n", " "),
                    "files": results,
                },
                indent=2,
            )
        )
    elif failed and not args.no_disclaimer:
        print(f"\n{DISCLAIMER}", file=sys.stderr)

    return 1 if failed else 0


# ---------------------------------------------------------------------------
# Self-test. One case per rule, drawn from spec/conformance/.
# ---------------------------------------------------------------------------

def self_test():
    """Assert-based checks. Each case names the rule it must and must not raise."""
    vocab = load_vocab()

    def rules_for(text, level=2, kind="auto"):
        return set(
            f["rule"] for f in check_text(text, level, vocab, kind)["findings"]
        )

    # Vocabulary loaded correctly.
    assert vocab["instead_of"].get("utilize") == "use", "wordlist: utilize -> use"
    assert vocab["instead_of"].get("prior to") == "before", "wordlist: prior to"
    assert "seamless" in vocab["marketing"], "wordlist: marketing adjectives"
    assert vocab["phrasal"].get("spin up") == "start", "wordlist: phrasal verbs"
    assert vocab["latin"].get("e.g.") == "for example", "wordlist: latin"
    assert "deploy" in vocab["term_verbs"], "terms: term verbs loaded"
    assert "check" in vocab["approved"], "wordlist: approved words"
    assert vocab["instead_of"].get("basically") is None, "filler has no replacement"
    assert "basically" in vocab["instead_of"], "filler is listed"
    # A word approved in one part of speech is never reported as not-approved,
    # even when another entry avoids it in a different sense.
    for w in sorted(vocab["approved"]):
        assert w not in vocab["instead_of"], f"{w} is both approved and routed away"
    assert "PSTE-V3" not in rules_for("Call the function once.", level=3)

    # Every route must point at a word the standard defines: an approved word, or a
    # term verb from terms.yaml. Otherwise the checker tells a writer to use a word
    # that the standard itself bans, or does not define at all.
    known = vocab["approved"] | vocab["term_verbs"]

    def _defined(target):
        # A multi-word target is fine when its first word is defined.
        return target.lower() in known or target.split()[0].lower() in known

    unknown = sorted({t for t in vocab["instead_of"].values() if t and not _defined(t)})
    assert not unknown, f"routes to undefined words: {unknown}"

    dangling = sorted(
        {f"{k} -> {t}" for k, t in vocab["phrasal"].items() if not _defined(t)}
    )
    assert not dangling, f"phrasal verbs route to undefined words: {dangling}"

    # Every example in the word list must itself pass the checker. A standard that
    # breaks its own rules in its own examples is not usable.
    import glob as _glob  # noqa: F401  (kept local; only the self-test needs it)
    _wl = os.path.join(SPEC_DIR, "wordlist.yaml")
    if os.path.exists(_wl) and EMBEDDED_VOCAB is None:
        bad_examples = []
        with open(_wl, encoding="utf-8") as fh:
            for line in fh:
                st = line.strip()
                if not st.startswith("example:"):
                    continue
                ex = _unquote(st.split(":", 1)[1])
                if not ex or ex == "null":
                    continue
                if check_text(ex, 2, vocab)["findings"]:
                    bad_examples.append(ex)
        assert not bad_examples, (
            f"{len(bad_examples)} word-list examples break the rules, "
            f"first: {bad_examples[0]!r}"
        )

    # A phrase match suppresses the single word inside it: "going forward" must not
    # also report "forward".
    msgs = [
        f["message"] for f in check_text("Going forward, we plan the work.", 3, vocab)["findings"]
    ]
    assert any("going forward" in m for m in msgs), msgs
    assert not any("'forward'" in m for m in msgs), msgs

    # A marketing adjective is one finding, not two.
    r = check_text("The parser is robust.", 3, vocab)["findings"]
    assert [f["rule"] for f in r] == ["PSTE-V9"], r

    # PSTE-N1 instruction length.
    long_instr = "Run the migration script " + " ".join(["now"] * 20) + "."
    assert "PSTE-N1" in rules_for(long_instr, kind="instruction")
    assert "PSTE-N1" not in rules_for("Run the migration script.")

    # PSTE-N2 description length.
    long_desc = "The service " + " ".join(["really"] * 30) + " fails."
    assert "PSTE-N2" in rules_for(long_desc, kind="description")

    # PSTE-N3 contractions.
    assert "PSTE-N3" in rules_for("The file doesn't exist.")
    assert "PSTE-N3" not in rules_for("The file does not exist.")

    # PSTE-X1 semicolon.
    assert "PSTE-X1" in rules_for("The build failed; the log shows why.")
    assert "PSTE-X1" not in rules_for("The build failed. The log shows why.")

    # PSTE-G1 passive voice, in an instruction only. PSTE-G2 permits the passive in
    # a description, so a checker that reports every passive contradicts the
    # standard and trains a writer to ignore it.
    assert "PSTE-G1" in rules_for("Check that the file is rejected by the linter.",
                                  kind="instruction")
    assert "PSTE-G1" not in rules_for("The linter rejects the file.")
    # A description states what happened. It conforms, and it must stay silent.
    assert "PSTE-G1" not in rules_for("The singleton was melted.", kind="description")
    assert "PSTE-G1" not in rules_for("The Chia blockchain is decentralized.")

    # PSTE-G4 perfect tense.
    assert "PSTE-G4" in rules_for("I have changed the timeout value.")
    assert "PSTE-G4" not in rules_for("I changed the timeout value.")

    # PSTE-G5 stacked auxiliaries.
    assert "PSTE-G5" in rules_for("The value would have been read from the cache.")

    # PSTE-G6 -ing main verb.
    assert "PSTE-G6" in rules_for("The worker is processing the queue.")
    assert "PSTE-G6" not in rules_for("The worker processes the queue.")
    # An -ing adjective states a condition and is not a progressive main verb.
    assert "PSTE-G6" not in rules_for("Check that the service is running.")
    assert "PSTE-G6" not in rules_for("The request fails when the header is missing.")

    # PSTE-N5 must break the run at a preposition.
    assert "PSTE-N5" not in rules_for(
        "The cache has a low hit rate during the first hour."
    )
    assert "PSTE-N5" not in rules_for(
        "The log shows a strange gap between two timestamps."
    )

    # PSTE-G7 nominalization.
    assert "PSTE-G7" in rules_for("Perform an analysis of the log file.")
    assert "PSTE-G7" not in rules_for("Analyze the log file.")

    # PSTE-G8 phrasal verb.
    assert "PSTE-G8" in rules_for("Spin up the container.")
    assert "PSTE-G8" not in rules_for("Start the container.")

    # PSTE-V8 Latin abbreviation.
    assert "PSTE-V8" in rules_for("Use a cache, e.g. Redis.")
    assert "PSTE-V8" not in rules_for("Use a cache, for example Redis.")
    # An abbreviation must match on a word boundary and never as a substring. `ie`
    # sits inside "client", `sic` inside "basic", and `nb` inside "unbounded". A bare
    # substring search was safe only while every entry ended in a period.
    assert "PSTE-V8" not in rules_for("The client retries the request once.")
    assert "PSTE-V8" not in rules_for("The basic check passes.")
    assert "PSTE-V8" in rules_for("Use a cache, i.e. Redis.")
    # An all-caps, period-free hit is an acronym, not the Latin abbreviation:
    # "VS Code" is a product name, not "versus". A genuine unpunctuated form
    # still fires, including sentence-initial title case.
    assert "PSTE-V8" not in rules_for("VS Code users should follow the same steps.")
    assert "PSTE-V8" in rules_for("Node versus Python is a common comparison.")
    assert "PSTE-V8" in rules_for("Eg this rule catches sentence-initial forms.")
    assert "PSTE-V8" in rules_for("N.B. check the config first.")

    # PSTE-V9 marketing adjective.
    assert "PSTE-V9" in rules_for("The parser is robust.")
    assert "PSTE-V9" not in rules_for("The parser recovers from a bad header.")

    # PSTE-V10 modal ambiguity.
    assert "PSTE-V10" in rules_for("The service should restart.")
    assert "PSTE-V10" not in rules_for("The service restarts automatically.")
    # RFC 2119 keywords are the unambiguous usage the rule asks for, not a violation.
    assert "PSTE-V10" not in rules_for("A writer SHOULD use a code span.")
    assert "PSTE-V10" not in rules_for("At Level 2 these rules are SHOULD.")

    # PSTE-N5 must measure a noun run, not a whole clause. Regression: the first
    # version matched verb phrases such as "result before the explanation".
    assert "PSTE-N5" in rules_for("Read the queue priority setting handler docs.")
    assert "PSTE-N5" not in rules_for("The handler that sets the queue priority.")
    assert "PSTE-N5" not in rules_for("A writer MUST state the result before the explanation.")
    assert "PSTE-N5" not in rules_for("No study known to the editors measures those conditions.")
    assert "PSTE-N5" not in rules_for("I changed the file, not the agent changed the file.")
    # An interior plural or third-person verb ends the run: these are clauses.
    assert "PSTE-N5" not in rules_for(
        "Testing the readability claim needs human readers, not a linter."
    )
    assert "PSTE-N5" not in rules_for("A style rubric cuts slop markers by half.")
    assert "PSTE-N5" not in rules_for("This shows how a style skill resists drift.")
    # A genuine four-word cluster is still caught.
    assert "PSTE-N5" in rules_for("Open the user account preference override panel.")
    # NOUN_RUN_BREAK must cover negated modals and irregular past tense too, not
    # just the base verb form. Regression: "cannot" and "took" were absent, so
    # these clauses were mistaken for four-word noun phrases.
    assert "PSTE-N5" not in rules_for(
        "Check that the scheduler cannot schedule new pods."
    )
    assert "PSTE-N5" not in rules_for(
        "Check that the user base took up more space."
    )
    # Genuine >3-word noun phrases must still be caught after widening the stoplist.
    assert "PSTE-N5" in rules_for("Check the user session timeout retry limit.")
    assert "PSTE-N5" in rules_for("Read the database connection pool config docs.")

    # PSTE-L1 stacked hedging.
    assert "PSTE-L1" in rules_for("This might possibly break the cache.")
    assert "PSTE-L1" not in rules_for("This can break the cache.")

    # PSTE-V3 vocabulary, level 3 only.
    assert "PSTE-V3" in rules_for("Utilize the cache.", level=3)
    assert "PSTE-V3" not in rules_for("Utilize the cache.", level=2)
    assert "PSTE-V3" not in rules_for("Use the cache.", level=3)

    # PSTE-L2 filler has no replacement, so it routes to L2 not V3.
    assert "PSTE-L2" in rules_for("This basically works.", level=3)

    # PSTE-D2 paragraph length.
    para = " ".join(f"The step {i} runs." for i in range(8))
    assert "PSTE-D2" in rules_for(para)
    # A list of eight items is not an eight-sentence paragraph.
    bullets = "\n".join(f"- The step {i} runs." for i in range(8))
    assert "PSTE-D2" not in rules_for(bullets)
    # A finding must point at the paragraph, not at wherever the sentence loop
    # stopped. The long paragraph is first and more text follows it, so a stale
    # offset from the end of the document reports the last line and not line 1.
    two = " ".join(f"The step {i} runs." for i in range(8)) + "\n\nThe cache is cold."
    d2 = [f for f in check_text(two)["findings"] if f["rule"] == "PSTE-D2"]
    assert len(d2) == 1 and d2[0]["line"] == 1, d2

    # PSTE-D7 list length. Seven is the limit, so eight is a finding.
    assert "PSTE-D7" in rules_for("\n".join(f"- item {i}" for i in range(8)))
    assert "PSTE-D7" not in rules_for("\n".join(f"- item {i}" for i in range(7)))
    # Two short lists separated by a blank line are two lists, not one long one.
    short = "\n".join(f"- item {i}" for i in range(5))
    assert "PSTE-D7" not in rules_for(short + "\n\n" + short)
    # A nested item belongs to its parent and does not add to the parent's count.
    nested = "\n".join(f"- item {i}\n  - sub {i}" for i in range(5))
    assert "PSTE-D7" not in rules_for(nested)
    # The finding points at the first item of the run. Text after the list means a
    # stale offset reports the last line instead.
    long_list = ("The steps follow.\n\n"
                 + "\n".join(f"- item {i}" for i in range(8))
                 + "\n\nThe cache is cold.")
    d7 = [f for f in check_text(long_list)["findings"] if f["rule"] == "PSTE-D7"]
    assert len(d7) == 1 and d7[0]["line"] == 3, d7

    # PSTE-D7.1 an exhaustive list is exempt from PSTE-D7's item limit.
    plain_long = "The values follow.\n\n" + "\n".join(f"- item {i}" for i in range(8))
    assert "PSTE-D7" in rules_for(plain_long), "no completeness marker; D7 still fires"
    exhaustive_long = ("This is the complete list of error codes.\n\n"
                       + "\n".join(f"- item {i}" for i in range(8)))
    assert "PSTE-D7" not in rules_for(exhaustive_long), "a stated-complete list is exempt"
    # The marker word must sit near the list, not merely somewhere earlier in the
    # document, or an unrelated list borrows another one's exemption.
    far_marker = ("This is the complete guide.\n\n" + ("Padding. " * 60) + "\n\n"
                 + "\n".join(f"- item {i}" for i in range(8)))
    assert "PSTE-D7" in rules_for(far_marker), "a distant marker must not exempt this list"

    # PSTE-L5 frame phrases, at the edges only.
    assert "PSTE-L5" in rules_for("Great question. The build fails.")
    assert "PSTE-L5" in rules_for("The build fails. Hope this helps.")
    # The same words mid-text are not a frame: only the first and the last
    # sentence can carry one.
    mid = "The build fails. Of course the cache is cold. A variable is missing."
    assert "PSTE-L5" not in rules_for(mid)
    # The finding points at the phrase, not at the end of the document.
    l5 = [f for f in check_text("Great question. The build fails.")["findings"]
          if f["rule"] == "PSTE-L5"]
    assert len(l5) == 1 and l5[0]["line"] == 1 and l5[0]["column"] == 1, l5

    # PSTE-X5: a dash separating a label from its definition in a list is permitted.
    assert "PSTE-X5" not in rules_for(
        "- Code comments and commit messages — match the repository's style"
    )
    assert "PSTE-X5" in rules_for(
        "The build failed on the first attempt — the log shows a missing dependency."
    )

    # PSTE-N3 must not flag a possessive.
    assert "PSTE-N3" not in rules_for("The writer's own actions are reported.")
    assert "PSTE-N3" in rules_for("It's broken.")

    # PSTE-G7 must not flag an ordinary noun that ends in -ence/-ment/-tion.
    assert "PSTE-G7" not in rules_for("The first sentence of the reply answers it.")
    assert "PSTE-G7" not in rules_for("Use a list for a sequence of three steps.")
    assert "PSTE-G7" not in rules_for("This changes the substance of the reply.")
    assert "PSTE-G7" in rules_for("The validation of the input happens first.")

    # A rule may quote its own counter-example without failing its own check.
    assert rules_for('Write "do not", not "don\'t".') == set()
    assert "PSTE-G1" not in rules_for(
        'Write "the linter rejects the file", not "the file is rejected".'
    )
    # The exemption must be narrow: only a NEGATED quote is skipped. The carrier is
    # an instruction, because PSTE-G2 permits the passive in a description and the
    # subject of this test is the quote exemption, not the voice.
    assert "PSTE-G1" in rules_for(
        'Check the docs that say "the file is rejected" here.', kind="instruction"
    ), "a quoted violation with no negation is still a finding"
    assert rules_for('Write "the linter rejects the file".') == set()

    # The opt-out directive.
    assert rules_for("This utilizes a robust approach. <!-- pste-lint: ignore -->",
                     level=3) == set()

    # PSTE-S1 / S2: code and quotes are exempt.
    fenced = "```\nutilize(); // spin up, e.g. don't\n```\nUse the cache."
    assert rules_for(fenced, level=3) == set(), "fenced code must be exempt"

    inline = "Call `utilize_cache()` to start the worker."
    assert "PSTE-V3" not in rules_for(inline, level=3), "inline code must be exempt"

    quoted = "> The file is rejected; it doesn't parse.\n\nI fixed the parser."
    assert rules_for(quoted, level=3) == set(), "blockquotes must be exempt"

    # Word count treats a code span as one word (PSTE-N7).
    assert count_words("Run `a-very-long-identifier-here` now.") == 3

    # PSTE-K1..K3: BCP 14 key words negate only with NOT, and bind a named actor.
    # Every BCP 14 key word is covered, in both the modal and the adjectival shape.
    BAD_FORMS = [
        # A key word negated by something other than NOT.
        ("A writer MUST never use a semicolon.", "PSTE-K1"),
        ("A writer MUST NEVER use a semicolon.", "PSTE-K1"),
        ("A writer MUST not use a semicolon.", "PSTE-K1"),      # lowercase not
        ("A writer MUST avoid semicolons.", "PSTE-K1"),
        ("A writer MUST abstain from semicolons.", "PSTE-K1"),
        ("A writer SHOULD rarely use a semicolon.", "PSTE-K1"),
        ("A writer SHALL refrain from semicolons.", "PSTE-K1"),
        ("A writer MAY no longer use a semicolon.", "PSTE-K1"),
        ("A writer SHOULD seldom use a semicolon.", "PSTE-K1"),
        # BCP 14 lists no MAY NOT, and the form is ambiguous.
        ("A writer MAY NOT use a semicolon.", "PSTE-K1"),
        # A negated subject in front of a key word.
        ("Nobody MUST present a score as evidence.", "PSTE-K1"),
        ("No writer MUST use a semicolon.", "PSTE-K1"),
        ("Neither writer SHALL use a semicolon.", "PSTE-K1"),
        ("None of the tools SHOULD report a score.", "PSTE-K1"),
        # An adjectival key word negated with NOT.
        ("A writer is NOT REQUIRED to use a semicolon.", "PSTE-K1"),
        ("A heading is NOT RECOMMENDED for a short note.", "PSTE-K1"),
        # A key word in the passive voice, which names no actor.
        ("Every number MUST be kept by the writer.", "PSTE-K2"),
        ("Every number MUST NOT be removed.", "PSTE-K2"),
        ("Every number SHALL be kept.", "PSTE-K2"),
        ("Every number SHALL NOT be removed.", "PSTE-K2"),
        ("Every number SHOULD be kept.", "PSTE-K2"),
        ("Every number SHOULD NOT be removed.", "PSTE-K2"),
        ("A code span MAY be used for an identifier.", "PSTE-K2"),
        ("A warning MUST NOT be subject to the limit.", "PSTE-K2"),
        # An adjectival key word with no actor.
        ("The actor is REQUIRED to be named.", "PSTE-K2"),
        ("A short sentence is RECOMMENDED.", "PSTE-K2"),
        ("It is REQUIRED that a writer names the actor.", "PSTE-K2"),
        ("A heading is OPTIONAL.", "PSTE-K2"),
    ]
    for text_, rule in BAD_FORMS:
        assert rule in rules_for(text_), f"{rule} missed: {text_!r}"

    GOOD_FORMS = [
        "A writer MUST NOT use a semicolon.",
        "A writer MUST keep every number.",
        "A writer SHOULD NOT use a semicolon.",
        "A writer SHOULD keep the sentence short.",
        "A writer SHALL NOT remove a fact.",
        "A writer SHALL keep every unit.",
        "A writer MAY use a code span.",
        # A permission to omit or to avoid is valid English, not a
        # negated key word.
        "A writer MAY omit the heading.",
        "A writer MAY avoid the semicolon.",
        "A tool MUST report the level that it checked.",
        # Ordinary prose that uses no key word is untouched.
        "The build must not fail without a reason.",
        "This is not required for the build.",
        "The heading is optional here.",
    ]
    for text_ in GOOD_FORMS:
        bad = [r for r in rules_for(text_) if r.startswith("PSTE-K")]
        assert not bad, f"false positive {bad} on: {text_!r}"

    # A finding carries a position that points at the offending token.
    # PSTE-K1: a prohibition must use the negative key word, and must not hide in
    # the predicate. "MUST write no more than 20 words" forbids something, so it
    # reads as an obligation to act and the reader has to translate it.
    for bad in (
        "A writer MUST write no more than 20 words.",
        "A writer SHOULD write no more than six sentences.",
    ):
        assert [
            f for f in check_text(bad, 2, vocab)["findings"] if f["rule"] == "PSTE-K1"
        ], bad
    for good in (
        "A writer MUST NOT write more than 20 words.",
        # `only` bounds a set. It is a positive requirement, and it is correct.
        "A writer MUST use only these verb forms.",
    ):
        assert not [
            f for f in check_text(good, 2, vocab)["findings"] if f["rule"] == "PSTE-K1"
        ], good

    # PSTE-N5: a past participle at the START of a run is an adjective, and opens
    # a noun chain. The same word later is a verb, and ends one. Position is the
    # only thing that separates them without a part of speech tagger.
    assert [
        f for f in check_text("the failed database connection retry", 2, vocab)["findings"]
        if f["rule"] == "PSTE-N5"
    ], "an adjectival participle must not hide a chain"
    for verb in ("the file failed the check", "the parser used the cache"):
        assert not [
            f for f in check_text(verb, 2, vocab)["findings"] if f["rule"] == "PSTE-N5"
        ], verb

    # PSTE-G11 and PSTE-G12: adjective count and order.
    #
    # These check only the words in ADJECTIVE_ORDER, because the checker has no
    # part of speech tagger and most English words change class with context.
    # "backup" is a noun in "restore the backup" and an adjective in "the backup
    # file", so a rule that guessed would report findings against correct text.
    order = [
        f["rule"] for f in check_text("the legacy small database", 2, vocab)["findings"]
    ]
    assert "PSTE-G12" in order, order
    assert "PSTE-G12" not in [
        f["rule"] for f in check_text("the small legacy database", 2, vocab)["findings"]
    ]

    many = check_text("a small round red plastic button", 2, vocab)["findings"]
    assert "PSTE-G11" in [f["rule"] for f in many], many

    # Two adjectives are allowed when the order is right.
    assert not [
        f
        for f in check_text("a new backup file", 2, vocab)["findings"]
        if f["rule"] in ("PSTE-G11", "PSTE-G12")
    ]

    # THE SAME WORDS AS NOUNS MUST NOT FIRE. This is the failure that would make
    # the rule worse than useless, because it reports against correct text.
    for clean in (
        "Restore the backup. Test the result.",
        "The test is green. The build is current.",
        "Run the test, then check the production log.",
        "A binary is a physical artefact.",
    ):
        got = [
            f
            for f in check_text(clean, 2, vocab)["findings"]
            if f["rule"] in ("PSTE-G11", "PSTE-G12")
        ]
        assert not got, (clean, got)

    # Two adjectives of one category have no order between them.
    assert not [
        f
        for f in check_text("the current legacy system", 2, vocab)["findings"]
        if f["rule"] == "PSTE-G12"
    ]

    # Every category in the table must have a name, or a message reads "None".
    for rank in set(ADJECTIVE_ORDER.values()):
        assert rank in ADJECTIVE_CATEGORY, rank

    r = check_text("The parser is robust.", 2, vocab)["findings"]
    assert r[0]["line"] == 1, r
    assert r[0]["column"] == 15, r  # "The parser is " is 14 characters
    assert "The parser is robust."[r[0]["column"] - 1 :].startswith("robust"), r
    multi = check_text("First line here.\n\nThe parser is robust.", 2, vocab)
    assert multi["findings"][0]["line"] == 3, multi["findings"]

    # PSTE-C8: the report gives a verdict, never a score, and a failure names
    # every offender so that a writer can correct it.
    clean = check_text("The linter reads the file.", 2, vocab)
    assert format_table("f.md", clean, False) == "f.md: PASS"

    # An instruction, so PSTE-G1 applies: PSTE-G2 permits the passive in a
    # description, and this test is about the report and not about the voice.
    dirty = check_text(
        "Check that the file is rejected; it doesn't parse.", 2, vocab,
        kind="instruction",
    )
    out = format_table("f.md", dirty, False)
    assert out.startswith("f.md: FAIL"), out
    assert "PSTE-G1" in out and "PSTE-X1" in out, "a failure must name each offender"
    for token in ("/100w", "findings", "score"):
        assert token not in out, f"the report must not present a count: {token!r}"

    # The disclaimer must name what a conformance result cannot support.
    for phrase in ("not quality", "readability"):
        assert phrase in DISCLAIMER.lower(), DISCLAIMER

    # PSTE-S4: an inflected identifier, not a bare one.
    assert "PSTE-S4" in rules_for("We are getUsering the record.")
    assert "PSTE-S4" in rules_for("The value was snake_cased before it was sent.")
    assert "PSTE-S4" not in rules_for("We call getUser to fetch the record.")
    assert "PSTE-S4" not in rules_for("The `getUsering` call is fenced.", level=3)
    # A plural-noun identifier is not an inflected verb. Cannot be told apart from
    # a real verb inflection without part-of-speech knowledge, so `s` alone is not
    # matched (see INFLECTION_RE).
    assert "PSTE-S4" not in rules_for("The mempoolItems list grew during the test.")
    assert "PSTE-S4" not in rules_for("The chia_rs crate exposes the function.")

    # PSTE-P1: a pre-filter for the easy non-imperative openers only.
    assert "PSTE-P1" in rules_for("You should run the tests.")
    assert "PSTE-P1" in rules_for("Please run the tests.")
    assert "PSTE-P1" not in rules_for("Run the tests.")
    # An opener starts a clause, and PSTE-X4 does not exempt what a parenthesis
    # holds. The rules apply inside one as they do outside.
    assert "PSTE-P1" in rules_for("Restart it (you should wait first).")
    assert "PSTE-P1" in rules_for("Restart it, and please note the log.")
    # "You can" states that something is possible. A command says the reader must
    # do it, so the rewrite would change the sentence. PSTE-A1 defeats P1 here.
    assert "PSTE-P1" not in rules_for("You can tune the interval.")
    # A description that quotes the words is not an instruction.
    assert "PSTE-P1" not in rules_for("The log shows what you should expect.")
    # The passive form is PSTE-G1's job, not this pre-filter's; it must not double
    # report the same sentence under both rules.
    passive_instr = rules_for("The tests should be run.", kind="instruction")
    assert "PSTE-P1" not in passive_instr, passive_instr

    # PSTE-G10: a gendered pronoun, reported at SHOULD because a word match cannot
    # tell an unknown-pronoun person from a quotation or a named person whose
    # pronouns are known.
    assert "PSTE-G10" in rules_for("Ask the user for his password.")
    assert "PSTE-G10" not in rules_for("Ask the user for their password.")
    g10 = [f for f in check_text("Ask the user for his password.", 2, vocab)["findings"]
          if f["rule"] == "PSTE-G10"]
    assert g10 and g10[0]["severity"] == "SHOULD", g10

    # PSTE-V7: American English spelling, sourced from spec/wordlist.yaml like V8.
    assert "PSTE-V7" in rules_for("The team organised the release.")
    assert "PSTE-V7" not in rules_for("The team organized the release.")
    assert "PSTE-V7" in rules_for("Read the licence before you deploy.")
    assert "PSTE-V7" not in rules_for("Read the license before you deploy.")
    assert "PSTE-V7" in rules_for("The build travelled through three stages.")
    assert "PSTE-V7" not in rules_for("The build traveled through three stages.")

    # ARBITRATED FINDINGS. N5/G7/G11/G12 are marked so a caller can route them to
    # the judge instead of a verdict; every other rule this checker can emit is
    # countable and goes straight to a verdict.
    arbitrated_hit = check_text("Perform an analysis of the log file.", 2, vocab)["findings"]
    assert [f["arbitrated"] for f in arbitrated_hit if f["rule"] == "PSTE-G7"] == [True]
    countable_hit = check_text("The build failed; the log shows why.", 2, vocab)["findings"]
    assert [f["arbitrated"] for f in countable_hit if f["rule"] == "PSTE-X1"] == [False]
    assert ARBITRATED_RULES == {"PSTE-N5", "PSTE-G7", "PSTE-G11", "PSTE-G12"}
    # Every ARBITRATED rule must have a severity, same as any other rule ID.
    for rule in ARBITRATED_RULES:
        assert rule in RULE_SEVERITY, rule

    # RFC-2119 severity: a known MUST rule and the one SHOULD rule the checker
    # emits (PSTE-X5) each carry the right severity, and every rule ID the
    # checker can emit over the eval corpus resolves to one.
    sev_check = check_text(
        "Check that the file is rejected — it does not parse.", 2, vocab,
        kind="instruction",
    )["findings"]
    by_rule = {f["rule"]: f["severity"] for f in sev_check}
    assert by_rule.get("PSTE-G1") == "MUST", by_rule
    assert by_rule.get("PSTE-X5") == "SHOULD", by_rule

    _corpus_dir = os.path.join(os.path.dirname(SPEC_DIR), "evals")
    for _root, _dirs, _files in os.walk(_corpus_dir):
        for _fn in _files:
            if not _fn.endswith(".md"):
                continue
            with open(os.path.join(_root, _fn), encoding="utf-8") as fh:
                _text = fh.read()
            for _f in check_text(_text, 2, vocab)["findings"]:
                assert _f["rule"] in RULE_SEVERITY, f"unmapped rule: {_f['rule']}"
                assert _f["severity"] in ("MUST", "SHOULD"), _f
                # spec/PSTE-1.md §15. A missing weight is a bug in the table, the
                # same way a missing severity is a bug in RULE_SEVERITY above.
                assert isinstance(_f["weight"], float), _f

    # spec/PSTE-1.md §15.6: the weight table and spec/rule_weights.csv MUST agree.
    # This file stays dependency-free (see the AST check below), so it cannot
    # import lib/build_appendix.py's table parser here. It re-reads the §15.5
    # table with the same small regex instead, and compares rule and weight
    # against the generated CSV, so a hand edit to one side without the other
    # fails here instead of drifting silently.
    _weight_row_re = re.compile(
        r"^\|\s*(PSTE-[A-Z0-9.]+)\s*\|\s*([0-9.]+|N/A)\s*\|"
    )
    _table_weights = {}
    _in_table = False
    with open(os.path.join(SPEC_DIR, "PSTE-1.md"), encoding="utf-8") as fh:
        for _line in fh:
            _stripped = _line.strip()
            if _stripped == "### 15.5 The weight table":
                _in_table = True
                continue
            if _in_table and _stripped.startswith("### "):
                break
            if not _in_table:
                continue
            _m = _weight_row_re.match(_stripped)
            if _m:
                _table_weights[_m.group(1)] = _m.group(2)
    assert _table_weights, "§15.5 weight table not found in spec/PSTE-1.md"

    _csv_weights_raw = {}
    with open(os.path.join(SPEC_DIR, "rule_weights.csv"),
              newline="", encoding="utf-8") as fh:
        for _row in csv.DictReader(fh):
            _csv_weights_raw[_row["rule"]] = _row["weight"]
    assert _table_weights == _csv_weights_raw, (
        "spec/PSTE-1.md §15.5 and spec/rule_weights.csv disagree; "
        "run: python3 lib/build_appendix.py"
    )

    # Every rule this checker can emit resolves to a weight, and accuracy (1.0)
    # outweighs punctuation (0.1), the ordering PSTE-A1 states in words.
    _weights = load_weights()
    for _rule in RULE_SEVERITY:
        assert _rule in _weights, f"no weight for {_rule!r}"
    assert _weights["PSTE-A1"] > _weights["PSTE-X1"], (
        "PSTE-A1 (accuracy) must outweigh PSTE-X1 (punctuation)"
    )
    assert _weights["PSTE-A1"] == 1.0, _weights["PSTE-A1"]

    # The distributed checker must import nothing outside the standard library. A
    # consumer copies one file and runs it. Verification tooling in evals/ may take
    # dependencies; this file may not. See evals/FUTURE-WORK.md.
    import ast as _ast

    _self = os.path.abspath(__file__)
    if os.path.exists(_self) and EMBEDDED_VOCAB is None:
        with open(_self, encoding="utf-8") as fh:
            _tree = _ast.parse(fh.read())
        _mods = {
            (n.module or "").split(".")[0]
            for n in _ast.walk(_tree)
            if isinstance(n, _ast.ImportFrom)
        }
        _mods |= {
            a.name.split(".")[0]
            for n in _ast.walk(_tree)
            if isinstance(n, _ast.Import)
            for a in n.names
        }
        _external = sorted(
            m for m in _mods if m and m not in sys.stdlib_module_names
        )
        assert not _external, (
            f"the distributed checker must stay dependency-free, found: {_external}"
        )

    print("self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
