# Advanced Patterns with FiberForce

**Real-world library usage of AnalysisService (the primary interface), custom single- and multi-variable sensitivity sweeps, geometric moment arm integration (including the convenient builder `use_geometric` path), multi-lift analysis, the full enhanced persistence layer (Saved*Run + profile linking), and full custom construction.**

This guide assumes you have read the [Usage Guide](./usage-guide.md) and [How the Model Works](./how-the-model-works.md). It focuses on the Python library (the most powerful interface) rather than the CLI. The `AnalysisService` is the **recommended and primary high-level entry point** for all serious work — every major capability (analyze, sensitivity, sensitivity_multi, compare, build_position for all four lifts, geometric access via builders or direct estimators, and the complete persistence APIs) flows through it or the tightly integrated `results` / `profiles` modules.

## Why Use the Library Over the CLI?

The CLI is excellent for quick checks and exploration (and now has dedicated `deadlift` / `ohp` commands plus full service backing). The library shines for:
- Custom rebuild logic in sensitivity analysis (varying femur length *and* load simultaneously, or grip width with live geometric MA)
- Combining multiple lifts into a single "program insight" or personal audit script (now trivial with full OHP/deadlift parity)
- Batch processing across saved profiles + geometric or multi-var studies, with full result persistence
- Integrating visualization directly into notebooks or reporting pipelines
- Building higher-level tools (personal "setup optimizer", training log correlator, weekly dashboard that loads prior SavedSensitivityRun objects)
- True longitudinal work: save every important analysis or sensitivity surface with rich metadata and retrieve it weeks later without re-entering measurements

All examples below use the current complete post-massive + wiring + persistence phase architecture with `AnalysisService` as the single source of truth, full four-lift parity, geometric prototype + builder integration, multi-var sensitivity, the full `results.py` persistence layer, visualization, and profiles.

## 1. AnalysisService as Your Primary Interface (Use This Everywhere)

```python
from fiberforce import AnalysisService, default_service
from fiberforce.models import Subject, UserAnthropometry

# Recommended: create your own (injectable for testing / custom calculators)
service = AnalysisService()

# Or use the global convenience instance
# service = default_service

# Quick subject creation from measurements (or load a profile)
subject = service.create_subject_from_measurements(
    name="Alex Powerlifter",
    humerus_length_cm=34.5,
    forearm_length_cm=27.0,
    biacromial_width_cm=42.0,
    femur_length_cm=44.0,
    tibia_length_cm=39.5,
    torso_depth_at_chest_cm=23.0,
)

print(service.describe())
# Shows: Sensitivity (single + multi): Yes
#        Full lift parity: bench | squat | deadlift (conv+sumo) | ohp (...)
#        Persistence: Full via fiberforce.results + profiles (Saved*Run, profile-based multi-var)
#        CLI primary backend: Yes
```

### Basic Analyze + Full Lift Parity Workflow

```python
# All four lifts via the exact same method (aliases supported)
pos_dl   = service.build_position("deadlift", 180, "conventional", "Upper fibers", femur_cm=44)
pos_ohp  = service.build_position("ohp", 70, "standing", "bottom", "Anterior")
pos_squat = service.build_position("squat", 160, "low_bar", "Upper fibers")
pos_bench = service.build_position("bench", 105, "incline_30", "Sternal fibers")

result = service.analyze(subject, pos_dl)
for r in result.results:
    print(f"{r.muscle_region}: {r.peak_force_newtons:.1f} N (conf: {r.confidence_level})")
print("Position:", result.position_description)
```

The returned `AnalysisResult` includes the raw `MuscleForceResult` list plus rich metadata. Use `service.compare(...)` for zero-friction two-way structured results ready for `plot_comparison`.

## 2. Custom Sensitivity Analysis — Single + Multi-Variable (The Real Power)

The built-in sensitivity in the CLI and basic `service.sensitivity()` are great for single-variable sweeps. For realistic coaching questions you usually need **custom rebuild functions**.

### Single-Variable (Still Extremely Useful)

See Example 03 for grip + incline bench work and the basic patterns in the usage guide.

### Multi-Variable Sequential Sweeps (Foundation + Geometric Power)

```python
from fiberforce.models import KNOWN_MUSCLE_REGIONS

glute_upper = next(r for r in KNOWN_MUSCLE_REGIONS if "Upper fibers" in r.region_name and "Glute" in r.muscle_name)

def rebuild_squat_multi(base, params):
    load = params.get("load_kg", 150)
    stance = params.get("stance_width_cm", 45)
    return service.build_position(
        "squat", load_kg=load, stance_width_cm=stance,
        femur_cm=44.0, tibia_cm=39.0,
        target_region_name="Upper fibers",
        use_geometric=True,   # latest convenient path
    )

multi = service.sensitivity_multi(
    subject=subject,
    base_position=base_squat,
    variables=[("load_kg", [140, 160, 180]), ("stance_width_cm", [30, 50, 70])],
    target_region=glute_upper,
    rebuild_multi=rebuild_squat_multi,
)
```

