# Improvement Backlog — Unit-Converter

- Repo slug: `unit-converter`
- Working copy: `D:\Documentos\GitHub\Unit-Converter`
- Enhancement branch (reviewed state): `enhancement/unit-converter-20260610`
- Author: the-recommender (planning only — no target-repo mutation). Date: 2026-06-13.
- Inputs: `docs/review-unit-converter.md`, `docs/research-competitive-unit-converter.md`,
  `docs/understanding-unit-converter.md`.
- Conventions: Gleaner threshold = 5 (orchestrator CONVENTIONS / agent-manifest). Asset-capability
  tags name what an in-repo coding agent (the `unit-conversion-operator` / generation agents) must
  be able to do — they verify the agent asset's capability surface.

How to use this backlog: every item is self-contained and pick-up-cold ready. IDs are stable.
Section 1 is ordered by severity (fix first). Section 2 is ordered by value/effort (do the
high-value/low-effort items first). Line references are against the reviewed branch and should be
re-confirmed before editing (code may have shifted).

---

## SECTION 1 — BUGS & FIXES (ordered by severity)

### UC-B01 — Invalid PEP 517 build backend blocks install/build
- Severity: **HIGH**
- File:line: `pyproject.toml:3`
- Root cause: `build-backend = "setuptools.backends.legacy:build"` is not a real setuptools entry
  point. `pip install .` and `python -m build` fail with `Backend ... is not a valid module`. The
  package the campaign produced cannot be installed or built.
- Fix approach: set `build-backend = "setuptools.build_meta"` and confirm `[build-system].requires`
  pins a setuptools version that provides it (e.g. `requires = ["setuptools>=61"]`). No other code
  change needed.
- Acceptance criterion: `python -m build` produces an sdist + wheel without error, AND
  `pip install .` into a clean venv succeeds and `import unit_converter` works. A CI/build step
  exercises one of these.
- Asset capability needed: **fix pyproject build config** (edit `[build-system]` in `pyproject.toml`).

### UC-B02 — Committed PyInstaller build artifacts on the branch
- Severity: **MED**
- File:line: `packaging/bin/UConverter/_internal/...`, `packaging/work/UConverter/warn-UConverter.txt`
  (review Gap G7, §D)
- Root cause: PyInstaller build output (`bin/`, `work/`) was committed instead of git-ignored —
  repo bloat plus stale binaries that drift from source.
- Fix approach: `git rm -r --cached` the committed build dirs; add `packaging/bin/` and
  `packaging/work/` (and any other PyInstaller output dirs the spec writes) to `.gitignore`. Confirm
  `packaging/build.py`/`UConverter.spec` write only into ignored paths.
- Acceptance criterion: `git status --ignored` shows `packaging/bin/` and `packaging/work/` as
  ignored; the tracked tree contains no built binaries; a fresh `python packaging/build.py` run
  leaves `git status` clean (no new tracked files).
- Asset capability needed: **edit .gitignore + untrack build output** (no compiled artifacts tracked).

### UC-B03 — GUI swallows all ValueError/ZeroDivisionError as 0.0
- Severity: **MED**
- File:line: `unit_converter/gui/main_window.py:692-693` and `725-726`
- Root cause: blanket `except (ValueError, ZeroDivisionError): result = 0.0` masks genuine
  unknown-unit / bad-order lookup failures as a legitimate clamp-to-zero, making real errors
  invisible (review Gap G2, §D).
- Fix approach: catch narrowly. Keep clamp-to-zero only for the documented clamp inputs (handled in
  the core `_clamp_input` already); for lookup/order errors, log via the module logger and surface a
  non-destructive UI signal (status text / disabled result) rather than silently writing 0.0. Do not
  change core math.
- Acceptance criterion: a unit test or GUI-logic test forcing an unknown unit/order asserts the
  handler logs an error and does NOT report `0.0` as a successful result; legitimate clamp inputs
  (negative/NaN/inf) still yield `0.0` unchanged.
- Asset capability needed: **edit GUI error handling + add logging** (narrow except + logger).

