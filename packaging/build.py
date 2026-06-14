#!/usr/bin/env python3
"""
build.py — Cross-platform reproducible build runner for UConverter.

Equivalent to build_windows.bat / build_posix.sh but callable with any Python
interpreter on any OS — useful for CI pipelines and environments where .bat or
.sh are inconvenient.

Usage
-----
    # From the repo root:
    python packaging/build.py

    # With explicit options:
    python packaging/build.py --log-level INFO --no-icon-convert

Prerequisites
-------------
    pip install "pyinstaller~=6.20.0" "PySide6~=6.11.1"
    pip install Pillow   # only needed for the automatic PNG->ICO step

Output
------
    packaging/bin/UConverter/UConverter.exe   (Windows)
    packaging/bin/UConverter/UConverter       (Linux)
    packaging/bin/UConverter.app/             (macOS)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DIST_DIR = Path(__file__).parent          # dist/
REPO_ROOT = DIST_DIR.parent              # repo root
SPEC = DIST_DIR / "UConverter.spec"
BIN_DIR = DIST_DIR / "bin"
WORK_DIR = DIST_DIR / "work"
PNG_SRC = REPO_ROOT / "Logo UC.png"
ICO_DEST = REPO_ROOT / "Logo UC.ico"


def ensure_ico(skip: bool = False) -> bool:
    """Try to produce Logo UC.ico from Logo UC.png.  Returns True if .ico exists."""
    if ICO_DEST.exists():
        return True
    if skip:
        print("[build] Skipping PNG->ICO conversion (--no-icon-convert).")
        return False
    print("[build] Logo UC.ico not found — running scripts/png_to_ico.py …")
    result = subprocess.run(
        [sys.executable, str(DIST_DIR / "scripts" / "png_to_ico.py"),
         str(PNG_SRC), str(ICO_DEST)],
        check=False,
    )
    if result.returncode != 0:
        print("[build] WARNING: PNG->ICO conversion failed. Building without icon.")
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the UConverter PyInstaller bundle.")
    ap.add_argument("--log-level", default="WARN",
                    choices=["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
                    help="PyInstaller log level (default: WARN)")
    ap.add_argument("--no-icon-convert", action="store_true",
                    help="Skip automatic PNG->ICO conversion.")
    args = ap.parse_args()

    print(f"[build] Repo root : {REPO_ROOT}")
    print(f"[build] Spec file : {SPEC}")

    ensure_ico(skip=args.no_icon_convert)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--distpath", str(BIN_DIR),
        "--workpath", str(WORK_DIR),
        "--log-level", args.log_level,
    ]
    print(f"[build] Running: {' '.join(cmd)}")

    # Run from repo root so relative datas paths in the spec resolve correctly
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    if result.returncode != 0:
        print("[build] ERROR: PyInstaller exited with an error.", file=sys.stderr)
        sys.exit(1)

    exe = BIN_DIR / "UConverter" / ("UConverter.exe" if sys.platform == "win32" else "UConverter")
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\n[build] Build complete.")
        print(f"[build] Executable : {exe}  ({size_mb:.1f} MB)")
    else:
        print(f"\n[build] Build complete. Bundle at: {BIN_DIR / 'UConverter'}")


if __name__ == "__main__":
    main()
