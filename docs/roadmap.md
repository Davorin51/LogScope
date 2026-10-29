# Roadmap and useful next development tasks

## 0.1 — implemented foundation

- Batch text/JSONL analysis, UTC ordering, filters, exact-message statistics.
- Validated rules, grouped sliding-window incidents and contextual samples.
- Self-contained HTML/JSON reports, CLI quality gates and pytest coverage.
- Windows/Linux CI definition and installable package.

## 0.2 — richer event ingestion

- Multiline Python traceback assembly with bounded continuation length.
- Configurable field mappings for structured logs and additional parser plugins.
- Explicit local-timezone handling and DST ambiguity diagnostics.
- Tests for interrupted and incomplete records across adapters.

## 0.3 — compare executions

- Compare successful and failed runs with complete issue counts.
- Identify new/disappeared messages, count deltas and duration differences.
- User-configured normalization with examples showing potential over-grouping.
- Golden comparison fixtures and regression tests.

## 0.4 — live operation

- Follow active files, retain incomplete lines and handle rotation/truncation.
- Define lateness/watermark behavior for cross-source event order.
- Checkpoint/resume and cancellation with deterministic clock-based tests.

## 0.5 — application layer

- Optional desktop interface or localhost API using the existing analysis service.
- Search, rule editing and progress/cancellation; validation before saving changes.
- Large-run benchmarks across documented datasets and OS environments.

These are future milestones, not switches to nonfunctional placeholder features.
