# The eval corpus

Real documents, written by people, under licenses that allow redistribution and
change. The eval rewrites these. No tool creates a document here, and no
document here changes.

## What is here

Fourteen documents in two classes: nine that people wrote, and five that a model
wrote. None is share-alike, so every rewrite of them falls under the license of this
project.

### Documents that people wrote

| Document | Type | Licence |
|---|---|---|
| `runbook-etcd-restore` | runbook | CC-BY-4.0 |
| `runbook-cassandra-repair` | runbook | Apache-2.0 |
| `postmortem-chia-mempool-fastforward` | incident report | Apache-2.0 |
| `postmortem-chia-clvm-cost` | incident report | Apache-2.0 |
| `migration-etcd-3-5` | migration guide | CC-BY-4.0 |
| `howto-k8s-debug-pods` | documentation | CC-BY-4.0 |
| `troubleshoot-gopls` | documentation | BSD-3-Clause |
| `troubleshoot-etcd-failures` | documentation | CC-BY-4.0 |

### Documents that a model wrote

The skill has two processes. It rewrites a document that a person wrote, and it
constrains what a model writes. A corpus of human documentation tests the first process
only, so `evals/corpus_generate.py` asks a model about this repository and commits
the answers.

Each carries front matter recording the **model**, the CLI version, the date, the
question, and the environment. The model matters most: a default moves without any
version changing, and two baselines from different models are not similar.

`claude-sonnet-5` wrote every one of them.

| Document | Type |
|---|---|
| `synth-repo-goals` | explanation |
| `synth-skill-persistence` | explanation |
| `synth-evidence` | explanation |
| `synth-pr-description` | review |
| `synth-release-notes` | release notes |

## Generating a clean baseline

A response generated on a configured machine is not a baseline. `claude -p` reads
the settings of the person who runs it.

One such subprocess was asked what it held. It reported a terse output style from
a plugin, a global CLAUDE.md, three session hook injections, and more than fifty
skills. Each of those changes how the model writes. A terse style is part of the
effect this project claims for the skill.

Command line flags switch most of that off, but a flag list is a reject list. A new
place for configuration appears, and the baseline is quietly contaminated again.

**The container removes the question.** It holds no home directory configuration, no
plugin, no hook, no memory, and no skill beyond what the CLI ships. Nothing is
inherited because nothing is there. `evals/Dockerfile.clean` is the evidence, and it
is 20 lines that anybody can read.

```
claude setup-token                     # once, on a machine with a browser
export CLAUDE_CODE_OAUTH_TOKEN=...     # bills to the subscription

python3 evals/corpus_generate.py --build
python3 evals/corpus_generate.py
```

`claude setup-token` makes a long lived token for this exact case: a script with no
browser. It needs a subscription and bills to it, so the eval costs no more than the
subscription already does. `ANTHROPIC_API_KEY` works too, and bills to API credits.

`docker run -e NAME` passes the credential by name and not by value, so the secret
never reaches a command line where `ps` would show it.

Verified after building the image: no `~/.claude`, no `~/.claude.json`, no CLAUDE.md
anywhere in the home directory, and a non-root account. The repository mounts read
only, so a subject that tries to write a file cannot.

The key arrives as an environment variable, so the image holds no credential and is
safe to rebuild and to share.

**Whoever runs this is responsible for a clean environment.** The tool does not check
the machine. It does not ask the model to describe its own context. Both checks are
weaker than a container that never held the configuration.

Every one of them fails the checker. That is the point: a corpus of documents that
already passed would measure nothing.

**The markup stays.** A document from a documentation site carries front matter,
pattern calls, and links. A rewrite has to survive them, so removing them would hide
the failure instead of testing for it.

**No document has to stress every rule.** The corpus tests across documents, not
within one.

`troubleshoot-etcd-failures` states no number and no identifier, so it tests the
grammar rules alone. `postmortem-chia-mempool-fastforward` carries 67 numbers, so it
tests whether a rewrite keeps them. More documents beat richer documents.

**One gap worth knowing.** The corpus holds no wiki-style document, which is prose
that some people wrote over some years in different voices.

## Why the documents are real, and committed

The eval asks whether the skill makes a document easier to read. That question needs
a document.

An earlier version of the eval gave a model a one-line short request and asked each
arm to **write** a document. That measured nothing. Each arm invented different
content, so content and form moved together, and a reader cannot separate the two.

For one short request, the three arms produced 310, 239, and 741 words of different
material. No comparison between them said anything about the skill.

Now every arm rewrites the same committed document. The corpus holds the content
still, so only the form moves.

## The three texts

| Text | Where it comes from |
|---|---|
| `source` | The file in this directory. Committed. Nothing generates it. |
| `control` | A rewrite, asked for plainly: *"Rewrite this document to be simpler to read."* |
| `pste` | A rewrite, with the skill. |

The comparison that matters is `pste` against `control`. The eval gives both arms
the same request, so the skill is the only difference between them. **A skill that
cannot beat a plain request for the same thing has not earned its complexity.**

The source is also the control for accuracy. `faithfulness.py` compares it with each
rewrite and reports every number, unit, identifier, negation, and scope word that
the rewrite dropped. That is the check that guards rule PSTE-A1, and it could not
run at all while the eval generated its own documents.

## Adding a document

Use the tool. It downloads the document, computes the sha256 and the word count from
the bytes it received, and appends the record:

```
python3 evals/corpus_add.py \
    --id runbook-postgres-failover \
    --type runbook \
    --title "Postgres failover procedure" \
    --url https://raw.githubusercontent.com/example/repo/main/docs/failover.md \
    --author "Example Project contributors" \
    --licence Apache-2.0

python3 evals/corpus_add.py --dry-run ...   # fetch and report, write nothing
```

Three fields have to agree: the file, its sha256, and its word count. A person who
types those by hand gets one wrong eventually. The corpus check then fails for a
reason that has nothing to do with the document.

`MANIFEST.yaml` needs every field. `evals/corpus.py --check` verifies each one, and
`run.py` refuses to start when the check fails.

1. **The license must allow redistribution and change.** Allowed: `CC0-1.0`,
   `public-domain`, `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`,
   `CC-BY-4.0`, `CC-BY-SA-4.0`, `CC-BY-SA-3.0`. A rewrite is a change, and
   this repository is public, so a no-derivatives or non-commercial license does
   not allow a rewrite at all.

   A **share-alike** source makes its rewrites share-alike too. The tooling records
   that per document, so nobody has to trace it by hand. See
   [LICENSES.md](../../LICENSES.md).
2. **Record the source:** the URL, the author or project, the license, and the
   date of retrieval.
3. **Record the sha256** of the file as committed. The check compares it, so nobody
   can edit a source document unnoticed. A source document that changes is no longer
   the document the manifest describes. Every result that names it then stops being
   similar.
4. **Keep the document whole** where you can. An excerpt must set `excerpt: true`
   and say what it cut.
5. **Attribution travels with the result.** `corpus.attribution()` builds the notice,
   `run.py` stores it beside the outputs, and `report.py` prints it. For `CC-BY-4.0`
   the notice must say the text is a change.

Choose documents that stress the rules: numbers with units, ordered steps,
warnings, identifiers, and conditions. A document with none of those cannot show
whether a rewrite dropped anything.

## What the types are for

The `type` field matches the artifact types that put the skill into strict mode
(`skill/hooks/pste-config.js`): runbook, release notes, incident report, error <!-- pste-lint: ignore -->
message, documentation, api docs, migration guide, and so on.

The corpus covers the types that cause strict mode in real use, because the skill
claims to help with those documents.
