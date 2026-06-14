#!/usr/bin/env python3
"""PostToolUse hook: remind to run the core coverage gate after touching core or tests.

Fires AFTER Edit/Write. Non-blocking: if the edited file is under unit_converter/core/ or tests/,
it emits a reminder (exit 0 with JSON additionalContext) to run the gate before claiming done. It
never blocks and never fails the session — a reminder only (CLAUDE.md invariant 5 / UC-B04).
"""
from __future__ import annotations

import json
import re
import sys

TARGET_RX = re.compile(r"unit_converter[\\/]core[\\/]|(?:^|[\\/])tests[\\/]")
GATE_CMD = "python -m pytest --cov=unit_converter --cov-report=term-missing --cov-fail-under=90"


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    path = (data.get("tool_input", {}) or {}).get("file_path", "") or ""
    if TARGET_RX.search(path):
        # PostToolUse additionalContext is surfaced to the model without blocking.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Coverage-gate reminder: you edited '{path}'. Before claiming done, run the "
                    f"core gate and READ the result: {GATE_CMD} (core/ must be >=90% and exit 0)."
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
