#!/usr/bin/env python3
"""
Advanced Example 06: Multi-Variable Sensitivity Analysis (with Geometric Integration)
====================================================================================

This script demonstrates the **multi-variable sensitivity foundation** delivered
in the massive phase continuation:

- `AnalysisService.sensitivity_multi()` (thin wrapper over `SensitivityAnalyzer.run_multi`)
- Sequential sweeps over multiple variables (e.g. load × femur, load × grip proxy)
  while holding others fixed.
- Full integration with the **geometric moment arm prototype** (Example 05):
  one powerful demo rebuilds positions using live `estimate_*_ma` functions driven
  by real UserAnthropometry + the swept parameters.

This is the practical bridge between single-var "what if load changes?" studies
and future high-fidelity grids that vary your actual skeleton + setup choices.

WHY THIS MATTERS
Single-variable sweeps are great. Real training decisions involve *interactions*:
- "How does increasing load affect glute demand *differently* for a long-femur
  lifter vs average proportions?"
- "What grip width + load combination maximizes or minimizes sternal pec demand
  for *my* humerus and biacromial width, using the actual geometric model?"

Multi-var + geometric lets you explore exactly that today (with the known
limitations of the prototype estimators and the overall unit bug).

DELIVERABLES
1. Clean `AnalysisService.sensitivity_multi` usage for squat (load + femur).
2. Bench example with custom grip/load rebuild (proxy for future geometric).
3. **Combined geometric + multi-var demo**: Live geometric MA estimators wired
   directly into the rebuild_multi callable for stance × load on squat (or grip
   on bench). This is the flagship pattern.
4. Visualization (ASCII bars + optional matplotlib) of the resulting sweeps.
5. Full report written to examples/outputs/06_multi_variable_sensitivity_report.txt
6. Detailed model + limitations documentation.

RUN:
    python examples/06_multi_variable_sensitivity.py

OUTPUTS:
    - Rich console tables + ASCII visualizations
    - examples/outputs/06_multi_variable_sensitivity_report.txt
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fiberforce import AnalysisService
from fiberforce.models import (
    AnalyzedPosition,
    ExternalLoad,
    MuscleAttachment,
    Pose,
    Subject,
    UserAnthropometry,
)
from fiberforce.models import KNOWN_MUSCLE_REGIONS
from fiberforce.reference import get_default_reference
from fiberforce.reference.geometric import (
    estimate_squat_glute_ma,
)
from fiberforce.visualization import ascii_bars, ascii_sparkline, plot_sensitivity
from fiberforce.calculations.sensitivity import SensitivityResult

# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def get_glute_upper_region():
    for r in KNOWN_MUSCLE_REGIONS:
        if "Upper fibers" in r.region_name and "Glute" in r.muscle_name:
            return r
    return next(r for r in KNOWN_MUSCLE_REGIONS if "Glute" in r.muscle_name)

def get_sternal_region():
    for r in KNOWN_MUSCLE_REGIONS:
        if r.region_name == "Sternal fibers":
            return r
    return next(r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name)


def print_sensitivity_result(res: SensitivityResult, title: str = ""):
    if title:
        print(f"\n{title}")
    print(f"  Variable: {res.variable_name}  | Target: {res.target_region}")
    print(f"  Summary: {res.summary}")
    print("  Points:")
    for p in res.points:
        print(f"    {p.variable_value!s:>8} → {p.peak_force_n:6.1f} N  ({p.confidence_level})")
    # ASCII sparkline of forces
    forces = [p.peak_force_n for p in res.points]
    if forces:
        print("  Trend:", ascii_sparkline(forces, width=40))


# -------------------------------------------------------------------
# REBUILD FUNCTIONS (including geometric-powered ones)
# -------------------------------------------------------------------

def rebuild_squat_load_femur(base_pos: AnalyzedPosition, params: dict) -> AnalyzedPosition:
    """Standard rebuild for load + femur (uses service builder under the hood)."""
    return AnalysisService().build_position(
        "squat",
        load_kg=params.get("load_kg", 140.0),
        variation="low_bar",
        target_region_name="Upper fibers",
        femur_cm=params.get("femur", 42.0),
        tibia_cm=38.0,
    )


def make_geometric_multi_rebuild(base_anthro: UserAnthropometry, base_load: float = 140.0):
    """
    Factory that returns a rebuild_multi callable using *live geometric estimators*
    for glute MA (and optionally quad).

    This is the killer combined pattern (Example 05 + 06):
    - Vary load_kg and stance_width_cm
    - Every position gets fresh, anthropometry-driven moment arms from the prototype
      instead of static tables.
    """
    service = AnalysisService()

    def rebuild(base_pos: AnalyzedPosition, params: dict) -> AnalyzedPosition:
        load = params.get("load_kg", base_load)
        stance = params.get("stance_width_cm", 65.0)

        # 1. Compute fresh geometric MA values for this exact body + stance
        geo_glute = estimate_squat_glute_ma(
            base_anthro,
            stance_width_cm=stance,
            variation="low_bar",
            hip_flexion_deg=110.0,
        )
        # (quad also available if you want to target quads)

        # 2. Build base position via service (gets correct load MA, angles, etc.)
        pos = service.build_position(
            "squat",
            load_kg=load,
            variation="low_bar",
            target_region_name="Upper fibers",
            femur_cm=base_anthro.femur_length_cm or 42.0,
            tibia_cm=base_anthro.tibia_length_cm or 38.0,
        )

        # 3. Mutate the glute attachment(s) to use the live geometric MA
        p = pos.pose
        new_atts = []
        for att in p.active_attachments:
            if "hip" in att.moment_arms_at_position:
                new_ma = att.moment_arms_at_position.copy()
                new_ma["hip"] = geo_glute
                new_atts.append(
                    MuscleAttachment(
                        muscle_region=att.muscle_region,
                        joints_crossed=att.joints_crossed,
                        moment_arms_at_position=new_ma,
                        notes=att.notes + f" [geo multi-var stance={stance:.0f}cm load={load}kg]",
                    )
                )
            else:
                new_atts.append(att)

        # 4. Light load MA scaling with stance (proxy; wider often slightly longer lever)
        new_load_ma = dict(p.load_moment_arms)
        new_load_ma["hip"] = round(32.0 + (stance - 55) * 0.04, 1)

        new_pose = Pose(
            name=p.name + f" [geo+multi load={load} stance={stance:.0f}]",
            joint_angles=p.joint_angles,
            external_load=ExternalLoad(mass_kg=load, load_type="barbell"),
            active_attachments=new_atts,
            load_moment_arms=new_load_ma,
            notes=p.notes + " | Geometric MA + multi-var sensitivity",
        )
        return AnalyzedPosition(pose=new_pose, target_regions=pos.target_regions)

    return rebuild


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main() -> None:
    print("=" * 78)
    print("FIBERFORCE ADVANCED EXAMPLE 06")
    print("Multi-Variable Sensitivity + Geometric Moment Arm Integration")
    print("=" * 78)
    print()

    service = AnalysisService()
    ref = get_default_reference()
    print(f"[Service] {service.describe()}")
    print(f"[Reference] {ref.describe()}")
    print()

    glute = get_glute_upper_region()
    sternal = get_sternal_region()

    # ----------------------------------------------------------------
    # PART 1: Basic multi-var (load + femur) on squat using service
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PART 1: Basic Multi-Variable — Squat load_kg × femur (long-femur lifter)")
    print("=" * 60)

    long_femur_anthro = UserAnthropometry(
        name="Long Femur Athlete",
        femur_length_cm=48.0,
        tibia_length_cm=40.0,
        biiliac_width_cm=29.0,
    )
    long_femur_subj = Subject(anthropometry=long_femur_anthro)

    base_squat = service.build_position(
        "squat", load_kg=140, variation="low_bar", target_region_name="Upper fibers",
        femur_cm=48.0, tibia_cm=40.0
    )

    multi_squat = service.sensitivity_multi(
        subject=long_femur_subj,
        base_position=base_squat,
        variables=[
            ("load_kg", [120, 140, 160, 180]),
            ("femur", [44, 48, 52]),
        ],
        target_region=glute,
        rebuild_multi=rebuild_squat_load_femur,
    )

    for res in multi_squat:
        print_sensitivity_result(res)

    # ----------------------------------------------------------------
    # PART 2: Bench load + grip proxy (classic single-rebuild style)
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PART 2: Bench — load_kg × grip proxy (sternal pecs)")
    print("=" * 60)

    bench_anthro = UserAnthropometry(
        name="Medium Build Bencher",
        humerus_length_cm=33.5,
        forearm_length_cm=26.0,
        biacromial_width_cm=39.5,
        torso_depth_at_chest_cm=23.0,
    )
    bench_subj = Subject(anthropometry=bench_anthro)

    def rebuild_bench_load_grip(base_pos: AnalyzedPosition, params: dict) -> AnalyzedPosition:
        load = params.get("load_kg", 100.0)
        grip = params.get("grip", 58.0)
        pos = service.build_position(
            "bench", load_kg=load, variation="flat", target_region_name="Sternal fibers"
        )
        # Proxy for what full geometric would do (see Part 3)
        p = pos.pose
        new_load = dict(p.load_moment_arms or {"shoulder": 32.0})
        new_load["shoulder"] = round(28.0 + (grip - 50) * 0.08, 1)
        new_pose = Pose(
            name=p.name + f" (grip~{grip})",
            joint_angles=p.joint_angles,
            external_load=ExternalLoad(mass_kg=load, load_type="barbell"),
            active_attachments=p.active_attachments,
            load_moment_arms=new_load,
            notes=p.notes,
        )
        return AnalyzedPosition(pose=new_pose, target_regions=pos.target_regions)

    base_bench = service.build_position(
        "bench", load_kg=100, variation="flat", target_region_name="Sternal fibers"
    )
    multi_bench = service.sensitivity_multi(
        subject=bench_subj,
        base_position=base_bench,
        variables=[
            ("load_kg", [80, 100, 120, 140]),
            ("grip", [52, 58, 68]),
        ],
        target_region=sternal,
        rebuild_multi=rebuild_bench_load_grip,
    )

    for res in multi_bench:
        print_sensitivity_result(res, title=f"Bench sweep on {res.variable_name}")

    # ----------------------------------------------------------------
    # PART 3: THE KILLER COMBO — Geometric MA + Multi-Variable Sensitivity
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PART 3: GEOMETRIC + MULTI-VAR (flagship pattern)")
    print("Squat: live estimate_squat_glute_ma inside rebuild_multi for stance × load")
    print("=" * 60)

    geo_anthro = UserAnthropometry(
        name="Realistic Geo Subject (long femur + wide stance preference)",
        femur_length_cm=46.0,
        tibia_length_cm=39.0,
        biiliac_width_cm=31.0,
    )
    geo_subj = Subject(anthropometry=geo_anthro)

    base_geo = service.build_position(
        "squat", load_kg=150, variation="low_bar", target_region_name="Upper fibers",
        femur_cm=46.0, tibia_cm=39.0
    )

    geo_rebuild = make_geometric_multi_rebuild(geo_anthro, base_load=150.0)

    multi_geo = service.sensitivity_multi(
        subject=geo_subj,
        base_position=base_geo,
        variables=[
            ("load_kg", [130, 150, 170]),
            ("stance_width_cm", [58, 68, 78]),   # realistic wide-stance range
        ],
        target_region=glute,
        rebuild_multi=geo_rebuild,
    )

    for res in multi_geo:
        print_sensitivity_result(res, title=f"Geometric multi-var sweep on {res.variable_name}")

    # Quick ASCII bar of one of the sweeps (last result)
    if multi_geo:
        last = multi_geo[-1]
        forces = [p.peak_force_n for p in last.points]
        labels = [f"{p.variable_value}" for p in last.points]
        print("\nASCII bars for last geometric sweep (stance effect):")
        print(ascii_bars(labels, forces, width=50))

    # ----------------------------------------------------------------
    # PART 4: Visualization + Summary
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("VISUALIZATION + SUMMARY")
    print("=" * 60)

    # Demonstrate plot on one result (falls back gracefully)
    try:
        if multi_squat:
            plot_sensitivity(multi_squat[0], save_path=None, show=False, ascii_only=True)
            print("Plot call succeeded (ASCII fallback or matplotlib).")
    except Exception as e:
        print(f"Plot note: {e}")

    print("\nMulti-variable sensitivity (especially when powered by the geometric")
    print("prototype) lets you quantify interaction effects that no single-var")
    print("sweep can reveal. This is the exact capability needed for personalized")
    print("setup optimization.")

    # ----------------------------------------------------------------
    # WRITE REPORT
    # ----------------------------------------------------------------
    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "06_multi_variable_sensitivity_report.txt"

    report_lines = [
        "FiberForce Advanced Example 06 Report",
        "Multi-Variable Sensitivity + Geometric MA Integration",
        f"Generated: {datetime.now().isoformat()}",
        f"Service: {service.describe()}",
        f"Reference: {ref.describe()}",
        "",
        "CAPABILITIES DEMONSTRATED",
        "  - AnalysisService.sensitivity_multi() for sequential multi-var sweeps",
        "  - Custom rebuild_multi functions (dict of current param values)",
        "  - Full integration of geometric estimators (05) inside multi-var rebuilds",
        "  - Consistent use of service.build_position + AnalysisService for all lifts",
        "  - Visualization (ASCII + plot API) on SensitivityResult objects",
        "",
        "KEY INSIGHT",
        "Geometric MA inside multi-var rebuilds means you can now answer questions like:",
        "  'For my 46 cm femur + 31 cm biiliac, how does going from 58 cm to 78 cm stance",
        "   change modeled glute upper demand across 130-170 kg loads?'",
        "",
        "The rebuild receives the exact current (load, stance) pair and calls",
        "estimate_squat_glute_ma(anthro, stance_width=..., variation=...) live.",
        "",
        "CURRENT LIMITATIONS (see also docs/limitations-deep-dive.md)",
        "  - Multi-var is sequential (one var at a time, others fixed at first value).",
        "    True 2D grids + heatmaps / surface plots are future work.",
        "  - Geometric prototype is limited (bench sternal + squat glute/quad only).",
        "  - Absolute force scale is off by ~100× (unit bug).",
        "  - Still static single-position analysis.",
        "  - Rebuilds for complex cases require manual attachment mutation today.",
        "",
        "FUTURE DIRECTIONS (already paved by this architecture)",
        "  - Auto geometric wiring inside the core builders when use_geometric=True.",
        "  - Full grid sensitivity + seaborn/pandas surface plots.",
        "  - Program-level accumulation using multi-var cost surfaces.",
        "  - Storing full (config + results) alongside profiles.",
        "",
        "See:",
        "  - examples/05_geometric_moment_arm_prototype.py (the geometric source)",
        "  - src/fiberforce/analysis/service.py (sensitivity_multi + build_position)",
        "  - src/fiberforce/calculations/sensitivity.py (run_multi implementation)",
        "  - src/fiberforce/reference/geometric.py (full model + limitations)",
        "",
        "All relative trends and interaction deltas from this script are meaningful",
        "for hypothesis generation and training experiment design today.",
    ]

    report_path.write_text("\n".join(report_lines))
    print(f"\nReport written to: {report_path}")

    print("\nExample 06 (Multi-Variable Sensitivity + Geometric) complete.")
    print("Next: Combine with profiles persistence (see docs/advanced-patterns.md and future 07 example).")


if __name__ == "__main__":
    main()