See Examples 06, 08, and especially **09** (the current flagship) for rich static-vs-geometric parallel multi-var surfaces persisted under a profile.

## 3. Combining Lifts for Program-Level Insight (Now with Full Parity + Profiles)

One of the highest-value uses of the library is running the *same* lifter (from a saved profile) across multiple movement patterns.

```python
from fiberforce.profiles import load_anthropometry
from fiberforce import AnalysisService
from fiberforce.models import Subject

anthro = load_anthropometry("my-real-profile")
subj = Subject(anthropometry=anthro)

service = AnalysisService()
lifts = ["bench", "squat", "deadlift", "ohp"]
# ... build positions, analyze, aggregate ...
```

See `examples/01_program_level_insights.py`, `examples/04_...`, `examples/07_persistence_profiles_and_batch.py`, and the new **08/09** for production versions of this pattern (with ranking, ASCII viz, structured `service.compare`, dated reports, and persisted artifacts).

### v0.4 Extension: Multi-Position ROM Curves Inside Program Work (build_multi_position + position=)

Beyond whole-week aggregation across lifts, the v0.4 helpers let you drill into *how demand shifts inside a single lift's ROM* for the exact same athlete + load. This is gold for programming decisions:

- "Is the bottom the true high-glute zone for *my* proportions on high-bar?"
- "Should I program pause squats or pin squats to bias a weak point?"
- "Does low-bar move the peak demand higher in the ROM compared to high-bar?"

```python
# v0.4 pattern (add this inside any program-level or personalization script)
positions = ["bottom", "mid", "top"]

# One call builds the full set of position snapshots (angles + geo MA where enabled)
pos_snapshots = service.build_multi_position(
    "squat", positions,
    load_kg=145,
    variation="high_bar",          # or "low_bar"
    target_region_name="Upper fibers",
    femur_cm=44.0, tibia_cm=39.0,
    use_geometric=True,
)

analyses = service.analyze_multi_position(
    subj, "squat", positions,
    load_kg=145, variation="high_bar",
    target_region_name="Upper fibers",
    femur_cm=44.0, tibia_cm=39.0,
    use_geometric=True,
)

# Now compute deltas or render a "force curve"
for pos, a in zip(positions, analyses):
    force = a.results[0].peak_force_newtons if a.results else 0
    print(f"{pos:8}: {force:.1f} N  ← use for pause location / emphasis choice")
```

The same `position=` kwarg works on individual `build_position` calls or the four low-level `build_*_analyzed_position` functions. All geometric estimators (squat glute/quad, deadlift glute, etc.) accept the position hint and adjust flexion angles automatically.

**Recommended reading**: New dedicated Example 5 in usage-guide.md, the expanded multi-position block added to `examples/01_program_level_insights.py` (program-level ROM insight with concrete programming recs), and the deep treatment + ASCII curves in Example 05 (Part 6).

This turns FiberForce from "what is the force at my sticking point?" into "how does the entire strength curve look for *me* on this variation?"

## 4. The Full Enhanced Persistence Layer (Profiles + Saved*Run — Now Production)

Profiles (anthropometry only) were the starting point (Example 07). The complete system (`fiberforce.results`) adds first-class, versioned, profile-linked persistence for every analysis artifact:

```python
from fiberforce import AnalysisService
from fiberforce.profiles import save_anthropometry, load_anthropometry
from fiberforce.results import (
    SavedAnalysisRun, SavedSensitivityRun, SavedCompareRun,
    run_profile_multi_sensitivity, run_profile_compare,
    save_analysis_run, load_sensitivity_run, list_saved_runs,
    save_profile_with_run, list_all_for_profile,
    load_profile_for_analysis,
)
from fiberforce.reference.geometric import estimate_bench_sternal_ma

service = AnalysisService()
anthro = load_anthropometry("me")
subj = service.create_subject_from_measurements(name="me", **anthro_as_dict...)

# 1. One-shot analyze + persist
pos = service.build_position("bench", 110, use_geometric=True, humerus_cm=34, ...)
res, path = service.save_current_analysis(subj, pos, profile_name="me", notes="Post-deload test")

# 2. Profile-based multi-var sensitivity (with geometric rebuild) + auto-persist
def my_geo_rebuild(base, params):
    return service.build_position(
        "squat", load_kg=params["load_kg"], stance_width_cm=params.get("stance_width_cm"),
        femur_cm=anthro.femur_length_cm, use_geometric=True
    )

sens_run, sens_path = run_profile_multi_sensitivity(
    "me", "squat",
    variables=[("load_kg", [140,170]), ("stance_width_cm", [35,55])],
    target_region_name="Upper fibers",
    rebuild_multi=my_geo_rebuild,
    notes="My real proportions + stance experiment"
)

# 3. Later: discovery and loading
print(list_saved_runs(profile_name="me"))
loaded = load_sensitivity_run(sens_run.run_id)   # full multi-var data restored

# 4. Bundle everything
save_profile_with_run(anthro, "me-archive", analysis_run=SavedAnalysisRun(...))

# 5. High-level discovery
print(list_all_for_profile("me"))
```

