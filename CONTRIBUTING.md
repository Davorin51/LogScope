# Contributing

Use Python 3.12+, a virtual environment and `python -m pip install -e ".[dev]"`.
Work in a feature branch and open a PR against `development`. Do not push directly
to main. Keep commits focused and run pytest, Ruff, mypy and a package build.

Prefer semantic tests: a known timeline, expected incident windows, unchanged
source bytes, a real CLI invocation or the previous output surviving a failed
write. For new formats, include a small synthetic fixture with valid and malformed
records. Never commit production logs, credentials, private paths or tokens.

Document timestamp assumptions, ordering, sample limits and any changed report
schema. Introduce a version bump when a report contract changes incompatibly.
Performance claims require a reproducible command, environment and raw result.

New code and assets must have verified compatible licenses. Original project
code is MIT; dependencies retain their own licenses.
