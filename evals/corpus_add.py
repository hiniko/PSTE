#!/usr/bin/env python3
"""Add a document to the corpus, and record where it came from.

    python3 evals/corpus_add.py \\
        --id runbook-postgres-failover \\
        --type runbook \\
        --title "Postgres failover procedure" \\
        --url https://raw.githubusercontent.com/example/repo/main/docs/failover.md \\
        --author "Example Project contributors" \\
        --licence Apache-2.0

This downloads the document, writes it to `evals/corpus/<id>.md`, and appends the
entry to `MANIFEST.yaml` with the sha256 and the word count filled in.

WHY A TOOL AND NOT A COPY AND PASTE

Three fields have to agree: the file on disk, its sha256, and its word count. A
person who types those by hand gets one wrong eventually, and the corpus check then
fails for a reason that has nothing to do with the document. This computes all three
from the bytes it downloaded.

It refuses a licence that this project may not redistribute or modify. That check
belongs here, at the moment the document arrives, and not later.

    --dry-run     fetch and report, write nothing
"""

import argparse
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import corpus  # noqa: E402

USER_AGENT = "pste-corpus-add/1 (+https://github.com/)"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    return raw.decode("utf-8")


def strip_site_machinery(text):
    """Remove the parts a site generator added, and keep the prose.

    USE THIS SPARINGLY. Real documentation carries markup, and a rewrite has to
    survive it: a rewrite that flattens a `{{< note >}}` or mangles a directive has
    failed at the job the skill claims to do. Stripping the markup hides that
    failure, because the eval never sees the markup at all.

    Strip only what would otherwise dominate the document, such as a front matter
    block of reviewer names. Keep the markup that a writer would meet.
    """
    removed = []

    # YAML front matter: reviewers, weight, and other build fields.
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            removed.append("front matter")
            text = text[end + 4 :]

    # Hugo section markers, and any line that is only a template call.
    for marker in ("<!-- overview -->", "<!-- body -->", "<!-- discussion -->"):
        if marker in text:
            removed.append(marker.strip("<!->" " "))
            text = text.replace(marker + "\n", "").replace(marker, "")

    lines, kept = text.splitlines(), []
    dropped_templates = 0
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"\{\{[<%].*[>%]\}\}", stripped):
            dropped_templates += 1
            continue
        # A heading that is only a template call, e.g. `## {{% heading "x" %}}`.
        if re.fullmatch(r"#+\s*\{\{[<%].*[>%]\}\}", stripped):
            dropped_templates += 1
            continue
        kept.append(line)
    if dropped_templates:
        removed.append(f"{dropped_templates} template calls")

    return "\n".join(kept).strip() + "\n", removed


def cut_to_sections(text, keep_from=None, keep_to=None):
    """Keep the run of sections between two headings.

    A long page holds several documents. Cutting on a heading keeps a whole section
    rather than a truncated one, so the excerpt reads as a document and not as a
    fragment that stops mid-thought.
    """
    lines = text.splitlines()
    # Match any heading level, so a page whose real sections are `###` can be cut
    # at the same place a reader would see the break. AsciiDoc writes `== Title`,
    # and several good source documents use it.
    starts = [
        i
        for i, line in enumerate(lines)
        if re.match(r"#{2,4} \S", line) or re.match(r"={2,4} \S", line)
    ]
    if not starts:
        return text, ""

    def find(name):
        for i in starts:
            if name.lower() in lines[i].lower():
                return i
        raise SystemExit(f"no section heading matches {name!r}")

    first = find(keep_from) if keep_from else 0
    if keep_to:
        last = find(keep_to)
    else:
        later = [i for i in starts if i > first]
        last = later[-1] if later else len(lines)

    cut = "\n".join(lines[first:last]).strip() + "\n"
    note = f"kept the sections from {lines[first].lstrip('#= ')!r}"
    if keep_to:
        note += f" up to {lines[last].lstrip('#= ')!r}"
    return cut, note


def entry_yaml(fields):
    """Render one manifest entry. The order matches the documented shape."""
    order = (
        "id",
        "type",
        "title",
        "url",
        "author",
        "licence",
        "retrieved",
        "sha256",
        "words",
        "excerpt",
    )
    lines = []
    for index, key in enumerate(order):
        value = fields[key]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int):
            rendered = str(value)
        elif key in ("title", "author") or " " in str(value):
            rendered = '"' + str(value).replace('"', "'") + '"'
        else:
            rendered = str(value)
        prefix = "  - " if index == 0 else "    "
        lines.append(f"{prefix}{key}: {rendered}")
    if fields.get("note"):
        lines.append(f'    note: "{fields["note"]}"')
    return "\n".join(lines)


