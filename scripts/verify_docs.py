"""Compile README Python blocks and run explicitly marked offline examples."""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
README = ROOT / "README.md"


@dataclass
class PythonBlock:
    index: int
    start_line: int
    code: str

    @property
    def marker(self) -> Optional[str]:
        for line in self.code.splitlines():
            stripped = line.strip()
            if stripped.startswith("# docs:"):
                return stripped.split(":", 1)[1].strip()
        return None


def extract_python_blocks(text: str) -> List[PythonBlock]:
    lines = text.splitlines()
    blocks = []
    in_block = False
    start_line = 0
    current = []
    index = 0

    for line_number, line in enumerate(lines, start=1):
        if not in_block and line.strip().lower() in {"```python", "```py"}:
            in_block = True
            start_line = line_number + 1
            current = []
            continue
        if in_block and line.strip() == "```":
            blocks.append(PythonBlock(index, start_line, "\n".join(current) + "\n"))
            index += 1
            in_block = False
            continue
        if in_block:
            current.append(line)

    if in_block:
        raise ValueError("unterminated Python code block in README")
    return blocks


def _compile_block(block: PythonBlock) -> Dict:
    if block.marker == "reference":
        return {
            "index": block.index,
            "start_line": block.start_line,
            "marker": block.marker,
            "status": "PASS",
            "check": "skip-reference",
        }

    try:
        compile(block.code, f"README.md:{block.start_line}", "exec")
        return {
            "index": block.index,
            "start_line": block.start_line,
            "marker": block.marker,
            "status": "PASS",
            "check": "compile",
        }
    except SyntaxError as exc:
        return {
            "index": block.index,
            "start_line": block.start_line,
            "marker": block.marker,
            "status": "FAIL",
            "check": "compile",
            "error": f"{exc.msg} at line {exc.lineno}",
        }


def _run_block(block: PythonBlock, timeout: float) -> Dict:
    started = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            [sys.executable, "-c", block.code],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "FAIL",
            "check": "run",
            "error": f"timeout after {timeout}s",
        }

    result = {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "check": "run",
        "returncode": completed.returncode,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    if completed.stdout:
        result["stdout_tail"] = completed.stdout[-1000:]
    if completed.stderr:
        result["stderr_tail"] = completed.stderr[-1000:]
    return result


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=README)
    parser.add_argument("--run-marked", action="store_true")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json-out", type=Path)
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")

    readme_path = args.readme.resolve()
    blocks = extract_python_blocks(readme_path.read_text(encoding="utf-8"))
    results = [_compile_block(block) for block in blocks]

    if args.run_marked:
        for block, result in zip(blocks, results):
            if result["status"] == "PASS" and block.marker == "run":
                result.update(_run_block(block, args.timeout))

    failed = [result for result in results if result["status"] != "PASS"]
    payload = {
        "scope": "chansdk documentation verification",
        "readme": str(readme_path),
        "block_count": len(blocks),
        "run_marked": args.run_marked,
        "status": "FAIL" if failed else "PASS",
        "results": results,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    console_encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded + "\n", encoding="utf-8")
    print(console_encoded)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
