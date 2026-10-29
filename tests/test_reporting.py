import json
from dataclasses import asdict

import pytest

from logscope.analysis import analyze
from logscope.models import Diagnostic, LogScopeError
from logscope.reporting import render_html, render_json, write_atomic
from logscope.rules import Rule


def test_json_round_trip_and_determinism(example_dir):
    report = analyze([example_dir])
    assert json.loads(render_json(report)) == json.loads(json.dumps(asdict(report)))
    assert render_json(report) == render_json(analyze([example_dir]))


def test_html_escapes_messages_components_rules_sources_and_diagnostics(log_file):
    payload = '<img src=x onerror="alert(1)">'
    path = log_file("2026-10-29T00:00:00Z ERROR [<script>] " + payload + "\n")
    report = analyze(
        [path], rules=(Rule("unsafe", "img", 1, 60, description="<script>bad</script>"),)
    )
    report.diagnostics.append(Diagnostic("<script>source</script>", 1, "<script>reason</script>"))
    report.files.append("<img src=x>")
    report.filters["contains"] = "<script>filter</script>"
    html = render_html(report)
    assert "<script>" not in html and "<img" not in html
    assert "&lt;img" in html and "&lt;script&gt;" in html
    assert "Content-Security-Policy" in html
    assert "<script src" not in html and "<link " not in html
    assert "1 matching events" in html


def test_empty_report_renders(log_file):
    html = render_html(analyze([log_file("")]))
    assert "No selected events" in html
    assert "No configured rule reached its threshold" in html
    assert "width:nan" not in html


def test_atomic_write_preserves_unicode(tmp_path):
    target = tmp_path / "report.json"
    target.write_text("old")
    write_atomic(target, "čitanje ✓", [])
    assert target.read_text(encoding="utf-8") == "čitanje ✓"
    assert not list(tmp_path.glob("*.tmp"))


def test_input_overwrite_is_rejected(log_file):
    target = log_file("original")
    with pytest.raises(LogScopeError, match="overwrite"):
        write_atomic(target, "changed", [str(target.resolve())])
    assert target.read_text() == "original"


def test_failed_replace_retains_existing_report_and_cleans_temp(tmp_path, monkeypatch):
    from logscope import reporting

    target = tmp_path / "report.json"
    target.write_text("old")

    def fail(*args):
        raise PermissionError("locked file")

    monkeypatch.setattr(reporting.os, "replace", fail)
    with pytest.raises(LogScopeError, match="locked file"):
        write_atomic(target, "new", [])
    assert target.read_text() == "old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report.json"]


def test_missing_parent_is_actionable(tmp_path):
    with pytest.raises(LogScopeError, match="Cannot write"):
        write_atomic(tmp_path / "missing" / "report.json", "text", [])
