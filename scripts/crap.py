"""CRAP gate — combines cyclomatic complexity with line coverage per function.

    CRAP(fn) = CC**2 * (1 - coverage)**3 + CC

Runs pytest under coverage, then per function scores complexity-vs-coverage.
Exits 1 if any function exceeds CRAP_GATE.

Usage:
    uv run python scripts/crap.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from radon.complexity import cc_visit

CRAP_GATE = 15  # fail-the-gate threshold; tighten over time
SOURCE_DIRS = ["moderation", "scripts"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_JSON = PROJECT_ROOT / "coverage.json"


@dataclass
class FnReport:
    file: str
    name: str
    cc: int
    coverage: float
    crap: float


def _crap(cc: int, coverage: float) -> float:
    return cc * cc * (1 - coverage) ** 3 + cc


def _run(args: list[str]) -> int:
    """Run a python -m subcommand from PROJECT_ROOT. Returns exit code."""
    proc = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    return proc.returncode


def _load_coverage() -> dict:
    """Run pytest under coverage and return the parsed coverage.json."""
    _run(["coverage", "run", "-m", "pytest", "-q"])
    rc = _run(["coverage", "json", "-o", str(COVERAGE_JSON), "--quiet"])
    if rc != 0 or not COVERAGE_JSON.exists():
        sys.exit("coverage failed to produce a JSON report — is the `coverage` package installed?")
    with COVERAGE_JSON.open() as f:
        return json.load(f)


def _fn_coverage(start: int, end: int, executed: set[int], missing: set[int]) -> float:
    in_range_exec = sum(1 for line in executed if start <= line <= end)
    in_range_miss = sum(1 for line in missing if start <= line <= end)
    total = in_range_exec + in_range_miss
    return 1.0 if total == 0 else in_range_exec / total


def _collect(cov: dict) -> list[FnReport]:
    out: list[FnReport] = []
    for src_dir in SOURCE_DIRS:
        for path in (PROJECT_ROOT / src_dir).rglob("*.py"):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            file_data = cov.get("files", {}).get(rel)
            executed = set(file_data["executed_lines"]) if file_data else set()
            missing = set(file_data["missing_lines"]) if file_data else set()
            try:
                source = path.read_text(encoding="utf-8")
                blocks = cc_visit(source)
            except (SyntaxError, OSError):
                continue
            for b in blocks:
                classname = getattr(b, "classname", None)
                name = f"{classname}.{b.name}" if classname else b.name
                cov_frac = _fn_coverage(b.lineno, b.endline, executed, missing)
                out.append(
                    FnReport(
                        file=rel,
                        name=name,
                        cc=b.complexity,
                        coverage=cov_frac,
                        crap=_crap(b.complexity, cov_frac),
                    )
                )
    return out


def _render(reports: list[FnReport]) -> None:
    reports.sort(key=lambda r: r.crap, reverse=True)
    print(f"{'function':<72} {'CRAP':>6}  {'CC':>3}  {'cov':>5}")
    print("-" * 92)
    shown = 0
    for r in reports:
        if r.crap < 5 and r.crap < CRAP_GATE:
            continue
        if r.crap > CRAP_GATE:
            marker = " FAIL"
        elif r.crap > 8:
            marker = " risky"
        else:
            marker = ""
        label = f"{r.file}::{r.name}"
        print(f"{label:<72} {r.crap:>6.2f}  {r.cc:>3}  {r.coverage:>5.0%}{marker}")
        shown += 1
    if shown == 0:
        print("(no functions above CRAP 5 — clean run)")


def main() -> int:
    cov = _load_coverage()
    reports = _collect(cov)
    _render(reports)
    failures = [r for r in reports if r.crap > CRAP_GATE]
    print()
    if failures:
        print(f"CRAP gate FAILED: {len(failures)} function(s) above {CRAP_GATE}")
        return 1
    print(f"CRAP gate passed (gate = {CRAP_GATE}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
