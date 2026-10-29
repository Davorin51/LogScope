# Input and output limits

| Item | Default / contract |
| --- | --- |
| Line length | 262,144 bytes including newline; CLI configurable up to 1,048,576 |
| Diagnostic samples | 20; all malformed lines still counted |
| Frequent error groups | Top 20 exact parsed-message/level/component groups |
| Error context samples | First 10 errors chronologically, 2 selected parsed events before/after in the same file |
| Rule incident samples | 100; aggregate incident count remains exact |
| Timeline | First 1,000 UTC minute buckets; total bucket count exposed |
| Displayed message | 2,000 characters; truncation flag exposed |
| Rule configuration | 256 KiB, 100 rules, 10,000 retained event references per rule maximum |

Python callers can supply a `Limits` object to adjust sample counts. Reports
include displayed and total counts so truncation is visible. Error grouping uses
complete messages before display truncation. Malformed lines do not become
context events. Context remains within the selected events and follows original
source line order, which can differ from timestamp order in an unsorted file.

Use full ISO calendar dates and times. Missing timezone offsets are interpreted
as UTC. No timezone guessing, multiline trace assembly, automatic field aliases
or arbitrary log-format inference is provided. The `auto` parser chooses JSONL
for a line beginning with `{`, otherwise the documented text syntax.

Directory discovery reads .log, .txt, .jsonl and .ndjson, case-insensitively.
Explicit file paths accept any extension. Recursive directory traversal is opt-in.
Resolved paths are deduplicated. Symlinked files are resolved to their target;
analysis should be run only on inputs the user intends to read.

Use completed/stable log files for reproducible analysis. Concurrent writers,
file rotation and interrupted process recovery are not supported by this batch
version. There is no automatic redaction: source paths and selected messages
are included in requested reports. Do not publish real private logs as examples.
