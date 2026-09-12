# How the PSTE word list was built

This document records where `wordlist.yaml` and `terms.yaml` come from. A reader can
check how the editors built the vocabulary, and where every entry starts.

## Where this list came from

ASD-STE100 is the originating work in controlled technical English, and it showed that a
restricted vocabulary helps a reader. PSTE takes that idea and builds for software.

This file records how the PSTE list was built, word by word. It is the answer to anybody
who asks where a word came from, including the editors themselves a year from now.

## Method

### Step 1 — General English core

Seed the candidate list from a public-domain word frequency source. These are data sets,
not controlled vocabularies:

- SUBTLEX word frequency lists
- Google Books n-gram frequency data
- The General Service List (public domain)

Take high-frequency verbs, nouns, prepositions, and conjunctions. Discard words that
never appear in technical prose.

### Step 2 — Software corpus layer

Mine prose terms from permissively licensed technical writing. Take the prose only, not
the code:

- Python, Rust, and Go standard library documentation
- MDN Web Docs (CC-BY-SA)
- Kubernetes and Docker documentation (Apache 2.0)
- Git manual pages (GPL, documentation)
- IETF RFCs (unrestricted publication)

Extract nouns and verbs by frequency. Filter identifiers, code fragments, and stopwords.
This layer produces the term categories in `terms.yaml` and the domain nouns.

### Step 3 — Collapse synonym clusters

This is the work, and it is where the value of the list comes from. For each cluster of
words that name the same action or object:

1. Choose the shortest word that a reader of basic English knows.
2. Record every other word in the cluster as `instead_of`.
3. Write one approved meaning for the chosen word.

Example. The cluster `verify / confirm / validate / inspect / examine / audit / check`
collapses to `check`, with the others routed to it.

### Step 4 — Keep literal operations

A synonym is not always a synonym. When a word names a literal operation in software, it
stays approved for that use even when the cluster routes elsewhere:

- `delete` and `drop` stay, because `DROP TABLE` is a drop and deleting a file is a delete
- `validate` stays for schema validation
- `verify` stays for cryptographic verification
- `enable` stays for a feature flag

Rule PSTE-A1 governs these cases: accuracy defeats consistency.

### Step 5 — One meaning per word

Where an approved word carries two common senses, approve one sense and route the other
to a different word. Record the approved meaning in the entry.

### Step 6 — Part of speech and forms

Tag each entry with its approved part of speech and its permitted inflections, so that a
checker can enforce PSTE-V2.

## How the v0.1 entries were actually chosen

Steps 1 and 2 above describe the method at scale. The editors have not run them that
way yet, so this section records what they did instead.

A language model proposed the candidate clusters. It read the permissively licensed
documentation the corpus lists:

- Django, etcd, Cassandra and Kubernetes
- Prometheus, Caddy, BorgBackup, ripgrep and Godot
- the Chia postmortems

It proposed the words that rotate in that prose, where a writer says `utilize` in one
paragraph and `use` in the next.

The editors then decided each entry by hand, against the software sense of the word.
That step is where most of the work sits, and where a generated list stops being
trustworthy on its own.

The notes in `wordlist.yaml` record those decisions:

- `flag` stays, because a command line flag is not a warning
- `bug` stays, because every tracker says bug
- `valid` stays, because a valid certificate is not a correct one
- `drop` stays, because `DROP TABLE` is a drop

Every one of those started as a collapse a model proposed and a person rejected.

## Current state

`wordlist.yaml` version 0.1.0 covers the highest-frequency synonym clusters in software
prose. It is not yet the full list.

The editors have not yet run steps 1 and 2 at scale. The v0 entries come from step 3,
applied by hand to the clusters that cause the most rotation in software writing. The
editors found those clusters by reading the source projects that the project README
lists, and by reading common technical documentation.

A word that is absent from `wordlist.yaml` is not thereby forbidden at Level 3. The
checker reports only the words it knows. When the list is complete, Level 3 will enforce
the closed vocabulary.

## Reproducing the corpus steps

Not yet implemented. When the editors run steps 1 and 2, the extraction scripts belong in
`tools/` and their outputs belong in `spec/corpus/`. A reader can then repeat the steps
and get the same candidate list.
