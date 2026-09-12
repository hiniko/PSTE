#!/usr/bin/env python3
"""Load and verify the eval corpus.

    python3 evals/corpus.py            # list the documents
    python3 evals/corpus.py --check    # verify every file against the manifest
    python3 evals/corpus.py --self-test

Every document in `evals/corpus/` is a real document under a licence that permits
redistribution and modification. The manifest records where each one came from.

WHY THE CHECK MATTERS

Two failures are silent without it. A source document that somebody edits stops
being the document the manifest describes, and a licence obligation that loses its
attribution becomes a licence breach. `--check` compares every file with its
recorded sha256 and refuses a document whose licence this project cannot use.

Run it in CI. `run.py` runs it before an eval, because rewriting a document this
project may not redistribute is worse than a failed eval.
"""

import argparse
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(ROOT, "evals", "corpus")
MANIFEST = os.path.join(CORPUS_DIR, "MANIFEST.yaml")

# A licence must permit redistribution AND modification. A rewrite is a
# modification, and the corpus lives in a public repository, so both are needed.
# This list is deliberately short. Add to it only with a licence you have read.
ALLOWED_LICENCES = {
    "CC0-1.0",
    "public-domain",
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "CC-BY-SA-3.0",
}

# A rewrite is an adaptation. Share-alike licences require that an adaptation carry
# the same licence, so a rewrite of one of these documents is NOT MIT, whatever the
# rest of the repository says. `derived_licence()` computes this, `run.py` stores it
# beside every output, and `report.py` shows it on the column.
SHARE_ALIKE = {"CC-BY-SA-4.0", "CC-BY-SA-3.0"}

# CC-BY requires that a modified version says it was modified. A rewrite is a
# modified version, so a result built from one of these must carry the notice.
ATTRIBUTION_REQUIRED = {
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "CC-BY-SA-3.0",
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
}

# The name of a licence is not the licence. A reader who checks an attribution needs
# the text, so the report links to it. The manifest does not carry these, because a
# hand-typed licence URL is one more thing that can be wrong.
LICENCE_URLS = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "MIT": "https://opensource.org/licenses/MIT",
    "Apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
    "BSD-2-Clause": "https://opensource.org/licenses/BSD-2-Clause",
    "BSD-3-Clause": "https://opensource.org/licenses/BSD-3-Clause",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-SA-3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "public-domain": "",
}

# The licence of the repository's own work. A rewrite of a permissively licensed
# document falls under this; a rewrite of a share-alike document does not.
PROJECT_LICENCE = "MIT"

REQUIRED_FIELDS = (
    "id",
    "type",
    "title",
    "url",
    "author",
    "licence",
    "retrieved",
    "sha256",
)


class CorpusError(Exception):
    """The corpus does not match its manifest, or holds something it may not."""


def _parse_manifest(text):
    """Read the manifest without a YAML dependency.

    The file is a fixed, flat shape: a `documents:` list of string fields. A real
    YAML parser would be better, but `evals/` tools must run from a clean checkout
    with no install step, and this file is written by this project alone.
    """
    documents, current = [], None
    in_documents = False

    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip() if " #" in raw else raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if re.match(r"^documents:\s*\[\s*\]\s*$", line):
            in_documents = True
            continue
        if re.match(r"^documents:\s*$", line):
            in_documents = True
            continue
        if not in_documents:
            continue

        item = re.match(r"^\s*-\s+(\w+):\s*(.*)$", line)
        if item:
            if current:
                documents.append(current)
            current = {item.group(1): _scalar(item.group(2), item.group(1))}
            continue

        field = re.match(r"^\s+(\w+):\s*(.*)$", line)
        if field and current is not None:
            current[field.group(1)] = _scalar(field.group(2), field.group(1))

    if current:
        documents.append(current)
    return documents


# Only these fields hold a number. A sha256 of all digits is a valid sha256, and
# reading it as an integer would strip its leading zeros and match no file.
NUMERIC_FIELDS = {"words"}


def _scalar(value, field=None):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value in ("true", "false"):
        return value == "true"
    if field in NUMERIC_FIELDS and re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def load(manifest=MANIFEST):
    """Every document in the manifest. Raises CorpusError when one is malformed."""
    if not os.path.exists(manifest):
        raise CorpusError(f"no manifest at {manifest}")
    with open(manifest, encoding="utf-8") as fh:
        documents = _parse_manifest(fh.read())

    seen = set()
    for doc in documents:
        missing = [f for f in REQUIRED_FIELDS if not doc.get(f)]
        if missing:
            raise CorpusError(
                f"document {doc.get('id', '?')} has no {', '.join(missing)}. "
                "Every field is required: a document with no provenance cannot "
                "stay in a public repository."
            )
        if doc["id"] in seen:
            raise CorpusError(f"duplicate document id {doc['id']}")
        seen.add(doc["id"])
        if doc["licence"] not in ALLOWED_LICENCES:
            raise CorpusError(
                f"document {doc['id']} is under {doc['licence']}, which this "
                f"project may not redistribute or modify.\n"
                f"Allowed: {', '.join(sorted(ALLOWED_LICENCES))}.\n"
                "A rewrite is a modification, and this repository is public."
            )
    return documents


