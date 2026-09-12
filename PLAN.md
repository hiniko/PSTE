# Plan: PSTE — Programming Simplified Technical English

**A controlled English standard for software communication, plus the tooling that
enforces it.**

Status: BUILT. Version 0.1.0, 2026-08-02.
Spike: complete. Phases 1-8 done, except the eval RUN (harness exists, no snapshot).

**Superseded.** This plan describes the original three-level design (§6, §13's
"Level 3 auto-selection"). A later pass removed conformance levels: PSTE now has one
level, where every rule applies and the vocabulary rules are MUST. See
`spec/RENUMBER.md` for the section renumbering this caused in the specification. This
file is kept as the historical record of the original design, not updated to match.

Open questions in section 13 are answered. Decisions taken:
- Name PSTE confirmed.
- Public repo, with SOURCES.md. ASD-STE100 is framed as INSPIRATION, never a source.
- Level 3 auto-engages for known artifact types, configurable per repository.
- The checker ships as one self-contained file, plus a pre-commit config here.

Remaining work:
- Run the evals and commit a real snapshot. No number goes in any document until then.
- Grow the word list from 177 entries toward the full vocabulary (METHOD.md steps 1-2).
- Human readability test on matched pairs. This is the claim the project rests on, and
  no automated check can stand in for it.

## 1. Author's goal — state this first, everywhere

**The goal is readability. It is NOT making the model smarter.**

The purpose of this project is to make agent output **easier to read, and easier to
share with other people**. A reader who is tired, hurried, working in a second
language, or reading a pasted excerpt out of context should not have to decode the
prose to get the fact.

This project makes **no claim** that controlled English improves the correctness,
reasoning, or substance of model output. It does not. It changes the *form* of the
output so that a human can read it faster and misread it less. That is the whole
claim, and it is a sufficient one.

Any README, doc, or commit message that drifts toward "cures AI slop", "better
answers", or "smarter output" is wrong and must be corrected. See `memory/ste-evidence-caveats.md`
for what the published evidence does and does not support.

Supporting evidence for the readability claim is real and is about **human readers**:
Chervak, Drury & Ouellette 1996 (FAA), n=175 aircraft technicians — controlled-English
manuals raised comprehension 76%→86% overall, and **69%→87% for non-native readers**.

## 2. What this is

Two things, in dependency order:

**A. The PSTE standard** — an original controlled-English specification for software
communication. Written by us, RFC-style, with MUST/SHOULD/MAY normative language.
Roughly 900 approved words with single fixed meanings, plus term categories for
software vocabulary. This is the deliverable that outlives the tooling.

**B. The `pste` skill** — a self-contained Claude Code skill that makes an agent write
its own user-facing prose in conformance with the standard, and a linter that checks
conformance mechanically.

It is a mashup of three sources, none of which had all three parts:

| Source | What we take | What we leave |
|---|---|---|
| `juliusbrussee/caveman` | Three-layer anti-drift architecture, mode/level system, flag-file persistence, eval discipline | Caveman voice, compression goal, token-savings framing |
| gist `L1nefeed/4164ecaaf77879e76dca3c06f142f1c2` | The four-target Scope model, "accuracy wins over style", the standard-verb table | Its stale Issue-8 terminology, its lack of enforcement |
| `woosal1337/blog` ep01 | `ste-lint.py` as a reference implementation for the checker | Its experiment framing and headline claims |

ASD-STE100 Issue 9 is **prior art and design authority**, not a dependency. We cite it
the way an RFC cites its influences. We do not redistribute it, extend it, or claim
conformance to it.

## 3. Hard constraints

**Copyright.** ASD owns ASD-STE100; it is also EU trademark 017966390. Issue 9 retains:
"Unauthorized distribution of ASD-STE100, direct or through different websites or
portals, is strictly prohibited without written permission from the STEMG." Free
reproduction is granted to 8 named categories (aerospace/defence bodies, airworthiness
authorities, universities for educational purposes). We are in none.

**Writing our own standard is the resolution, not a workaround.** PSTE is an original
specification for a different domain. Software communication is not aircraft
maintenance: our readers are different, our nouns are different, our procedures are
different. ASD's dictionary approves *rivet*, *fuselage*, and *aileron*, and has no
entry for *mutex*, *rollback*, or *idempotent*. A derived work would be both legally
awkward and technically worse.

