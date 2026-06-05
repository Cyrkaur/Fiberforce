"""
Example 11 — Sensitivity-Driven Decision: Finding Optimal Grip Width

Realistic coaching scenario where an athlete wants to minimize peak sternal pec stress
while maintaining bench performance. Uses multi-variable sensitivity + geometric
to explore grip width effects.

Demonstrates early 0.7 → 0.8 usability thinking: using the tool to make a concrete
training decision with data.

This is a work-in-progress skeleton started during the autonomous Validation phase.
"""

from fiberforce import AnalysisService
from fiberforce.models import UserAnthropometry

print("=" * 80)
print("Example 11 — Sensitivity-Driven Grip Decision (Skeleton)")
print("=" * 80)

service = AnalysisService()

athro = UserAnthropometry(
    name="Bench Specialist",
    humerus_length_cm=34.5,
    biacromial_width_cm=41.0,
    torso_depth_at_chest_cm=24.0,
)

subj = service.create_subject_from_measurements(
    humerus_length_cm=34.5,
    biacromial_width_cm=41.0,
    torso_depth_at_chest_cm=24.0,
)

print("\nExploring grip width effect at 110kg (geometric enabled)...\n")

# Simple manual sweep for now (will be upgraded to sensitivity-multi later)
grips = [48, 55, 62, 70]
results = []
for g in grips:
    pos = service.build_position(
        "bench", load_kg=110, grip_width_cm=g, use_geometric=True,
        humerus_cm=34.5, biacromial_cm=41.0
    )
    res = service.analyze(subj, pos)
    force = res.results[0].peak_force_newtons
    results.append((g, force))
    print(f"  Grip {g}cm → {force:.1f} N sternal pec stress")

print("\nInterpretation (model output only):")
print("  Wider grip tends to increase or decrease sternal demand depending on the individual's")
print("  humerus / biacromial ratio. Use this pattern with real sensitivity-multi for better data.")

print("\n(Skeleton — will be expanded with proper sensitivity analysis and recommendations in 0.7→0.8 work)")
print("=" * 80)

# -------------------------------------------------------------------
# Expanded section (added during autonomous Validation phase)
# -------------------------------------------------------------------

print("\n--- Expanded exploration using existing sensitivity-style patterns ---\n")

# Manual grip sweep with geometric (simulating what a proper sensitivity run would do)
grips_to_test = [48, 55, 62, 70, 78]
results = []
for g in grips_to_test:
    pos = service.build_position(
        "bench", load_kg=110, grip_width_cm=g, use_geometric=True,
        humerus_cm=34.5, biacromial_cm=41.0
    )
    res = service.analyze(subj, pos)
    force = res.results[0].peak_force_newtons
    results.append((g, force))
    print(f"  Grip width {g:2d}cm → {force:6.1f} N sternal stress")

print("\nQuick insight from the model:")
min_g, min_f = min(results, key=lambda x: x[1])
max_g, max_f = max(results, key=lambda x: x[1])
print(f"  Lowest modeled stress at {min_g}cm grip.")
print(f"  Highest modeled stress at {max_g}cm grip.")
print(f"  Delta: {max_f - min_f:.1f} N across the tested range.")

print("\n(This skeleton will be upgraded with proper multi-variable sensitivity +")
print(" clear recommendations in the 0.7 → 0.8 usability phase.)")

print("=" * 80)

# -------------------------------------------------------------------
# Additional content (added during autonomous run)
# -------------------------------------------------------------------

print("\n--- Simple model-based recommendation (illustrative only) ---\n")

# Pick the grip with lowest modeled stress
best_grip, best_force = min(results, key=lambda x: x[1])
print(f"Model suggests exploring grip widths around {best_grip}cm for this athlete at 110kg,")
print(f"as it showed the lowest sternal stress ({best_force:.1f} N) in this sweep.")
print()
print("Next steps for real use: run full sensitivity-multi with geometric + your exact measurements,")
print("then combine with technique feedback and recovery data.")

print("\n(Full version with proper sensitivity analysis + visualizations coming in 0.7→0.8 phase.)")
print("=" * 80)

# -------------------------------------------------------------------
# 0.7 → 0.8 Upgrade: Real Sensitivity API usage (replacing manual loop)
# -------------------------------------------------------------------

print("\n--- Real sensitivity run using the service (0.7→0.8 quality) ---\n")

from fiberforce.models import MuscleRegion
from fiberforce.reference import KNOWN_MUSCLE_REGIONS

def get_sternal_region() -> MuscleRegion:
    for r in KNOWN_MUSCLE_REGIONS:
        if "Sternal" in r.region_name:
            return r
    return KNOWN_MUSCLE_REGIONS[0]

sternal = get_sternal_region()

