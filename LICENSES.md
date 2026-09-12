# Licenses

This repository holds work under more than one license. The split follows who wrote
what.

| What | License | Where |
|---|---|---|
| The standard, the checker, the skill, the tooling | **MIT** | [LICENSE](LICENSE) |
| Corpus documents | **per document** | [evals/corpus/MANIFEST.yaml](evals/corpus/MANIFEST.yaml) |
| Rewrites of corpus documents | **follows the source** | `derived_licence` in each result |

## The work of this project

`spec/`, `lib/`, `skill/`, `tools/`, and the tooling in `evals/` are MIT. Take them,
change them, and ship them.

## Corpus documents

`evals/corpus/` holds documents that other people wrote. Each one keeps the license
its author chose. `MANIFEST.yaml` records that license, the author, the URL, and the
retrieval date.

A document may only enter the corpus under a license that permits redistribution and
change, because the eval rewrites it and this repository is public.
`evals/corpus.py` refuses anything else.

## Rewrites

**A rewrite adapts its source. It is not new work of this project.**

Every eval run produces a rewrite of a corpus document. The license of that rewrite
follows the license of the document it came from:

- Source under CC0, public domain, MIT, Apache-2.0, BSD, or CC-BY-4.0 → the rewrite
  is **MIT**, like the rest of this project's work. CC-BY also needs the
  attribution notice, which the result carries.
- Source under **CC-BY-SA** → the rewrite is **CC-BY-SA too**. Share-alike requires
  that an adaptation carry the same license. The MIT license of this repository does
  not override that, and cannot.

`evals/corpus.py` computes this with `derived_licence()`, `evals/run.py` stores it in
every result, and `evals/report.py` prints it on each column of the report. A reader
does not have to work it out per document, and a reuser can see it on the text they
are about to copy.

## ASD-STE100

ASD-STE100 is a registered trademark of ASD (EU trade mark 017966390), and this project
holds no part of it. ASD-STE100 inspired PSTE, and PSTE reproduces no part of it.

PSTE is built for software, and its word list was built for software.
[spec/METHOD.md](spec/METHOD.md) records where every word came from: which part a
language model proposed from permissively licensed documentation, and which part a
person decided by hand. See also [SOURCES.md](SOURCES.md).

Conformance to PSTE is not conformance to ASD-STE100.