Rules for staying clean:
- **Write original rule text.** Do not paraphrase ASD's rule statements sentence by
  sentence. Derive the *ideas* — controlled vocabulary, one word one meaning, active
  voice, sentence caps — which are decades-old common practice in controlled English
  and not ASD's invention. Express them in our own words, our own numbering, our own
  structure.
- **Build the word list from software corpora**, not by transcribing ASD's dictionary.
  Method in §5 below. Overlap on common English verbs (*use*, *start*, *remove*) is
  unavoidable and unproblematic — those are English, not ASD's property.
- **Ship no PDF, no extracted spec text, no dictionary extract.** Link to ASD's free
  download for readers who want the aerospace original.
- **Do not claim conformance to, or endorsement by, ASD or STEMG.** Do not use the
  ASD-STE100 name as our product name — it is EU trademark 017966390. Cite it in a
  "Prior art" section as an influence.
- Keep the extracted Issue 8/9 text in the scratchpad as **research only**. It never
  enters the repo.

**Self-contained.** No PDF dependency at runtime, per requirement. Writing our own
standard satisfies this by construction.

## 4. Design input from ASD-STE100 Issue 9

Issue 9 (2025-01-15) is the current version and supersedes the Issue 8 PDF on hand. All
three source projects work from stale terminology. Where we borrow *ideas*, borrow the
current ones:

- ASD renamed `technical name` → **`technical noun`** for ISO 1087:2019 alignment. Our
  equivalent concept should use current terminology, not the dead term.
- Their Section 2 is now "Multi-word nouns" with 2 rules; the article rule moved to 4.5.
- General Recommendations grew to GR-1..GR-8, adding inclusive language and possessive form.

**The load-bearing observation for PSTE:** Issue 9's technical-noun category 19 is now
*"Computer science, information and communication technology"* and lists *AI, large
language model, machine learning, prompt engineering, hallucination, token, metadata,
cybersecurity, database, operating system*. Its technical-verb category 2 covers
*debug, boot, install, deploy, download, upload, reboot, validate, encrypt*.

This tells us two things. First, the controlled-English approach demonstrably extends
to software vocabulary — the aerospace body itself concluded so in 2025. Second, they
extended it only far enough to describe *using* computers, not *building* software.
There is no *refactor*, *merge*, *deploy*, *roll back*, *deprecate*, *mock*, *lint*.
**That gap is exactly what PSTE fills.** We are not competing with Issue 9; we are
covering the domain it stops short of.

## 5. The PSTE standard — `spec/PSTE-1.md`

The centerpiece. An RFC-style specification, versioned, normative.

### 5.1 Normative language

RFC 2119 / RFC 8174 keywords, with the standard boilerplate:

> The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT,
> RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described
> in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals.

Every rule carries a keyword and a stable identifier. Conformance is checkable and
citable — a linter finding says `PSTE-V3` and a reader can look it up.

### 5.2 Document structure

```
PSTE-1.md
  1. Introduction              purpose, non-goals, the readability claim
  2. Terminology               conformance vocabulary, "approved word", "term"
  3. Conformance               levels 1/2/3, what "conforms" means, how to claim it
  4. Scope of application      the four targets (§6) — what PSTE governs
  5. Vocabulary rules          V1..Vn   approved words, one meaning, one verb
  6. Term rules                T1..Tn   the escape hatch for software vocabulary
  7. Grammar rules             G1..Gn   voice, tense, verb forms
  8. Sentence rules            S1..Sn   length, one instruction, no omission
  9. Structure rules           D1..Dn   paragraphs, lists, lead-with-result
 10. Procedure rules           P1..Pn   imperative, conditions, notes vs instructions
 11. Warning rules             W1..Wn   destructive/irreversible operations
 12. Punctuation rules         X1..Xn   semicolon, hyphen, parentheses
 13. Recommendations           R1..Rn   non-normative guidance
 14. Prior art                 ASD-STE100, Basic English, Plain Language Act, Orwell
 15. Change log
Appendix A  Approved word list (normative)
Appendix B  Term categories for software (normative)
Appendix C  Not-approved words and their approved alternatives (informative)
Appendix D  Conformance test cases
```

Rule ID prefixes are mnemonic and stable across versions. A retired rule keeps its ID
and gets marked withdrawn — never reused, per normal standards practice.

### 5.3 Rules PSTE needs that aerospace does not

The domain gap justifies the whole project. Draft candidates:

