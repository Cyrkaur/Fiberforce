# FiberForce Advanced Examples

High-quality, runnable, notebook-style Python scripts demonstrating advanced usage of the FiberForce `AnalysisService` (the primary high-level API), reference-backed builders (with auto + explicit geometric moment arm support), multi-variable sensitivity, the full enhanced persistence layer (Saved*Run artifacts, profile-linked runs), visualization, and profiles.

These scripts go far beyond basic `fiberforce demo` or CLI usage. They are intended for:
- Serious lifters and coaches exploring "what-if" training decisions with real personalization
- Researchers prototyping new analysis workflows
- Contributors learning the full power of the library (service + geometric builders + multi-var + complete persistence + post-v1 continuous ROM / dynamics)

12_continuous_rom_demo.py demonstrates the dynrom continuous ROM MVP (analyze over joint angle range, MultiPositionResult output).

## Prerequisites (v2 — Bulletproofed for the Real Workspace)

**The examples live inside the canonical workspace. Past friction came from running pip outside the dir or without venv. Use this exact sequence (for dev / running examples):**

For the primary end-user GUI (v2.0): build the clickable .app/DMG once (scripts/build_macos_app.sh) then double-click the icon — no python/venv needed for daily use of the full interface.

```bash
cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[gui,viz]"
```

All scripts run cleanly even without matplotlib (they use built-in rich tables + pure-ASCII visualization fallbacks via `fiberforce.visualization` + imperial/ft-lb by default in the modern ones).

**Easiest way to verify everything works (after the block above):**
```bash
fiberforce smoke          # v1: imperial, ft-lb torque (~227 example), recipes, .interpret(), WeeklyProgram, sensitivity insight
python -m pytest -q       # ~204 tests
```

See the **Development & Testing** section in the main [README.md](../README.md) for the full recommended test matrix + GUI launch + flagship examples (01/10/11). Never skip the cd + venv + activate.

## The Nine Advanced Examples (05 heavily expanded for v0.4 multi-position)

### 01 — Program-Level Insights (`01_program_level_insights.py`)
Simulates a full training week across bench, squat, and deadlift variations using the new v0.5 `TrainingSession` + `WeeklyProgram` dataclasses (Phase 3).
Accumulates regional stress/volume via the official accumulation helpers, generates model reports, and demonstrates direct comparison of two weekly programs built from multi-position data.
Produces recommendations + ASCII charts + full model comparison output.

**Key concepts**: `TrainingSession` / `WeeklyProgram` (fiberforce.results), batch + multi-position analysis via `AnalysisService`, program comparison, realistic program modeling, integration with accumulate helpers.

