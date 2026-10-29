# Third-party notices

Original LogScope code and documentation are MIT licensed. No third-party
application code, assets or log files are vendored. The example logs are synthetic.

The runtime dependency PyYAML is MIT licensed; installing it keeps its own notices:
https://github.com/yaml/pyyaml/blob/main/LICENSE

Python and its bundled SQLite implementation retain their respective licenses.
Development tools (pytest, Ruff, mypy, build and type stubs) are separate tools;
the project license does not relicense them. Before distributing a frozen binary,
collect the exact installed components' full license texts and native notices.
No frozen executable or third-party driver is shipped in this version.
