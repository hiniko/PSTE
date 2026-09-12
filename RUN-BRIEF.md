# Brief: run the PSTE publication eval

You have a copy of this repository. Your job is one command, then commit what it
writes and hand the repository back. Nothing else needs to change.

This run costs real money and about an hour. Read the whole brief first.

## What you are running

The eval rewrites 14 committed documents with three arms, checks every rewrite
against the PSTE-1 standard, and writes a result plus two HTML pages.

    control      a plain request for simpler prose, no standard
    pste         the same request, plus the skill in skill/SKILL.md
    `pste_fixed` the pste draft, handed its own faults, asked to fix only those

A checker reads every arm locally, and a model judges the rules no regular
expression can check. `--judge-all` judges every document rather than a sample,
which is what makes this run the one worth publishing and also what makes it
expensive.

## Before you start

1. **Docker must run.** The judge calls a model inside a clean container, so
   that the model inherits no configuration from the machine.

2. **Build the image, once.** It is about 1 GB.

        python3 evals/corpus_generate.py --build

   Confirm it exists:

        docker images | grep pste-eval-clean

3. **Write a `.env` file** in the repository root. It is deliberately not
   committed, so your clone does not carry one. Copy the example and fill it in:

   ```sh
   cp .env.example .env
   ```

   Put ONE credential in it. `CLAUDE_CODE_OAUTH_TOKEN`, from
   `claude setup-token`, bills the subscription that made the token.
   `ANTHROPIC_API_KEY`, from the Anthropic console, bills API credit. The choice
   decides who pays for the run, so use whichever Sherman told you to use.

   Check it loads before you spend anything:

   ```sh
   python3 -c "import sys; sys.path.insert(0,'evals'); import corpus_generate as g; print(g.load_env_file())"
   ```

   It prints the name it loaded, never the value. An empty list means the file
   is missing, or the value is blank, and every judge call will then fail with
   "the judge container is not logged in".

4. **The tree must be clean.** `git status` must print nothing. The run names
   its result after the commit it started from, so an uncommitted edit would
   make the name claim prose the tree no longer describes. The run refuses to
   start on a dirty tree, and that refusal is correct: do not work around it.

5. **Check the tests pass** before spending anything:

   ```sh
   for t in pste_lint report semantic_lint run corpus faithfulness diagnose; do
     python3 evals/$t.py --self-test
   done
   ```

## The command

    python3 evals/run.py --level 3 --judge-all --generation-model claude-sonnet-5

Run it from the repository root. Nothing else. Do not add flags, and do not
change any default.

What each part means, so you can tell whether it ran as asked:

```
--level 3              applies the vocabulary rules as MUST, not as advice.
                       PSTE-C3 asks for level 3 on a runbook, on release notes
                       and on published documentation, which is most of this
                       corpus.
--judge-all            judges every document. Without it the judge reads five
                       and the rest report NOT JUDGED.
--generation-model     the model that writes. The judge is pinned separately
  claude-sonnet-5      to claude-opus-5 and does not move.
```

Defaults it inherits, which are correct and must not be changed: three rewrites
per document per arm, three judge passes per text, a 0.5 agreement gate, and the
fix pass on.

## What it costs

    84 generation calls   claude-sonnet-5   about 4 minutes
    14 fix pass calls     claude-sonnet-5   under 2 minutes
    126 judge calls       claude-opus-5     about 45 minutes

The judge is the expensive half. Expect 45 to 60 minutes in total. Run it in the
background and let it finish.

## While it runs

**Do not commit anything.** A commit mid-run makes the result's name wrong, and
a previous attempt was thrown away for exactly that.

Progress prints one line per generation, then one line per judged text.

## When it finishes

It writes three files into `evals/results/`:

    eval-<date>-<commit>.json          the result
    eval-<date>-<commit>-level2.html   the page, form rules only
    eval-<date>-<commit>-level3.html   the page, form and vocabulary

The last line it prints names them.

**A non-zero exit code does not mean the run failed.** The run reports how many
cells failed, and exits non-zero when any did. A judge call that fails is
recorded, named, and marked UNJUDGED on the page.

Read the summary. If it says `0 failures`, everything was judged. If it names
failed cells, say which ones in your report. Do not rerun to chase a clean exit.

If the run dies before it writes a result, nothing is saved. Say so rather than
trying to repair it.

## What to commit

    git add evals/results/
    git commit -m "eval: sonnet generation, every document judged, level 3"

Commit **only** what the run wrote. If `git status` shows anything else
modified, do not commit it, and say what it was in your report.

## What to report back

1. The three filenames it wrote.
2. The final summary lines: the document count, the arm count, and the failure
   count.
3. The per-stage line, which reads like `generation: 84 calls, 257s`.
4. Any cell it named as failed, verbatim.
5. Whether `git status` was clean before the run and after your commit.

Do not analyse the numbers. That happens back here.

## What not to do

- Do not edit the corpus, the standard, the word list, the skill, or any script.
  A number is only comparable to another number when the inputs held still.
- Do not rerun to get a better result.
- Do not change a flag to make it cheaper. A sampled run is a different
  measurement and this one is meant to be the complete one.
