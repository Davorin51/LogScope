# Validation record — 2026-10-29

Environment: Linux x86_64, CPython 3.12.14, PyYAML 6.0.3, pytest 9.1.1,
Ruff 0.17.3 and mypy 1.20.2. All example inputs are synthetic.

| Executed check | Actual outcome |
| --- | --- |
| `pytest --cov=logscope --cov-report=term-missing` | 115 passed in 0.88 s |
| Coverage from that run | 98% statements; subprocess entry-point execution is not included in the parent coverage process |
| `ruff check .` | Passed |
| `mypy` | Passed, 9 source files in strict mode |
| `python -m build` | Built sdist and universal Python wheel |
| Real CLI demo over `examples` with rules | 14 selected events, 6 errors, 1 incident, 1 malformed line; HTML and JSON written |

Test evidence includes a simple independent sliding-window oracle over generated
timelines, inclusive boundaries, duplicate timestamps, globally unsorted sources,
timezone offsets, invalid encoding, long-line draining, escaped HTML content,
input preservation, failed output replacement and real CLI subprocesses.

## Synthetic performance sample

Command: `python scripts/benchmark.py --events 100000`.
One measurement on this runner, with tracemalloc enabled and input generation
excluded from the timed interval:

| Metric | Observed |
| --- | --- |
| Selected events | 100,000 |
| Wall time | 13.069231696 seconds |
| Process CPU time | 12.832388769 seconds |
| Peak traced Python allocations | 81,952 bytes |

The allocation metric excludes SQLite/native allocations, OS file cache and
process RSS. It must not be advertised as total memory consumption. Tracing
changes runtime overhead. This is one synthetic sample, not a throughput SLA,
capacity limit, cross-machine comparison or Windows benchmark. The script is
included so future changes can be evaluated under the same conditions.

The GitHub Actions definition covers Windows/Linux and Python 3.12/3.13.
Hosted results, when available, must be inspected separately from this local run.

A clean virtual environment also installed the built wheel with its declared
runtime dependency and executed the real demo CLI from outside the source tree,
producing both HTML and JSON with the expected counts. This verifies that the
HTML template is included and usable in the installed wheel.

Visual browser inspection of the local HTML was not completed: the cloud browser
rejected the file URL protocol. Automated HTML rendering/escaping tests and actual
report generation passed; no claim of a completed browser-layout review is made.
