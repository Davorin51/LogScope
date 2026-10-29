"""Shared immutable records and explicit resource limits."""

from dataclasses import dataclass, field
from datetime import datetime

LEVELS = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
ALIASES = {"WARN": "WARNING", "FATAL": "CRITICAL"}


class LogScopeError(Exception):
    """An input, configuration or output error suitable for CLI display."""


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    level: str
    message: str
    component: str
    source: str
    line: int


@dataclass(frozen=True, slots=True)
class Diagnostic:
    source: str
    line: int
    reason: str


@dataclass(frozen=True, slots=True)
class EventView:
    timestamp: str
    level: str
    message: str
    component: str
    source: str
    line: int
    message_truncated: bool


def event_view(event: Event) -> EventView:
    return EventView(
        event.timestamp.isoformat().replace("+00:00", "Z"),
        event.level,
        event.message[:2000],
        event.component,
        event.source,
        event.line,
        len(event.message) > 2000,
    )


@dataclass(frozen=True, slots=True)
class Issue:
    level: str
    component: str
    message: str
    count: int
    message_truncated: bool


@dataclass(frozen=True, slots=True)
class TimelineBucket:
    minute: str
    events: int
    errors: int


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    description: str
    start: str
    end: str
    match_count: int
    first_match: EventView


@dataclass(frozen=True, slots=True)
class Context:
    event: EventView
    before: tuple[EventView, ...]
    after: tuple[EventView, ...]


@dataclass(frozen=True, slots=True)
class Limits:
    max_line_bytes: int = 262144
    diagnostic_samples: int = 20
    issue_samples: int = 20
    context_samples: int = 10
    finding_samples: int = 100
    timeline_buckets: int = 1000

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_line_bytes > 1048576:
            raise ValueError("max_line_bytes must be <= 1048576")


@dataclass(frozen=True, slots=True)
class Filters:
    since: datetime | None = None
    until: datetime | None = None
    levels: frozenset[str] = frozenset()
    components: frozenset[str] = frozenset()
    contains: str = ""

    def __post_init__(self) -> None:
        for timestamp in (self.since, self.until):
            if timestamp is not None and timestamp.utcoffset() is None:
                raise ValueError("filter timestamps must be timezone-aware")
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("since must not be later than until")
        if not self.levels.issubset(LEVELS):
            raise ValueError("unknown filter level")

    def accepts(self, event: Event) -> bool:
        return (
            (self.since is None or event.timestamp >= self.since)
            and (self.until is None or event.timestamp <= self.until)
            and (not self.levels or event.level in self.levels)
            and (not self.components or event.component in self.components)
            and self.contains.casefold() in event.message.casefold()
        )


@dataclass(slots=True)
class Report:
    schema_version: int = 1
    files: list[str] = field(default_factory=list)
    filters: dict[str, object] = field(default_factory=dict)
    lines: int = 0
    blank_lines: int = 0
    parsed_events: int = 0
    selected_events: int = 0
    malformed_lines: int = 0
    levels: dict[str, int] = field(default_factory=lambda: dict.fromkeys(LEVELS, 0))
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    distinct_issues: int = 0
    timeline: list[TimelineBucket] = field(default_factory=list)
    total_timeline_buckets: int = 0
    findings: list[Finding] = field(default_factory=list)
    total_findings: int = 0
    contexts: list[Context] = field(default_factory=list)
    rules: list[dict[str, object]] = field(default_factory=list)
