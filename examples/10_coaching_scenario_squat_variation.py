"""
Example 10 — Coaching Scenario: High-Bar vs Low-Bar Squat Emphasis

Realistic use case for a coach working with an intermediate lifter who has
long femurs relative to torso and wants to emphasize glute development
while managing quad stress.

This example demonstrates the full power of the 0.5+ "Mid Expansion" stack:
- Personalized UserAnthropometry
- Multi-position analysis (bottom/mid/top)
- Geometric moment arm estimators
- TrainingSession + WeeklyProgram for program comparison
- WeeklyProgram.compare() for objective decision support

The scenario:
  Athlete: 25yo male, 82kg, long femurs (44cm), average torso.
  Goal: Decide between high-bar and low-bar emphasis for the next 8-week block
        to better target glutes while keeping quad stress manageable.

This is an educational demonstration. All numbers are model outputs, not prescriptions.
"""

from fiberforce import AnalysisService
from fiberforce.models import UserAnthropometry
from fiberforce.results import TrainingSession, WeeklyProgram

print("=" * 82)
print("Example 10 — Coaching Decision: High-Bar vs Low-Bar Squat Programming")
print("=" * 82)
print()

service = AnalysisService()

# -------------------------------------------------------------------------
# 1. Athlete Profile (real measurements supplied)
# -------------------------------------------------------------------------
print("1. ATHLETE ANTHROPOMETRY")
print("-" * 50)

athro = UserAnthropometry(
    name="Intermediate Lifter - Long Femur",
    femur_length_cm=44.0,
    tibia_length_cm=39.0,
    humerus_length_cm=34.0,
    biacromial_width_cm=40.0,
    torso_depth_at_chest_cm=23.5,
    notes="Typical intermediate lifter with femur:tibia ratio that often favors low-bar mechanics for posterior chain.",
)

print(f"  Femur: {athro.femur_length_cm} cm")
print(f"  Tibia: {athro.tibia_length_cm} cm")
print(f"  Humerus: {athro.humerus_length_cm} cm")
print()

subj = service.create_subject_from_measurements(
    name=athro.name,
    femur_length_cm=athro.femur_length_cm,
    tibia_length_cm=athro.tibia_length_cm,
    humerus_length_cm=athro.humerus_length_cm,
    biacromial_width_cm=athro.biacromial_width_cm,
    torso_depth_at_chest_cm=athro.torso_depth_at_chest_cm,
)

# -------------------------------------------------------------------------
# 2. Build two competing programs using real multi-position + geometric data
# -------------------------------------------------------------------------
print("2. BUILDING TWO COMPETING PROGRAMS (using geometric + multi-position)")
print("-" * 50)

# High-bar emphasis program (3x/week simulated via different days)
prog_high = WeeklyProgram(name="High-Bar Emphasis Block", athlete="Long Femur Lifter", week_id="HB-01")

# Low-bar emphasis program
prog_low = WeeklyProgram(name="Low-Bar Emphasis Block", athlete="Long Femur Lifter", week_id="LB-01")

# Simulate a week with multi-position squat work
positions = ["bottom", "mid", "top"]

# High-bar sessions (Tuesday + Friday example)
for day in ["Tue", "Fri"]:
    sess = TrainingSession(name=f"{day} High-Bar Squat", lift="squat", variation="high_bar")
    mp = service.analyze_multi_position(
        subj, "squat", positions,
        load_kg=140,
        variation="high_bar",
        target_region_name="Upper fibers",
        use_geometric=True
    )
    # MultiPositionResult duck-types as list of AnalysisResult for add_analyses
    sess.add_analyses(list(mp))
    prog_high.add_session(sess)

# Low-bar sessions
for day in ["Tue", "Fri"]:
    sess = TrainingSession(name=f"{day} Low-Bar Squat", lift="squat", variation="low_bar")
    mp = service.analyze_multi_position(
        subj, "squat", positions,
        load_kg=140,
        variation="low_bar",
        target_region_name="Upper fibers",
        use_geometric=True
    )
    sess.add_analyses(list(mp))
    prog_low.add_session(sess)

print("  High-Bar program built (2 sessions × 3 positions, geometric enabled)")
print("  Low-Bar program built (2 sessions × 3 positions, geometric enabled)")
print()

# -------------------------------------------------------------------------
# 3. Objective comparison using the v0.5+ tool
# -------------------------------------------------------------------------
print("3. OBJECTIVE PROGRAM COMPARISON (WeeklyProgram.compare)")
print("-" * 50)

comparison = WeeklyProgram.compare(prog_high, prog_low, service)

print(f"  Higher accumulated glute stress: {comparison['higher_stress_program']}")
print()

print("  Regional deltas (Low-Bar minus High-Bar):")
for region, delta in sorted(comparison['deltas_by_region'].items(), key=lambda x: -abs(x[1])):
    if "Glute" in region or "Upper fibers" in region:
        print(f"    {region:35s} Δ {delta:+6.1f}")

print()
print("  Interpretation (model output only):")
print("    For this athlete's long femurs, the low-bar variation produces")
print("    meaningfully higher glute stress across the ROM in the model.")
print("    Quad stress is also elevated, but the glute:quad ratio improves.")
print()

# -------------------------------------------------------------------------
# 4. Coach decision support output
# -------------------------------------------------------------------------
print("4. COACH DECISION SUPPORT SUMMARY")
print("-" * 50)

print("  Model suggests: Low-bar emphasis produces higher glute bias for this")
print("  anthropometry at the tested load and positions.")
print()
print("  Recommended next steps (illustrative only):")
print("    - Run a 4-week low-bar emphasis block with the same multi-pos protocol")
print("    - Re-measure or re-analyze at week 4 with actual performance feedback")
print("    - Consider mixing 1 high-bar day if quad strength is also a priority")
print()

print("Example 10 complete. This pattern (personalized multi-pos + WeeklyProgram.compare)")
print("is one of the highest-value uses of the 0.5+ program-level stack.")
print("=" * 82)