### UC-B04 — Coverage gate (≥90%) documented but not machine-enforced
- Severity: **MED**
- File:line: `pyproject.toml` `[tool.pytest.ini_options]` / `[tool.coverage]` (review Gap G6, §D);
  coverage scope already set at `pyproject.toml:74-84`
- Root cause: no `--cov-fail-under=90` (nor `[tool.coverage.report] fail_under = 90`) is configured,
  so the strategy's ≥90% core-coverage gate is not enforced by the test run.
- Fix approach: add `fail_under = 90` under `[tool.coverage.report]` (and/or `--cov-fail-under=90`
  in pytest addopts), keeping the existing `unit_converter`-scoped coverage with `gui/`, `api/`,
  `data/`, `.pyw` omitted so the gate lands on `core/`.
- Acceptance criterion: running the suite with coverage below 90% on `core/` exits non-zero;
  at/above 90% exits zero. Demonstrated by the testing agent's `run_coverage`.
- Asset capability needed: **fix pyproject test/coverage config** (add fail_under gate).

### UC-B05 — `_apply_superscripts` converts only a single trailing 2/3
- Severity: **LOW**
- File:line: `unit_converter/core/data_loader.py:151-179`
- Root cause: the helper rewrites only one trailing `2`/`3` (end-of-string or just before `)`).
  Other exponents (`4`), multi-digit exponents (`m22`), or interior-then-trailing digits in future
  legacy files pass through unconverted (review Gap G3, §B/§D). No current corruption — shipped TOML
  only needs `2`/`3`.
- Fix approach: generalize trailing-exponent detection to any digit run at the unit-name end (map
  each digit through the Unicode superscript table), preserving the existing guard that leaves
  embedded digits like `H2O`/`unit1` intact. Add the wider cases to the existing tests.
- Acceptance criterion: tests assert `m4 -> m⁴`, `m22 -> m²²` (or the chosen multi-digit rule), and
  that `H2O`/`unit1` remain unchanged.
- Asset capability needed: **edit core data_loader + extend pytest cases** (superscript normalizer).

### UC-B06 — Deprecated `asyncio.get_event_loop().run_until_complete` in smoke tests
- Severity: **LOW**
- File:line: `tests/test_api_smoke.py:60, 78, 152`
- Root cause: `get_event_loop()` with no running loop is deprecated on Python 3.12+ (can raise on
  3.14); fragile against the project's `requires-python>=3.11` / CI-on-3.13 target (review Gap G4).
- Fix approach: replace each with `asyncio.run(<coro>)` (or a pytest-asyncio fixture). No behavior
  change intended.
- Acceptance criterion: the smoke tests run on Python 3.13 with no `DeprecationWarning` for event
  loops (assert via `-W error::DeprecationWarning` on that file or a filter).
- Asset capability needed: **edit pytest async tests** (modernize asyncio usage).

### UC-B07 — MCP tool-name assertion too loose to catch real route-id/name mismatch
- Severity: **LOW**
- File:line: `tests/test_api_smoke.py:154`
- Root cause: the smoke test only asserts a tool name *containing* `magnitude`/`list`, so a real
  mismatch between `FastMCP.from_fastapi` derived names (`get_magnitudes`, `get_units`,
  `post_convert`, `health`) and the names asserted by the agent asset / `agent-access.md` would not
  fail the suite (review Gap G5).
- Fix approach: assert the exact expected tool-name set against the documented contract (single
  source of truth for the four operation IDs); fail if the generated set differs.
- Acceptance criterion: renaming any FastAPI operation id (changing a derived MCP tool name) makes
  the suite fail; the unchanged contract passes.
- Asset capability needed: **edit pytest MCP assertion** (exact tool-name contract check).

### UC-B08 — Default bind `0.0.0.0` for a single-user local compute service
- Severity: **LOW / advisory**
- File:line: `unit_converter/api/main.py:85` (`run_server`)
- Root cause: server binds all interfaces by default; mild exposure for a single-user local tool
  (review §C advisory).
- Fix approach: default host to `127.0.0.1`; expose a `--host`/arg override for intentional remote
  use; document the override.
