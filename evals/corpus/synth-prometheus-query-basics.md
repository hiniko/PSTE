---
model: claude-sonnet-5
generated_by: 2.1.220 (Claude Code)
generated_on: 2026-09-11
environment: container, evals/Dockerfile.clean
isolation: |
  No CLAUDE.md, no plugin, no hook, no memory, and no configured skill.
  The container holds none of them, so none can reach the model.
constrained: false
grounding_url: https://raw.githubusercontent.com/prometheus/prometheus/main/docs/querying/basics.md
grounding_licence: Apache-2.0
question: |
  Write a documentation page for the basics of its query language, PromQL in Prometheus. A copy of an upstream page for this topic is mounted at /grounding/synth-prometheus-query-basics.md. Use it only to check facts and stay accurate. Do not paraphrase it, follow its structure, or reuse its wording: write your own independent documentation page, organised and expressed the way you normally would. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository.
---
# PromQL Basics

PromQL (Prometheus Query Language) is the language Prometheus uses to read data back out of its time series database. You use it everywhere: in the expression browser, in Grafana panels, in alerting rules, and in recording rules. This page covers the core concepts you need before writing your own queries — what a query returns, how time series are selected and filtered, and a handful of syntax details that trip people up.

## Instant queries vs. range queries

Every PromQL expression can be evaluated in two ways:

- **Instant query** — evaluated at a single point in time, producing one value per matching series. This is what powers the "Table" view in the Prometheus UI.
- **Range query** — the same expression evaluated repeatedly at fixed steps between a start and end time, producing a series of points you can plot. This powers the "Graph" view.

The language itself doesn't change between the two modes — a range query is just an instant query run over and over at different timestamps. Anything other than the built-in UI (dashboards, scripts, custom tooling) typically fetches these results over Prometheus's HTTP API.

## What a query evaluates to

An expression (or any sub-expression) always produces one of four types:

| Type | What it looks like |
|---|---|
| **Instant vector** | A set of series, each with exactly one sample, all at the same timestamp |
| **Range vector** | A set of series, each with a window of samples over time |
| **Scalar** | A single floating-point number, no labels attached |
| **String** | A string value (rarely used in practice today) |

Not every context accepts every type. Instant queries will accept any of the four as a final result; range queries only accept scalars and instant vectors as the top-level result — you can't graph a range vector or a string directly.

Samples themselves come in two flavors: ordinary **float** samples (a plain number) and **native histogram** samples (a full histogram with count, sum, and bucket data bundled into one sample). A single vector can contain a mix of both kinds. Native histograms know whether they're a counter or a gauge, so Prometheus can warn you if you apply the wrong kind of function to them (e.g., `rate()` on a gauge histogram). Ordinary float samples don't carry that flavor information — Prometheus can't stop you from calling `rate()` on a float gauge, even though the result will be meaningless. This is why counter metrics conventionally end in `_total`: it's a naming convention to help humans (and dashboards) avoid that mistake, not something PromQL enforces.

One more terminology note: a "classic histogram" — the `_bucket`/`_count`/`_sum` trio of plain metrics — is just three ordinary float series to PromQL. There's no such thing as a "classic histogram sample"; only native histograms produce histogram-typed samples.

## Selecting time series

### Instant vector selectors

The simplest possible query is just a metric name:

```
http_requests_total
```

This returns one sample per series carrying that metric name — specifically, the most recent sample at or before the query's evaluation time (subject to the staleness rules described below).

To narrow that down, add label matchers in curly braces after the metric name. A query for `http_requests_total` scoped to a `job` label of `prometheus` and a `group` label of `canary` returns only series matching both.

Four matcher operators are available:

| Operator | Meaning |
|---|---|
| `=` | label equals this string |
| `!=` | label does not equal this string |
| `=~` | label matches this regex |
| `!~` | label does not match this regex |

Regex matches in PromQL are always fully anchored — a `=~` match against `foo` behaves as an anchored `^foo$`, not as a substring search. The regex flavor is RE2.

A subtlety worth knowing: a matcher against an empty string on a label matches series that have that label explicitly set to empty *and* series that don't have the label at all. You can also repeat a matcher on the same label name — all of them have to pass for the series to be selected (e.g., excluding one specific value while regex-matching a broader pattern on the same label).

Because a selector made up of only regex matchers could otherwise match every series in the database, Prometheus requires that a selector contain a metric name or at least one matcher that can't match an empty value. A selector with nothing but a wildcard-style regex on a single label is rejected; requiring at least one non-empty character in that regex makes it valid.

Under the hood, the metric name is really just a label called `__name__`, so writing the metric name bare is equivalent to matching `__name__` directly — and you can use non-`=` operators against it too, which lets you match every metric whose name starts with a given prefix. One quirk from this: a few words (`bool`, `on`, `ignoring`, `group_left`, `group_right`) are reserved as operator keywords, so you can't use them bare as a metric name; matching them via `__name__` explicitly is the workaround.

### Range vector selectors

Append a duration in square brackets to pull a window of history instead of a single point:

```
http_requests_total{job="prometheus"}[5m]
```

This is a **range vector**: for every matching series you get all the samples from the last 5 minutes, not just the latest one. The window is left-open, right-closed — a sample sitting exactly on the start boundary is excluded, one sitting exactly on the end boundary is included. Range vectors are mostly consumed by functions like `rate()`, `increase()`, and `avg_over_time()` rather than displayed directly.

