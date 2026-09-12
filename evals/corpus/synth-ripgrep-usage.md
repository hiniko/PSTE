---
model: claude-sonnet-5
generated_by: 2.1.220 (Claude Code)
generated_on: 2026-09-11
environment: container, evals/Dockerfile.clean
isolation: |
  No CLAUDE.md, no plugin, no hook, no memory, and no configured skill.
  The container holds none of them, so none can reach the model.
constrained: false
grounding_url: https://raw.githubusercontent.com/BurntSushi/ripgrep/master/GUIDE.md
grounding_licence: MIT
question: |
  Write a documentation page for everyday command line usage and pattern matching in ripgrep. A copy of an upstream page for this topic is mounted at /grounding/synth-ripgrep-usage.md. Use it only to check facts and stay accurate. Do not paraphrase it, follow its structure, or reuse its wording: write your own independent documentation page, organised and expressed the way you normally would. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository.
---
# ripgrep for everyday use

ripgrep (`rg`) is a line-oriented search tool: point it at a pattern and it walks through your files, printing every line that matches. What makes it pleasant for daily use is less the raw speed and more the defaults — it already knows to skip your `.git` directory, your `node_modules`, your build output, and anything else your `.gitignore` already tells it to ignore. This page walks through the parts of ripgrep you'll actually reach for day to day: running a search, writing patterns, controlling what gets searched, and shaping the output.

## Your first search

The simplest invocation is a pattern and a file:

```
$ rg TODO app.py
42:# TODO: handle the empty-cart case
118:# TODO: this retries forever, add a max
```

Each matching line is printed with its line number. If nothing matches, `rg` prints nothing and exits with a non-zero status — handy in scripts.

Drop the filename and `rg` searches the current directory tree instead:

```
$ rg TODO
app.py
42:# TODO: handle the empty-cart case
118:# TODO: this retries forever, add a max

tests/test_cart.py
9:# TODO: this test is flaky, investigate
```

`rg pattern` is really shorthand for `rg pattern .` — recursive search is the default mode, not a special flag you have to remember.

## Patterns: literal by default, regex when you want it

Whatever you type after `rg` is treated as a regular expression unless you tell it otherwise. A plain word like `TODO` happens to also be a valid regex that matches itself, which is why the example above "just worked." Things get more interesting once you use regex metacharacters:

```
$ rg 'retr\w+' app.py
118:# TODO: this retries forever, add a max
```

`\w` matches a "word" character (letters, digits, underscore), and `+` means "one or more of the previous thing." So `retr\w+` matches `retr` followed by at least one more word character — it'll match `retries` and `retry` but not a bare `retr`. Swap `+` for `*` (zero or more) and a bare `retr` would match too, and `rg` would highlight only the `retr` prefix on lines where nothing follows it.

A few things worth knowing up front:

- Parentheses, brackets, dots, question marks, and other regex punctuation are special. If your pattern contains literal punctuation — say you're searching for `array[0]` — either escape it (`array\[0\]`) or tell ripgrep not to interpret the pattern as regex at all with `-F`/`--fixed-strings`.
- ripgrep's regex engine is Unicode-aware by default: `\w` matches Unicode word characters, and `.` matches any Unicode codepoint, not just any byte. That's usually what you want for source code and prose alike.
- Full regex syntax is out of scope here, but everything ripgrep supports is documented at https://docs.rs/regex/*/regex/#syntax.

A handful of pattern-matching flags come up constantly:

- `-i`/`--ignore-case` — case-insensitive matching.
- `-S`/`--smart-case` — case-insensitive *unless* your pattern has an uppercase letter in it, in which case it becomes case-sensitive. This is the one people put in a shell alias and forget about, because it does the right thing almost all the time.
- `-w`/`--word-regexp` — only match whole words, so `rg -w cat` won't match inside `concatenate`.
- `-v`/`--invert-match` — print lines that *don't* match.
- `-F`/`--fixed-strings` — treat the pattern as literal text, not regex.

## Scoping a search to a directory or a few files

Pass a path (or several) after the pattern to limit where `rg` looks:

```
$ rg 'def handle_' src/
$ rg 'def handle_' src/ tests/
```

This is often simpler than piping through `grep -r` with a bunch of `find` gymnastics, since recursion and filtering are already built in.

## What ripgrep leaves out, by default

This is the part that surprises people coming from `grep -r`: ripgrep won't search everything under a directory. Four things are excluded automatically:

1. Anything matched by a `.gitignore` file — including your global gitignore, per-repo excludes in `.git/info/exclude`, and `.gitignore` files in parent directories of the same repo. `.ignore` files (tool-agnostic) and `.rgignore` files (ripgrep-specific) work the same way and take increasingly higher precedence when rules conflict.
2. Hidden files and directories (anything starting with `.`).
3. Binary files — anything containing a NUL byte.
4. Symlink targets — symlinks aren't followed.

Each of these can be switched off individually:

| Want to search... | Flag |
|---|---|
| Files listed in `.gitignore`/`.ignore` | `--no-ignore` |
| Hidden files and dotfiles | `--hidden` (`-.`) |
| Binary files as plain text | `--text` (`-a`) |
| Through symlinks | `--follow` (`-L`) |

If you just want to cast a wider net without remembering which flag does what, stack `-u`: one `-u` turns off gitignore filtering, `-uu` also picks up hidden files, and `-uuu` (equivalently `--unrestricted` three times) turns off binary detection too. It's a good first move when a search comes back suspiciously empty.

