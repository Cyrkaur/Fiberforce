# FiberForce Usage Guide

**Current version**: 2.0.0 (v2 — The Clickable Icon App) — Full imperial (inches/ft/lbs) default + ft-lb torque + dynrom/continuous ROM. 8 lifts. AnalysisService + recipes. Top-tier GUI now primarily launched by double-clicking the icon (DMG + self-contained .app with custom .icns produced by scripts/build_macos_app.sh). Real persisted History, .interpret()/.insight(), geometric + continuous. Launch docs updated for icon-first + preserved bulletproof dev path (see README). See imperial/torque + dynrom sections below.

## Current Capabilities (Post-Massive Phase + Continuation + Persistence Completion)

**Primary recommended interface**: `AnalysisService` (library) and the thin CLI that sits on top of it.

- **`analyze` / `sensitivity` / `compare` / `build_position`**: Unified high-level API for all lifts.
- **`profile`**: Full persistence commands — `save`, `load`, `list`, `run` (anthropometry) + the complete enhanced layer: `save-result`, `multi-sens` (profile-based multi-var + auto-persist of `SavedSensitivityRun`), `compare-runs`, `list-results`, `save-config`, etc. All artifacts are profile-linked JSON under `~/.fiberforce/results/`.
- **Visualization**: First-class (`--plot` / `--save-plot` on sensitivity/compare; dedicated `visualize` command). Matplotlib when available + rich tables + high-quality pure-ASCII sparklines/bars for headless/CI/no-display environments.
- **`AnalysisService`**: The **sole recommended high-level Python API**. Unifies calculators, builders (all four lifts with rich aliases + `use_geometric` support for bench sternal and squat glute/quad), single + multi-var sensitivity, compare, reference data (including geometric estimators), subject factories, result enrichment, and persistence helpers (`save_current_analysis`, `run_profile_multi_sensitivity`, etc.).
- **Geometric moment arm prototype** (new + wired): `ReferenceData.estimate_moment_arm` + direct functions in `fiberforce.reference.geometric` for bench sternal pecs (humerus + biacromial + grip + torso depth) and squat glute/quad (femur + tibia + stance). Now conveniently available via `service.build_position(..., use_geometric=True, ...)` (or explicit `use_geometric=False` to force static tables). Can also be wired into custom sensitivity rebuilds (see Examples 05, 06, **08**, and the flagship **09**).
- **Full enhanced persistence**: `SavedAnalysisRun`, `SavedSensitivityRun` (multi-var supported), `SavedCompareRun`, robust JSON round-tripping, profile foreign-key linking, `run_profile_*` helpers, `save_profile_with_run`, `list_all_for_profile`, etc. This layer is production and is the foundation for longitudinal and coaching use.
- **Library power**: Full Python API for custom scripts, multi-lift comparisons, custom moment arms, batch profile analysis, geometric-driven sweeps, multi-var interaction studies, persisted result loading, and rapid experimentation.
- **Confidence + notes**: Every `MuscleForceResult` carries explicit `confidence_level` (`high (user-influenced)`, `medium (reference data)`, `low (defaults used)`, error states) plus detailed notes (including MA source when geometric estimators were used).
- **Personalization**: Pass segment lengths (`--femur`, `--humerus`, `--biacromial`, `--tibia`, etc.) or load a saved profile. Geometric prototype + builder wiring makes many of those measurements mechanically active in both direct analyses and sensitivity studies today.
- **Extensive validation**: Core library + AnalysisService + all new builders (deadlift, full OHP) + geometric + multi-var paths + the complete persistence layer are covered.

**Unit handling note (updated 0.6)**: The previous cm-vs-m torque scaling bug in the core calculator has been fixed. Absolute force values are now physically reasonable. 

Relative comparisons, deltas, and directional effects were already trustworthy. Remaining modeling limitations are documented in [limitations-deep-dive.md](./limitations-deep-dive.md).

## Quick Start (v1 — Use the Bulletproof Block)

**IMPORTANT**: This project lives at a specific volume path on the dev Mac. Past sessions failed with PATH, "editable mode" from wrong dir, and GUI crashes when the cd/venv/activate sequence was skipped. Always follow the hardened setup.

