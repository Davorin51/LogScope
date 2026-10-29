"""Validated literal-match rules and bounded chronological sliding windows."""

import re
from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
from math import isfinite
from pathlib import Path

import yaml

from logscope.models import Event, Finding, LogScopeError, event_view
from logscope.parsing import normalize_level


class _UniqueKeyLoader(yaml.SafeLoader):
    """Keep SafeLoader's tag restrictions and reject ambiguous duplicate fields."""

    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict[object, object]:
        if not isinstance(node, yaml.MappingNode):
            raise ValueError("expected a YAML mapping")
        result: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError(f"duplicate configuration key: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    contains: str
    threshold: int
    window_seconds: float
    levels: frozenset[str] = frozenset()
    component: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if type(self.threshold) is not int or not 1 <= self.threshold <= 10000:
            raise ValueError("threshold must be an integer between 1 and 10000")
        if (
            type(self.window_seconds) not in (int, float)
            or not isfinite(self.window_seconds)
            or not 0 < self.window_seconds <= 86400
        ):
            raise ValueError("window_seconds must be finite and in (0, 86400]")
        if not self.contains or not self.levels.issubset(
            ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        ):
            raise ValueError("rule requires non-empty contains and supported levels")

    def matches(self, event: Event) -> bool:
        return (
            self.contains.casefold() in event.message.casefold()
            and (not self.levels or event.level in self.levels)
            and (self.component is None or event.component == self.component)
        )


def load_rules(path: Path) -> tuple[Rule, ...]:
    try:
        with path.open("rb") as stream:
            data = stream.read(262145)
        if len(data) > 262144:
            raise ValueError("rules file exceeds 256 KiB")
        raw = yaml.load(data.decode("utf-8-sig"), Loader=_UniqueKeyLoader)
        if not isinstance(raw, dict) or set(raw) != {"version", "rules"}:
            raise ValueError("rules document requires exactly 'version' and 'rules'")
        if type(raw["version"]) is not int or raw["version"] != 1:
            raise ValueError("supported rules version is 1")
        if not isinstance(raw["rules"], list) or not 1 <= len(raw["rules"]) <= 100:
            raise ValueError("rules must be a list of 1 to 100 entries")
        rules: list[Rule] = []
        ids: set[str] = set()
        for item in raw["rules"]:
            required = {"id", "contains", "threshold", "window_seconds"}
            allowed = required | {"levels", "component", "description"}
            if not isinstance(item, dict) or not required <= set(item) <= allowed:
                raise ValueError("rule has missing or unknown fields")
            rule_id = item["id"]
            if not isinstance(rule_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", rule_id):
                raise ValueError("rule id must contain 1-80 letters, digits, '_' or '-'")
            if rule_id in ids:
                raise ValueError(f"duplicate rule id: {rule_id}")
            contains = item["contains"]
            if not isinstance(contains, str) or not 1 <= len(contains) <= 1000:
                raise ValueError("contains must be a string of 1-1000 characters")
            threshold = item["threshold"]
            window = item["window_seconds"]
            if type(threshold) is not int or not 1 <= threshold <= 10000:
                raise ValueError("threshold must be an integer between 1 and 10000")
            if type(window) not in (int, float) or not isfinite(window) or not 0 < window <= 86400:
                raise ValueError("window_seconds must be finite and in (0, 86400]")
            levels = item.get("levels", [])
            if not isinstance(levels, list) or not all(isinstance(x, str) for x in levels):
                raise ValueError("levels must be a list of level names")
            component = item.get("component")
            description = item.get("description", "")
            if component is not None and (not isinstance(component, str) or len(component) > 200):
                raise ValueError("component must be a string of at most 200 characters")
            if not isinstance(description, str) or len(description) > 2000:
                raise ValueError("description must be a string of at most 2000 characters")
            rules.append(
                Rule(
                    rule_id,
                    contains,
                    threshold,
                    float(window),
                    frozenset(normalize_level(x) for x in levels),
                    component,
                    description,
                )
            )
            ids.add(rule_id)
        return tuple(rules)
    except (OSError, ValueError, TypeError, yaml.YAMLError, RecursionError) as exc:
        raise LogScopeError(f"Invalid rules file '{path}': {exc}") from exc


@dataclass(slots=True)
class RuleState:
    rule: Rule
    recent: deque[Event] = field(init=False)
    first: Event | None = None
    last: Event | None = None
    count: int = 0

    def __post_init__(self) -> None:
        self.recent = deque(maxlen=self.rule.threshold)

    def consume(self, event: Event) -> Finding | None:
        if not self.rule.matches(event):
            return None
        completed = None
        if self.last is not None and event.timestamp - self.last.timestamp > timedelta(
            seconds=self.rule.window_seconds
        ):
            completed = self.finish()
        self.recent.append(event)
        triggered = len(self.recent) == self.rule.threshold and event.timestamp - self.recent[
            0
        ].timestamp <= timedelta(seconds=self.rule.window_seconds)
        if not triggered and self.first is not None:
            completed = self.finish()
        if triggered:
            if self.first is None:
                self.first = self.recent[0]
                self.count = self.rule.threshold
            else:
                self.count += 1
            self.last = event
        return completed

    def finish(self) -> Finding | None:
        if self.first is None or self.last is None:
            return None
        result = Finding(
            self.rule.id,
            self.rule.description,
            event_view(self.first).timestamp,
            event_view(self.last).timestamp,
            self.count,
            event_view(self.first),
        )
        self.first = self.last = None
        self.count = 0
        return result