If a search behaves unexpectedly — no results when you're sure there should be some — `rg --debug` will tell you which ignore rule or filter is responsible.

Sometimes you want to *un-ignore* one specific thing without turning off ignore handling globally — say your `.gitignore` excludes `vendor/`, but you occasionally want to grep through it. Create a `.rgignore` (or `.ignore`) file next to the `.gitignore` with:

```
!vendor/
```

Since `.rgignore` and `.ignore` outrank `.gitignore`, the negation wins and `vendor/` becomes searchable again — without touching source control's own ignore rules.

## Filtering by glob

Beyond the automatic ignore-file handling, you can filter manually with `-g`/`--glob`:

```
$ rg import -g '*.py'
```

restricts the search to Python files. Quote the glob so your shell doesn't expand the `*` itself. Prefix a glob with `!` to exclude instead of include:

```
$ rg import -g '!*_test.py'
```

You can combine several `-g` flags, and like `.gitignore` rules, later globs take precedence over earlier ones when they conflict. One gotcha: as soon as you supply *any* non-negated glob, ripgrep requires a match against at least one glob — so `-g '!*.md' -g '*.md'` searches only Markdown files (the positive glob at the end wins), while `-g '*.md' -g '!*.md'` matches nothing at all (the exclusion, being last, wins outright).

## Filtering by file type

If you find yourself typing the same glob over and over, use `--type` (`-t`) instead:

```
$ rg TODO --type py
$ rg TODO -tpy
```

`-t` includes a type, `-T`/`--type-not` excludes one. Run `rg --type-list` to see what's built in and which extensions each name covers — there are presets for most common languages and formats already.

You're not limited to the built-ins. Define your own with `--type-add`:

```
$ rg --type-add 'web:*.{html,css,js}' -tweb title
```

This only applies for the current command, though — it's not saved anywhere. To make a custom type stick around, put it in a shell alias:

```
alias rg="rg --type-add 'web:*.{html,css,js}'"
```

or in ripgrep's config file (see below).

One more useful special case: `--type all` matches any file recognized by *any* known type (built-in or custom). Files with no extension that don't match any type's glob — like an extensionless shell script — won't be picked up by `--type all`, but *will* be picked up by `--type-not all`.

## Shaping the output

A handful of flags change what gets printed rather than what gets searched:

- `-c`/`--count` — print a count of matching lines per file instead of the lines themselves.
- `-l`/`--files-with-matches` — print just the filenames that contain a match, not the matching lines.
- `-o`/`--only-matching` — print only the matched text, not the whole line.
- `-C`/`--context N` — show `N` lines of context around each match (`-A` for after only, `-B` for before only).
- `-m`/`--max-count N` — stop after `N` matches per file.
- `--files` — don't search at all, just list the files ripgrep *would* search. Great for sanity-checking your glob/type filters before running the real search.

## Replacing matched text (in output only)

`-r`/`--replace` swaps the matched portion of text for something else in ripgrep's output:

```
$ rg fetchUser -r loadUser src/
```

This only changes what's printed to your terminal — ripgrep never edits files on disk, and there's no flag that makes it do so. By default only the matched substring is swapped; if you want to replace the entire line, write a pattern that matches the whole line (`^.*fetchUser.*$`), or combine `-o` with `-r` to get the same effect.

Replacements can reference capture groups from the pattern:

```
$ rg 'const (\w+) = require' -r 'import $1 from' src/
```

`$1` refers to the first parenthesized group (group `0` is always the whole match). Named groups work too, and read more clearly in longer patterns:

```
$ rg 'const (?P<name>\w+) = require' -r 'import $name from' src/
```

## Saving your preferences

If you keep typing the same flags, put them in a config file instead of an alias. Point ripgrep at one via the `RIPGREP_CONFIG_PATH` environment variable, then list one flag per line:

```
# ~/.ripgreprc
--smart-case
--hidden
--glob=!.git/*
```

Lines starting with `#` are comments; blank lines are fine. There's no shell quoting or escaping inside this file — each line becomes one literal argument, so a flag with a value either needs `=` (`--max-columns=150`) or its own line, never a space on the same line. Config-file flags are treated as if they came before your actual command-line flags, so anything you type on the command line overrides the config. Use `--no-config` if you ever need to bypass the config file entirely, and `--debug` if you're not sure which config file (if any) is being picked up.

## Quick reference

| Flag | Meaning |
|---|---|
| `-i`, `--ignore-case` | case-insensitive search |
| `-S`, `--smart-case` | case-insensitive unless pattern has uppercase |
| `-F`, `--fixed-strings` | treat pattern as literal text |
| `-w`, `--word-regexp` | match whole words only |
| `-v`, `--invert-match` | print non-matching lines |
| `-g`, `--glob` | include/exclude files by glob (`!` to exclude) |
| `-t`, `-T` | include/exclude files by type |
| `--type-list` | list known file types and their globs |
| `-c`, `--count` | count matches per file |
| `-l`, `--files-with-matches` | list files with at least one match |
| `-o`, `--only-matching` | print only the matched text |
| `-r`, `--replace` | substitute matched text in the output |
| `-C`, `-A`, `-B` | show surrounding context lines |
| `-m` | cap matches per file |
| `--hidden`, `--no-ignore`, `--text`, `--follow` | disable one automatic filter |
| `-u`, `-uu`, `-uuu` | progressively disable automatic filtering |
| `--files` | list files that would be searched, without searching |
| `--debug` | explain why a file was or wasn't searched |

---

Let me know if you'd like this saved to a specific file path — I don't have file-write access in this session, so I couldn't create it on disk myself.
