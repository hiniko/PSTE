#!/usr/bin/env python3
"""Identify the inputs of an eval run, and refuse to run when they are not tracked.

An eval result is only comparable with another when you know what produced it. Git
already answers that question, so this module asks git and adds nothing of its own:
the commit identifies the skill prompt, the prompt set, the standard, and the
checker, all at once.

That identity holds only when the tree is clean. An uncommitted edit to SKILL.md
changes the result while the commit stays the same, so two runs would carry one name
and differ. `require_clean_tree` refuses in that case. The refusal is the thing that
makes the commit mean something.

    python3 evals/provenance.py          # show what a run would record
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DirtyTree(Exception):
    """The tree does not match a commit, so a result cannot name its inputs."""


def _git(*args, strip=True):
    """Run a git command in the repository root. Returns None when git cannot.

    `strip` must be false for `status --porcelain`. Its first column is a space
    when a change is unstaged, so stripping the output eats the leading space of
    the first line and shifts the path by one character.
    """
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() if strip else out.stdout


def is_repo():
    return _git("rev-parse", "--is-inside-work-tree") == "true"


def dirty_paths():
    """Every path that differs from HEAD, including an untracked file.

    `--porcelain` covers the staged change, the unstaged change, and the untracked
    file in one call. An untracked file counts: a new prompt file changes the run
    and would not appear in the commit.
    """
    status = _git("status", "--porcelain", "--untracked-files=all", strip=False)
    if not status:
        return []
    paths = []
    for line in status.splitlines():
        if not line.strip():
            continue
        # Each line is two status characters, a space, then the path. A rename
        # reads `R  old -> new`, and the new name is the one that matters.
        path = line[3:]
        if line[:1] == "R" and " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def describe():
    """Everything a result should record about the code that produced it."""
    if not is_repo():
        return None
    head = _git("rev-parse", "HEAD")
    if not head:
        return None  # a repository with no commit yet
    return {
        "commit": head,
        "short": head[:8],
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "committed": _git("log", "-1", "--format=%cI"),
        "subject": _git("log", "-1", "--format=%s"),
    }


def require_clean_tree():
    """Return the provenance, or raise DirtyTree with the reason and the fix.

    THIS REFUSAL IS THE POINT. Do not soften it into a warning, and do not add a
    flag that skips it. A result that a commit does not identify cannot be compared
    with another result, and a comparison between two such results is not evidence.
    """
    if not is_repo():
        raise DirtyTree(
            "refusing to run: this directory is not a git repository.\n"
            f"  {ROOT}\n\n"
            "An eval result is named after the commit that produced it. Without a\n"
            "repository there is nothing to name it after, and two runs cannot be\n"
            "compared. Start tracking the inputs:\n\n"
            "    git init\n"
            "    git add -A\n"
            "    git commit -m 'initial commit'"
        )

    head = _git("rev-parse", "HEAD")
    if not head:
        raise DirtyTree(
            "refusing to run: this repository has no commit yet.\n\n"
            "An eval result is named after the commit that produced it. Make the\n"
            "first commit, then run the eval:\n\n"
            "    git add -A\n"
            "    git commit -m 'initial commit'"
        )

    paths = dirty_paths()
    if paths:
        shown = "\n".join(f"    {p}" for p in paths[:20])
        more = f"\n    ... and {len(paths) - 20} more" if len(paths) > 20 else ""
        raise DirtyTree(
            "refusing to run: the working tree is dirty.\n\n"
            f"{shown}{more}\n\n"
            "An eval result is named after the commit that produced it. These\n"
            "changes would change the result while the commit stayed the same, so\n"
            "the name would be wrong and two runs would not compare. Commit them,\n"
            "or stash them:\n\n"
            "    git add -A && git commit -m '...'\n"
            "    git stash"
        )

    return describe()


RESULTS_DIR = os.path.join(ROOT, "evals", "results")


def find_results(directory=RESULTS_DIR):
    """Every result file, oldest first.

    The name starts with the date, so a plain sort orders them by run. Two results
    from one day sort by commit, which is arbitrary but stable.
    """
    if not os.path.isdir(directory):
        return []
    names = [
        n for n in os.listdir(directory) if n.startswith("eval-") and n.endswith(".json")
    ]
    return [os.path.join(directory, n) for n in sorted(names)]


def resolve(path=None, directory=RESULTS_DIR):
    """Pick the result to read: the one named, or the newest.

    There is no fallback to an older location. An earlier version of this eval
    asked each arm to WRITE a document rather than rewrite a committed one, and
    every result it produced measured nothing. Reading one by accident would be
    worse than finding nothing at all.
    """
    if path:
        return path
    found = find_results(directory)
    return found[-1] if found else None


def describe_result(data, path):
    """One line naming the result, for the top of a report.

    THE MODEL IS PART OF WHAT PRODUCED THIS RESULT, same as the commit. A
    result that does not say which model ran cannot be compared with another
    one — the failure this whole module exists to catch, applied to the model
    instead of the code. `models` is absent on a result written before this
    was tracked, and that must not be an error: older results still name a
    commit, which is what the "no provenance recorded" branch below guards.
    """
    git = data.get("git") or {}
    models = data.get("models") or {}
    model_bit = ""
    if models.get("generation"):
        model_bit = f"  gen {models['generation']}"
        if models.get("judging"):
            model_bit += f", judge {models['judging']}"
    if git.get("short"):
        return (
            f"{os.path.basename(path)}  commit {git['short']} on "
            f"{git.get('branch')}{model_bit}"
        )
    return f"{os.path.basename(path)}  (no provenance recorded){model_bit}"


def self_test():
    # The gate must refuse for each distinct reason, and say which one applies.
    import unittest.mock as mock

    with mock.patch(f"{__name__}.is_repo", return_value=False):
        try:
            require_clean_tree()
            raise AssertionError("a missing repository must refuse")
        except DirtyTree as exc:
            assert "not a git repository" in str(exc), exc
            assert "git init" in str(exc), exc

    with mock.patch(f"{__name__}.is_repo", return_value=True), mock.patch(
        f"{__name__}._git", return_value=""
    ):
        try:
            require_clean_tree()
            raise AssertionError("a repository with no commit must refuse")
        except DirtyTree as exc:
            assert "no commit yet" in str(exc), exc

    def fake_git(*args):
        if args[0] == "rev-parse" and args[1] == "HEAD":
            return "a" * 40
        return ""

    with mock.patch(f"{__name__}.is_repo", return_value=True), mock.patch(
        f"{__name__}._git", side_effect=fake_git
    ), mock.patch(f"{__name__}.dirty_paths", return_value=["skill/SKILL.md"]):
        try:
            require_clean_tree()
            raise AssertionError("a dirty tree must refuse")
        except DirtyTree as exc:
            assert "dirty" in str(exc), exc
            # The refusal must name the offending path. A refusal with no
            # detail leaves the reader with nothing to fix.
            assert "skill/SKILL.md" in str(exc), exc

    # A long list must not flood the terminal, and must say what it held back.
    with mock.patch(f"{__name__}.is_repo", return_value=True), mock.patch(
        f"{__name__}._git", side_effect=fake_git
    ), mock.patch(f"{__name__}.dirty_paths", return_value=[f"f{i}" for i in range(25)]):
        try:
            require_clean_tree()
            raise AssertionError("must refuse")
        except DirtyTree as exc:
            assert "and 5 more" in str(exc), exc

    # A clean tree returns the provenance and raises nothing.
    with mock.patch(f"{__name__}.is_repo", return_value=True), mock.patch(
        f"{__name__}._git", side_effect=fake_git
    ), mock.patch(f"{__name__}.dirty_paths", return_value=[]):
        got = require_clean_tree()
        assert got["commit"] == "a" * 40, got
        assert got["short"] == "aaaaaaaa", got

    # PARSE THE REAL PORCELAIN FORMAT.
    #
    # The first column is a space when a change is unstaged, so stripping the
    # output of `git status` eats the leading space of the first line and cuts one
    # character off the first path. Mocking `dirty_paths` hides this, so these
    # cases feed the exact bytes git produces.
    porcelain = (
        " M skill/SKILL.md\n"
        "M  spec/METHOD.md\n"
        "?? evals/newfile.json\n"
        "R  README.md -> READYOU.md\n"
        "MM evals/pste_lint.py\n"
    )
    with mock.patch(f"{__name__}._git", return_value=porcelain):
        got = dirty_paths()
    assert got == [
        "skill/SKILL.md",
        "spec/METHOD.md",
        "evals/newfile.json",
        "READYOU.md",
        "evals/pste_lint.py",
    ], got

    # `status` must be read without stripping. This asserts the call, because the
    # fault is invisible in the result of any single well-formed line.
    with mock.patch(f"{__name__}._git") as spy:
        spy.return_value = ""
        dirty_paths()
        assert spy.call_args.kwargs.get("strip") is False, spy.call_args

    # Results sort oldest first, and `resolve` takes the newest.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        assert find_results(tmp) == []
        assert resolve(None, tmp) is None
        for name in (
            "eval-2026-08-01-aaaaaaaa.json",
            "eval-2026-08-03-cccccccc.json",
            "eval-2026-08-02-bbbbbbbb.json",
            "notes.txt",
        ):
            open(os.path.join(tmp, name), "w").close()
        found = find_results(tmp)
        assert len(found) == 3, found
        assert found[0].endswith("2026-08-01-aaaaaaaa.json"), found
        assert found[-1].endswith("2026-08-03-cccccccc.json"), found
        assert resolve(None, tmp).endswith("2026-08-03-cccccccc.json")
        assert resolve("/x/y.json", tmp) == "/x/y.json"

    line = describe_result({"git": {"short": "abc12345", "branch": "main"}}, "/d/e.json")
    assert "abc12345" in line and "e.json" in line, line
    assert "no provenance" in describe_result({}, "/d/e.json")

    # THE MODEL MUST APPEAR BESIDE THE COMMIT. A result that does not say
    # which model ran cannot be compared with another one.
    with_model = describe_result(
        {
            "git": {"short": "abc12345", "branch": "main"},
            "models": {"generation": "claude-sonnet-5", "judging": "claude-opus-5"},
        },
        "/d/e.json",
    )
    assert "claude-sonnet-5" in with_model, with_model
    assert "claude-opus-5" in with_model, with_model

    # An older result with no `models` key must not error, and must not claim
    # a model it never recorded.
    no_model = describe_result({"git": {"short": "abc12345", "branch": "main"}}, "/d/e.json")
    assert "gen " not in no_model, no_model

    print("provenance self-test: all checks passed")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    try:
        info = require_clean_tree()
    except DirtyTree as exc:
        print(exc, file=sys.stderr)
        return 1
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
