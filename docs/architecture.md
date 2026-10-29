# Architecture

The CLI coordinates small independent modules:

1. `inputs` resolves and deduplicates paths and reads bounded byte lines.
2. `parsing` converts a supported line into an immutable, UTC-aware `Event`.
3. `analysis` filters events and spools selected records into a temporary SQLite database.
4. `rules` evaluates selected events in global chronological order.
5. `reporting` converts the result to escaped HTML or versioned JSON and writes output.

`models` contains shared records, filters, sample limits and the result schema.
The HTML template is packaged as a resource, so installed wheels render the same
report as editable development checkouts. Python rules and the presentation layer
are independent; there is no browser-driven application state.

## Ordering and resource decisions

A one-pass deque over input-file order gives incorrect threshold results for
unsorted logs or overlapping files. Instead, selected events are inserted into
SQLite in batches of 1,000, indexed by UTC timestamp and insertion ID, and read
in chronological order. Ties follow sorted resolved file paths and source line
order. Original files remain read-only. Connections are explicitly closed before
temporary-directory cleanup, including on errors, for Windows compatibility.

The input is not retained in a Python list. SQLite uses a 4 MiB page-cache target
and file-backed temporary storage; its native memory and sort behavior are not a
hard process-memory ceiling. The temporary disk must hold the selected records
and indexes. Each rule retains at most `threshold` event references. Report
samples and displayed messages are capped; aggregate counts cover all events.
The resolved file catalog itself grows with the number of distinct input paths.

## Error model

Blank lines are counted separately. Invalid UTF-8, unsupported lines, invalid
JSON and oversized lines become malformed-line diagnostics; their raw content
is not copied into diagnostics. An oversized record is drained in bounded chunks
and counted once, preserving the next source line number. Missing/unreadable
inputs, SQLite failures, invalid rules and output failures are actionable errors.

CLI output is ASCII-escaped when showing untrusted message/component content.
HTML text is escaped, includes a restrictive CSP and has no executable scripts,
external styles or remote fonts. Rules use a safe YAML loader and literal string
matching, never eval or caller-supplied regex. Rule configuration is capped before
parsing and structurally validated. This is not a sandbox for hostile multi-user
uploads; it is a local analysis tool.

Each report is written to a temporary sibling, flushed, fsynced and replaced
atomically. Input and rules-file collisions are rejected. HTML+JSON together are
not a cross-file transaction: if the second target fails, the first may already
have been replaced. Directory fsync/crash-durable multi-file commits are not
claimed. Existing report targets are intentionally replaced when explicitly selected.

## Extension boundaries

Add parser adapters that return `Event`; do not fork rule logic per input type.
A future run-comparison module needs complete issue data or an explicit partial
comparison contract, not just the top-20 display samples. Live following needs
file-rotation, partial-record and timestamp-watermark semantics before it can
reuse chronological rule evaluation safely. A UI can call the analysis service
on a worker and display the same report model.