```bash
# === MANDATORY FIRST STEPS (volume workspace + venv) ===
cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[gui,viz]"

# Now safe
fiberforce --help
fiberforce demo
fiberforce list-lifts
fiberforce list-regions
fiberforce smoke   # v1 imperial + ft-lb + interpret + program verifier
```

For the **full GUI** (v2.0 primary: the clickable icon app):
```bash
# Build once (after venv + pip -e ".[gui]"):
bash scripts/build_macos_app.sh
# Then open the DMG, drag FiberForce.app to /Applications, and double-click the icon.
# (No terminal or python required for coaches/end users after the one-time build.)
```

Dev / fast iteration still works:
```bash
fiberforce gui
# or
python -m fiberforce.gui
```

**Library quickstart (recommended)**:

```python
from fiberforce import AnalysisService
from fiberforce.profiles import save_anthropometry

service = AnalysisService()
print(service.describe())

# Create + save your profile once (rich measurements unlock geometric)
subj = service.create_subject_from_measurements(
    name="You",
    humerus_length_cm=33.0, forearm_length_cm=26.0,
    biacromial_width_cm=40.0, torso_depth_at_chest_cm=23.0,
    femur_length_cm=44.0, tibia_length_cm=38.5,
)
save_anthropometry(subj.anthropometry, "my-profile")

# One-line deadlift analysis (full parity) — or use geometric on supported lifts
pos = service.build_position("deadlift", load_kg=170, variation="sumo", target_region_name="Upper fibers")
result = service.analyze(subj, pos)
print(result.results[0])

# Geometric-enabled bench (latest convenient path)
pos_bench = service.build_position(
    "bench", load_kg=105, grip_width_cm=60,
    humerus_cm=33.0, biacromial_cm=40.0, torso_depth_cm=23.0,
    use_geometric=True
)
print(service.analyze(subj, pos_bench).results[0])
```

**CLI quickstarts (v1 — --load-lbs + imperial first)**:
- `fiberforce analyze deadlift --load-lbs 385 -v sumo --target "Upper fibers"`
- `fiberforce sensitivity squat --variable load_kg --start 120 --end 180 --step 10 --plot  # (load_kg still accepted; --load-lbs preferred for US)`
- `fiberforce compare deadlift --a conventional --b sumo --load-lbs 385 --plot`
- `fiberforce profile save me --femur 17.3 --tibia 15.4 --humerus 13.4  # inches supported in profile save`
- `fiberforce profile run me --lift squat --load-lbs 315`
- `fiberforce profile multi-sens me --lift bench --variables "load_lbs:225,275,315" "grip_width_cm:48,58,68" --target "Sternal fibers"`  (persists full SavedSensitivityRun)

Full quickstarts, recipes, and advanced patterns live in the documentation (especially the new Examples 08 and 09 + updated advanced-patterns.md).

## Example 1: Deadlift — Conventional vs Sumo (Full Parity)

**Training question**: At the floor with 180 kg, how does the model shift demand between glute max upper fibers and lumbar erectors between conventional and sumo for *your* proportions?

(See detailed code in the original version of this guide + rich patterns in `examples/04_deadlift_vs_squat_posterior_chain.py` and `examples/07_persistence_profiles_and_batch.py`. The new 08/09 also exercise deadlift via the profile persistence helpers.)

## Example 2: Sensitivity (Single + Multi-Variable) + Geometric

**Training question**: How does sternal pec demand scale with load *and* grip width? What happens on squat when we vary both load and stance for a long-femur lifter, using live geometric MA estimators?

```python
# See the full combined geometric + multi-var + persistence treatment in
# examples/06_multi_variable_sensitivity.py (foundation)
# examples/08_profile_persistence_workflows.py (integrated with Saved*Run)
# examples/09_geometric_multi_var_persistence.py (flagship static vs geo parallel surfaces)
```

The modern recommended pattern (used in 08/09) is:

```python
pos = service.build_position("bench", 110, grip_width_cm=58, use_geometric=True, ...)
# or inside a rebuild_multi for sensitivity:
return service.build_position(lift, load_kg=load, grip_width_cm=g, use_geometric=True, ...)
```

## Example 3: Full Personal Setup Audit with Profiles + Full Persistence (Current Recommended Workflow)

