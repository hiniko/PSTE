# PSTE-1: Programming Simplified Technical English

**Version:** 1.0.0-draft
**Date:** 2026-08-02
**State:** Draft

---

## 1. Introduction

### 1.1 Purpose

PSTE is a controlled form of English for software communication. It restricts
vocabulary, grammar, and sentence organization. The restriction has one purpose: to make
technical prose **easier to read, and easier to share with other people**.

PSTE aims at the conditions software prose meets. A reader may be tired, or hurried, or
reading a second language. A reader may meet the text away from the page it came from,
as an excerpt in a chat window or a ticket. Nobody has yet measured how often those
conditions hold, or what PSTE does for a reader under them.

### 1.2 Non-goals

This specification makes **no claim** that controlled English improves the correctness,
the reasoning, or the substance of what a writer says. It does not. PSTE governs the
*form* of prose only.

A conforming document can be wrong. A conforming document can be useless. PSTE governs
the form of a document. It cannot make a hollow paragraph true. An implementation
`MUST NOT` claim that conformance to PSTE improves the accuracy of content.

PSTE is also not a rule set for compression. Conforming text is often shorter than its
source, but this is a result and not a goal. Rule PSTE-A1 (§5.5) states that accuracy
always defeats brevity.

### 1.3 Applicability

PSTE applies to prose about software: documentation, README files, pull request
descriptions, commit bodies, release notes, error messages, runbooks, postmortems,
code review comments, and the output of software agents.

PSTE does not apply to code. It does not apply to marketing copy, essays, tutorials
that use narrative, or any text that needs a voice. PSTE removes voice deliberately.

### 1.4 Evidence

