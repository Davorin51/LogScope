from datetime import UTC, datetime

import pytest

from logscope.parsing import normalize_level, parse_line, parse_timestamp


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-10-29T10:15:00Z",
        "2026-10-29 10:15:00",
        "2026-10-29T11:15:00+01:00",
        "2026-10-29T05:15:00-05:00",
        "2026-10-29T10:15:00.000000Z",
    ],
)
def test_timestamp_normalization(stamp):
    assert parse_timestamp(stamp) == datetime(2026, 10, 29, 10, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "stamp",
    [
        "10:15:00",
        "2026-10-29",
        "2026-13-01T00:00:00Z",
        "2026-10-29T00:00:00+25:00",
        "0001-01-01T00:00:00+01:00",
        "2026-10-29T00:00:60Z",
        "nonsense",
    ],
)
def test_invalid_timestamps(stamp):
    with pytest.raises(ValueError):
        parse_timestamp(stamp)


def test_fractional_microseconds_and_comma():
    assert parse_timestamp("2026-10-29 10:15:00,123456").microsecond == 123456


def test_text_components_and_aliases():
    event = parse_line("2026-10-29 10:15:00 WARN [gateway]  Request slow", "a.log", 3)
    assert (event.level, event.component, event.message, event.line) == (
        "WARNING",
        "gateway",
        "Request slow",
        3,
    )
    assert event.source == "a.log"


def test_text_without_component():
    event = parse_line("2026-10-29T10:15:00Z INFO Process ready", "a", 1)
    assert event.component == ""
    assert event.message == "Process ready"


def test_jsonl_and_unicode():
    event = parse_line(
        '{"timestamp":"2026-10-29T10:15:00Z","level":"fatal",'
        '"message":"Pogreška čitanja\\nsecond line","component":"radnik"}',
        "x",
        1,
    )
    assert event.level == "CRITICAL"
    assert event.message == "Pogreška čitanja\nsecond line"


@pytest.mark.parametrize(
    "text,format",
    [
        ("not a record", "auto"),
        ("{}", "auto"),
        ("[]", "jsonl"),
        ('{"timestamp":2,"level":"INFO","message":"x"}', "jsonl"),
        ('{"timestamp":"2026-10-29T00:00:00Z","level":null,"message":"x"}', "jsonl"),
        ('{"timestamp":"2026-10-29T00:00:00Z","level":"INFO","message":2}', "jsonl"),
        (
            '{"timestamp":"2026-10-29T00:00:00Z","level":"INFO","message":"x","component":4}',
            "jsonl",
        ),
        ('{"a":', "auto"),
        ("2026-10-29T10:15:00Z SILLY Message", "text"),
        ("2026-10-29T10:15:00Z INFO Message", "jsonl"),
    ],
)
def test_malformed_records(text, format):
    with pytest.raises(ValueError):
        parse_line(text, "x", 1, format)


@pytest.mark.parametrize(
    "value,expected", [("warn", "WARNING"), ("FATAL", "CRITICAL"), ("INFO", "INFO")]
)
def test_level_aliases(value, expected):
    assert normalize_level(value) == expected
