# PSTE evals

This directory measures whether the skill (`skill/SKILL.md`) writes prose that
follows the standard (`spec/PSTE-1.md`). It also measures whether the skill beats a
plain request for the same thing.

Every tool here is verification tooling for this repository. None of it ships as a
product.

## The three texts

Every arm rewrites the same committed document.

| Text | Where it comes from |
|---|---|
| `source` | The document in `evals/corpus/`. Committed. Nothing generates it. |
| `control` | A rewrite, asked for plainly: *"Rewrite this document to be simpler to read."* |
| `pste` | The same plain ask, plus `skill/SKILL.md` |

**The comparison that matters is `pste` against `control`.** Both arms get the same
request. The skill is the only difference between them. A skill that cannot beat a
plain request for the same thing has not earned its complexity.

There is no `baseline` arm. An arm with no instruction measures the difference
between asking and not asking. That is not the question here.

## The corpus

`evals/corpus/` holds real documents, written by people, under licences that permit
redistribution and modification. It also holds a smaller set of synthetic
documents, which a model wrote about this repository.

`evals/corpus.py --check` verifies every file against a manifest of source and
licence. An edited source document or a broken attribution then fails loudly,
instead of drifting unnoticed.

The real documents test whether the skill can improve writing nobody here
produced.

The synthetic documents test the skill's other job: constraining what a model
writes from a blank page. A corpus of human documentation alone tests only the
first job.

## The mechanical checker

`evals/pste_lint.py` is a regular-expression checker. It implements 29 of the 78
rules in the standard, the ones a machine can count.

Examples: sentence length, contractions, semicolons, Latin abbreviations,
marketing adjectives, filler words, and passive-voice patterns.

**It is eval tooling, not a conformance authority.** Earlier versions of this
project distributed it as a standalone tool. That stopped. A cheap, reliable signal
for a countable rule is not the same thing as a reliable signal for a rule that
needs judgement, and four of the 25 rules need judgement.

`PSTE-N5`, `G7`, `G11`, and `G12` infer part of speech from a fixed word list. Is
"test" a noun or an adjective here? Is "binary" a noun or an adjective there?
English marks no adjective, so a closed list can never cover every case.

Measured against the checker's own test cases, the false-positive rate is 75
percent for N5 and 30 percent for G7.

The checker still runs these four rules and reports what it finds. It marks each
finding `arbitrated` (see `ARBITRATED_RULES` in `pste_lint.py`), rather than
folding the finding into a verdict on its own.

A finding from one of the other 21 rules is `countable`. It fails a document by
itself, because the false-positive rate on those is low enough to trust unread.

A model told to fix every finding cannot tell a countable finding from an
arbitrated one. It would rewrite good prose to satisfy a false positive.

This is why the skill prompt (`skill/SKILL.md`) no longer runs the checker at all.
The model composes, reasons against the spec directly, and sends. No linter output
reaches it.

## The LLM judge

`evals/semantic_lint.py` asks a model to judge the 52 rules a regular expression
cannot. Does the passive voice hide an actor that the text could name? Does a
warning lead with the risk? Does the first sentence give the result?

The judge also receives every `arbitrated` finding from the mechanical checker,
and it must confirm or reject each one. It never sees the countable findings, so it
never repeats a decision the mechanical checker already made.

A single judgement is not evidence. The same model disagrees with itself between
runs. `run.py` judges each text several times and keeps every pass: `--judge-passes`
sets the count, 5 by default.

A finding counts as **confirmed** only when the share of passes that reported it
meets the agreement gate, a plain majority.

Below the gate, the finding is **low-agreement**. A low-agreement finding still
appears on the page for a person to read, but it never fails a document on its
own.

With only two judge passes, agreement can only ever read 0.5 or 1.0. That is too
coarse to trust. Use more passes before you publish a result.

## The fact-loss gate

Rule PSTE-A1 says accuracy defeats every other rule, and the mechanical checker
cannot see that rule at all. Worse, the checker rewards the failure: a rewrite that
drops a fact has fewer words to break a rule with, so it scores better on
everything else.

`evals/faithfulness.py` compares a rewrite against its source. It reports every
number, unit, identifier, negation, obligation, and scope word that the rewrite
lost.

Every check here is a plain string comparison, on purpose. An entailment model can
score a rewrite as faithful after a number changes, and that is the one error this
project cannot afford.

A document must pass the fact-loss check before anything else counts toward PASS.
A document with a clean conformance report still fails if it dropped a fact.

