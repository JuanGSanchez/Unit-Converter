# Instruction: SDD Constitution (Unit-Converter)

## Principles Applied
Inherited: P1 (source grounding — phases read predecessor artifacts, not memory or prior context), P2 (determinism — gate conditions are explicit; no ambiguous phase transitions), P3 (systematicity — phase order and gate criteria are enumerated; each phase transition has a named decision point), P4 (consistency — same invariants and gates apply every pipeline run and every session), P6 (self-contained — all gates, invariants, and acceptance criteria stated here), P7 (reference hygiene — citations resolve to CLAUDE.md §Invariants and .claude/instructions/python-repo-conventions.md; hook names resolve to CLAUDE.md §Hooks), P8 (this block is the P8 expression for this asset), P9 Role Separation (this instruction governs the cross-phase pipeline contract; per-agent instructions govern individual agent execution; no agent owns the constitution), P10 Exit-Status Determinism (Rule 17 requires each agent to report PASS/FAIL for each gate criterion and return EXIT STATUS at phase completion, per CLAUDE.md Operating contract), P11 Programmatic Determinism (harness hooks enforce invariants 1, 4, and 6 deterministically at the tool-use level — plans must not propose workarounds; R18/P11 canonical definition: `repo-enhancer/orchestrator.md` CONVENTIONS, do not restate), P12 Maximal-Effort Completeness (all 7 CLAUDE.md invariants and all 6 pre-implement pipeline phase gates are covered; no invariant is partial), P13 Token Economy (rules cite invariant/rule IDs rather than restating them; terse). Engineering Disciplines (R17): canonical definition at `repo-enhancer/orchestrator.md` CONVENTIONS; prompt layer = numbered gated directives with positive/negative examples; context layer = each phase reads only its predecessor artifact, not the full pipeline history; harness layer = gate conditions block phase advancement until the predecessor artifact exists and is approved.

Custom:
- C1 — Pipeline Gate Integrity: every phase must verify its predecessor artifact exists on disk and is approved before proceeding; no phase runs without its input artifact; no phase skips its predecessor regardless of perceived urgency.

Scope: applies to every Unit-Converter coding agent (core-dev, gui-dev, access-dev, test-author, packaging-builder) and the active session/orchestrator when executing SDD pipeline phases (specify / clarify / plan / tasks / analyze / checklist / implement). The per-agent instructions own individual agent execution; this instruction owns the cross-phase contract that binds all of them.

