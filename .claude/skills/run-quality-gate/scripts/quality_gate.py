#!/usr/bin/env python3
"""Deterministic Unit-Converter quality gate + invariant sweep.

Runs the core-scoped coverage gate and grep-checkable repo invariants, then prints a
single PASS/FAIL verdict block. Same tree -> same verdict. No network, no mutation.

Usage:
    python .claude/skills/run-quality-gate/scripts/quality_gate.py [--repo <path>]

Exit code: 0 on PASS, 1 on FAIL, 2 on harness error (repo not found / tooling missing).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def _grep(root: Path, pattern: str, subdir: str, suffixes=(".py",)) -> list[str]:
    """Return 'relpath:lineno' for each line in subdir matching pattern (regex)."""
    rx = re.compile(pattern)
    hits: list[str] = []
    base = root / subdir
    if not base.exists():
        return hits
    for path in base.rglob("*"):
        if path.is_file() and path.suffix in suffixes:
            try:
                for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{path.relative_to(root)}:{i}")
            except OSError:
                continue
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".", help="repo root (holds pyproject.toml)")
    args = ap.parse_args()
    root = Path(args.repo).resolve()

    if not (root / "pyproject.toml").exists() or not (root / "unit_converter").exists():
        print(f"HARNESS ERROR: {root} is not the Unit-Converter repo root", file=sys.stderr)
        return 2

    findings: list[str] = []

    # --- Coverage gate ---
    cov = _run(
        [sys.executable, "-m", "pytest", "--cov=unit_converter",
         "--cov-report=term-missing", "--cov-fail-under=90"],
        root,
    )
    out = cov.stdout + cov.stderr
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", out)
    core_pct = m.group(1) if m else "?"
    cov_ok = cov.returncode == 0
    if not cov_ok:
        findings.append(f"HIGH · coverage · core {core_pct}% exit {cov.returncode} · test-author")

    # --- Core purity (no GUI/transport import in core) ---
    purity = _grep(root, r"\b(PySide\d?|PyQt\d?|tkinter|fastapi|mcp|fastmcp)\b", "unit_converter/core")
    purity_ok = not purity
    if not purity_ok:
        findings.append(f"HIGH · core purity · {purity[0]} · core-dev")

    # --- Tkinter regression (no tkinter anywhere, no .pyw) ---
    tk_imports = _grep(root, r"^\s*(import|from)\s+tkinter\b", "unit_converter")
    pyw = [str(p.relative_to(root)) for p in root.rglob("*.pyw")]
    tk_ok = not tk_imports and not pyw
    if not tk_ok:
        ev = (tk_imports + pyw)[0]
        findings.append(f"HIGH · tkinter regression · {ev} · core-dev/gui-dev")

    # --- Deprecated async usage (UC-B06) ---
    async_hits = _grep(root, r"get_event_loop\(\)\.run_until_complete", "tests")
    async_ok = not async_hits
    if not async_ok:
        findings.append(f"MED · deprecated async · {async_hits[0]} · test-author")

    # --- Artifact hygiene ---
    status = _run(["git", "status", "--porcelain", "--ignored"], root)
    tracked_artifacts = [
        ln[3:] for ln in status.stdout.splitlines()
        if not ln.startswith("!!") and re.search(r"packaging/(bin|work)/|^dist/|^build/", ln[3:])
    ]
    art_ok = not tracked_artifacts
    if not art_ok:
        findings.append(f"HIGH · committed artifact · {tracked_artifacts[0]} · packaging-builder")

    # --- MCP exact tool-name assertion present (UC-B07) ---
    smoke = root / "tests" / "test_api_smoke.py"
    mcp_ok = smoke.exists() and all(
        t in smoke.read_text(encoding="utf-8", errors="ignore")
        for t in ("post_convert", "get_magnitudes")
    )
    if not mcp_ok:
        findings.append("MED · MCP tool-name assertion missing · tests/test_api_smoke.py · test-author")

    overall = cov_ok and purity_ok and tk_ok and async_ok and art_ok and mcp_ok

    print(f"QUALITY GATE: {'PASS' if overall else 'FAIL'}")
    print(f"- Coverage: core {core_pct}% (exit {cov.returncode})")
    print(f"- Core purity (no GUI/transport import in core): {'OK' if purity_ok else 'VIOLATION ' + purity[0]}")
    print(f"- Tkinter regression (no tkinter/.pyw): {'OK' if tk_ok else 'VIOLATION ' + (tk_imports + pyw)[0]}")
    print(f"- Async (no get_event_loop().run_until_complete): {'OK' if async_ok else 'VIOLATION ' + async_hits[0]}")
    print(f"- Artifacts (build dirs ignored, tree clean): {'OK' if art_ok else 'ISSUE ' + tracked_artifacts[0]}")
    print(f"- MCP tool-name assertion present: {'OK' if mcp_ok else 'MISSING'}")
    print("Findings: " + ("; ".join(findings) if findings else "none"))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
