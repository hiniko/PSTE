# Measuring readability: what we built, what we rejected, and what comes next

This document records a survey of automated ways to measure readability and
comprehension, and the reasons behind each decision. It exists so that a later
reader does not repeat the survey, and does not adopt a measure that this project
already rejected for a stated reason.

Date of the survey: 2026-08-02.

## All tooling lives in evals/

Every checker and measure in this repository is verification tooling. Nothing here
is distributed as a standalone product, so nothing here needs to stay dependency-free
for a consumer's sake. `evals/pste_lint.py` happens to have no dependencies, because a
regular expression does not need one, not because a distribution rule requires it.

Anything in `evals/` that takes a dependency must record it, and its licence, in
this file.

## The problem this solves

`evals/pste_lint.py` counts the things that PSTE-1 forbids. The skill prompt tells a
model to avoid those same things. A good score there shows that the model followed
the instruction. It cannot show that a reader understands more.

Every measure below is judged against one question: **is it independent of the
rules, or does it restate them?**

## Built

### Vocabulary coverage — `evals/readability.py`

The share of words that a reader can be expected to know, against a core word list
plus the vocabulary that PSTE-1 itself defines.

**Why this one.** It is the only family in the survey with evidence that runs
against real comprehension scores rather than against another metric. Nation (2006)
and Laufer and Ravenhorst-Kalovski (2010) found two thresholds for readers whose
first language is not English: 95 percent coverage for reading with support, and 98
percent for independent reading. Those readers are the ones this project most wants
to help, and they are the group with the largest measured gain in the study that
motivates the whole standard.

**Independence.** Fully independent of the sentence-length rules. Partly correlated
with the short-word rules, because common English words tend to be short. The demo
below shows the independence is real.

**Demonstration.** A passage of short sentences built from rare Latinate words
scores **0 findings** in the rule checker and **5.26 percent** coverage here. The
rule checker cannot see the problem at all. That is the gap this measure fills.

### Fact preservation — `evals/faithfulness.py`

Compares a source with its rewrite and reports every number, unit, identifier,
negation, obligation, condition, and scope word that the rewrite lost or changed.

**Why this one first.** Rule PSTE-A1 says that accuracy defeats every other rule,
and nothing enforced it. The rule checker made the problem worse: a rewrite that
drops a fact has fewer words to break a rule with, so it scores **better**. The
checker rewarded the failure that the standard most fears.

