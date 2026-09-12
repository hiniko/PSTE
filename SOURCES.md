# Sources and inspiration

This project takes ideas from the work below. This document records what came from
where, so that a reader can check the source of any part of PSTE.

The list separates **inspiration** from **sources**. The difference matters:

- An **inspiration** showed that a way works. This project read about it, learned
  from it, and then wrote its own version. No text moved between the two.
- A **source** supplied text, data, or code that this project uses or adapts.

## Inspiration

### ASD-STE100 Simplified Technical English

Published by the AeroSpace, Security and Defence Industries Association of Europe. <!-- pste-lint: ignore -->
https://asd-ste100.org

**Inspiration, not a source.**

ASD-STE100 is the best known controlled English for technical documentation. It
demonstrated the idea that this project rests on: a restricted vocabulary and a fixed
grammar make technical text easier to read. The effect is largest for readers whose
first language is not English.

**What PSTE took: the idea only.** A controlled vocabulary works. <!-- pste-lint: ignore -->
Approve one word per meaning. <!-- pste-lint: ignore -->
Give writers a type-based escape hatch for domain vocabulary that a general
word list cannot hold. Write the rules as a numbered, citable standard. <!-- pste-lint: ignore -->

**What PSTE did not take.** No rule text. No rule numbering. <!-- pste-lint: ignore -->
No dictionary entry. No examples. No structure of the document. <!-- pste-lint: ignore -->
PSTE has its own rule identifiers (`PSTE-G1`,
`PSTE-V3`), its own rule text, and its own word list.

**Why the separation is strict.** ASD-STE100 is a registered trademark of ASD (EU trade
mark 017966390). ASD grants free reproduction rights to eight named categories of
organization, which are aerospace and defence bodies, airworthiness authorities, and <!-- pste-lint: ignore -->
universities for educational purposes. This project is in none of them. ASD also
prohibits anyone from redistributing the specification without written permission.

This project so keeps no copy of the ASD-STE100 text in the repository, quotes
none of it, and reproduces no part of its dictionary.

**Conformance to PSTE is not conformance to ASD-STE100.** A writer of aerospace
maintenance documentation must use ASD-STE100 and not this project. ASD publishes it free
of charge at the address above.

### Basic English

C.K. Ogden, 1930. The earliest systematic restricted-vocabulary English. It established
that a short list of approved words can carry general meaning.

### Politics and the English Language

George Orwell, 1946. Six rules for clear prose. Two of them shape PSTE:

- Cut a word if you can cut it.
- Break any of these rules sooner than write something barbarous.

The second rule is the ancestor of PSTE-A1, which says that accuracy defeats every other
rule in the standard. <!-- pste-lint: ignore -->

### Plain Writing Act of 2010

US Public Law 111-274, and the plain-language guidance that followed it. Precedent for
treating readability as a requirement, not a preference.

## Sources

### RFC 2119 and RFC 8174

Bradner (1997) and Leiba (2017), IETF. **Source.** PSTE-1 §2 uses the BCP 14 conformance
vocabulary, with the usual boilerplate that both RFCs specify. IETF publishes RFCs for
public use.

### caveman

Julius Brussee. https://github.com/juliusbrussee/caveman

**Source, for architecture.** caveman is a mature output-style skill. This project takes
its response to one hard case: a style instruction decays over a long session,
especially after context compaction removes it.

What PSTE takes:

- Inject the full rule set once at session start, read live from the skill file so the
  hook can never drift from the documented rules
- Inject a short reminder on every user turn, which survives competing instructions from
  other plugins
- Hold the active level in a file, so it survives compaction and new sessions
- Compare a skill against a plain "be concise" control, never against an unprompted
  baseline, because the second comparison inflates the result

What PSTE does not take: the caveman voice, the compression goal, and the token-savings
framing. PSTE is not a compression standard. <!-- pste-lint: ignore -->

### A controlled-English skill by L1nefeed

https://gist.github.com/L1nefeed/4164ecaaf77879e76dca3c06f142f1c2

**Source, for the scope model.** This skill answered the question of what a style rule
governs. Its four-target model separates the prose that a writer composes from code, from
quoted text, and from repository text. PSTE-1 §4 keeps that model and adds the rules for
identifiers.

It also supplied the principle that accuracy wins over style, and a table of default
verb choices that seeded the word list clusters.

### The cure for AI slop (episode 1)

woosal1337. https://github.com/woosal1337/blog/tree/main/videos/ep01-the-cure-for-ai-slop

**Source, for the checker design.** Its `ste-lint.py` showed that a useful checker needs
no dependencies and no parser: regular expressions and word lists find most of the <!-- pste-lint: ignore -->
mechanical failures. `evals/pste_lint.py` is a rewrite, not a fork, but it follows that
way.

Read its experiment with care. The report is honest about its limits, and the limits are
large: six prompts with one run each, two models, and a metric that counts the same
markers that the prompt forbids. On one of the two models a simpler rubric matched or beat
the controlled-English prompt. It is a pilot, not proof.

### Chervak, Drury and Ouellette (1996)

"Simplified English for Aircraft Workcards", Proceedings of the Human Factors and
Ergonomics Society Annual Meeting.

**Source, for the evidence claim.** 175 aircraft technicians. Comprehension rose from 76%
to 86%. For readers whose first language was not English, it rose from 69% to 87%.

This is the strongest evidence that this project cites, and it is the reason the project
exists. Note its scope: aerospace text, human authors, human readers. It does not measure
software text, and it does not measure machine-generated text.

## What no source supplies

The word list in `spec/wordlist.yaml` is original. `spec/METHOD.md` records how the
editors built it. No access came from another controlled vocabulary.

The rules in `spec/PSTE-1.md` are original text. No aerospace standard has the same <!-- pste-lint: ignore -->
rules for these:

- PSTE-S4 (identifiers are never inflected)
- PSTE-V4 (one name per entity, matching the code)
- PSTE-L1 (state uncertainty once)
- PSTE-V10 (the four modal meanings)
- The warning rules in §11
