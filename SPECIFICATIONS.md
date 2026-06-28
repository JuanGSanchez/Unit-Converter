# Post-review remediation specifications (2026-06-28)

Outcome of the critical pre-merge review of branch `enhancement/unit-converter-20260625` (PR #3 →
`main`). The original 22-spec product backlog was delivered and is archived in
`SPECIFICATIONS-archive-20260625.md`; this document supersedes it as the active work list.

The review found the branch **substantially merge-ready**: the quality gate is green (822 passed,
92.24 % core coverage ≥ 90 % gate), the working tree is clean, no stray/temporary files are
committed (every `subagent-report-*` / `claude-checkpoint-*` file is untracked and git-ignored), no
build artifacts or secrets are tracked, and the branch is 0 commits behind `main` (a clean
fast-forward merge). The two product invariants (UI-independent core; cross-adapter accuracy) hold.

Only three remediation items remain, all narrow. Each is concrete, acceptance-testable, and
prioritized. **Where the review found no real issue, that is stated explicitly** (§ "Areas reviewed
with no remediation required") rather than inventing work.

Priorities: **P1** = blocks merge / correctness; **P2** = consistency & contract hygiene that should
land before merge; **P3** = documentation/clarity follow-up, non-blocking.

---

## SPEC-R1 — Document the 16-tool MCP/REST surface as an accepted expansion of SPEC-04
- **Priority:** P2
- **Origin:** Phase-A finding R1 / carried follow-up (c).
- **Problem:** Original SPEC-04 acceptance criteria literally require "exactly three tools"
  (`list_magnitudes`, `list_units`, `convert`) and "Tool count stays minimal (3)". The shipped
  access layer instead exposes **16 operations/tools** (discovery, convert, compound, currency,
  history/favorites, custom units). This is a deliberate, accepted capability expansion — **not** a
  regression to be undone — but the deviation from SPEC-04's written criteria is nowhere recorded as
  an accepted decision. The docs (`docs/agent-access.md`, `docs/agent-operating-doc.md`,
  `docs/usage-guide.md`) state "16 operations" as fact without reconciling it against the spec.
- **Scope:**
  - Add an explicit rationale note — in the archived spec's SPEC-04 entry (as a "superseded by
    SPEC-R1" pointer) and in `docs/agent-access.md` — explaining that the 3-tool minimum was
    intentionally expanded to 16 to cover compound parsing, currency, history/favorites, and custom
    units, while preserving the F4 "small, purposeful toolset" intent (no redundant tools; each tool
    maps 1:1 to a curated FastAPI operation; the single shared core invariant is unbroken).
  - Confirm the surface is exactly the 16 named tools and is locked by an exact-match test.
- **Acceptance criteria:**
  - `docs/agent-access.md` contains a short, dated rationale paragraph stating the 16-tool surface is
    an accepted expansion of SPEC-04's original 3-tool scope, naming the added capability groups.
  - The archived `SPECIFICATIONS-archive-20260625.md` SPEC-04 entry carries a one-line note that its
    "exactly three" criterion is superseded by SPEC-R1.
  - `tests/test_api_routes.py` asserts the MCP tool set equals exactly `_EXPECTED_TOOL_NAMES_16`
    (already present — verify it remains the authoritative lock; no count regression to 3).
  - Quality gate stays green.

## SPEC-R2 — Make the batch dialog's save/copy errors non-blocking (SPEC-19 consistency)
- **Priority:** P2
- **Origin:** Phase-A finding R2 / carried follow-up (b).
- **Problem:** `_BatchDialog._on_save` surfaces a CSV-write failure with a modal
  `QMessageBox.warning`. SPEC-19 mandates that user-facing errors use "a non-blocking, themed
  surface (not a popup window — consistent with SPEC-01's centralized approach)". A modal dialog for
  a non-fatal file-write failure is inconsistent with that contract and with the main window, which
  reports conversion failures non-blockingly (result label → `"error"`).
- **Scope:**
  - Add a single inline, themed status label to `_BatchDialog` (styled from the dialog's `colors`,
    consistent with the active theme; no per-widget style that fights the central QSS).
  - Route the CSV **save** failure (current `OSError` path) and, for symmetry, a **save/copy success
    confirmation** through this inline label instead of a modal popup. The label clears on the next
    action.
  - Keep the change minimal: no new error framework — reuse the existing logging call; only the
    user-facing surface changes from modal to inline.
- **Acceptance criteria:**
  - `_BatchDialog._on_save` no longer calls `QMessageBox` on the write-failure path; the failure
    message appears in the inline status label and the original exception is still logged at
    `ERROR`.
  - A test drives `_on_save` with a write that raises `OSError` (e.g. an unwritable path or a
    patched `open`) and asserts the inline label shows a non-empty error message and that no modal
    dialog is invoked (e.g. `QMessageBox.warning` is patched and asserted not-called).
  - The inline label's colors derive from the dialog's theme `colors` (no hard-coded style).
  - Quality gate stays green; coverage does not regress below the 90 % gate.

## SPEC-R3 — Document the SPEC-19 modal-dialog policy (remaining intentional QMessageBox uses)
- **Priority:** P3
- **Origin:** Phase-A finding R3.
- **Problem:** After SPEC-R2, the GUI still uses modal `QMessageBox` in four places that are
  *intentional* but undocumented, so a future reviewer could read them as SPEC-19 regressions:
  (1) fatal magnitude-database load failure → message then `SystemExit` (no usable app to host an
  inline surface); (2) blocking input validation in the add-custom-unit dialog (the user must
  correct input before the action can proceed); (3) the "About" informational dialog; (4) the
  "custom unit added" success confirmation.
- **Scope:** Record the policy — non-blocking inline surfaces are the default for transient/runtime
  errors (conversions, batch save); modal dialogs are reserved for (a) fatal startup failures that
  terminate the app, (b) explicit blocking input-validation gates, and (c) About/explicit
  acknowledgement dialogs. Place this note where SPEC-19 behavior is documented (`docs/usage-guide.md`
  error-handling section or `docs/agent-operating-doc.md`).
- **Acceptance criteria:**
  - A short, dated "Error-surface policy" note exists in the docs naming the inline-default rule and
    the three modal exceptions, so the surviving `QMessageBox` calls are documented as intentional.
  - No code change required beyond SPEC-R2; this is documentation only.
  - Quality gate stays green.

---

## Areas reviewed with no remediation required

These were scrutinized and found correct, complete, and tested — **no work is warranted**:

- **SPEC-01 (centralized widget-info):** `info_registry.py` is the sole info surface. No tracked
  `description.py`/`DescriptionLabel`, no inline `setToolTip(` literal, no `_tip()` helper, no
  `attach_description` import — all enforced by guard tests in `tests/test_info_registry.py`
  (`test_description_py_deleted`, `test_no_inline_settoolTip_literal`,
  `test_no_inline_tip_helper_in_main_window`, `test_no_attach_description_import`) plus tooltip ==
  accessibleDescription coverage tests. **Headline follow-up (a) is fully closed.**
- **SPEC-02 / SPEC-16 (UI-independent core, accuracy):** core imports headless; no GUI/Qt in
  `core/`; round-trip and cross-adapter parity covered by the suite.
- **SPEC-04 surface correctness:** all 16 MCP tools are derived from curated FastAPI operations and
  locked by `_EXPECTED_TOOL_NAMES_16` (the only open item is *documenting* the count — SPEC-R1).
- **SPEC-08 / SPEC-09 (expanded magnitudes, affine):** ~20 magnitudes including affine Temperature
  (offsets) and Temperature_delta; `0 °C → 273.15 K`, `0 °C → 32 °F` tested.
- **SPEC-05 / SPEC-06 (packaging, manifest):** PEP 517 backend configured (`setuptools.build_meta`,
  `requires-python >=3.11`); PyInstaller spec tracked; build artifacts (`packaging/bin/`,
  `packaging/work/`) untracked and git-ignored.
- **SPEC-07 (test/coverage gate):** 822 tests pass; total core coverage 92.24 % ≥ 90 % gate,
  enforced in `pyproject.toml`.
- **SPEC-19 print/cleanup hygiene:** no `print(` diagnostics in the package; logging used throughout;
  no `del self`/`gc.collect()` cargo-cult cleanup. (Only the modal-vs-inline surface needs the
  SPEC-R2/R3 touch.)
- **Merge hygiene:** working tree clean; no `subagent-report-*` / `claude-checkpoint-*` / scratch
  files committed (all untracked + git-ignored); no secrets or build artifacts tracked; 0 commits
  behind `main` (clean fast-forward).

---

## Priority summary
- **P1 (0):** none — no merge-blocking correctness defects were found.
- **P2 (2):** SPEC-R1 (document 16-tool surface), SPEC-R2 (non-blocking batch errors).
- **P3 (1):** SPEC-R3 (document modal-dialog policy).
