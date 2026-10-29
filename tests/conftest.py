from pathlib import Path

import pytest


@pytest.fixture
def log_file(tmp_path):
    def write(text, name="sample.log"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return write


@pytest.fixture
def example_dir():
    return Path(__file__).resolve().parents[1] / "examples"