## Durations

Time durations are written as a number followed by a unit:

| Unit | Meaning |
|---|---|
| `ms` | milliseconds |
| `s` | seconds |
| `m` | minutes |
| `h` | hours |
| `d` | days (24h, DST ignored) |
| `w` | weeks (7d) |
| `y` | years (365d, leap days ignored) |

Units can be chained as long as they go from largest to smallest and each appears once: `1h30m`, `12h34m56s`. Under the hood a duration is really just a float literal in seconds — `1s` is `1`, `1ms` is `0.001` — but you can only suffix a *decimal integer*, so `1.5h` and hex numbers with unit suffixes aren't valid.

You can also build a duration with arithmetic, anywhere a duration is expected (range vector brackets, `offset`): multiplying `5m` by `2` gives a 10-minute window; dividing `1h` by `2` gives a 30-minute offset. The usual `+ - * / % ^` operators all work with normal precedence. Note that `offset` needs the expression wrapped in parentheses, or only the first term gets used. There are also a few helper functions usable inside duration expressions: `step()` (the range-query step width, `0s` for instant queries), `range()` (end minus start of a range query, `0s` for instant queries), and `min_of()`/`max_of()` for clamping — e.g. `max_of(step(), 5s)` never lets the duration drop below 5 seconds. Duration expressions aren't allowed inside the `@` modifier, though.

## Shifting time: `offset` and `@`

**`offset`** shifts where a selector looks, relative to the query's evaluation time. Appending `offset 5m` to a selector returns what the value was 5 minutes ago. It works on range vectors too, and combines naturally with functions — you can ask for this week's 5-minute rate as it looked a week ago by combining a `[5m]` range with `offset 1w`. A negative offset looks forward instead of back, which is occasionally useful for comparisons against "the future" relative to some earlier evaluation point.

**`@`** pins a selector to an absolute Unix timestamp instead of a relative offset, e.g. `http_requests_total @ 1609746000`. `start()` and `end()` are handy special values here — for a range query they resolve to the query's start/end and stay fixed across every step; for an instant query both just resolve to the evaluation time.

The one rule to remember for both modifiers: they bind to the selector immediately to their left, not to the whole enclosing expression. Wrapping the bare selector (with its `offset` or `@` attached) inside an aggregation like `sum(...)` is correct; putting the modifier after the closing parenthesis of `sum(...)` is a syntax error.

`offset` and `@` can be combined on the same selector, and order doesn't matter — the offset is always applied relative to the `@` time.

## Subqueries

A subquery lets you run what is effectively an instant-query expression repeatedly over a range, turning it into a range vector — useful when you want to apply a range-vector function (like `max_over_time`) on top of something that's already a rate or other computed expression, e.g. wrapping `rate(metric[5m])` in a further `[30m:1m]` window to get the max of that rate over the last 30 minutes at 1-minute resolution. The resolution part is optional and defaults to the global evaluation interval if omitted.

## Everything else, briefly

- **Operators** (`+`, `and`, `on`, `group_left`, etc.) and **functions** (`rate`, `sum`, `histogram_quantile`, and dozens more) are where most of PromQL's actual power lives — worth a dedicated read once you're comfortable with selectors.
- **Comments** start with `#` and run to the end of the line.
- **String literals** use single quotes, double quotes, or backticks. Single/double-quoted strings follow Go's escaping rules (backslash escapes plus octal/hex escapes); backtick strings are raw — no escape processing, and newlines inside them are preserved as-is.
- **Numeric literals** accept integers, decimals, scientific notation, hex, `Inf`/`NaN`, and underscores as digit separators for readability (e.g. `1_000_000`).

## Two gotchas worth knowing up front

**Staleness.** Because a query samples at fixed timestamps that don't necessarily line up with when data was actually scraped, Prometheus has to decide what value to report at each timestamp — it uses the newest sample that's less than the *lookback period* old (5 minutes by default, tunable via the `--query.lookback-delta` flag or a per-query `lookback_delta` parameter). If a target stops being scraped or disappears, its series gets marked stale, and once a query's evaluation timestamp is past that staleness point, the series simply stops appearing in results — which is why a graph line will visibly end rather than flatline forever.

**Performance.** A bare metric name selector can silently expand into thousands of series if the metric is high-cardinality, and any aggregation over that many series costs real work on the server even if the final output is a single number — much like summing a huge column in a SQL database isn't free just because the result is one row. When you're exploring an unfamiliar metric, check it in the tabular view first, narrow it down with label matchers or aggregation until the result set is reasonably sized, and only then switch to graphing it. If a query is inherently expensive even after narrowing, that's what recording rules are for — pre-compute it once, query the cheap result repeatedly.

---

A couple of notes on the process: I wasn't able to save this as a file in this session — the file-write tool wasn't enabled, and shell redirection to files was blocked by sandbox policy (it also specifically flags `{...}`-style curly-brace label matchers as suspicious shell syntax, which is why the code examples above are described in prose rather than shown as literal `{job="..."}` snippets in a couple of spots). If you'd like this as an actual `.md` file, you can copy the text above, or let me know if there's a different way you'd like me to attempt saving it.
