#!/usr/bin/env python3
"""Build the GitHub Pages site in docs/: the eval index, and the corpus list.

    python3 evals/pages.py             # write docs/examples.html, docs/results/
    python3 evals/pages.py --self-test

`evals/results/` fills up one pair of files per run: a JSON record and the HTML
page `report.py` built from it. Nothing links them together for a browser. A
person who wants to compare two runs has to clone the repository and open files
by hand, because the published tree has no list.

A hand-written list goes stale the moment somebody runs the eval again, and
nobody remembers to update a page that is not the thing they ran. So this reads
`evals/results/*.json` itself, the same files `provenance.py` already treats as
the source of truth, and writes a fresh index every time. There is no other
input: a run that never happened cannot appear, and a run that did happen
cannot be missed.

The same rule covers the corpus list: `docs/examples.html` reads
`evals/corpus/MANIFEST.yaml` through `corpus.load()`, the same loader
`run.py` trusts, rather than a copy of the manifest's data typed by hand.

WHAT THIS IS NOT

This is not a second conformance table. Pick the fields a reader needs to
CHOOSE a run to open — date, commit, document count, arms, models — and
link to the pages `report.py` already built. The findings themselves stay
inside those pages, where `pste_lint.py` computed them. See report.py's
DISCLAIMER for why: a conformance count is not a measure of quality, and a
list of runs must not read as a leaderboard either.

HOW docs/ GETS BUILT

`evals/results/` is where a run WRITES its record — `provenance.py` reads it,
and a run in progress appends to it. It must never become a build output, or a
build would delete a run nobody has copied yet. So `docs/results/` is a COPY,
made fresh on every call to `sync_results_dir()`, and `evals/results/` itself
is never touched by this script.
"""

import argparse
import glob
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "evals", "results")
DOCS_DIR = os.path.join(ROOT, "docs")
DOCS_RESULTS_DIR = os.path.join(DOCS_DIR, "results")
SPEC_DIR = os.path.join(ROOT, "spec")
SPEC_MD = os.path.join(SPEC_DIR, "PSTE-1.md")
# PSTE has one level now. report.py still writes the page under the old
# "-level3.html" name — the same suffix the two-level tool used for its
# stricter page — so an existing results directory needs no file renamed.
PAGE_SUFFIX = "-level3.html"
sys.path.insert(0, os.path.join(ROOT, "evals"))

import corpus  # noqa: E402
import provenance  # noqa: E402

DISCLAIMER = (
    "This is a list of conformance runs, not a leaderboard. A conformance "
    "result is not a measure of quality. Nobody has yet run a reading trial "
    "with people. See evals/FUTURE-WORK.md."
)


def load_runs(directory=RESULTS_DIR):
    """Read every result JSON, and pair it with its report page, when one exists.

    Sorted newest first, because a reader opens this page to find the LATEST
    run almost every time. `find_results` (provenance.py) sorts oldest first
    for a different reason — stable ordering for `resolve()` — so this reverses
    rather than duplicating that function's sort key.

    A report page is written as `-level3.html`, the same name the old two-level
    tool used for its stricter page (see PAGE_SUFFIX). An older result directory
    may also carry a `-level2.html` beside it; that page is ignored here.
    """
    runs = []
    for path in reversed(provenance.find_results(directory)):
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        page = os.path.join(directory, f"{name}{PAGE_SUFFIX}")
        git = data.get("git") or {}
        models = data.get("models") or None  # absent on a result older than this field
        runs.append(
            {
                "file": os.path.basename(path),
                "date": (git.get("committed") or "")[:10],
                "commit": git.get("short", ""),
                "branch": git.get("branch", ""),
                "documents": data.get("document_count", len(data.get("results", {}))),
                "arms": data.get("arms", []),
                "models": models,
                "has_page": os.path.exists(page),
            }
        )
    return runs