def path_of(doc, directory=CORPUS_DIR):
    return os.path.join(directory, f"{doc['id']}.md")


def check(manifest=MANIFEST, directory=CORPUS_DIR):
    """Verify every document. Returns the list of problems, empty when correct."""
    problems = []
    try:
        documents = load(manifest)
    except CorpusError as exc:
        return [str(exc)]

    for doc in documents:
        path = path_of(doc, directory)
        if not os.path.exists(path):
            problems.append(f"{doc['id']}: the manifest lists it, but {path} is absent")
            continue
        actual = sha256_of(path)
        if actual != doc["sha256"]:
            problems.append(
                f"{doc['id']}: the file changed since somebody recorded it.\n"
                f"    manifest {doc['sha256']}\n"
                f"    file     {actual}\n"
                "    A source document must not change. An eval that rewrites a\n"
                "    different document than the manifest describes compares\n"
                "    nothing. Restore the file, or record the new sha256 and say\n"
                "    why it changed."
            )

    # README.md documents the corpus. It is not part of it.
    known = {f"{d['id']}.md" for d in documents} | {"README.md"}
    if os.path.isdir(directory):
        for name in sorted(os.listdir(directory)):
            if name.endswith(".md") and name not in known:
                problems.append(
                    f"{name} sits in the corpus, and the manifest does not list it. "
                    "Add it with its licence, or delete it."
                )
    return problems


def attribution(doc):
    """The notice that a rewrite of this document must carry."""
    if doc["licence"] not in ATTRIBUTION_REQUIRED:
        return ""
    notice = (
        f"Rewritten from \"{doc['title']}\" by {doc['author']}, "
        f"used under {doc['licence']}. Source: {doc['url']}. "
        "This text is a modification of the original."
    )
    if doc["licence"] in SHARE_ALIKE:
        notice += f" This modification is published under {doc['licence']}."
    return notice


def derived_licence(doc):
    """The licence that covers a REWRITE of this document.

    A rewrite is an adaptation. A share-alike licence requires that an adaptation
    carry the same licence, so a rewrite of a CC-BY-SA document stays CC-BY-SA even
    though the rest of this repository is MIT. Every other allowed licence permits
    the rewrite to be released under the project licence.

    Nobody should have to work this out per document, which is why it is computed
    and stored in the result rather than left to a reader.
    """
    if doc["licence"] in SHARE_ALIKE:
        return doc["licence"]
    return PROJECT_LICENCE


