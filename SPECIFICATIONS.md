# Unit-Converter — Product Specifications

Prioritized product capability + robustness backlog for **Unit-Converter** (Python 3 / PySide6 — a
unit & magnitude converter GUI with a UI-independent conversion core). This document drives the
repo's own SDD pipeline: each spec below is a concrete, testable unit of work the pipeline will
later IMPLEMENT. It is a *product* backlog, not orchestration vocabulary.

Two invariants hold for EVERY spec and override any conflicting detail:

- **UI-independent-core invariant.** All conversion logic lives in one pure, framework-free core
  module (`core/converter.py` or equivalent). The PySide6 UI, the REST API, and the MCP server are
  all thin adapters over that single core. No conversion math may be forked, duplicated, or
  re-derived in any UI/adapter layer.
- **Conversion-accuracy invariant.** Numeric results must be correct and reproducible across all
  adapters. The same `(magnitude, value, from_unit, to_unit, orders)` request returns the identical
  value through GUI, REST, and MCP. Accuracy/precision guarantees (SPEC-16) are non-negotiable.

Priorities: **P1** = critical path / user-flagged / blocks other work; **P2** = high-value core
capability; **P3** = valuable expansion. Within this document the user-flagged centralized-popup
replacement (SPEC-01) leads. Specs are grouped by theme; each theme is ordered by priority.

> Migration note: the current code (`UConverter_UI.pyw`) is Tkinter with hand-rolled popup windows.
> The target stack is PySide6. Specs that touch the UI assume the PySide6 surface; where a port step
> is a prerequisite it is named as a dependency. The conversion core (SPEC-02) is UI-framework
> agnostic and must land first regardless.

---

## Theme A — UX / Centralized Widget-Info Pop-up

### SPEC-01 Replace cumbersome popup windows with ONE centralized widget-info component
- **Priority:** P1 (user-flagged, highest priority)
- **Motivation:** The current Unit-Converter help/info experience uses bespoke, cumbersome pop-up
  windows (Tkinter `Toplevel`-style overlays via `show_manual` / `show_menucontext`). They are
  scattered, modal-feeling, inconsistent, hover-unaware, and inaccessible. FF-Explorer is the
  reference solution: it deletes the hand-rolled overlay and uses Qt's framework-managed `QToolTip`
  singleton fed by a single help-text registry and styled in one QSS block
  (see `docs/reference-ff-widget-popup.md`). Replicate that pattern AND its mandated improvements.
