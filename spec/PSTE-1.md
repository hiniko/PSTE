# PSTE-1: Programming Simplified Technical English

**Version:** 1.0.0-draft
**Date:** 2026-08-02
**Status:** Draft

---

## 1. Introduction

### 1.1 Purpose

PSTE is a controlled form of English for software communication. It restricts
vocabulary, grammar, and sentence structure. The restriction has one purpose: to make
technical prose **easier to read, and easier to share with other people**.

A reader of software prose is often tired, hurried, or working in a second language.
That reader frequently sees the text out of context, as a pasted excerpt in a chat
window or a ticket. PSTE makes such text hold its meaning under those conditions.

### 1.2 Non-goals

This specification makes **no claim** that controlled English improves the correctness,
the reasoning, or the substance of what a writer says. It does not. PSTE governs the
*form* of prose only.

A conforming document can be wrong. A conforming document can be useless. PSTE makes a
document easier to read. It cannot make a hollow paragraph true. An implementation MUST
NOT claim that conformance to PSTE improves the accuracy of content.

PSTE is also not a compression standard. Conforming text is frequently shorter than its
source, but this is a result and not a goal. Rule PSTE-A1 (§4.5) states that accuracy
always defeats brevity.

### 1.3 Applicability

PSTE applies to prose about software: documentation, README files, pull request
descriptions, commit bodies, release notes, error messages, runbooks, incident reports,
code review comments, and the output of software agents.

PSTE does not apply to code. It does not apply to marketing copy, essays, tutorials
that use narrative, or any text that needs a voice. PSTE removes voice deliberately.

### 1.4 Evidence

Controlled English improves comprehension for human readers. Chervak, Drury and
Ouellette (1996) tested 175 aircraft technicians on maintenance procedures. Comprehension
increased from 76% to 86% with controlled-English text. For readers whose first language
was not English, comprehension increased from 69% to 87%.

That study examined aerospace text, human authors, and human readers. It supports the
readability claim in §1.1. It does not measure software text, and it does not measure
machine-generated text. No study known to the editors measures those conditions.

---

## 2. Conformance language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be
interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear
in all capitals, as shown here.

### 2.1 How to write a rule

These requirements apply to this document, and to any document that states rules with
these key words.

**PSTE-K1**: A writer MUST negate a key word only with the word "NOT", and only in the
forms `MUST NOT`, `SHALL NOT`, and `SHOULD NOT`.

`MUST`, `SHALL`, and `SHOULD` introduce an action to take. `MUST NOT`, `SHALL NOT`, and
`SHOULD NOT` introduce an action to avoid. No other construction carries the meaning.

`MAY` states a permission, so it has no negated form. To forbid an action, use
`MUST NOT`. To state that an action is unnecessary, use `MAY` on the alternative.

Write "A writer MUST NOT use a semicolon". Do not write "A writer MUST never use a <!-- pste-lint: ignore -->
semicolon", "A writer MUST avoid semicolons", or "Nobody MUST use a semicolon". Each of <!-- pste-lint: ignore -->
those reads as an obligation to do something, and the last states an obligation on a
subject that does not exist.

The rule covers every key word, in either shape:

| Shape | Key words | Negate as |
|---|---|---|
| Modal | `MUST`, `SHALL`, `SHOULD`, `MAY` | `MUST NOT`, `SHALL NOT`, `SHOULD NOT` |
| Adjectival | `REQUIRED`, `RECOMMENDED`, `OPTIONAL` | rewrite with a modal key word |

An adjectival key word has no negated form. `NOT REQUIRED` is not a BCP 14 form: it
reads as an absent obligation, which is what `MAY` already states. Write "A writer MAY
omit the heading", not "A heading is NOT REQUIRED". <!-- pste-lint: ignore -->

The word `NOT` MUST appear in capitals. `MUST not` reads as ordinary prose, and a
reader cannot tell a requirement from a description.

**PSTE-K2**: A writer MUST name the actor that a rule binds, and MUST place that actor
before the key word.

A rule binds somebody to an action. Write "A writer MUST keep every number". Do not
write "Every number MUST be kept", because that names no actor and uses the passive <!-- pste-lint: ignore -->
voice, which rule PSTE-G1 already forbids.

The same fault appears with an adjectival key word. Write "A writer MUST name the
actor", not "The actor is REQUIRED to be named". Write "A writer MAY omit the heading", <!-- pste-lint: ignore -->
not "A heading is OPTIONAL". <!-- pste-lint: ignore -->

**PSTE-K3**: A writer MUST NOT use a key word for a statement of fact. A key word states
a requirement.

Write "A writer MAY write a warning that is longer than the limit". Do not write "A
warning MUST NOT be subject to the limit", because a warning is not an actor and cannot <!-- pste-lint: ignore -->
obey a rule.

> **Note.** `SHALL`, `SHALL NOT`, `REQUIRED`, `RECOMMENDED`, and `OPTIONAL` are valid
> BCP 14 key words, and this section keeps them valid. A writer SHOULD use `MUST`,
> `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` instead, because five key words are
> easier to hold in mind than ten, and the others add no meaning.

---

## 3. Terminology

**approved word**
: A word listed in Appendix A. An approved word has exactly one approved meaning and one
  approved part of speech in PSTE text.

**not-approved word**
: A word listed in Appendix C with one or more approved alternatives. §6 states when a
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
: Text that the agent composes. §4 defines this precisely and separates it from quoted
  text and from code.

**instruction**
: A sentence that tells the reader to do something. Instructions use the imperative form.

**description**
: A sentence that gives information and does not tell the reader to do something.

---

## 4. Scope of application

