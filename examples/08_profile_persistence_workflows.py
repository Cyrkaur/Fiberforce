#!/usr/bin/env python3
"""
Advanced Example 08: Profile + Full Enhanced Persistence Workflows
==================================================================

This script demonstrates the **complete modern persistence layer** in FiberForce
(results.py + AnalysisService + profiles) — the production way to save, retrieve,
version, and build real longitudinal/personal tooling around your anthropometry.

It specifically showcases:
- Rich profile creation (full measurements that unlock geometric MA)
- AnalysisService.save_current_analysis (one-shot analyze + SavedAnalysisRun)
- run_profile_* helpers including run_profile_multi_sensitivity with custom
  rebuild_multi callables
- **Combined geometric + multi-variable sensitivity inside persisted runs**
  (using the convenient new builder support: use_geometric=True + stance/grip
  parameters forwarded through rebuilds)
- SavedSensitivityRun (including multi-var), SavedAnalysisRun, SavedCompareRun
- list_saved_runs, load_*_run, save_profile_with_run, list_all_for_profile
- Using persisted artifacts to drive reports and "before/after" style reasoning

FEATURES SHOWN (latest post-wiring capabilities)
- Profile-linked everything (anthropometry + full analysis/sensitivity/compare runs)
- Convenient geometric wiring via build_position(..., use_geometric=True)
- Multi-var sensitivity powered by live geometric estimators (via rebuild)
- Full round-tripping of complex results through JSON (no pydantic required)
- Service as the single source of truth for both computation and persistence
- Reusable patterns for personal dashboards, coaching archives, and experiment tracking

WHY THIS MATTERS
Profiles alone (Example 07) let you stop re-typing measurements.
The enhanced results layer lets you *stop losing your analyses*. Every sensitivity
surface, every key position audit, every variation comparison can be saved with
the exact profile + timestamp + notes + tags you used. Later scripts/notebooks
can load them for trend analysis without re-running expensive (or manual) work.

This is the template for anyone building:
- A personal "my current setup vs last mesocycle" comparator
- Automated weekly reports that append to a profile's history
- Coaching tools that attach rich artifacts to athlete profiles

RUN:
    python examples/08_profile_persistence_workflows.py

    # After running you can explore the saved artifacts via CLI too:
    # fiberforce profile list
    # fiberforce profile list-results --profile advanced-persist-athlete-2026
    # fiberforce profile load-result <run_id>

OUTPUTS:
    - Console: rich tables, ASCII visualizations, discovery of saved artifacts
    - examples/outputs/08_profile_persistence_report.txt (comprehensive, dated)
    - Real artifacts written to ~/.fiberforce/profiles/ and ~/.fiberforce/results/
      (analyses/, sensitivities/, comparisons/)

This script is deliberately self-contained and educational. Replace the synthetic
"advanced-persist-athlete-2026" measurements with your own and it becomes your
personal archive engine.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fiberforce import AnalysisService
from fiberforce.models import (
    KNOWN_MUSCLE_REGIONS,
    UserAnthropometry,
)
from fiberforce.profiles import (
    save_anthropometry,
    save_profile_with_run,
    list_all_for_profile,
)
from fiberforce.results import (
    SavedAnalysisRun,
    load_analysis_run,
    load_sensitivity_run,
    run_profile_analysis,
    run_profile_multi_sensitivity,
    run_profile_compare,
    list_saved_runs,
    load_profile_for_analysis,
)
from fiberforce.visualization import ascii_bars

# -------------------------------------------------------------------
# CONFIG — change these to experiment with your own body
# -------------------------------------------------------------------
PROFILE_NAME = "advanced-persist-athlete-2026"
REPORT_NAME = "08_profile_persistence_report.txt"

# Rich measurements (chosen so geometric estimators are active for bench + squat)
RICH_ATHRO = {
    "humerus_length_cm": 34.2,
    "forearm_length_cm": 26.8,
    "biacromial_width_cm": 41.0,
    "torso_depth_at_chest_cm": 22.8,
    "femur_length_cm": 45.0,
    "tibia_length_cm": 39.2,
    "biiliac_width_cm": 29.5,
}


def get_glute_region() -> Any:
    for r in KNOWN_MUSCLE_REGIONS:
        if "Upper fibers" in r.region_name and "Glute" in r.muscle_name:
            return r
    return KNOWN_MUSCLE_REGIONS[0]


def get_sternal_region() -> Any:
    for r in KNOWN_MUSCLE_REGIONS:
        if "Sternal fibers" in r.region_name:
            return r
    return KNOWN_MUSCLE_REGIONS[0]


def make_squat_geo_multi_rebuild(anthro: UserAnthropometry, base_target_name: str = "Upper fibers"):
    """
    Rebuild callable for multi-var sensitivity that uses the *latest convenient
    geometric path*: service.build_position(..., use_geometric=True, stance_width_cm=...).

    This is the clean modern pattern (post auto-wiring in builders) for letting
    real anthropometry + variable stance/load drive continuously updated MA values
    inside sensitivity sweeps. Far simpler than manual attachment mutation.
    """
    service = AnalysisService()

    def rebuild(base_pos: Any, params: dict) -> Any:
        load = float(params.get("load_kg", 150.0))
        stance = float(params.get("stance_width_cm", 45.0))
        return service.build_position(
            "squat",
            load_kg=load,
            variation="low_bar",  # or high_bar; kept fixed for this demo
            stance_width_cm=stance,
            target_region_name=base_target_name,
            femur_cm=anthro.femur_length_cm,
            tibia_cm=anthro.tibia_length_cm,
            use_geometric=True,   # <-- the new convenient flag (latest capability)
        )
    return rebuild


def main() -> None:
    print("=" * 80)
    print("FIBERFORCE ADVANCED EXAMPLE 08")
    print("Profiles + Full Enhanced Persistence (Saved*Run, run_profile_*, geometric multi-var)")
    print("=" * 80)
    print()

    service = AnalysisService()
    print(f"[Service] {service.describe()}\n")

    # ----------------------------------------------------------------
    # 1. CREATE & PERSIST A RICH PROFILE (measurements that drive geometric)
    # ----------------------------------------------------------------
    print("1. Creating and saving rich athlete profile (enables geometric MA)...")
    my_anthro = UserAnthropometry(
        name="Advanced Persist Demo Athlete (2026)",
        measurement_date="2026-05-26",
        notes="Full measurements for geometric + persistence example",
        **RICH_ATHRO,
    )
    save_anthropometry(my_anthro, PROFILE_NAME)
    print(f"   Saved profile '{PROFILE_NAME}' with complete limb + torso data.")

    # Also show the convenience loader that gives you a ready Subject
    _, subject = load_profile_for_analysis(PROFILE_NAME)
    print(f"   Loaded via load_profile_for_analysis → Subject ready (name={subject.name})")
    print()

    # ----------------------------------------------------------------
    # 2. SIMPLE PERSISTED ANALYSIS via service.save_current_analysis + geometric
    # ----------------------------------------------------------------
    print("2. Running + persisting a single analysis using geometric builder path...")
    # Use the new builder support directly (latest wiring)
    pos_bench = service.build_position(
        "bench",
        load_kg=110,
        variation="flat",
        target_region_name="Sternal fibers",
        humerus_cm=RICH_ATHRO["humerus_length_cm"],
        biacromial_cm=RICH_ATHRO["biacromial_width_cm"],
        torso_depth_cm=RICH_ATHRO["torso_depth_at_chest_cm"],
        grip_width_cm=58.0,          # realistic medium-wide
        use_geometric=True,          # triggers estimate_bench_sternal_ma internally
    )
    analysis_res, saved_path = service.save_current_analysis(
        subject=subject,
        position=pos_bench,
        run_id=f"{PROFILE_NAME}_bench_110kg_sternal_geo",
        profile_name=PROFILE_NAME,
        notes="Example 08: geometric-enabled bench via use_geometric=True in builder",
    )
    print(f"   SavedAnalysisRun written to: {saved_path}")
    first_force = analysis_res.results[0].peak_force_newtons if analysis_res.results else 0.0
    print(f"   Result: {first_force:.1f} N on sternal pecs (geo source recorded in notes)")
    print()

    # ----------------------------------------------------------------
    # 3. PROFILE-BASED MULTI-VAR SENSITIVITY WITH GEOMETRIC (flagship combo)
    # ----------------------------------------------------------------
    print("3. Profile-based multi-variable sensitivity (load × stance) powered by geometric MA...")
    print("   Using custom rebuild_multi that calls build_position(use_geometric=True)")
    variables = [
        ("load_kg", [140.0, 160.0, 180.0]),
        ("stance_width_cm", [35.0, 50.0, 65.0]),
    ]
    get_glute_region()

    geo_rebuild = make_squat_geo_multi_rebuild(my_anthro, "Upper fibers")

    sens_run, sens_path = run_profile_multi_sensitivity(
        profile_name=PROFILE_NAME,
        lift="squat",
        variables=variables,
        target_region_name="Upper fibers",
        load_kg=150.0,
        variation="low_bar",
        rebuild_multi=geo_rebuild,
        notes="Example 08: geometric + multi-var (stance + load) via persisted profile helper",
    )
    print(f"   SavedSensitivityRun (multi-var): {sens_path}")
    print(f"   is_multi_var: {sens_run.is_multi_var()} | results: {len(sens_run.sensitivity_results)}")
    print(f"   Total data points across sweeps: {sum(len(r.points) for r in sens_run.sensitivity_results)}")
    print()

    # Quick ASCII peek at the last sweep (stance effect at highest load)
    if sens_run.sensitivity_results:
        last = sens_run.sensitivity_results[-1]
        labels = [f"stance={p.variable_value:.0f}cm" for p in last.points]
        forces = [p.peak_force_n for p in last.points]
        print("   ASCII view of final stance sweep (highest load):")
        print("   " + ascii_bars(labels, forces, width=52))
    print()

    # ----------------------------------------------------------------
    # 4. DISCOVERY + LOADING PERSISTED ARTIFACTS
    # ----------------------------------------------------------------
    print("4. Discovering and loading saved runs (the real power of the layer)...")
    all_runs = list_saved_runs(profile_name=PROFILE_NAME)
    print(f"   All runs for profile '{PROFILE_NAME}': {len(all_runs)} total")
    for name in all_runs[:6]:
        print(f"     - {name}")

    # Load the analysis we just saved
    try:
        loaded_analysis = load_analysis_run(f"{PROFILE_NAME}_bench_110kg_sternal_geo")
        print(f"   Successfully round-tripped SavedAnalysisRun: {loaded_analysis.short_summary()}")
    except Exception as e:
        print(f"   Load note: {e}")

    # Load the multi-var sensitivity we just saved
    try:
        loaded_sens = load_sensitivity_run(sens_run.run_id)
        print(f"   Round-tripped SavedSensitivityRun: {loaded_sens.short_summary()}")
        print(f"     Variable set: {loaded_sens.variable}")
    except Exception as e:
        print(f"   Sens load note: {e}")
    print()

    # ----------------------------------------------------------------
    # 5. HIGHER-LEVEL HELPERS + COMPARE PERSISTENCE
    # ----------------------------------------------------------------
    print("5. Using save_profile_with_run + run_profile_compare (bundled persistence)...")
    # Run a quick profile compare and persist it
    try:
        comp_run, comp_path = run_profile_compare(
            profile_name=PROFILE_NAME,
            lift="squat",
            config_a="high_bar",
            config_b="low_bar",
            load_kg=155.0,
            target="Upper fibers",
            notes="Example 08: high vs low bar on saved rich profile (persisted)",
        )
        print(f"   SavedCompareRun: {comp_path}")
    except Exception as e:
        print(f"   Compare persistence note (may be limited on some builders): {e}")

    # Bundle the profile + one of our analysis runs using the convenience helper
    bundle_path, a_path, _ = save_profile_with_run(
        anthro=my_anthro,
        profile_name=f"{PROFILE_NAME}-bundled",
        analysis_run=SavedAnalysisRun(
            run_id=f"bundled-demo-{datetime.now().strftime('%H%M')}",
            profile_name=PROFILE_NAME,
            analysis_result=analysis_res,
            notes="Attached via save_profile_with_run in Example 08",
        ),
    )
    print(f"   Bundled profile+analysis via save_profile_with_run → {bundle_path}")

    # Discovery helper
    summary = list_all_for_profile(PROFILE_NAME)
    print(f"   list_all_for_profile summary: profile_exists={summary['profile_exists']}, "
          f"associated_runs={len(summary['associated_runs'])}")
    print()

    # ----------------------------------------------------------------
    # 6. USING run_profile_analysis (the simple persisted single-shot helper)
    # ----------------------------------------------------------------
    print("6. Using run_profile_analysis for a deadlift (persisted automatically)...")
    try:
        dl_run, dl_path = run_profile_analysis(
            profile_name=PROFILE_NAME,
            lift="deadlift",
            variation="sumo",
            load_kg=175.0,
            target_region_name="Upper fibers",
            notes="Example 08 demo: sumo DL persisted via run_profile_analysis",
        )
        print(f"   run_profile_analysis produced: {dl_path}")
    except Exception as e:
        print(f"   run_profile_analysis note: {e}")
    print()

    # ----------------------------------------------------------------
    # 7. WRITE THE DETAILED REPORT (template you can extend)
    # ----------------------------------------------------------------
    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_NAME

    lines = [
        "FiberForce Example 08 — Profile + Full Enhanced Persistence Report",
        f"Profile: {PROFILE_NAME}",
        f"Generated: {datetime.now().isoformat()}",
        f"Service: {service.describe()}",
        "",
        "RICH PROFILE MEASUREMENTS USED (these drive geometric estimators)",
    ]
    for k, v in RICH_ATHRO.items():
        lines.append(f"  {k}: {v}")

    lines += [
        "",
        "PERSISTED ARTIFACTS CREATED IN THIS RUN",
        f"  - SavedAnalysisRun (bench geometric): {PROFILE_NAME}_bench_110kg_sternal_geo",
        f"  - SavedSensitivityRun (multi-var + geo rebuild): {sens_run.run_id}",
        f"  - Additional runs via run_profile_* helpers and save_current_analysis",
        "",
        "KEY DEMONSTRATED PATTERNS",
        "  1. service.save_current_analysis(subject, pos_with_use_geometric=True)",
        "  2. run_profile_multi_sensitivity(..., rebuild_multi=geo_aware_rebuild)",
        "     → The rebuild uses the modern build_position(use_geometric=True, stance=...)",
        "     → Real femur/tibia + variable stance produce fresh glute MA on every point",
        "  3. Full round-tripping: save → list_saved_runs → load_*_run",
        "  4. save_profile_with_run and list_all_for_profile for archive hygiene",
        "  5. run_profile_compare + run_profile_analysis as zero-boilerplate persisted workflows",
        "",
        "NEXT STEPS FOR REAL USE",
        "  - Replace RICH_ATHRO with your actual measured values (or load an existing profile).",
        "  - Extend the multi-var variables and rebuild to explore grip/stance/load interactions",
        "    on *your* skeleton (bench + squat are the best-supported for geometric today).",
        "  - Add your own tags (e.g. ['post-deload', 'RPE-8']) and notes with training context.",
        "  - Write a small wrapper that runs this weekly and appends to a master report.",
        "  - Use the loaded SavedSensitivityRun.points to feed pandas/seaborn for 2D surfaces",
        "    (the data model already gives you everything you need).",
        "",
        "PERSISTENCE IMPLEMENTATION NOTES",
        "  - All artifacts live under ~/.fiberforce/results/{analyses,sensitivities,comparisons}/",
        "  - Human-readable JSON with explicit __type__ tags for robust reconstruction.",
        "  - Profile name is the natural foreign key linking anthropometry ↔ results.",
        "  - The layer was designed so that future additions (program accumulation,",
        "    dynamic ROM exports, etc.) can attach to the same Saved*Run objects.",
        "",
        "See also:",
        "  - examples/07_persistence_profiles_and_batch.py (the anthropometry-only predecessor)",
        "  - examples/09_geometric_multi_var_persistence.py (deeper combined geo+multi-var focus)",
        "  - docs/advanced-patterns.md (now updated with full persistence recipes)",
        "  - src/fiberforce/results.py and src/fiberforce/analysis/service.py",
        "",
        "All relative trends, interaction effects, and deltas from persisted runs are",
        "meaningful today. Absolute force values should be interpreted directionally only.",
    ]

    report_path.write_text("\n".join(lines))
    print(f"Detailed report written to: {report_path}")

    print("\n" + "=" * 80)
    print("Example 08 complete.")
    print("Your profile and multiple rich persisted artifacts (analyses + multi-var sens)")
    print("are now available for any future script, notebook, or CLI inspection.")
    print("This is the current recommended foundation for serious personal or coaching use.")
    print("=" * 80)


if __name__ == "__main__":
    main()