- **Scope:**
  - DELETE the existing custom popup-window code paths (`show_manual`, `show_menucontext`, any
    `Toplevel`/bespoke info window). No ad-hoc, per-widget popup windows remain anywhere in the UI.
  - Introduce exactly ONE centralized info surface: Qt's `QToolTip` singleton (do NOT hand-roll a
    popup/manager class). The app instantiates no popup window; it only registers text per widget.
  - Single widget→info **registry**: all info strings as named constants / a `dict` keyed by stable
    widget ids in one module (mirroring FF's `_HELP_*` constants). No inline string literals in
    `setToolTip(...)` calls — every text comes from the registry.
  - One **coverage helper** `register_info(widget, key)` (a.k.a. `attach_info`) that, from a single
    registry lookup, sets BOTH `widget.setToolTip(text)` AND `widget.setAccessibleDescription(text)`
    (plus optional `setWhatsThis(text)`). Every interactive widget is wired through this helper.
  - **Triggers:** hover (Qt default) AND keyboard/focus reachability via accessible description /
    WhatsThis (`?` affordance), so info is available to keyboard-only and screen-reader users — not
    hover-only. Auto-dismiss on leave/timeout handled by the framework.
  - **Single theming point:** one `QToolTip { ... }` QSS rule in the theme module driven by the
    active theme (light/dark `tooltip_bg`/`tooltip_text`). No per-widget `setStyleSheet` overrides
    that fight the central style.
  - Support data-driven tooltips: where text depends on widget state (e.g. selected magnitude or
    selected order/prefix), recompute the tooltip from the registry on the relevant signal (FF's
    `currentIndexChanged → _update_*_tooltip` pattern).
- **Acceptance criteria:**
  - Grep of the codebase finds NO bespoke popup/overlay class and no surviving `Toplevel`-style
    info window; the only info surface is `QToolTip`.
  - Every interactive widget (magnitude selector, unit comboboxes, order/prefix selectors, value
    entries, swap/reset buttons, copy/clipboard controls, menu actions) has info registered via
    `register_info`; a test asserts 100% coverage by iterating registered widgets against the
    registry (no widget missing a key, no orphan keys).
  - No `setToolTip(...)` call passes an inline literal; all text resolves through the registry
    (lint/test check).
  - Each registered widget exposes a non-empty `accessibleDescription()` equal to its tooltip text;
    keyboard focus + WhatsThis surfaces the same info without a mouse.
  - Tooltip styling derives solely from the active theme; toggling light/dark restyles all tooltips
    from the one QSS block; no widget carries a conflicting inline style.
  - A state-dependent control updates its tooltip when its selection changes (verified by a UI/unit
    test on the slot).
- **Notes/Dependencies:** Reference: `docs/reference-ff-widget-popup.md` §2–§6 (replicate the
  registry + single-theming + coverage-helper pattern AND close its named gaps: inconsistent
  registry, no accessibility, no coverage enforcement, local style overrides). Depends on the
  PySide6 UI surface existing (Tkinter→PySide6 port). Independent of the conversion core.

---

## Theme B — Access Layer (REST + MCP over the shared core)

### SPEC-02 Extract the UI-independent conversion core
- **Priority:** P1 (critical path — blocks SPEC-03/04/05/07 and accuracy testing)
- **Motivation:** Conversion math is currently entangled with Tk widget state inside
  `UC_UI.__init__` / `unit_converter()` (reads `Cb_opt*`, `Lb_order*`, `DoubleVar`s directly). No
  pure function can be called without a live UI. This is the single biggest obstacle to the access
  layer and to testing.
- **Scope:** Create a pure module `core/converter.py` exposing, with type hints and docstrings:
  - `list_magnitudes() -> list[str]`
  - `list_units(magnitude: str) -> UnitsInfo` (unit names + base unit + allowed orders/prefixes)
  - `convert(magnitude, value, from_unit, to_unit, from_order='1', to_order='1') -> float`
  - The GUI is refactored to call this core only; it holds no conversion math of its own.
- **Acceptance criteria:**
  - Core module imports with zero GUI/Qt/Tk dependency (importable in a headless test process).
  - GUI conversion produces identical results to direct `convert()` calls (parity test).
  - All 9 existing magnitudes (Mass, Length, Area, Volume, Time, Energy, Power, Pressure, Data)
    are reachable through the core API.
  - No conversion arithmetic remains in any UI method (grep/structural check).
- **Notes/Dependencies:** Prerequisite for the entire access layer, packaging data-loading, and the
  test suite. Owned by feature-enhancer/refactor step; must land before Theme B/C/D complete.

### SPEC-03 REST API exposing the conversion core
- **Priority:** P2
- **Motivation:** Surface the conversion capability to non-GUI consumers and automation
  (dossier R5 dual-interface; single core, dual interface).
- **Scope:** FastAPI app over `core/converter.py` with read-only/compute endpoints:
  `GET /magnitudes`, `GET /magnitudes/{magnitude}/units`,
  `GET /convert?magnitude=&value=&from_unit=&to_unit=&from_order=&to_order=`
  (or `POST /convert` with a JSON body). Structured error responses; OpenAPI schema served.
- **Acceptance criteria:**
  - Endpoints return values identical to the core for the same inputs (parity tests).
  - Invalid magnitude/unit/order → 4xx with a structured, machine-readable error body (not a 500).
  - Numeric inputs that are non-finite / unparseable → validated 422, never a stack trace.
  - OpenAPI doc lists exactly the curated endpoints; no write/stateful routes.
  - The app imports the same core module — no duplicated conversion logic (structural check).
- **Notes/Dependencies:** Depends on SPEC-02. Pairs with SPEC-04 (shared core).

### SPEC-04 MCP server exposing the conversion core
- **Priority:** P2
- **Motivation:** Make the converter usable as agent tooling (dossier R5/F4 small, purposeful
  toolset).
- **Scope:** FastMCP server exposing exactly three tools backed by the same core:
  `list_magnitudes()`, `list_units(magnitude)`, `convert(...)`. No write/stateful tools.
- **Acceptance criteria:**
  - The three tools are discoverable and each returns values identical to the core (parity tests).
  - Tool count stays minimal (3) per F4 discipline; no redundant tools.
  - Error inputs return structured tool errors, not crashes.
  - Server and REST app share one core module (no logic fork).
- **Notes/Dependencies:** Depends on SPEC-02. Shares validation/error contract with SPEC-03.

---

## Theme C — Packaging

### SPEC-05 Cross-platform packaged executable (PyInstaller)
- **Priority:** P2
- **Motivation:** Ship a runnable GUI without a Python environment (dossier R3/F5). `.gitignore`
  already anticipates PyInstaller but nothing is wired.
- **Scope:** PyInstaller `--windowed`/`--noconsole` build producing a single-file executable;
  bundle data files (`Magnitudes.txt`, logo) via `--add-data`/`datas`; resolve all resource paths
  through a `sys._MEIPASS`-aware path helper (current `os.path.dirname(__file__)` breaks under a
  frozen bundle). Provide a `.spec` and a documented build command.
- **Acceptance criteria:**
  - Built executable launches the GUI on the target OS with no console window.
  - Data file and logo load correctly from the frozen bundle (path helper test covers both frozen
    and source-tree modes).
  - A clean build from the documented command succeeds reproducibly.
  - No hardcoded absolute paths; NumPy/Qt hidden-import hooks validated.
- **Notes/Dependencies:** Depends on a resource-path helper (shared with SPEC-18) and SPEC-06.

### SPEC-06 Dependency manifest and Python floor
- **Priority:** P2
- **Motivation:** No `requirements.txt`/`pyproject.toml` exists (dossier R2.c). Nothing is pinned;
  the gap is the *absence* of a manifest. Reproducible installs and builds need one.
- **Scope:** Author `pyproject.toml` (+ `requirements.txt`) pinning runtime deps (PySide6, NumPy or
  its stdlib replacement, FastAPI/uvicorn, FastMCP) and declaring `requires-python >=3.10` (target
  3.11). Separate dev/test extras (pytest, pytest-cov). Define a console/GUI entry point.
- **Acceptance criteria:**
  - Fresh `pip install` into a clean venv from the manifest yields a runnable app + passing tests.
  - Python floor is declared and enforced (install fails below the floor).
  - All imported third-party packages appear in the manifest; no undeclared imports (check).
  - README/code Python-version mismatch (3.10.9 vs 3.11) resolved to one declared floor.
- **Notes/Dependencies:** Underpins SPEC-05 and SPEC-07.

---

## Theme D — Testing

### SPEC-07 pytest suite meeting the coverage gate
- **Priority:** P1 (gate; unblocked by SPEC-02)
- **Motivation:** Zero tests exist; logic was untestable while entangled with Tk. After core
  extraction the conversion logic is fully unit-testable (dossier R4).
- **Scope:** `pytest` + `pytest-cov` suite targeting the core and adapters, with a coverage gate
  configured in `pyproject.toml`. GUI layer may be excluded from the coverage target; coverage is
  aimed at the core + REST/MCP adapters.
- **Acceptance criteria:**
  - `convert()` round-trip A→B→A within tolerance for all 9 (and any added) magnitudes.
  - SI-prefix order math tested; the special base-1024 `Data` path tested distinctly from base-10.
  - Affine-unit conversions (SPEC-09) tested where present (e.g. 0 °C = 32 °F = 273.15 K).
  - Malformed-data-file handling, zero/negative/inf inputs, and divide-by-zero-factor guards tested.
  - REST and MCP parity tests assert adapter results equal core results.
  - Coverage meets or exceeds the configured gate; CI-runnable command documented.
- **Notes/Dependencies:** Depends on SPEC-02; consumes contracts from SPEC-09, SPEC-16, SPEC-17,
  SPEC-18.

---

## Theme E — Feature Expansion

### SPEC-09 Correct affine (offset) vs factor units
- **Priority:** P1 (accuracy correctness — enables Temperature and any offset unit)
- **Motivation:** The current model is purely multiplicative (`val*order*factor / (order*factor)`).
  It cannot represent affine units (Celsius/Fahrenheit need an offset, not just a scale), so
  Temperature is absent and any offset unit would be silently wrong. Conversion-accuracy invariant
  demands this be modeled correctly before such units are added.
- **Scope:** Extend the core unit model to support an affine form `y = a*x + b` (factor + offset),
  with pure-factor units as the `b=0` special case. Add a Temperature magnitude (°C, °F, K, °R) as
  the reference affine case. Conversion composes via the base unit using the affine transform.
- **Acceptance criteria:**
  - 0 °C ↔ 32 °F ↔ 273.15 K and 100 °C ↔ 212 °F ↔ 373.15 K within tolerance, both directions.
  - Pure-factor magnitudes are unaffected (regression parity vs SPEC-02 baseline).
  - The data format distinguishes factor-only vs affine units unambiguously (loader-validated).
  - Round-trip A→B→A holds for affine units.
- **Notes/Dependencies:** Depends on SPEC-02; data-format change coordinated with SPEC-18.

### SPEC-13 Precision and output formatting controls
- **Priority:** P2
- **Motivation:** Current rounding uses `np.round` with fixed behavior; users need control over
  significant figures / decimal places, scientific vs plain notation, and thousands separators.
- **Scope:** Core-level formatting policy (precision, notation, separator) applied consistently by
  all adapters; a UI control to set it. Core `convert()` still returns full-precision `float`;
  formatting is a separate, pure presentation function so accuracy is never lost upstream.
- **Acceptance criteria:**
  - Selecting significant figures / decimal places changes displayed output deterministically.
  - Scientific notation toggles for very large/small magnitudes; `inf`/overflow displayed safely.
  - Formatting is a pure function unit-tested independently of `convert()`.
  - REST/MCP can request raw value and/or formatted string; raw value is always full precision.
- **Notes/Dependencies:** Depends on SPEC-02; interacts with SPEC-16 (precision guarantees) and
  SPEC-20 (locale separators).

### SPEC-15 Copy/paste and clipboard integration
- **Priority:** P2
- **Motivation:** A converter is high-frequency copy/paste; manual retyping is friction.
- **Scope:** Copy result (and optionally a full "value unit = value unit" expression) to the
  clipboard via a button/shortcut; paste a numeric value into the input with parsing/validation.
- **Acceptance criteria:**
  - Copy places the formatted result on the system clipboard (testable via Qt clipboard API).
  - Paste of a valid number populates the input; paste of garbage is rejected per SPEC-17.
  - Keyboard shortcuts (Ctrl+C on result, Ctrl+V into input) work and are documented in tooltips.
- **Notes/Dependencies:** Tooltips registered via SPEC-01; parsing via SPEC-17/SPEC-20.

### SPEC-08 Expanded unit categories and magnitudes
- **Priority:** P2
- **Motivation:** Only 9 magnitudes exist. A competitive converter covers more domains
  (Temperature, Speed/Velocity, Acceleration, Force, Angle, Frequency, Electric current/voltage/
  resistance, Fuel economy, Density, Torque, Luminance, Digital data-rate, Currency-style ratios).
- **Scope:** Add new magnitudes + units purely as DATA in the magnitude database (no code fork);
  affine ones use SPEC-09. Each addition is a data + test increment, never a logic change.
- **Acceptance criteria:**
  - Each new magnitude lists correctly via `list_magnitudes()`/`list_units()` and converts within
    tolerance against authoritative reference values.
  - Adding a magnitude requires no change to `convert()` logic (data-only, structural check).
  - Round-trip tests pass for every added magnitude.
- **Notes/Dependencies:** Depends on SPEC-02, SPEC-18 (validated loader), SPEC-09 (for affine ones).

### SPEC-14 Unit and magnitude search
- **Priority:** P3
- **Motivation:** With many units, scrolling combos is slow; users want to type to find a unit
  across all magnitudes.
- **Scope:** A search/filter field that matches unit names and aliases (and magnitude names),
  surfacing results across categories; selecting a result sets magnitude + unit.
- **Acceptance criteria:**
  - Typing a substring/alias returns matching units across all magnitudes (case/accent-insensitive).
  - Selecting a result configures the converter to that magnitude/unit.
  - Search index is built from the core's unit data (no separate hardcoded list).
- **Notes/Dependencies:** Depends on SPEC-02; benefits from unit aliases (SPEC-08 data).

### SPEC-11 Conversion history and favorites
- **Priority:** P3
- **Motivation:** Users repeat conversions; recall and one-click favorites improve flow.
- **Scope:** Session (and optionally persisted) history of recent conversions and a favorites list
  of pinned (magnitude, from_unit, to_unit) presets; UI to recall/apply them. Persistence is a UI
  concern; the core stays stateless.
- **Acceptance criteria:**
  - Performing a conversion records an entry (magnitude, inputs, result, timestamp).
  - Selecting a history/favorite entry re-applies it and reproduces the same result (accuracy
    invariant).
  - Favorites persist across restarts if persistence is enabled; the core remains stateless
    (history lives in the UI/adapter layer, not the core).
- **Notes/Dependencies:** Depends on SPEC-02; must not introduce state into the core.

### SPEC-12 Batch conversion
- **Priority:** P3
- **Motivation:** Converting many values (or one value to all units of a magnitude) at once is a
  common power-user need.
- **Scope:** Batch mode: convert a list of input values, or one value to every unit in a magnitude,
  returning a table; exportable (CSV/clipboard). Backed by repeated core calls.
- **Acceptance criteria:**
  - A list of N values converts to N results matching N individual `convert()` calls.
  - "One value → all units" produces a complete, correct table for the magnitude.
  - Results are exportable (CSV/clipboard) with the active formatting (SPEC-13).
- **Notes/Dependencies:** Depends on SPEC-02; reuses SPEC-13 formatting and SPEC-15 clipboard.

### SPEC-10 Custom and compound units
- **Priority:** P3
- **Motivation:** Advanced users want user-defined units and compound/derived units
  (e.g. km/h, kWh, kg·m/s²) without editing source.
- **Scope:** Allow defining custom units (name, magnitude, factor/offset, or a compound expression
  over existing units) via a UI/config, validated and persisted; the core treats them like any data
  unit. Optional dimensional-analysis check for compound definitions.
- **Acceptance criteria:**
  - A user-defined factor unit converts correctly and survives restart.
  - A compound unit (e.g. km/h derived from m and s) converts within tolerance to/from base units.
  - Invalid/circular/dimensionally-inconsistent definitions are rejected with a clear error.
  - Custom units are loaded through the same validated loader path (SPEC-18); no logic fork.
- **Notes/Dependencies:** Depends on SPEC-02, SPEC-09, SPEC-18. Lowest-priority feature; gate behind
  the validated loader.

---

## Theme F — Robustness

### SPEC-16 Conversion accuracy and precision guarantees
- **Priority:** P1
- **Motivation:** Accuracy is the product's core value; the invariant must be made explicit and
  defended by tests.
- **Scope:** Define and document the precision contract: `convert()` returns a full-precision
  `float`; round-trip error bound; handling of very large/small magnitudes and SI vs 1024 base.
  Eliminate accuracy-eroding patterns (premature rounding inside the math path).
- **Acceptance criteria:**
  - Round-trip A→B→A relative error ≤ a documented tolerance for all magnitudes/units.
  - Rounding occurs only at presentation (SPEC-13), never inside `convert()`.
  - Cross-adapter determinism: GUI, REST, MCP return bit-identical raw values for equal inputs.
  - Edge magnitudes (e.g. data sizes spanning many prefixes) convert without overflow/precision loss
    beyond the documented bound.
- **Notes/Dependencies:** Depends on SPEC-02; enforced by SPEC-07.

### SPEC-17 Input validation and graceful edge-input handling
- **Priority:** P1
- **Motivation:** Current handling is a bare `try/except` in `check_value`; malformed input and
  edge values (empty, non-numeric, `inf`, `NaN`, negative where invalid, zero divisor factor) are
  not robustly handled. A factor of `0` in the data file would divide by zero.
- **Scope:** Centralized input parsing/validation in the core (shared by GUI/REST/MCP): numeric
  parsing with clear errors, guards for non-finite inputs, divide-by-zero-factor protection,
  range/sign checks where physically meaningful (e.g. absolute-zero floor for Kelvin).
- **Acceptance criteria:**
  - Empty / non-numeric / `NaN` input yields a defined validation error (no crash, no silent wrong
    result) across all three adapters.
  - A zero (or missing) conversion factor never produces a division-by-zero crash; it surfaces a
    clear error.
  - Below-absolute-zero temperature inputs (post SPEC-09) are rejected with a clear message.
  - `inf`/overflow results are represented and displayed safely.
  - Validation logic lives once in the core (no per-adapter reimplementation).
- **Notes/Dependencies:** Depends on SPEC-02; shared error contract with SPEC-03/04; tested by
  SPEC-07.

### SPEC-18 Structured, validated magnitude-data loader
- **Priority:** P2
- **Motivation:** `Magnitudes.txt` parsing is fragile: requires line-count divisible by 3 and "no
  empty end line", calls `self.exit()` (sometimes before it exists) and `print`s on violation; the
  superscript hack replaces literal `'2'`/`'3'` chars (can corrupt names). This blocks reliable data
  expansion (SPEC-08/09/10).
- **Scope:** Replace the fragile parser with a structured, schema-validated loader (keep
  `Magnitudes.txt` or migrate to JSON/TOML) that validates each magnitude (unique unit names,
  numeric finite non-zero factors, valid affine fields, declared base unit) and reports precise,
  non-fatal errors instead of `print`+exit. Resource path resolution is frozen-bundle-safe
  (`sys._MEIPASS`), shared with SPEC-05.
- **Acceptance criteria:**
  - A malformed entry yields a precise, located error (which magnitude/field) without crashing the
    app; the app degrades gracefully (loads valid magnitudes, flags the bad one).
  - Unit names containing literal digits (e.g. "m2"-style or accented names) are not corrupted; the
    superscript transform is rendering-only and reversible/lossless in stored data.
  - Loader rejects zero/negative/non-finite factors and duplicate unit names at load time.
  - The same loader serves source-tree and frozen-bundle runs (path-helper test).
  - Loader is unit-tested independently of the GUI.
- **Notes/Dependencies:** Depends on SPEC-02; prerequisite for SPEC-08/09/10; shares path helper
  with SPEC-05.

### SPEC-19 Structured error handling and logging
- **Priority:** P2
- **Motivation:** The app uses `print` and cargo-cult cleanup (`del self`, `gc.collect()`, no-op
  `del locals()`); there is no logging and no consistent error surface.
- **Scope:** Introduce the stdlib `logging` framework (configurable level, file + console handlers)
  across core and adapters; replace `print`/`exit` debugging with logged, typed exceptions; remove
  the cargo-cult `exit()` cleanup. UI shows user-facing errors via a non-blocking, themed surface
  (not a popup window — consistent with SPEC-01's centralized approach).
- **Acceptance criteria:**
  - No `print` statements remain for diagnostics (grep check); all go through `logging`.
  - Errors raise/propagate typed exceptions handled at a single UI/adapter boundary.
  - Log level is configurable; logs include enough context to trace a failed conversion.
  - The `del self`/`gc.collect()`/`del locals()` cleanup is removed without resource leaks.
- **Notes/Dependencies:** Depends on SPEC-02; error contract aligns with SPEC-03/04/17.

### SPEC-22 Accessibility
- **Priority:** P2
- **Motivation:** Beyond tooltips, the GUI should be keyboard-navigable and screen-reader friendly;
  FF's reference notes hover-only info is inaccessible.
- **Scope:** Accessible names/descriptions on all interactive widgets (driven by SPEC-01's
  registry), logical tab order, keyboard shortcuts for primary actions, and sufficient color
  contrast in both themes.
- **Acceptance criteria:**
  - Every interactive widget has a non-empty accessible name and description (test asserts coverage).
  - The full conversion flow (pick magnitude, units, enter value, read/copy result) is completable
    with keyboard only.
  - Light and dark themes meet a documented contrast ratio for text and tooltips.
- **Notes/Dependencies:** Builds on SPEC-01; pairs with SPEC-15 shortcuts.

### SPEC-20 Locale and number-format handling (i18n)
- **Priority:** P3
- **Motivation:** Decimal/thousands separators and number formats differ by locale; current parsing
  assumes a single format.
- **Scope:** Locale-aware input parsing and output formatting (decimal comma vs point, grouping
  separators) configurable and/or derived from the system locale; optional UI string translation
  scaffolding. Parsing normalizes to the canonical float the core expects.
- **Acceptance criteria:**
  - Input "1.234,56" (comma-decimal locale) and "1,234.56" (point-decimal locale) parse to the same
    value under the matching locale setting.
  - Output formatting respects the selected locale's separators (coordinated with SPEC-13).
  - Locale parsing/formatting is unit-tested across at least two locales.
- **Notes/Dependencies:** Depends on SPEC-13 formatting and SPEC-17 validation.

### SPEC-21 Performance
- **Priority:** P3
- **Motivation:** Interactive conversion and batch/search must feel instant; data loading must not
  block startup noticeably.
- **Scope:** Ensure single conversions are O(1) and sub-millisecond; data loaded/parsed once and
  cached; batch conversion scales linearly; UI stays responsive (no blocking on the GUI thread for
  large batches).
- **Acceptance criteria:**
  - A single `convert()` completes well under a documented threshold (e.g. < 1 ms) in a benchmark.
  - Magnitude data is parsed once and cached (no re-read per conversion; verified by test/spy).
  - A large batch (e.g. 10k values) completes within a documented bound without freezing the UI.
- **Notes/Dependencies:** Depends on SPEC-02, SPEC-12, SPEC-18.

---

## Priority summary

- **P1 (6):** SPEC-01 (centralized popup), SPEC-02 (core extraction), SPEC-07 (test/coverage gate),
  SPEC-09 (affine units), SPEC-16 (accuracy guarantees), SPEC-17 (input validation).
- **P2 (10):** SPEC-03 (REST), SPEC-04 (MCP), SPEC-05 (PyInstaller), SPEC-06 (dependency manifest),
  SPEC-08 (more magnitudes), SPEC-13 (precision/formatting), SPEC-15 (clipboard), SPEC-18 (validated
  loader), SPEC-19 (error/logging), SPEC-22 (accessibility).
- **P3 (6):** SPEC-10 (custom/compound units), SPEC-11 (history/favorites), SPEC-12 (batch),
  SPEC-14 (search), SPEC-20 (i18n/locale), SPEC-21 (performance).

Total: **22 specs** (P1 ×6, P2 ×10, P3 ×6).

Critical path: **SPEC-02 → {SPEC-07, SPEC-16, SPEC-17, SPEC-18} → {SPEC-03/04, SPEC-08/09, SPEC-05}**;
**SPEC-01** is independent of the core and proceeds in parallel once the PySide6 UI surface exists.
