# FiberForce — Current Capabilities & Next Frontier (0.5 + 0.6 polish snapshot)

**Date**: 2026-05-27  
**Version context**: 0.5.0-dev (Mid Expansion complete: multi-position + WeeklyProgram/TrainingSession + geometric 4-lift + rich persistence) + active 0.5 → 0.6 cleanup & consistency pass  
**Purpose**: Honest, concise snapshot for the user / future contributors / next autonomous phase. This is the primary handoff artifact on the path to v1.0.

---

## Rock-Solid (High Confidence for Intended Use)

- **AnalysisService** as the single source of truth
  - `build_position(lift, ...)` and `build_multi_position(...)` for all 4 primary lifts with full aliasing and position support.
  - `analyze(subject, position)`, `analyze_multi_position(...)`, `sensitivity(...)`, `sensitivity_multi(...)`, `compare(...)`.
  - Full program-level accumulation (`accumulate_regional_stress`, `accumulate_regional_volume`, `summarize_regional_accumulation`).
  - All CLI commands (top-level + `profile` tree + `multi-pos`) are thin, correct callers of the service.
  - `create_subject_from_measurements(...)` + profile loading + geometric forwarding.

- **Core domain models** (anthropometry, muscle architecture, Pose, AnalyzedPosition, Subject, LiftConfiguration, ExternalLoad, etc.)
  - Strong validation, helpful error messages, dataclasses with `from __future__ annotations`.

- **ReferenceData + static tables**
  - Full 4-lift coverage (moment arms + load arms + parallel confidence metadata tables: high/medium/low/estimated).
  - Rich query API: `get_moment_arm_with_confidence`, `list_available_*`, `describe()`.

- **Rich persistence layer** (`results.py` + `profiles.py`)
  - `SavedAnalysisRun`, `SavedSensitivityRun` (including `is_multi_var()`), `SavedCompareRun`.
  - Versioned JSON with recursive stdlib serializer.
  - Profile as foreign key + `run_profile_multi_sensitivity`, `save_profile_with_run`, `list_all_for_profile`.
  - CLI: `profile save-result`, `multi-sens`, `load-result`, `compare-runs`, `list-results`.

- **Length-tension modeling**
  - Real heuristic using `MuscleArchitecture` (PCSA, optimal fiber length, pennation, tendon slack) + joint angle + excursion.

- **Visualization**
  - Matplotlib optional + excellent ASCII/rich fallback (sparklines, bars).
  - Wired into sensitivity/compare commands and library helpers.

- **Test surface**
  - 72 focused, fast, green tests (geometric paths, multi-var sensitivity with custom rebuilders, full persistence roundtrips, service orchestration, OHP parity).
  - All use real public contracts + `tmp_path` isolation where needed.

- **CLI surface**
  - `analyze`, `sensitivity`, `sensitivity-multi` (with `--use-geometric` default on + 4-lift rebuild support), `compare`, `visualize`.
  - Full `profile` subcommand tree with persistence.
  - Dedicated `deadlift` and `ohp` top-level commands (thin but functional service wrappers added in 0.3.0-dev baseline hygiene pass).
  - Good error handling and tips.
  - Note: CLI now much closer to Python API parity after Phase 1 fixes (sensitivity family, save-config, dedicated lift commands). Some minor target-matching and discovery flakiness remains for non-bench lifts.

- **9 advanced runnable examples** (with generated reports in `examples/outputs/`)
  - 08 and 09 are the current flagships for combined geometric + multi-var + full persistence workflows on real profiles.

- **Documentation**
  - Brutally honest `limitations-deep-dive.md`.
  - Strong `how-the-model-works.md`, `usage-guide.md`, `advanced-patterns.md`.
  - Fresh retrospective in `CHANGES.md` + updated baseline in `GAMEPLANS.md`.
  - This `CURRENT_CAPABILITIES.md` file.

---

## Strong but Prototype / Directional (Excellent for Exploration & Sensitivity)

- **Geometric moment arm estimators** (`reference/geometric.py`)
  - Now covers all 4 primary lifts (bench sternal pecs, squat glute/quad, deadlift glute + hamstring, OHP anterior delt + triceps).
  - Preferred path in ReferenceData / builders when `UserAnthropometry` with relevant measurements is supplied.
  - Returns "estimated (geometric prototype)" confidence + values directionally consistent with static tables.
  - Transparent math (trig projections, stance/grip/flexion effects, simple scaling from segment lengths).
  - **Use for**: relative comparisons, sensitivity to your actual limb lengths / grip / stance, educational insight.
  - **Do not use for**: absolute clinical torque predictions or coaching prescriptions without further validation.

