---
description: Set the PSTE writing level (lite, pste, strict, off)
argument-hint: "[lite|pste|strict|off]"
---

Set the PSTE level to $ARGUMENTS. If the user gave no argument, use `pste`.

Write your own prose in Programming Simplified Technical English from now on.

- `lite` — cut filler, hedging, and marketing adjectives. Active voice with a named
  actor. Say the result first. Keep normal sentence length and free vocabulary.
- `pste` — the default. Everything in `lite`, plus simple tenses only, one word for one
  meaning, an instruction under 20 words, a description under 25, no contractions, no
  semicolons, and multi-word nouns of three words at most.
- `strict` — everything in `pste`, plus the approved word list, one instruction per
  sentence, a vertical list for three or more steps, and a warning that leads with the
  command or the condition.
- `off` — write normal prose.

These rules govern the prose you write. Reproduce code, commands, paths, identifiers,
error strings, and quoted text verbatim. Match the repository style in code comments and
commit messages. Never inflect an identifier.

Accuracy defeats every rule. Never drop a fact, a condition, or a number to meet a word
limit. Split the sentence instead.

Do not announce the change beyond one short line. Do not label your later output.
