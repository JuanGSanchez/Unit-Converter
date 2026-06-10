@echo off
REM build_windows.bat — Reproducible PyInstaller build for UConverter (Windows)
REM
REM Usage:
REM   From the repo root:   packaging\build_windows.bat
REM   Or directly:          cd packaging && build_windows.bat
REM
REM Prerequisites:
REM   pip install "pyinstaller~=6.20.0" "PySide6~=6.11.1"
REM   (optionally run  python packaging\scripts\png_to_ico.py  first for the icon)
REM
REM Output:   packaging\bin\UConverter\UConverter.exe   (one-dir bundle)

setlocal enabledelayedexpansion

REM Resolve repo root as the parent of this script's directory
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

REM Canonicalise REPO_ROOT
pushd "%REPO_ROOT%"
set "REPO_ROOT=%CD%"
popd

echo [build_windows] Repo root : %REPO_ROOT%
echo [build_windows] Spec file : %SCRIPT_DIR%UConverter.spec

REM Optional: generate .ico from Logo UC.png if it does not exist yet
if not exist "%REPO_ROOT%\Logo UC.ico" (
    echo [build_windows] Logo UC.ico not found -- running png_to_ico.py ...
    python "%SCRIPT_DIR%scripts\png_to_ico.py" "%REPO_ROOT%\Logo UC.png" "%REPO_ROOT%\Logo UC.ico"
    if errorlevel 1 (
        echo [build_windows] WARNING: PNG-to-ICO conversion failed. Building without icon.
    ) else (
        echo [build_windows] Logo UC.ico created.
    )
)

REM Run PyInstaller from the repo root so relative datas paths resolve correctly
cd /d "%REPO_ROOT%"
pyinstaller "%SCRIPT_DIR%UConverter.spec" ^
    --noconfirm ^
    --distpath "%SCRIPT_DIR%bin" ^
    --workpath "%SCRIPT_DIR%work" ^
    --log-level WARN

if errorlevel 1 (
    echo [build_windows] ERROR: PyInstaller exited with an error.
    exit /b 1
)

echo.
echo [build_windows] Build complete.
echo [build_windows] Executable : %SCRIPT_DIR%bin\UConverter\UConverter.exe
exit /b 0
