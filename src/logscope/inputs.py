"""Resolve inputs once and read bounded byte lines without modifying source logs."""

from collections.abc import Iterator, Sequence
from pathlib import Path

from logscope.models import LogScopeError

SUFFIXES = {".log", ".txt", ".jsonl", ".ndjson"}


def discover_files(paths: Sequence[Path], recursive: bool = False) -> tuple[Path, ...]:
    found: set[Path] = set()
    try:
        for path in paths:
            if path.is_file():
                found.add(path.resolve())
            elif path.is_dir():
                candidates = path.rglob("*") if recursive else path.iterdir()
                found.update(
                    p.resolve() for p in candidates if p.is_file() and p.suffix.lower() in SUFFIXES
                )
            else:
                raise LogScopeError(f"Input does not exist or is not a file/directory: {path}")
    except OSError as exc:
        raise LogScopeError(f"Cannot inspect inputs: {exc}") from exc
    if not found:
        raise LogScopeError("No supported input files found (.log, .txt, .jsonl, .ndjson)")
    return tuple(sorted(found, key=str))


def read_lines(path: Path, max_bytes: int) -> Iterator[tuple[int, str | None, str | None]]:
    """Yield (line, text, error). Oversized lines are drained in bounded chunks."""
    with path.open("rb") as stream:
        line = 0
        while data := stream.readline(max_bytes + 1):
            line += 1
            if len(data) > max_bytes:
                while not data.endswith(b"\n"):
                    data = stream.readline(max_bytes + 1)
                    if not data:
                        break
                yield line, None, "line exceeds max_line_bytes"
                continue
            try:
                text = data.decode("utf-8-sig" if line == 1 else "utf-8")
            except UnicodeDecodeError:
                yield line, None, "invalid UTF-8"
                continue
            yield line, text, None
