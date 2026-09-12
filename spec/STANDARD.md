# The standard, in brief

This page explains PSTE for a reader who wants the shape of the rules, not the
full text. [spec/PSTE-1.md](PSTE-1.md) is the standard itself, with every rule <!-- pste-lint: ignore -->
and its identifier.

## The rules, in short

- State the result first.
- Name the actor. Use the active voice.
- Use one word for one meaning.
- Keep an instruction under 20 words, and a description under 25.
- Use simple tenses only.
- Do not use contractions, semicolons, Latin abbreviations, marketing
  adjectives, or filler.
- State uncertainty once.

A destructive operation needs its own warning. The writer must warn the
reader before an operation that destroys something, and must say what the
reader loses.

Accuracy defeats every one of those rules. A writer must never drop a fact to
satisfy a word limit.

## Scope

PSTE governs the prose that the writer composes. It does not govern:

- Code, commands, paths, identifiers, and error strings. Reproduce these
  verbatim.
- Quoted text from any source. Reproduce this verbatim.
- Code comments and commit messages. Match the repository's style.

## Where to go next

[spec/PSTE-1.md](PSTE-1.md) states every rule, with its identifier and its
test cases. [spec/METHOD.md](METHOD.md) records how the word list was built.
[evals/OVERVIEW.md](../evals/OVERVIEW.md) explains how this project checks
its own work.