### 4.1 The four targets

Every part of a document falls into one of four targets. Each target has one rule.

| Target | Content | Rule |
|---|---|---|
| **T1 — author prose** | Explanations, summaries, instructions, status reports, descriptions | PSTE applies in full |
| **T2 — code and literals** | Code, commands, file paths, identifiers, error strings, API names, configuration | Reproduce verbatim. PSTE does not apply |
| **T3 — quoted text** | Text copied from a file, a document, a specification, or tool output | Reproduce verbatim. PSTE does not apply |
| **T4 — repository text** | Code comments and commit messages inside a repository | Match the style of the repository |

**PSTE-S1**: A writer MUST apply the rules of this specification to target T1 only.

**PSTE-S2**: A writer MUST reproduce T2 and T3 content character for character. A writer
MUST NOT correct the spelling, the grammar, or the style of quoted text.

**PSTE-S3**: When a writer quotes text that does not conform to PSTE, the writer MUST NOT
mark the quoted text as a conformance failure.

### 4.2 Identifiers inside prose

**PSTE-S4**: A writer MUST NOT inflect an identifier. Write "the `getUser` function
returns a record", not "getUsering the record" or "we getUser the record".

**PSTE-S5**: A writer SHOULD set an identifier in a code span when the output format
supports one.

### 4.3 Structural markup

**PSTE-S6**: A writer MAY use headings, lists, tables, code blocks, and code spans.
A reader of software prose depends on this structure.

### 4.4 The first person

**PSTE-S7**: A writer MAY use the pronoun "I" to report the writer's own actions. Write
"I changed the file", not "the agent changed the file".

> **Note.** This diverges from aerospace practice, which disapproves the first person.
> An agent that reports its own work needs to name itself, and the alternative
> constructions are less clear, not more.

### 4.5 Accuracy defeats style

**PSTE-A1**: A writer MUST keep every fact, condition, number, unit, and scope
qualifier that the text states. A writer MUST NOT remove one to satisfy a length limit
or a vocabulary limit. This rule defeats every other rule in this specification.

When a rule and precision conflict, the writer MUST keep the precision. The writer SHOULD
then split the sentence, or add a sentence, to satisfy the rule.

> This rule exists because a controlled vocabulary can degrade correctness if a writer
> applies it mechanically. A shorter sentence that omits a condition is a defect, not a
> conformance success.

### 4.6 Brevity is not optional

PSTE-A1 protects facts. It does not protect words. A writer who invokes PSTE-A1 to keep
text that states no fact inverts the rule, and the result is the failure that PSTE-L2
and §9 exist to prevent.

**PSTE-A2**: Before a writer exceeds a limit under PSTE-A1, the writer MUST identify the
specific fact, condition, number, unit, or scope qualifier that the limit would remove.
When the writer cannot name that item, PSTE-A1 does not apply and the limit stands.

**PSTE-A3**: A writer MUST first try to satisfy the rule and keep the precision. A writer
SHOULD split the sentence, and MUST exceed a limit only when no division of the text
keeps every item and meets the limit.

> Almost every conflict between accuracy and a length limit is false. A sentence of 30
> words that states two facts becomes two sentences of 15 words, and both facts survive.
> PSTE-A3 makes the split the first action and the exemption the last one.

#### 4.6.1 When the balance tips

A writer MAY exceed a limit in these cases only:

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

## 5. Conformance levels

PSTE defines three levels. A higher level includes every requirement of the levels below
it.

| Level | Name | Requirements |
|---|---|---|
| **1** | Basic | §7 Grammar, §9 Structure, and the clarity rules of §5.3. Vocabulary is unconstrained. |
| **2** | Standard | Level 1, plus §8 Sentences, §10 Procedures, §11 Warnings, §12 Punctuation, and the vocabulary rules of §6 as SHOULD. |
| **3** | Strict | Level 2, with the vocabulary rules of §6 as MUST. Appendix A is enforced. |

**PSTE-C1**: A document that claims conformance MUST state its level. Example: "Conforms
to PSTE-1 Level 2".

**PSTE-C2**: A tool that checks conformance MUST report the level that it checked. The
tool MUST identify each finding by its rule identifier.

**PSTE-C3**: An agent that produces prose interactively SHOULD use Level 2 by default.
An agent SHOULD use Level 3 for procedures, runbooks, release notes, error messages, and
published documentation.

**PSTE-C4**: *Withdrawn.* This identifier is retired and MUST NOT name a new rule. §5.2
replaces it with a non-normative note.

**PSTE-C5**: *Withdrawn.* This identifier is retired and MUST NOT name a new rule. §5.2
replaces it with a non-normative note.

> A withdrawn identifier keeps its place in this document rather than a gap. The closing
> note under Appendices states the policy: an identifier is never reused. Read §5.2 for
> the design reasoning that PSTE-C4 and PSTE-C5 used to state as rules.

### 5.1 The pass threshold

**PSTE-C6**: A tool that checks conformance MUST compute the verdict this way:

A document PASSES when all three hold:

1. The document has no MUST finding.
2. The count of SHOULD findings stays at or below one for every 100 words, rounded up.
3. The document has no fact loss under PSTE-A1.

A document that fails any one of the three FAILS.

**PSTE-C7**: A tool MUST count words for PSTE-C6 the way PSTE-N7 counts them.

**PSTE-C8**: A tool that checks conformance MUST report a verdict of PASS or FAIL. The
tool MUST NOT report a score in the place of a verdict.

When the text does not conform, the tool MUST list each finding, so that a writer can
correct it. A verdict with no detail helps nobody.

