from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest

from logscope.analysis import analyze
from logscope.models import Filters, Limits, LogScopeError
from logscope.parsing import parse_timestamp
from logscope.rules import Rule, load_rules


def test_demo_golden_counts_and_context(example_dir):
    report = analyze([example_dir], rules=load_rules(example_dir / "rules.yaml"))
    assert report.lines == 15
    assert report.parsed_events == report.selected_events == 14
    assert report.malformed_lines == 1
    assert report.levels["ERROR"] == 6
    assert report.levels["WARNING"] == 1
    assert report.total_findings == 1
    assert report.findings[0].match_count == 5
    assert report.issues[0].message == "Connection timeout"
    assert report.issues[0].count == 5
    assert [(b.events, b.errors) for b in report.timeline] == [(12, 6), (2, 0)]
    first = report.contexts[0]
    assert first.event.line == 3
    assert [e.line for e in first.before] == [1, 2]
    assert [e.line for e in first.after] == [4, 5]
    assert all(e.source == first.event.source for e in (*first.before, *first.after))


def test_unsorted_files_are_globally_ordered(log_file):
    a = log_file(
        "2026-10-29T00:00:20Z ERROR timeout\n2026-10-29T00:00:00Z ERROR timeout\n", "a.log"
    )
    b = log_file("2026-10-29T01:00:10+01:00 ERROR timeout\n", "b.log")
    report = analyze([b, a], rules=(Rule("r", "timeout", 3, 20),))
    assert report.total_findings == 1
    assert report.first_timestamp == "2026-10-29T00:00:00Z"
    assert report.last_timestamp == "2026-10-29T00:00:20Z"
    assert asdict(report) == asdict(analyze([a, b], rules=(Rule("r", "timeout", 3, 20),)))


def test_filters_are_inclusive_and_apply_to_rules_and_context(log_file):
    p = log_file(
        "2026-10-29T00:00:00Z ERROR [a] timeout\n"
        "2026-10-29T00:00:01Z ERROR [b] timeout\n"
        "2026-10-29T00:00:02Z INFO [a] TIMEOUT\n"
        "2026-10-29T00:00:03Z ERROR [a] timeout\n"
    )
    report = analyze(
        [p],
        filters=Filters(
            since=parse_timestamp("2026-10-29T00:00:01Z"),
            until=parse_timestamp("2026-10-29T00:00:03Z"),
            levels=frozenset({"ERROR"}),
            components=frozenset({"a"}),
            contains="TIMEOUT",
        ),
        rules=(Rule("r", "timeout", 2, 60),),
    )
    assert report.parsed_events == 4 and report.selected_events == 1
    assert report.total_findings == 0
    assert report.contexts[0].before == report.contexts[0].after == ()


def test_blank_empty_invalid_bytes_and_oversized_lines(tmp_path):
    path = tmp_path / "x.log"
    path.write_bytes(b"\n\xff\n" + b"x" * 10000 + b"\n2026-10-29T00:00:00Z INFO ok\n")
    report = analyze([path], limits=Limits(max_line_bytes=64))
    assert (report.lines, report.blank_lines, report.malformed_lines, report.selected_events) == (
        4,
        1,
        2,
        1,
    )
    assert [d.line for d in report.diagnostics] == [2, 3]


def test_empty_file_is_valid(log_file):
    report = analyze([log_file("")])
    assert report.selected_events == 0
    assert report.first_timestamp is report.last_timestamp is None
    assert report.issues == report.timeline == report.contexts == []


def test_all_samples_are_bounded_but_counts_are_not(log_file):
    text = "bad\n" * 5 + "".join(f"2026-10-29T00:0{i}:00Z ERROR error-{i}\n" for i in range(5))
    p = log_file(text)
    report = analyze(
        [p],
        rules=(Rule("r", "error", 1, 1),),
        limits=Limits(
            diagnostic_samples=2,
            issue_samples=2,
            context_samples=2,
            finding_samples=2,
            timeline_buckets=2,
        ),
    )
    assert report.malformed_lines == 5 and len(report.diagnostics) == 2
    assert report.distinct_issues == 5 and len(report.issues) == 2
    assert report.total_findings == 5 and len(report.findings) == 2
    assert report.total_timeline_buckets == 5 and len(report.timeline) == 2
    assert len(report.contexts) == 2


def test_messages_group_before_display_truncation(log_file):
    text = "x" * 2100
    p = log_file(f"2026-10-29T00:00:00Z ERROR {text}a\n2026-10-29T00:00:01Z ERROR {text}b\n")
    report = analyze([p])
    assert report.distinct_issues == 2
    assert all(i.count == 1 and i.message_truncated for i in report.issues)
    assert report.contexts[0].event.message_truncated


def test_minute_boundary_and_pre_epoch(log_file):
    p = log_file("1969-12-31T23:59:59.999999Z INFO old\n1970-01-01T00:00:00Z INFO new\n")
    report = analyze([p])
    assert [b.minute for b in report.timeline] == ["1969-12-31T23:59:00Z", "1970-01-01T00:00:00Z"]


def test_input_logs_are_unchanged(example_dir):
    files = [example_dir / "service.log", example_dir / "worker.jsonl"]
    before = [p.read_bytes() for p in files]
    analyze(files)
    assert before == [p.read_bytes() for p in files]


def test_read_error_is_actionable_and_spool_closes(log_file, monkeypatch):
    p = log_file("content")

    def fail(*args, **kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(LogScopeError, match="permission denied"):
        analyze([p])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"levels": frozenset({"NOPE"})},
        {"since": datetime(2026, 1, 1)},
        {
            "since": parse_timestamp("2026-10-29T10:00:00Z"),
            "until": parse_timestamp("2026-10-29T09:00:00Z"),
        },
    ],
)
def test_invalid_filters(kwargs):
    with pytest.raises(ValueError):
        Filters(**kwargs)


@pytest.mark.parametrize(
    "kwargs", [{"diagnostic_samples": 0}, {"max_line_bytes": 1048577}, {"context_samples": True}]
)
def test_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        Limits(**kwargs)