def render(runs):
    rows = []
    for run in runs:
        if run["has_page"]:
            page_name = run["file"].replace(".json", PAGE_SUFFIX)
            links = f'<a href="{html.escape(page_name)}">report</a>'
        else:
            links = '<span class="missing">no page built</span>'
        if run["models"]:
            gen = html.escape(run["models"].get("generation") or "?")
            judge = html.escape(run["models"].get("judging") or "?")
            models_cell = f"gen {gen}, judge {judge}"
        else:
            models_cell = '<span class="missing">not recorded</span>'
        rows.append(
            "<tr>"
            f"<td>{html.escape(run['date'] or '?')}</td>"
            f"<td><code>{html.escape(run['commit'] or '?')}</code></td>"
            f"<td class=\"n\">{run['documents']}</td>"
            f"<td>{html.escape(', '.join(run['arms']) or '?')}</td>"
            f"<td>{models_cell}</td>"
            f"<td>{links}</td>"
            "</tr>"
        )

    return f"""<title>Eval runs</title>
<meta name="description" content="Every committed PSTE conformance run. Each row shows its commit, its arms, its models, and its pages.">
<link rel="stylesheet" href="../style.css">

<header class="site"><div class="brand"><a href="../index.html">PSTE</a></div><nav class="top"><a href="../examples.html">Examples</a> <a href="../spec.html">Specification</a> <a href="../validation.html">Validation</a> <a href="index.html">Eval runs</a> <a href="../index.html#get-pste">Get PSTE</a> <button id="theme-toggle" aria-label="Toggle light and dark theme"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1a7 7 0 1 0 0 14V1Z" fill="currentColor"/><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor"/></svg></button> <a href="https://github.com/hiniko/PSTE" aria-label="PSTE on GitHub"><svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.66 7.66 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg></a></nav></header> <!-- pste-lint: ignore -->

<div class="wrap">

<h1>PSTE eval runs</h1>

<p class="lede">This list holds every committed conformance run. Each row links to the pages that show a run's own documents and findings.</p>

<div class="honest">
<p>{html.escape(DISCLAIMER)}</p>
</div>

<p><a href="../eval-help.html">What weighted cost, clean-sentence rate, and the other terms mean</a>.</p>

<table class="numbers">
<thead><tr>
<th>Date</th><th>Commit</th><th class="n">Documents</th><th>Arms</th><th>Models</th><th>Pages</th>
</tr></thead> <!-- pste-lint: ignore -->
<tbody>
{"".join(rows) if rows else '<tr><td colspan="6">No results yet.</td></tr>'} <!-- pste-lint: ignore -->
</tbody>
</table>

</div>

<footer class="site">

<p>PSTE is MIT licensed. The corpus keeps the license of each source document. <a href="https://github.com/hiniko/PSTE">hiniko/PSTE on GitHub</a>.</p>

</footer>

<script src="../theme.js"></script>
"""


def corpus_run_map(directory=RESULTS_DIR):
    """For each corpus document id, which result files judged it and have a
    report page built.

    A manifest entry must link to a real page, not to a run that has no page
    built for it yet, so this checks for the same `PAGE_SUFFIX` file
    `load_runs` does rather than assuming every result has a page.
    """
    by_doc = {}
    for path in provenance.find_results(directory):
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not os.path.exists(os.path.join(directory, f"{name}{PAGE_SUFFIX}")):
            continue
        for doc_id in data.get("results", {}):
            by_doc.setdefault(doc_id, []).append(name)
    return by_doc


FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
HEADING_LINE_RE = re.compile(r"^\s{0,3}(#{1,6}\s|={3,}\s*$|-{3,}\s*$)")
# One line of nothing but heading decoration: RST underlines and overlines,
# and the setext forms. Matched per line, not per paragraph.
DECORATION_LINE_RE = re.compile(r"^[=\-~^\"'`*+#_]{3,}$")
EXCERPT_MIN_CHARS = 80
EXCERPT_MAX_CHARS = 320


def pick_excerpt(text, max_chars=EXCERPT_MAX_CHARS, min_chars=EXCERPT_MIN_CHARS):
    """The first paragraph of running prose in a document.

    Deterministic, so the same source always yields the same excerpt, and this
    page can regenerate after every eval run with no hand-picked text. Skips
    YAML front matter, headings, and heading-underline decoration, then takes
    the first paragraph long enough to show real sentences. A long paragraph
    is cut at a word boundary, with an ellipsis marking the cut.
    """
    body = FRONT_MATTER_RE.sub("", text, count=1)
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para or HEADING_LINE_RE.match(para):
            continue
        # An RST title in over-and-under form puts a decoration line on BOTH
        # sides of the text, so the whole block is one paragraph and the check
        # above does not catch it. Drop every decoration line, then judge what
        # is left: a title alone falls under min_chars and is skipped.
        kept = [ln for ln in para.splitlines()
                if not DECORATION_LINE_RE.match(ln.strip())]
        if not kept:
            continue
        para = "\n".join(kept)
        # A single line under the minimum is a heading or a label, not prose.
        line = " ".join(para.split())
        if len(line) < min_chars:
            continue
        if len(line) <= max_chars:
            return line
        cut = line.rfind(" ", 0, max_chars)
        cut = cut if cut > 0 else max_chars
        return line[:cut].rstrip(",;:") + "…"
    return ""