- **Multi-position (limited dynamic) + Program-level APIs — 0.5 Mid Expansion**
  - `AnalysisService.build_multi_position(...)` and `analyze_multi_position(...)` returning rich `MultiPositionResult` (aggregates, deltas, geo-vs-static provenance, full duck-typing for accumulators).
  - `TrainingSession` + `WeeklyProgram` dataclasses in `results.py` with `.compare()`, accumulation delegation, and reporting.
  - Full integration of multi-position results into regional stress/volume accumulation.
  - CLI: `fiberforce multi-pos ...` with rich table + summary + `--plot` + `--save-result`.
  - **Use for**: ROM curves, sticking point analysis, program comparison, weekly regional stress modeling.

- **Multi-variable sensitivity** (`SensitivityAnalyzer.run_multi` + service + CLI)
  - Sequential sweeps with custom `rebuild_multi` factories.
  - Live geometric integration when anthropometry + `--use-geometric`.
  - Persistence of full multi-var `SavedSensitivityRun` objects.
  - **Use for**: understanding trade-offs (e.g. "how much does increasing femur length change required quad force at a given load?").
  - **Limitation**: Still sequential (not a true grid); rebuild factories are heuristic.

- **OHP and certain deadlift variations**
  - Full builder + service + reference table support + CLI commands.
  - Geometric now adds directional MA estimates for key regions.
  - Still lighter real-world data density than bench/squat in some reference tables.

- **Personalization via profiles + anthropometry**
  - Extremely strong when the user supplies real measurements (humerus, forearm, biacromial, femur, tibia, torso depth, biiliac, etc.).
  - Geometric estimators scale directly with those measurements.

---

## Data-Limited / Explicitly Future (Out of Current Scope or Thin)

- Full dynamic range-of-motion / angle-continuous moment arms (current work is static key positions only — the original scoped intent).
- True program-level accumulation, fatigue, or weekly volume modeling (examples can simulate manually; no engine yet).
- Clinical / in-vivo validation of the geometric estimators or length-tension factors (these are educational prototypes).
- More muscle regions per lift with high-quality geometric or literature data (many "other" muscles still fall back to coarse estimates).
- GUI / app packaging (Briefcase + PySide6 skeleton exists but paused; not part of current backend focus).
- Export formats beyond the current JSON (CSV/MD diffing of saved runs is a natural next small win).
- Performance at scale (not a concern yet — everything is fast).

**Unit handling**: The previous cm-vs-m torque scaling bug was fixed during the 0.5 → 0.6 polish phase. Absolute force values are now in the correct physical range. Relative comparisons and directional effects were already reliable. See limitations-deep-dive.md for remaining modeling caveats.

---

## Recommended Safe Usage Patterns (v0.3.0-dev)

1. **Exploration / personalization studies** — Use `AnalysisService` + a real `UserAnthropometry` profile + geometric-enabled builders. Run `sensitivity` and `sensitivity-multi` heavily. Persist everything with `profile multi-sens` / `save-result`.

2. **Program-level insight** — Run the advanced examples (especially 08 and 09) and modify them. They demonstrate the current ceiling.

3. **Teaching / communication** — The ASCII visualization + rich reports from the examples are excellent for coaches/athletes.

4. **Never** — Treat geometric MA values or peak force numbers as absolute prescriptions without additional data sources and expert review.

**Quick start (library)**:
```python
from fiberforce import AnalysisService
from fiberforce.models import UserAnthropometry

service = AnalysisService()
anthro = UserAnthropometry(humerus_length_cm=34.0, femur_length_cm=43.0, ...)  # your real measurements
subj = service.create_subject_from_measurements(anthropometry=anthro)
pos = service.build_position("squat", load_kg=140, variation="high_bar", target_region_name="glute_max", use_geometric=True)
res = service.analyze(subj, pos)
print(res.results[0].peak_force_newtons)
```

---

## What "Next Step Version" (Stable 0.3.x) Would Ideally Contain

- Complete verification of all 9 examples + exhaustive CLI matrix with zero surprises.
- ReferenceData + geometric cross-validation notes / simple calibration hooks.
- Persistence power-ups (saved-run diff, structured export, batch profile tools).
- One or two more "killer" examples that feel like real training decisions.
- Even denser test coverage on the geometric estimators themselves.
- The Current Capabilities snapshot (this document) kept up to date after every wave.

---

**Bottom line**: As of this 0.3.0-dev snapshot, FiberForce is a credible, well-tested, well-documented library for personalized static-position biomechanical analysis of the four primary lifts, with a working geometric direction for anthropometry and excellent persistence/CLI ergonomics. It is already far more capable than the original v0.1–v0.2 scope anticipated.

The foundation for deeper future work (dynamic modeling, program engines, validation studies) is solid.

Use it. Break it. Tell us what you learn.

---

*This document was produced autonomously during the "next step version" overdrive push as the primary handoff artifact. It will be updated after every significant wave.*