- **Identifiers are never inflected.** `PSTE-T?`: refer to `getUser` as "the `getUser`
  function", never "getUsering" or "we getUser the record". MUST.
- **One name per entity, matching the code.** If the code calls it `orderId`, prose
  calls it "the order ID" — not "the order identifier", "the ID", or "the order key". MUST.
- **Version and path strings are quoted verbatim and count as one word.** SHOULD.
- **State the destructive scope before the command.** "This deletes every row in
  `users`. Run the backup first." not the reverse order. MUST for irreversible ops.
- **Distinguish the four modal meanings** that wreck technical prose: capability
  ("the API can"), permission ("you may"), obligation ("you must"), and probability
  ("this is likely to"). Never use "should" for capability. MUST.
- **Name the actor for every action.** "The linter rejects the file", not "the file is
  rejected". Software has too many candidate actors — user, agent, CI, runtime — for
  the passive to be recoverable. MUST.
- **Error text and log lines are quoted, never paraphrased.** MUST.
- **Uncertainty is stated once, explicitly, and never hedged twice.** "I did not test
  this." not "this might possibly work, but I'm not entirely sure". MUST.

That last one matters more than it looks: stacked hedging is the single most common
readability failure in agent output, and it is a *precision* problem, not a style
problem. One clear statement of uncertainty is more honest than three vague ones.

### 5.4 Building the ~900-word vocabulary — method

Original construction, not transcription. Reproducible and documented in
`spec/METHOD.md` so the provenance is defensible:

1. **Seed from public-domain frequency data.** General English core from a public
   frequency list (e.g. Google Books n-grams, SUBTLEX, or the public-domain GSL) —
   these are data, not ASD's dictionary.
2. **Add a software corpus layer.** Mine high-frequency prose terms from permissively
   licensed technical writing: Python/MDN/Rust/Kubernetes docs, RFCs, Git man pages.
   Take the top nouns and verbs that survive a stopword and identifier filter.
3. **Collapse synonym clusters by hand.** For each cluster, pick one approved word and
   list the rest as not-approved alternatives. This is the labour and the value:
   `check` over verify/confirm/validate/inspect; `start` over initiate/launch/commence;
   `remove` over eliminate/strip/purge — while keeping `delete` where it names a literal
   operation, since precision beats consistency.
4. **Assign one meaning per approved word.** Where a word carries two common senses,
   approve one and route the other to a different word.
5. **Tag part of speech and permitted forms**, so the linter can enforce "approved as a
   verb, not as a noun".
6. **Target ~900 approved entries** plus a not-approved cross-reference list. Size is a
   target, not a quota — stop when coverage is good, not when the count is round.

Entry format, machine-readable, `spec/wordlist.yaml` as the source of truth with the
Markdown appendix generated from it:

```yaml
- word: check
  pos: verb
  meaning: To look at something to find out if it is correct or present.
  forms: [check, checks, checked]
  instead_of: [verify, confirm, validate, inspect, ensure]
  example: "Check that the service is running."
  counter_example: "Verify the service status."
```

One source of truth, two consumers: the linter reads the YAML, the spec appendix is
generated. No hand-sync drift.

### 5.5 Term categories — the software escape hatch

A controlled vocabulary that cannot name a `Deployment` is useless. `spec/PSTE-1.md`
§6 defines **terms**: words outside the approved list that a writer MAY use when they fall
into a named category. Our categories, drafted for software:

1. Identifiers from code — symbol, file, path, package, branch, environment variable
2. Languages, runtimes, frameworks, and tools
3. Protocols, formats, and encodings
4. Infrastructure and platform nouns — container, cluster, queue, bucket, region
5. Data and storage nouns — index, shard, migration, schema, transaction
6. Version control and delivery — commit, branch, merge, rebase, tag, release, rollback
7. Testing and quality — fixture, mock, stub, coverage, flake, regression
8. Observability — log, trace, span, metric, alert, dashboard
9. Security — credential, token, secret, certificate, scope, principal
10. Units, quantities, and time — byte, millisecond, percentile, rate limit
11. Quoted UI, CLI, and error text
12. Organizations, standards bodies, and named specifications

Plus **term verbs** for software actions with no plain-English equivalent: *deploy,
merge, rebase, refactor, mock, lint, cache, serialize, throttle, roll back*. Each
constrained by the same discipline ASD applies: if an approved word says it accurately,
use the approved word. Do not coin a term where plain English works.