> §14.1 lists the rules a checker counts. This document does not yet mark each rule as
> MUST-severity or SHOULD-severity for PSTE-C6. A checker that implements PSTE-C6 needs
> that mapping, and this draft does not supply one.

### 5.2 Why the distributed tool shows no score

This section states a design choice. It is not a rule, and no key word in it binds a
writer or a tool.

The tool that this project distributes to a writer shows PASS or FAIL, and a list of
findings on FAIL. It does not show a count, a rate, or a percentage next to that
verdict.

A visible score invites a writer to chase it. A writer who sees "3 findings" edits
toward "0 findings", and that edit spends effort on the number, not on the prose.

The number also invites comparison between documents. It invites a claim that a lower
count means a better document. A conformance result is not a measure of quality, and a
smaller one is not either.

This choice governs only what the distributed tool shows a person. A program MAY still
compute a count or a rate for its own use, such as a pre-commit hook that checks the
count fell to zero.

An evaluation harness that this project keeps and does not distribute is a different
tool for a different reader. Its reader is a project maintainer who compares a change
across a corpus, and that reader needs the count to see whether a change helped.

Such a harness MAY report a count, a rate, or a percentage. It MUST still carry the
notice that a conformance result is not a measure of quality. It SHOULD still withhold
a single combined score from a page that a broader audience reads, for the same reason
the distributed tool withholds one.

### 5.3 Clarity rules (all levels)

**PSTE-L1**: A writer MUST NOT state uncertainty more than once about the same claim.
Write "I did not test this." Do not write "this might possibly work, but I am not
entirely certain".

> Stacked hedging is the most common readability failure in machine-generated prose.
> It is a precision failure and not a style failure: three vague qualifiers tell the
> reader less than one clear statement.

**PSTE-L2**: A writer MUST NOT add text that carries no information. This includes
openings that restate the question, closings that repeat the body, and transitions that
announce what the writer is about to do.

**PSTE-L3**: A writer MUST state the result before the explanation. The first sentence of
a response answers the question or reports what happened.

**PSTE-L4**: A writer MUST NOT state the same fact twice in one document. A writer MAY
repeat a fact in a warning, because a reader who skips a section still needs the risk.

> PSTE-L2 covers a closing that repeats the body. PSTE-L4 covers the wider case: the same
> fact in two paragraphs, in different words, is still one fact. A reader who meets it
> twice must decide whether the second statement adds something. It does not.

**PSTE-L5**: A writer MUST NOT open with a phrase that announces the response, and MUST
NOT close with a phrase that offers further help. Appendix C lists the phrases.

> Examples of an opener to remove: "Great question", "Let me look into that", "To answer
> your question". Examples of a closer to remove: "Let me know if you need anything else",
> "Hope this helps", "Feel free to ask".
>
> These phrases are frames and not content. A reader who wants the answer reads past them,
> and a reader in a hurry reads the frame and stops.

---

## 6. Vocabulary rules

The requirement level of this section depends on the conformance level. At Level 3 these
rules are MUST. At Level 2 they are SHOULD. At Level 1 they do not apply.

**PSTE-V1**: A writer MUST use a word from one of these three sets:
- An approved word from Appendix A
- A term, as §3 defines one
- An identifier, quoted under §4.2

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
> judgement is needed, and a list never arrives there. `spec/terms.yaml` still holds
> the common core, because a tool needs a lookup to stop reporting `cache` and
> `latency` as unusual. It is not normative, and a word absent from it is not thereby
> forbidden.

**PSTE-V2**: A writer MUST use an approved word only with the meaning given in Appendix A,
and only as the part of speech given in Appendix A.

**PSTE-V3**: A writer MUST use one word for one meaning throughout a document. A writer
MUST NOT use two approved words for the same action or the same object.

> Example. Select `check` and use it in every place. Do not alternate between `check`,
> `verify`, `confirm`, and `validate`. The reader of a rotating vocabulary must decide
> whether each new word signals a new meaning. It usually does not, and the decision
> costs the reader time.

**PSTE-V4**: A writer MUST use one name for one entity, and that name MUST match the name
in the code. If the code declares `orderId`, the prose says "the order ID". The prose
MUST NOT say "the order identifier", "the order key", or "the ID" for the same value.

**PSTE-V5**: A writer MUST NOT use a term when an approved word states the meaning
accurately. A writer MUST NOT coin a term where plain English works.

**PSTE-V6**: A writer MUST NOT use a term noun as a verb, and MUST NOT use a term verb as
a noun. Write "I made a deployment" or "I deployed the service". Do not write "I did a
deploy".

**PSTE-V7**: A writer MUST use American English spelling.

**PSTE-V8**: A writer MUST NOT use a Latin abbreviation. Replace `e.g.` with "for
example", `i.e.` with "that is", and `etc.` with a complete list or with "and others".

**PSTE-V9**: A writer MUST NOT use marketing adjectives. Appendix C lists them. Examples:
`seamless`, `robust`, `powerful`, `blazing`, `elegant`, `effortless`.

**PSTE-V10**: A writer MUST distinguish the four modal meanings and MUST NOT use one modal
verb for another meaning:

| Meaning | Use | Do not use |
|---|---|---|
| Capability | can | should, is able to |
| Permission | may | can, is allowed to |
| Obligation | must | should, needs to, is required to |
| Probability | is likely to | should, could |

> "The service should restart" is ambiguous. It can mean the service is capable of
> restarting, the operator is obliged to restart it, or the service will probably
> restart. Each meaning takes a different word.

---

## 7. Grammar rules

**PSTE-G1**: A writer MUST use the active voice and MUST name the actor. Write "the
linter rejects the file", not "the file is rejected".

