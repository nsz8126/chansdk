# -*- coding: utf-8 -*-
"""Tests for README documentation verification."""

import json

from scripts.verify_docs import extract_python_blocks, main


def test_extract_python_blocks_tracks_markers_and_lines():
    blocks = extract_python_blocks(
        "text\n\n```python\n# docs: run\nprint('ok')\n```\n"
        "\n```bash\nnot python\n```\n"
    )

    assert len(blocks) == 1
    assert blocks[0].marker == "run"
    assert blocks[0].start_line == 4


def test_verify_docs_compiles_and_runs_marked_block(tmp_path, capsys):
    readme = tmp_path / "README.md"
    readme.write_text(
        "```python\n# docs: run\nprint('docs ok')\n```\n"
        "\n```python\n# docs: external\nvalue = 1\n```\n",
        encoding="utf-8",
    )

    assert main(["--readme", str(readme), "--run-marked"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["block_count"] == 2
    assert all(item["status"] == "PASS" for item in payload["results"])