**Key files & entry points**:
- `src/fiberforce/results.py` (Saved* dataclasses, all save/load/run_profile_* helpers, robust JSON)
- `AnalysisService.save_current_analysis`, `run_profile_multi_sensitivity` (passthrough), etc.
- Re-exported at top level and via `fiberforce.profiles`
- Full CLI surface: `fiberforce profile save-result`, `multi-sens`, `compare-runs`, `list-results`

**See the definitive runnable demonstrations**:
- `examples/08_profile_persistence_workflows.py` (broad coverage of every helper + geometric multi-var inside persisted runs)
- `examples/09_geometric_multi_var_persistence.py` (deepest combined geometric surfaces persisted + static-vs-geo post-hoc loading)

The older Example 07 and the "future" bullets in prior docs are now historical. The full layer is stable, round-trips complex nested results, and is the foundation for any serious longitudinal or coaching tooling.

## 5. Visualization Integration Patterns

```python
from fiberforce.visualization import plot_sensitivity, plot_comparison, ascii_bars, ComparisonResult

# SensitivityResult and ComparisonResult objects (including those loaded from disk) are directly usable
plot_sensitivity(some_sens_result, save_path="my_sweep.png")
```

Examples 04, 06, 07, 08, and 09 all contain production patterns (ASCII fallbacks are excellent for headless/CI environments).

## 6. Full Custom Pose Construction (When Builders + Geometric Are Not Enough)

For unusual bar positions, your own ultrasound-derived moment arms, or adding stabilization notes: drop down to direct `AnalyzedPosition` + `Pose` + `MuscleAttachment` construction (see the "Full Custom" section in older versions of this doc or the source of the builders in `examples.py` for patterns). The geometric estimators remain available as pure functions you can call yourself.

## 7. Recommended Project Patterns (Now with 08 + 09 as the New Gold Standard)

- **Personal dashboard script**: Load your profile → run 8–12 key positions across all four lifts (using `use_geometric=True` where supported) → generate matplotlib report + ASCII summary + dated text report → persist every analysis via `save_current_analysis` or `run_profile_*` → append to master archive.
- **Setup optimizer / geometric what-if engine**: Multi-var sweeps over load + grip/stance using the patterns in 06/08/09. Persist both static and geometric variants under the same profile for later fidelity comparison. This is the most advanced workflow available today.
- **Longitudinal tracking**: Every important session or experiment produces a `SavedSensitivityRun` or `SavedAnalysisRun` with your profile + timestamp + free-form notes/tags. Load prior runs in future scripts to compute deltas without re-running or re-measuring.
- **Coaching reports**: Use `AnalysisService` + `plot_*` + loaded profiles + `list_all_for_profile` inside a Jupyter notebook; export figures + the generated report txt + the actual JSON artifacts.
- **Geometric prototyping**: Copy the rebuild factories from Examples 05/06/08/09. The new builder integration (`use_geometric`) makes the 80% case trivial; drop to direct `estimate_*_ma` calls when you need more control.

## Next-Level Ideas (Roadmap Aligned — Already Paved by Current Architecture)

- Multi-variable sensitivity with true 2D grids + seaborn/pandas heatmaps (the `run_multi` + persisted `SensitivityResult.points` foundation + geometric rebuilds make this a small step — see 09 for the data model).
- Program-level accumulation engine that consumes lists of persisted runs.
- Expanding geometric coverage (more regions, dynamic curves, deadlift/OHP) — the estimator + `ReferenceData.estimate_moment_arm` + builder dispatch points are already in place.
- Richer saved-run metadata (RPE, bodyweight, session RPE, video links) attached to `Saved*Run` objects.

Start with the service + a saved profile. Layer geometric (via the builder flag or direct estimators) inside multi-var rebuilds. Persist everything. Visualize the slopes and interactions. Load prior artifacts for comparison. That loop, repeated with your real measurements and honest interpretation of the limitations, is how FiberForce becomes genuinely useful.

---

*See `docs/limitations-deep-dive.md` for the full list of assumptions and "when not to use" guidance (including current geometric prototype scope and multi-var sequential nature). All patterns above were validated against the current complete implementation (AnalysisService + builder geometric wiring, full 4-lift parity, geometric.py, sensitivity run_multi, the entire results.py persistence layer, profiles, visualization).*

*See the nine runnable scripts in `examples/` (especially the new 08 and 09) for complete, copy-pasteable working code of the patterns described here. The Limitations sections inside those scripts are the most up-to-date honesty statements.*
