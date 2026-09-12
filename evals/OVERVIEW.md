# How this project checks its own work

This project uses the word "checker" for two different tools. This page keeps
them apart.

`evals/pste_lint.py` checks one document. A writer runs it against a single
file, and it reports every finding, each with its rule's weight, and a
weighted total. It is a tool, in the same sense as a linter.

The eval suite is a different thing. It tests whether the standard itself <!-- pste-lint: ignore -->
works: whether the skill beats a plain request, whether a fix pass helps,
and whether any of that costs the reader a fact. The suite uses a corpus, three
arms, a judge, and a fact-loss gate. `pste_lint.py` is one part of it, not
the whole of it.

Read this page for both jobs. [evals/README.md](README.md) covers the eval
suite in depth.

## Use the checker

```
python3 evals/pste_lint.py README.md              # check a file
python3 evals/pste_lint.py -v docs/*.md            # show each finding
python3 evals/pste_lint.py --json spec/PSTE-1.md   # machine-readable
python3 evals/pste_lint.py --self-test             # run the conformance cases
```

The tool reports each finding with its weight and the weighted total, or no
findings on a clean file. It exits 1 when it finds anything, so it works as a
pre-commit hook.

It implements 29 of the 78 rules in the standard, the ones a regular <!-- pste-lint: ignore -->
expression can count. Four of the 29 rules (N5, G7, G11, G12) infer part of
speech from a fixed word list, which can never cover every case. A judge
must check their findings.

## What the checker cannot do

The checker measures conformance to the rules. It does not measure
readability, and it does not measure quality. It counts what the rules
forbid, so a clean report is necessary but not enough.

Worse, the checker rewards one failure. A rewrite that drops a fact has fewer
words to break a rule with, so it scores better. Rule PSTE-A1 says that
accuracy defeats every other rule, and the checker cannot see that rule at
all.

Two measures in `evals/` cover what the checker cannot:

```
python3 evals/readability.py FILE...          # vocabulary coverage
python3 evals/faithfulness.py SOURCE REWRITE  # what a rewrite lost
```

`readability.py` measures the share of words a reader can be expected to
know. `faithfulness.py` reports every number, unit, identifier, negation,
obligation, and scope word that a rewrite lost. Neither measures
comprehension. No reading trial with people happened yet. Until one does,
the honest claim is that PSTE text passes some automatic checks, not that
it is easier to read.

## The corpus, and where it came from

`evals/corpus/` holds 14 documents. Nine are real documents that people wrote
for real projects. Five are synthetic: a model wrote them, in a clean
container, each one grounded in a fetch of a real upstream page.

The real documents test whether the skill can improve writing nobody here
produced. The synthetic documents test the skill's other purpose: constraining
what a model writes from an empty page.

[evals/corpus/MANIFEST.yaml](corpus/MANIFEST.yaml) lists every document, with
its title, its type, its license, and the URL it came from.

Four licenses appear in the corpus: CC-BY-4.0, Apache-2.0, BSD-3-Clause, and
CC0-1.0. Every document carries its URL, its author, and its attribution.
`evals/corpus_add.py` refuses a license outside the allowed set. A
no-derivatives license or a non-commercial license cannot enter the corpus.

`evals/corpus.py --check` compares every document against its recorded
checksum. An edited source document, or a broken attribution, then fails
loudly instead of drifting unnoticed.

## How a run works, end to end

`evals/run.py` runs three arms against the same corpus document. A plain
request asks a model to simplify the text, with no other instruction. The
skill arm adds `skill/SKILL.md` to the same request. A third arm takes the
skill's draft and runs one fix pass against the checker's own findings.

The comparison that matters is the skill against the plain request. Both get
the same ask. The skill is the only difference, so a gap between them is the
skill's effect, not the effect of asking at all.

A fix pass can remove a fact to satisfy a rule. The fact-loss gate catches
this: when a fix drops a fact that the draft before it still had, the run
keeps the draft and discards the fix. A document must never trade a fact for
a shorter sentence.

A judge model then reads every draft and confirms or rejects the findings
the checker could not decide by itself. [evals/README.md](README.md)
explains the arms, the judge, the fact-loss gate, and the rule weights in
full depth.

## How the project verifies itself

Twelve scripts in this repository carry a `--self-test` flag, which runs a
fixed set of cases and needs no network call and no model.

`evals/corpus.py --check` compares every corpus file against its recorded
checksum. `lib/build_appendix.py --check` compares the generated appendices
against the word list they come from, and catches drift between the two.

None of these three checks costs money, and none of them depends on a model
being available.

## Evidence

Controlled English improves comprehension for human readers. Chervak, Drury,
and Ouellette (1996) tested 175 aircraft technicians. Comprehension rose from
76% to 86%. For readers whose first language was not English, it rose from
69% to 87%.

That study covers aerospace text, human authors, and human readers. It
supports the readability claim behind PSTE. It does not measure software
text, and it does not measure machine-generated text. No study known to the
editors does.

A published experiment on controlled English and language models
([woosal1337/blog ep01](https://github.com/woosal1337/blog/tree/main/videos/ep01-the-cure-for-ai-slop))
reports that a style rubric cuts slop markers by half or more. Read it with
care. The sample is six prompts with one run each. A simpler rubric matched
or beat the STE prompt on one of the two models. The metric counts the same
markers that the prompt forbids.

The authors disclose these limits. It is a pilot, not proof.

`evals/results/` holds four eval runs, each dated and named after its
commit. The tool computes every finding at build time from the current
standard and checker. Read a run's own page before you treat its number as <!-- pste-lint: ignore -->
settled.

Across the 14-document corpus, a sentence carries no finding from the
checker at these rates:

| Arm | Sentences clean per hundred |
|---|---|
| Source documents, as published | 47.5 |
| A plain request to simplify | 73.6 |
| The skill | 83.9 |
| The skill and a fix pass | 96.0 |

These numbers are smaller than earlier ones from the same day, because a
checker bug was fixed. `split_sentences` counted a hard-wrapped sentence as
some sentences, and that flattered every file it measured. The numbers
above use the corrected count.

Read the numbers for what they are: the share of sentences that draw no
finding from a checker that implements 29 of PSTE-1's 78 rules. A
conformance result is not a measure of quality. No reading trial with
people ran yet. Until one runs, no number on this page is a readability
claim.