```bash
# Save your real data once (rich measurements recommended)
fiberforce profile save myname-2026 --femur 44.5 --tibia 38.5 --humerus 34 --biacromial 40.5 --torso-depth 23

# Run analyses directly from the saved profile (any lift)
fiberforce profile run myname-2026 --lift deadlift --load-kg 180 -v sumo --target "Upper fibers"
fiberforce profile run myname-2026 --lift ohp --load-kg 72 -v standing --target "Anterior"

# Profile-based multi-var sensitivity (auto-persisted as SavedSensitivityRun)
fiberforce profile multi-sens myname-2026 --lift squat \
  --variables "load_kg:140,160,180" "stance_width_cm:30,50,70" \
  --target "Upper fibers"

# Later exploration
fiberforce profile list-results --profile myname-2026
fiberforce profile load-result <run_id>
```

**Or in Python (modern pattern — see Examples 07/08/09)**:

```python
from fiberforce.profiles import load_anthropometry
from fiberforce import AnalysisService
from fiberforce.results import run_profile_multi_sensitivity, list_saved_runs, load_sensitivity_run

service = AnalysisService()
anthro = load_anthropometry("myname-2026")
subj = service.create_subject_from_measurements(name="me", **{...from anthro...})

# Simple + persisted
pos = service.build_position("squat", 160, use_geometric=True, femur_cm=anthro.femur_length_cm, ...)
res, path = service.save_current_analysis(subj, pos, profile_name="myname-2026")

# Advanced geometric multi-var persisted
run, path = run_profile_multi_sensitivity(
    "myname-2026", "squat",
    variables=[("load_kg", [140,180]), ("stance_width_cm", [35,65])],
    target_region_name="Upper fibers",
    # optional custom rebuild using use_geometric or direct estimators...
)
print(list_saved_runs(profile_name="myname-2026"))
loaded = load_sensitivity_run(run.run_id)
```

See the nine runnable examples (especially the new **08** and **09**) for complete templates.

## Example 4: OHP Full Parity Exploration

```python
pos = service.build_position("ohp", 70, "standing", "bottom", "Anterior")
# ... or seated / lockout / different heads (Lateral, Posterior) / triceps
```

Full support exists for standing/seated/strict variations + bottom/mid/lockout positions + anterior/lateral/posterior delts + triceps.

## Example 5: Multi-Position Analysis (v1) — Force Demand Shifts for Programming Decisions

**Training question**: "Where in the squat is my glute max upper fibers most stressed for a given variation and load? How should that shape my choice of pauses, depth emphasis, or high-bar vs low-bar selection?"

v1 has full support for discrete multi-position ("limited dynamic") snapshots via the high-level helpers and the `position=` parameter. The same lifter + load is analyzed at bottom / mid / top (or lockout), with position-aware joint angles and (when `use_geometric=True`) live MA adjustment in the geometric estimators. Imperial units and ft-lb torque outputs are used throughout.

```python
from fiberforce import AnalysisService
from fiberforce.profiles import load_anthropometry

service = AnalysisService()
anthro = load_anthropometry("my-real-profile")  # or create_subject_from_measurements(...)
subj = service.create_subject_from_measurements(
    name="You", femur_length_cm=anthro.femur_length_cm, tibia_length_cm=anthro.tibia_length_cm
)

positions = ["bottom", "mid", "top"]

# v1 convenience helpers (recommended)
multi_pos = service.build_multi_position(
    "squat", positions,
    load_kg=145.0,
    variation="high_bar",
    target_region_name="Upper fibers",
    femur_cm=44.0, tibia_cm=39.0,
    use_geometric=True,          # position hint flows through to geometric MA
)
# → list[AnalyzedPosition], order preserved, each fully populated

analyses = service.analyze_multi_position(
    subj, "squat", positions,
    load_kg=145.0,
    variation="high_bar",
    target_region_name="Upper fibers",
    femur_cm=44.0, tibia_cm=39.0,
    use_geometric=True,
)
# → list[AnalysisResult] (one per position)

print("Glute demand across squat ROM (programming insight):")
for pos_name, res in zip(positions, analyses):
    r = res.results[0] if res.results else None
    force = r.peak_force_newtons if r else 0
    ma = r.moment_arm_used_cm if r else "?"
    print(f"  {pos_name:8} → {force:6.1f} N  (MA {ma} cm)")

# Typical interpretation (relative deltas are trustworthy):
# - Highest glute demand often at bottom (deep hip flexion → favorable MA)
#   → Pause squats, tempo, or full-ROM emphasis for glute bias.
# - Mid/top lower glute contribution → better for quad/lockout focus or
#   low-bar variation if the goal is different regional stress.
# Use the exact same pattern for deadlift (bottom/mid/top), bench, or OHP.
```

