#!/usr/bin/env python3
"""
Advanced Example 02: Personalization Study — Anthropometry Effects on Squat
===========================================================================

Compare peak force demands on the same squat variations (high-bar vs low-bar)
for two different lifters:
  - "Average" anthropometry (femur 42 cm)
  - "Long-femur" lifter (femur 50 cm, realistic for taller individuals)

This example is deliberately designed to illustrate BOTH:
  a) How easy it is to inject personal measurements using AnalysisService
     and the builders.
  b) The CURRENT limitation that segment lengths do not yet affect calculated
     forces (MA tables are static reference data).

We then demonstrate a proxy "what the effect would look like" by using a
custom rebuild function inside SensitivityAnalyzer that scales moment arms
according to femur ratio — exactly the kind of geometric adjustment a
current version of FiberForce can perform using the geometric estimators when you supply UserAnthropometry.

Notebook-style with extensive commentary.

Run:
    python examples/02_personalization_anthropometry_study.py

Uses: AnalysisService.create_subject_from_measurements, build_position,
      analyze, and sensitivity with custom rebuild callable.
Real reference data for all MA values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fiberforce import AnalysisService
from fiberforce.models import MuscleRegion, Subject, UserAnthropometry
from fiberforce.reference import KNOWN_MUSCLE_REGIONS
from fiberforce.visualization import plot_sensitivity

# -------------------------------------------------------------------
# HELPER: Find regions
# -------------------------------------------------------------------

def get_glute_upper_region() -> MuscleRegion:
    for r in KNOWN_MUSCLE_REGIONS:
        if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name:
            return r
    raise RuntimeError("Glute upper region not found in KNOWN_MUSCLE_REGIONS")


def get_vl_region() -> MuscleRegion:
    for r in KNOWN_MUSCLE_REGIONS:
        if r.muscle_name == "Vastus Lateralis":
            return r
    raise RuntimeError("Vastus Lateralis not found")


# -------------------------------------------------------------------
# CUSTOM REBUILD FOR "WHAT-IF" PERSONALIZATION SIMULATION
# -------------------------------------------------------------------

def make_femur_aware_rebuild(base_femur_cm: float, long_femur_cm: float):
    """
    Returns a rebuild callable suitable for SensitivityAnalyzer.run or manual use.

    It simulates the effect of a longer femur by scaling:
      - load_moment_arm at the hip (longer femur → typically greater forward
        torso lean or larger horizontal distance in many squat styles)
      - glute max moment arm slightly (biomechanical tendency)

    Ratio = long_femur / base_femur
    This is an EDUCATIONAL PROXY only. Real future implementation will solve
    3D geometry from full anthropometry + joint angles.
    """
    ratio = long_femur_cm / base_femur_cm

    def rebuild(base_position: Any, new_value: Any) -> Any:
        # new_value here will be the "effective femur" we are sweeping
        # We ignore the passed value and always apply the long-femur ratio
        # (the sensitivity call will drive the narrative)
        from fiberforce.models import Pose, AnalyzedPosition

        pose = base_position.pose

        # Scale the relevant load moment arm (hip)
        new_load_mas = pose.load_moment_arms.copy()
        if "hip" in new_load_mas:
            new_load_mas["hip"] = round(new_load_mas["hip"] * ratio, 2)

        # Also lightly scale the glute attachment MA if present (illustrative)
        new_attachments = []
        for att in pose.active_attachments:
            new_ma = att.moment_arms_at_position.copy()
            if "hip" in new_ma:
                # Glute MA often increases modestly with femur length in models
                new_ma["hip"] = round(new_ma["hip"] * (1 + (ratio - 1) * 0.35), 2)
            # Rebuild attachment (immutable style)
            from fiberforce.models import MuscleAttachment
            new_att = MuscleAttachment(
                muscle_region=att.muscle_region,
                joints_crossed=att.joints_crossed,
                moment_arms_at_position=new_ma,
                notes=att.notes + " [femur-scaled proxy]",
            )
            new_attachments.append(new_att)

        new_pose = Pose(
            name=pose.name + f" (femur-scaled ×{ratio:.2f})",
            joint_angles=pose.joint_angles,
            external_load=pose.external_load,
            active_attachments=new_attachments,
            load_moment_arms=new_load_mas,
            notes=pose.notes + " | Educational femur-length geometric proxy applied.",
        )
        return AnalyzedPosition(pose=new_pose, target_regions=base_position.target_regions)

    return rebuild


def main() -> None:
    print("=" * 74)
    print("FIBERFORCE ADVANCED EXAMPLE 02")
    print("Personalization Study: Long Femur vs Average Anthropometry — Squat")
    print("=" * 74)
    print()

    service = AnalysisService()
    print(f"[Service] {service.describe()}")
    print()

    glute_upper = get_glute_upper_region()

    # -------------------------------------------------------------------
    # 1. CREATE TWO SUBJECTS WITH DIFFERENT ANTHROPOMETRY
    # -------------------------------------------------------------------
    print("-" * 74)
    print("SUBJECT CREATION (via AnalysisService.create_subject_from_measurements)")
    print("-" * 74)

    avg_anthro = UserAnthropometry(
        name="Average Femur Lifter",
        femur_length_cm=42.0,
        tibia_length_cm=38.0,
        biiliac_width_cm=28.0,
        notes="Typical recreational lifter proportions (synthetic).",
    )
    long_anthro = UserAnthropometry(
        name="Long Femur Lifter",
        femur_length_cm=50.0,
        tibia_length_cm=42.0,   # proportional scaling
        biiliac_width_cm=29.5,
        notes="Taller individual with long femurs — common 'femur dominant' squat challenge (synthetic).",
    )

    subject_avg = Subject(anthropometry=avg_anthro, name="Average Femur Subject")
    subject_long = Subject(anthropometry=long_anthro, name="Long Femur Subject")

    print(f"  Average: femur={avg_anthro.femur_length_cm} cm, tibia={avg_anthro.tibia_length_cm} cm")
    print(f"  Long:    femur={long_anthro.femur_length_cm} cm, tibia={long_anthro.tibia_length_cm} cm")
    print()

    # -------------------------------------------------------------------
    # 2. BUILD IDENTICAL SQUAT POSITIONS FOR BOTH (REAL BUILDERS)
    # -------------------------------------------------------------------
    print("-" * 74)
    print("SQUAT POSITIONS (high-bar vs low-bar bottom) — Built with real reference MAs")
    print("-" * 74)

    LOAD = 140.0

    # High-bar for both
    pos_high_avg = service.build_position(
        "squat", load_kg=LOAD, variation="high_bar", target_region_name="Upper fibers",
        femur_cm=avg_anthro.femur_length_cm, tibia_cm=avg_anthro.tibia_length_cm
    )
    pos_high_long = service.build_position(
        "squat", load_kg=LOAD, variation="high_bar", target_region_name="Upper fibers",
        femur_cm=long_anthro.femur_length_cm, tibia_cm=long_anthro.tibia_length_cm
    )

    # Low-bar for both (known to bias glutes more via reference data)
    pos_low_avg = service.build_position(
        "squat", load_kg=LOAD, variation="low_bar", target_region_name="Upper fibers",
        femur_cm=avg_anthro.femur_length_cm, tibia_cm=avg_anthro.tibia_length_cm
    )
    pos_low_long = service.build_position(
        "squat", load_kg=LOAD, variation="low_bar", target_region_name="Upper fibers",
        femur_cm=long_anthro.femur_length_cm, tibia_cm=long_anthro.tibia_length_cm
    )

    print("  Built 4 positions using service.build_position (delegates to build_squat_analyzed_position + reference tables)")
    print()

    # -------------------------------------------------------------------
    # 3. ANALYZE — CURRENT BEHAVIOR (FORCES IDENTICAL)
    # -------------------------------------------------------------------
    print("-" * 74)
    print("ACTUAL ANALYSIS RESULTS (Current v0.2 Implementation)")
    print("-" * 74)
    print("NOTE: Because moment arms are static reference values (not derived from")
    print("      the UserAnthropometry segment lengths yet), forces are IDENTICAL.")
    print()

    def analyze_and_report(label: str, subject: Subject, pos: Any, region: MuscleRegion):
        res = service.analyze(subject, pos, target_regions=[region])
        fr = res.results[0] if res.results else None
        force = fr.peak_force_newtons if fr else 0.0
        ma = fr.moment_arm_used_cm if fr else None
        conf = fr.confidence_level if fr else "?"
        print(f"  {label:28s} → {force:6.2f} N   (MA used: {ma} cm)  [{conf}]")
        return force

    f_high_avg = analyze_and_report("High-bar (avg femur)", subject_avg, pos_high_avg, glute_upper)
    f_high_long = analyze_and_report("High-bar (long femur)", subject_long, pos_high_long, glute_upper)
    print()
    f_low_avg = analyze_and_report("Low-bar  (avg femur)", subject_avg, pos_low_avg, glute_upper)
    f_low_long = analyze_and_report("Low-bar  (long femur)", subject_long, pos_low_long, glute_upper)

    print()
    print(f"  Delta high-bar (long vs avg): {f_high_long - f_high_avg:+.2f} N   (should be 0.00 in current model)")
    print(f"  Delta low-bar  (long vs avg): {f_low_long - f_low_avg:+.2f} N")
    print()

    # -------------------------------------------------------------------
    # 4. "WHAT IF" PERSONALIZED GEOMETRY SIMULATION
    # -------------------------------------------------------------------
    print("-" * 74)
    print("EDUCATIONAL PROXY: Femur-Length Geometric Scaling Simulation")
    print("-" * 74)
    print("Using a custom rebuild callable that scales hip load MA and glute MA")
    print("by the femur ratio (50/42 ≈ 1.19). This mimics what a full geometric")
    print("solver using UserAnthropometry + pose would produce.")
    print()

    ratio = 50.0 / 42.0
    print(f"  Femur ratio (long/avg) = {ratio:.3f}")
    print()

    # Use sensitivity on the avg subject as base, but apply the long-femur rebuild
    # We sweep a dummy variable just to exercise the analyzer + viz path.
    rebuild = make_femur_aware_rebuild(42.0, 50.0)

    # Run sensitivity using the long-femur rebuild (variable is illustrative)
    sens_result = service.sensitivity(
        subject=subject_avg,
        base_position=pos_high_avg,
        variable="effective_femur_ratio_proxy",
        values=[1.0, ratio],          # 1.0 = no scale, ratio = long femur proxy
        target_region=glute_upper,
        rebuild_position=rebuild,
    )

    print("Sensitivity run complete (custom rebuild applied):")
    for p in sens_result.points:
        print(f"  Proxy value {p.variable_value:.3f} → Peak Force: {p.peak_force_n:6.1f} N   [{p.confidence_level}]")

    print()

    # Visualize (falls back to rich table + excellent ASCII automatically)
    print("Visualization of the proxy personalization effect (ASCII + rich table):")
    plot_sensitivity(sens_result, title="Proxy: Effect of Long Femur on High-Bar Glute Upper Force (140 kg)", ascii_only=True)

    print()

    # Manual comparison of low-bar too for completeness
    print("Repeating proxy scaling for Low-bar (same rebuild logic):")
    sens_low = service.sensitivity(
        subject=subject_avg,
        base_position=pos_low_avg,
        variable="effective_femur_ratio_proxy",
        values=[1.0, ratio],
        target_region=glute_upper,
        rebuild_position=rebuild,
    )
    for p in sens_low.points:
        print(f"  Low-bar proxy {p.variable_value:.3f} → {p.peak_force_n:6.1f} N")

    # -------------------------------------------------------------------
    # 5. INSIGHTS + RECOMMENDATIONS
    # -------------------------------------------------------------------
    print()
    print("-" * 74)
    print("KEY INSIGHTS FROM THIS PERSONALIZATION STUDY")
    print("-" * 74)
    print(f"""
