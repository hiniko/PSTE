# PSTE-1 conformance cases

These cases are Appendix D of the specification. They are also the linter's test suite.

Each case gives a conforming form and a non-conforming form for one rule. The linter's
`--self-test` asserts that it reports the rule for the non-conforming text and stays
silent on the conforming text.

If the specification and the linter disagree about a case, one of them is wrong. That is
the purpose of keeping one set of cases for both.

## Cases

| Rule | Non-conforming | Conforming |
|---|---|---|
| PSTE-L1 | This might possibly break the cache. | This can break the cache. |
| PSTE-L2 | It is important to note that the build failed. | The build failed. |
| PSTE-L3 | I looked at the config, checked the logs, and found that the timeout is too low. | The timeout is too low. I found it in the config after I read the logs. |
| PSTE-V3 | Verify the file, then validate the schema. | Check the file. Then check the schema. |
| PSTE-V4 | The order identifier is null, so the ID fails the check. | The order ID is null, so the order ID fails the check. |
| PSTE-V8 | Use a cache, e.g. Redis. | Use a cache, for example Redis. |
| PSTE-V9 | The parser is robust. | The parser recovers from a malformed header. |
| PSTE-V10 | The service should restart. | The service restarts automatically. |
| PSTE-G1 | The file is rejected by the linter. | The linter rejects the file. |
| PSTE-G4 | I have changed the timeout value. | I changed the timeout value. |
| PSTE-G5 | The value would have been read from the cache. | The cache holds the value. |
| PSTE-G6 | The worker is processing the queue. | The worker processes the queue. |
| PSTE-G7 | Perform an analysis of the log file. | Analyze the log file. |
| PSTE-G8 | Spin up the container. | Start the container. |
| PSTE-G9 | Files not backed up are skipped. | The script skips the files that the backup does not include. |
| PSTE-G11 | Replace the small round red plastic button. | Replace the small red button. |
| PSTE-G12 | Restore the legacy small database. | Restore the small legacy database. |
| PSTE-N1 | (an instruction over 20 words) | Two instructions, each under 20 words. |
| PSTE-N2 | (a description over 25 words) | Two descriptions, each under 25 words. |
| PSTE-N3 | The file doesn't exist. | The file does not exist. |
| PSTE-N5 | Read the queue priority setting handler docs. | Read the docs for the handler that sets the queue priority. |
| PSTE-N6 | Open the file and check line 3. | Open the file. Check line 3. |
| PSTE-X1 | The build failed; the log shows why. | The build failed. The log shows why. |
| PSTE-D2 | (a paragraph over six sentences) | Two paragraphs. |
| PSTE-P1 | You should run the tests. | Run the tests. |
| PSTE-P2 | Read the log if the build fails. | If the build fails, read the log. |
| PSTE-W2 | Run the backup first, because this deletes rows. | This deletes every row in `users`. Run the backup first. |
| PSTE-W4 | This can cause problems. | You lose every uncommitted change. |

## Exemptions

The linter MUST NOT report a finding for:

- Text inside a fenced code block
- Text inside a code span
- Text inside a block quote
- A quoted phrase that follows the word "not", "never", or "instead of" — a rule must be
  able to show what breaks it
- A line that contains `pste-lint: ignore`

## Known limits

A counter-example that puts the negation and the quoted phrase on different lines is not
detected. Use `pste-lint: ignore` on such a line.

The checker measures rule conformance. It does not measure readability, and it does not
measure quality. A clean report is necessary, not sufficient.
