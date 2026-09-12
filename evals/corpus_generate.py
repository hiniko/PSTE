#!/usr/bin/env python3
"""Generate the synthetic half of the corpus: unconstrained model-authored docs.

    python3 evals/corpus_generate.py --list
    python3 evals/corpus_generate.py --build      # build the container image
    python3 evals/corpus_generate.py              # generate, in the container
    python3 evals/corpus_generate.py --only synth-caddy-automatic-https

WHY A SECOND KIND OF DOCUMENT

The human half of the corpus asks whether the skill can rewrite a document that a
person wrote. That is one of the two jobs the skill claims. The other job is to
constrain what a model writes in the first place, and a corpus of human
documentation cannot test it.

So this generates the answers a model gives when somebody asks about a code base,
and commits them. Each answer becomes a source document, and the same two arms
rewrite it. The content is fixed before the arms run, so the comparison stays fair.

THE BASELINE MUST BE CLEAN, AND THE CONTAINER IS THE GUARANTEE

An answer generated in a session that carries a terse output style is not a
baseline. It is part of the way to the result the skill claims to produce, and an
eval built on it reports an effect that the style produced.

A plain `claude -p` on a developer machine inherits everything that developer has
configured. One such subprocess, asked what it held, reported a terse output style
from a plugin, a global CLAUDE.md, three session hook injections, and more than
fifty skills. Every one of those changes how the model writes.

Command line flags can switch most of that off, but a flag list is a deny list: a
new configuration surface appears, and the baseline is quietly contaminated again.

**The container removes the question.** It holds no home directory configuration, no
plugin, no hook, no memory, and no skill beyond what the CLI itself ships. Nothing
is inherited because nothing is there. The Dockerfile is the evidence, and a reader
can check it in a way that no assurance in a document can match.

    claude setup-token                     # once, on a machine with a browser
    export CLAUDE_CODE_OAUTH_TOKEN=...
    python3 evals/corpus_generate.py --build
    python3 evals/corpus_generate.py

`claude setup-token` makes a long lived token for exactly this case: a script with
no browser. It needs a subscription and bills to it, so the eval costs no more than
the subscription already does. ANTHROPIC_API_KEY works too, and bills to API
credits.

The credential goes in as an environment variable, so the image holds none, and
`docker run -e NAME` passes it by name so that it never reaches a command line.

`--allow-host` exists for a developer who wants a quick look. It runs on the host
with isolation flags, refuses to write anything, and prints what it would produce.
It cannot write a corpus document, because a document generated that way is not a
baseline this project will stand behind.

TOPICS: REAL SYSTEMS, NOT THIS REPOSITORY

The first five synthetic documents were all questions about PSTE itself: one
subject, one vocabulary. Between two runs with no change to that arm, the control's
synthetic-doc findings moved 76 -> 93 (+22%) while the human-authored docs moved 90
-> 91 (+1%). Subject narrowness was confounded with AI-authorship, and the fix is
documents whose SUBJECT varies while the AI-authorship stays constant.

`TOPICS` asks a model to write a documentation page about a real open source
feature. It is grounded, not paraphrased: `--only` and the default run fetch the
live upstream page ON THE HOST first (reusing corpus_add.fetch(), so there is one
fetcher and one licence gate, not two), and hand the fetched text to the container
as a second read-only mount, `/grounding/<id>.md`, alongside the existing `/repo`
mount. The prompt tells the subject that file is background to consult, not text to
rewrite, and repeats the instruction that it must produce its own independent
treatment. Embedding a 500-1500 word fetched page inside the CLI's `--` argument
was the other option; a mount was chosen because it keeps the prompt short and
reviewable in the front matter and avoids command-line length and quoting limits
that grow with every future topic.

Provenance never confuses the two authors: the generated page is `licence:
CC0-1.0` (the model's prose is new work), and the upstream `url` and its own
licence are recorded in the front matter and the manifest note, never propagated
as the licence of the generated file.
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evals"))

import corpus  # noqa: E402
import corpus_add  # noqa: E402

IMAGE = "pste-eval-clean"
DOCKERFILE = os.path.join(ROOT, "evals", "Dockerfile.clean")

# THE GENERATION MODEL, PINNED. Never left to the CLI default: a default reads
# from the operator's own settings, and one full eval ran unnoticed on Fable
# that way — the very failure this constant exists to close off.
#
# Sonnet: this generates the corpus documents both eval arms then rewrite, and
# the front matter already claims Sonnet produced them. Pinning it here is
# what makes that claim true for every document generated from now on,
# instead of a hardcoded guess. `image_model()` below still asks the
# container what actually answered, so a claim in the front matter is
# verified, not assumed, even with a pin in place.
MODEL_GENERATION = "claude-sonnet-5"

# Either credential works, and the container holds neither. Both arrive as an
# environment variable at run time.
#
#   CLAUDE_CODE_OAUTH_TOKEN   a long lived token from `claude setup-token`. It
#                             needs a subscription, and it bills to that
#                             subscription. Preferred: the eval costs no extra.
#   ANTHROPIC_API_KEY         a key from console.anthropic.com. It bills to API
#                             credits.
#
# `claude setup-token` opens a browser, so a person runs it once and exports the
# result. That is the whole reason the command exists.
CREDENTIAL_VARS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")

ENV_FILE = os.path.join(ROOT, ".env")


def load_env_file(path=ENV_FILE):
    """Read `.env` into this process, so a run needs no manual export.

    THE VALUE NEVER LEAVES THIS PROCESS. It goes into `os.environ`, and from there
    `docker run -e NAME` passes it by name. It is never printed, never written to a
    result, and never placed on a command line where `ps` would show it.

    `.env` is in `.gitignore`. A credential in a commit is a leaked credential.
    """
    if not os.path.exists(path):
        return []

    loaded = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip().strip("\"'")
            if name in CREDENTIAL_VARS and value and not os.environ.get(name):
                os.environ[name] = value
                loaded.append(name)
    return loaded

# The answer must be prose in the reply, and never a file. A subject with the Write
# tool treats "write the release notes" as a filesystem task, and then asks for
# permission rather than answering the question.
DENIED_TOOLS = "Write,Edit,NotebookEdit"

# A document shorter than this is not a document. A subject that refuses, or asks a
# question back, lands well under it.
MIN_WORDS = 150

# EVERY QUESTION READS A REPOSITORY THAT DESCRIBES A WRITING STANDARD.
#
# A subject that reads PSTE and then writes its answer in PSTE has contaminated the
# baseline with the very thing under test. It happened: one answer came back with 5
# findings where its siblings had 28 to 66, because the model announced it would
# "write the release notes in PSTE style itself".
STYLE_GUARD = (
    " Write in your own normal style. Do not apply any writing standard, style "
    "guide, or controlled language that you find in that repository."
)

# Load no settings from any source: not the user's, not the project's, not the
# local one. In the container almost nothing exists to load, but the mounted
# repository is a project directory, and it holds a plugin and a skill. These
# flags make certain that neither ever reaches the subject.
ISOLATION_FLAGS = [
    "--setting-sources",
    "",
    "--strict-mcp-config",
    "--settings",
    '{"enabledPlugins":{},"hooks":{}}',
]

# The same flags, for `--allow-host`. On a configured machine they switch off only
# what they know about, which is why a document generated there never reaches the
# corpus.
HOST_FLAGS = ISOLATION_FLAGS

QUESTIONS = [
    {
        "id": "synth-repo-goals",
        "type": "explanation",
        "title": "What this repository is for",
        "question": (
            "Read the repository at /repo and describe its goals. What problem does it "
            "solve, who is it for, and what does it deliberately not claim? "
            "Answer in prose for a developer who has never seen it. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository."
        ),
    },
    {
        "id": "synth-skill-persistence",
        "type": "explanation",
        "title": "How the skill stays active during a session",
        "question": (
            "Read the repository at /repo and explain how the skill makes sure it is still "
            "applied late in a long session, after the conversation has been "
            "compacted. Describe the mechanisms and why each one exists. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository."
        ),
    },
    {
        "id": "synth-evidence",
        "type": "explanation",
        "title": "The evidence behind the standard",
        "question": (
            "Read the repository at /repo and explain what evidence supports the claim "
            "that its controlled English helps a reader. Cover what has been "
            "measured, what has not, and which measures the project rejected. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository."
        ),
    },
    {
        "id": "synth-pr-description",
        "type": "review",
        "title": "Pull request description for the conformance checker",
        "question": (
            "Read /repo/evals/pste_lint.py and write the pull request "
            "description that would accompany it, as if you had just written the "
            "file. Cover what it does, the design decisions, and what a reviewer "
            "should look at closely. Return the description as your reply. Do not "
            "create a file." + STYLE_GUARD
        ),
    },
    {
        "id": "synth-release-notes",
        "type": "release notes",
        "title": "Release notes for version 0.1.0",
        "question": (
            "Read the repository at /repo and write the release notes for version 0.1.0. "
            "Cover what a user gets, how to install it, the known limits, and what "
            "is not ready yet. Return the release notes as your reply. Do not "
            "create a file." + STYLE_GUARD
        ),
    },
]

# The instruction that keeps a grounded answer independent. The fetched page sits
# at /grounding/<id>.md so the subject can check a fact, but the document it
# produces must be its own treatment: same job the STYLE_GUARD does for writing
# style, aimed at content instead. Without this, "write a documentation page"
# plus a source file in front of the model is an invitation to paraphrase, and a
# paraphrase is not what "what a model writes unprompted" is supposed to measure.
INDEPENDENT_TREATMENT_GUARD = (
    " A copy of an upstream page for this topic is mounted at {grounding_path}. Use "
    "it only to check facts and stay accurate. Do not paraphrase it, follow its "
    "structure, or reuse its wording: write your own independent documentation "
    "page, organised and expressed the way you normally would. Reply with the "
    "documentation page and nothing else: no preamble, no note about your tools "
    "or what you can and cannot do, no closing remark."
)

# TOPICS: real, external, permissively licensed FOSS projects. Each becomes a
# `synth-<id>` document, grounded in a live fetch of the named URL and written as
# an independent treatment (INDEPENDENT_TREATMENT_GUARD) in the subject's own
# style (STYLE_GUARD). Domain and licence both vary deliberately, so the
# synthetic half of the corpus is no longer one subject in one vocabulary.
#
# Every `licence` here is checked against corpus.ALLOWED_LICENCES by self_test()
# and by generate_topic() before a fetch is trusted, exactly like corpus_add.py.
TOPICS = [
    {
        "id": "synth-caddy-automatic-https",
        "type": "documentation",
        "system": "the Caddy web server",
        "feature": "automatic HTTPS",
        "fetch_url": (
            "https://raw.githubusercontent.com/caddyserver/website/master/"
            "src/docs/markdown/automatic-https.md"
        ),
        "licence": "Apache-2.0",
    },
    {
        "id": "synth-borg-quickstart",
        "type": "documentation",
        "system": "BorgBackup",
        "feature": "the backup and restore quickstart workflow",
        "fetch_url": (
            "https://raw.githubusercontent.com/borgbackup/borg/master/"
            "docs/quickstart.rst"
        ),
        "licence": "BSD-3-Clause",
    },
    {
        "id": "synth-prometheus-query-basics",
        "type": "documentation",
        "system": "Prometheus",
        "feature": "the basics of its query language, PromQL",
        "fetch_url": (
            "https://raw.githubusercontent.com/prometheus/prometheus/main/"
            "docs/querying/basics.md"
        ),
        "licence": "Apache-2.0",
    },
    {
        "id": "synth-ripgrep-usage",
        "type": "documentation",
        "system": "ripgrep",
        "feature": "everyday command line usage and pattern matching",
        "fetch_url": (
            "https://raw.githubusercontent.com/BurntSushi/ripgrep/master/GUIDE.md"
        ),
        "licence": "MIT",
    },
    {
        "id": "synth-godot-signals",
        "type": "documentation",
        "system": "the Godot game engine",
        "feature": "signals, its event and callback mechanism",
        "fetch_url": (
            "https://raw.githubusercontent.com/godotengine/godot-docs/master/"
            "getting_started/step_by_step/signals.rst"
        ),
        "licence": "MIT",
    },
]


def topic_question(topic):
    """The prompt for one TOPICS entry: independent, grounded, unstyled."""
    grounding_path = f"/grounding/{topic['id']}.md"
    return (
        f"Write a documentation page for {topic['feature']} in {topic['system']}."
        + INDEPENDENT_TREATMENT_GUARD.format(grounding_path=grounding_path)
        + STYLE_GUARD
    )

DOCKERFILE_TEXT = """\
# A clean room for generating eval baselines.
#
# This image exists so that a generated document carries no instruction from the
# machine that produced it. It holds no CLAUDE.md, no plugin, no hook, no memory,
# and no configured skill. Nothing is inherited, because nothing is here.
#
# Authentication arrives as an environment variable at run time, so the image
# holds no credential and is safe to rebuild and to share.
#
#   claude setup-token                      # once, on a machine with a browser
#   export CLAUDE_CODE_OAUTH_TOKEN=...      # bills to the subscription
#
#   docker build -f evals/Dockerfile.clean -t pste-eval-clean .
#   docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN -v "$PWD:/repo:ro" \\
#       pste-eval-clean claude -p -- "your question"
#
# ANTHROPIC_API_KEY works too, and bills to API credits instead.