> Software text has many candidate actors: the user, the agent, the compiler, the test
> runner, the pipeline, the runtime. A reader cannot recover the actor from context the
> way a reader of a single-machine manual can. The passive voice therefore loses more
> information in software prose than in other technical prose.

**PSTE-G2**: A writer MAY use the passive voice in a description, and only when the actor
is genuinely unknown or when no reader could act on the identity of the actor. A writer
MUST NOT use the passive voice in an instruction.

**PSTE-G3**: A writer MUST use only these verb forms:
- The infinitive form
- The imperative form
- The simple present tense
- The simple past tense
- The simple future tense
- The past participle, as an adjective only

**PSTE-G4**: A writer MUST NOT use a perfect tense. Write "I changed the file", not "I
have changed the file".

**PSTE-G5**: A writer MUST NOT stack auxiliary verbs. Constructions such as "would have
been", "could be being", and "may need to be able to" are not permitted.

**PSTE-G6**: A writer MUST NOT use an `-ing` form as a main verb. A writer MAY use an
`-ing` form as part of a term noun, such as `logging` or `load balancing`.

**PSTE-G7**: A writer MUST use a verb to describe an action, not a noun. Write "analyze
the log", not "perform an analysis of the log". Write "the service failed", not "a
failure of the service occurred".

**PSTE-G8**: A writer MUST NOT create a phrasal verb where a single verb exists. Write
"start the container", not "spin up the container". Appendix C lists common cases.

**PSTE-G9**: A writer MUST use an article or a demonstrative adjective before a noun,
where English grammar permits one. Write "the files that the backup does not include",
not "files not backed up".

**PSTE-G10**: A writer MUST NOT use gendered pronouns for a person whose pronouns the
writer does not know. Use "they".

**PSTE-G11**: A writer MUST NOT write more than two adjectives before a noun. Write
"a small red button", not "a small round red plastic button".

**PSTE-G12**: When a writer writes two adjectives before a noun, the writer MUST put
them in this order:

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

Write "the small legacy database", not "the legacy small database".
Write "a new backup file", not "a backup new file".

A native reader applies this order without thinking, and text that breaks it reads
as wrong even when the reader cannot say why. A reader whose first language is not
English does not have that instinct, so a wrong order costs that reader time.

**A writer SHOULD write one adjective and not two.** Two adjectives make a noun
phrase that PSTE-N5 counts, and a phrase of one adjective needs no order at all.
Move the second adjective into its own sentence when the sentence carries both.

*The categories above shorten to OSASCOMP, which is a memory aid and not a rule
identifier. Cite PSTE-G12.*

---

## 8. Sentence rules

**PSTE-N1**: A writer MUST NOT write more than 20 words in an instruction.

**PSTE-N2**: A writer MUST NOT write more than 25 words in a description.

**PSTE-N3**: A writer MUST NOT use a contraction. Write "do not", not "don't".

**PSTE-N4**: A writer MUST NOT omit words to shorten a sentence. Keep the subject, the
verb, and the articles.

**PSTE-N5**: A writer MUST NOT write more than three words in a multi-word noun. Write
"the handler that sets the priority of the queue", not "the queue priority setting
handler".

**PSTE-N6**: A writer MUST write one instruction in each sentence, unless two actions
occur at the same time.

### 8.1 Word count

**PSTE-N7**: For the limits in PSTE-N1 and PSTE-N2, count each of these as one word:
- A number, with its unit
- An abbreviation
- An identifier, a path, or a command
- Quoted text
- A hyphenated word
- Text inside parentheses

---

## 9. Structure rules

**PSTE-D1**: A writer MUST write one topic in each paragraph.

**PSTE-D2**: A writer MUST NOT write more than six sentences in a paragraph.

**PSTE-D3**: A writer MUST use a numbered list for a sequence of three or more steps.

**PSTE-D4**: A writer MUST use a bulleted list for three or more parallel items or
conditions.

**PSTE-D5**: A writer MUST NOT hide a sequence or a set of conditions inside one prose
sentence.

**PSTE-D6**: A writer MUST give information in a logical order. State what a thing is
before stating what it does. State what it does before stating how to change it.

**PSTE-D7**: A writer MUST NOT write more than seven items in a list, and SHOULD NOT
write more than five. Above the limit, a writer MUST divide the list by rank or by
group. Write "do now" and "do later", or "required" and "optional".

**PSTE-D7.1**: PSTE-D7 does not apply to a list that must be exhaustive, such as a list
of the permitted values of a field, a list of the error codes of an interface, or a
generated list. A writer MUST state that such a list is complete.

> A reader holds about five items. A list of twelve is a reference table that lost its
> heading. Five items in rank order tell a reader more than ten in no order.

**PSTE-D8**: A writer MUST finish one topic before starting the next. When a document
raises a second topic, a writer MUST put it in its own section, or name it at the end as
separate work.

---

## 10. Procedure rules

**PSTE-P1**: A writer MUST write an instruction in the imperative form. Write "run the
tests", not "you should run the tests" and not "the tests should be run".

**PSTE-P2**: When an instruction depends on a condition, a writer MUST state the condition
first, and MUST separate it from the command with a comma. Write "If the build fails,
read the log."

**PSTE-P3**: A writer MUST use a note to give information only. A writer MUST NOT put an
instruction inside a note.

**PSTE-P4**: A writer MUST state the expected result of a procedure, or of a step whose
result the reader cannot predict.

---

## 11. Warning rules

**PSTE-W1**: A writer MUST warn the reader before an operation that destroys data, that
the reader cannot reverse, or that affects a shared or production system.

