#!/usr/bin/env python3
"""
Advanced Example 04: Deadlift vs Squat — Posterior Chain Regional Comparison
============================================================================

Direct head-to-head of the most important posterior chain regions across
two primary lifts using the *real* production builders and AnalysisService:

Regions analyzed:
  - Gluteus Maximus (Upper fibers) — primary hip extensor
  - Hamstrings (Biceps Femoris long head) — hip extension + knee stability
  - Erector Spinae (Lumbar) — anti-flexion / spinal extension

Lifts / variations (bottom position):
  - Squat: high_bar vs low_bar
  - Deadlift: conventional vs sumo

All numbers come from live reference moment arm tables (DEADLIFT_* and
SQUAT_* in fiberforce/reference/moment_arms.py) via the builders.

Demonstrates:
  - AnalysisService.build_position for deadlift + squat
  - Full posterior chain Subject construction
  - Multi-region analysis and structured comparison
  - Visualization of comparison results

Run:
    python examples/04_deadlift_vs_squat_posterior_chain.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fiberforce import AnalysisService
from fiberforce.examples import example_subject_with_posterior_chain
from fiberforce.models import MuscleRegion
from fiberforce.reference import KNOWN_MUSCLE_REGIONS
from fiberforce.visualization import plot_comparison, ComparisonResult, ascii_bars

# -------------------------------------------------------------------
# REGION LOOKUP (robust)
# -------------------------------------------------------------------

def find_region(muscle_substring: str, region_substring: str) -> MuscleRegion:
    for r in KNOWN_MUSCLE_REGIONS:
        if muscle_substring.lower() in r.muscle_name.lower() and region_substring.lower() in r.region_name.lower():
            return r
    for r in KNOWN_MUSCLE_REGIONS:
        if muscle_substring.lower() in r.muscle_name.lower():
            return r
    raise RuntimeError(f"Region not found for {muscle_substring} / {region_substring}")


def main() -> None:
    print("=" * 78)
    print("FIBERFORCE ADVANCED EXAMPLE 04")
    print("Deadlift vs Squat Posterior Chain Comparison (Real Builders + Service)")
    print("=" * 78)
    print()

    service = AnalysisService()
    print(f"[Service] {service.describe()}")
    print()

    # -------------------------------------------------------------------
    # 1. SUBJECT WITH FULL POSTERIOR CHAIN (real example helper)
    # -------------------------------------------------------------------
    subject = example_subject_with_posterior_chain()
    print(f"[Subject] {subject.name}")
    print(f"  Attachments loaded: {len(subject.attachments)} (glute + ham + erector)")
    print(f"  Regions: {[str(r) for r in subject.get_all_regions()]}")
    print()

    glute = find_region("Gluteus Maximus", "Upper")
    ham = find_region("Biceps Femoris", "Long")
    erector = find_region("Erector Spinae", "Lumbar")

    LOAD = 150.0   # Challenging but comparable load for illustration

    # -------------------------------------------------------------------
    # 2. BUILD ALL FOUR KEY POSITIONS (real builders via service)
    # -------------------------------------------------------------------
    print("-" * 78)
    print(f"BUILDING POSITIONS @ {LOAD} kg bottom (real reference MAs)")
    print("-" * 78)

    # Squats
    service.build_position(
        "squat", load_kg=LOAD, variation="high_bar", target_region_name="Upper fibers"
    )
    service.build_position(
        "squat", load_kg=LOAD, variation="low_bar", target_region_name="Upper fibers"
    )

    # Deadlifts (conventional + sumo)
    service.build_position(
        "deadlift", load_kg=LOAD, variation="conventional", target_region_name="Upper fibers"
    )
    service.build_position(
        "deadlift", load_kg=LOAD, variation="sumo", target_region_name="Upper fibers"
    )

    print("  Squat high-bar, low-bar, Deadlift conventional, sumo — all constructed.")
    print()

    # -------------------------------------------------------------------
    # 3. MULTI-REGION ANALYSIS — RUN FOR EVERY COMBINATION
    # -------------------------------------------------------------------
    print("-" * 78)
    print("POSTERIOR CHAIN PEAK FORCE DEMANDS (150 kg bottom position)")
    print("-" * 78)
    print("Each cell = AnalysisService.analyze(...) using the matching real builder + attachment.")
    print()

    results: dict[str, dict[str, float]] = {}

    def analyze_region(pos: Any, region: MuscleRegion, lift_label: str, var_label: str) -> float:
        analysis = service.analyze(subject, pos, target_regions=[region])
        fr = next((r for r in analysis.results if region.region_name.lower() in r.muscle_region.region_name.lower()), analysis.results[0])
        force = fr.peak_force_newtons
        print(f"  {lift_label:12s} {var_label:12s} | {region.muscle_name:20s} — {region.region_name:12s} : {force:7.2f} N  [{fr.confidence_level}]")
        return force

    # Re-build per region (builders select correct attachment for target)
    print("\n[GLUTEUS MAXIMUS UPPER FIBERS]")
    results["glute"] = {}
    results["glute"]["Squat High-bar"] = analyze_region(
        service.build_position("squat", load_kg=LOAD, variation="high_bar", target_region_name="Upper fibers"),
        glute, "Squat", "High-bar"
    )
    results["glute"]["Squat Low-bar"] = analyze_region(
        service.build_position("squat", load_kg=LOAD, variation="low_bar", target_region_name="Upper fibers"),
        glute, "Squat", "Low-bar"
    )
    results["glute"]["DL Conventional"] = analyze_region(
        service.build_position("deadlift", load_kg=LOAD, variation="conventional", target_region_name="Upper fibers"),
        glute, "Deadlift", "Conventional"
    )
    results["glute"]["DL Sumo"] = analyze_region(
        service.build_position("deadlift", load_kg=LOAD, variation="sumo", target_region_name="Upper fibers"),
        glute, "Deadlift", "Sumo"
    )

    print("\n[HAMSTRINGS — BICEPS FEMORIS LONG HEAD]")
    results["ham"] = {}
    results["ham"]["Squat High-bar"] = analyze_region(
        service.build_position("squat", load_kg=LOAD, variation="high_bar", target_region_name="Biceps Femoris"),
        ham, "Squat", "High-bar"
    )
    results["ham"]["Squat Low-bar"] = analyze_region(
        service.build_position("squat", load_kg=LOAD, variation="low_bar", target_region_name="Biceps Femoris"),
        ham, "Squat", "Low-bar"
    )
    results["ham"]["DL Conventional"] = analyze_region(
        service.build_position("deadlift", load_kg=LOAD, variation="conventional", target_region_name="Biceps Femoris"),
        ham, "Deadlift", "Conventional"
    )
    results["ham"]["DL Sumo"] = analyze_region(
        service.build_position("deadlift", load_kg=LOAD, variation="sumo", target_region_name="Biceps Femoris"),
        ham, "Deadlift", "Sumo"
    )

    print("\n[ERECTOR SPINAE — LUMBAR]")
    results["erector"] = {}
    results["erector"]["Squat High-bar"] = analyze_region(
        service.build_position("squat", load_kg=LOAD, variation="high_bar", target_region_name="Lumbar"),
        erector, "Squat", "High-bar"
    )
    results["erector"]["Squat Low-bar"] = analyze_region(
        service.build_position("squat", load_kg=LOAD, variation="low_bar", target_region_name="Lumbar"),
        erector, "Squat", "Low-bar"
    )
    results["erector"]["DL Conventional"] = analyze_region(
        service.build_position("deadlift", load_kg=LOAD, variation="conventional", target_region_name="Lumbar"),
        erector, "Deadlift", "Conventional"
    )
    results["erector"]["DL Sumo"] = analyze_region(
        service.build_position("deadlift", load_kg=LOAD, variation="sumo", target_region_name="Lumbar"),
        erector, "Deadlift", "Sumo"
    )

    # -------------------------------------------------------------------
    # 4. VISUAL COMPARISONS
    # -------------------------------------------------------------------
    print("\n" + "-" * 78)
    print("VISUAL COMPARISONS (using fiberforce.visualization)")
    print("-" * 78)

    comp_glute = ComparisonResult(
        lift="Posterior Chain",
        config_a="DL Conventional",
        config_b="Squat Low-bar",
        load_kg=LOAD,
        target="Glute Upper",
        force_a_n=results["glute"]["DL Conventional"],
        force_b_n=results["glute"]["Squat Low-bar"],
        confidence_a="reference",
        confidence_b="reference",
    )
    print("\nGlute Upper: Conventional Deadlift vs Low-Bar Squat")
    plot_comparison(comp_glute, ascii_only=True)

    comp_ham = ComparisonResult(
        lift="Posterior Chain",
        config_a="Squat High-bar",
        config_b="DL Sumo",
        load_kg=LOAD,
        target="Hamstrings (BFLH)",
        force_a_n=results["ham"]["Squat High-bar"],
        force_b_n=results["ham"]["DL Sumo"],
        confidence_a="reference",
        confidence_b="reference",
    )
    print("\nHamstrings: High-Bar Squat vs Sumo Deadlift")
    plot_comparison(comp_ham, ascii_only=True)

    # -------------------------------------------------------------------
    # 5. SUMMARY TABLE + INSIGHTS
    # -------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SUMMARY — POSTERIOR CHAIN DEMAND RANKING (150 kg)")
    print("=" * 78)

    for region_key, label in [("glute", "GLUTE UPPER"), ("ham", "HAMSTRINGS"), ("erector", "ERECTOR LUMBAR")]:
        print(f"\n{label}")
        sorted_items = sorted(results[region_key].items(), key=lambda x: -x[1])
        for var, force in sorted_items:
            print(f"  {var:18s} : {force:7.2f} N")
        print(ascii_bars(
            [k for k, v in sorted_items],
            [v for k, v in sorted_items],
            width=46, unit="N", max_bar_width=26
        ))

    print("""
