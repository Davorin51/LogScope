"""Disk-spooled analysis: deterministic ordering without retaining the input in RAM."""

import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from logscope.inputs import discover_files, read_lines
from logscope.models import (
    Context,
    Diagnostic,
    Event,
    Filters,
    Finding,
    Issue,
    Limits,
    LogScopeError,
    Report,
    TimelineBucket,
    event_view,
)
from logscope.parsing import LogFormat, parse_line, parse_timestamp
from logscope.rules import Rule, RuleState


def _event(row: sqlite3.Row) -> Event:
    return Event(
        parse_timestamp(str(row["stamp"])),
        str(row["level"]),
        str(row["message"]),
        str(row["component"]),
        str(row["source"]),
        int(row["line"]),
    )


def _add_finding(report: Report, finding: Finding | None, limits: Limits) -> None:
    if finding is not None:
        report.total_findings += 1
        if len(report.findings) < limits.finding_samples:
            report.findings.append(finding)


def analyze(
    paths: Sequence[Path],
    *,
    format: LogFormat = "auto",
    rules: tuple[Rule, ...] = (),
    filters: Filters | None = None,
    limits: Limits | None = None,
    recursive: bool = False,
) -> Report:
    if format not in ("auto", "text", "jsonl"):
        raise ValueError("format must be auto, text or jsonl")
    filters = filters if filters is not None else Filters()
    limits = limits if limits is not None else Limits()
    files = discover_files(paths, recursive)
    report = Report(files=[str(p) for p in files])
    report.filters = {
        "since": filters.since.isoformat() if filters.since else None,
        "until": filters.until.isoformat() if filters.until else None,
        "levels": sorted(filters.levels),
        "components": sorted(filters.components),
        "contains": filters.contains,
    }
    report.rules = [{**asdict(rule), "levels": sorted(rule.levels)} for rule in rules]
    try:
        with TemporaryDirectory(prefix="logscope-") as temporary:
            with closing(sqlite3.connect(Path(temporary) / "events.sqlite3")) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA cache_size = -4096")
                db.execute("PRAGMA temp_store = FILE")
                db.execute("""CREATE TABLE events (
                    id INTEGER PRIMARY KEY, stamp TEXT, minute TEXT, level TEXT,
                    component TEXT, message TEXT, source TEXT, line INTEGER)""")
                for path in files:
                    for number, text, error in read_lines(path, limits.max_line_bytes):
                        report.lines += 1
                        if error is None and text is not None and not text.strip():
                            report.blank_lines += 1
                            continue
                        event = None
                        if error is None and text is not None:
                            try:
                                event = parse_line(text, str(path), number, format)
                            except ValueError as exc:
                                error = str(exc)
                        if error is not None:
                            report.malformed_lines += 1
                            if len(report.diagnostics) < limits.diagnostic_samples:
                                report.diagnostics.append(Diagnostic(str(path), number, error))
                            continue
                        assert event is not None
                        report.parsed_events += 1
                        if not filters.accepts(event):
                            continue
                        report.selected_events += 1
                        report.levels[event.level] += 1
                        db.execute(
                            "INSERT INTO events VALUES(NULL, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                event.timestamp.isoformat(timespec="microseconds"),
                                event.timestamp.replace(second=0, microsecond=0).isoformat(),
                                event.level,
                                event.component,
                                event.message,
                                event.source,
                                event.line,
                            ),
                        )
                        if report.selected_events % 1000 == 0:
                            db.commit()
                db.commit()
                db.execute("CREATE INDEX event_time ON events(stamp, id)")
                db.execute("CREATE INDEX event_source ON events(source, line)")
                states = [RuleState(rule) for rule in rules]
                for row in db.execute("SELECT * FROM events ORDER BY stamp, id"):
                    event = _event(row)
                    stamp = event_view(event).timestamp
                    if report.first_timestamp is None:
                        report.first_timestamp = stamp
                    report.last_timestamp = stamp
                    for state in states:
                        _add_finding(report, state.consume(event), limits)
                for state in states:
                    _add_finding(report, state.finish(), limits)
                report.findings.sort(key=lambda f: (f.start, f.rule_id))
                # Full messages are grouped in SQLite before display truncation.
                issue_query = """SELECT level, component, message, count(*) AS n FROM events
                    WHERE level IN ('ERROR', 'CRITICAL') GROUP BY level, component, message"""
                report.distinct_issues = int(
                    db.execute(f"SELECT count(*) FROM ({issue_query})").fetchone()[0]
                )
                for row in db.execute(
                    issue_query + " ORDER BY n DESC, level, component, message LIMIT ?",
                    (limits.issue_samples,),
                ):
                    message = str(row["message"])
                    report.issues.append(
                        Issue(
                            str(row["level"]),
                            str(row["component"]),
                            message[:2000],
                            int(row["n"]),
                            len(message) > 2000,
                        )
                    )
                bucket_query = """SELECT minute, count(*) AS n,
                    sum(level IN ('ERROR', 'CRITICAL')) AS errors FROM events GROUP BY minute"""
                report.total_timeline_buckets = int(
                    db.execute(f"SELECT count(*) FROM ({bucket_query})").fetchone()[0]
                )
                for row in db.execute(
                    bucket_query + " ORDER BY minute LIMIT ?", (limits.timeline_buckets,)
                ):
                    report.timeline.append(
                        TimelineBucket(
                            str(row["minute"]).replace("+00:00", "Z"),
                            int(row["n"]),
                            int(row["errors"]),
                        )
                    )
                for row in db.execute(
                    """SELECT * FROM events WHERE level IN ('ERROR', 'CRITICAL')
                                         ORDER BY stamp, id LIMIT ?""",
                    (limits.context_samples,),
                ):
                    before = db.execute(
                        """SELECT * FROM events WHERE source = ? AND line < ?
                                          ORDER BY line DESC LIMIT 2""",
                        (row["source"], row["line"]),
                    )
                    preceding = tuple(reversed([event_view(_event(r)) for r in before]))
                    after = db.execute(
                        """SELECT * FROM events WHERE source = ? AND line > ?
                                         ORDER BY line LIMIT 2""",
                        (row["source"], row["line"]),
                    )
                    report.contexts.append(
                        Context(
                            event_view(_event(row)),
                            preceding,
                            tuple(event_view(_event(r)) for r in after),
                        )
                    )
    except (OSError, sqlite3.Error) as exc:
        raise LogScopeError(f"Analysis could not complete: {exc}") from exc
    return report