### 02 — Personalization Study (`02_personalization_anthropometry_study.py`)
Compares force demands for "average femur" vs "long femur" lifters on high-bar vs low-bar squats.
Shows current limitation (segment lengths don't yet auto-affect forces via static tables in all paths) while demonstrating the full Subject + builder personalization API + educational custom rebuild proxy.
Includes early foreshadowing of geometric scaling.

**Key concepts**: `AnalysisService.create_subject_from_measurements`, custom `SensitivityAnalyzer` rebuild callables, honest surfacing of roadmap items.

### 03 — Sensitivity Sweeps for Training Decisions (`03_sensitivity_grip_bench_pecs.py`)
Quantifies the effect of grip width (close/medium/wide using real reference data) and bar angle (flat/incline/decline) on **both** sternal and clavicular fibers of the pec major.

Includes discrete real-data tables + continuous proxy sweep with visualization.

**Key concepts**: custom `AnalyzedPosition` construction for non-default regions, multiple sensitivity styles, regional pec comparison, single-var foundation.

### 04 — Deadlift vs Squat Posterior Chain Comparison (`04_deadlift_vs_squat_posterior_chain.py`)
The flagship comparison example. Uses real posterior-chain subject data and all four major bottom-position variations (squat high/low-bar + deadlift conventional/sumo) to rank demand on glutes (upper), hamstrings (BFLH), and lumbar erectors.

Beautiful side-by-side `ComparisonResult` visualizations + full ranking tables via service + viz.

**Key concepts**: first-class deadlift support (conventional + sumo), multi-region posterior chain analysis, `plot_comparison`, production builders, full OHP/deadlift parity groundwork.

### 05 — Geometric Moment Arm Prototype (`05_geometric_moment_arm_prototype.py`)
Demonstrates the **geometric moment arm prototype** (new in the massive phase continuation): the first step from purely static reference tables toward subject-specific, anthropometry-driven MA estimation.

- Bench sternal pec MA driven by humerus + biacromial + grip + torso depth.
- Squat glute + quad MA driven by femur + tibia + stance (optional).
- Side-by-side static vs. geometric for multiple realistic body profiles.
- **Live SensitivityAnalyzer rebuilds** that use the geometric estimators directly as the source of truth for continuous grip/stance sweeps (the key power demo).
- **Heavily expanded for v0.4 FiberForce push (Part 6)**: Complete runnable demonstration of multi-position (limited dynamic) analysis.
  - Uses `AnalysisService.build_multi_position("squat", ["bottom","mid","top"], ...)` and `analyze_multi_position`.
  - Position-aware builders (`position="bottom"|"mid"|"top"`) with differentiated joint angles.
  - Full wiring to geometric estimators (estimate_squat_glute_ma now position-aware via hip flexion mapping 110°→25°).
  - Live comparison + ASCII visualization of how glute demand changes dramatically from bottom (peak MA) to top (sharp drop) on identical lifter/load.
  - Also cross-variation (high-bar vs low-bar) at multiple ROM points.
  - Notebook-style, production-quality template for "limited dynamic" questions.

**Key concepts**: `fiberforce.reference.geometric` (and `ReferenceData.estimate_moment_arm`), custom rebuilds with live geometry, prototype limitations + model docs, preparation for future personalization, **v0.4** `build_multi_position` / position-aware builders / analyze_multi_position.

**New capability highlight**: You can now vary *real body measurements or grip/stance* and get continuously varying, anthropometrically grounded moment arms. **Plus**: first-class support for discrete multi-position (limited dynamic) ROM analysis with geometric MA.

### 06 — Multi-Variable Sensitivity Analysis (`06_multi_variable_sensitivity.py`)
Demonstrates the **multi-variable sensitivity foundation** (`AnalysisService.sensitivity_multi` / `SensitivityAnalyzer.run_multi`): sequential sweeps over multiple variables (e.g. load × femur, load × grip) while holding others fixed.

Includes a powerful **combined geometric + multi-var demo** that wires the live geometric estimators into the multi-variable rebuild callable — exactly the pattern for future high-fidelity "what-if" studies on your actual skeleton + setup choices.

**Key concepts**: `sensitivity_multi`, custom `rebuild_multi` dict-based rebuilders, combining with geometric MA (05), AnalysisService as single source of truth, visualization of multiple result objects.

### 07 — Persistence, Profiles & Full-Lift Batch Analysis (`07_persistence_profiles_and_batch.py`)
The persistence flagship (original anthropometry-focused version). Shows how to save your real anthropometry **once** with the profiles system, load it anywhere (library or `fiberforce profile run`), and then drive a complete personal audit across **all four first-class lifts** (bench + squat + deadlift conv/sumo + OHP standing/seated + multi-head) using the unified `AnalysisService.build_position` + `analyze`.

Includes ranking, simple aggregation, structured `service.compare`, visualization, and a reusable dated report template you can turn into your own weekly dashboard.

**Key concepts**: `save_anthropometry` / `load_anthropometry` / `list_profiles`, `AnalysisService` as the single source for all lifts + personalization, batch + reporting patterns, CLI/library symmetry via profiles.

### 08 — Profile + Full Enhanced Persistence Workflows (`08_profile_persistence_workflows.py`)
**New (latest persistence layer showcase)**. Demonstrates the *complete* production persistence system (`fiberforce.results` + `SavedAnalysisRun` / `SavedSensitivityRun` / `SavedCompareRun`, `run_profile_multi_sensitivity`, `service.save_current_analysis`, `save_profile_with_run`, `list_saved_runs` + round-tripping, `list_all_for_profile`, etc.).

Includes a strong integrated **combined geometric + multi-var** section that uses the modern convenient builder path (`build_position(..., use_geometric=True, stance_width_cm=...)`) inside a custom `rebuild_multi` driven from a saved rich profile.

This is the recommended template for anyone building personal archives, longitudinal tracking, or coaching dashboards that must survive across sessions and scripts.

**Key concepts**: Full `results.py` API surface, profile-linked Saved*Run artifacts, geometric-aware rebuilds via the wired builders, service persistence helpers, discovery & loading of prior runs.

### 09 — Geometric + Multi-Variable Sensitivity with Full Persistence (Flagship) (`09_geometric_multi_var_persistence.py`)
**New (current pinnacle combined demonstration)**. The flagship script for the intersection of the two most advanced capabilities:

- Side-by-side **static tables vs live geometric** multi-variable sensitivity (bench load × grip and squat load × stance) on the *exact same saved profile*.
- Both the convenient `use_geometric=True` builder path *and* direct calls to `estimate_bench_sternal_ma` / `estimate_squat_glute_ma` inside rebuild factories.
- Full persistence of every surface as `SavedSensitivityRun` objects (plus loading for post-hoc static-vs-geo delta analysis).
- Rich ASCII interaction views + a comprehensive reusable "personal geometric optimizer" report.

This script shows exactly how to answer real coaching questions today ("For *my* proportions, does wider grip help or hurt sternal demand more at higher loads?") while automatically archiving the full data for future comparison.

**Key concepts**: Parallel modeling fidelity studies (static vs geometric), profile + `run_profile_multi_sensitivity` + manual `save_sensitivity_run`, loading persisted runs for longitudinal reasoning, deepest current integration of `reference/geometric` + `sensitivity_multi` + persistence.

## How to Run Any Example

```bash
python examples/01_program_level_insights.py
python examples/05_geometric_moment_arm_prototype.py   # geometric prototype + v0.4 multi-position (Part 6)
python examples/06_multi_variable_sensitivity.py       # multi-var + geo combo
python examples/07_persistence_profiles_and_batch.py   # profiles + batch (anthropometry focus)
python examples/08_profile_persistence_workflows.py    # full Saved*Run + helpers + geo multi-var
python examples/09_geometric_multi_var_persistence.py  # flagship static-vs-geo + persistence
```

Each script:
- Is fully self-contained and heavily commented (notebook style)
- Uses `AnalysisService` (and `default_service` where convenient) as the **primary API**
- Pulls real numbers from `reference/moment_arms.py` (and `geometric.py` + builder auto-wiring for 05/06/08/09)
- Includes a prominent, detailed Limitations section
- Writes a high-quality report to `examples/outputs/`

## Latest Capabilities Highlighted (08 + 09)

**Auto geometric wiring in builders (new convenience, used heavily in 08/09)**  
`service.build_position("squat", load_kg=155, stance_width_cm=48, femur_cm=..., use_geometric=True)` (or via the profile helpers) now automatically prefers the anthropometry-driven estimators for supported regions (sternal pecs on bench; glute + quad on squat). Pass `use_geometric=False` to force static tables. This is the practical, low-boilerplate path going forward.

**Combined geometric + multi-var inside persisted profile workflows (08 & 09 flagship)**  
Custom `rebuild_multi` callables (or the ones supplied to `run_profile_multi_sensitivity`) that call the builders with `use_geometric=True` + the swept variables (grip/stance) give you continuously varying, body-specific moment arms on every point of every surface — all automatically saved and retrievable later under your profile name.

**Complete enhanced persistence layer (08 primary, 09 heavy user)**  
Everything beyond basic anthropometry profiles is now first-class:
- `SavedAnalysisRun`, `SavedSensitivityRun` (single + multi-var), `SavedCompareRun`
- `AnalysisService.save_current_analysis`, `run_and_save_profile_sensitivity`, `run_profile_multi_sensitivity`
- `run_profile_analysis`, `run_profile_compare`, `save_profile_with_run`, `list_all_for_profile`
- Robust JSON round-tripping + `list_saved_runs` / `load_*_run` discovery
- CLI symmetry (`fiberforce profile save-result`, `multi-sens`, `compare-runs`, `list-results`)

All of this was previously described as "future" or "enhanced" in older docs and Example 07. It is now fully implemented, tested via the CLI, exported at the top level, and exercised by 08 and 09.

## Important Shared Limitations (All Examples)

See the Limitations section at the end of every script (and the dedicated `docs/limitations-deep-dive.md`).

Highlights (current complete state):
- Absolute force values are currently ~100× too low (known torque / cm vs / m bug in `calculations/peak_force.py`).
- All calculations are static peak force at one chosen position only.
- **Geometric MA is a prototype** (primarily bench sternal pecs + squat glute/quad via the estimators and the new builder integration; deadlift, OHP heads, most other regions/variations, and many positions still fall back to static tables even with `use_geometric=True`).
- Multi-var sensitivity is currently sequential sweeps (pragmatic foundation delivered; true 2D grids + heatmaps + pandas/seaborn surfaces are the obvious small next layer on this architecture — the data is already there in the persisted `SensitivityResult` objects).
- Many simplifications (single-joint, fixed length-tension 0.85, no velocity, reference data synthesized, etc.).

**Relative comparisons, trends, slopes, interaction effects, and deltas (including static-vs-geometric differences) are trustworthy and useful today.**

## Relationship to Core Code

- `src/fiberforce/analysis/service.py` — The high-level facade (AnalysisService) these examples champion as primary. Full 4-lift parity, `sensitivity_multi`, `compare`, `build_position` (with `use_geometric`), `save_current_analysis`, passthroughs to profile multi-sens, etc.
- `src/fiberforce/examples.py` — Builder factories with deep `use_geometric` + `ReferenceData.estimate_moment_arm` integration for bench & squat (the "auto-wiring").
- `src/fiberforce/reference/geometric.py` + `data.py` — The geometric prototype + `ReferenceData.estimate_moment_arm` integration point (bench sternal + squat glute/quad).
- `src/fiberforce/calculations/sensitivity.py` — `SensitivityAnalyzer.run` + `run_multi` implementation.
- `src/fiberforce/results.py` — The full enhanced persistence implementation (`Saved*Run` dataclasses, save/load, `run_profile_*` helpers, JSON round-tripping).
- `src/fiberforce/profiles.py` — Anthropometry persistence + the higher `save_profile_with_run` / `list_all_for_profile` integration points.
- `src/fiberforce/visualization.py` — Plotting + ASCII fallbacks.
- `docs/usage-guide.md`, `docs/how-the-model-works.md`, `docs/advanced-patterns.md`, `docs/limitations-deep-dive.md` — Required reading (updated May 2026 to reflect the complete state including 08/09 and the full persistence + builder geometric wiring).

## Contributing / Extending

These examples (especially the newest 08 and 09) are the best places to prototype new features:
- True 2D sensitivity grids + heatmaps on top of the existing `SensitivityResult` lists
- Program-level accumulation / fatigue engines that consume persisted runs
- Full geometric auto-defaulting + more regions/lifts in the estimators
- Richer longitudinal tooling that correlates saved runs with external training logs
- OHP- or deadlift-specific geometric studies

When you improve the core (e.g. expanding geometric coverage, adding grid support, or enhancing the persistence model), update the corresponding example(s), their generated reports, the Limitations sections in the scripts, and this README + the four docs.

---

Generated / polished as part of the final docs + examples expansion for the post-massive / wiring + persistence phase of FiberForce (May 2026). All nine examples now showcase `AnalysisService` as primary, full lift parity (including OHP), the geometric MA prototype + convenient builder integration, multi-var sensitivity, the *complete* enhanced persistence layer (`results.py` + profile linking), and production-grade reporting patterns. Absolute honesty about limitations is maintained throughout.
