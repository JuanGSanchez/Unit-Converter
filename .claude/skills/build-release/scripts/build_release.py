#!/usr/bin/env python3
"""Deterministic Unit-Converter build + verify runner.

Builds the wheel (and optionally the PyInstaller executable), verifies install/import,
confirms the spec bundles the data file, and checks the tree stays clean. Reports a
PASS/FAIL block. No source mutation; the only writes are into build output dirs (which
must be git-ignored per UC-B02).

Usage:
    python .claude/skills/build-release/scripts/build_release.py [--repo <path>] [--mode wheel|exe|all]

Exit code: 0 on PASS, 1 on FAIL, 2 on harness error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--mode", choices=["wheel", "exe", "all"], default="wheel")
    args = ap.parse_args()
    root = Path(args.repo).resolve()

    pyproject = root / "pyproject.toml"
    if not pyproject.exists() or not (root / "unit_converter").exists():
        print(f"HARNESS ERROR: {root} is not the Unit-Converter repo root", file=sys.stderr)
        return 2

    findings: list[str] = []

    # --- Backend check (UC-B01) ---
    pp = pyproject.read_text(encoding="utf-8")
    backend_ok = 'build-backend = "setuptools.build_meta"' in pp
    if not backend_ok:
        findings.append("HIGH · backend · build-backend != setuptools.build_meta · packaging-builder")
        print("BUILD RELEASE: FAIL")
        print("- Backend valid (setuptools.build_meta): WRONG")
        print("Findings: " + "; ".join(findings))
        return 1

    wheel_ok = True
    exe_line = "skipped"

    # --- Wheel build + install + import ---
    if args.mode in ("wheel", "all"):
        build = _run([sys.executable, "-m", "build"], root)
        if build.returncode != 0:
            wheel_ok = False
            findings.append("HIGH · wheel build · python -m build failed · packaging-builder")
        else:
            wheels = sorted((root / "dist").glob("*.whl"))
            if not wheels:
                wheel_ok = False
                findings.append("HIGH · wheel build · no .whl produced · packaging-builder")
            else:
                with tempfile.TemporaryDirectory() as td:
                    inst = _run([sys.executable, "-m", "pip", "install", "--target", td, str(wheels[-1])], root)
                    imp = _run([sys.executable, "-c", f"import sys; sys.path.insert(0, r'{td}'); import unit_converter"], root)
                    if inst.returncode != 0 or imp.returncode != 0:
                        wheel_ok = False
                        findings.append("HIGH · install/import · wheel not importable · packaging-builder")

    # --- Executable build + data-file bundling ---
    if args.mode in ("exe", "all"):
        exe = _run([sys.executable, "packaging/build.py"], root)
        if exe.returncode != 0:
            exe_line = "FAIL (build.py exit != 0)"
            findings.append("HIGH · exe build · packaging/build.py failed · packaging-builder")
        else:
            spec = (root / "packaging" / "UConverter.spec").read_text(encoding="utf-8", errors="ignore")
            data_bundled = "magnitudes.toml" in spec
            exe_line = "OK (data file bundled)" if data_bundled else "FAIL (spec missing magnitudes.toml)"
            if not data_bundled:
                findings.append("HIGH · exe data · spec does not bundle magnitudes.toml · packaging-builder")

    # --- Clean-tree hygiene (UC-B02) ---
    status = _run(["git", "status", "--porcelain"], root)
    tracked_new = [
        ln[3:] for ln in status.stdout.splitlines()
        if re.search(r"packaging/(bin|work)/|^dist/|^build/", ln[3:]) and not ln.startswith("!!")
    ]
    clean_ok = not tracked_new
    if not clean_ok:
        findings.append(f"HIGH · clean tree · tracked artifact {tracked_new[0]} · packaging-builder")

    overall = backend_ok and wheel_ok and clean_ok and "FAIL" not in exe_line

    print(f"BUILD RELEASE: {'PASS' if overall else 'FAIL'}")
    print("- Backend valid (setuptools.build_meta): OK")
    print(f"- Wheel/sdist build + install + import: {'OK (exit 0)' if wheel_ok else 'FAIL'}")
    print(f"- Executable build (if requested): {exe_line}")
    print(f"- Clean tree (no tracked artifacts): {'OK' if clean_ok else 'ISSUE ' + tracked_new[0]}")
    print("Findings: " + ("; ".join(findings) if findings else "none"))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