FROM node:22-slim

RUN apt-get update \\
    && apt-get install -y --no-install-recommends git ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# A non-root user with an empty home. No configuration reaches this account.
RUN useradd --create-home --shell /bin/bash evaluser

# A writable scratch directory that the agent owns. The repository mounts read
# only, so without this the agent has nowhere to put a temporary file and reports
# a permission error instead of answering the question.
RUN mkdir -p /work && chown evaluser:evaluser /work

USER evaluser
WORKDIR /work

# Fail loudly rather than fall back to an interactive login.
ENV CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

ENTRYPOINT []
CMD ["claude", "--version"]
"""


def have_docker():
    return shutil.which("docker") is not None


def image_exists():
    if not have_docker():
        return False
    out = subprocess.run(
        ["docker", "image", "inspect", IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.returncode == 0


def write_dockerfile():
    with open(DOCKERFILE, "w", encoding="utf-8") as fh:
        fh.write(DOCKERFILE_TEXT)
    return DOCKERFILE


def build_image():
    write_dockerfile()
    print(f"building {IMAGE} from {DOCKERFILE}...")
    out = subprocess.run(
        ["docker", "build", "-f", DOCKERFILE, "-t", IMAGE, ROOT],
        check=False,
    )
    return out.returncode


def credential():
    """The credential variable this machine has set, or None.

    Returns the NAME, and never the value. `docker run -e NAME` passes the value
    from the environment without it appearing in a command line, where `ps` and a
    shell history would both record it.
    """
    for name in CREDENTIAL_VARS:
        if os.environ.get(name):
            return name
    return None


def container_command(
    question, credential_var, grounding_file=None, grounding_id=None, model=MODEL_GENERATION
):
    """The command that runs one question inside the clean image.

    `model` defaults to `MODEL_GENERATION`, but the judge (semantic_lint.py)
    passes its own model here too — this is the one place a `claude -p`
    command for the container gets built, so it is also the one place the
    pin has to happen.

    THE WORKING DIRECTORY IS NOT THE REPOSITORY.

    The repository holds `.claude-plugin/plugin.json`, `skill/SKILL.md`, and two
    hooks. A CLI that starts inside a directory treats what it finds there as
    project configuration, and the subject would then run under the very skill the
    eval measures. So the run starts in `/work`, and reads the repository through
    an explicit path.

    Checked: from `/repo`, a subject reported the plugin, the skill, the two slash
    commands, and the hooks, and said none were active. Discovery is one release
    away from loading, and this arrangement removes the question.

    `grounding_file` is a host path fetched by generate_topic() BEFORE this
    container ever starts, so the container never touches the network for it. It
    mounts read only at `/grounding/<grounding_id>.md`, next to `/repo`, and the
    prompt (INDEPENDENT_TREATMENT_GUARD) is the only thing that tells the subject
    it exists.
    """
    mounts = ["-v", f"{ROOT}:/repo:ro"]
    add_dirs = ["--add-dir", "/repo"]
    if grounding_file:
        mounts += ["-v", f"{grounding_file}:/grounding/{grounding_id}.md:ro"]
        add_dirs += ["--add-dir", "/grounding"]
    return [
        "docker",
        "run",
        "--rm",
        # `-e NAME` with no `=value` copies the value from this environment. Never
        # write the credential into the command line.
        "-e",
        credential_var,
        # Read only. A subject that reaches for a file cannot change one.
        *mounts,
        # A writable scratch directory the subject owns. Without one, a subject
        # that wants a temporary file reports a permission error instead of
        # answering. `tmpfs` keeps it in memory and discards it with the container.
        "--tmpfs",
        "/work:rw,size=64m,mode=1777",
        # Start outside the repository, so nothing there loads as configuration.
        "-w",
        "/work",
        IMAGE,
        "claude",
        "-p",
        # Pin the model explicitly. Never rely on the CLI default: it reads
        # from the operator's own settings, and a default that changes
        # silently changes every number this project publishes.
        "--model",
        model,
        # Grant read access to the mounted repository (and grounding file, when
        # present). The working directory is `/work`, and the CLI allows tool
        # access to that directory alone, so without this the subject cannot read
        # what it is asked about.
        #
        # This grants ACCESS, and not configuration: the isolation flags below
        # still load no settings from it. Verified after adding it, by asking a
        # subject what was active. It answered NONE.
        *add_dirs,
        # Load no settings from anywhere, including the mounted repository.
        *ISOLATION_FLAGS,
        # An eval subject asked to "write release notes" reaches for the Write
        # tool and asks permission instead of answering. Deny the filesystem tools
        # so the only way to answer is prose.
        "--disallowedTools",
        DENIED_TOOLS,
        "--",
        question,
    ]


def generate(
    question,
    use_container=True,
    timeout=900,
    credential_var=None,
    grounding_file=None,
    grounding_id=None,
):
    if use_container:
        cmd = container_command(
            question, credential_var or credential(), grounding_file, grounding_id
        )
    else:
        cmd = ["claude", "-p", "--model", MODEL_GENERATION, *HOST_FLAGS, "--", question]
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=None if use_container else ROOT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or "").strip()[:400]
    return out.stdout.strip(), None


def fetch_grounding(topic):
    """Fetch a TOPICS entry's upstream page ON THE HOST, licence-gated.

    Reuses corpus_add.fetch() rather than a second HTTP client, and refuses a
    licence outside corpus.ALLOWED_LICENCES before a single byte reaches the
    container, exactly the check corpus_add.py already makes for a human-authored
    document. Fetching here, not inside the clean room, keeps the container's only
    job "run the model" and keeps this one uncontrolled input (a live webpage) out
    of the generation environment the self-test and the Dockerfile promise is
    otherwise closed.
    """
    if topic["licence"] not in corpus.ALLOWED_LICENCES:
        raise SystemExit(
            f"refusing {topic['id']}: upstream licence {topic['licence']} is not "
            f"in ALLOWED_LICENCES: {', '.join(sorted(corpus.ALLOWED_LICENCES))}"
        )
    return corpus_add.fetch(topic["fetch_url"])


def image_version():
    """Which CLI answered. A later run on another version is not the same run."""
    out = subprocess.run(
        ["docker", "run", "--rm", IMAGE, "claude", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip() or "unknown"


def image_model(credential_var):
    """WHICH MODEL ANSWERED.

    The CLI version is not the model. Two runs of the same CLI answer with
    different models when the default moves, and the prose changes with it. A
    baseline that does not name its model cannot be compared with a later one.

    `--output-format json` reports the model under `modelUsage`, so this asks for
    the cheapest possible answer and reads the key.
    """
    cmd = [
        "docker",
        "run",
        "--rm",
        "-e",
        credential_var,
        "--tmpfs",
        "/work:rw,size=64m,mode=1777",
        "-w",
        "/work",
        IMAGE,
        "claude",
        "-p",
        # Pin the same model generation uses. This probe exists to VERIFY the
        # model that answers, not to guess it — pinning here too means the
        # `modelUsage` reply below confirms the pin actually took effect,
        # rather than reporting some other default.
        "--model",
        MODEL_GENERATION,
        *ISOLATION_FLAGS,
        "--output-format",
        "json",
        "--",
        "Reply with the single word OK.",
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, check=False
        )
        report = json.loads(out.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return "unknown"

    usage = report.get("modelUsage") or {}
    for name, detail in usage.items():
        return detail.get("canonicalModel") or name
    return report.get("model") or "unknown"


def front_matter(entry, version, today, model="unknown"):
    """The header that records how the document came to exist.

    A synthetic document is only useful when a reader can tell what produced it.
    The model, the question, the CLI version, and the environment all change the
    text, so each is recorded in the file and not only in the manifest.

    THE MODEL MATTERS MOST. The CLI version is not the model, and a default moves
    without any version changing. Two baselines from different models are not
    comparable, and nothing else in the file would reveal it.

    THE PROMPT IS PART OF THE REPORT SURFACE. It is what shapes both arms' source
    document, so it belongs here in the front matter and not only inside the
    script that ran it. A TOPICS entry also names its grounding source and that
    source's own licence, because the prompt alone does not say what fact-checking
    material the subject had in front of it.
    """
    grounding = ""
    if entry.get("fetch_url"):
        grounding = (
            f"grounding_url: {entry['fetch_url']}\n"
            f"grounding_licence: {entry['licence']}\n"
        )
    return (
        "---\n"
        f"model: {model}\n"
        f"generated_by: {version}\n"
        f"generated_on: {today}\n"
        "environment: container, evals/Dockerfile.clean\n"
        "isolation: |\n"
        "  No CLAUDE.md, no plugin, no hook, no memory, and no configured skill.\n"
        "  The container holds none of them, so none can reach the model.\n"
        "constrained: false\n"
        f"{grounding}"
        f"question: |\n  {entry['question']}\n"
        "---\n\n"
    )


def main():
    ap = argparse.ArgumentParser(
        description="Generate unconstrained model answers about this repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--build", action="store_true", help="build the container image")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument(
        "--topics",
        action="store_true",
        help=(
            "generate the real-external-system documents (TOPICS) instead of the "
            "self-referential ones (QUESTIONS)"
        ),
    )
    ap.add_argument(
        "--allow-host",
        action="store_true",
        help="run on the host with isolation flags. Writes nothing.",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    pool = TOPICS if args.topics else QUESTIONS
    for entry in pool:
        entry.setdefault("question", topic_question(entry) if args.topics else None)

    if args.list:
        for entry in pool:
            title = entry.get("title") or f"{entry['feature']} in {entry['system']}"
            print(f"{entry['id']:<32} {entry['type']:<16} {title}")
        return 0

    if args.build:
        if not have_docker():
            print("docker is not installed", file=sys.stderr)
            return 2
        return build_image()

    selected = pool
    if args.only:
        selected = [q for q in pool if q["id"] in args.only]
    if not selected:
        print("no question matches", file=sys.stderr)
        return 2

    if args.allow_host:
        # A host run is for looking, not for building a corpus. The isolation flags
        # switch off what they know about, and a flag list cannot know about a
        # configuration surface that did not exist when somebody wrote it.
        print(
            "HOST RUN. This writes nothing.\n"
            "A document generated on a configured machine is not a baseline. Use\n"
            "the container for anything that reaches the corpus.\n",
            file=sys.stderr,
        )
        for entry in selected:
            text, err = generate(entry["question"], use_container=False)
            if err:
                print(f"  {entry['id']}: FAILED {err}", file=sys.stderr)
                continue
            print(f"\n===== {entry['id']} ({len(text.split())} words) =====")
            print(text[:1500])
        return 0

    if not have_docker():
        print(
            "refusing to generate: docker is not installed.\n\n"
            "A baseline must come from an environment that holds no CLAUDE.md, no\n"
            "plugin, no hook, and no memory. The container is what guarantees that.\n"
            "See evals/Dockerfile.clean, and --allow-host for a look without one.",
            file=sys.stderr,
        )
        return 2

    load_env_file()
    credential_var = credential()
    if not credential_var:
        print(
            "refusing to generate: no credential is set.\n\n"
            "The container carries no home directory from this machine, so it needs\n"
            "a credential from the environment. Either works:\n\n"
            "    claude setup-token                       # opens a browser, once\n"
            "    export CLAUDE_CODE_OAUTH_TOKEN=...       # bills to the subscription\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...      # bills to API credits\n\n"
            "A .env file in the repository root works too, and git ignores it.\n\n"
            "Prefer the token. It needs a subscription, and the eval then costs no\n"
            "more than the subscription already does.",
            file=sys.stderr,
        )
        return 2

    if not image_exists():
        print(
            f"the image {IMAGE} does not exist. Build it:\n\n"
            "    python3 evals/corpus_generate.py --build",
            file=sys.stderr,
        )
        return 2

    version = image_version()
    model = image_model(credential_var)
    today = datetime.date.today().isoformat()
    print(
        f"environment: container {IMAGE}\n"
        f"cli: {version}\n"
        f"model: {model}\n"
        f"credential: {credential_var}\n"
    )

    written = 0
    for entry in selected:
        path = os.path.join(corpus.CORPUS_DIR, f"{entry['id']}.md")
        if os.path.exists(path):
            print(f"  {entry['id']}: exists, skipping")
            continue

        # TOPICS: fetch the upstream page on the HOST, before the container ever
        # starts, and hand it in as a second read-only mount. See the module
        # docstring for why a mount and not a prompt-embedded string.
        grounding_file = grounding_id = None
        if args.topics:
            try:
                upstream_text = fetch_grounding(entry)
            except Exception as exc:  # noqa: BLE001 - report any fetch failure alike
                print(f"  {entry['id']}: FAILED fetch: {exc}", file=sys.stderr)
                continue
            grounding_id = entry["id"]
            grounding_fh = tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            )
            grounding_fh.write(upstream_text)
            grounding_fh.close()
            grounding_file = grounding_fh.name

        try:
            text, err = generate(
                entry["question"],
                use_container=True,
                credential_var=credential_var,
                grounding_file=grounding_file,
                grounding_id=grounding_id,
            )
        finally:
            if grounding_file:
                os.remove(grounding_file)
        if err:
            print(f"  {entry['id']}: FAILED {err}", file=sys.stderr)
            continue

        words = len(text.split())

        # A subject that refuses, or asks a question back, produces a few dozen
        # words instead of a document. That is not a baseline, and it must not
        # reach the corpus quietly.
        if words < MIN_WORDS:
            print(
                f"  {entry['id']}: REFUSED, {words} words. Not written.\n"
                f"      {text[:200]}",
                file=sys.stderr,
            )
            continue

        body = front_matter(entry, version, today, model) + text + "\n"
        print(f"  {entry['id']}: {words} words")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)

        digest = corpus.hashlib.sha256(body.encode("utf-8")).hexdigest()
        if args.topics:
            title = f"{entry['feature']} in {entry['system']}".capitalize()
            manifest_url = "generated by evals/corpus_generate.py --topics"
            author = f"{model}, writing an independent documentation page"
            note = (
                f"Synthetic. An unconstrained model answer, grounded in a fetch of "
                f"{entry['fetch_url']} (upstream licence {entry['licence']}, not "
                "propagated here) and written as an independent treatment, not a "
                "paraphrase. The prompt is in the front matter."
            )
        else:
            title = entry["title"]
            manifest_url = "generated by evals/corpus_generate.py from this repository"
            author = f"{model}, answering a question about this repository"
            note = (
                "Synthetic. An unconstrained model answer, generated in the "
                "clean container. The question is in the front matter."
            )

        corpus_add.append_entry(
            corpus.MANIFEST,
            corpus_add.entry_yaml(
                {
                    "id": entry["id"],
                    "type": entry["type"],
                    "title": title,
                    "url": manifest_url,
                    "author": author,
                    "licence": "CC0-1.0",
                    "retrieved": today,
                    "sha256": digest,
                    "words": len(body.split()),
                    "excerpt": False,
                    "note": note,
                }
            ),
        )
        written += 1

    problems = corpus.check()
    if problems:
        print("\nthe corpus check failed:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"\nwrote {written} documents, and recorded them in the manifest")
    return 0


def self_test():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids)), ids
    for entry in QUESTIONS:
        for field in ("id", "type", "title", "question"):
            assert entry.get(field), entry
        assert entry["id"].startswith("synth-"), entry["id"]
        assert len(entry["question"]) > 60, entry["id"]

        # EVERY QUESTION MUST TELL THE SUBJECT NOT TO ADOPT THE REPOSITORY'S OWN
        # STYLE. Without it, a subject reads PSTE and answers in PSTE, and the
        # baseline already conforms to the standard under test.
        assert "own normal style" in entry["question"], entry["id"]

    # TOPICS: THE WELL-FORMEDNESS AND LICENCE CHECKS THAT REPLACE THE OLD SUBJECT.
    #
    # Five real, external systems, each with a fetchable URL and a licence this
    # project may actually redistribute a rewrite of (corpus.ALLOWED_LICENCES,
    # the same gate corpus_add.py uses). A `synth-` id keeps the load-bearing
    # prefix report.py's is_synthetic() and run.py's ANCHOR_DOCS_DEFAULT depend
    # on. No network call happens here — this checks shape and licence only.
    topic_ids = [t["id"] for t in TOPICS]
    assert len(topic_ids) == 5, topic_ids
    assert len(topic_ids) == len(set(topic_ids)), topic_ids
    assert len({t["system"] for t in TOPICS}) == 5, "topics must vary in subject"
    for topic in TOPICS:
        for field in ("id", "type", "system", "feature", "fetch_url", "licence"):
            assert topic.get(field), topic
        assert topic["id"].startswith("synth-"), topic["id"]
        assert topic["fetch_url"].startswith("https://"), topic["id"]
        assert topic["licence"] in corpus.ALLOWED_LICENCES, (
            topic["id"], topic["licence"], corpus.ALLOWED_LICENCES,
        )

        question = topic_question(topic)
        # The grounding source is context, never text to rewrite: both guards
        # must reach the prompt, or a fetched page becomes something the model
        # paraphrases instead of an independently written page.
        assert "own normal style" in question, topic["id"]
        assert "Do not paraphrase" in question, topic["id"]
        assert "independent" in question, topic["id"]
        assert f"/grounding/{topic['id']}.md" in question, topic["id"]
        assert topic["feature"] in question and topic["system"] in question, topic["id"]

    # THE CONTAINER MUST CARRY NO CREDENTIAL AND NO CONFIGURATION.
    #
    # A key baked into the image leaks with the image. A home directory copied into
    # it reintroduces every instruction the container exists to exclude.
    # No line may ASSIGN a credential. A mention in a comment is documentation; an
    # `ENV NAME=value` or an `ARG` default bakes the secret into every layer, and
    # the image then leaks it to anybody who pulls it.
    for line in DOCKERFILE_TEXT.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for var in CREDENTIAL_VARS:
            assert f"{var}=" not in stripped, f"credential assigned: {line}"
            assert not stripped.startswith(f"ENV {var}"), line
            assert not stripped.startswith(f"ARG {var}"), line

    for banned in ("COPY ~/.claude", "COPY /root/.claude", ".credentials.json"):
        assert banned not in DOCKERFILE_TEXT, banned
    assert "useradd" in DOCKERFILE_TEXT, "the container must not run as root"

    # The image must provide a writable directory the eval user owns, and must not
    # start in the mounted repository.
    assert "chown evaluser:evaluser /work" in DOCKERFILE_TEXT, DOCKERFILE_TEXT
    assert "WORKDIR /work" in DOCKERFILE_TEXT, "must not start in /repo"
    assert "WORKDIR /repo" not in DOCKERFILE_TEXT, "must not start in /repo"

    # The run command must pass the credential by environment, mount the
    # repository read only, and end its options before the question.
    for var in CREDENTIAL_VARS:
        cmd = container_command("Rewrite this.", var)
        assert cmd[:3] == ["docker", "run", "--rm"], cmd
        mount = cmd[cmd.index("-v") + 1]
        assert mount.endswith(":/repo:ro"), mount
        assert cmd[-2] == "--" and cmd[-1] == "Rewrite this.", cmd[-3:]

        # THE MODEL MUST BE PINNED, NEVER LEFT TO THE CLI DEFAULT. A default
        # reads from the operator's own settings, and one full eval ran
        # unnoticed on Fable that way — the failure this constant closes off.
        assert "--model" in cmd, cmd
        pinned = cmd[cmd.index("--model") + 1]
        assert pinned == MODEL_GENERATION, cmd
        assert "sonnet" in pinned or "opus" in pinned, \
            f"generation must run on Sonnet or Opus, not {pinned}"
        assert "fable" not in pinned, f"generation must never run on Fable: {pinned}"

        # A caller (the judge, semantic_lint.py) can pin a different model
        # for its own purpose, and that pin must actually take effect.
        judged = container_command("Rewrite this.", var, model="claude-opus-5")
        assert judged[judged.index("--model") + 1] == "claude-opus-5", judged

        # THE SUBJECT MUST NOT START INSIDE THE REPOSITORY.
        #
        # The repository holds a plugin, a skill, two slash commands, and two
        # hooks. A CLI that starts in a directory reads it as project
        # configuration, and the subject would then run under the skill the eval
        # measures. Start in the scratch directory instead.
        assert cmd[cmd.index("-w") + 1] == "/work", cmd
        assert "/repo" not in cmd[cmd.index("-w") + 1], cmd

        # A WRITABLE PLACE MUST EXIST.
        #
        # The repository is read only. Without somewhere to write, a subject that
        # wants a temporary file reports a permission error instead of answering.
        tmpfs = cmd[cmd.index("--tmpfs") + 1]
        assert tmpfs.startswith("/work:"), tmpfs
        assert "rw" in tmpfs, tmpfs

        # The isolation flags must reach the container run, and not only the host
        # path. The mounted repository is a project directory.
        for flag in ISOLATION_FLAGS:
            assert flag in cmd, (flag, cmd)
        assert cmd.index("--setting-sources") < cmd.index("--"), cmd

        # The filesystem tools stay denied.
        assert cmd[cmd.index("--disallowedTools") + 1] == DENIED_TOOLS, cmd

        # THE SUBJECT MUST STILL BE ABLE TO READ THE REPOSITORY.
        #
        # The CLI allows tool access to the working directory alone, so starting
        # in `/work` without this leaves the subject unable to read the repository
        # it is asked about. It answered "I do not have permission to read that
        # file" until `--add-dir` was added.
        assert cmd[cmd.index("--add-dir") + 1] == "/repo", cmd

        # THE CREDENTIAL MUST TRAVEL BY NAME, NEVER BY VALUE.
        #
        # `-e NAME` copies the value from the environment. `-e NAME=value` would
        # put the secret in the command line, where `ps` shows it to every user on
        # the machine and a shell history keeps it.
        assert cmd[cmd.index("-e") + 1] == var, cmd
        assert not any("=" in part for part in cmd if part.startswith(var)), cmd

    # THE GROUNDING FILE MOUNTS READ ONLY, ALONGSIDE /repo, AND ONLY WHEN GIVEN.
    #
    # A TOPICS run fetches upstream text on the host and must hand it to the
    # container as a second mount, never write access, and must not appear at
    # all for a QUESTIONS run (which passes no grounding_file).
    grounded = container_command(
        "Write about it.", "CLAUDE_CODE_OAUTH_TOKEN",
        grounding_file="/tmp/fetched.md", grounding_id="synth-example-topic",
    )
    mounts = [grounded[i + 1] for i, part in enumerate(grounded) if part == "-v"]
    assert any(m.endswith(":/repo:ro") for m in mounts), mounts
    assert "/tmp/fetched.md:/grounding/synth-example-topic.md:ro" in mounts, mounts
    assert "/grounding" in grounded, grounded
    ungrounded = container_command("Rewrite this.", "CLAUDE_CODE_OAUTH_TOKEN")
    assert "/grounding" not in ungrounded, ungrounded

    # The preferred credential comes first, so a machine with both set uses the
    # token and bills to the subscription rather than to API credits.
    assert CREDENTIAL_VARS[0] == "CLAUDE_CODE_OAUTH_TOKEN", CREDENTIAL_VARS

    import unittest.mock as mock

    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}, clear=True):
        assert credential() == "ANTHROPIC_API_KEY"
    with mock.patch.dict(
        os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "t", "ANTHROPIC_API_KEY": "k"},
        clear=True,
    ):
        assert credential() == "CLAUDE_CODE_OAUTH_TOKEN"
    with mock.patch.dict(os.environ, {}, clear=True):
        assert credential() is None

    # The `.env` loader must read a credential, ignore anything else, and never
    # overwrite a variable that the environment already set.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        envfile = os.path.join(tmp, ".env")
        with open(envfile, "w", encoding="utf-8") as fh:
            fh.write(
                "# a comment\n"
                "\n"
                "CLAUDE_CODE_OAUTH_TOKEN=tok-from-file\n"
                'ANTHROPIC_API_KEY="key-from-file"\n'
                "SOME_OTHER_THING=ignored\n"
            )
        with mock.patch.dict(os.environ, {}, clear=True):
            loaded = load_env_file(envfile)
            assert set(loaded) == set(CREDENTIAL_VARS), loaded
            assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-from-file"
            # Quotes come off, and a variable that is not a credential stays out.
            assert os.environ["ANTHROPIC_API_KEY"] == "key-from-file"
            assert "SOME_OTHER_THING" not in os.environ

        # An exported value wins over the file, so a person can override it.
        with mock.patch.dict(
            os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "from-shell"}, clear=True
        ):
            load_env_file(envfile)
            assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "from-shell"

    # A missing file is not an error.
    assert load_env_file(os.path.join("/nonexistent", ".env")) == []

    # The host path must stay a look-only path, and must still carry its flags.
    assert "--setting-sources" in HOST_FLAGS, HOST_FLAGS
    assert HOST_FLAGS[HOST_FLAGS.index("--setting-sources") + 1] == "", HOST_FLAGS

    # THE HOST PATH MUST ALSO PIN THE MODEL. `--allow-host` runs on a
    # configured machine, exactly where a CLI default is most likely to be
    # something other than Sonnet or Opus.
    import unittest.mock as mock

    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=0, stdout="x", stderr="")
        generate("a question", use_container=False)
    host_argv = spy.call_args[0][0]
    assert "--model" in host_argv, host_argv
    assert host_argv[host_argv.index("--model") + 1] == MODEL_GENERATION, host_argv

    matter = front_matter(QUESTIONS[0], "2.1.0", "2026-08-03", "claude-sonnet-5")
    assert matter.startswith("---\n") and matter.rstrip().endswith("---"), matter
    for needed in (
        "model: claude-sonnet-5",
        "generated_by: 2.1.0",
        "constrained: false",
        "container",
    ):
        assert needed in matter, needed
    # A QUESTIONS entry carries no grounding source, so none is printed.
    assert "grounding_url" not in matter, matter

    # A TOPICS entry's front matter must record the grounding source and its
    # licence too, not just the prompt — point 5: the prompt shapes the source
    # both arms then rewrite, so it belongs in the provenance.
    example_topic = dict(TOPICS[0], question=topic_question(TOPICS[0]))
    topic_matter = front_matter(example_topic, "2.1.0", "2026-08-03", "claude-sonnet-5")
    assert f"grounding_url: {TOPICS[0]['fetch_url']}" in topic_matter, topic_matter
    assert f"grounding_licence: {TOPICS[0]['licence']}" in topic_matter, topic_matter

    # FETCH_GROUNDING MUST REFUSE A LICENCE THIS PROJECT MAY NOT REDISTRIBUTE,
    # before any network call — same gate corpus_add.py applies at the CLI.
    try:
        fetch_grounding({"id": "synth-bad", "fetch_url": "https://x", "licence": "GPL-3.0"})
        raise AssertionError("a forbidden licence must be refused")
    except SystemExit as exc:
        assert "ALLOWED_LICENCES" in str(exc), exc

    # An allowed licence reaches corpus_add.fetch(), and nothing else: one
    # fetcher, reused, not reimplemented here.
    with mock.patch.object(corpus_add, "fetch", return_value="fetched text") as spy:
        got = fetch_grounding(TOPICS[0])
        assert got == "fetched text", got
        spy.assert_called_once_with(TOPICS[0]["fetch_url"])

    # THE MODEL MUST COME OFF THE USAGE REPORT.
    #
    # The CLI version is not the model, and a default moves without a version
    # changing. `--output-format json` names it under `modelUsage`.
    import unittest.mock as mock

    report = {
        "modelUsage": {
            "claude-sonnet-5": {"canonicalModel": "claude-sonnet-5", "costUSD": 0.05}
        }
    }
    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=0, stdout=json.dumps(report), stderr="")
        assert image_model("CLAUDE_CODE_OAUTH_TOKEN") == "claude-sonnet-5"
        argv = spy.call_args[0][0]
        assert "--output-format" in argv and "json" in argv, argv
        # The probe must be isolated too, or it reports a model that a project
        # setting selected rather than the default.
        for flag in ISOLATION_FLAGS:
            assert flag in argv, flag
        # The probe must pin the same model generation uses, so its answer
        # verifies the pin took effect rather than reporting some other
        # default.
        assert argv[argv.index("--model") + 1] == MODEL_GENERATION, argv

    # A broken reply must not become a fake model name.
    with mock.patch("subprocess.run") as spy:
        spy.return_value = mock.Mock(returncode=1, stdout="not json", stderr="boom")
        assert image_model("X") == "unknown"

    print("corpus_generate self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