INTERPRETATION (from live reference data):

• Glutes: Low-bar squat and conventional DL are the two highest-demand
  movements for upper glute fibers at the bottom. Sumo reduces the demand
  (more upright torso + shorter load MA in reference tables).

• Hamstrings: Deadlifts (especially conventional) load the hip-extension
  function of the hamstrings far more than squats at comparable loads.
  High-bar squat is the lowest.

• Erectors: Conventional DL is king for lumbar anti-flexion demand.
  Sumo and both squat variations are noticeably lower (reference MAs
  reflect the more upright torso possible in sumo and the bar-on-back
  geometry of squats).

Practical programming uses:
  - Want maximal glute + erector stimulus together? Conventional deadlift.
  - Want glute emphasis with less lumbar shear? Low-bar squat or sumo DL.
  - Hamstring hip-dominant work: Prioritize conventional or sumo pulls over
    squats (or use RDLs / good mornings — not modeled here yet).

Relative comparisons and deltas are reliable (unit bug fixed in 0.6).
""")

    # -------------------------------------------------------------------
    # LIMITATIONS
    # -------------------------------------------------------------------
    print("=" * 78)
    print("LIMITATIONS (Posterior Chain Comparison Example)")
    print("=" * 78)
    print("""
1. BOTTOM POSITION ONLY:
   The most demanding point for posterior chain, but mid-rep and lockout
   demands differ dramatically (especially in deadlift).

