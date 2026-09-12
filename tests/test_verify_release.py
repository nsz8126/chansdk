# -*- coding: utf-8 -*-
"""Tests for release-gate helpers."""

from scripts.verify_release import (
    _clear_release_artifacts,
    _latest_wheel,
    _read_project_version,
    _tail,
)


def test_tail_keeps_only_latest_output():
    assert _tail("abcdef", limit=3) == "def"


def test_project_version_is_declared():
    assert _read_project_version() == "1.0.1"


def test_latest_wheel_returns_most_recent_artifact(tmp_path, monkeypatch):
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    old_wheel = wheel_dir / "chansdk-1.0.0-py3-none-any.whl"
    new_wheel = wheel_dir / "chansdk-1.0.1-py3-none-any.whl"
    old_wheel.write_bytes(b"old")
    new_wheel.write_bytes(b"new")
    old_wheel.touch()
    old_mtime = old_wheel.stat().st_mtime
    new_wheel.touch()
    new_wheel_mtime = max(old_mtime + 2, new_wheel.stat().st_mtime)
    import os

    os.utime(new_wheel, (new_wheel_mtime, new_wheel_mtime))
    monkeypatch.setattr("scripts.verify_release.WHEEL_DIR", wheel_dir)

    assert _latest_wheel() == new_wheel


def test_clear_release_artifacts_removes_only_chansdk_archives(tmp_path, monkeypatch):
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    old_wheel = wheel_dir / "chansdk-1.0.0-py3-none-any.whl"
    old_sdist = wheel_dir / "chansdk-1.0.0.tar.gz"
    unrelated = wheel_dir / "other-package.whl"
    for artifact in (old_wheel, old_sdist, unrelated):
        artifact.write_bytes(b"artifact")
    monkeypatch.setattr("scripts.verify_release.WHEEL_DIR", wheel_dir)

    _clear_release_artifacts()

    assert not old_wheel.exists()
    assert not old_sdist.exists()
    assert unrelated.exists()
