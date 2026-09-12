# -*- coding: utf-8 -*-
"""Tests for the repeatable gray probe utility."""

import json

from scripts.gray_probe import _make_rows, main


def test_gray_probe_rows_follow_requested_start_date():
    rows = _make_rows(__import__("datetime").date(2025, 1, 2), count=2)

    assert [row["date"] for row in rows] == ["2025-01-02", "2025-01-03"]


def test_gray_probe_local_run_accepts_non_default_window(capsys):
    assert main(
        [
            "--begin",
            "2025-01-02",
            "--end",
            "2025-01-10",
            "--repeat",
            "1",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["status"] == "PASS"
    assert payload["results"][0]["klu_count"] == 9