**PSTE-W2**: A writer MUST state the scope of the effect before the command. Write "This
deletes every row in the `users` table. Run the backup first." Do not write "Run the
backup first, because this deletes rows."

**PSTE-W3**: A writer MUST identify the level of risk with a word. Use "warning" for a
risk to people or to production data. Use "caution" for a risk of losing local work or
time.

**PSTE-W4**: A writer MUST state the specific result of the risk. Write "you lose every
uncommitted change", not "this can cause problems".

**PSTE-W5**: A writer MAY write a warning that is longer than the limits in §8, when a
limit would remove information about the risk. PSTE-A1 applies.

---

## 12. Punctuation rules

**PSTE-X1**: A writer MUST NOT use a semicolon. Write two sentences.

**PSTE-X2**: A writer MAY use every other standard English punctuation mark.

**PSTE-X3**: A writer MUST use a hyphen to connect words that act as one unit before a
noun, such as "read-only file".

**PSTE-X4**: A writer MAY use parentheses to give a reference, an abbreviation, or an
alternative. A writer MUST NOT use parentheses to add a second idea to a sentence.

**PSTE-X5**: A writer SHOULD NOT use an em dash to join two independent clauses. Write two
sentences.

> This is not an aerospace rule. It appears here because the em dash is the most common
> structural marker of unedited machine-generated prose, and because two sentences are
> easier to read than one sentence with a hinge in the middle.

---

## 13. Recommendations

These are not requirements. They help a writer prevent common errors.

**PSTE-R1 — Keep the conjunction "that".** Write "make sure that the service is running".
The conjunction helps a reader parse the sentence and helps a translator.

**PSTE-R2 — Check every use of "with".** The word carries several meanings. Re-read each
sentence that uses it and confirm that only one meaning is available.

**PSTE-R3 — Replace an ambiguous pronoun with its noun.** If a paragraph contains two
candidate referents, name the referent again.

**PSTE-R4 — Check "this" and "it" at the start of a sentence.** These words frequently
refer to a whole preceding sentence, which is rarely what the writer means.

**PSTE-R5 — Prefer the specific noun.** Write "the timeout", not "the issue". Write "the
`404` response", not "the problem".

**PSTE-R6 — State what you did not do.** A reader assumes completeness. If you tested one
path and not another, say so.

---

## 14. The check before the text is final

A writer cannot count and compose at the same time. The rules that need a count are the
rules that a writer breaks most often, and they are also the rules that a tool measures
exactly. This section divides the work on that line.

### 14.1 The mechanical check

**PSTE-K4**: Before a writer publishes a document, or writes it to a file, the writer
MUST run a conformance checker over the text and MUST correct every finding, or MUST
record why a finding stands.

A checker counts these exactly, and a writer MUST NOT count them by hand:

| What the tool counts | Rule |
|---|---|
| Words in a sentence | PSTE-N1, PSTE-N2, PSTE-N7 |
| Sentences in a paragraph | PSTE-D2 |
| Items in a list | PSTE-D7 |
| Words in a multi-word noun | PSTE-N5 |
| Adjectives before a noun, and their order | PSTE-G11, PSTE-G12 |
| Filler, stacked hedging, and frame phrases | PSTE-L1, PSTE-L2, PSTE-L5 |
| Not-approved words | PSTE-V1, PSTE-V3, PSTE-V8, PSTE-V9 |

> A clean report is necessary and not sufficient. The checker covers part of this
> specification, and §14.2 lists what no checker decides. A writer who reports a clean
> run as conformance overstates the result. §5.2 states why.

### 14.2 The judgement check

No tool decides these. A writer MUST check them after the checker reports clean:

1. Does the first sentence give the result? (PSTE-L3)
2. Does the last sentence add a fact, or repeat one? (PSTE-L2, PSTE-L4)
3. Is there a second topic that belongs in its own section? (PSTE-D8)
4. Did an edit for any rule above remove a fact, a number, a unit, a condition, or a
   scope qualifier? (PSTE-A1, PSTE-A2)

**PSTE-K5**: A writer MUST make item 4 the last check, and MUST restore any item that an
edit removed.

> Item 4 comes last because every other item in this section removes text. A writer who
> checks accuracy first checks a draft that later edits change. The final action on a
> document is a check that the document still states everything it stated at the start.

---

## 15. Rule weight

### 15.1 Why a weight exists

§14 counts findings. A count alone treats a dropped negation and a missing hyphen as
one fault each. That measures nothing useful.

A writer who removes a condition sends the next reader down the wrong path. A writer
who omits a hyphen costs that reader one extra glance at the sentence. The two faults
do not cost a reader the same thing.

PSTE-A1 already ranks these faults against each other. It states that accuracy
defeats every other rule in this specification. §15.2 turns that ranking into a
number a tool can use.

### 15.2 What the number means

Each rule in this specification carries a weight from 0 to 1. The weight states the
consequence when a writer violates the rule once. The scale is normalized, so the
most serious violation a document can carry is 1.

| Weight | Meaning |
|---|---|
| 1.0 | A fact, condition, number, unit, or scope qualifier is gone. PSTE-A1 states that this defeats every other rule. |
| 0.8 | A reader acts on the faulty text, and is harmed when it is wrong: a missing warning, a miscopied quote, an inflected identifier. |
| 0.5 | A MUST rule on the form of the prose: grammar, sentence and paragraph limits, procedure structure, the checker's own process. The meaning survives; the form does not. |
| 0.3 | A vocabulary rule. An unapproved word is usually understood. The fault is rotation or convention, not lost meaning. |
| 0.1 | A SHOULD rule, or a punctuation rule. The standard's own key word, or its own note, already marks these as the weakest rules in this specification. |
| N/A | A rule that states a permission only (MAY), with no obligation a writer can fail. No action breaks such a rule, so it carries no weight. |