<instructions>
  <context>
    Unit-Converter uses the SDD pipeline: specify → clarify → plan → tasks →
    analyze → checklist → implement. This instruction is the project constitution
    — the non-negotiable contract every phase, artifact, and agent must satisfy.
    Its purpose is to keep each pipeline artifact a trustworthy handoff to the
    next phase across sessions, agents, and context windows.

    Existing reality this constitution reflects:
    - Architecture: "one core, many faces" (CLAUDE.md §Architecture). One
      headless core (`unit_converter/core/converter.py`,
      `unit_converter/core/data_loader.py`) powers a PySide6 GUI, a dual
      FastAPI+FastMCP access layer over one shared service, and a PyInstaller
      build. Every new capability must propagate through this architecture.
    - 7 invariants (CLAUDE.md §Invariants 1–7) and coding rules
      (.claude/instructions/python-repo-conventions.md) are in force throughout
      every phase.
    - Hooks enforce invariants mechanically (headless_core_guard.py,
      no_secrets_or_artifacts.py, tkinter_regression_guard.py). Plans must not
      propose workarounds.
    - Unit-Converter is a compute-only utility: there are no destructive file
      operations. The safety-gate concern is conversion accuracy and transport
      integrity, not filesystem mutation.
  </context>

  <rules>
    <!-- Phase gate rules (C1: predecessor artifact must exist before each phase begins) -->

    1. Mandatory phase order. Execute phases in this order only:
       specify → clarify → plan → tasks → analyze → checklist → implement.
       No phase begins until its predecessor artifact exists on disk and is
       approved. Under no circumstances write code before spec.md, plan.md,
       and tasks.md exist and are cross-artifact-consistent.

    2. Specify gate. spec.md must state user-facing requirements (what and why)
       with explicit acceptance criteria per requirement. All requirements must
       be unambiguous when the clarify phase closes; none may remain open.

    3. Clarify gate. Every underspecified area in spec.md must be resolved
       through structured questioning before plan begins. Record every
       resolution in spec.md. A plan must not proceed while any requirement
       reads as ambiguous.

    4. Plan gate. plan.md must: (a) assign every new or modified module to its
       subsystem owner (core-dev / gui-dev / access-dev / test-author /
       packaging-builder); (b) state all data-model changes; (c) explicitly
       confirm that each of the 7 CLAUDE.md invariants holds under the plan.
       A plan that proposes importing a GUI or transport symbol into
       unit_converter/core/* (violates Invariant 1), routing affine (temperature)
       math through the multiplicative path (violates Invariant 2), or forking
       behavior between rest.py and mcp_server.py (violates Invariant 3) is
       rejected without modification. Instead, redesign to preserve the invariant.

    5. Tasks gate. tasks.md must list dependency-ordered, single-owner work
       items. Each item must name: its owning agent, a done criterion
       (feature-level and verifiable), and a test criterion (the specific
       test(s) that must pass before the item is marked done).

    6. Analyze gate. Before implement begins, a cross-artifact consistency
       check must verify: (a) every spec requirement is covered by at least
       one plan component; (b) every plan component appears in at least one
       task; (c) no task introduces a latent invariant violation. All
       conflicts identified here must be resolved before implement begins;
       implement does not begin with open conflicts.

    7. Checklist gate. A project-specific quality checklist covering CLAUDE.md
       Invariants 1–7 and python-repo-conventions.md Rules 1–7 must be
       generated and run against the implementation. All items must pass, or
       be documented exceptions with a risk assessment, before the feature is
       declared done.

    <!-- Non-negotiable architecture invariants (carry through every phase) -->

    8. Headless core purity (CLAUDE.md Invariant 1;
       python-repo-conventions.md Rule 2). unit_converter/core/converter.py
       and unit_converter/core/data_loader.py must import no Tkinter, PySide6,
       Qt*, FastAPI, FastMCP, or any GUI/transport symbol. Every plan and task
       that touches core/* must explicitly confirm this invariant holds after
       the change. The headless_core_guard.py hook (PreToolUse) enforces this
       mechanically; plans must not propose workarounds.

    9. Affine unit accuracy (CLAUDE.md Invariant 2;
       python-repo-conventions.md Conditional Rule 1). Temperature-class and
       other affine units (offset + scale) must be routed through the offset
       path in convert(); under no circumstances may an affine unit be pushed
       through the multiplicative factor-ratio formula. A plan or task that
       routes temperature conversion through the scale-only path is rejected.

    10. No logic forking (CLAUDE.md Invariant 3;
        python-repo-conventions.md Rule 5). Behavior changes go in the shared
        core/service, never forked into rest.py or mcp_server.py. MCP tool
        names derive from FastAPI operation IDs; changing an operation ID
        changes the derived tool name and the operator/docs contract. Under no
        circumstances may a plan add capability by forking logic between the
        two transports.

    11. Data-file integrity (CLAUDE.md Invariant 4;
        python-repo-conventions.md Conditional Rule 2).
        unit_converter/data/magnitudes.toml is the canonical unit/magnitude
        definition. Every plan that adds or modifies a unit must also confirm
        that packaging/UConverter.spec still bundles the data file correctly.
        A plan that removes or bypasses magnitudes.toml is rejected.

    12. Coverage gate (CLAUDE.md Invariant 5;
        python-repo-conventions.md Rule 7). The gate is fail_under=90 scoped
        to unit_converter (gui/, api/, data/, .pyw omitted as configured in
        pyproject.toml). No plan or task may lower the threshold, widen the
        omit, or defer tests to a later task. Every implement task ships its
        tests in the same work item.

    13. No secrets / no build artifacts (CLAUDE.md Invariant 6;
        python-repo-conventions.md Rule 6). Under no circumstances do commits
        include credentials, tokens, keys, .env content, or build output
        (packaging/bin/, packaging/work/, dist/, build/). The
        no_secrets_or_artifacts.py hook (PreToolUse) enforces this.

    14. Branch policy (CLAUDE.md Invariant 7). All commits land on the
        enhancement branch (enhancement/*), never main or master.

    <!-- Cross-cutting standards (apply throughout the pipeline) -->

    15. Stdlib/zero-dep core (python-repo-conventions.md Rule 1). The core has
        zero third-party runtime deps. Plans must not propose adding a dep for
        something stdlib covers. Any new dep must appear in pyproject.toml
        under the correct optional group (gui/api/dev) with a pinned range and
        a one-line rationale — never in the top-level dependencies array.

    16. Type all public APIs (python-repo-conventions.md Rule 3). Every new
        public function/method in core/, api/service.py, and new helpers must
        carry parameter and return type hints. A task is not done if its public
        surface is untyped.

    17. PySide6 only for the GUI (python-repo-conventions.md Rule 2 + hook).
        No Tkinter reintroduction. The tkinter_regression_guard.py hook
        (PreToolUse) enforces this.

    <!-- Acceptance gates: what "done" means -->

    18. A feature is "done" only when all of the following hold, reported as
        explicit PASS/FAIL per criterion in the agent's phase completion
        output, followed by an EXIT STATUS payload:
        (a) cross-artifact analysis (Phase 5) is complete and all conflicts
            resolved (analyze gate — PASS);
        (b) project checklist (Phase 6) is run and all items pass
            (checklist gate — PASS);
        (c) pytest --cov=unit_converter --cov-fail-under=90 passes with
            QT_QPA_PLATFORM=offscreen set (coverage gate — PASS);
        (d) all 7 CLAUDE.md invariants hold — hooks verify invariants 1, 4,
            and 6 mechanically; agents verify 2, 3, 5, and 7 before reporting
            PASS;
        (e) all changes committed on the enhancement branch, never main/master
            (branch gate — PASS).
  </rules>

  <conditional_rules>
    - If a plan touches unit_converter/core/, then tasks.md must include an
      explicit "headless purity re-check" task that verifies no GUI or
      transport import was added (Rule 8). This task is a prerequisite for
      every other task that modifies core/*.
    - If a feature introduces or modifies an affine (offset+scale) unit, then
      tasks.md must include an "affine offset-path contract test" that verifies
      round-trip correctness for at least one known value pair before any other
      conversion-path task is marked done (Rule 9).
    - If the coverage gate drops below 90% at any point during implement,
      then halt the phase, report the gap, and escalate to the user; do not
      advance or merge (Rule 12).
    - If a task requires a new dependency, then the pyproject.toml entry
      (and packaging/UConverter.spec hidden-imports update, if needed) is
      part of the same task, not a follow-up task (Rule 15).
    - If a plan changes a FastAPI operation ID, then tasks.md must include a
      task that updates the expected-tool-name assertion in
      tests/test_api_routes.py and any affected docs-writer output (Rule 10).
  </conditional_rules>

  <output_format>
    At each phase gate: report PASS or FAIL for each gate criterion (Rules
    2–7). At implement completion: report PASS or FAIL for each acceptance
    gate criterion (Rule 18a–e). End with the agent's EXIT STATUS payload.
  </output_format>

  <examples>
    <example>
      <input>Plan: add a `parts_per_million` unit under the Concentration
      magnitude in magnitudes.toml.</input>
      <output>
        Accepted. plan.md assigns the change to core-dev
        (magnitudes.toml, data_loader.py validation) and test-author
        (test_data_loader.py, test_converter.py). Data model:
        factor = 1e-6 relative to the base Concentration unit. Invariant
        check: (1) core/* gains no surface import — PASS; (2) affine path
        not involved — PASS; (3) no transport fork — PASS; (4) spec update
        to confirm UConverter.spec data bundle unchanged — PASS; (5) tests
        ship with same task — PASS; (6) no credentials/artifacts — PASS;
        (7) branch policy enforced — PASS. tasks.md entry:
        owner=core-dev, done="magnitudes.toml carries ppm with factor 1e-6
        and convert() returns correct result", test="test_converter.py
        asserts ppm → base and base → ppm within 1e-12 tolerance."
        Headless purity re-check task included.
      </output>
    </example>
    <example>
      <input>Plan: implement Celsius→Fahrenheit by adding (value * 9/5) + 32
      directly in rest.py's convert route handler to avoid changing the core.</input>
      <output>
        Rejected (Rule 10 — no logic forking and Rule 9 — affine accuracy).
        Affine temperature conversion belongs in the offset path of
        unit_converter/core/converter.py so both REST and MCP inherit it
        and the round-trip is tested once. Add the offset+scale values to
        magnitudes.toml under Temperature, route through the existing affine
        path in convert(), and let rest.py and mcp_server.py inherit via
        service.py with no logic changes.
      </output>
    </example>
  </examples>
</instructions>

<!--
  SOURCES:
  - User requirement: SDD constitution instruction governing pipeline gates
    and invariants for Unit-Converter (Group E, step 16).
  - CLAUDE.md §Invariants 1–7, §Architecture, §Gate commands, §Hooks:
    existing repo reality (7 invariants, one-core/many-faces architecture,
    coverage gate, branch policy, hook roster).
  - .claude/instructions/python-repo-conventions.md Rules 1–7 + Conditional
    Rules: coding standards carried through every pipeline phase.
  - asset-metaprompting/references/software-development.md §2: SDD phase
    definitions (specify/clarify/plan/tasks/analyze/checklist/implement)
    and the gate-before-proceed property.
  - templates/claude_instruction.md: structural template.
  - repo-enhancer/orchestrator.md CONVENTIONS R17 (Engineering Disciplines)
    and R18/P11 (Programmatic Determinism): canonical definitions (cited,
    not restated).
-->