def append_entry(manifest, text):
    """Add an entry to the manifest, whether or not it already holds one."""
    with open(manifest, encoding="utf-8") as fh:
        current = fh.read()

    if "documents: []" in current:
        current = current.replace("documents: []", "documents:")
    elif not re.search(r"^documents:\s*$", current, re.M):
        raise SystemExit(f"{manifest} has no `documents:` key")

    # Append after the last entry, not after the `documents:` key. The file ends
    # with a comment block describing the entry shape, and inserting at the key
    # would strand that block in the middle of the list.
    updated = current.rstrip("\n") + "\n" + text + "\n"

    # Read fully, then write. Opening for write truncates the file, so a read that
    # happens after the open returns nothing and the manifest is destroyed.
    with open(manifest, "w", encoding="utf-8") as fh:
        fh.write(updated)


def main():
    ap = argparse.ArgumentParser(
        description="Add a document to the corpus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # `--self-test` takes none of the other options, so it is checked before
    # argparse can reject a run that supplies only that flag.
    if "--self-test" in sys.argv:
        return self_test()

    ap.add_argument("--id", required=True)
    ap.add_argument("--type", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--licence", required=True)
    ap.add_argument("--retrieved", default=None, help="defaults to today")
    ap.add_argument("--excerpt", action="store_true")
    ap.add_argument("--note", default="")
    ap.add_argument(
        "--strip-machinery",
        action="store_true",
        help="remove front matter, build markers, and template calls",
    )
    ap.add_argument("--from-section", default=None, help="keep from this heading")
    ap.add_argument("--to-section", default=None, help="keep up to this heading")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.licence not in corpus.ALLOWED_LICENCES:
        print(
            f"refusing: {args.licence} does not permit redistribution and "
            f"modification.\nAllowed: {', '.join(sorted(corpus.ALLOWED_LICENCES))}",
            file=sys.stderr,
        )
        return 2

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.id):
        print("refusing: --id must be lower case, digits, and hyphens", file=sys.stderr)
        return 2

    path = os.path.join(corpus.CORPUS_DIR, f"{args.id}.md")
    if os.path.exists(path):
        print(f"refusing: {path} exists", file=sys.stderr)
        return 2

    try:
        body = fetch(args.url)
    except Exception as exc:  # noqa: BLE001 - report any fetch failure the same way
        print(f"could not fetch {args.url}: {exc}", file=sys.stderr)
        return 1

    notes = []
    if args.strip_machinery:
        body, removed = strip_site_machinery(body)
        if removed:
            notes.append("removed " + ", ".join(removed))
    if args.from_section or args.to_section:
        body, cut_note = cut_to_sections(body, args.from_section, args.to_section)
        if cut_note:
            notes.append(cut_note)

    is_excerpt = args.excerpt or bool(notes)
    note = args.note or "; ".join(notes)
    if is_excerpt and not note:
        print(
            "refusing: an excerpt must record what it cut. Pass --note.",
            file=sys.stderr,
        )
        return 2

    words = len(body.split())
    digest = corpus.hashlib.sha256(body.encode("utf-8")).hexdigest()

    print(f"{args.id}: {words} words, sha256 {digest[:12]}...")
    if words < 150:
        print(
            "  WARNING: under 150 words. A short document cannot show whether a "
            "rewrite dropped anything.",
            file=sys.stderr,
        )
    if words > 1500:
        print(
            "  WARNING: over 1500 words. Consider an excerpt, and record what it cut.",
            file=sys.stderr,
        )

    if args.dry_run:
        print("\n--dry-run: nothing written. The entry would be:\n")
        print(
            entry_yaml(
                {
                    "id": args.id,
                    "type": args.type,
                    "title": args.title,
                    "url": args.url,
                    "author": args.author,
                    "licence": args.licence,
                    "retrieved": args.retrieved or _today(),
                    "sha256": digest,
                    "words": words,
                    "excerpt": is_excerpt,
                    "note": note,
                }
            )
        )
        return 0

    os.makedirs(corpus.CORPUS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)

    append_entry(
        corpus.MANIFEST,
        entry_yaml(
            {
                "id": args.id,
                "type": args.type,
                "title": args.title,
                "url": args.url,
                "author": args.author,
                "licence": args.licence,
                "retrieved": args.retrieved or _today(),
                "sha256": digest,
                "words": words,
                "excerpt": is_excerpt,
                "note": note,
            }
        ),
    )

    problems = corpus.check()
    if problems:
        print("\nthe corpus check failed after the addition:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(f"wrote {path} and recorded it in the manifest")
    return 0


def _today():
    import datetime

    return datetime.date.today().isoformat()


def self_test():
    import tempfile

    fields = {
        "id": "runbook-x",
        "type": "runbook",
        "title": "A Title With Spaces",
        "url": "https://example.org/a.md",
        "author": "Someone",
        "licence": "Apache-2.0",
        "retrieved": "2026-08-03",
        "sha256": "0" * 64,
        "words": 300,
        "excerpt": False,
    }
    text = entry_yaml(fields)
    assert text.startswith("  - id: runbook-x"), text
    assert '    title: "A Title With Spaces"' in text, text
    assert "    words: 300" in text, text
    assert "    excerpt: false" in text, text

    # The rendered entry must survive a round trip through the manifest parser,
    # or the corpus check fails on a document that is actually correct.
    parsed = corpus._parse_manifest("documents:\n" + text)
    assert len(parsed) == 1, parsed
    for key in ("id", "type", "title", "url", "author", "licence", "sha256"):
        assert parsed[0][key] == fields[key], (key, parsed[0].get(key))
    assert parsed[0]["words"] == 300 and parsed[0]["excerpt"] is False, parsed

    # Appending must work on an empty manifest and on one that holds a document,
    # and must never truncate what is already there.
    with tempfile.TemporaryDirectory() as tmp:
        man = os.path.join(tmp, "MANIFEST.yaml")
        with open(man, "w", encoding="utf-8") as fh:
            fh.write("# a comment\nversion: 1\n\ndocuments: []\n")
        append_entry(man, text)
        first = open(man, encoding="utf-8").read()
        assert "version: 1" in first, first
        assert len(corpus._parse_manifest(first)) == 1, first

        second = entry_yaml({**fields, "id": "runbook-y"})
        append_entry(man, second)
        both = open(man, encoding="utf-8").read()
        assert "version: 1" in both, both
        got = corpus._parse_manifest(both)
        assert [d["id"] for d in got] == ["runbook-x", "runbook-y"], got

    # Site machinery must come off, and the prose must survive intact.
    page = (
        "---\ntitle: Debug Pods\nreviewers:\n- someone\n---\n\n"
        "<!-- overview -->\n\nThe first line of prose.\n\n"
        "<!-- body -->\n\n## Diagnosing\n\nSet the flag.\n\n"
        '## {{% heading "whatsnext" %}}\n\n{{< note >}}\n'
    )
    cleaned, removed = strip_site_machinery(page)
    assert "title: Debug Pods" not in cleaned, cleaned
    assert "reviewers" not in cleaned, cleaned
    assert "<!--" not in cleaned, cleaned
    assert "{{" not in cleaned, cleaned
    assert "The first line of prose." in cleaned, cleaned
    assert "Set the flag." in cleaned, cleaned
    assert "front matter" in removed, removed

    # A document with no machinery must come back unchanged.
    plain = "# Title\n\nSet the flag.\n"
    same, nothing = strip_site_machinery(plain)
    assert same.strip() == plain.strip(), same
    assert nothing == [], nothing

    # Cutting on a heading keeps whole sections, and says which it kept.
    doc = (
        "# Title\n\nIntro.\n\n## One\n\nFirst.\n\n"
        "## Two\n\nSecond.\n\n## Three\n\nThird.\n"
    )
    cut, note = cut_to_sections(doc, "One", "Three")
    assert cut.startswith("## One"), cut
    assert "Second." in cut and "Third." not in cut, cut
    assert "One" in note and "Three" in note, note

    # A heading that does not exist must stop the run, not silently keep the lot.
    try:
        cut_to_sections(doc, "Nowhere")
        raise AssertionError("a missing heading must raise")
    except SystemExit as exc:
        assert "Nowhere" in str(exc), exc

    print("corpus_add self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
