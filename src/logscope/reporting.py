"""Portable JSON and escaped, self-contained HTML with atomic per-file output."""

import json
import os
from contextlib import suppress
from dataclasses import asdict
from html import escape
from importlib import resources
from pathlib import Path
from string import Template
from tempfile import NamedTemporaryFile

from logscope.models import EventView, LogScopeError, Report


def render_json(report: Report) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _event(event: EventView) -> str:
    clipped = " [message truncated]" if event.message_truncated else ""
    return escape(f"{event.timestamp} {event.level} [{event.component}] {event.message}{clipped}")


def render_html(report: Report) -> str:
    errors = report.levels["ERROR"] + report.levels["CRITICAL"]
    peak = max((bucket.events for bucket in report.timeline), default=1)
    timeline = "".join(
        f'<tr><td>{escape(b.minute)}</td><td><div class="bar" '
        f'style="width:{b.events / peak * 100:.2f}%"></div></td>'
        f"<td>{b.events}</td><td>{b.errors}</td></tr>"
        for b in report.timeline
    )
    issues = "".join(
        f"<tr><td>{issue.count}</td><td>{escape(issue.level)}</td>"
        f"<td>{escape(issue.component)}</td><td>{escape(issue.message)}"
        f"{' [truncated]' if issue.message_truncated else ''}</td></tr>"
        for issue in report.issues
    )
    findings = "".join(
        f'<article><span class="tag">{escape(f.rule_id)}</span>'
        f"<h3>{escape(f.description or f.rule_id)}</h3>"
        f"<p>{escape(f.start)} → {escape(f.end)} · {f.match_count} matching events</p>"
        f"<pre>{_event(f.first_match)}</pre></article>"
        for f in report.findings
    )
    contexts = "".join(
        f'<article><p class="muted">{escape(c.event.source)}:{c.event.line}</p><pre>'
        + "\n".join(_event(e) for e in c.before)
        + f'</pre><pre class="error">{_event(c.event)}</pre><pre>'
        + "\n".join(_event(e) for e in c.after)
        + "</pre></article>"
        for c in report.contexts
    )
    diagnostics = "".join(
        f"<li>{escape(d.source)}:{d.line} — {escape(d.reason)}</li>" for d in report.diagnostics
    )
    files = "".join(f"<li>{escape(path)}</li>" for path in report.files)
    levels = "".join(
        f'<span class="pill">{escape(level)} <b>{count}</b></span>'
        for level, count in report.levels.items()
    )
    filters = escape(json.dumps(report.filters, ensure_ascii=False))
    template = (
        resources.files("logscope").joinpath("templates/report.html").read_text(encoding="utf-8")
    )
    return Template(template).substitute(
        first_timestamp=escape(report.first_timestamp or "No selected events"),
        last_timestamp=escape(report.last_timestamp or "—"),
        selected_events=report.selected_events,
        errors=errors,
        total_findings=report.total_findings,
        malformed_lines=report.malformed_lines,
        levels=levels,
        timeline_shown=len(report.timeline),
        timeline_total=report.total_timeline_buckets,
        timeline=timeline,
        findings_shown=len(report.findings),
        findings_total=report.total_findings,
        findings=findings or "<p>No configured rule reached its threshold.</p>",
        issues_shown=len(report.issues),
        issues_total=report.distinct_issues,
        issues=issues,
        contexts_shown=len(report.contexts),
        contexts=contexts,
        malformed_count=report.malformed_lines,
        diagnostics_shown=len(report.diagnostics),
        diagnostics=diagnostics,
        sources=files,
        filters=filters,
        line_count=report.lines,
        blank_count=report.blank_lines,
        parsed_count=report.parsed_events,
        selected_count=report.selected_events,
    )


def write_atomic(path: Path, text: str, source_files: list[str]) -> None:
    target = path.resolve()
    if target in (Path(source).resolve() for source in source_files):
        raise LogScopeError("Refusing to overwrite an input log with a report")
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        raise LogScopeError(f"Cannot write report '{path}': {exc}") from exc
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
