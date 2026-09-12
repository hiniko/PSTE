# PSTE — Programming Simplified Technical English

A controlled English specification for software communication, and a Claude Code skill
that enforces it.

**The goal is readability.** PSTE makes agent output easier to read, and easier to share
with other people. A tired reader, a hurried reader, or a reader who works in a second
language gets the fact without decoding the prose.

**PSTE does not make a model smarter.** It changes the form of the output only. It does
not change the substance, the reasoning, or the correctness.

A conforming document can still be wrong. This project makes no other claim. A document
here that claims more is a defect.

See [hiniko.github.io/PSTE](https://hiniko.github.io/PSTE/) for PSTE at work on real
documentation. It has a before-and-after example and the eval corpus.

## Quick start

Most readers want the skill, not the checker. [skill/SKILL.md](skill/SKILL.md) is the
skill, and its name is `pste`. Install it one of two ways.

**Copy the skill directory.** Clone this repository, then copy `skill/` into your
Claude Code skills directory as `pste/`, so the path ends `pste/SKILL.md`.

**Add the repository as a plugin.** [.claude-plugin/plugin.json](.claude-plugin/plugin.json)
declares a plugin with the skill, a set of commands, and two hooks. The hooks keep the
rules active across a long session. Point your plugin configuration at this repository to
pick up all three together.

Once the skill is active, ask for any documentation, release notes, or runbook text, and
the model writes it in PSTE. See [hiniko.github.io/PSTE](https://hiniko.github.io/PSTE/)
for the before-and-after comparison. It shows PSTE's effect on real text, before you
try it yourself.

A checker also exists, at `evals/pste_lint.py`. It is a testing tool for this project,
not a step a skill user needs. [evals/OVERVIEW.md](evals/OVERVIEW.md) explains its process.

## What is here

| Path | What it is |
|---|---|
| `spec/PSTE-1.md` | The specification. RFC-style, with MUST/SHOULD/MAY and stable rule identifiers. |
| `spec/STANDARD.md` | How PSTE works, in brief: the rules and the scope. |
| `spec/wordlist.yaml` | Approved words, one meaning each, and the synonyms they replace. |
| `spec/terms.yaml` | Term categories: the software vocabulary a general word list cannot hold. |
| `spec/appendix-*.md` | Generated from the two YAML files. Do not edit. |
| `spec/METHOD.md` | How the editors built the word list, and why it copies nothing. |
| `spec/conformance/` | Test cases. Appendix D of the specification, and the checker's test suite. |
| `skill/SKILL.md` | The skill prompt. Scope, rules, examples. |
| `skill/hooks/` | Three layers that stop the rules from decaying over a long session. |
| `evals/` | Verification tooling: the mechanical checker, coverage, fact preservation, and the arm harness. |
| `evals/OVERVIEW.md` | The checker against the eval suite, and why they answer different questions. |
| `evals/README.md` | How the evals work, in depth, and what the mechanical checker can and cannot do. |
| `evals/FUTURE-WORK.md` | Which readability measures work, which are circular, and why. |
| `docs/` | The site at [hiniko.github.io/PSTE](https://hiniko.github.io/PSTE/). |

Every tool in this repository is verification tooling for PSTE-1 and the skill.
This project distributes no separate checker binary.

## Licence

The work of this project is **MIT**. See [LICENSE](LICENSE).

The corpus in `evals/corpus/` holds documents that other people wrote, each under the
license its author chose. A rewrite of one of those documents follows the license of
its source. [LICENSES.md](LICENSES.md) sets out the split. The tooling records the
license of every rewrite, so nobody has to trace it by hand.

## Inspiration and sources

See [SOURCES.md](SOURCES.md) for the full list, and for what this project took from each.

**ASD-STE100 Simplified Technical English** inspired this work. It is the best known
controlled English for technical documentation. It showed that a restricted vocabulary
and a fixed grammar make technical text easier to read.

PSTE takes the idea and builds its own specification for software: its own rules, and
its own word list, built from permissively licensed documentation.
[spec/METHOD.md](spec/METHOD.md) records where each word came from.

ASD-STE100 is a registered trademark of ASD (EU trade mark 017966390), and ASD restricts
who may reproduce its specification. **Conformance to PSTE is not conformance to
ASD-STE100.** If you write aerospace maintenance documentation, use ASD-STE100 and not
this. ASD publishes it at https://asd-ste100.org.

PSTE covers a domain that aerospace controlled English does not: how people build
software.

A writer of software prose needs words such as `refactor`, `merge`, `deploy`, and
`deprecate`. That writer also needs rules for identifiers, for destructive commands,
and for stated uncertainty.

## Status

Version 0.1.0. PSTE-1, the checker, the skill, and the hooks work.

Two limits are worth knowing before you depend on this:

- **The word list is incomplete.** It holds 270 entries and about 1,160 vocabulary
  items, which covers the synonym clusters that cause the most rotation in software
  writing. `spec/METHOD.md` records the steps that fill the rest. A word that the list
  does not name is not thereby forbidden.
- **Few eval runs happened so far.** `evals/results/` holds the runs. Read
  [evals/OVERVIEW.md](evals/OVERVIEW.md) before you treat a number there as a settled
  claim.