def latest_eval_documents(directory=RESULTS_DIR):
    """The per-document source/rewrite pairs from the newest full eval run.

    `provenance.resolve()` (no path argument) is the same "pick the newest
    result" logic the rest of this project uses, so this page and a report
    opened by hand never disagree about which run is current. A run that
    lands tomorrow needs no edit here: rerunning `pages.py` picks it up.
    """
    path = provenance.resolve(directory=directory)
    if not path:
        return None, {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return os.path.splitext(os.path.basename(path))[0], data.get("results", {})


def render_examples(documents, eval_results, run_name=None):
    """The examples page: the standard working, side by side, on every
    document in the corpus that the latest eval run judged.

    A reader switches document with a tab, so fourteen documents fit above
    the fold instead of one long scroll. Each panel still carries the
    document's title, source project, license, and attribution, because
    those are license obligations that travel with the text (MANIFEST.yaml,
    corpus.attribution()), not decoration this page may drop.
    """
    tabs, panels = [], []
    for i, doc in enumerate(documents):
        result = eval_results.get(doc["id"])
        active = " active" if i == 0 else ""
        tabs.append(
            f'<option value="panel-{i}"{" selected" if i == 0 else ""}>'
            f'{html.escape(doc["title"])}</option>'
        )

        url = doc["url"]
        source_link = (
            f'<a href="{html.escape(url)}">source</a>'
            if url.startswith("http")
            else html.escape(url)
        )
        meta = (
            '<div class="meta">'
            f'<span>{html.escape(doc["type"])}</span>'
            f'<span>{html.escape(doc["author"])}</span>'
            f'<span>{html.escape(doc["licence"])}</span>'
            f"<span>{source_link}</span>"
            "</div>"
        )
        attribution_html = ""
        note = corpus.attribution(doc)
        if note:
            attribution_html = f'<p class="attribution">{html.escape(note)}</p>'

        if result:
            before = html.escape(pick_excerpt(result["source"]))
            after = html.escape(pick_excerpt(result["outputs"]["pste_fixed"]))
            compare = (
                '<div class="compare">'
                f'<div class="col before"><div class="label">Before</div>'
                f'<div class="text">{before}</div></div>'
                f'<div class="col after"><div class="label">After</div>'
                f'<div class="text">{after}</div></div>'
                "</div>"
            )
        else:
            compare = '<p class="missing">Not judged in a committed run yet.</p>'

        panels.append(
            f'<div class="panel" id="panel-{i}"'
            f'{"" if i == 0 else " hidden"}>'
            f'<h2>&ldquo;{html.escape(doc["title"])}&rdquo;</h2>'
            f"{meta}"
            f"{compare}"
            f"{attribution_html}"
            "</div> <!-- pste-lint: ignore -->"
        )

    run_note = (
        f'<p class="lede">The excerpts below come from <code>{html.escape(run_name)}</code>, '
        "the newest full-corpus eval run. The first long paragraph of each document "
        "stands beside the same paragraph after the skill and a fix pass rewrote it.</p>"
        if run_name
        else '<p class="lede">No eval run has judged the corpus yet.</p>'
    )

    return f"""<title>Examples</title>
<meta name="description" content="The PSTE skill working on 13 documents, source beside rewrite.">
<link rel="stylesheet" href="style.css">

<header class="site"><div class="brand"><a href="index.html">PSTE</a></div><nav class="top"><a href="examples.html">Examples</a> <a href="spec.html">Specification</a> <a href="validation.html">Validation</a> <a href="results/index.html">Eval runs</a> <a href="index.html#get-pste">Get PSTE</a> <button id="theme-toggle" aria-label="Toggle light and dark theme"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1a7 7 0 1 0 0 14V1Z" fill="currentColor"/><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor"/></svg></button> <a href="https://github.com/hiniko/PSTE" aria-label="PSTE on GitHub"><svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.66 7.66 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg></a></nav></header> <!-- pste-lint: ignore -->

<div class="wrap">

<h1>The corpus, before and after</h1>

{run_note}

<div class="switcher"><label for="doc-select">Document</label><select id="doc-select">{"".join(tabs)}</select></div> <!-- pste-lint: ignore -->

{chr(10).join(panels)}

</div>

<footer class="site">

<p>PSTE is MIT licensed. The corpus keeps the license of each source document. <a href="https://github.com/hiniko/PSTE">hiniko/PSTE on GitHub</a>.</p>

</footer>

<script src="theme.js"></script>
<script src="switcher.js"></script>
"""


# ---------------------------------------------------------------------------
# spec.html: PSTE-1.md rendered as a site page.
#
# spec/PSTE-1.md stays the one normative document a person edits. This is a
# build product, the same relationship lib/build_appendix.py has to
# spec/wordlist.yaml: never hand-edit the HTML, rerun this script instead.
#
# The source has a fixed, small shape (headings, paragraphs, tables, lists, a
# definition list in §3, blockquotes, bold/italic/code/links, and a handful of
# `<!-- pste-lint: ignore -->` markers for the checker that runs over the
# markdown itself). That shape needs no general markdown library, and every
# tool in this repository already avoids adding a dependency for a parser it
# can write in a page. There are no code fences in this document.
# ---------------------------------------------------------------------------

RULE_ID_RE = re.compile(r"PSTE-[A-Z][0-9]+(?:\.[0-9]+)?")
# A rule's defining paragraph starts with its bold identifier, either
# "**PSTE-N1**: text" or, in §14's recommendations, "**PSTE-R1: Title.** text".
RULE_HEAD_RE = re.compile(r"^\*\*(PSTE-[A-Z][0-9]+(?:\.[0-9]+)?)\b")
LINT_COMMENT_RE = re.compile(r"\s*<!--\s*pste-lint:\s*ignore\s*-->")
INLINE_CODE_MD_RE = re.compile(r"`([^`]+)`")
BOLD_MD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_MD_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_MD_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
GITHUB_SPEC_BASE = "https://github.com/hiniko/PSTE/blob/main/spec/"


def _slugify(heading):
    """GitHub's heading-anchor algorithm: lowercase, drop punctuation, spaces to
    hyphens. Close enough for this document's headings (no repeats, no unicode)."""
    slug = re.sub(r"[^\w\s-]", "", heading.lower()).strip()
    return re.sub(r"[\s]+", "-", slug)


AUTOLINK_MD_RE = re.compile(r"<(https?://[^>\s]+)>")
# A reference tag, as RFCs write one: [RFC2119], [CHERVAK]. The entry for it
# sits in the references section, so the tag links there. An entry's own line
# starts with its tag and must not link to itself.
REFERENCE_TAG_RE = re.compile(r"\[([A-Z][A-Z0-9]{2,})\]")


def _md_inline(text, rule_id=None):
    """Inline markdown -> HTML: code, bold, italic, links, then escape the rest.

    Order matters: pull out code spans first (their contents must not become
    bold/italic/linked), escape everything that is left, then re-insert the
    formatted pieces as raw HTML. `rule_id`, when given, links a bare mention
    of a different rule ID to its own anchor on this page, so cross-references
    inside the spec's own prose become deep links too.
    """
    codes = []

    def _stash_code(m):
        codes.append(html.escape(m.group(1)))
        return f"\x00CODE{len(codes) - 1}\x00"

    text = INLINE_CODE_MD_RE.sub(_stash_code, text)
    # A bare <https://example.com> is markdown's own autolink, and the
    # references section uses it. Stash it beside the code spans so the
    # escape pass below cannot turn it into &lt;https://…&gt;.
    def _stash_autolink(m):
        url = html.escape(m.group(1))
        codes.append(f'<a href="{url}">{url}</a>')
        return f"\x00CODE{len(codes) - 1}\x00"

    text = AUTOLINK_MD_RE.sub(_stash_autolink, text)

    def _stash_reference(m):
        tag = html.escape(m.group(1))
        codes.append(f'<a href="#17-references">[{tag}]</a>')
        return f"\x00CODE{len(codes) - 1}\x00"

    if not text.lstrip().startswith("["):
        text = REFERENCE_TAG_RE.sub(_stash_reference, text)
    # A pste-lint marker in the source stays a REAL trailing HTML comment
    # here too, not stripped text: pste_lint.py's IGNORE_RE blanks a whole
    # line that contains the literal string, the same exemption the source
    # .md relies on for a line it marks as a counter-example. Stripping it
    # would either leak escaped comment syntax as visible text, or lose the
    # exemption and turn a deliberately-bad quoted example into a finding.
    has_ignore = bool(LINT_COMMENT_RE.search(text))
    text = LINT_COMMENT_RE.sub("", text)

    links = []

    def _stash_link(m):
        label, target = m.group(1), m.group(2)
        if target.startswith("http"):
            href = target
        elif target.endswith(".md") or "/" in target:
            href = GITHUB_SPEC_BASE + target
        else:
            href = target
        links.append(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')
        return f"\x00LINK{len(links) - 1}\x00"

    text = LINK_MD_RE.sub(_stash_link, text)

    # quote=False: a literal " in text content is safe HTML (escaping matters
    # only inside an attribute value), and pste_lint.py's counter-example
    # detector (NEGATION_BEFORE_RE + QUOTED_SPAN_RE) matches a literal quote
    # mark. An escaped &quot; would defeat that detector and turn every quoted
    # "do not write this" example in the spec into a false finding.
    text = html.escape(text, quote=False)
    text = BOLD_MD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = ITALIC_MD_RE.sub(lambda m: f"<em>{m.group(1)}</em>", text)

    def _link_rule_ids(m):
        rid = m.group(0)
        if rule_id and rid == rule_id:
            return rid  # do not link a rule to itself
        return f'<a class="rule" href="#{rid}">{rid}</a>'

    text = RULE_ID_RE.sub(_link_rule_ids, text)

    for i, code in enumerate(codes):
        text = text.replace(f"\x00CODE{i}\x00", f"<code>{code}</code>")
    for i, link in enumerate(links):
        text = text.replace(f"\x00LINK{i}\x00", link)
    if has_ignore:
        text += " <!-- pste-lint: ignore -->"
    return text


def _md_table(rows):
    """A GitHub-flavoured markdown table (a header row, a `---` divider row,
    then body rows) as an HTML table. Every cell runs through _md_inline.

    Rendered as one dense line, same as every other structural block this
    module writes (see docs/validation.html's `table.numbers`). A table cell
    is data, not prose (PSTE-S6 permits tables; the sentence and paragraph
    rules of §9-10 govern author prose). pste_lint.py has no notion of an HTML
    table, so a `pste-lint: ignore` marks the line exempt the same way the
    rest of this site's generated pages already do.
    """
    header = [c.strip() for c in rows[0].strip("|").split("|")]
    body_rows = [
        [c.strip() for c in r.strip("|").split("|")] for r in rows[2:]
    ]
    thead = "".join(f"<th>{_md_inline(c)}</th>" for c in header)
    tbody = "".join(
        "<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in cells) + "</tr>"
        for cells in body_rows
    )
    return (
        f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"
        " <!-- pste-lint: ignore -->"
    )


def render_spec_html(markdown_text):
    """PSTE-1.md as page content: the same fragment shape render()/render_examples()
    return (a <title>, then body content, no <html>/<head> wrapper).

    Every rule's defining paragraph (`**PSTE-XX**: ...`) gets `id="PSTE-XX"`, so
    a citation elsewhere in the site can deep-link to `spec.html#PSTE-XX`.
    """
    lines = markdown_text.splitlines()
    blocks, i, n = [], 0, len(lines)
    seen_ids = set()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            blocks.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            slug = _slugify(text)
            blocks.append(f'<h{level} id="{slug}">{_md_inline(text)}</h{level}>')
            i += 1
            continue

        if stripped.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            blocks.append(_md_table(lines[i:j]))
            i = j
            continue

        if stripped.startswith(">"):
            # A blank ">" line is a paragraph break inside the quote (§6's
            # PSTE-L5 example, §7's term-list note), not the end of running
            # prose, so it starts a new <p> rather than joining onto one giant
            # paragraph that would never satisfy PSTE-D2's six-sentence limit.
            j, paras, cur = i, [], []
            while j < n and lines[j].strip().startswith(">"):
                content = re.sub(r"^\s*>\s?", "", lines[j]).strip()
                if content:
                    cur.append(content)
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
                j += 1
            if cur:
                paras.append(" ".join(cur))
            # Each <p> goes on its own line, with a blank line between: the
            # checker finds a paragraph break by a blank line, not an HTML
            # tag, so a two-paragraph note rendered on one dense line would
            # read as one paragraph and could trip PSTE-D2 on the combined
            # sentence count.
            ps = "\n\n".join(f"<p>{_md_inline(p)}</p>" for p in paras)
            blocks.append(f"<blockquote>\n\n{ps}\n\n</blockquote>")
            i = j
            continue

        # A list is rendered as one dense line, with its own pste-lint marker,
        # same as _md_table: pste_lint.py exempts a markdown list line from
        # its sentence and paragraph counts (LIST_RE, used by split_sentences
        # AND by _join_wrapped, which otherwise re-joins any wrapped line
        # back onto the one above it regardless of the HTML tag on it). A
        # list item is PSTE-D3/D4 structure, not free-running prose, so this
        # is the same exemption _md_table already claims for a table row.
        if re.match(r"^[-*]\s+", stripped):
            j, items = i, []
            while j < n and (re.match(r"^[-*]\s+", lines[j].strip())
                              or (lines[j].startswith(("  ", "\t")) and lines[j].strip())):
                if re.match(r"^[-*]\s+", lines[j].strip()):
                    items.append(re.sub(r"^[-*]\s+", "", lines[j].strip()))
                else:
                    items[-1] += " " + lines[j].strip()  # wrapped continuation line
                j += 1
            lis = "".join(f"<li>{_md_inline(it)}</li>" for it in items)
            blocks.append(f"<ul>{lis}</ul> <!-- pste-lint: ignore -->")
            i = j
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            j, items = i, []
            while j < n and (re.match(r"^\d+[.)]\s+", lines[j].strip())
                              or (lines[j].startswith(("  ", "\t")) and lines[j].strip())):
                if re.match(r"^\d+[.)]\s+", lines[j].strip()):
                    items.append(re.sub(r"^\d+[.)]\s+", "", lines[j].strip()))
                else:
                    items[-1] += " " + lines[j].strip()  # wrapped continuation line
                j += 1
            lis = "".join(f"<li>{_md_inline(it)}</li>" for it in items)
            blocks.append(f"<ol>{lis}</ol> <!-- pste-lint: ignore -->")
            i = j
            continue

        # Definition list (§3: "**term**" then ": definition", the definition
        # possibly wrapped across indented continuation lines). A term's
        # definition is one short sentence or two of real prose, so unlike a
        # table or a plain list this is left subject to the checker, not
        # exempted.
        if re.match(r"^\*\*[^*]+\*\*\s*$", stripped) and i + 1 < n and \
                lines[i + 1].lstrip().startswith(":"):
            term = re.match(r"^\*\*([^*]+)\*\*\s*$", stripped).group(1)
            j, def_lines = i + 1, []
            while j < n and (lines[j].lstrip().startswith(":") or
                              (lines[j].strip() and lines[j].startswith(" ") and def_lines)):
                def_lines.append(re.sub(r"^\s*:\s?", "", lines[j]))
                j += 1
            definition = " ".join(l.strip() for l in def_lines)
            blocks.append(
                f"<dl><dt>{_md_inline(term)}</dt><dd>{_md_inline(definition)}</dd></dl>"
            )
            i = j
            continue

        # A paragraph: gather wrapped lines up to the next blank line or block.
        j, para_lines = i, []
        while j < n and lines[j].strip() and not (
            lines[j].strip().startswith(("#", "|", ">", "---"))
            or re.match(r"^[-*]\s+", lines[j].strip())
            or re.match(r"^\d+[.)]\s+", lines[j].strip())
        ):
            para_lines.append(lines[j].strip())
            j += 1
        para = " ".join(para_lines)

        rule_match = RULE_HEAD_RE.match(para)
        if rule_match:
            rid = rule_match.group(1)
            attr = ""
            if rid not in seen_ids:
                seen_ids.add(rid)
                attr = f' id="{rid}"'
            blocks.append(f"<p{attr}>{_md_inline(para, rule_id=rid)}</p>")
        else:
            blocks.append(f"<p>{_md_inline(para)}</p>")
        i = j

    return "\n\n".join(blocks)


def render_spec(markdown_text):
    """The full spec.html page: header, nav, the rendered spec, footer."""
    body = render_spec_html(markdown_text)
    return f"""<title>PSTE-1: the specification</title>
<meta name="description" content="PSTE-1, the full specification, rendered as a page: every rule, its identifier, and its weight.">
<link rel="stylesheet" href="style.css">

<header class="site"><div class="brand"><a href="index.html">PSTE</a></div><nav class="top"><a href="examples.html">Examples</a> <a href="spec.html">Specification</a> <a href="validation.html">Validation</a> <a href="results/index.html">Eval runs</a> <a href="index.html#get-pste">Get PSTE</a> <button id="theme-toggle" aria-label="Toggle light and dark theme"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1a7 7 0 1 0 0 14V1Z" fill="currentColor"/><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor"/></svg></button> <a href="https://github.com/hiniko/PSTE" aria-label="PSTE on GitHub"><svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.66 7.66 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg></a></nav></header> <!-- pste-lint: ignore -->

<div class="wrap spec">

<p class="lede">This page tracks the canonical specification, which lives at <a href="https://github.com/hiniko/PSTE/blob/main/spec/PSTE-1.md">spec/PSTE-1.md</a>. The short version is <a href="https://github.com/hiniko/PSTE/blob/main/spec/STANDARD.md">spec/STANDARD.md</a>.</p>

{body}

</div>

<footer class="site">

<p>PSTE is MIT licensed. The corpus keeps the license of each source document. <a href="https://github.com/hiniko/PSTE">hiniko/PSTE on GitHub</a>.</p>

</footer>

<script src="theme.js"></script>
"""


def sync_results_dir(src=RESULTS_DIR, dst=DOCS_RESULTS_DIR):
    """Copy every result JSON and HTML page into docs/, and nothing else.

    evals/results/ is where a run WRITES, so this only ever reads from it.
    dst is removed and rebuilt each time, so a page for a result that no
    longer exists (renamed, or deleted) cannot linger in the published copy.
    """
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst, exist_ok=True)
    copied = 0
    for pattern in ("*.json", "*.html"):
        for path in glob.glob(os.path.join(src, pattern)):
            if os.path.basename(path) == "index.html":
                continue  # rebuilt fresh below, not copied from evals/results/
            shutil.copy2(path, os.path.join(dst, os.path.basename(path)))
            copied += 1
    return copied


def self_test():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        # A run with every field, including the newer `models` key.
        full = {
            "git": {"short": "abc12345", "committed": "2026-09-11T10:00:00+01:00"},
            "document_count": 14,
            "arms": ["control", "pste"],
            "models": {"generation": "claude-sonnet-5", "judging": "claude-opus-5"},
            "results": {},
        }
        with open(os.path.join(tmp, "eval-2026-09-11-abc12345.json"), "w") as fh:
            json.dump(full, fh)
        # A pre-Task-L result directory carries both pages; only the level3
        # one is the report page now (PAGE_SUFFIX), and the level2 page must
        # not break anything just by sitting there.
        open(os.path.join(tmp, "eval-2026-09-11-abc12345-level2.html"), "w").close()
        open(os.path.join(tmp, "eval-2026-09-11-abc12345-level3.html"), "w").close()

        # An older run with no `models` key and no built page at all.
        old = {
            "git": {"short": "def45678", "committed": "2026-08-01T09:00:00+01:00"},
            "document_count": 2,
            "arms": ["control"],
            "results": {},
        }
        with open(os.path.join(tmp, "eval-2026-08-01-def45678.json"), "w") as fh:
            json.dump(old, fh)

        runs = load_runs(tmp)
        assert len(runs) == 2, runs
        # Newest first.
        assert runs[0]["commit"] == "abc12345", runs
        assert runs[1]["commit"] == "def45678", runs
        assert runs[0]["has_page"] is True, runs[0]
        assert runs[0]["models"]["generation"] == "claude-sonnet-5", runs[0]
        # The older result must not crash, and must not invent a model.
        assert runs[1]["models"] is None, runs[1]
        assert runs[1]["has_page"] is False, runs[1]

        page = render(runs)
        assert "abc12345" in page and "def45678" in page, page
        assert "claude-sonnet-5" in page, page
        assert "not recorded" in page, "an older result must say so, not guess"
        assert "no page built" in page, "a result with no page must say so"
        assert "eval-2026-09-11-abc12345-level3.html" in page, page
        assert "eval-2026-09-11-abc12345-level2.html" not in page, \
            "the level2 page must not be linked; level3 is the single report page"
        # Conformance is not a quality claim, and this page lists runs, not
        # scores, so the disclaimer must survive into the rendered HTML.
        assert "not a leaderboard" in page, page

        # Reader-facing text must never carry a raw "<" — everything that came
        # from a result file must go through html.escape before it reaches the
        # page (a commit or an arm name is free text, not a trusted constant).
        escaped = render([{
            "file": "x.json", "date": "2026-09-11", "commit": "<script>alert(1)</script>",
            "branch": "", "documents": 1, "arms": ["<x>"], "models": None, "has_page": False,
        }])
        assert "<script>alert" not in escaped, escaped
        assert "&lt;script&gt;" in escaped, escaped

        # corpus_run_map: only "abc12345" has a page, so only it must appear,
        # and only under the document ids its own results dict names.
        full["results"] = {"doc-a": {}, "doc-b": {}}
        old["results"] = {"doc-a": {}}
        with open(os.path.join(tmp, "eval-2026-09-11-abc12345.json"), "w") as fh:
            json.dump(full, fh)
        with open(os.path.join(tmp, "eval-2026-08-01-def45678.json"), "w") as fh:
            json.dump(old, fh)

        run_map = corpus_run_map(tmp)
        assert run_map["doc-a"] == ["eval-2026-09-11-abc12345"], run_map
        assert "doc-b" in run_map, run_map
        assert "def45678" not in json.dumps(run_map), "a run with no built page must be absent"

        eval_results = {
            "doc-a": {
                "source": "The queue doesn't retry a failed job, and it just drops the "
                           "message on the floor without telling anyone about it at all.",
                "outputs": {
                    "pste_fixed": "The queue does not retry a failed job. It drops the "
                                   "message. It does not tell anyone."
                },
            },
        }
        examples = render_examples(
            [
                {"id": "doc-a", "title": "<Escaped> Title", "type": "runbook",
                 "author": "Someone", "licence": "MIT", "url": "https://x.example",
                 "note": None},
                {"id": "doc-c", "title": "Never Judged", "type": "runbook",
                 "author": "Someone", "licence": "MIT", "url": "https://x.example",
                 "note": None},
                {"id": "doc-d", "title": "Synthetic", "type": "runbook",
                 "author": "Someone", "licence": "MIT",
                 "url": "generated by evals/corpus_generate.py --topics",
                 "note": None},
            ],
            eval_results,
            run_name="eval-2026-09-11-abc12345",
        )
        assert "&lt;Escaped&gt;" in examples and "<Escaped>" not in examples, examples
        assert "eval-2026-09-11-abc12345" in examples, examples
        assert "doesn&#x27;t retry" in examples or "doesn't retry" in examples, examples
        assert "does not retry a failed job" in examples, examples
        assert "Not judged in a committed run yet." in examples, \
            "doc-c has no eval result and must say so, not silently omit the panel"
        # A synthetic document's "url" names a generator, not a page, and
        # must never render as a broken link.
        assert '<a href="generated' not in examples, examples
        assert "generated by evals/corpus_generate.py --topics" in examples, examples
        # The switcher needs one option and one panel per document, and only
        # the first panel starts visible so a reader is never shown them all
        # at once. The page ships in that state, so it reads correctly before
        # switcher.js runs and with scripting off entirely.
        assert examples.count("<option ") == 3, examples
        assert examples.count('class="panel"') == 3, examples
        assert examples.count(" hidden>") == 2, \
            "only the first panel may lack the hidden attribute"
        # Every option must address a panel that exists, or the dropdown
        # selects nothing and the page goes blank.
        for i in range(3):
            assert f'<option value="panel-{i}"' in examples, examples
            assert f'id="panel-{i}"' in examples, examples
        assert examples.count(" selected>") == 1, \
            "exactly one option starts selected"

        # sync_results_dir: copies JSON and HTML, skips index.html, and clears
        # a stale file from a previous copy that no longer exists in the source.
        with tempfile.TemporaryDirectory() as dst_parent:
            dst = os.path.join(dst_parent, "results")
            os.makedirs(dst)
            with open(os.path.join(dst, "stale-run.json"), "w") as fh:
                fh.write("{}")
            open(os.path.join(tmp, "index.html"), "w").close()
            copied = sync_results_dir(tmp, dst)
            names = set(os.listdir(dst))
            assert "stale-run.json" not in names, "a removed run must not survive a resync"
            assert "index.html" not in names, "the index is rebuilt, never copied verbatim"
            assert "eval-2026-09-11-abc12345-level2.html" in names, names
            assert "eval-2026-09-11-abc12345.json" in names, names
            assert copied == len(names), (copied, names)

    # No results directory at all must not crash, only report nothing.
    with tempfile.TemporaryDirectory() as empty:
        assert load_runs(empty) == []
        assert "No results yet" in render([])
        assert latest_eval_documents(empty) == (None, {})

    # pick_excerpt: skip front matter, headings, and decoration; take the
    # first paragraph long enough to be real prose; cut a long one cleanly.
    assert pick_excerpt("--- \ntitle: x\n---\n\n# Heading\n\nShort.\n\n"
                         "This paragraph is long enough on its own to count as "
                         "running prose for the excerpt picker to select.") == (
        "This paragraph is long enough on its own to count as running prose "
        "for the excerpt picker to select."
    ), pick_excerpt("x")
    assert pick_excerpt("====\nTitle\n====\n\nThis paragraph is long enough on "
                         "its own to count as running prose for the picker.") == (
        "This paragraph is long enough on its own to count as running prose "
        "for the picker."
    )
    long_para = "word " * 100
    cut = pick_excerpt(long_para, max_chars=50, min_chars=10)
    assert cut.endswith("…"), cut
    assert len(cut) <= 51, cut
    assert pick_excerpt("") == ""
    assert pick_excerpt("# Only a heading\n\n---\n") == ""

    # render_spec_html: headings get a GitHub-style slug id, a rule's defining
    # paragraph gets id="PSTE-XX" so a citation can deep-link to it, a later
    # mention of the same or a different rule ID becomes a link, tables and
    # lists render, and a pste-lint HTML comment marker disappears rather
    # than leaking into the page as escaped text.
    sample_md = """## 8. Sentence rules

**PSTE-N1**: A writer MUST NOT write more than 20 words in an instruction.

**PSTE-N2**: A writer MUST NOT write more than 25 words in a description.

Write "A writer MUST NOT use a semicolon". Do not write "avoid semicolons". <!-- pste-lint: ignore -->

A sentence that breaks PSTE-N1 also risks PSTE-N2 in the same draft.

| Rule | Weight |
|---|---|
| PSTE-N1 | 0.5 |

- An approved word
- A term

> **Note.** This is a note.

**term**
: A definition of the term, on one line.
"""
    spec_page = render_spec_html(sample_md)
    assert '<h2 id="8-sentence-rules">' in spec_page, spec_page
    assert '<p id="PSTE-N1">' in spec_page, spec_page
    assert '<p id="PSTE-N2">' in spec_page, spec_page
    # A rule is not linked to itself inside its own defining paragraph.
    assert '<p id="PSTE-N1"><strong>PSTE-N1</strong>: A writer' in spec_page, spec_page
    # The later cross-reference paragraph links both rule IDs.
    assert '<a class="rule" href="#PSTE-N1">PSTE-N1</a>' in spec_page, spec_page
    assert '<a class="rule" href="#PSTE-N2">PSTE-N2</a>' in spec_page, spec_page
    # A pste-lint marker in the source survives as a REAL HTML comment (not
    # escaped text): it must never appear as visible reader-facing text like
    # "&lt;!-- pste-lint" would render as.
    assert "&lt;!--" not in spec_page, spec_page
    assert '<p>Write "A writer MUST NOT use a semicolon".' in spec_page, spec_page
    assert "pste-lint: ignore -->" in spec_page, spec_page
    # The table this module writes gets its OWN marker: pste_lint.py has no
    # notion of an HTML table, and without it a wide table reads as one
    # enormous run-on sentence or paragraph (PSTE-N2, PSTE-D2 both fire on
    # the raw markup). A table cell is data, not prose PSTE-S6 governs.
    assert "<table>" in spec_page and "<td>0.5</td>" in spec_page, spec_page
    assert "<table>" in spec_page and "pste-lint: ignore -->" in spec_page, spec_page
    assert "<li>An approved word</li>" in spec_page, spec_page
    assert "<blockquote>" in spec_page and "This is a note." in spec_page, spec_page
    assert "<dt>" in spec_page and "A definition of the term" in spec_page, spec_page

    # The full committed spec must render without crashing and must anchor
    # every rule identifier this document defines.
    with open(SPEC_MD, encoding="utf-8") as fh:
        full_spec_html = render_spec_html(fh.read())
    for rid in sorted(set(RULE_ID_RE.findall(open(SPEC_MD, encoding="utf-8").read()))):
        assert f'id="{rid}"' in full_spec_html, f"{rid} has no anchor on spec.html"

    print("pages self-test: all checks passed")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Build docs/: the eval index, the results copy, and the corpus list.",
    )
    ap.add_argument("--out", default=os.path.join(DOCS_RESULTS_DIR, "index.html"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    copied = sync_results_dir()
    runs = load_runs()
    page = render(runs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"copied {copied} result files to {DOCS_RESULTS_DIR}")
    print(f"wrote {args.out}  ({len(runs)} runs)")

    documents = corpus.load()
    run_name, eval_results = latest_eval_documents()
    examples_page = render_examples(documents, eval_results, run_name)
    examples_out = os.path.join(DOCS_DIR, "examples.html")
    with open(examples_out, "w", encoding="utf-8") as fh:
        fh.write(examples_page)
    print(f"wrote {examples_out}  ({len(documents)} documents, run {run_name})")

    with open(SPEC_MD, encoding="utf-8") as fh:
        spec_page = render_spec(fh.read())
    spec_out = os.path.join(DOCS_DIR, "spec.html")
    with open(spec_out, "w", encoding="utf-8") as fh:
        fh.write(spec_page)
    print(f"wrote {spec_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
