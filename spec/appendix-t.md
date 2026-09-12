# Appendix T — Obligations on a tool

This appendix is informative. It binds a tool or an agent that checks or produces PSTE
text, not the writer of that text. None of its identifiers is a rule of the
specification: a document's conformance to PSTE-1 never depends on whether a tool meets
these obligations. A checker `MUST` still meet them to call itself a PSTE-1 checker.

## T.1 What a tool reports

**PSTE-T1**: The tool `MUST` name each finding by its rule identifier.

A report that omits the identifier cannot be compared against another report. A writer
who reads a finding with no identifier cannot look up the rule it cites.

## T.2 How a tool counts words

**PSTE-T2**: A tool `MUST` count words the way PSTE-N7 counts them.

A word count that disagrees with PSTE-N7 gives a writer a limit that does not match the
limit this specification states, at PSTE-N1 and PSTE-N2.

## T.3 What a checker counts mechanically

A writer cannot count and compose at the same time. The rules below are the ones a
checker measures exactly, so a writer never needs to count them by hand.

| What the tool counts | Rule |
|---|---|
| Words in a sentence | PSTE-N1, PSTE-N2, PSTE-N7 |
| Sentences in a paragraph | PSTE-D2 |
| Items in a list | PSTE-D7 |
| Words in a multi-word noun | PSTE-N5 |
| Adjectives before a noun, and their order | PSTE-G11, PSTE-G12 |
| Filler, stacked hedging, and frame phrases | PSTE-L1, PSTE-L2, PSTE-L5 |
| Not-approved words | PSTE-V1, PSTE-V3, PSTE-V8, PSTE-V9 |

A clean report from a checker is necessary. It is not enough on its own. The table
above is part of the specification a checker covers today. A rule this table does not
list still binds the writer. It waits on a checker able to measure it.

## T.4 The weight CSV and the self-test that keeps it in step

`spec/rule_weights.csv` is generated from the inline weight that follows each rule in
`spec/PSTE-1.md` by `lib/build_appendix.py`, the same script that generates the word
appendices from `spec/wordlist.yaml`. `spec/PSTE-1.md` is the only place a person edits
a weight. A person who needs the CSV to change edits the weight in the specification
and regenerates the file.

`evals/pste_lint.py --self-test` reads both the specification and the CSV and asserts
they agree. A mismatch fails the self-test, the same way an unknown rule identifier
fails it elsewhere in the tooling.