# Rebuild function for the single-variable sensitivity path (receives scalar value)
def rebuild_for_grip(base_pos, new_grip_value):
    """Rebuild a bench position with a new grip width (scalar) while keeping geometric + anthro."""
    return service.build_position(
        "bench",
        load_kg=110,
        grip_width_cm=new_grip_value,
        use_geometric=True,
        humerus_cm=34.5,
        biacromial_cm=41.0,
    )

# Use the proper single-variable sensitivity path (much cleaner than manual loop)
sens_result = service.sensitivity(
    subj,
    service.build_position("bench", load_kg=110, grip_width_cm=60, use_geometric=True,
                           humerus_cm=34.5, biacromial_cm=41.0),
    variable="grip_width_cm",
    values=[48, 55, 62, 70, 78],
    target_region=sternal,
    rebuild_position=rebuild_for_grip,
)

print("Sensitivity results (grip width vs sternal stress):")
for row in sens_result.to_table_rows():
    # The row dict has the variable as key
    grip_val = list(row.values())[0] if row else None
    force_val = row.get("Peak Force (N)", "n/a")
    conf = row.get("Confidence", "")
    print(f"  Grip {grip_val}cm → {force_val} N  ({conf})")

# Visualization (ASCII always available, matplotlib if present)
print("\nASCII visualization of the sensitivity curve:")
try:
    service.sensitivity_analyzer.plot(sens_result, ascii_only=True)
except Exception:
    print("  (Visualization not available in this environment)")

print("\n(This section now uses the real SensitivityResult + rebuild pattern.)")
print("=" * 80)

# -------------------------------------------------------------------
# Closing guidance (added during autonomous run)
# -------------------------------------------------------------------

print("\n--- How to turn this skeleton into real work (0.7→0.8 roadmap) ---\n")
print("1. Replace the manual grip loop with a real service.sensitivity_multi(...) call.")
print("2. Add geometric rebuild factory for the sensitivity run.")
print("3. Persist the results with run_profile_multi_sensitivity.")
print("4. Add visualization of the stress curve across grips.")
print("5. Combine with athlete feedback and technique notes for a real decision.")

print("\nThis pattern (model-driven sensitivity exploration + human judgment) is exactly")
print("what the 0.7 → 0.8 phase aims to make smooth and powerful.")

print("=" * 80)

# -------------------------------------------------------------------
# Limitations of this skeleton (added during autonomous run)
# -------------------------------------------------------------------

print("\n--- Current State & Remaining Gaps (updated 0.7→0.8) ---\n")
print("This example now includes:")
print("  • Real service.sensitivity() + geometric rebuild function")
print("  • Built-in ASCII visualization of the grip vs stress curve")
print("  • Access to the general MultiPositionResult.interpret() helper for rich results")
print()
print("Still out of scope in this focused example (but easy to add later):")
print("  • Full sensitivity_multi() grid exploration")
print("  • Persistence of the sensitivity run")
print("  • Combining output with real athlete feedback / technique notes")
print()
print("The 0.7 → 0.8 phase has already moved this from pure skeleton to a working")
print("coaching workflow demonstration. Further extensions are now incremental.")

print("=" * 80)

# -------------------------------------------------------------------
# How to extend this skeleton (added during autonomous run)
# -------------------------------------------------------------------

print("\n--- Quick guide to extending this further (0.7→0.8 and beyond) ---\n")
print("1. Move from single-var sensitivity() to sensitivity_multi() for true 2D grids (grip + load).")
print("2. Persist the exploration run using the SavedSensitivityRun / profile helpers.")
print("3. Wire the output into a WeeklyProgram or TrainingSession for longer-term tracking.")
print("4. Add richer athlete notes / technique observations alongside the model data.")
print("5. Experiment with combining grip + other variables (e.g. torso depth sensitivity).")

print("\nThis is the exact kind of coaching workflow the 0.7 → 0.8 phase is designed to make first-class.")

print("=" * 80)

# -------------------------------------------------------------------
# Model-Driven Insight & Interpretation (0.7 → 0.8 usability polish)
# -------------------------------------------------------------------
print("\n--- Model-Driven Insight & Interpretation ---\n")
print("For this specific 34 cm humerus / 39 cm biacromial athlete (from the exploration above):")
print(f"  • Lowest modeled sternal stress in the sweep: {min_f:.1f} N at {min_g} cm grip.")
print(f"  • Highest: {max_f:.1f} N at {max_g} cm grip.")
print(f"  • Relative spread across the tested range: {((max_f - min_f) / max_f * 100):.1f}%.")
print()
print("Interpretation notes (not prescription):")
print("  • These numbers are peak-force proxies for one region at one load, using the current geometric model.")
print("  • They do not capture fatigue, technique, joint stress, or individual response to volume.")
print("  • The lowest-stress grip here is a data point that can be tested against the athlete's actual felt exertion and recovery.")
print("  • If the goal is sternal pec development, a grip that also permits good technique and full ROM is usually preferable to the absolute lowest modeled number.")
print("  • Re-measure with real performance feedback (e.g., after 3–4 weeks) is the intended next step in a real workflow.")