A weight of 1.0 is not twice as bad as 0.5. The scale is ordinal: a higher number is
a worse fault, and the bands group faults of comparable consequence. §15.4 states how
a tool uses the number.

### 15.3 The weights are normative

The weight of each rule is part of this specification, at the same conformance level
as the rule it weights. A tool that reports a weighted measure MUST use the weight
this section states for each rule. A tool MUST NOT assign its own weight to a rule
that this section weights.

### 15.4 How a tool uses the weight

A tool MAY compute a weighted sum of findings, by adding each finding's rule weight
instead of adding one per finding. A maintainer uses the sum to compare documents, or
to compare a change, in the same way §5.2 permits a count.

§5.2 still governs what the distributed tool shows a person. A weighted sum carries
the same restriction as a raw count.

A weighted sum MUST NOT replace the PSTE-C6 verdict. PSTE-C6 computes PASS or FAIL
from the presence of a MUST finding, and this section does not change that
computation.

### 15.5 The weight table

This table states the weight of every rule in this specification. `spec/rule_weights.csv`
holds the same data for a program that needs it without parsing this document. §15.6
states how the two are kept the same.

| Rule | Weight | Reason |
|---|---|---|
| PSTE-A1 | 1.0 | PSTE-A1 states it defeats every other rule in this specification; losing a fact is the one fault the standard ranks above all others. |
| PSTE-A2 | 1.0 | PSTE-A2 exists only to test whether PSTE-A1 applies; failing it means a fact was removed without the check that PSTE-A1 requires. |
| PSTE-A3 | 1.0 | PSTE-A3 exists only to keep PSTE-A1's precision intact before a limit is allowed to win; failing it means precision lost that a split sentence could have kept. |
| PSTE-C1 | 0.5 | MUST rule on document form: a missing conformance level is a process omission, not a content loss. |
| PSTE-C2 | 0.5 | MUST rule on tool form: a report that omits the level or the rule identifier is an omission in reporting, not in the prose itself. |
| PSTE-C3 | 0.1 | SHOULD rule: a default level choice, weak by the standard's own key word. |
| PSTE-C6 | 0.5 | MUST rule on tool form: the verdict computation is a process rule, not a content fault in the prose. |
| PSTE-C7 | 0.5 | MUST rule on tool form: a wrong word count changes a verdict's arithmetic, not a fact in the text. |
| PSTE-C8 | 0.5 | MUST rule on tool form: reporting a score instead of a verdict is a reporting-shape fault, not a content loss. |
| PSTE-D1 | 0.5 | MUST rule governing paragraph form: one topic per paragraph is a structure requirement, not a fact at risk. |
| PSTE-D2 | 0.5 | MUST rule governing paragraph form: the six-sentence limit is a length rule like PSTE-N1 and PSTE-N2. |
| PSTE-D3 | 0.5 | MUST rule governing procedure form: the wrong list type for a sequence is a presentation fault, not a lost fact. |
| PSTE-D4 | 0.5 | MUST rule governing list form: the wrong list type for parallel items is a presentation fault, not a lost fact. |
| PSTE-D5 | 0.5 | MUST rule governing structure: hiding a sequence in one sentence is a form fault. PSTE-A1 already covers the case where a fact is lost doing it. |
| PSTE-D6 | 0.5 | MUST rule governing order: the wrong order of information is a readability fault, not a missing fact. |
| PSTE-D7 | 0.5 | MUST rule governing list form: too many items in one list is a presentation fault. The standard calls it a lost heading, not a lost fact. |
| PSTE-D7.1 | 0.5 | MUST rule governing list form: not stating a list is exhaustive is a missing label on the list, not a missing item. |
| PSTE-D8 | 0.5 | MUST rule governing document form: an unfinished topic is a structure fault, not a lost fact. |
| PSTE-G1 | 0.5 | MUST rule governing grammar: passive voice drops the actor. The standard calls this a readability loss, not a fact loss under PSTE-A1. |
| PSTE-G2 | 0.5 | The MUST NOT clause forbids passive voice in an instruction. Same basis as PSTE-G1: an actor goes missing from a command. |
| PSTE-G3 | 0.5 | MUST rule restricting verb forms to a closed set. A form outside the set is a grammar fault, not a content fault. |
| PSTE-G4 | 0.5 | MUST rule governing tense: a perfect tense is a grammar fault. The rule's own example shows a paraphrase, and no fact changes. |
| PSTE-G5 | 0.5 | MUST rule governing grammar: stacked auxiliaries are a parsing-difficulty fault, not a fact at risk. |
| PSTE-G6 | 0.5 | MUST rule governing grammar: an -ing main verb is a form fault. The rule allows the same form as a noun part elsewhere. |
| PSTE-G7 | 0.5 | MUST rule governing grammar: a nominalization restates the same action as a noun. The rule's own example adds and removes no fact. |
| PSTE-G8 | 0.5 | MUST rule governing grammar: a phrasal verb has a single-verb replacement in Appendix C, so the meaning survives and only the form changes. |
| PSTE-G9 | 0.5 | MUST rule governing grammar: a missing article is a grammar fault. The rule's own example states the same fact either way. |
| PSTE-G10 | 0.1 | Checker runs this at SHOULD. It flags a common and often-correct pattern for a human to confirm, and does not fail a document on a hit alone. |
| PSTE-G11 | 0.5 | MUST rule governing grammar: too many adjectives is a parsing-load fault for a non-native reader, not a lost fact. |
| PSTE-G12 | 0.5 | MUST rule governing grammar: wrong adjective order reads as wrong without changing what the adjectives describe. |
| PSTE-K1 | 0.5 | MUST rule governing how a rule is written: a malformed negation of a key word is a form fault in stating the requirement, not in its content. |
| PSTE-K2 | 0.5 | MUST rule governing how a rule is written: an unnamed actor is a form fault in the rule statement. |
| PSTE-K3 | 0.5 | MUST rule governing how a rule is written: a key word used for a fact rather than a requirement is a category fault in form. |
| PSTE-K4 | 0.5 | MUST rule governing process: skipping the checker is a process omission. It raises the risk that other faults survive uncaught, but is not itself a content fault. |
| PSTE-K5 | 0.5 | MUST rule governing process: checking accuracy out of order is a process fault. PSTE-A1 already carries the weight of an actual fact lost. |
| PSTE-L1 | 0.5 | MUST rule governing clarity: stacked hedging is a precision-of-expression fault that the standard says tells the reader less, not a removed fact. |
| PSTE-L2 | 0.5 | MUST rule governing clarity: filler text carries no information by the rule's own wording, so removing it loses nothing. |
| PSTE-L3 | 0.5 | MUST rule governing order: stating the explanation before the result is a sequencing fault. The fact itself is still present. |
| PSTE-L4 | 0.5 | MUST rule governing clarity: the same fact stated twice is redundant, not lost. The second statement is the fault, not the first. |
| PSTE-L5 | 0.5 | MUST rule governing clarity: a frame phrase states no fact by the rule's own wording, so it has nothing to lose. |
| PSTE-N1 | 0.5 | MUST rule governing sentence form: an instruction over the word limit is a length fault, not a dropped fact. |
| PSTE-N2 | 0.5 | MUST rule governing sentence form: a description over the word limit is a length fault, not a dropped fact. |
| PSTE-N3 | 0.5 | MUST rule governing sentence form: a contraction is a register fault. The rule's own example shows the identical meaning spelled out. |
| PSTE-N4 | 0.5 | MUST rule governing sentence form: omitting the subject, the verb, or an article is a grammar fault. PSTE-A1 escalates it further only if a fact is dropped too. |
| PSTE-N5 | 0.5 | MUST rule governing noun form: a multi-word noun over three words is a parsing-load fault. The rule's own example shows the same meaning in more words. |
| PSTE-N6 | 0.5 | MUST rule governing sentence form: two instructions in one sentence is a form fault, not a missing instruction. |
| PSTE-N7 | 0.5 | MUST rule governing how a tool counts words: a miscounted word changes a limit's arithmetic, not the text's content. |
| PSTE-P1 | 0.5 | MUST rule governing procedure form: a non-imperative instruction is a form fault. The rule's own example keeps the same command, worded differently. |
| PSTE-P2 | 0.5 | MUST rule governing procedure form: a misplaced condition is an order fault, not a missing condition. PSTE-A1 covers an actually dropped condition. |
| PSTE-P3 | 0.5 | MUST rule governing procedure form: an instruction placed inside a note is a structure fault that risks the reader skipping a command meant to be followed. |
| PSTE-P4 | 0.5 | MUST rule governing procedure form: an unstated expected result leaves the reader unable to confirm success. A readability fault, not a missing fact in the step. |
| PSTE-S1 | 0.5 | MUST rule governing scope of application: applying PSTE rules outside target T1 is a scope fault, not a content fault. |
| PSTE-S2 | 0.8 | A writer MUST reproduce quoted text and code character for character. The reader acts on this text as given, and a silent change is harder to detect than an obvious one. |
| PSTE-S3 | 0.5 | MUST rule governing how non-conforming quotes are marked: mislabelling a quote as a conformance failure is a process fault in the check, not a change to the quote. |
| PSTE-S4 | 0.8 | An inflected identifier is no longer the literal string the reader must use verbatim against code or a command line. A reader who trusts it acts on a name that does not exist. |
| PSTE-S5 | 0.1 | SHOULD rule: a missing code span is a formatting preference. The identifier text itself is unchanged. |
| PSTE-S6 | N/A | PSTE-S6 is MAY only, a permission with no obligation. There is no action a writer can take that breaks it. |
| PSTE-S7 | N/A | PSTE-S7 is MAY only, a permission with no obligation. There is no action a writer can take that breaks it. |
| PSTE-V1 | 0.3 | MUST rule on word choice: an out-of-set word is understood by the reader, just not the approved form PSTE-V2 assigns it. |
| PSTE-V2 | 0.5 | MUST rule governing meaning: an approved word used with the wrong meaning or part of speech breaks the one-word-one-meaning guarantee PSTE-V1 relies on. |
| PSTE-V3 | 0.3 | MUST rule on word choice: the rule's own example shows synonyms the reader already understands. The fault is rotation, not lost meaning. |
| PSTE-V4 | 0.5 | MUST rule governing identity: a renamed entity forces the reader to match two names to the same thing in the code, a precision fault PSTE-V1 alone does not cover. |
| PSTE-V5 | 0.3 | MUST rule on word choice: a coined term where an approved word already states the meaning accurately is the word-choice fault PSTE-V1 targets. |
| PSTE-V6 | 0.3 | MUST rule on word choice: a term noun used as a verb, or the reverse, is understood from context. The part of speech is the only fault. |
| PSTE-V7 | 0.3 | MUST rule on word choice: British and American spellings name the same word, so the fault is spelling convention, not meaning. |
| PSTE-V8 | 0.3 | MUST rule on word choice: a Latin abbreviation is understood by most readers. The rule exists for the reader who is not one of them, not because meaning is lost. |
| PSTE-V9 | 0.3 | MUST rule on word choice: a marketing adjective such as robust or seamless states an opinion the reader discounts, not a fact the reader loses. |
| PSTE-V10 | 0.5 | MUST rule governing meaning: the four modal meanings are genuinely different, so the wrong modal verb can flip what a sentence requires. A precision fault closer to form than to word choice. |
| PSTE-W1 | 0.8 | A writer MUST warn before an operation that destroys data or is not reversible. A reader who is not warned runs the command, and the damage is exactly what the warning exists to prevent. |
| PSTE-W2 | 0.8 | A writer MUST state the scope of the effect before the command. A reader who runs the command first and reads the scope after has already caused the effect. |
| PSTE-W3 | 0.8 | A writer MUST identify the level of risk with a word. A reader who cannot tell a warning from a caution misjudges how much care the action needs. |
| PSTE-W4 | 0.8 | A writer MUST state the specific result of the risk. A vague risk statement such as this can cause problems gives the reader nothing to act on before the damage happens. |
| PSTE-W5 | N/A | PSTE-W5 is MAY only, a permission to exceed a limit for a warning. There is no action a writer can take that breaks it. |
| PSTE-X1 | 0.1 | A semicolon is punctuation. PSTE-X2 permits every other standard mark, so this is the narrowest of the punctuation rules. |
| PSTE-X2 | N/A | PSTE-X2 is MAY only, a permission to use any other standard punctuation mark. There is no action a writer can take that breaks it. |
| PSTE-X3 | 0.1 | A missing hyphen on a compound modifier is a punctuation fault. The words and their meaning are unchanged, only momentarily harder to parse. |
| PSTE-X4 | 0.1 | Parentheses used for a second idea are a punctuation and structure fault at the weak end of the scale. PSTE-X4 still permits them for a reference or an abbreviation. |
| PSTE-X5 | 0.1 | PSTE-X5 is itself a SHOULD rule, and the standard notes it is not even an aerospace rule, added only because the em dash marks unedited machine prose. |

