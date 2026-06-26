---
name: expose-op
description: >
  Threads a core function (or a new parameter) through the Unit-Converter access layer end-to-end:
  core → shared service.py → FastAPI route in rest.py (with Pydantic validation + error-code mapping)
  → the auto-derived FastMCP tool → contract tests, keeping one core behind both transports. Use this
  skill when asked to "expose <op> via the API", "add a param to the API", "thread <fn> through
  REST/MCP", or to surface a core capability to agents. Pairs with the access-dev agent. A
  state-changing/network op is GATED on explicit re-approval.
version: 0.1.0
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity
    - P4 — Consistency
    - P5 — Context Budget Discipline
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P8 — Principles Inheritance
    - P9 — Role Separation
    - P10 — Exit-Status Determinism
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
---
# Expose Op

Procedural workflow to surface a core capability through the dual REST + MCP access layer over one shared service, with validation, error mapping, and contract tests.

## Workflow

### Step 1: Confirm the core capability exists
Read the core function/parameter in `unit_converter/core/*` you are exposing. If it does not exist yet, STOP — that is a core-dev change first; this skill only threads an existing core capability.

### Step 2: Classify the op surface — GATE check
Determine if the op is READ-only or STATE-CHANGING/network. A state-changing or network-touching endpoint (write, refresh, delete) expands the access surface and is GATED: require explicit F4 tool-count + access-layer-safety re-approval before adding it (ai-execution-discipline Rule 4). If gated and unapproved, stop and request approval.

### Step 3: Thread through the shared service
Add/extend the function in `unit_converter/api/service.py` so it delegates to the core. All transport-shared logic lives here — never fork it into `rest.py` or `mcp_server.py` (CLAUDE.md invariant 3).

### Step 4: Add the FastAPI route + validation + error mapping
In `rest.py`: define the route with an explicit `operation_id` (this becomes the MCP tool name), a Pydantic request model that validates inputs at the boundary, and error mapping — core `ValueError`/`IncompatibleUnitsError` → HTTP 422 via `_value_error_to_422`; unknown currency → 404; upstream unavailable → 503. No core error may escape as a 500.

### Step 5: Confirm the derived MCP tool
The MCP tool name is derived from the FastAPI `operation_id` by `FastMCP.from_fastapi` in `mcp_server.py` — you do not hand-write the tool. Confirm the derived name matches the intended contract (e.g. `post_convert`, `get_units`). If you changed an operation_id, you changed a tool name AND the operator-agent/docs contract.

### Step 6: Add contract tests
In `tests/test_api_routes.py` / `test_service_validation.py` / `test_api_smoke.py`: assert the route status codes (success + each mapped error), the boundary validation rejections, and the EXACT MCP tool-name set (UC-B07) — fail if the derived set drifts. Async via `asyncio.run`.

### Step 7: Update the contract docs + verify
Update `docs/agent-operating-doc.md` (16-op table, I/O, error table), `agent-access.md`, and the operator agent's op table so the documented contract matches (route to docs-writer or do it inline). Run the API tests, READ the output, report status codes, the tool-name set, and an acceptance checklist.

## Output Format

```
EXPOSE OP: <op/param> via REST+MCP
- Surface: read-only | state-changing (GATE: approved? yes/no)
- service.py: <fn/param threaded>
- rest.py: route <method path> operation_id=<id>, validation <model>, errors <codes mapped>
- MCP tool (derived): <name>
- Tests: <route status, validation, exact tool-name set>
- Docs contract updated: <files>
- Checklist: <criterion: met/NOT met + evidence>
```

## Examples

### Example 1
**Input:** "Thread sig_figs through the convert API (UC-I01)."
**Output:**
```
EXPOSE OP: sig_figs param via REST+MCP
- Surface: read-only (no gate)
- service.py: convert(...) gains sig_figs pass-through to core._round_sig_figs
- rest.py: POST /convert operation_id=post_convert, Pydantic field sig_figs:int>0, ValueError→422
- MCP tool (derived): post_convert (unchanged name; new param exposed)
- Tests: route asserts rounded result + unchanged default; validation rejects sig_figs<=0; exact tool set
- Docs contract updated: agent-operating-doc.md, agent-access.md, unit-conversion-operator.md
- Checklist: accepts/validates sig_figs ✓; default unchanged ✓; exact tool set ✓
```

## Self-Containment Index

This skill package contains everything needed for its complete usage:
- SKILL.md (this file): workflow, output format, example

External dependencies (must be available in the execution environment):
- Python 3.11+ with the repo `[api]` and `[dev]` extras (fastmcp, fastapi, pytest) installed.

## Sources
- `unit_converter/api/{service,rest,mcp_server}.py` (shared service, routes, `_value_error_to_422`, `from_fastapi` tool derivation), `core/converter.py`.
- `CLAUDE.md` (invariant 3), `docs/BACKLOG.md` (UC-I01, UC-I02, gated UC-I03/UC-I05, UC-B07), `docs/agent-operating-doc.md` (16-op contract, error table).
- `.claude/instructions/ai-execution-discipline.md` (gate / stop-and-confirm).
- references/claude.md §SKILL: frontmatter, description rules, body structure.
- Engineering disciplines (R17) per `repo-enhancer/orchestrator.md` CONVENTIONS.