## 6. Levels

Conformance levels, defined in the spec §3 and implemented by the skill:

| Level | Name | Behavior |
|---|---|---|
| 1 | `lite` | Grammar and slop rules only. Remove marketing adjectives, hedges, filler, nominalizations, phrasal verbs. Vocabulary unconstrained. Normal sentence length. |
| 2 | `pste` **(default)** | Level 1, plus: active voice with named actor, simple tenses only, one word one meaning, one action one verb, 20/25-word caps, no contractions, no semicolons, multi-word nouns max 3, lead with the result. Vocabulary guided, not enforced. |
| 3 | `strict` | Level 2, plus: **approved word list enforced**, one instruction per sentence, vertical lists for 3+ steps, notes separated from instructions, warnings lead with the command or condition. For runbooks, procedures, release notes, error text, and published docs. |
| — | `off` | Normal prose. |

A document claiming conformance MUST state its level, e.g. "Conforms to PSTE-1 Level 2".

## 7. Scope model — what PSTE applies to

Spec §4. Four targets, one rule each. Adopted from the gist, which got this right:

1. **Prose the agent writes itself** — answers, summaries, status updates, explanations,
   instructions. **PSTE applies.**
2. **Code, commands, file paths, identifiers, error strings, API names** — reproduce
   verbatim. PSTE never applies.
3. **Quoted text from files, docs, or tool output** — reproduce verbatim.
4. **Code comments and commit messages** — match the repository's existing style.

Overriding rule: **accuracy beats style.** Never drop a fact, condition, number, or scope
qualifier to satisfy a word cap. If a rule and precision conflict, keep precision and
split the sentence instead. The spec MUST state this rule, because it
is the rule that stops a controlled vocabulary from degrading correctness.

Two deliberate divergences from aerospace practice, documented in "Prior art":
- **Permit the pronoun `I`.** ASD's GR-3 disapproves it; an agent reporting its own
  actions needs it, and "the agent updated the file" is worse, not better.
- **Permit Markdown structure.** Headings, fenced code, tables, and lists are part of
  how software prose is read. ASD-STE100 predates all of it.

## 8. Deliverables

```
spec/
  PSTE-1.md                  THE STANDARD. RFC-style, MUST/SHOULD/MAY, stable rule IDs
  wordlist.yaml              source of truth: ~900 approved words, one meaning each
  terms.yaml                 term categories + term verbs for software
  METHOD.md                  how the wordlist was built, for provenance
  conformance/*.md           test cases: conforming and non-conforming pairs per rule
skill/
  SKILL.md                   the prompt: levels, scope, rules, examples, boundaries
  hooks/pste-activate.js     SessionStart — reads SKILL.md live, injects active level
  hooks/pste-tracker.js      UserPromptSubmit — parses /pste, writes flag, per-turn anchor
  hooks/pste-config.js       shared: flag read/write, level resolution, atomic writes
  commands/pste.md           /pste [lite|pste|strict|off]
  commands/pste-lint.md      /pste-lint [paths]
lib/
  pste_lint.py               deterministic checker, stdlib only, reports by rule ID
  build_appendix.py          wordlist.yaml -> spec appendix, no hand-sync drift
evals/
  run.py                     3-arm harness
  measure.py                 scores via pste_lint, medians per arm
  snapshots/results.json     committed, CI reads offline, no API calls
README.md                    goal-first: readability, not smarter output. FAA citation.
```

## 9. Anti-drift architecture

Copied from caveman because it is the part that measurably works. Their own code
comments record that a two-sentence summary let models drift back to verbose
mid-conversation, especially once context compaction pruned it.

- **Layer 1 — SessionStart.** `pste-activate.js` reads `SKILL.md` off disk at runtime,
  strips frontmatter, filters the level table down to the active level, emits as stdout.
  Claude Code injects that as system context. Reading live means the hook can never
  drift out of sync with the documented rules.
- **Layer 2 — UserPromptSubmit.** `pste-tracker.js` injects a short anchor every turn:
  active level, the three or four load-bearing rules, and the scope boundary. Cheap,
  and survives competing style instructions from other plugins.
- **Layer 3 — flag file.** Level persists in `$CLAUDE_CONFIG_DIR/.pste-active`, so it
  survives context compaction and new sessions. Atomic write, symlink-refused, whitelist
  validated on read. Silent-fail on all filesystem errors: a hook MUST NOT block
  session start.

