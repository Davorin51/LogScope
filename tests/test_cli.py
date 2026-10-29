import json
import subprocess
import sys

import pytest

from logscope import cli


def test_cli_end_to_end(example_dir, tmp_path, capsys):
    json_path = tmp_path / "report.json"
    html_path = tmp_path / "report.html"
    result = cli.main(
        [
            "analyze",
            str(example_dir),
            "--rules",
            str(example_dir / "rules.yaml"),
            "--json",
            str(json_path),
            "--html",
            str(html_path),
        ]
    )
    assert result == 0
    assert json.loads(json_path.read_text())["total_findings"] == 1
    assert "timeout_burst" in html_path.read_text(encoding="utf-8")
    assert "14 selected events" in capsys.readouterr().out


@pytest.mark.parametrize("gate", ["error", "alert", "malformed"])
def test_requested_quality_gates_write_reports_and_return_three(example_dir, tmp_path, gate):
    target = tmp_path / "report.json"
    result = cli.main(
        [
            "analyze",
            str(example_dir),
            "--rules",
            str(example_dir / "rules.yaml"),
            "--fail-on",
            gate,
            "--json",
            str(target),
        ]
    )
    assert result == 3 and target.is_file()


def test_clean_quality_gate_passes(log_file):
    path = log_file("2026-10-29T00:00:00Z INFO Ready\n")
    assert cli.main(["analyze", str(path), "--fail-on", "error", "--fail-on", "malformed"]) == 0


def test_cli_filters(example_dir, tmp_path):
    target = tmp_path / "report.json"
    assert (
        cli.main(
            [
                "analyze",
                str(example_dir),
                "--level",
                "WARN",
                "--component",
                "gateway",
                "--contains",
                "SLOW",
                "--since",
                "2026-10-29T10:15:00Z",
                "--until",
                "2026-10-29T10:16:00Z",
                "--json",
                str(target),
            ]
        )
        == 0
    )
    assert json.loads(target.read_text())["selected_events"] == 1


@pytest.mark.parametrize(
    "args",
    [
        ["--level", "invalid"],
        ["--since", "today"],
        ["--max-line-bytes", "0"],
        ["--since", "2026-10-29T00:00:01Z", "--until", "2026-10-29T00:00:00Z"],
    ],
)
def test_invalid_configuration_is_actionable(log_file, args, capsys):
    assert cli.main(["analyze", str(log_file("")), *args]) == 1
    assert "LogScope:" in capsys.readouterr().err


def test_missing_input(tmp_path, capsys):
    assert cli.main(["analyze", str(tmp_path / "missing.log")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_input_collision_preflight_prevents_both_outputs(log_file, tmp_path):
    source = log_file("2026-10-29T00:00:00Z INFO Original\n")
    output = tmp_path / "report.json"
    assert cli.main(["analyze", str(source), "--json", str(output), "--html", str(source)]) == 1
    assert not output.exists()
    assert "Original" in source.read_text()


def test_duplicate_output_paths_rejected(log_file, tmp_path):
    target = tmp_path / "report.html"
    assert (
        cli.main(["analyze", str(log_file("")), "--json", str(target), "--html", str(target)]) == 1
    )
    assert not target.exists()


def test_rules_file_cannot_be_overwritten(example_dir, tmp_path):
    rules = tmp_path / "rules.yaml"
    original = (example_dir / "rules.yaml").read_text()
    rules.write_text(original)
    assert cli.main(["analyze", str(example_dir), "--rules", str(rules), "--json", str(rules)]) == 1
    assert rules.read_text() == original


def test_keyboard_interrupt_returns_130(monkeypatch, log_file):
    def fail(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "analyze", fail)
    assert cli.main(["analyze", str(log_file(""))]) == 130


def test_real_module_entrypoint(example_dir):
    completed = subprocess.run(
        [sys.executable, "-m", "logscope", "analyze", str(example_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0
    assert "14 selected events" in completed.stdout


def test_real_cli_usage_error():
    completed = subprocess.run([sys.executable, "-m", "logscope", "analyze"], capture_output=True)
    assert completed.returncode == 2