- Acceptance criterion: with no host argument the server binds `127.0.0.1`; passing the override
  binds the requested interface; documented in `README-access.md`.
- Asset capability needed: **edit access-layer server config** (bind default + arg).

### UC-B09 — Legacy `Magnitudes.txt` vs TOML unit-name drift (silent rename)
- Severity: **LOW**
- File:line: data layer — `unit_converter/data/magnitudes.toml` vs legacy `Magnitudes.txt`
  (review §D last item)
- Root cause: the TOML silently "corrects" legacy typos (`jule (J)` -> `joule (J)`,
  `electronvolt (Ev)` -> `eV`), so a user still loading the legacy file gets different unit-name keys
  than the TOML — cross-format round-trip is not name-identical.
- Fix approach: document the canonical TOML names as the source of truth, and either (a) ship a short
  migration note mapping legacy->canonical names, or (b) add a name-alias map in the loader. Prefer
  the documentation route for a small app unless an alias is cheap.
- Acceptance criterion: a docs section (or `data/` README) lists the legacy->canonical name mapping;
  if aliasing is implemented, a test asserts a legacy name resolves to the canonical unit.
- Asset capability needed: **extend units data file + docs note** (canonical-name mapping).

---

## SECTION 2 — IMPROVEMENTS & FEATURES (ordered by value/effort)

Domain judgement for a small factor-based desktop+API converter: adopt the features that strengthen
the correctness contract and expose cleanly as API parameters, and that fit a factor model.
DEFERRED (do not fit a small app without an expression engine / heavy deps, called out at the end):
free-form expression parser, units-aware NumPy/Pandas integration, interval arithmetic, optimal-unit
auto-simplification.

### UC-I01 — Significant-figures / precision control
- Value/Effort: **High / S**
- What it adds: an optional `sig_figs` (or `precision`) parameter on `convert` that rounds the result
  to N significant digits, with a sane default preserving current behavior.
- Why: precision control is a top differentiator and the cheapest high-value win — a pure post-math
  formatting step over the existing factor result; no new dependency.
- Reference tool: Qalculate! significant-figures / precision. https://qalculate.github.io/features.html
- Modules/files: `unit_converter/core/converter.py` (add param + rounding), `api/rest.py` +
  `api/service.py` (thread the param + Pydantic field), `gui/main_window.py` (optional control),
  `.claude/agents/unit-conversion-operator.md` + `docs/agent-access.md` (document the param),
  `tests/test_converter.py`.
- Rough approach: implement sig-fig rounding in core (stdlib `decimal` or a small helper), default to
  current rounding; pass through service -> REST body field -> MCP tool param; surface optionally in
  GUI; document and test.
- Acceptance criteria: `convert(..., sig_figs=3)` returns the result rounded to 3 significant figures;
  default call output is unchanged from today; REST `POST /convert` accepts/validates the field; a
  test asserts representative sig-fig cases and the unchanged default.
- Asset capability needed: **edit core converter + thread param through MCP tool + REST route + add pytest cases**.

### UC-I02 — Dimensional-compatibility guard between magnitudes
- Value/Effort: **High / S**
- What it adds: explicit rejection of conversions whose source and target units belong to different
  magnitudes (dimensions), with a clear error rather than a silent factor-ratio.
- Why: the core correctness guarantee of any credible converter; for this factor model it is cheap —
  "same magnitude" is already the implicit contract, so make it explicit and validated. Closes the
  conceptual gap that full dimensional analysis addresses, scaled to the app.
- Reference tool: GNU units — dimensional analysis with incompatibility warnings.
  https://www.gnu.org/software/units/
- Modules/files: `unit_converter/core/converter.py` (validate from/to units resolve within the same
  magnitude; raise a typed `IncompatibleUnitsError`/`ValueError`), `api/rest.py` (map to HTTP 422),
  `tests/test_converter.py`, agent asset + `agent-access.md` (document the error contract).
- Rough approach: at convert entry, confirm both units exist under the requested magnitude (the API
  already passes a magnitude, so this hardens against future cross-magnitude or free-form callers);
  raise a clear, typed error; map to 422 in REST and to a structured error for MCP.