Controlled English improves comprehension for human readers. Chervak, Drury and
Ouellette (1996) tested 175 aircraft technicians on maintenance procedures. See
[CHERVAK](#16-references). Comprehension
increased from 76% to 86% with controlled-English text. For readers whose first language
was not English, comprehension increased from 69% to 87%.

That study examined aerospace text, human authors, and human readers. It supports the
readability claim in §1.1. It does not measure software text, and it does not measure
machine-generated text. No study known to the editors measures those conditions.

---

## 2. Conformance language

The key words `MUST`, `MUST NOT`, `REQUIRED`, `SHALL`, `SHALL NOT`, `SHOULD`, <!-- pste-lint: ignore -->
`SHOULD NOT`, `RECOMMENDED`, `MAY`, and `OPTIONAL` in this document are to be <!-- pste-lint: ignore -->
interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear <!-- pste-lint: ignore -->
in all capitals, as shown here. <!-- pste-lint: ignore -->

### 2.1 How to write a rule

These requirements apply to this document, and to any document that states rules with
these key words.

**PSTE-K1**: A writer `MUST` negate a key word only with the word "NOT", and only in the
forms `MUST NOT`, `SHALL NOT`, and `SHOULD NOT`.

*Weight: 0.5.* `MUST` rule governing how a rule is written: a key word negated the
wrong way is a form fault in stating the requirement, not in its content.

`MUST`, `SHALL`, and `SHOULD` mark an action to take. `MUST NOT`, `SHALL NOT`, and
`SHOULD NOT` mark an action to avoid. No other construction carries the meaning.

`MAY` states a permission, so it has no negated form. To forbid an action, use
`MUST NOT`. To state that an action is unnecessary, use `MAY` on the option.

Write "A writer `MUST NOT` use a semicolon". Do not write "A writer `MUST` never use a <!-- pste-lint: ignore -->
semicolon", "A writer `MUST` avoid semicolons", or "Nobody `MUST` use a semicolon". Each <!-- pste-lint: ignore -->
of those reads as an obligation to do something, and the last states an obligation on a
subject that does not exist.

The rule covers every key word, in either shape:

| Shape | Key words | Negate as |
|---|---|---|
| Modal | `MUST`, `SHALL`, `SHOULD`, `MAY` | `MUST NOT`, `SHALL NOT`, `SHOULD NOT` |
| Adjectival | `REQUIRED`, `RECOMMENDED`, `OPTIONAL` | rewrite with a modal key word |

An adjectival key word has no negated form. `NOT REQUIRED` is not a BCP 14 form: it
reads as a missing obligation, which is what `MAY` already states. Write "A writer `MAY`
omit the heading", not "A heading is `NOT REQUIRED`". <!-- pste-lint: ignore -->

The word `NOT` `MUST` appear in capitals. `MUST not` reads as ordinary prose, and a
reader cannot tell a requirement from a description.

**PSTE-K2**: A writer `MUST` name the actor that a rule binds, and `MUST` place that
actor before the key word.

*Weight: 0.5.* `MUST` rule governing how a rule is written: an unnamed actor is a form
fault in the rule statement.

A rule binds somebody to an action. Write "A writer `MUST` keep every number". Do not
write "Every number `MUST` be kept", because that names no actor and uses the passive <!-- pste-lint: ignore -->
voice, which rule PSTE-G1 already forbids.

The same fault appears with an adjectival key word. Write "A writer `MUST` name the
actor", not "The actor is `REQUIRED` to be named". Write "A writer `MAY` omit the <!-- pste-lint: ignore -->
heading", not "A heading is `OPTIONAL`". <!-- pste-lint: ignore -->

**PSTE-K3**: A writer `MUST NOT` use a key word for a statement of fact. A key word
states a requirement.

*Weight: 0.5.* `MUST` rule governing how a rule is written: a key word used for a fact
instead of a requirement is a type fault in form.

Write "A writer `MAY` write a warning that is longer than the limit". Do not write "A
warning `MUST NOT` be subject to the limit", because a warning is not an actor and <!-- pste-lint: ignore -->
cannot obey a rule.

> **Note.** `SHALL`, `SHALL NOT`, `REQUIRED`, `RECOMMENDED`, and `OPTIONAL` are valid
> BCP 14 key words, and this section keeps them valid. A writer `SHOULD` use `MUST`,
> `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` instead, because five key words are
> easier to hold in mind than ten, and the others add no meaning.

---

## 3. Terminology

**approved word**
: A word listed in Appendix A. An approved word has exactly one approved meaning and one
  approved part of speech in PSTE text.

**not-approved word**
: A word listed in Appendix C with one or more approved alternatives. §7 states when a
  writer may use one.

**term**
: A word or multi-word name that is not in Appendix A, and that names something in
  software that plain English cannot name accurately. No list of terms is complete,
  so PSTE-V1 leaves the judgement to the writer.

**term noun**
: A term used as a noun. Example: `container`, `pull request`, `certificate`.

**term verb**
: A term used as a verb. Example: `deploy`, `merge`, `refactor`.

**identifier**
: A name taken from source code, configuration, or a command line. Examples: `getUser`,
  `--dry-run`, `PATH`, `src/main.rs`.

**agent**
: The writer of the text. A person or a program.

**actor**
: The entity that does an action that the text describes. Examples: the user, the
  compiler, the test runner, the deployment pipeline.

**author prose**
: Text that the agent composes. §5 defines this precisely and separates it from quoted
  text and from code.

**instruction**
: A sentence that tells the reader to do something. Instructions use the imperative form.

**description**
: A sentence that gives information and does not tell the reader to do something.

---

## 4. Rule weight

### 4.1 Why a weight exists

A count of findings alone treats a dropped negation and a missing hyphen as one fault
each. That measures nothing useful.

A writer who removes a condition sends the next reader down the wrong path. A writer
who omits a hyphen costs that reader one extra glance at the sentence. The two faults
do not cost a reader the same thing.

PSTE-A1 already ranks these faults against each other. It states that accuracy
defeats every other rule in this specification. §4.2 turns that ranking into a
number a tool can use.

### 4.2 What the number means

Each rule in this specification carries a weight from 0 to 1. The weight states the
consequence when a writer violates the rule once. The scale is normalized, so the
most serious violation a document can carry is 1.

| Weight | Meaning |
|---|---|
| 1.0 | A fact, condition, number, unit, or scope qualifier is gone. PSTE-A1 states that this defeats every other rule. |
| 0.8 | A reader acts on the faulty text, and is harmed when it is wrong: a missing warning, a miscopied quote, an inflected identifier. |
| 0.5 | A `MUST` rule on the form of the prose: grammar, sentence and paragraph limits, procedure structure, how a rule itself is written. The meaning survives; the form does not. |
| 0.3 | A vocabulary rule. An unapproved word is usually understood. The fault is rotation or convention, not lost meaning. |
| 0.1 | A `SHOULD` rule, or a punctuation rule. The standard's own key word, or its own note, already marks these as the weakest rules in this specification. |
| N/A | A rule that states a permission only (`MAY`), with no obligation a writer can fail. No action breaks such a rule, so it carries no weight. |

A weight of 1.0 is not twice as bad as 0.5. The scale is ordinal: a higher number is
a worse fault, and the bands group faults of comparable consequence. §4.4 states how
a tool uses the number.

### 4.3 The weights are normative

The weight of each rule is part of this specification. A tool that reports a weighted
measure `MUST` use the weight
this specification states for each rule. A tool `MUST NOT` assign its own weight to a
rule that this specification weights.

### 4.4 How a tool uses the weight

A tool `MAY` compute a weighted sum of findings, by adding each finding's rule weight
instead of adding one per finding. A maintainer uses the sum to compare documents, or
to compare a change.

---

## 5. Scope of application

### 5.1 The four targets

Every part of a document falls into one of four targets. Each target has one rule.

| Target | Content | Rule |
|---|---|---|
| **T1 — author prose** | Explanations, summaries, instructions, status reports, descriptions | PSTE applies in full |
| **T2 — code and literals** | Code, commands, file paths, identifiers, error strings, API names, configuration | Reproduce verbatim. PSTE does not apply |
| **T3 — quoted text** | Text copied from a file, a document, a specification, or tool output | Reproduce verbatim. PSTE does not apply |
| **T4 — repository text** | Code comments and commit messages inside a repository | Match the style of the repository |

**PSTE-S1**: A writer `MUST` apply the rules of this specification to target T1 only.

*Weight: 0.5.* `MUST` rule governing scope of application: applying PSTE rules outside
target T1 is a scope fault, not a content fault.

**PSTE-S2**: A writer `MUST` reproduce T2 and T3 content character for character. A
writer `MUST NOT` correct the spelling, the grammar, or the style of quoted text.

*Weight: 0.8.* A writer `MUST` reproduce quoted text and code character for character.
The reader acts on this text as given, and a silent change is harder to detect than an
obvious one.

**PSTE-S3**: When a writer quotes text that does not conform to PSTE, the writer
`MUST NOT` mark the quoted text as a conformance failure.

*Weight: 0.5.* `MUST` rule governing how non-conforming quotes are marked: mislabelling
a quote as a conformance failure is a fault in how the writer treats T3 content, not a
change to the quote.

### 5.2 Identifiers inside prose

**PSTE-S4**: A writer `MUST NOT` inflect an identifier. Write "the `getUser` function
returns a record", not "getUsering the record" or "we getUser the record".

*Weight: 0.8.* An inflected identifier is no longer the literal string the reader must
use verbatim against code or a command line. A reader who trusts it acts on a name that
does not exist.

**PSTE-S5**: A writer `SHOULD` set an identifier in a code span when the output format
supports one.

*Weight: 0.1.* `SHOULD` rule: a missing code span is a formatting preference. The
identifier text itself is unchanged.

### 5.3 Structural markup

**PSTE-S6**: A writer `MAY` use headings, lists, tables, code blocks, and code spans.
A reader of software prose depends on this organization.

*Weight: N/A.* PSTE-S6 is `MAY` only, a permission with no obligation. There is no
action a writer can take that breaks it.

### 5.4 The first person

**PSTE-S7**: A writer `MAY` use the pronoun "I" to report the writer's own actions.
Write "I changed the file", not "the agent changed the file".

*Weight: N/A.* PSTE-S7 is `MAY` only, a permission with no obligation. There is no
action a writer can take that breaks it.

> **Note.** This diverges from aerospace practice, which disapproves the first person.
> An agent that reports its own work needs to name itself, and the alternative
> constructions are less clear, not more.

### 5.5 Accuracy defeats style

**PSTE-A1**: A writer `MUST` keep every fact, condition, number, unit, and scope
qualifier that the text states. A writer `MUST NOT` remove one to satisfy a length limit
or a vocabulary limit. This rule defeats every other rule in this specification.

*Weight: 1.0.* PSTE-A1 states it defeats every other rule in this specification. Losing
a fact is the one fault this specification ranks above all others.

When a rule and precision conflict, the writer `MUST` keep the precision. The writer
`SHOULD` then split the sentence, or add a sentence, to satisfy the rule.

> This rule exists because a controlled vocabulary can degrade correctness if a writer
> applies it mechanically. A shorter sentence that omits a condition is a defect, not a
> conformance success.

### 5.6 Brevity is not optional

PSTE-A1 protects facts. It does not protect words. A writer who invokes PSTE-A1 to keep
text that states no fact inverts the rule. The result is the failure that PSTE-L2 and
§10 exist to prevent.

**PSTE-A2**: Before a writer exceeds a limit under PSTE-A1, the writer `MUST` find
the item that the limit would remove. The writer `MUST` name that item as an exact
fact, condition, number, unit, or scope qualifier. When the writer cannot name that
item, PSTE-A1 does not apply and the limit stands.

*Weight: 1.0.* PSTE-A2 exists only to test whether PSTE-A1 applies. Failing it means a
fact was removed without the check that PSTE-A1 requires.

**PSTE-A3**: A writer `MUST` first try to satisfy the rule and keep the precision. A
writer `SHOULD` split the sentence, and `MUST` exceed a limit only when no division of
the text keeps every item and meets the limit.

*Weight: 1.0.* PSTE-A3 exists only to keep PSTE-A1's precision intact before a limit is
allowed to win. Failing it means the writer lost precision that a split sentence keeps.

> Almost every conflict between accuracy and a length limit is false. A sentence of 30
> words that states two facts becomes two sentences of 15 words, and both facts survive.
> PSTE-A3 makes the split the first action and the exemption the last one.

#### 5.6.1 When the balance tips

A writer `MAY` exceed a limit in these cases only:

| Case | Rule | Why the limit yields |
|---|---|---|
| A warning states a risk | PSTE-W5 | A short warning that omits the scope of the damage is a defect |
| A condition has several parts | PSTE-A1 | A split can invert the logic of a condition |
| A list must be exhaustive | PSTE-D7 | A short list of options reads as a complete list |
| The reader asks again | PSTE-L3 | A repeated question reports that the first answer failed |

In every other case the limit applies.

> **Note.** The rule is constant. The frequency of the exception is not. A runbook holds
> the limit, because an operator reads it under time pressure and needs the next command.
> A design record yields more often, because a reader returns to it and needs the reasons.
> A writer who claims the second case for every document has stopped applying PSTE-A2.

---

## 6. Clarity rules

**PSTE-L1**: A writer `MUST NOT` state uncertainty more than once about the same claim.
Write "I did not test this." Do not write "this might possibly work, but I am not
entirely certain".

*Weight: 0.5.* `MUST` rule governing clarity: stacked hedging is a fault of precision
in expression. The standard says it tells the reader less, not a removed fact.

> Stacked hedging is the most common readability failure in machine-generated prose.
> It is a precision failure and not a style failure: three vague qualifiers tell the
> reader less than one clear statement.

**PSTE-L2**: A writer `MUST NOT` add text that carries no information. This includes
openings that restate the question, closings that repeat the body, and transitions that
announce what the writer is about to do.

*Weight: 0.5.* `MUST` rule governing clarity: filler text carries no information by the
rule's own wording, so removing it loses nothing.

**PSTE-L3**: A writer `MUST` state the result before the explanation. The first
sentence of a response answers the question or reports what happened.

*Weight: 0.5.* `MUST` rule governing order: stating the explanation before the result
is a sequencing fault. The fact itself is still present.

**PSTE-L4**: A writer `MUST NOT` state the same fact twice in one document. A writer
`MAY` repeat a fact in a warning, because a reader who skips a section still needs the
risk.

*Weight: 0.5.* `MUST` rule governing clarity: the same fact stated twice is redundant,
not lost. The second statement is the fault, not the first.

> PSTE-L2 covers a closing that repeats the body. PSTE-L4 covers the wider case: the same
> fact in two paragraphs, in different words, is still one fact. A reader who meets it
> twice must decide whether the second statement adds something. It does not.

**PSTE-L5**: A writer `MUST NOT` open with a phrase that announces the response, and
`MUST NOT` close with a phrase that offers further help. Appendix C lists the phrases.

*Weight: 0.5.* `MUST` rule governing clarity: a frame phrase states no fact by the
rule's own wording, so it has nothing to lose.

> Examples of an opener to remove: "Great question", "Let me look into that", "To answer
> your question". Examples of a closer to remove: "Let me know if you need anything else",
> "Hope this helps", "Feel free to ask".
>
> These phrases are frames and not content. A reader who wants the answer reads past them,
> and a reader in a hurry reads the frame and stops.

---

## 7. Vocabulary rules

The rules in this section are `MUST`.

**PSTE-V1**: A writer `MUST` use a word from one of these three sets:
- An approved word from Appendix A
- A term, as §3 defines one
- An identifier, quoted under §5.2

*Weight: 0.3.* `MUST` rule on word choice: an out-of-set word is understood by the
reader, just not the approved form PSTE-V2 assigns it.

A writer decides whether a word is a term. The test is what the word does, and not
whether a list names it. A term names something in software that plain English cannot
name accurately, and the reader of THIS document already knows it.

`mempool` is a term in a Chia document. `leverage` is not a term anywhere, because
`use` says it.

> An earlier draft answered the question with a list of fifteen categories and their
> example words. The list could not work, and its own header said so: the examples
> were "illustrative, not exhaustive". A writer who checked a word against it learned
> nothing about `mempool`, `clvm`, or `gopls`, which are ordinary vocabulary in the
> projects that use them.
>
> A list reaches the common core of a domain and stops. The tail is where the
> judgement is needed, and a list never arrives there. A separate, non-normative
> lookup still holds the common core, because a tool needs one to stop reporting
> `cache` and `latency` as unusual. A word absent from that lookup is not thereby
> forbidden.

**PSTE-V2**: A writer `MUST` use an approved word only with the meaning given in
Appendix A, and only as the part of speech given in Appendix A.

*Weight: 0.5.* `MUST` rule governing meaning: an approved word used with the wrong
meaning or part of speech breaks the one-word-one-meaning guarantee PSTE-V1 relies on.

**PSTE-V3**: A writer `MUST` use one word for one meaning throughout a document. A
writer `MUST NOT` use two approved words for the same action or the same object.

*Weight: 0.3.* `MUST` rule on word choice: the rule's own example shows synonyms the
reader already understands. The fault is rotation, not lost meaning.

> Example. Select `check` and use it in every place. Do not alternate between `check`,
> `verify`, `confirm`, and `validate`. The reader of a rotating vocabulary must decide
> whether each new word signals a new meaning. It usually does not, and the decision
> costs the reader time.

**PSTE-V4**: A writer `MUST` use one name for one entity, and that name `MUST` match
the name in the code. If the code declares `orderId`, the prose says "the order ID".
The prose `MUST NOT` say "the order identifier", "the order key", or "the ID" for the
same value.

*Weight: 0.5.* `MUST` rule governing identity: a renamed entity forces the reader to
match two names to the same thing in the code, a precision fault PSTE-V1 alone does not
cover.

**PSTE-V5**: A writer `MUST NOT` use a term when an approved word states the meaning
accurately. A writer `MUST NOT` coin a term where plain English works.

*Weight: 0.3.* `MUST` rule on vocabulary: a coined term where an approved word already
states the meaning accurately is the vocabulary fault PSTE-V1 targets.

**PSTE-V6**: A writer `MUST NOT` use a term noun as a verb, and `MUST NOT` use a term
verb as a noun. Write "I made a deployment" or "I deployed the service". Do not write
"I did a deploy".

*Weight: 0.3.* `MUST` rule on vocabulary: a term noun used as a verb, or the reverse,
is understood from context. The part of speech is the only fault.

**PSTE-V7**: A writer `MUST` use American English spelling.

*Weight: 0.3.* `MUST` rule on vocabulary: British and American spellings name the same
word, so the fault is convention, not meaning.

**PSTE-V8**: A writer `MUST NOT` use a Latin abbreviation. Replace `e.g.` with "for
example", `i.e.` with "that is", and `etc.` with a complete list or with "and others".

*Weight: 0.3.* `MUST` rule on vocabulary: a Latin abbreviation is understood by most
readers. The rule exists for the reader who is not one of them, not because meaning is
lost.

**PSTE-V9**: A writer `MUST NOT` use marketing adjectives. Appendix C lists them.
Examples: `seamless`, `robust`, `powerful`, `blazing`, `elegant`, `effortless`.

*Weight: 0.3.* `MUST` rule on vocabulary: a marketing adjective such as `robust` or
`seamless` states an opinion the reader discounts, not a fact the reader loses.

**PSTE-V10**: A writer `MUST` distinguish the four modal meanings and `MUST NOT` use
one modal verb for another meaning:

| Meaning | Use | Do not use |
|---|---|---|
| Capability | can | should, is able to |
| Permission | may | can, is allowed to |
| Obligation | must | should, needs to, is required to |
| Probability | is likely to | should, could |

*Weight: 0.5.* `MUST` rule governing meaning: the four modal meanings are genuinely
different, so the wrong modal verb can flip what a sentence requires. A precision fault
closer to form than to vocabulary.

> "The service should restart" is ambiguous. It can mean the service is capable of
> restarting, the operator is obliged to restart it, or the service will probably
> restart. Each meaning takes a different word.

---

## 8. Grammar rules

**PSTE-G1**: A writer `MUST` use the active voice and `MUST` name the actor. Write "the
linter rejects the file", not "the file is rejected".

*Weight: 0.5.* `MUST` rule governing grammar: passive voice drops the actor. This
specification calls this a readability loss, not a fact loss under PSTE-A1.

> Software text has many candidate actors: the user, the agent, the compiler, the test
> runner, the pipeline, the runtime. A reader cannot recover the actor from context the
> way a reader of a single-machine manual can. The passive voice therefore loses more
> information in software prose than in other technical prose.

**PSTE-G2**: A writer `MAY` use the passive voice in a description, and only in the two
cases below. The first case is an actor that is genuinely unknown. The second case is
an actor whose identity gives a reader nothing to act on. A writer `MUST NOT` use the
passive voice in an instruction.

*Weight: 0.5.* The `MUST NOT` clause forbids passive voice in an instruction. Same
basis as PSTE-G1: an actor goes missing from a command.

**PSTE-G3**: A writer `MUST` use only these verb forms:
- The infinitive form
- The imperative form
- The simple `present tense`
- The simple `past tense`
- The simple `future tense`
- The past participle, as an adjective only

*Weight: 0.5.* `MUST` rule restricting verb forms to a closed set. A form outside the
set is a grammar fault, not a content fault.

**PSTE-G4**: A writer `MUST NOT` use a perfect tense. Write "I changed the file", not
"I have changed the file".

*Weight: 0.5.* `MUST` rule governing tense: a perfect tense is a grammar fault. The
rule's own example shows a paraphrase, and no fact changes.

**PSTE-G5**: A writer `MUST NOT` stack auxiliary verbs. Do not write "would have been".
Do not write "could be being". Do not write "may need to be able to".

*Weight: 0.5.* `MUST` rule governing grammar: stacked auxiliaries are a fault of
parsing difficulty, not a fact at risk.

**PSTE-G6**: A writer `MUST NOT` use an `-ing` form as a main verb. A writer `MAY` use
an `-ing` form as part of a term noun, such as `logging` or `load balancing`.

*Weight: 0.5.* `MUST` rule governing grammar: an -ing main verb is a form fault. The
rule allows the same form as a noun part elsewhere.

**PSTE-G7**: A writer `MUST` use a verb to describe an action, not a noun. Write
"analyze the log", not "perform an analysis of the log". Write "the service failed",
not "a failure of the service occurred".

*Weight: 0.5.* `MUST` rule governing grammar: a nominalization restates the same action
as a noun. The rule's own example adds and removes no fact.

**PSTE-G8**: A writer `MUST NOT` create a phrasal verb where a single verb exists.
Write "start the container", not "spin up the container". Appendix C lists common
cases.

*Weight: 0.5.* `MUST` rule governing grammar: a phrasal verb has a single-verb
replacement in Appendix C, so the meaning survives and only the form changes.

**PSTE-G9**: A writer `MUST` use an article or a demonstrative adjective before a
noun, where English grammar permits one. Write "the files that the backup does not
include", not "files not backed up".

*Weight: 0.5.* `MUST` rule governing grammar: a missing article is a grammar fault.
Either way, the rule's own example states the same fact.

**PSTE-G10**: A writer `MUST NOT` use gendered pronouns for a person whose pronouns
the writer does not know. Use "they".

*Weight: 0.1.* Checker runs this at `SHOULD`. It flags a common and often-correct
pattern for a human to check, and does not fail a document on a hit alone.

**PSTE-G11**: A writer `MUST NOT` write more than two adjectives before a noun. Write
"a small red button", not "a small round red plastic button".

*Weight: 0.5.* `MUST` rule governing grammar: too many adjectives is a parsing-load
fault for a non-native reader, not a lost fact.

**PSTE-G12**: When a writer writes two adjectives before a noun, the writer `MUST`
put them in this order:

| Order | Category | Examples |
|---|---|---|
| 1 | Opinion | useful, correct, safe |
| 2 | Size | large, small, short |
| 3 | Age | new, old, current, legacy |
| 4 | Shape | round, flat |
| 5 | Colour | red, green |
| 6 | Origin | remote, local, upstream |
| 7 | Material | binary, digital, physical |
| 8 | Purpose | backup, debug, test |

*Weight: 0.5.* `MUST` rule governing grammar: wrong adjective order reads as wrong
without changing what the adjectives describe.

Write "the small old database", not "the old small database".
Write "a new backup file", not "a backup new file".

A native reader applies this order without thinking, and text that breaks it reads
as wrong even when the reader cannot say why. A reader whose first language is not
English does not have that instinct, so a wrong order costs that reader time.

A writer `SHOULD` write one adjective and not two. Two adjectives make a noun phrase
that PSTE-N5 counts. A phrase of one adjective needs no order at all. Move the second
adjective into its own sentence when the sentence carries both.

*The categories above shorten to OSASCOMP, which is a memory aid and not a rule
identifier. Cite PSTE-G12.*

---

## 9. Sentence rules

**PSTE-N1**: A writer `MUST NOT` write more than 20 words in an instruction.

*Weight: 0.5.* `MUST` rule governing sentence form: an instruction over the word limit
is a length fault, not a dropped fact.

**PSTE-N2**: A writer `MUST NOT` write more than 25 words in a description.

*Weight: 0.5.* `MUST` rule governing sentence form: a description over the word limit
is a length fault, not a dropped fact.

**PSTE-N3**: A writer `MUST NOT` use a contraction. Write "do not", not "don't".

*Weight: 0.5.* `MUST` rule governing sentence form: a contraction is a register fault.
The rule's own example spells out the same meaning.

**PSTE-N4**: A writer `MUST NOT` skip words to shorten a sentence. Keep the subject,
the verb, and the articles.

*Weight: 0.5.* `MUST` rule governing sentence form: skipping the subject, the verb, or
an article is a grammar fault. PSTE-A1 escalates it further only if a fact is dropped
too.

**PSTE-N5**: A writer `MUST NOT` write more than three words in a multi-word noun.
Write "the handler that sets the priority of the queue", not "the queue priority
setting handler".

*Weight: 0.5.* `MUST` rule governing noun form: a multi-word noun over three words is a
parsing-load fault. The rule's own example shows the same meaning in more words.

**PSTE-N6**: A writer `MUST` write one instruction in each sentence, unless two
actions occur at the same time.

*Weight: 0.5.* `MUST` rule governing sentence form: two instructions in one sentence is
a form fault, not a missing instruction.

### 9.1 Word count

**PSTE-N7**: For the limits in PSTE-N1 and PSTE-N2, count each of these as one word:
- A number, with its unit
- An abbreviation
- An identifier, a path, or a command
- Quoted text
- A hyphenated word
- Text inside parentheses

*Weight: 0.5.* `MUST` rule governing how a word count is taken: a miscounted word
changes a limit's arithmetic, not the text's content.

---

## 10. Structure rules

**PSTE-D1**: A writer `MUST` write one topic in each paragraph.

*Weight: 0.5.* `MUST` rule governing paragraph form: one topic per paragraph is an
organization requirement, not a fact at risk.

**PSTE-D2**: A writer `MUST NOT` write more than six sentences in a paragraph.

*Weight: 0.5.* `MUST` rule governing paragraph form: the six-sentence limit is a length
rule like PSTE-N1 and PSTE-N2.

**PSTE-D3**: A writer `MUST` use a numbered list for three or more steps done in order.

*Weight: 0.5.* `MUST` rule governing procedure form: the wrong list type for ordered
steps is a presentation fault, not a lost fact.

**PSTE-D4**: A writer `MUST` use a bulleted list for three or more parallel items or
conditions.

*Weight: 0.5.* `MUST` rule governing list form: the wrong list type for parallel items
is a presentation fault, not a lost fact.

**PSTE-D5**: A writer `MUST NOT` hide steps done in order, or a set of conditions,
inside one prose sentence.

*Weight: 0.5.* `MUST` rule governing organization: hiding ordered steps in one
sentence is a form fault. PSTE-A1 already covers the case where a fact is lost doing
it.

**PSTE-D6**: A writer `MUST` give information in a logical order. State what a thing is
before stating what it does. State what it does before stating how to change it.

*Weight: 0.5.* `MUST` rule governing order: the wrong order of information is a
readability fault, not a missing fact.

**PSTE-D7**: A writer `MUST NOT` write more than seven items in a list, and
`SHOULD NOT` write more than five. Above the limit, a writer `MUST` split the list by
sort order or by group. Write "do now" and "do later", or `required` and `optional`.

*Weight: 0.5.* `MUST` rule governing list form: too many items in one list is a
presentation fault. This specification calls it a lost heading, not a lost fact.

**PSTE-D7.1**: PSTE-D7 does not apply to a list that must be complete. A list of the
permitted values of a field, a list of the error codes of an interface, and a generated
list are examples. A writer `MUST` state that such a list is complete.

*Weight: 0.5.* `MUST` rule governing list form: not stating a list is complete is a
missing label on the list, not a missing item.

> A reader holds about five items. A list of twelve is a reference table that lost its
> heading. Five items in rank order tell a reader more than ten in no order.

**PSTE-D8**: A writer `MUST` finish one topic before starting the next. When a document
raises a second topic, a writer `MUST` put it in its own section, or name it at the end
as separate work.

*Weight: 0.5.* `MUST` rule governing document form: an unfinished topic is an
organization fault, not a lost fact.

---

## 11. Procedure rules

**PSTE-P1**: A writer `MUST` write an instruction in the imperative form. Write "run
the tests", not "you should run the tests" and not "the tests should be run".

*Weight: 0.5.* `MUST` rule governing procedure form: a non-imperative instruction is a
form fault. The rule's own example keeps the same command, worded differently.

**PSTE-P2**: When an instruction depends on a condition, a writer `MUST` state the
condition first, and `MUST` separate it from the command with a comma. Write "If the
build fails, read the log."

*Weight: 0.5.* `MUST` rule governing procedure form: a misplaced condition is an order
fault, not a missing condition. PSTE-A1 covers a condition that is dropped outright.

**PSTE-P3**: A writer `MUST` use a note to give information only. A writer `MUST NOT`
put an instruction inside a note.

*Weight: 0.5.* `MUST` rule governing procedure form: an instruction placed inside a
note is an organization fault that risks the reader skipping a command meant to be
followed.

**PSTE-P4**: A writer `MUST` state the expected result of a procedure, or of a step
whose result the reader cannot predict.

*Weight: 0.5.* `MUST` rule governing procedure form: when the result stays unstated,
the reader cannot check success. A readability fault, not a missing fact in the step.

---

## 12. Warning rules

**PSTE-W1**: A writer `MUST` warn the reader before an operation that destroys data,
that the reader cannot reverse, or that affects a shared or production system.

*Weight: 0.8.* A writer `MUST` warn before an operation that destroys data or is not
reversible. A reader who is not warned runs the command, and the damage is exactly what
the warning exists to prevent.

**PSTE-W2**: A writer `MUST` state the scope of the effect before the command. Write
"This deletes every row in the `users` table. Run the backup first." Do not write "Run
the backup first, because this deletes rows."

*Weight: 0.8.* A writer `MUST` state the scope of the effect before the command. A
reader who runs the command first and reads the scope after has already caused the
effect.

**PSTE-W3**: A writer `MUST` name the level of risk with a word. Use `warning` for
a risk to people or to production data. Use `caution` for a risk of losing local work
or time.

*Weight: 0.8.* A writer `MUST` name the level of risk with a word. A reader who
cannot tell a `warning` from a `caution` misjudges how much care the action needs.

**PSTE-W4**: A writer `MUST` state the exact result of the risk. Write "you lose
every uncommitted change", not "this can cause problems".

*Weight: 0.8.* A writer `MUST` state the exact result of the risk. A vague risk
statement such as this can cause problems gives the reader nothing to act on before the
damage happens.

**PSTE-W5**: A writer `MAY` write a warning that is longer than the limits in §9, when
a limit would remove information about the risk. PSTE-A1 applies.

*Weight: N/A.* PSTE-W5 is `MAY` only, a permission to exceed a limit for a warning.
There is no action a writer can take that breaks it.

---

## 13. Punctuation rules

**PSTE-X1**: A writer `MUST NOT` use a semicolon. Write two sentences.

*Weight: 0.1.* A semicolon is punctuation. PSTE-X2 permits every other normal mark,
so this is the narrowest of the punctuation rules.

**PSTE-X2**: A writer `MAY` use every other normal English punctuation mark.

*Weight: N/A.* PSTE-X2 is `MAY` only, a permission to use any other normal
punctuation mark. There is no action a writer can take that breaks it.

**PSTE-X3**: A writer `MUST` use a hyphen to connect words that act as one unit before
a noun, such as "read-only file".

*Weight: 0.1.* A missing hyphen on a compound modifier is a punctuation fault. The
words and their meaning are unchanged, only momentarily harder to parse.

**PSTE-X4**: A writer `MAY` use parentheses to give a reference, an abbreviation, or an
option. A writer `MUST NOT` use parentheses to add a second idea to a sentence.

*Weight: 0.1.* Parentheses used for a second idea are a punctuation and organization
fault at the weak end of the scale. PSTE-X4 still permits them for a reference or an
abbreviation.

**PSTE-X5**: A writer `SHOULD NOT` use an em dash to join two independent clauses.
Write two sentences.

*Weight: 0.1.* PSTE-X5 is itself a `SHOULD` rule. This specification notes it is not
even an aerospace rule, added only because the em dash marks unedited machine prose.

> This is not an aerospace rule. It appears here because the em dash is the most common
> structural marker of unedited machine-generated prose, and because two sentences are
> easier to read than one sentence with a hinge in the middle.

---

## 14. Recommendations

These are not requirements. They help a writer avoid errors that are common.

**PSTE-R1: Keep the conjunction "that".** Write "make sure that the service is running".
The conjunction helps a reader parse the sentence and helps a translator.

**PSTE-R2: Check every use of "with".** The word carries some meanings. Re-read each
sentence that uses it and check that only one meaning is available.

**PSTE-R3: Replace an ambiguous pronoun with its noun.** If a paragraph contains two
candidate referents, name the referent again.

**PSTE-R4: Check "this" and "it" at the start of a sentence.** These words often
refer to the whole sentence before. That is rarely what the writer means.

**PSTE-R5: Prefer the exact noun.** Write "the timeout", not "the issue". Write "the
`404` response", not "an unspecified failure".

**PSTE-R6: State what you did not do.** A reader assumes completeness. If you tested one
path and not another, say so.

---

## 15. Inspiration

Controlled English is an established practice with a long history. PSTE follows that
practice. The works below inspired this specification. None of them is a source for its
text.

**ASD-STE100 Simplified Technical English**, published by the AeroSpace, Security and
Defence Industries Association of Europe, is the best known controlled English for <!-- pste-lint: ignore -->
technical documentation. It showed that a restricted vocabulary and a fixed grammar make
technical text easier to read. That demonstration inspired this work.

ASD-STE100 is a registered trademark of ASD (EU trade mark 017966390). ASD restricts who
may reproduce and share its specification. So this document:

- Quotes no text from ASD-STE100
- Reproduces no part of the ASD-STE100 dictionary
- Uses its own rule numbers, its own rule text, and its own word list
- Makes no claim of conformance to ASD-STE100, and no claim of endorsement by ASD or by
  the STE Maintenance Group

**Conformance to PSTE is not conformance to ASD-STE100.** A reader who writes aerospace
maintenance documentation `MUST` use ASD-STE100 and `MUST NOT` use this specification.
ASD publishes it at https://asd-ste100.org.

PSTE covers a domain that aerospace controlled English does not: building software. A
writer of software prose needs words such as `refactor`, `merge`, `deploy`, `roll back`,
and `deprecate`. That writer also needs rules for identifiers, for destructive commands,
and for stated uncertainty. §5.3 of the project plan records that gap.

**Basic English**, C.K. Ogden (1930). The earliest systematic restricted-vocabulary
English.

**Politics and the English Language**, George Orwell (1946). Six rules, in particular the
rule to cut a word wherever cutting one is possible. Also the rule that permits a writer
to break any rule before writing something barbarous.

**Plain Writing Act of 2010** (US Public Law 111-274), and the plain-language guidance
that followed it.

**RFC 2119** and **RFC 8174**, for the conformance vocabulary in §2.

---

## 16. References

[RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels",
BCP 14, RFC 2119, March 1997.
<https://www.rfc-editor.org/rfc/rfc2119>

[RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", <!-- pste-lint: ignore -->
BCP 14, RFC 8174, May 2017.
<https://www.rfc-editor.org/rfc/rfc8174>

[CHERVAK] Chervak, S., Drury, C.G., and Ouellette, J.P., "Simplified English for Aircraft
Workcards", Proceedings of the Human Factors and Ergonomics Society Annual Meeting, 1996.
<https://doi.org/10.1177/154193129604000416>

---

## 17. Change log

| Version | Date | Change |
|---|---|---|
| 1.0.0-draft | 2026-08-02 | First draft. |

---

## Appendices

- **[Appendix A](appendix-a.md)** — Approved words (normative).
- **[Appendix C](appendix-c.md)** — Words to avoid, and their approved alternatives
  (informative).
- **[Appendix D](conformance/README.md)** — Conformance test cases.
- **[Appendix T](appendix-t.md)** — Obligations on a tool (informative).

Appendices A and C are generated from `wordlist.yaml` by
`lib/build_appendix.py`. Edit the YAML files, then run that script. The checker reads
the same YAML, so this specification and the checker cannot disagree about which words
are approved.