def self_test():
    import tempfile

    sample = """
documents:
  - id: runbook-example
    type: runbook
    title: "An example"
    url: https://example.org/a.md
    author: "Example contributors"
    licence: Apache-2.0
    retrieved: 2026-08-03
    sha256: PLACEHOLDER
    words: 12
    excerpt: false
"""
    with tempfile.TemporaryDirectory() as tmp:
        body = "# Example\n\nSet the flag. The parser reads the file.\n"
        doc_path = os.path.join(tmp, "runbook-example.md")
        with open(doc_path, "w", encoding="utf-8") as fh:
            fh.write(body)
        digest = sha256_of(doc_path)

        man = os.path.join(tmp, "MANIFEST.yaml")
        with open(man, "w", encoding="utf-8") as fh:
            fh.write(sample.replace("PLACEHOLDER", digest))

        docs = load(man)
        assert len(docs) == 1, docs
        assert docs[0]["id"] == "runbook-example", docs
        assert docs[0]["excerpt"] is False, docs
        assert docs[0]["words"] == 12, docs
        assert check(man, tmp) == [], check(man, tmp)

        # AN EDITED SOURCE DOCUMENT MUST FAIL.
        with open(doc_path, "a", encoding="utf-8") as fh:
            fh.write("An extra line.\n")
        problems = check(man, tmp)
        assert problems and "changed since" in problems[0], problems

        # A file with no manifest entry must fail.
        with open(doc_path, "w", encoding="utf-8") as fh:
            fh.write(body)
        stray = os.path.join(tmp, "unlisted.md")
        with open(stray, "w", encoding="utf-8") as fh:
            fh.write("x")
        problems = check(man, tmp)
        assert any("unlisted.md" in p for p in problems), problems
        os.remove(stray)

        # README.md documents the corpus, and is not a corpus document.
        readme = os.path.join(tmp, "README.md")
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write("# The corpus\n")
        assert check(man, tmp) == [], check(man, tmp)
        os.remove(readme)

        # A manifest entry with no file must fail.
        os.remove(doc_path)
        problems = check(man, tmp)
        assert any("is absent" in p for p in problems), problems

    # A SHA OF ALL DIGITS MUST STAY A STRING.
    #
    # A sha256 can be all digits. Reading it as a number strips its leading zeros,
    # so it matches no file, and the corpus check fails for a reason that has
    # nothing to do with the document. Only `words` is a number.
    numeric_sha = "0" * 63 + "1"
    parsed = _parse_manifest(sample.replace("PLACEHOLDER", numeric_sha))
    assert parsed[0]["sha256"] == numeric_sha, parsed
    assert isinstance(parsed[0]["sha256"], str), parsed
    assert parsed[0]["words"] == 12 and isinstance(parsed[0]["words"], int), parsed

    # A FORBIDDEN LICENCE MUST FAIL. This is the check that keeps the repository
    # lawful, so it must fire before anything reads the document.
    for bad in ("CC-BY-NC-4.0", "CC-BY-ND-4.0", "GPL-3.0", "proprietary", "unknown"):
        with tempfile.TemporaryDirectory() as tmp:
            man = os.path.join(tmp, "MANIFEST.yaml")
            with open(man, "w", encoding="utf-8") as fh:
                fh.write(
                    sample.replace("PLACEHOLDER", "0" * 64).replace(
                        "licence: Apache-2.0", f"licence: {bad}"
                    )
                )
            try:
                load(man)
                raise AssertionError(f"{bad} must be refused")
            except CorpusError as exc:
                assert "may not redistribute" in str(exc), exc

    # A missing field must fail: provenance is not optional.
    for field in ("url", "author", "licence", "sha256"):
        with tempfile.TemporaryDirectory() as tmp:
            man = os.path.join(tmp, "MANIFEST.yaml")
            text = "\n".join(
                l for l in sample.splitlines() if not l.strip().startswith(f"{field}:")
            )
            with open(man, "w", encoding="utf-8") as fh:
                fh.write(text.replace("PLACEHOLDER", "0" * 64))
            try:
                load(man)
                raise AssertionError(f"a missing {field} must be refused")
            except CorpusError as exc:
                assert field in str(exc), exc

    # The committed manifest must parse, and every document in it must satisfy the
    # rules. An empty corpus is valid too, so this asserts the shape and not a count.
    committed = load(MANIFEST)
    for doc in committed:
        assert doc["licence"] in ALLOWED_LICENCES, doc
        assert doc["sha256"] and len(doc["sha256"]) == 64, doc
        assert isinstance(doc.get("words"), int), doc
        # An excerpt must say what it cut, or nobody can tell what is missing.
        if doc.get("excerpt"):
            assert doc.get("note"), f"{doc['id']} is an excerpt with no note"

    # Every allowed licence needs a link to its text, or a reader who checks an
    # attribution has only a name. Adding a licence above must add its URL too.
    assert set(LICENCE_URLS) == ALLOWED_LICENCES, (
        set(LICENCE_URLS) ^ ALLOWED_LICENCES
    )

    notice = attribution(
        {
            "licence": "CC-BY-4.0",
            "title": "T",
            "author": "A",
            "url": "U",
        }
    )
    assert "modification of the original" in notice, notice
    assert attribution({"licence": "CC0-1.0"}) == ""

    # SHARE-ALIKE MUST PROPAGATE TO THE REWRITE.
    #
    # A rewrite is an adaptation, so a rewrite of a CC-BY-SA document is CC-BY-SA
    # and not MIT. Getting this wrong publishes somebody else's licensed text under
    # terms they did not grant, so it is checked for every allowed licence.
    for licence in ALLOWED_LICENCES:
        doc = {"licence": licence, "title": "T", "author": "A", "url": "U"}
        got = derived_licence(doc)
        if licence in SHARE_ALIKE:
            assert got == licence, (licence, got)
            assert "published under" in attribution(doc), licence
        else:
            assert got == PROJECT_LICENCE, (licence, got)
            assert "published under" not in attribution(doc), licence

    print("corpus self-test: all checks passed")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Load and verify the eval corpus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.check:
        problems = check()
        if problems:
            print("corpus check FAILED\n", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
            return 1
        documents = load()
        print(f"corpus check passed: {len(documents)} documents")
        return 0

    try:
        documents = load()
    except CorpusError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not documents:
        print("the corpus is empty. Add a document to evals/corpus/MANIFEST.yaml.")
        return 0

    print(f"{'id':<34} {'type':<16} {'licence':<14} words")
    for doc in documents:
        print(
            f"{doc['id']:<34} {doc['type']:<16} "
            f"{doc['licence']:<14} {doc.get('words', '?')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
