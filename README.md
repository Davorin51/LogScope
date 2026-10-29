# LogScope

**Local log analysis that turns long test runs into inspectable evidence.**

Python 3.12+ · MIT original code · Windows and Linux · CLI first

Analyze completed UTF-8 text and JSONL logs, filter events, detect repeated
problems with explicit rules, and produce a self-contained HTML report or
machine-readable JSON. No API key, external service or network access is required.

This is an implemented analysis tool. Live tailing, automatic root-cause diagnosis
and comparison between runs are not claimed by this first version.

## Quick start

```shell
python -m venv .venv
# Activate the environment, then:
python -m pip install -e ".[dev]"
logscope analyze examples --rules examples/rules.yaml --json report.json --html report.html
```

Open `report.html` in your browser. The included synthetic example should produce
14 selected events, 6 errors, 1 rule incident and 1 malformed line. The gateway
incident groups five timeouts within one minute. Sources are merged in UTC
chronological order, even when individual files are unsorted.

```shell
logscope analyze ./logs --recursive --level ERROR --since 2026-10-29T10:00:00Z
logscope analyze server.log worker.jsonl --component gateway --contains timeout
logscope analyze ./logs --rules examples/rules.yaml --fail-on alert --json report.json
```

Windows PowerShell can call the environment directly:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\logscope analyze examples --rules examples/rules.yaml --html report.html
```

## Implemented features

- Text and JSONL parsers with strict full-date timestamps and UTC normalization.
- Multiple files or directories, optional recursion, deterministic ordering and path deduplication.
- Inclusive time filters, severity/component filters and literal message search.
- Exact-message error counts, per-minute timeline and surrounding parsed events.
- Validated YAML/JSON rules with bounded sliding windows and grouped incidents.
- Malformed/invalid-UTF-8/oversized line diagnostics and explicit sample limits.
- Temporary SQLite spooling, so input files are not loaded into a Python list.
- Escaped offline HTML, versioned JSON, and atomic replacement of each report file.
- Optional CLI quality gates for automation/CI use.

### Accepted input

```text
2026-10-29T10:15:03Z ERROR [gateway] Connection timeout
2026-10-29 10:15:04 INFO Retrying connection
```

```json
{"timestamp":"2026-10-29T11:15:03+01:00","level":"ERROR","component":"gateway","message":"Connection timeout"}
```

JSON requires string `timestamp`, `level` and `message`; `component` is optional.
Levels are TRACE, DEBUG, INFO, WARNING, ERROR and CRITICAL. WARN and FATAL are
normalized aliases. Missing timezone offsets mean UTC, never the machine's
local timezone. Time-only records such as `10:15:03 ERROR ...` are diagnosed
rather than assigned a guessed date. Multiline stack traces are not assembled
in this version; unrecognized continuation lines appear in diagnostics.

### Rules

```yaml
version: 1
rules:
  - id: timeout_burst
    description: Five gateway timeouts within one minute
    contains: timeout
    levels: [ERROR, CRITICAL]
    component: gateway
    threshold: 5
    window_seconds: 60
```

Matching is literal and case-insensitive; there is no executable rule language
or arbitrary regular expression. Rules apply to the selected events across all
input files. Use `component` to scope a rule. A window includes its boundary.
See [rule semantics](docs/rules.md) for how continuing incidents are grouped.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Analysis completed; errors in logs are data, not a tool failure |
| 1 | Input, configuration, database or report-writing failure |
| 2 | CLI usage error |
| 3 | Requested `--fail-on error`, `alert` or `malformed` gate failed; requested reports are still written |
| 130 | Interrupted by the user |

## Development

```shell
pytest --cov=logscope --cov-report=term-missing
ruff check .
ruff format --check .
mypy
python -m build
```

Tests cover parsers, synthetic logs, out-of-order events, window boundaries,
filters, report escaping, data preservation, quality gates and CLI execution.
See [architecture](docs/architecture.md), [validation](docs/validation.md),
[limits](docs/limits.md), [roadmap](docs/roadmap.md) and [contributing](CONTRIBUTING.md).

LogScope reports observed events and explicit rule matches. Nearby messages
can aid investigation; they do not prove that a timeout was recovered or identify
its root cause. Source logs and reports may contain sensitive data; analysis
remains local, and users choose whether to share the resulting reports.