**Also available**:
- `position="bottom"` (or "mid"/"top"/"lockout") on any single `service.build_position("squat", ..., position=...)` call.
- Direct builder functions accept the same kwarg.
- CLI: `fiberforce multi-pos squat --positions bottom,mid,top -l 145 -v high_bar -t "Upper fibers"`

Full runnable treatment (with richer visualization + high/low-bar cross-comparison at every depth) lives in `examples/05_geometric_moment_arm_prototype.py` (Part 6). A focused program-level ROM insight block was also added to `examples/01_program_level_insights.py`.

This is the cleanest way today to answer "where does this muscle do the most work in the lift?" for evidence-informed programming.

## Reading Results: Confidence, Notes, and the Unit Reality

Every result includes:
- `peak_force_newtons` + rough kgf (treat kgf as directional only)
- `confidence_level` + rich `notes` (including when geometric MA was used and which estimator)
- The `AnalysisResult` / `SensitivityResult` wrappers add position description and context

## Philosophy and How to Get Value Immediately

FiberForce is deliberately honest. The absolute numbers are not yet physiologically realistic. Many exciting capabilities (full geometric auto-defaulting + expanded coverage, true multi-joint resolution, dynamic ROM, richer architecture models, program-level fatigue, 2D grid visualization) are ahead.

**What you can do powerfully today**:
- Use profiles + the full persistence layer for repeatable personal workflows that survive sessions
- Combine all four lifts (bench + squat + deadlift + OHP) in the same script for regional bias insights
- Use geometric estimators inside your own sensitivity rebuilds (or the convenient `use_geometric=True` builder flag) — see Examples 05/06/08/09
- Persist every meaningful surface or audit so future you can load exact prior conditions

Run the commands. Look at the slopes, deltas, interaction effects, and static-vs-geometric differences. Question the absolutes. Save your real measurements in profiles **now**. Contribute better moment arm data when you can.

The same clean architecture (`AnalysisService` as the single source of truth, pluggable calculators, reference layer with geometric direction + builder integration, rich domain models + first-class persistence) powers the current feature set and will make future versions (deeper geometric coverage, better multi-joint handling, etc.) dramatically more accurate without breaking your existing scripts and notebooks.

## Further Reading & Quick References

- [How the Model Works](./how-the-model-works.md) — core concepts, data flow, shorter assumption list, geometric & multi-var sections
- [Advanced Patterns](./advanced-patterns.md) — deep library usage, `sensitivity_multi` recipes, geometric integration (builder + direct), combining lifts, **the complete persistence layer with Saved*Run examples**, full custom Pose construction
- [Limitations Deep Dive](./limitations-deep-dive.md) — full assumptions + "when not to use" + unit bug + current geometric scope (bench sternal + squat glute/quad only)
- `fiberforce --help` and individual command help for the latest CLI surface (analyze/sensitivity/compare/profile/visualize + dedicated deadlift/ohp sugar + the full profile persistence subcommands)
- **Runnable examples** (the best way to learn — nine total):
  - `examples/05_geometric_moment_arm_prototype.py`
  - `examples/06_multi_variable_sensitivity.py` (geo + multi combo)
  - `examples/07_persistence_profiles_and_batch.py`
  - `examples/08_profile_persistence_workflows.py` (full Saved* + helpers + geo multi-var)
  - `examples/09_geometric_multi_var_persistence.py` (flagship combined geometric multi-var surfaces + persistence + static-vs-geo loading)
  - Plus 01–04 (program, personalization, grip sensitivity, posterior chain)

Source: `src/fiberforce/analysis/service.py`, `examples.py` (builders + geometric wiring), `visualization.py`, `profiles.py`, `results.py`, `reference/geometric.py`, `reference/data.py`, `reference/moment_arms.py`.

Start simple (demo + one sensitivity with `--plot` + save a profile). Then move to the advanced patterns document and the nine examples for the real power.

---

*FiberForce is deliberately transparent and scoped. Use it for relative comparisons and hypothesis generation while respecting its current limitations.*
