"""Command line interface. Exit 3 is an explicitly requested quality-gate failure."""

import argparse
import sys
from pathlib import Path
from typing import cast

from logscope import __version__
from logscope.analysis import analyze
from logscope.models import Filters, Limits, LogScopeError
from logscope.parsing import LogFormat, normalize_level, parse_timestamp
from logscope.reporting import render_html, render_json, write_atomic
from logscope.rules import load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="logscope", description="Local log analysis and reports")
    parser.add_argument("--version", action="version", version=f"LogScope {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("analyze", help="Analyze completed UTF-8 text/JSONL logs")
    command.add_argument("paths", nargs="+", type=Path)
    command.add_argument("--format", choices=("auto", "text", "jsonl"), default="auto")
    command.add_argument("--rules", type=Path, help="Validated YAML/JSON rule document")
    command.add_argument("--recursive", action="store_true")
    command.add_argument("--since", help="Inclusive ISO date/time; absent offset means UTC")
    command.add_argument("--until", help="Inclusive ISO date/time; absent offset means UTC")
    command.add_argument("--level", action="append", default=[])
    command.add_argument("--component", action="append", default=[])
    command.add_argument("--contains", default="", help="Case-insensitive literal message filter")
    command.add_argument("--max-line-bytes", type=int, default=262144)
    command.add_argument("--json", type=Path, dest="json_path")
    command.add_argument("--html", type=Path, dest="html_path")
    command.add_argument(
        "--fail-on", choices=("error", "alert", "malformed"), action="append", default=[]
    )
    args = parser.parse_args(argv)
    try:
        filters = Filters(
            since=parse_timestamp(args.since) if args.since else None,
            until=parse_timestamp(args.until) if args.until else None,
            levels=frozenset(normalize_level(level) for level in args.level),
            components=frozenset(args.component),
            contains=args.contains,
        )
        outputs = [p.resolve() for p in (args.json_path, args.html_path) if p is not None]
        if len(set(outputs)) != len(outputs):
            raise LogScopeError("JSON and HTML output paths must be different")
        if args.rules is not None and args.rules.resolve() in outputs:
            raise LogScopeError("Refusing to overwrite the rules file")
        rules = load_rules(args.rules) if args.rules else ()
        report = analyze(
            args.paths,
            format=cast(LogFormat, args.format),
            rules=rules,
            filters=filters,
            limits=Limits(max_line_bytes=args.max_line_bytes),
            recursive=args.recursive,
        )
        # Preflight all input collisions before writing either output.
        if any(str(p) in report.files for p in outputs):
            raise LogScopeError("Refusing to overwrite an input log with a report")
        if args.json_path:
            write_atomic(args.json_path, render_json(report), report.files)
        if args.html_path:
            write_atomic(args.html_path, render_html(report), report.files)
        errors = report.levels["ERROR"] + report.levels["CRITICAL"]
        print(f"LogScope | {len(report.files)} files | {report.selected_events} selected events")
        print(
            f"Errors: {errors} | Rule incidents: {report.total_findings} | "
            f"Malformed lines: {report.malformed_lines}"
        )
        for issue in report.issues[:5]:
            # ASCII escaping handles terminal controls and legacy Windows encodings.
            print(
                f"  {issue.count}x {issue.level} [{ascii(issue.component)}] "
                f"{ascii(issue.message[:160])}"
            )
        failed = (
            ("error" in args.fail_on and errors > 0)
            or ("alert" in args.fail_on and report.total_findings > 0)
            or ("malformed" in args.fail_on and report.malformed_lines > 0)
        )
        return 3 if failed else 0
    except (LogScopeError, ValueError) as exc:
        print(f"LogScope: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("LogScope: interrupted", file=sys.stderr)
        return 130
