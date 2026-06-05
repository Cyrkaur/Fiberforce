#!/usr/bin/env python3
"""
Advanced Example 07: Persistence & Profiles + Batch Analysis with AnalysisService
=================================================================================

This script demonstrates the **profiles + persistence** system (massive phase)
combined with the primary `AnalysisService` API for powerful, repeatable,
personalized batch workflows.

FEATURES SHOWN
- `fiberforce.profiles.save_anthropometry` / `load_anthropometry` / `list_profiles`
- `AnalysisService.create_subject_from_measurements` + direct construction
- Saving a "real" profile once, then loading it in the same or future sessions
- Batch analysis across **all four first-class lifts** (bench, squat, deadlift
  conventional/sumo, ohp standing/seated) using the unified `service.build_position`
- Multi-region reporting + simple aggregation
- Visualization integration (`plot_comparison`, ASCII)
- Writing a dated, reusable report (perfect for a personal dashboard script)

WHY THIS MATTERS
Profiles turn FiberForce from a one-off calculator into a personal tool.
You measure yourself once (or update seasonally), save it, and every script,
notebook, or CLI `fiberforce profile run ...` reuses the exact same numbers.
Combined with full lift parity and the service layer, you can run a complete
"my current setup audit" in <30 lines.

This example also serves as a template you can copy into your own
`~/training/fiberforce_audit.py` or Jupyter workflow.

RUN:
    python examples/07_persistence_profiles_and_batch.py

    # After first run you can also do (from anywhere):
    # fiberforce profile list
    # fiberforce profile run my-real-2026 --lift deadlift --load-kg 180 -v sumo

OUTPUTS:
    - Console report + ASCII viz
    - examples/outputs/07_profiles_batch_report.txt
    - (Side effect) A real profile saved under ~/.fiberforce/profiles/ under the name "example-athlete-2026"
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fiberforce import AnalysisService
from fiberforce.models import KNOWN_MUSCLE_REGIONS, Subject, UserAnthropometry
from fiberforce.profiles import (
    save_anthropometry,
    load_anthropometry,
    list_profiles,
    get_or_create_default_profile,
)
from fiberforce.visualization import ascii_bars, plot_comparison

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

PROFILE_NAME = "example-athlete-2026"
REPORT_NAME = "07_profiles_batch_report.txt"


def get_region(name_substring: str, muscle_hint: str = "") -> Any:
    """Robust region lookup."""
    for r in KNOWN_MUSCLE_REGIONS:
        if name_substring.lower() in r.region_name.lower():
            if not muscle_hint or muscle_hint.lower() in r.muscle_name.lower():
                return r
    # fallback
    return KNOWN_MUSCLE_REGIONS[0]


def main() -> None:
    print("=" * 78)
    print("FIBERFORCE ADVANCED EXAMPLE 07")
    print("Profiles + Persistence + Full-Lift Batch Analysis via AnalysisService")
    print("=" * 78)
    print()

    service = AnalysisService()
    print(f"[Service] {service.describe()}\n")

    # ----------------------------------------------------------------
    # 1. CREATE + SAVE A REALISTIC PERSONAL PROFILE
    # ----------------------------------------------------------------
    print("1. Creating and persisting a realistic athlete profile...")
    my_anthro = UserAnthropometry(
        name="Example Athlete (May 2026)",
        measurement_date="2026-05-26",
        humerus_length_cm=34.0,
        forearm_length_cm=26.5,
        biacromial_width_cm=40.5,
        torso_depth_at_chest_cm=23.5,
        femur_length_cm=44.5,
        tibia_length_cm=38.5,
        biiliac_width_cm=30.0,
        notes="Self-measured with calipers + tape. Updated for summer training block.",
    )

    saved_path = save_anthropometry(my_anthro, PROFILE_NAME)
    print(f"   Saved profile → {saved_path}")

    # Demonstrate load + list
    loaded = load_anthropometry(PROFILE_NAME)
    print(f"   Loaded back: femur={loaded.femur_length_cm}cm, humerus={loaded.humerus_length_cm}cm")
    print(f"   All profiles on disk: {list_profiles()}")

    # Also show the convenience default
    default = get_or_create_default_profile("default-demo")
    print(f"   Default profile available: {default.name}")

    # Build subject once (reusable across every analysis)
    subject = Subject(anthropometry=loaded, name=PROFILE_NAME)

    # ----------------------------------------------------------------
    # 2. DEFINE A REPRESENTATIVE "MY CURRENT SETUP" BATCH
    #    (uses full 4-lift parity through the single service method)
    # ----------------------------------------------------------------
    print("\n2. Running batch analysis across all four lifts (full parity)...")

    scenarios = [
        # Bench family
        ("Bench Flat 105kg bottom", "bench", 105, "flat", "Sternal fibers"),
        ("Bench Incline 30° 95kg bottom", "bench", 95, "incline_30", "Sternal fibers"),
        # Squat family
        ("Low-bar Squat 155kg bottom", "squat", 155, "low_bar", "Upper fibers"),
        ("High-bar Squat 145kg bottom", "squat", 145, "high_bar", "Upper fibers"),
        # Deadlift family (first-class)
        ("Conventional DL 175kg floor", "deadlift", 175, "conventional", "Upper fibers"),
        ("Sumo DL 175kg floor", "deadlift", 175, "sumo", "Upper fibers"),
        # OHP (full parity: standing + multi-head + triceps)
        ("Standing OHP 70kg bottom", "ohp", 70, "standing", "Anterior"),
        ("Seated OHP 65kg mid (lateral delt)", "ohp", 65, "seated", "Lateral"),
    ]

    results = []
    for label, lift, load, var, target in scenarios:
        kwargs = {
            "load_kg": load,
            "variation": var,
            "target_region_name": target,
        }
        l = lift.lower()
        if l in ("bench", "ohp"):
            kwargs.update({
                "humerus_cm": loaded.humerus_length_cm,
                "forearm_cm": loaded.forearm_length_cm,
                "biacromial_cm": loaded.biacromial_width_cm,
            })
        else:
            kwargs.update({
                "femur_cm": loaded.femur_length_cm,
                "tibia_cm": loaded.tibia_length_cm,
            })
        pos = service.build_position(lift, **kwargs)
        analysis = service.analyze(subject, pos)
        # Pick the best matching result for the requested target
        match = next(
            (r for r in analysis.results if target.lower() in str(r.muscle_region).lower()),
            analysis.results[0],
        )
        results.append({
            "label": label,
            "lift": lift,
            "force_n": match.peak_force_newtons,
            "conf": match.confidence_level,
            "notes": match.notes[:60] if match.notes else "",
        })
        print(f"   {label:35s} → {match.peak_force_newtons:6.1f} N  ({match.confidence_level})")

    # ----------------------------------------------------------------
    # 3. SIMPLE AGGREGATION + RANKING (program insight style)
    # ----------------------------------------------------------------
    print("\n3. Regional demand ranking (your current setups):")
    sorted_by_demand = sorted(results, key=lambda x: x["force_n"], reverse=True)
    for i, r in enumerate(sorted_by_demand[:6], 1):
        print(f"   {i}. {r['label']:35s} {r['force_n']:6.1f} N")

    # Quick ASCII bars of the top forces
    bar_data = {r["label"][:28]: r["force_n"] for r in sorted_by_demand[:8]}
    print("\n   ASCII demand bars (top setups):")
    print(ascii_bars(list(bar_data.keys()), list(bar_data.values()), width=55))

    # ----------------------------------------------------------------
    # 4. STRUCTURED COMPARISON EXAMPLE (service.compare under the hood)
    # ----------------------------------------------------------------
    print("\n4. Head-to-head comparison via service (Conventional vs Sumo on your profile):")
    comp = service.compare(
        lift="deadlift",
        config_a="conventional",
        config_b="sumo",
        load_kg=175,
        target="Upper fibers",
        femur_cm=loaded.femur_length_cm,
        tibia_cm=loaded.tibia_length_cm,
    )
    print(f"   {comp.config_a} vs {comp.config_b} @ {comp.load_kg}kg — {comp.target}")
    print(f"   Forces: {comp.force_a_n:.1f} N vs {comp.force_b_n:.1f} N")
    delta = comp.force_b_n - comp.force_a_n
    print(f"   Δ (sumo - conv): {delta:+.1f} N  ({'sumo lower demand' if delta < 0 else 'sumo higher demand'})")

    # ----------------------------------------------------------------
    # 5. VISUALIZATION + PERSISTENCE BEST PRACTICE
    # ----------------------------------------------------------------
    try:
        # The ComparisonResult returned by service.compare is ready for viz
        plot_comparison(comp, save_path=None, show=False)
        print("\n   plot_comparison call succeeded (matplotlib or rich+ASCII fallback).")
    except Exception as e:
        print(f"\n   Viz note: {e}")

    # ----------------------------------------------------------------
    # 6. WRITE DATED REPORT (template for your own dashboards)
    # ----------------------------------------------------------------
    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_NAME

    lines = [
        "FiberForce Example 07 — Profiles + Batch Analysis Report",
        f"Profile: {PROFILE_NAME}",
        f"Generated: {datetime.now().isoformat()}",
        f"Service: {service.describe()}",
        "",
        "SAVED PROFILE MEASUREMENTS",
        f"  humerus={loaded.humerus_length_cm}, forearm={loaded.forearm_length_cm}",
        f"  biacromial={loaded.biacromial_width_cm}, torso_depth={loaded.torso_depth_at_chest_cm}",
        f"  femur={loaded.femur_length_cm}, tibia={loaded.tibia_length_cm}",
        f"  biiliac={loaded.biiliac_width_cm}",
        "",
        "BATCH RESULTS (full 4-lift parity via AnalysisService.build_position)",
    ]
    for r in results:
        lines.append(f"  {r['label']:38s} {r['force_n']:6.1f} N  conf={r['conf']}")

    lines += [
        "",
        "TOP DEMAND RANKING (your current personal setups)",
    ]
    for i, r in enumerate(sorted_by_demand[:6], 1):
        lines.append(f"  {i}. {r['label']:35s} {r['force_n']:6.1f} N")

    lines += [
        "",
        "DEADLIFT CONVENTIONAL vs SUMO COMPARISON (on your exact proportions)",
        f"  {comp.config_a}: {comp.force_a_n:.1f} N",
        f"  {comp.config_b}:   {comp.force_b_n:.1f} N",
        f"  Delta: {delta:+.1f} N",
        "",
        "RECOMMENDED NEXT STEPS (real usage pattern)",
        "  1. Replace the synthetic numbers above with your actual measured values.",
        "  2. Save once: fiberforce profile save myname --femur XX --humerus YY ...",
        "  3. Run this script (or a derivative) weekly / before a training block.",
        "  4. Correlate the force deltas with real-world data (RPE, soreness by region,",
        "     progress on variations).",
        "  5. Layer in geometric MA (Example 05) + multi-var (Example 06) for deeper",
        "     personalization of the batch.",
        "",
        "PERSISTENCE NOTES",
        "  - Profiles live in ~/.fiberforce/profiles/<name>.json",
        "  - They contain only UserAnthropometry (easy to version control or backup).",
        "  - Future: full saved analysis results + LiftConfiguration objects alongside.",
        "",
        "See also:",
        "  - examples/01_program_level_insights.py (weekly accumulation)",
        "  - docs/advanced-patterns.md §4 (Persistence with Profiles + Batch Analysis)",
        "  - fiberforce profile --help (CLI surface over the same system)",
        "",
        "Relative deltas and rankings produced with your real measurements are the",
        "actionable output of FiberForce today.",
    ]

    report_path.write_text("\n".join(lines))
    print(f"\nDetailed report written to: {report_path}")

    print("\n" + "=" * 78)
    print("Example 07 complete. Your profile is now saved and reusable everywhere.")
    print("Update the numbers with your real measurements and re-run regularly.")
    print("=" * 78)


if __name__ == "__main__":
    main()
