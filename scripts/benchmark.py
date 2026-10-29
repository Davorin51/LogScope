"""Reproducible synthetic analysis measurement, not a hardware-independent speed guarantee."""

import argparse
import json
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, process_time

from logscope.analysis import analyze
from logscope.rules import Rule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=100000)
    args = parser.parse_args()
    if not 1 <= args.events <= 10000000:
        parser.error("events must be in [1, 10000000]")
    with TemporaryDirectory(prefix="logscope-benchmark-") as temporary:
        path = Path(temporary) / "synthetic.log"
        start = datetime(2026, 1, 1, tzinfo=UTC)
        with path.open("w", encoding="utf-8") as stream:
            for index in range(args.events):
                timestamp = (start + timedelta(milliseconds=index * 100)).isoformat()
                level = "ERROR" if index % 10 == 0 else "INFO"
                stream.write(f"{timestamp} {level} [worker] timeout-{index % 100}\n")
        tracemalloc.start()
        wall_start = perf_counter()
        cpu_start = process_time()
        report = analyze([path], rules=(Rule("burst", "timeout", 5, 60),))
        elapsed = perf_counter() - wall_start
        cpu = process_time() - cpu_start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert report.selected_events == args.events
        print(
            json.dumps(
                {
                    "events": report.selected_events,
                    "wall_seconds": elapsed,
                    "process_cpu_seconds": cpu,
                    "peak_python_traced_bytes": peak,
                    "note": (
                        "Generation excluded; tracing enabled. "
                        "Python allocations only, not process RSS."
                    ),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