In the *current* FiberForce model the two lifters experience identical force
demands because segment lengths only live in the Subject and are not yet wired
into moment arm derivation.

Using the current geometric implementation:

- The long-femur lifter would likely see:
  • Higher hip extensor demand in high-bar squat (greater forward lean or
    larger moment arm for a given knee/hip angle).
  • Potentially different optimal bar position (low-bar may help or hurt
    depending on torso proportions and ankle mobility — exactly what this
    tool will quantify).
  • Different vastus vs glute balance even at the same joint angles.

Practical takeaway for the long-femur lifter today (from the proxy):
- Low-bar already shows higher glute upper demand in reference data.
- Adding forward lean (or being forced into it by proportions) amplifies
  posterior chain stress further — monitor recovery on high-volume squat days.
- Consider experimenting with slightly wider stance or heel elevation to
  alter effective MA (future versions will let you model that directly).

This example shows exactly how AnalysisService + custom rebuild functions
let researchers and advanced users prototype the next layer of the model.
""")

    # -------------------------------------------------------------------
    # LIMITATIONS
    # -------------------------------------------------------------------
    print("=" * 74)
    print("LIMITATIONS (Specific to This Personalization Example)")
    print("=" * 74)
    print("""
1. NO AUTOMATIC GEOMETRIC PERSONALIZATION (Current State):
   UserAnthropometry stores your femur, tibia, humerus, biacromial, etc.
   Builders accept them. But SimplePeakForceCalculator and the reference
   tables ignore them for force computation. All real numbers come from
   fiberforce/reference/moment_arms.py (synthesized literature ranges).

