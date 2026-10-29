import json
import random
from datetime import timedelta

import pytest

from logscope.models import Event, LogScopeError
from logscope.parsing import parse_timestamp
from logscope.rules import Rule, RuleState, load_rules

BASE = parse_timestamp("2026-10-29T00:00:00Z")


def event(second, message="Connection timeout", level="ERROR", component="gateway"):
    return Event(BASE + timedelta(seconds=second), level, message, component, "test.log", 1)


def collect(rule, seconds):
    state = RuleState(rule)
    findings = []
    for second in seconds:
        finding = state.consume(event(second))
        if finding:
            findings.append(finding)
    final = state.finish()
    if final:
        findings.append(final)
    return findings


def test_inclusive_window_boundary_and_grouped_episode():
    findings = collect(Rule("burst", "timeout", 3, 60), [0, 30, 60, 70])
    assert len(findings) == 1
    assert findings[0].match_count == 4
    assert findings[0].start.endswith("00:00:00Z")
    assert findings[0].end.endswith("00:01:10Z")


def test_outside_window_does_not_trigger():
    assert collect(Rule("burst", "timeout", 3, 60), [0, 30, 60.000001]) == []


def test_independent_episodes():
    findings = collect(Rule("burst", "timeout", 2, 10), [0, 5, 100, 105])
    assert [f.match_count for f in findings] == [2, 2]


def test_threshold_one_separates_long_gaps():
    findings = collect(Rule("one", "timeout", 1, 10), [0, 5, 100])
    assert [f.match_count for f in findings] == [2, 1]


def test_duplicate_timestamps_are_separate_events():
    assert collect(Rule("burst", "timeout", 3, 1), [0, 0, 0])[0].match_count == 3


def test_match_is_literal_case_insensitive_and_scoped():
    rule = Rule("r", "[Timeout]", 1, 60, frozenset({"ERROR"}), "gateway")
    assert rule.matches(event(0, "[TIMEOUT] failed"))
    assert not rule.matches(event(0, "Timeout failed"))
    assert not rule.matches(event(0, "[TIMEOUT] failed", level="INFO"))
    assert not rule.matches(event(0, "[TIMEOUT] failed", component="worker"))


def test_against_simple_sliding_window_oracle():
    # Independent O(n²) reference checks active/inactive transitions across random timelines.
    rng = random.Random(713)
    for threshold in (1, 2, 5):
        seconds = sorted(rng.randrange(0, 2000) for _ in range(200))
        expected = 0
        active = False
        previous = None
        for index, now in enumerate(seconds):
            if previous is not None and now - previous > 20:
                active = False
            triggered = sum(now - t <= 20 for t in seconds[: index + 1]) >= threshold
            if triggered and not active:
                expected += 1
            active = triggered
            previous = now
        assert len(collect(Rule("r", "timeout", threshold, 20), seconds)) == expected


def base_rule():
    return {"id": "timeouts", "contains": "timeout", "threshold": 5, "window_seconds": 60}


def test_load_yaml(example_dir):
    rules = load_rules(example_dir / "rules.yaml")
    assert rules[0].threshold == 5
    assert rules[0].component == "gateway"
    assert rules[0].levels == frozenset({"ERROR", "CRITICAL"})


def test_load_json(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"version": 1, "rules": [base_rule()]}))
    assert load_rules(path)[0].id == "timeouts"


@pytest.mark.parametrize(
    "patch",
    [
        {"threshold": True},
        {"threshold": 0},
        {"threshold": 10001},
        {"threshold": 2.5},
        {"window_seconds": 0},
        {"window_seconds": float("inf")},
        {"window_seconds": float("nan")},
        {"window_seconds": True},
        {"contains": ""},
        {"contains": []},
        {"id": "bad id"},
        {"levels": "ERROR"},
        {"levels": ["WRONG"]},
        {"levels": [3]},
        {"component": 2},
        {"description": {}},
        {"typo": 1},
    ],
)
def test_invalid_rule_fields(tmp_path, patch):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"version": 1, "rules": [base_rule() | patch]}))
    with pytest.raises(LogScopeError):
        load_rules(path)


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"version": True, "rules": [base_rule()]},
        {"version": 2, "rules": [base_rule()]},
        {"version": 1, "rules": []},
        {"version": 1, "rules": {}},
        {"version": 1, "rules": [base_rule(), base_rule()]},
        {"version": 1, "rules": [{}]},
        {"version": 1, "rules": [None]},
    ],
)
def test_invalid_documents(tmp_path, document):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(document))
    with pytest.raises(LogScopeError):
        load_rules(path)


def test_yaml_cannot_construct_python_objects(tmp_path):
    path = tmp_path / "unsafe.yaml"
    path.write_text('!!python/object/apply:os.system ["echo should-not-run"]')
    with pytest.raises(LogScopeError):
        load_rules(path)


def test_rule_size_limit(tmp_path):
    path = tmp_path / "huge.yaml"
    path.write_bytes(b"x" * 262145)
    with pytest.raises(LogScopeError, match="256 KiB"):
        load_rules(path)


def test_duplicate_yaml_configuration_keys_rejected(tmp_path):
    path = tmp_path / "rules.yaml"
    path.write_text("version: 1\nversion: 2\nrules: []\n")
    with pytest.raises(LogScopeError, match="duplicate configuration key"):
        load_rules(path)


def test_unhashable_yaml_key_is_actionable(tmp_path):
    path = tmp_path / "rules.yaml"
    path.write_text("? [one, two]\n: value\n")
    with pytest.raises(LogScopeError):
        load_rules(path)