### 15.6 Keeping the table and the file the same

`spec/rule_weights.csv` is generated from the table in §15.5 by
`lib/build_appendix.py --weights`, the same script that generates the appendices from
`spec/wordlist.yaml`. This document is the only place a person edits a weight. A
person who needs the CSV to change edits the table above and regenerates the file.

`evals/pste_lint.py --self-test` reads both the table and the file and asserts they
agree. A mismatch fails the self-test, the same way an unknown rule identifier fails
it elsewhere in this specification.

---

## 16. Inspiration

Controlled English is an established practice with a long history. PSTE follows that
practice. The works below inspired this specification. None of them is a source for its
text.

**ASD-STE100 Simplified Technical English**, published by the AeroSpace, Security and
Defence Industries Association of Europe, is the best known controlled English for
technical documentation. It showed that a restricted vocabulary and a fixed grammar make
technical text easier to read. That demonstration inspired this work.

ASD-STE100 is a registered trademark of ASD (EU trade mark 017966390). ASD restricts the
reproduction and the distribution of its specification. This document therefore:

- Quotes no text from ASD-STE100
- Reproduces no part of the ASD-STE100 dictionary
- Uses its own rule numbers, its own rule text, and its own word list
- Makes no claim of conformance to ASD-STE100, and no claim of endorsement by ASD or by
  the STE Maintenance Group

