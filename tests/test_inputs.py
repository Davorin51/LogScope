import pytest

from logscope.inputs import discover_files, read_lines
from logscope.models import LogScopeError


def test_directory_discovery_is_sorted_deduplicated_and_filtered(tmp_path):
    a = tmp_path / "a.log"
    a.write_text("")
    b = tmp_path / "b.JSONL"
    b.write_text("")
    (tmp_path / "ignored.csv").write_text("")
    assert discover_files([tmp_path, a]) == (a.resolve(), b.resolve())


def test_recursive_discovery(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    log = child / "a.log"
    log.write_text("")
    with pytest.raises(LogScopeError, match="No supported"):
        discover_files([tmp_path])
    assert discover_files([tmp_path], recursive=True) == (log.resolve(),)


def test_explicit_file_accepts_other_suffix(tmp_path):
    log = tmp_path / "application.out"
    log.write_text("")
    assert discover_files([log]) == (log.resolve(),)


def test_missing_input(tmp_path):
    with pytest.raises(LogScopeError, match="does not exist"):
        discover_files([tmp_path / "missing"])


def test_bom_crlf_invalid_encoding_and_last_line(tmp_path):
    path = tmp_path / "a.log"
    path.write_bytes(b"\xef\xbb\xbffirst\r\n\xff\nlast")
    assert list(read_lines(path, 100)) == [
        (1, "first\r\n", None),
        (2, None, "invalid UTF-8"),
        (3, "last", None),
    ]


def test_long_line_is_drained_once_and_next_line_retained(tmp_path):
    path = tmp_path / "a.log"
    path.write_bytes(b"x" * 10000 + b"\nnext\n")
    assert list(read_lines(path, 8)) == [
        (1, None, "line exceeds max_line_bytes"),
        (2, "next\n", None),
    ]


def test_long_final_line(tmp_path):
    path = tmp_path / "a.log"
    path.write_bytes(b"x" * 1000)
    assert list(read_lines(path, 10)) == [(1, None, "line exceeds max_line_bytes")]


def test_exact_byte_limit(tmp_path):
    path = tmp_path / "a.log"
    path.write_bytes(b"1234567\n")
    assert list(read_lines(path, 8)) == [(1, "1234567\n", None)]
