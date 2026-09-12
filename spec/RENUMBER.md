# RENUMBER — old to new identifiers

This table records the B1 renumbering for the spec restructure on `feat/conciseness-rules`.
Delete this file only when Sherman says so.

## Section numbers (spec/PSTE-1.md)

| Old section | Old title | New section | New title |
|---|---|---|---|
| 1 | Introduction | 1 | Introduction |
| 2 | Conformance language | 2 | Conformance language |
| 3 | Terminology | 3 | Terminology |
| 4 | Scope of application | 6 | Scope of application |
| 5 | Conformance levels | 4 | Conformance levels |
| 5.1 | The pass threshold | — | removed (PASS/FAIL, Task A) |
| 5.2 | Why the distributed tool shows no score | — | removed (addendum, not a spec rule) |
| 5.3 | Clarity rules (all levels) | 7 | Clarity rules (all levels) |
| 6 | Vocabulary rules | 8 | Vocabulary rules |
| 7 | Grammar rules | 9 | Grammar rules |
| 8 | Sentence rules | 10 | Sentence rules |
| 9 | Structure rules | 11 | Structure rules |
| 10 | Procedure rules | 12 | Procedure rules |
| 11 | Warning rules | 13 | Warning rules |
| 12 | Punctuation rules | 14 | Punctuation rules |
| 13 | Recommendations | 15 | Recommendations |
| 14 | The check before the text is final | — | removed (process, not a writing rule) |
| 14.1 | The mechanical check | — | table rescued to Appendix T §T.4; PSTE-K4 dropped |
| 14.2 | The judgement check | — | removed (process checklist; PSTE-K5 dropped) |
| 15 | Rule weight | 5 | Rule weight |
| 15.1-15.4 | why/what/normative/how a tool uses the weight | 5.1-5.4 | same, trimmed of PASS/FAIL and §14 references |
| 15.5 | The weight table | — | removed as a table; each row now sits inline under its rule |
| 15.6 | Keeping the table and the file the same | — | removed from spec body; content moved to Appendix T §T.5 |
| 16 | Inspiration | 16 | Inspiration |
| 17 | References | 17 | References |
| 18 | Change log | 18 | Change log |

## Rule identifiers

Every surviving rule identifier (letter + number, such as `PSTE-V1`) is unchanged. Only
the C series moves and renumbers, into the new Appendix T:

| Old identifier | New identifier | Disposition |
|---|---|---|
| PSTE-C1 | — | removed entirely (B2): "not a good rule really" |
| PSTE-C2 | PSTE-T1 | moved to Appendix T §T.1 |
| PSTE-C3 | PSTE-T2 | moved to Appendix T §T.2 |
| PSTE-C4 | — | removed entirely (B2): withdrawn, no replacement |
| PSTE-C5 | — | removed entirely (B2): withdrawn, no replacement |
| PSTE-C6 | — | removed entirely (Task A): PASS/FAIL verdict |
| PSTE-C7 | PSTE-T3 | moved to Appendix T §T.3, restated without the verdict |
| PSTE-C8 | — | removed entirely (Task A): PASS/FAIL verdict |
| PSTE-K4 | — | removed entirely (B2/B7): process rule ("run a checker") |
| PSTE-K5 | — | removed entirely (B2/B7): process rule ("check accuracy last") |

All other identifiers (K1-K3, S1-S7, A1-A3, L1-L5, V1-V10, G1-G12, N1-N7, D1-D8 and
D7.1, P1-P4, W1-W5, X1-X5, R1-R6) are unchanged. 78 rules existed before this pass; 10
identifiers left the rule sections (7 removed outright, 3 relocated to Appendix T),
leaving 68 rules in the specification body.

## Cross-references removed with their sections

- The "identifier is never reused" note under Appendices (false once C1/C4/C5/C6/C8
  are gone; also a process rule, not a writing rule).
- Every cross-reference to old §5.2 and old §14/§14.1/§14.2 inside the spec body.
- The PSTE-C6 verdict paragraph in old §15.4 (Task A: verdict concept retired).

---

## Task L — conformance levels removed (spec/PSTE-1.md)

This table records the L1 renumbering for removing conformance levels entirely, on
`feat/conciseness-rules`. Applied on top of the B1 renumbering above; "Old section" here
is the section number as it stood after Task B, not the original pre-B number.

| Old section | Old title | New section | New title |
|---|---|---|---|
| 4 | Conformance levels | — | removed entirely: PSTE now has one level, every rule applies |
| 5 | Rule weight | 4 | Rule weight |
| 5.1-5.4 | why/what/normative/how a tool uses the weight | 4.1-4.4 | same, "conformance level" reference dropped from §4.3 |
| 6 | Scope of application | 5 | Scope of application |
| 6.1-6.6, 6.6.1 | (subsections) | 5.1-5.6, 5.6.1 | same |
| 7 | Clarity rules (all levels) | 6 | Clarity rules |
| 8 | Vocabulary rules | 7 | Vocabulary rules (opening rewritten: "The rules in this section are `MUST`", the Level 3/2/1 sentence removed) |
| 9 | Grammar rules | 8 | Grammar rules |
| 10 | Sentence rules | 9 | Sentence rules |
| 10.1 | Word count | 9.1 | Word count |
| 11 | Structure rules | 10 | Structure rules |
| 12 | Procedure rules | 11 | Procedure rules |
| 13 | Warning rules | 12 | Warning rules |
| 14 | Punctuation rules | 13 | Punctuation rules |
| 15 | Recommendations | 14 | Recommendations |
| 16 | Inspiration | 15 | Inspiration |
| 17 | References | 16 | References |
| 18 | Change log | 17 | Change log |

No rule identifiers changed or moved in this pass. All `§N` cross-references inside
`spec/PSTE-1.md` were updated to the new numbers, including the `#16-references` anchor
link in §1.4 (previously `#17-references`). The external reference "§5.3 of the project
plan" in §16 References is not a reference to this spec and was left unchanged.

### spec/appendix-t.md

| Old identifier | New identifier | Disposition |
|---|---|---|
| PSTE-T1 | PSTE-T1 | kept; the level-reporting clause dropped, the rule-identifier clause kept |
| PSTE-T2 | — | removed entirely: was "an agent SHOULD use Level 2 by default... Level 3 for procedures..."; choosing a level is meaningless with one level |
| PSTE-T3 | PSTE-T2 | renumbered, section T.3 -> T.2 |
| T.4, T.5 | T.3, T.4 | renumbered to close the gap left by T.2's removal |