## 10. The linter

Rebuild, do not fork. woosal's `ste-lint.py` is a slop-smell detector with ~100
hardcoded words. Ours checks PSTE rules and **reports by rule ID**, so every finding is
citable against the spec.

- Reads `spec/wordlist.yaml` and `spec/terms.yaml` — no duplicated word lists in code.
- Strips fenced and inline code before analysis. Non-negotiable; target 2 in §7.
- Checks: sentence caps, contractions, semicolons, passive with recoverable actor,
  non-simple tenses and auxiliary stacks, `-ing` main verbs, nominalizations, phrasal
  verbs, multi-word nouns over 3, paragraph caps, same-entity-named-two-ways, stacked
  hedging, Latin abbreviations, marketing adjectives, and level-3 vocabulary violations
  with the approved alternative named in the message.
- Output: compact table or JSON, counts per 100 words, each finding tagged `PSTE-G2` etc.
- Exit non-zero on findings at or above a `--level`, so it works as a pre-commit hook.

Runnable check per ponytail: `python3 lib/pste_lint.py --self-test` with assert-based
cases drawn from `spec/conformance/`. One case per rule, conforming and non-conforming.
No framework. **The conformance cases are the spec's test suite and the linter's test
suite at once** — if they disagree, one of them is wrong, and that is the point.

## 11. Evals — honest by construction

Caveman's key discipline: **the honest delta is skill vs a plain "be concise" control,
never skill vs an unprompted baseline**, because baseline-vs-skill conflates the skill
with the generic terseness ask and inflates the number.

Three arms:
| Arm | System prompt |
|---|---|
| `baseline` | none |
| `control` | "Answer concisely and clearly." |
| `pste` | "Answer concisely and clearly." + SKILL.md |

Scored by `pste_lint.py`. Report median violations/100w per arm, per level.

State the limitation in `evals/README.md` rather than hiding it: this measures **rule
conformance, not readability and not quality**. The checker counts what the prompt
forbids, so a good score is necessary but not sufficient. It cannot tell you the text is
true, useful, or actually easier to read. Say so plainly, the way caveman notes that a
skill replying "k" to everything would score -99% and "win".

Since the project goal is readability, the eval that would actually test the claim is a
human one: comprehension or preference on matched pairs. Out of scope for the spike.
Note it as future work rather than implying the linter covers it.

## 12. Build order — spike

Phases 1–4 are the spike. Stop there, use it, decide if it earns the rest.

1. **`spec/PSTE-1.md` skeleton** — normative language, conformance levels, scope model,
   and the rule sections with IDs. Rules drafted, examples thin. This is the artifact
   everything else derives from, so it goes first even though it is the slowest.
2. **`spec/wordlist.yaml` v0** — ~200 entries covering the highest-frequency synonym
   clusters, not the full 900. Enough to prove the format and the linter integration.
   Full corpus build comes later if the spike holds.
3. **`skill/SKILL.md`** — levels, scope, rules, worked before/after examples, boundaries.
4. **`lib/pste_lint.py`** + self-test against `spec/conformance/`.

Then, if it holds up in real use:

5. Hooks, commands, flag file.
6. Wordlist to full ~900 via the §5.4 corpus method.
7. `evals/` + committed snapshot.
8. `README.md`, prior-art section, publication decision.

## 13. Open questions for Sherman

- **Name.** `PSTE` / "Programming Simplified Technical English" is descriptive but sits
  close to ASD's trademarked `ASD-STE100` / "Simplified Technical English". A distinct
  name would be safer and more memorable if this ever goes public. Worth deciding before
  the spec header is written, since the rule IDs bake it in.
  -- Name is good
- **Distribution.** Personal, or public repo? Public is cleaner for an original standard,
  and the "Prior art" framing is the right posture either way.
  Priot art and a md file is a good thing to have, lets paste our sources, but list the ASD-STE100 as an inspiration not a source, ironcially while a llm found a copy of the latest spec we can't reference it directly 
- **Level 3 auto-selection.** Should `strict` engage automatically for known artifact
  types (release notes, runbooks, error text, published docs), or always manual?
  Yes it should, but users can configure it 
- **Linter as pre-commit** in your own repos, or standalone for now?
Linter should be something that can just run, like a go project that is a single bin release so users can hook up, we can include a pre-commit in this repo for usage however