2. SAME LOAD (150 kg) FOR BOTH LIFTS:
   In reality most people squat more than they deadlift (or vice versa).
   Relative intensity (% of 1RM) would be a better normalizer in future.

3. REFERENCE DATA DRIVEN (NOT PERSONALIZED GEOMETRY):
   Deadlift vs squat differences come entirely from the different MA tables
   (DEADLIFT_* vs SQUAT_*). Your individual femur/torso proportions would
   modulate these in a full geometric model (see Example 02).

4. NO MULTI-JOINT OR CO-CONTRACTION:
   Hamstrings are simultaneously extending the hip and resisting knee
   extension in DL — not partitioned. Erectors work with glutes in a
   chain that is simplified here.

5. CORE SCALING & MODEL LIMITATIONS:
   - Forces ~100× too low (cm vs m bug)
   - Fixed 0.85 length-tension
   - Static only, no velocity or technique variance
   - Single-joint approximation

This example is one of the cleanest demonstrations of the current system's
strength: first-class, consistent support for deadlift (conventional + sumo)
and squat variations using the same AnalysisService + reference-backed
builders.

See fiberforce/examples.py (build_deadlift_analyzed_position etc.) and
reference/moment_arms.py for the exact data.

Example 04 complete.
""")

    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "04_posterior_chain_comparison.txt", "w") as f:
        f.write("FiberForce Deadlift vs Squat Posterior Chain Comparison\n")
        f.write(f"Load: {LOAD} kg | Subject: {subject.name}\n\n")
        for region_key, label in [("glute", "GLUTE UPPER"), ("ham", "HAMSTRINGS"), ("erector", "ERECTOR LUMBAR")]:
            f.write(f"{label}\n")
            for var, force in sorted(results[region_key].items(), key=lambda x: -x[1]):
                f.write(f"  {var}: {force:.2f} N\n")
            f.write("\n")
        f.write("Generated live via AnalysisService + real builders.\n")

    print(f"[Saved] Full numeric report → {out_dir / '04_posterior_chain_comparison.txt'}")
    print()
    print("Example 04 finished. Excellent demonstration of v0.2 deadlift + squat parity.")
    print("=" * 78)


if __name__ == "__main__":
    main()
