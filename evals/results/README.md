# Eval results

Two files per run:

    eval-2026-08-03-3f9a1b7c.json         the record
    eval-2026-08-03-3f9a1b7c-level2.html  the page a person reads
         │          └── the commit that produced it
         └── the date of that commit

Each file is self-contained. It holds the source document, every rewrite of it, the
commit, and the notice that credits the source. It stays readable after the
repository moves on, and after the corpus changes.

`evals/run.py` writes both, so a run needs no second command. The page opens in a
browser with no server and no network: the data is inside it.

Both are committed. The page is rebuildable from the result, so a copy could drift
in principle, but a result nobody can read is a result nobody checks. Rebuild one
with `python3 evals/report.py --snapshot <result>`, and read one with:

```
python3 evals/report.py --open        # the newest result
```

The markup lives in `../report-template.html`, not inside `report.py`.

## Why a run refuses on a dirty tree

The commit in the name identifies the inputs: the skill prompt, the corpus, the
standard, and the checker. Git already tracks all four, so nothing here hashes them
again.

That identity holds only when the tree matches the commit. An uncommitted edit to
`skill/SKILL.md` changes the result while the commit stays the same, so two runs
would carry one name and hold different text. `evals/run.py` refuses to start in
that case, and the refusal is what makes the name mean something.

There is no flag that skips the check. A result that no commit identifies cannot be
compared with another result, and a comparison between two such results is not
evidence.

## Compare two runs

```
python3 evals/measure.py --snapshot evals/results/eval-2026-08-01-aaaaaaaa.json
python3 evals/measure.py --snapshot evals/results/eval-2026-08-03-3f9a1b7c.json
```

Both commands with no `--snapshot` read the newest result.

Read the two commits before you read the two tables. `git diff a..b -- skill/spec` shows
what changed between the runs. A difference in the tables means nothing until you know
which input moved, and a run repeats a model, so two results from one commit can still
differ.

A conformance table is not a quality measure. See `../FUTURE-WORK.md`.
