"""Strict, line-oriented parsers with explicit timestamp semantics."""

import json
import re
from datetime import UTC, datetime
from typing import Literal

from logscope.models import ALIASES, LEVELS, Event

LogFormat = Literal["auto", "text", "jsonl"]
STAMP = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?"
TIMESTAMP = re.compile(rf"^{STAMP}$", re.ASCII)
TEXT = re.compile(
    rf"^(?P<timestamp>{STAMP})\s+(?P<level>[A-Za-z]+)\s+(?:\[(?P<component>[^\]\r\n]{{1,200}})\]\s*)?(?P<message>.*)$",
    re.ASCII,
)


def parse_timestamp(value: str) -> datetime:
    """Full ISO calendar date/time; absent offset means UTC, never local time."""
    if not TIMESTAMP.fullmatch(value):
        raise ValueError("timestamp requires YYYY-MM-DDTHH:MM:SS with optional UTC offset")
    try:
        result = datetime.fromisoformat(value.replace(",", "."))
        if result.tzinfo is None:
            result = result.replace(tzinfo=UTC)
        return result.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid timestamp or UTC conversion outside supported range") from exc


def normalize_level(value: str) -> str:
    level = value.upper()
    level = ALIASES.get(level, level)
    if level not in LEVELS:
        raise ValueError(f"unsupported level: {value[:40]}")
    return level


def parse_line(text: str, source: str, line: int, format: LogFormat = "auto") -> Event:
    stripped = text.strip()
    use_json = format == "jsonl" or (format == "auto" and stripped.startswith("{"))
    if use_json:
        try:
            payload = json.loads(stripped)
        except (ValueError, RecursionError) as exc:
            raise ValueError("invalid JSON object") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON record must be an object")
        for key in ("timestamp", "level", "message"):
            if not isinstance(payload.get(key), str):
                raise ValueError(f"JSON field '{key}' must be a string")
        component = payload.get("component", "")
        if not isinstance(component, str) or len(component) > 200:
            raise ValueError("component must be a string of at most 200 characters")
        return Event(
            parse_timestamp(payload["timestamp"]),
            normalize_level(payload["level"]),
            payload["message"],
            component,
            source,
            line,
        )
    if format not in ("auto", "text"):
        raise ValueError("unknown log format")
    match = TEXT.fullmatch(stripped)
    if match is None:
        raise ValueError("expected full timestamp, level, optional [component] and message")
    return Event(
        parse_timestamp(match["timestamp"]),
        normalize_level(match["level"]),
        match["message"],
        match["component"] or "",
        source,
        line,
    )