**Conformance to PSTE is not conformance to ASD-STE100.** A reader who writes aerospace
maintenance documentation MUST use ASD-STE100 and MUST NOT use this specification. ASD
publishes it at https://asd-ste100.org.

PSTE covers a domain that aerospace controlled English does not: the construction of
software. A writer of software prose needs words such as `refactor`, `merge`, `deploy`,
`roll back`, and `deprecate`, and needs rules for identifiers, for destructive commands,
and for stated uncertainty. §5.3 of the project plan records that gap.

**Basic English**, C.K. Ogden (1930). The earliest systematic restricted-vocabulary
English.

**Politics and the English Language**, George Orwell (1946). Six rules, in particular the
rule to cut a word wherever cutting one is possible, and the rule that permits a writer to
break any rule rather than write something barbarous.

**Plain Writing Act of 2010** (US Public Law 111-274), and the plain-language guidance
that followed it.

**RFC 2119** and **RFC 8174**, for the conformance vocabulary in §2.

---

## 17. References

[RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels",
BCP 14, RFC 2119, March 1997.

[RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words",
BCP 14, RFC 8174, May 2017.

[CHERVAK] Chervak, S., Drury, C.G., and Ouellette, J.P., "Simplified English for Aircraft
Workcards", Proceedings of the Human Factors and Ergonomics Society Annual Meeting, 1996.

---

## 18. Change log

| Version | Date | Change |
|---|---|---|
| 1.0.0-draft | 2026-08-02 | First draft. |

---

## Appendices

- **[Appendix A](appendix-a.md)** — Approved words (normative).
- **[Appendix C](appendix-c.md)** — Words to avoid, and their approved alternatives
  (informative).
- **[Appendix D](conformance/README.md)** — Conformance test cases.

Appendices A and C are generated from `wordlist.yaml` by
`lib/build_appendix.py`. Edit the YAML files, then run that script. The checker reads
the same YAML, so the standard and the checker cannot disagree about which words are
approved.

> Rule identifiers are stable. A withdrawn rule keeps its identifier and is marked
> withdrawn. An identifier is never reused for a different rule.
