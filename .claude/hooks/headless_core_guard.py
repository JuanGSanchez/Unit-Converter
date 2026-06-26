#!/usr/bin/env python3
"""PreToolUse hook: keep unit_converter/core/* headless and pure (CLAUDE.md invariant 1).

Fires on Edit/Write. Reads the Claude Code hook JSON from stdin, inspects the tool input, and
BLOCKS (exit 2) if the new content for a file under unit_converter/core/ introduces a GUI or
transport import (PySide/PyQt/tkinter/fastapi/mcp/fastmcp). Otherwise exits 0 (allow).

Non-fatal on its own errors: any parse/IO failure exits 0 so the hook never wedges the session.
Block protocol: exit code 2 + reason on stderr (Claude Code feeds stderr back to the model).

## Principles Applied
P2 Full Determinism | P8 Principles Inheritance | P9 Role Separation (enforces the headless-core
boundary; harness-level guard for CLAUDE.md invariant 1 so only core-dev changes core) |
P11 Programmatic Determinism (this hook IS the deterministic enforcement mechanism).
"""
from __future__ import annotations

import json
import re
import sys

CORE_RX = re.compile(r"unit_converter[\\/]core[\\/]")
FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(PySide\d?|PyQt\d?|tkinter|fastapi|fastmcp|mcp)\b",
    re.MULTILINE,
)


def _candidate_text(tool_input: dict) -> str:
    # Write: full content; Edit: the replacement; MultiEdit: all replacements.
    parts = [tool_input.get("content", ""), tool_input.get("new_string", "")]
    for e in tool_input.get("edits", []) or []:
        parts.append(e.get("new_string", ""))
    return "\n".join(p for p in parts if p)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # never wedge the session on a parse error
    tool_input = data.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""
    if not CORE_RX.search(path):
        return 0
    m = FORBIDDEN_IMPORT.search(_candidate_text(tool_input))
    if m:
        sys.stderr.write(
            f"BLOCKED (headless-core-guard): '{m.group(1)}' import into core file '{path}'. "
            "unit_converter/core/* must stay headless and stdlib-pure (CLAUDE.md invariant 1). "
            "Put GUI logic in unit_converter/gui/ (gui-dev) or transport in unit_converter/api/ (access-dev)."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
