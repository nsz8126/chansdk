"""Run the chansdk release gate and write a machine-readable report."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GRAY_PROBE = ROOT / "scripts" / "gray_probe.py"
DOCS_VERIFY = ROOT / "scripts" / "verify_docs.py"
WHEEL_DIR = ROOT / "dist"
REPORT_DIR = ROOT / "build" / "release"
PYPROJECT = ROOT / "pyproject.toml"


def _tail(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def _read_project_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', text)
    if match is None:
        raise ValueError("project version is missing from pyproject.toml")
    return match.group(1)


def _version_check() -> Dict:
    started = time.perf_counter()
    try:
        expected = _read_project_version()
        import chan

        actual = chan.__version__
        passed = expected == actual
        result = {
            "name": "version_consistency",
            "status": "PASS" if passed else "FAIL",
            "returncode": 0 if passed else 1,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "project_version": expected,
            "package_version": actual,
        }
        if not passed:
            result["error"] = "pyproject.toml and chan.__version__ differ"
        return result
    except Exception as exc:
        return {
            "name": "version_consistency",
            "status": "FAIL",
            "returncode": 1,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _run_step(name: str, command: Sequence[str], cwd: Path = ROOT) -> Dict:
    started = time.perf_counter()
    env = None
    if name == "pytest":
        env = os.environ.copy()
        # Do not let unrelated globally installed pytest plugins affect the
        # release gate or mask project test results.
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return {
        "name": name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _latest_artifact(pattern: str) -> Optional[Path]:
    artifacts = list(WHEEL_DIR.glob(pattern))
    return max(artifacts, key=lambda path: path.stat().st_mtime) if artifacts else None


def _latest_wheel() -> Optional[Path]:
    return _latest_artifact("chansdk-*.whl")


def _latest_sdist() -> Optional[Path]:
    return _latest_artifact("chansdk-*.tar.gz")


def _clear_release_artifacts() -> None:
    """Remove prior chansdk archives so checks only inspect this run."""
    for pattern in ("chansdk-*.whl", "chansdk-*.tar.gz"):
        for artifact in WHEEL_DIR.glob(pattern):
            artifact.unlink()


def _run_wheel_import(wheel: Path) -> Dict:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="chansdk-release-wheel-") as temp_dir:
        target = Path(temp_dir)
        install = _run_step(
            "wheel_install",
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(target),
                str(wheel),
            ],
        )
        if install["status"] != "PASS":
            install["name"] = "wheel_import"
            install["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            return install

        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [
                sys.executable,
                "-S",
                "-c",
                (
                    f"import sys; sys.path.insert(0, {str(target)!r}); "
                    "import chan; "
                    "import chan.data.cache_api; "
                    "import chan.data.csv_api; "
                    "import chan.data.pytdxdata_api; "
                    "import chan.data.tdx_python_api; "
                    "print(chan.__file__)"
                ),
            ],
            cwd=str(target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return {
            "name": "wheel_import",
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "returncode": completed.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
            "wheel": str(wheel),
        }


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument("--begin", default="2024-01-01")
    parser.add_argument("--end", default="2024-01-16")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--pytdx-timeout", type=float, default=2.0)
    parser.add_argument("--report-out", type=Path, default=REPORT_DIR / "release_report.json")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    gray_report = args.report_out.parent / "gray_probe.json"

    steps: List[Dict] = []
    steps.append(_version_check())
    steps.append(
        _run_step(
            "pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--disable-warnings",
                "--maxfail=30",
                "-rxX",
            ],
        )
    )
    steps.append(
        _run_step(
            "compileall",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "chan",
                "tests",
                "scripts",
            ],
        )
    )
    steps.append(
        _run_step(
            "docs_verify",
            [
                sys.executable,
                str(DOCS_VERIFY),
                "--run-marked",
                "--json-out",
                str(args.report_out.parent / "docs_report.json"),
            ],
        )
    )

    gray_command = [
        sys.executable,
        str(GRAY_PROBE),
        "--begin",
        args.begin,
        "--end",
        args.end,
        "--repeat",
        str(args.repeat),
        "--json-out",
        str(gray_report),
    ]
    if args.include_external:
        gray_command.extend(
            [
                "--include-external",
                "--pytdx-timeout",
                str(args.pytdx_timeout),
            ]
        )
    steps.append(_run_step("gray_probe", gray_command))

    WHEEL_DIR.mkdir(parents=True, exist_ok=True)
    _clear_release_artifacts()
    steps.append(
        _run_step(
            "wheel_build",
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--wheel-dir",
                str(WHEEL_DIR),
            ],
        )
    )
    steps.append(
        _run_step(
            "sdist_build",
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                "--outdir",
                str(WHEEL_DIR),
                str(ROOT),
            ],
            cwd=ROOT.parent,
        )
    )

    wheel_build_ok = steps[-2]["status"] == "PASS"
    sdist_build_ok = steps[-1]["status"] == "PASS"
    wheel = _latest_wheel() if wheel_build_ok else None
    if wheel is None:
        steps.append(
            {
                "name": "wheel_import",
                "status": "FAIL",
                "returncode": 1,
                "elapsed_ms": 0.0,
                "error": "no wheel was produced",
            }
        )
    else:
        steps.append(_run_wheel_import(wheel))

    sdist = _latest_sdist() if sdist_build_ok else None
    if sdist is None:
        steps.append(
            {
                "name": "sdist_check",
                "status": "FAIL",
                "returncode": 1,
                "elapsed_ms": 0.0,
                "error": "no source distribution was produced",
            }
        )
    else:
        project_version = _read_project_version()
        expected_name = f"chansdk-{project_version}.tar.gz"
        steps.append(
            {
                "name": "sdist_check",
                "status": "PASS" if sdist.name == expected_name else "FAIL",
                "returncode": 0 if sdist.name == expected_name else 1,
                "elapsed_ms": 0.0,
                "sdist": str(sdist),
                "expected_name": expected_name,
            }
        )

    failed = [step for step in steps if step["status"] != "PASS"]
    payload = {
        "scope": "chansdk release gate",
        "status": "FAIL" if failed else "PASS",
        "version": _read_project_version(),
        "python": sys.version,
        "root": str(ROOT),
        "include_external": args.include_external,
        "gray_report": str(gray_report),
        "steps": steps,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    args.report_out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