`faithfulness.py` finds dropped tokens, not changed meaning. A passing fact-loss
check is not proof a rewrite is faithful. It is only proof the rewrite did not drop
what the checker looks for.

## The pass threshold

Spec §5.1 states the rule a conformance tool must compute a verdict by (PSTE-C6,
C7, C8). A document passes when three things hold: it has no MUST finding, its
SHOULD findings stay at or below one for every 100 words rounded up, and it has no
fact loss under PSTE-A1.

A tool must report PASS or FAIL. It must not report a score in place of a verdict,
so a writer sees a target and not a number to chase.

`evals/report.py` builds one page per eval result. It computes a pass for each cell
from three checks: no countable mechanical finding, no confirmed semantic finding,
and no fact loss.

This is the harness's own verdict, built for a maintainer who compares one run
against another. It is stricter than the mechanical checker alone, because it also
gates on the LLM judge.

`evals/measure.py` reports this as a share across the corpus. Spec §5.2 permits an
evaluation harness to show a rate, unlike a tool this project would hand to a
writer.

## Running the evals

```
python3 evals/pste_lint.py FILE...                mechanical check, one file
python3 evals/readability.py FILE...               vocabulary coverage
python3 evals/faithfulness.py SOURCE REWRITE       what a rewrite lost
python3 evals/corpus.py --check                    verify the corpus against its manifest
python3 evals/run.py                               the full publication run (calls a model)
python3 evals/run.py --limit 2                     a quick check, cheaper
python3 evals/measure.py                           score the newest result, print the table
python3 evals/diagnose.py                          rank which rules the skill still breaks
python3 evals/report.py --open                     read the newest result in a browser
```

`pste_lint.py`, `readability.py`, `faithfulness.py`, and `corpus.py` are free,
offline, and deterministic.

`run.py` calls a model and costs money; judging runs every time, and costs more of
it. `--limit`, `--only`, and `--passes` make a run cheaper for debugging.
`measure.py`, `diagnose.py`, and `report.py` each read a result that `run.py`
already wrote.

## One file per run

Each run writes a self-contained result, named after the day and the commit:

    evals/results/eval-2026-08-03-3f9a1b7c.json

The commit identifies the inputs, so two results compare directly. **A run refuses
to start on a dirty tree**, because an uncommitted edit would change the result
while the commit stayed the same. `results/README.md` covers the rule, and there is
no flag that skips it.

`report.py` writes the page beside the result and gives it the same name, so a
directory of results produces a directory of pages that still match.

Git ignores the generated page and keeps the result. Every verdict is computed at
build time from the current standard and checker, so a change to either shows up
on the next build, with no new eval run needed.

## What this measures

Conformance to the rules in `spec/PSTE-1.md`, and fact preservation under PSTE-A1,
for the documents in `evals/corpus/`.

## What this does not measure

**Comprehension.** No script here has a reader in it. `readability.py` measures
vocabulary coverage. That property correlates with comprehension in published
research (Nation 2006, and Laufer and Ravenhorst-Kalovski 2010).

It is not the same as measuring comprehension. A blind reading trial with real
readers is the validation this project still needs.
[FUTURE-WORK.md](FUTURE-WORK.md) records the trial design.

Until that trial runs, the honest claim is that PSTE text passes several
independent automated checks. It is not that PSTE text is easier to read.

**Quality, correctness, or usefulness.** Nothing here can tell you the text is true
or complete.

**A fair contest.** The mechanical checker counts what the rules forbid, and the
skill prompt tells the model to avoid those same things. A large improvement on
the mechanical score alone is close to circular. It shows the model followed the
instruction, not that the instruction was worth giving.

The LLM judge and the fact-loss gate exist to test something the skill prompt does
not name directly.

An arm that answered every document with a single word would pass every mechanical
check. Read the outputs, not only the table.

## Known limits

- One model judges its own output family. The writer and the judge are not
  independent. [FUTURE-WORK.md](FUTURE-WORK.md) records the plan to check this
  against a judge from a different model family.
- A small corpus. Enough to show a direction, not enough for a statistical claim.
- Model output varies between runs. `run.py --passes` and `--judge-passes` each
  take several samples for this reason, but the harness does not report a
  confidence interval.
- The mechanical checker covers 29 of 78 rules, and four of those need the judge's
  confirmation before they count. The other 49 rules depend on the judge alone, and
  a judge is not a measurement. See `semantic_lint.py`'s own docstring.