- Acceptance criteria: converting a Mass unit to a Length unit (or an unknown unit under a magnitude)
  raises the typed error / returns HTTP 422 with a descriptive message; valid same-magnitude
  conversions are unaffected; tests cover both paths.
- Asset capability needed: **edit core converter (typed validation) + map error in REST route + add pytest cases**.

### UC-I03 — User-defined custom units (persisted)
- Value/Effort: **High / M**
- What it adds: ability to add custom units (name + factor, under an existing magnitude) persisted to
  a user data file so they survive restart and are visible via the GUI and API.
- Why: high-value extensibility that fits the factor model exactly (a custom unit is just a
  name->factor pair); turns a fixed table into a user-extensible one. The data layer + validated
  loader already exist, so persistence is incremental.
- Reference tool: Qalculate! user-defined custom units (persisted).
  https://qalculate.github.io/manual/qalculate-units.html
- Modules/files: `unit_converter/core/data_loader.py` (load+merge a user units file with validation
  via existing `_validate_factor`), `unit_converter/data/` (user-units file path / `_default_data_dir`
  + `sys._MEIPASS` awareness), `api/service.py` + `api/rest.py` (optional add/list custom units —
  keep read-only safety in mind: a write endpoint expands the access surface, see acceptance),
  `gui/main_window.py` (add-unit dialog), `tests/test_data_loader.py`.
- Rough approach: define a user-writable units file (e.g. `~/.unit-converter/custom.toml`), merge it
  over the shipped TOML at load with the same factor validation; expose listing through existing
  `list_units`. For the API, prefer keeping the network surface read-only — add custom units via GUI/
  local file only, and only expose a write endpoint if F4 tool-count discipline and access-layer
  safety are explicitly re-approved.
- Acceptance criteria: a persisted custom unit appears in `list_units(magnitude)` and converts
  correctly after a restart; an invalid factor (0/neg/NaN/inf) is rejected at load with a clear
  error; tests cover merge, persistence, and validation. If a write endpoint is added, it is
  validated and documented; otherwise the API remains read-only and docs state custom units are
  added locally.
- Asset capability needed: **extend units data file + edit core data_loader (user-file merge) + (optional, gated) add MCP tool + REST route + add pytest cases**.

### UC-I04 — Affine/offset temperature magnitude (absolute vs increment)
- Value/Effort: **High / M**
- What it adds: a Temperature magnitude with correct absolute conversion (offset + scale, e.g.
  °C/°F/K) distinguished from temperature increments (scale-only), without breaking the existing
  multiplicative factor model for all other magnitudes.
- Why: temperature is the canonical converter trap; the review explicitly flags that the current
  multiplicative-only model would be WRONG for °C/°F if temperature is added. This unlocks a major
  expected category correctly.