**Why every check is deterministic and not a model.** Entailment models score a
rewrite as faithful after a number changes (Park 2019, "Breaking Numerical
Reasoning in NLI"). A rewrite that turns 30 seconds into 300 seconds is exactly the
error this project must catch, so the numeric checks are string comparisons.

**Demonstration.** A rewrite that reads well and scores 1 finding in the rule
checker lost the rate limit, the status code, the header name, a prohibition, and
the scope of a statement. This script reports all five.

## Rejected, with reasons

### Classical readability formulas — circular

Flesch-Kincaid, Flesch Reading Ease, Gunning Fog, SMOG, Coleman-Liau, ARI, LIX, RIX,
and Linsear Write are all functions of word length and sentence length. PSTE-1 sets
limits on word length and sentence length. Reporting them as support for the
standard would restate the rule checker in another form.

Two further reasons:

- Tanprasert and Kauchak (2021) showed that a writer raises the Flesch-Kincaid score
  by cutting sentences mechanically, with no gain for a reader.
- The formulas were validated on graded school passages for children in the 1920s.
  DuBay (2004) records the history. A 2025 eye-tracking study (arXiv:2502.11150)
  found that these formulas predict measured reading ease poorly. The US Agency for
  Healthcare Research and Quality warns against using them for technical material.

`evals/readability.py --include-circular` prints Flesch-Kincaid under a label that
says what it is, for comparison with other published work. Do not cite it as
support.

**Dale-Chall** is the least bad of the family, because half its score comes from a
familiarity word list rather than from length. It is not used here because its
sentence-length term still drives roughly half the score, and its 1948 word list
marks ordinary software vocabulary as difficult.

### Language model surprisal and perplexity — independent but counter-evidenced

Per-word surprisal predicts human reading time. The finding is well replicated
(Hale 2001; Levy 2008; Smith and Levy 2013). It is genuinely independent of the
length rules.

Rejected for two reasons:

1. **The failure mode runs backwards for this project.** A precise technical term is
   rare in general text, so a general language model scores it as surprising, while
   a trained reader finds it clearest. Surprisal would penalise good controlled
   terminology.
2. **Counter-evidence inside the literature.** Oh and Schuler (TACL 2023) found that
   surprisal from larger, lower-perplexity models fits human reading time *worse*.
   Lower perplexity and better reading-time fit are different axes.

Uniform information density adds nothing here. Meister et al. (2021) found its
strongest signal is for acceptability judgments, not comprehension.

### Automated cloze testing — disconfirmed

Mask every Nth word and have a model restore it. The idea is attractive because the
classical human comprehension test is a cloze test.

Rejected because the direct test of the idea disconfirms it. Jacobs, Grobol and
Tsang (2024, arXiv:2410.12057) found that model completions diverge from human
response distributions in both lexical and semantic terms. The same backwards
failure mode applies: a passage of precise, unambiguous terms scores worse than a
vague one.

### Reference-based simplification metrics — blocked

SARI, BLEU, and LENS need human-written gold rewrites that this project does not
have. BLEU is worse than unusable here: Sulem et al. (2018) showed it penalises
valid sentence splitting, which PSTE-1 requires.

### Model as judge — not yet

Cheap and flexible, but Liu et al. (2025, arXiv:2504.09394) found that model judges
agree with each other more than with humans, and are least reliable on the
simplicity dimension. They also favour longer answers, which for a standard about
concise writing is a bias pointing the wrong way.

Worth revisiting with a judge from a different model family than the writer, and
only alongside a human sample that calibrates it.

## Worth building next

Three items were held back because they need a dependency that a regular expression
does not. Because `evals/` may take dependencies, they are open. Each belongs in
`evals/`.

### Entailment checking, as a second layer on fact preservation

`evals/faithfulness.py` catches what a string comparison can catch. An entailment
model catches a claim that survives every number and still contradicts the source.

- **Tool:** SummaC (Laban et al., TACL 2022). `pip install summac`, Apache 2.0,
  maintained. Sentence-level aggregation, which fixes the granularity problem of
  naive document-level entailment.
- **Cost:** PyTorch plus a model download. Acceptable in CI, not for a consumer.
- **Constraint:** it must run **alongside** the deterministic checks, never instead
  of them. These models score a rewrite as faithful after a number changes, which
  is this project's highest-stakes error. The deterministic layer stays primary.
- **Caveat to record:** every benchmark for these tools is news summarization or
  generic fact-verification. None covers technical documentation.

### Vocabulary coverage against a real frequency corpus

`evals/core-vocabulary.txt` is a hand-built list of about 1,000 words. It is
auditable and needs nothing, but it is a floor rather than a graded scale.

- **Tool:** `wordfreq` (MIT). Gives a Zipf frequency per word, so coverage becomes a
  curve rather than a yes or no.
- **Cost:** about 57 MB. This is exactly why it cannot go in the distributed
  checker, and exactly why it is fine here.
- **What it adds:** graded bands rather than one threshold, and a check on whether
  the hand-built list is missing common words.
- **Keep both.** The hand-built list stays the default so the checker runs with
  nothing installed. The corpus version becomes a CI-only cross-check.

### Dale-Chall with this project's own word list

Rejected above because its 1948 list marks ordinary software vocabulary as
difficult. That objection disappears if the stock list is replaced with Appendix A
plus the term categories, which is what this project's readers actually know.

The result is no longer Dale-Chall and must not be reported under that name. It is
a familiarity measure over this standard's vocabulary, and it is close to what
`evals/readability.py` already computes. Low priority.

## Next: the blind reading trial

**This is the real validation, and it is a separate project.**

Everything above is a proxy. A proxy can show that text has properties associated
with readability. Only a reader can show that a reader understands more.

### Shape of the trial

1. Build a corpus. For each source document, produce a control version and a PSTE
   version. Hold the facts constant, so that only the form changes. Check each pair
   with `evals/faithfulness.py` first: a pair that fails is not a fair comparison,
   because the two versions no longer say the same thing.
2. Put it on the web. A reader gets one version, does not know which, reads it, and
   answers questions about it.
3. Measure answer accuracy, time to answer, and confidence.
4. Record whether English is the reader's first language. The study that motivates
   this project found the largest gain in that group, and a trial that does not
   record it cannot test the strongest version of the claim.

### What makes it valid

- **Blind.** The reader must not know which version they have, and must not know
  what the trial is testing.
- **Between subjects.** One reader sees one version of a given document. A reader
  who sees both has already learned the content.
- **Questions written from the source.** Not from either rewrite, or the questions
  favour the version they came from.
- **Report the null.** Publish the result whether or not PSTE wins. A trial that
  only gets published when it agrees with the author is not evidence.

### The automated proxy worth building alongside it

The one method in the survey with direct validation against human comprehension:
generate questions from the source, then have a model answer them reading only each
rewrite, and compare accuracy. Agrawal and Carpuat (2024, arXiv:2312.10126) measured
this design against human reading comprehension and found Spearman correlation of
0.838. On the same data, SARI reached 0.719, BERTScore 0.167, and BLEU −0.012.

Failure modes to control for:

- The model may answer from what it already knows. Test it with no text at all, and
  subtract that score.
- Generated questions skew toward facts about entities, and under-cover procedures.
  A standard for runbooks needs questions of the form "what must you do before X".
- Question generation with a sampling model is not reproducible. Use greedy decoding
  and commit the questions.

Building this needs API calls per run, so it belongs with the trial rather than in
the offline checks.

## Standing warning

If this project ever tunes PSTE to score better on the measures in this directory,
it has built a second circular loop with more steps. These measures exist to detect
a problem, not to be optimised against.

Until the trial runs, the honest claim is that PSTE text **passes several
independent automated checks**. It is not that PSTE text is easier to read.

## References

- Agrawal and Carpuat (2024). Do Text Simplification Systems Preserve Meaning?
  arXiv:2312.10126.
- Chervak, Drury and Ouellette (1996). Simplified English for Aircraft Workcards.
  Human Factors and Ergonomics Society Annual Meeting 40(1):303-307.
- DuBay (2004). The Principles of Readability.
- Hale (2001); Levy (2008); Smith and Levy (2013), Cognition. Surprisal and reading
  time.
- Jacobs, Grobol and Tsang (2024). Large-scale cloze evaluation. arXiv:2410.12057.
- Laufer and Ravenhorst-Kalovski (2010). Reading in a Foreign Language 22(1).
- Liu, Nam, Cui and Swayamdipta (2025). arXiv:2504.09394.
- Meister et al. (2021). Revisiting Uniform Information Density. EMNLP.
- Nation (2006). Canadian Modern Language Review 63(1).
- Oh and Schuler (2023). TACL.
- Park (2019). Breaking Numerical Reasoning in NLI.
- Sulem, Abend and Rappoport (2018). BLEU is Not Suitable for Simplification. EMNLP.
- Tanprasert and Kauchak (2021). Flesch-Kincaid is Not a Text Simplification
  Evaluation Metric. ACL GEM.
