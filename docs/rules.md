# Rule semantics

A version-1 rule has an `id`, non-empty literal `contains`, integer `threshold`
and `window_seconds`. `levels`, exact `component` and `description` are optional.
IDs must be unique. Unknown fields and unsupported levels are errors. Thresholds
range from 1 to 10,000; windows are finite, greater than zero and at most 86,400
seconds. A document holds 1-100 rules and is at most 256 KiB.

A match requires the message substring (Unicode case-insensitive), the selected
levels if specified, and the component if specified. No regex or executable
expressions are accepted. All matching selected events count across sources;
identical lines in different files are separate observations, not deduplicated
events. Only repeated input *paths* are deduplicated.

## Inclusive sliding window and episodes

At matching time `t`, a rule triggers when at least `threshold` matches exist in
`[t - window_seconds, t]`. The engine only needs the most recent `threshold`
matching events to test this condition. It does not retain the complete window.

An incident starts with the first match in the initial triggering window. Its
reported `start` may precede the moment the threshold was first reached.
Subsequent matching events extend the same episode while the threshold condition
continues to hold at those observations. A gap exceeding the window or a matching
event that no longer meets the condition closes the episode. End of input also
closes an active episode. `end` is the last observed matching event, not an
inferred recovery time. `match_count` covers the initial threshold matches and
subsequent matches belonging to that episode; it is not a peak-window count.

For threshold 3 and a 60-second window, matches at 0, 30, 60 and 70 seconds form
one incident with 4 matches. A match at 60.000001 instead of 60 does not make
the first three qualify. For threshold 1, matches at 0 and 5 form one episode,
and a further match at 100 starts another when the window is 10 seconds.

Filters run before rule detection. Restricting levels/components/time can change
which incidents exist. Malformed lines are counted before event filtering because
they have no reliable timestamp/level to filter.

Default report storage retains at most 100 completed incident samples; the total
count remains exact. Samples are retained in completion order, then sorted by
start time for presentation. Longer episodes can complete later than short ones.
