# PSTE — Programming Simplified Technical English

A controlled English standard for software communication, and a Claude Code skill that
enforces it.

**The goal is readability.** PSTE makes agent output easier to read, and easier to share
with other people. A tired reader, a hurried reader, or a reader who works in a second
language gets the fact without decoding the prose.

**PSTE does not make a model smarter.** It changes the form of the output only. It does
not change the substance, the reasoning, or the correctness.

A conforming document can still be wrong. This project makes no other claim. A document
here that claims more is a defect.

## What is here

| Path | What it is |
|---|---|
| `spec/PSTE-1.md` | The standard. RFC-style, with MUST/SHOULD/MAY and stable rule identifiers. |
| `spec/wordlist.yaml` | Approved words, one meaning each, and the synonyms they replace. |
| `spec/terms.yaml` | Term categories: the software vocabulary a general word list cannot hold. |
| `spec/appendix-*.md` | Generated from the two YAML files. Do not edit. |
| `spec/METHOD.md` | How the editors built the word list, and why it copies nothing. |
| `spec/conformance/` | Test cases. Appendix D of the standard, and the checker's test suite. |
| `skill/SKILL.md` | The skill prompt. Levels, scope, rules, examples. |
| `skill/hooks/` | Three layers that stop the rules from decaying over a long session. |
| `evals/` | Verification tooling: the mechanical checker, coverage, fact preservation, and the arm harness. |
| `evals/README.md` | How the evals work, and what the mechanical checker can and cannot do. |
| `evals/FUTURE-WORK.md` | Which readability measures work, which are circular, and why. |

Every tool in this repository is verification tooling for the standard and the skill.
This project distributes no separate checker binary. See
[evals/README.md](evals/README.md) for how the checker and the other evals work.

## Use the checker

```
python3 evals/pste_lint.py README.md              # check a file
python3 evals/pste_lint.py --level 3 -v docs/*.md # enforce vocabulary, show each finding
python3 evals/pste_lint.py --json spec/PSTE-1.md  # machine-readable
python3 evals/pste_lint.py --self-test            # run the conformance cases
```

It reports `PASS`, or `FAIL` with a list of findings, and exits 1 on a failure, so it
works as a pre-commit hook inside this repository.

It implements 29 of the 78 rules in the standard, the ones a regular expression can
count. Four of those 29 (N5, G7, G11, G12) infer part of speech from a fixed word
list, which can never cover every case. Their findings are candidates for a judge to
confirm.

See [evals/README.md](evals/README.md) for the measured false-positive rates and how
the eval harness resolves them.

## The rules, in short

- Say the result first.
- Name the actor. Use the active voice.
- Use one word for one meaning.
- Keep an instruction under 20 words, and a description under 25.
- Use simple tenses only.
- Do not use contractions, semicolons, Latin abbreviations, marketing adjectives, or filler.
- State uncertainty once.
- Warn before an operation that destroys something. Say what the reader loses.

Accuracy defeats every one of those rules. Never drop a fact to satisfy a word limit.

## Levels

| Level | Name | What it checks |
|---|---|---|
| 1 | `lite` | Grammar and slop. Vocabulary is free. |
| 2 | `pste` | Level 1, plus sentence limits, simple tenses, structure. The default. |
| 3 | `strict` | Level 2, plus the approved word list. For runbooks, release notes, and published documentation. |

## Scope

PSTE governs the prose that the writer composes. It does not govern:

- Code, commands, paths, identifiers, and error strings — reproduce these verbatim
- Quoted text from any source — reproduce this verbatim
- Code comments and commit messages — match the repository's style

## What the checker cannot do

The checker measures conformance to the rules. It does not measure readability, and it
does not measure quality. It counts the things that the rules forbid, so a clean report
is necessary but not sufficient.

Worse, it **rewards** one failure. A rewrite that drops a fact has fewer words to break
a rule with, so it scores better. Rule PSTE-A1 says that accuracy defeats every other
rule, and the checker cannot see that rule at all.

Two measures in `evals/` cover what the checker cannot:

```
python3 evals/readability.py FILE...          vocabulary coverage
python3 evals/faithfulness.py SOURCE REWRITE  what a rewrite lost
```

`readability.py` measures the share of words a reader can be expected to know, against
the thresholds that Nation (2006) and Laufer and Ravenhorst-Kalovski (2010) validated
against real comprehension scores. It is independent of the rules: a passage of short
sentences built from rare words scores 0 findings in the checker and 5 percent here.

`faithfulness.py` reports every number, unit, identifier, negation, obligation, and
scope word that a rewrite lost. Every check is a string comparison, because entailment
models score a rewrite as faithful after a number changes.

Neither measures comprehension. That needs readers who answer questions, and
[evals/FUTURE-WORK.md](evals/FUTURE-WORK.md) records the trial design. Until it runs,
the honest claim is that PSTE text passes several independent automated checks, not
that it is easier to read.

## Evidence

Controlled English improves comprehension for human readers. Chervak, Drury and Ouellette
(1996) tested 175 aircraft technicians. Comprehension rose from 76% to 86%. For readers
whose first language was not English, it rose from 69% to 87%.

That study covers aerospace text, human authors, and human readers. It supports the
readability claim. It does not measure software text, and it does not measure
machine-generated text. No study known to the editors does.

A published experiment on controlled English and language models
([woosal1337/blog ep01](https://github.com/woosal1337/blog/tree/main/videos/ep01-the-cure-for-ai-slop))
reports that a style rubric cuts slop markers by half or more. Read it with care. The
sample is six prompts with one run each. A simpler rubric matched or beat the STE prompt
on one of the two models. The metric counts the same markers that the prompt forbids.
The authors disclose these limits. It is a pilot, not proof.

## Licence

The work of this project is **MIT**. See [LICENSE](LICENSE).

The corpus in `evals/corpus/` holds documents that other people wrote, each under the
licence its author chose, and a rewrite of one of those documents follows the licence
of its source. [LICENSES.md](LICENSES.md) sets out the split, and the tooling records
the licence of every rewrite so that nobody has to trace it by hand.

## Inspiration and sources

See [SOURCES.md](SOURCES.md) for the full list, and for what this project took from each.

**ASD-STE100 Simplified Technical English** inspired this work. It is the best known
controlled English for technical documentation, and it showed that a restricted
vocabulary and a fixed grammar make technical text easier to read.

PSTE takes the idea and builds its own standard for software: its own rules, and its own
word list, built from permissively licensed documentation.
[spec/METHOD.md](spec/METHOD.md) records where each word came from.

ASD-STE100 is a registered trademark of ASD (EU trade mark 017966390), and ASD restricts
who may reproduce its specification. **Conformance to PSTE is not conformance to
ASD-STE100.** If you write aerospace maintenance documentation, use ASD-STE100 and not
this. ASD publishes it at https://asd-ste100.org.

PSTE covers a domain that aerospace controlled English does not: how people build
software. A writer of software prose needs words such as `refactor`, `merge`, `deploy`,
and `deprecate`. That writer also needs rules for identifiers, for destructive commands,
and for stated uncertainty.

## Status

Version 0.1.0. The standard, the checker, the skill, and the hooks work.

Two limits are worth knowing before you rely on this:

- **The word list is incomplete.** It holds 270 entries and about 1,160 vocabulary
  items, which covers the synonym clusters that cause the most rotation in software
  writing. `spec/METHOD.md` records the steps that fill the rest. A word that the list
  does not name is not thereby forbidden at level 3.
- **No eval run has happened.** `evals/` works, and `evals/results/` is empty until
  somebody runs it. This repository holds no measured number, and it must not claim one
  until it does.