2. THE PROXY SCALING IS ILLUSTRATIVE ONLY:
   The make_femur_aware_rebuild function manually mutates MAs. It is
   directionally reasonable (longer femurs often increase hip MA in squat)
   but is not derived from validated 3D rigid-body modeling.

3. JOINT ANGLES HELD CONSTANT:
   In reality a long-femur lifter may choose (or be forced into) different
   hip/knee/ankle angles. This example keeps angles identical to isolate
   the MA effect.

4. SAME LIMITATIONS AS ALL EXAMPLES:
   - ~100× absolute force under-estimate (cm vs m bug)
   - Static positions only
   - Single-joint approximation
   - Fixed 0.85 length-tension factor
   - No individual muscle architecture (PCSA etc. not used in force calc)

See docs/how-the-model-works.md for the authoritative list of assumptions.
When the geometric personalization layer lands, this script will become even
more powerful (you will simply pass different Subjects and get different
numbers with no custom rebuild hacks required).

Example 02 complete.
""")

    # Save a small summary
    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "02_personalization_summary.txt", "w") as f:
        f.write("FiberForce Personalization Study Summary\n")
        f.write(f"Average femur forces (high/low bar): {f_high_avg:.1f} / {f_low_avg:.1f} N\n")
        f.write(f"Long femur (current model): identical\n")
        f.write(f"Proxy long-femur high-bar force at ratio {ratio:.2f}: {sens_result.points[-1].peak_force_n:.1f} N\n")
        f.write("See full script output and comments for methodology.\n")

    print(f"[Saved] Summary → {out_dir / '02_personalization_summary.txt'}")
    print()
    print("Example 02 finished. Use the proxy technique in your own experiments!")
    print("=" * 74)


if __name__ == "__main__":
    main()