- Reference tools: GNU units — affine/offset temperature handling
  (https://www.gnu.org/software/units/manual/html_node/Temperature-Conversions.html) and general
  nonlinear/functional units (https://www.gnu.org/software/units/manual/html_node/Defining-Nonlinear-Units.html).
- Modules/files: `unit_converter/core/converter.py` (introduce an affine unit kind: `offset` +
  `factor`, applied before/after the ratio; branch by unit kind), `unit_converter/data/magnitudes.toml`
  (Temperature magnitude with offset metadata + absolute-vs-increment flag), `data_loader.py`
  (parse/validate offset fields), `tests/test_converter.py` (0°C==32°F, 100°C==212°F, K round-trips,
  increment vs absolute), agent asset + docs (document the two modes).
- Rough approach: extend the unit record schema with an optional `offset` (and an absolute/increment
  flag); in `convert`, apply `to_base = (value - from_offset) * from_factor` then
  `result = to_base / to_factor + to_offset` for absolute units, falling back to today's pure-ratio
  path when offset is absent (zero) so all existing magnitudes are byte-for-byte unchanged.
- Acceptance criteria: 0°C -> 32°F, 100°C -> 212°F, 0°C -> 273.15K all correct within tolerance;
  increment conversion (ΔT) uses scale only; every pre-existing magnitude's results are unchanged
  (regression test); incompatible mix (UC-I02) still rejected. Coverage stays ≥90%.
- Asset capability needed: **edit core converter (affine math) + extend units data file (offset schema) + edit data_loader + add pytest cases**.

### UC-I05 — Live currency conversion with auto-updating rates (API-fronted)
- Value/Effort: **Med / L**
- What it adds: a Currency "magnitude" whose factors are exchange rates fetched from a rates source,
  refreshable manually or on an interval, keyed by ISO 4217 codes.
- Why: high user appeal and a natural fit for the MCP/REST surface (an endpoint that refreshes rates).
  Effort is L because it introduces a network dependency, caching, staleness handling, and offline
  fallback — out of proportion to the rest of a small offline app, hence Med value-for-effort.
- Reference tool: Qalculate! live currency with auto-updating exchange rates.
  https://qalculate.github.io/manual/qalculate-units.html
- Modules/files: new `unit_converter/core/rates.py` (fetch + cache + staleness), `data_loader.py`
  (treat rates as Currency-magnitude factors), `api/service.py` + `api/rest.py` + `api/mcp_server.py`
  (a refresh-rates operation + currency listing — this is a STATE-CHANGING op, so F4 tool-count and
  access-layer safety must be re-approved), `pyproject.toml` (add an HTTP client dependency),
  `tests/` (mock the rates source; offline fallback; staleness). Requires a RESEARCH REQUEST for a
  current free rates API + its schema/limits before build.
- Rough approach: pluggable rates provider with a cached snapshot file and a documented staleness
  window; convert reuses the factor path with rate-as-factor; the refresh endpoint updates the cache.
  Default to cached/offline; never block conversion on the network.
- Acceptance criteria: with mocked rates, USD->EUR uses the fetched rate; a forced refresh updates
  the cached snapshot; with the network unavailable, conversion falls back to the last cached
  snapshot and reports staleness; tests cover fetch, cache, refresh, and offline fallback; the new
  endpoint is validated and access-layer-safety reviewed.
- Asset capability needed: **add core rates module + extend units data file + add MCP tool + REST route (state-changing, gated) + add HTTP dependency in pyproject + add pytest cases**. (Also requires a RESEARCH REQUEST — see below.)

### UC-I06 — Compound / derived unit parsing (limited, no full expression engine)
- Value/Effort: **Med / L**
- What it adds: parse simple compound units (products/quotients/powers of existing base units, e.g.
  `N*m`, `km/h`) so derived conversions work without per-pair tables.
- Why: a real converter differentiator, but it requires a tokenizer + dimension tracking on top of
  the flat magnitude model. Worthwhile but the largest correctly-scoped feature here; gated on
  UC-I02 (dimensional guard) existing first.
- Reference tool: GNU units — compound/derived unit parsing.
  https://www.gnu.org/software/units/manual/html_node/Overview.html
- Modules/files: new `unit_converter/core/expr.py` (small parser for `* / ^` over known units),
  `core/converter.py` (compose factors + dimensions), `data_loader.py` (per-unit dimension vector),
  `api/rest.py` (accept compound unit strings), GUI optional, `tests/` (extensive).
- Rough approach: assign each base unit a dimension signature; parse compound strings into a
  factor+dimension product; reuse UC-I02 to reject dimension mismatches. Keep scope to `* / ^` and
  grouping — no general arithmetic/free-form (that is deferred below).
- Acceptance criteria: `N*m -> J` and `km/h -> m/s` convert correctly; a dimensionally invalid
  compound (`kg + m`) is rejected via the UC-I02 path; existing single-unit conversions unaffected;
  parser has unit tests for tokens, precedence, and error cases.
- Asset capability needed: **add core expression parser + edit core converter (dimension composition) + extend data_loader (dimension vectors) + edit REST route + add pytest cases**. Depends on UC-I02.

### UC-I07 — Conversion history / favorites (local presets)
- Value/Effort: **Low / S**
- What it adds: persist recent conversions and let the user re-run/favorite them in the GUI.
- Why: nice UX polish, cheap, but lowest-confidence (inferred from calculator UX, not a discrete
  sourced feature) and not core to a converter's value. Do last.
- Reference tool: Qalculate! desktop calculator UX (history/favorites — inferred, low confidence).
  https://qalculate.github.io/
- Modules/files: `unit_converter/gui/main_window.py` (history panel/menu), a small local history file
  under the user data dir, `tests/` (history persistence logic, GUI-independent).
- Rough approach: append each successful conversion to a capped local JSON history; GUI lists recent
  entries and re-applies them; keep the logic in a small testable helper, not entangled with widgets.
- Acceptance criteria: a completed conversion appears in history and survives restart; selecting a
  history entry repopulates the inputs; the history helper has unit tests independent of the GUI.
- Asset capability needed: **edit GUI + add local history helper module + add pytest cases**.

### Deferred (do NOT fit a small factor-based app without disproportionate effort)
These competitive features were evaluated and intentionally excluded for this repo; recorded so the
decision is auditable, not lost:
- **Free-form natural-ish expression parser** (Wolfram|Alpha / Wolfram Quantity) — needs a full
  expression engine; UC-I06 covers the limited-compound subset that fits. Defer the general parser.
- **Units-aware NumPy/Pandas integration** (Pint) — out of scope for a desktop converter + small API;
  the app is not a numeric-pipeline library.
- **Interval arithmetic** and **optimal-unit auto-simplification** (Qalculate!) — require a heavier
  numeric/CAS core than a factor table warrants for a small app.
- **Uncertainty propagation** (Pint/`uncertainties`) — a meaningful feature but a new dependency and
  conceptual surface (±values through every op) beyond this app's scope; revisit only if UC-I01 sig-figs
  demand proves users want measurement semantics.
- **General nonlinear/functional units** (dB, pH) — the affine path (UC-I04) covers the common
  temperature case; full functional units are deferred until a real demand exists.

---

## Embedded routing requests (for the orchestrator)

- **RESEARCH REQUEST (for UC-I05, before build):** identify a current, free/low-cost exchange-rate
  API (e.g. provider name, base URL, auth model, rate limits, ISO-4217 coverage, response schema, and
  licensing) suitable for periodic refresh from a desktop app. Route to The Researcher; fold cited
  results into UC-I05 before it is implemented.
- **GATHERING REQUEST:** none. Each generation agent above touches a bounded, named file set (< 5
  files of new reading beyond its own outputs); no ≥5-file extraction is required for any single item.
- **ASSET REQUEST:** none. The existing generation agents cover every capability tag (feature-enhancer
  for core/GUI edits, access-layer-builder for MCP+REST, packaging for build config, testing for
  pytest, docs for documentation). UC-I05's state-changing endpoint and UC-I03's optional write
  endpoint require an access-layer-safety / F4 tool-count re-approval, not a new asset.

## Distinct asset-capability tags (capability surface the agent asset must cover)
1. fix pyproject build config (UC-B01)
2. edit .gitignore + untrack build output (UC-B02)
3. edit GUI error handling + add logging (UC-B03)
4. fix pyproject test/coverage config (UC-B04)
5. edit core data_loader (UC-B05, UC-I03, UC-I06)
6. add/extend pytest cases (UC-B05, UC-B06, UC-B07, UC-I01-I07)
7. edit pytest async tests (UC-B06)
8. edit pytest MCP assertion (UC-B07)
9. edit access-layer server config / bind (UC-B08)
10. extend units data file (UC-B09, UC-I03, UC-I04, UC-I05, UC-I06)
11. edit core converter (UC-I01, UC-I02, UC-I04, UC-I06)
12. thread param through MCP tool + REST route (UC-I01)
13. map/raise typed error in REST route (UC-I02)
14. add MCP tool + REST route, state-changing/gated (UC-I03, UC-I05)
15. add core module (rates UC-I05; expression parser UC-I06; history helper UC-I07)
16. add dependency in pyproject (UC-I05)
17. edit/extend docs + agent asset (UC-I01-I06, UC-B09)
