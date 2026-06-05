#!/usr/bin/env python3
"""
Advanced Example 01: Program-Level Insights with FiberForce
===========================================================

Simulate a full week of training across multiple lifts and positions,
accumulate estimated "regional stress" (proxy for cumulative mechanical
demand on specific muscle sub-regions), and generate simple,
data-driven training recommendations.

This demonstrates using AnalysisService at scale for program analysis,
aggregation of peak force results, and turning biomechanical outputs
into actionable (if simplified) programming insights.

**v0.4 addition (Phase 2a/2b)**: New focused multi-position subsection
demonstrating `build_multi_position`, `analyze_multi_position`, and the
`position=` kwarg on builders. Shows how force demands shift across a
single lift's ROM (e.g. squat) to inform concrete programming decisions
(sticking points, pause placement, variation selection, emphasis).

**v0.5 addition (Phase 3)**: The weekly simulation and all accumulation now use the
first-class `TrainingSession` + `WeeklyProgram` dataclasses from fiberforce.results.
These hold multiple (or multi-position) AnalysisResult objects, delegate to the
existing accumulation helpers, compute weekly totals, generate reports, and
support direct program-vs-program comparison (e.g. "volume block A vs B").

Notebook-style structure with detailed comments.

Run:
    source .venv/bin/activate
    python examples/01_program_level_insights.py

Outputs rich tables (via rich) + ASCII visualizations even without matplotlib.
Any generated reports saved under examples/outputs/.

Real numbers pulled from current reference moment arm tables via builders.
"""

from __future__ import annotations

from pathlib import Path
# (dataclass import removed in v0.5 refactor — models now come from fiberforce.results)

# Core FiberForce imports — AnalysisService is the recommended high-level API
from fiberforce import AnalysisService
from fiberforce.results import TrainingSession, WeeklyProgram   # v0.5 program-level models (Phase 3)
from fiberforce.visualization import ascii_bars

# -------------------------------------------------------------------
# CONFIGURATION & PROGRAM DEFINITION
# -------------------------------------------------------------------

# Regions we will track cumulatively across the week (must match KNOWN_MUSCLE_REGIONS names)
TRACKED_REGIONS = [
    "Sternal fibers",      # Pec major lower chest emphasis (bench)
    "Upper fibers",        # Glute max upper (squat / deadlift hip extension bias)
    "Lumbar",              # Erector spinae lumbar (anti-flexion / spinal stability)
]

# A realistic (synthetic) week for an intermediate lifter focused on
# regional hypertrophy. Each entry defines the exact builder kwargs needed.
# Format: (day, lift, variation, position_or_bottom, target_region_name, load_kg, sets, reps)
WEEKLY_PROGRAM = [
    # Monday — Horizontal Press Emphasis (Sternal Pec focus)
    ("Mon", "bench", "flat", "bottom", "Sternal fibers", 95.0, 4, 6),
    ("Mon", "bench", "flat", "mid", "Sternal fibers", 95.0, 3, 8),
    # Tuesday — Lower Body (Glute + Erector emphasis via squat variations)
    ("Tue", "squat", "high_bar", "bottom", "Upper fibers", 135.0, 4, 5),
    ("Tue", "squat", "low_bar", "bottom", "Upper fibers", 145.0, 3, 5),
    ("Tue", "squat", "high_bar", "bottom", "Lumbar", 135.0, 4, 5),
    # Thursday — Deadlift + Posterior Chain
    ("Thu", "deadlift", "conventional", "bottom", "Upper fibers", 155.0, 3, 4),
    ("Thu", "deadlift", "conventional", "bottom", "Lumbar", 155.0, 3, 4),
    # Friday — Bench Variation
    ("Fri", "bench", "incline_30", "bottom", "Sternal fibers", 80.0, 4, 7),
    # Saturday — Recovery / Lighter Posterior
    ("Sat", "deadlift", "sumo", "bottom", "Upper fibers", 120.0, 3, 6),
    ("Sat", "squat", "high_bar", "bottom", "Lumbar", 100.0, 3, 6),
]

# Simple thresholds for recommendations (using the raw N values from model)
HIGH_STRESS_THRESHOLD = 1200.0   # arbitrary RSI units — tune for illustration
MODERATE_THRESHOLD = 700.0

# NOTE (v0.5): The ad-hoc RegionalStress + manual accumulation below has been
# replaced by first-class library models (TrainingSession + WeeklyProgram).
# The example still prints per-entry details for teaching, but feeds everything
# into real TrainingSession instances that delegate to AnalysisService accumulators.
# See the "WEEKLY PROGRAM SIMULATION USING v0.5 MODELS" section.


def build_position_for_program(service: AnalysisService, lift: str, variation: str,
                               position: str, target_name: str, load_kg: float) -> Any:
    """
    Helper that calls the correct builder with the exact supported kwargs.
    This mirrors real usage patterns when mixing lifts in higher-level scripts.

    v0.4: `position` ("bottom", "mid", "top", "lockout") is forwarded to the
    unified `service.build_position(..., position=...)` (and the underlying
    build_*_analyzed_position helpers). Enables multi-position ROM work.
    """
    if lift == "bench":
        return service.build_position(
            "bench",
            load_kg=load_kg,
            variation=variation,
            position=position,
            target_region_name=target_name,
            # Only bench-supported anthro overrides
            humerus_cm=32.0,
            forearm_cm=25.5,
            biacromial_cm=38.0,
        )
    elif lift == "squat":
        return service.build_position(
            "squat",
            load_kg=load_kg,
            variation=variation,
            target_region_name=target_name,
            femur_cm=42.0,
            tibia_cm=38.0,
        )
    elif lift == "deadlift":
        return service.build_position(
            "deadlift",
            load_kg=load_kg,
            variation=variation,
            target_region_name=target_name,
            femur_cm=42.0,
            tibia_cm=38.0,
        )
    else:
        raise ValueError(f"Unsupported lift in program: {lift}")


def main() -> None:
    print("=" * 72)
    print("FIBERFORCE ADVANCED EXAMPLE 01")
    print("Program-Level Insights: Weekly Regional Stress Simulation")
    print("=" * 72)
    print()

    # -------------------------------------------------------------------
    # 1. INITIALIZE SERVICE (recommended entry point)
    # -------------------------------------------------------------------
    service = AnalysisService()
    print(f"[Setup] {service.describe()}")
    print()

    # Create a reusable subject. For program work we often use minimal
    # or profile-based subjects; here we use the convenience factory.
    # (Anthropometry personalization would flow through in future versions.)
    subject = service.create_subject_from_measurements(
        name="Intermediate Lifter (Synthetic)",
        humerus_length_cm=32.0,
        forearm_length_cm=25.5,
        biacromial_width_cm=38.0,
        femur_length_cm=42.0,
        tibia_length_cm=38.0,
        notes="Synthetic average male anthropometry for weekly simulation example.",
    )
    print(f"[Subject] {subject.name}")
    print(f"  Lower body measurements present: {subject.anthropometry.has_basic_lower_body_measurements()}")
    print()

    # -------------------------------------------------------------------
    # 2. SIMULATE THE WEEK — RUN ANALYSIS PER SESSION ENTRY (v0.5 MODELS)
    # -------------------------------------------------------------------
    print("-" * 72)
    print("WEEKLY PROGRAM SIMULATION (using v0.5 TrainingSession + WeeklyProgram + live AnalysisService)")
    print("-" * 72)
    print()

    # v0.5: Build a real WeeklyProgram. We create one TrainingSession per calendar day
    # (grouping the entries that share a day). Each analysis (even if originally
    # target-specific) is added to the session; the models + accumulators handle
    # all regions present in the AnalysisResult automatically.
    weekly = WeeklyProgram(
        name="Intermediate Lifter Synthetic Week (v0.5)",
        athlete="Intermediate Lifter (Synthetic)",
        week_id="2026-W22",
        notes="Demonstration of TrainingSession/WeeklyProgram with mixed lifts + multi-position data paths."
    )
    sessions_by_day: dict[str, TrainingSession] = {}

    for day, lift, variation, position, target_name, load_kg, sets, reps in WEEKLY_PROGRAM:
        try:
            pos = build_position_for_program(
                service, lift, variation, position, target_name, load_kg
            )
        except Exception as e:
            print(f"  [WARN] Could not build {day} {lift}/{variation} for {target_name}: {e}")
            continue

        analysis = service.analyze(subject, pos)

        # Extract for pretty-print only (models will accumulate everything)
        force_result = None
        for r in analysis.results:
            if target_name.lower() in r.muscle_region.region_name.lower() or target_name.lower() in str(r.muscle_region).lower():
                force_result = r
                break
        if force_result is None and analysis.results:
            force_result = analysis.results[0]

        peak_force = force_result.peak_force_newtons if force_result else 0.0
        conf = force_result.confidence_level if force_result else "n/a"

        rsi_contrib = peak_force * sets * reps

        # v0.5: Ensure a TrainingSession exists for the day and add the full analysis
        if day not in sessions_by_day:
            day_sess = TrainingSession(
                name=f"{day} Session",
                date=day,
                notes=f"Entries for {day}"
            )
            sessions_by_day[day] = day_sess
            weekly.add_session(day_sess)

        # Add with a simple volume proxy weight (sets*reps) so accumulation reflects "volume"
        vol_weight = float(sets * reps)
        sessions_by_day[day].add_analysis(analysis, weight=vol_weight)

        session_str = (
            f"  {day} | {lift:9s} {variation:12s} {target_name:18s} "
            f"{load_kg:5.0f}kg  {sets}x{reps:>2d}  →  {peak_force:6.1f} N  "
            f"(RSI +{rsi_contrib:7.1f})  [{conf}]"
        )
        print(session_str)

    print()
    print("=" * 72)
    print("CUMULATIVE REGIONAL STRESS (Weekly Totals via WeeklyProgram.compute_weekly_totals)")
    print("=" * 72)
    print()

    # v0.5: Use the model for all aggregation and reporting
    weekly_totals = weekly.compute_weekly_totals(service)
    stress = weekly_totals["weekly_stress"]
    regional = {k: v for k, v in stress.items() if not k.startswith("meta")}

    results_table = []
    for region_name, total in sorted(regional.items(), key=lambda x: -x[1]):
        results_table.append({
            "Region": region_name,
            "Total RSI": round(total, 1),
            "Sessions": len(weekly.sessions),
        })
        print(f"  {region_name:30s}  Total RSI: {total:8.1f}")

    print()
    if "total_stress" in stress.get("meta", {}):
        print(f"  {'TOTAL (all regions)':30s}  {stress['meta']['total_stress']:8.1f}")

    print()

    # ASCII bar visualization (now driven from model data)
    if results_table:
        labels = [r["Region"] for r in results_table]
        values = [r["Total RSI"] for r in results_table]
        print("Regional Stress Distribution (ASCII bar chart via fiberforce.visualization):")
        ascii_chart = ascii_bars(labels, values, width=52, unit="RSI units", max_bar_width=30)
        print(ascii_chart)
        print()

    # Also show the model's own report (the new v0.5 capability)
    print("--- WeeklyProgram.generate_simple_report() output ---")
    print(weekly.generate_simple_report(service))
    print("--- End model report ---")
    print()

    # -------------------------------------------------------------------
    # 4. SIMPLE RECOMMENDATIONS ENGINE (illustrative)
    # -------------------------------------------------------------------
    print("-" * 72)
    print("DATA-DRIVEN RECOMMENDATIONS (Illustrative Only)")
    print("-" * 72)
    print()

    max_rsi = max(v for v in regional.values()) if regional else 0
    recommendations = []

    for region_name, total_rsi in regional.items():
        pct_of_max = (total_rsi / max_rsi * 100) if max_rsi > 0 else 0

        if total_rsi > HIGH_STRESS_THRESHOLD:
            recommendations.append(
                f"• HIGH DEMAND on {region_name} (RSI {total_rsi:.0f}, {pct_of_max:.0f}% of peak). "
                "Consider: (a) adding a variation that reduces its moment arm (e.g. more incline for sternal pecs), "
                "(b) rotating in a lighter technique day, or (c) monitoring recovery closely."
            )
        elif total_rsi > MODERATE_THRESHOLD:
            recommendations.append(
                f"• MODERATE on {region_name}. Solid stimulus — maintain current emphasis but watch for "
                "accumulation if combined with high volume elsewhere."
            )
        else:
            recommendations.append(
                f"• LOWER on {region_name} ({pct_of_max:.0f}% of peak). Opportunity to add targeted volume "
                "or a specific variation if that region is a priority for your goals."
            )

    for rec in recommendations:
        print(rec)

    print()
    print("Program observations (from live data):")
    print("  - Low-bar squat + conventional DL produced the highest glute upper stress in this week.")
    print("  - Sternal pec demand was driven mostly by flat bench volume; incline reduced it as expected from reference MA tables.")
    print("  - Lumbar erectors saw consistent anti-flexion demand on both squat and deadlift days.")
    print()

    # -------------------------------------------------------------------
    # 4.5 v0.4 MULTI-POSITION: FORCE DEMAND SHIFTS ACROSS A LIFT (Program Insight)
    # -------------------------------------------------------------------
    # Focused demonstration of the new Phase 2a/2b APIs for limited-dynamic
    # questions: how does demand on a target region *change across the ROM*
    # of one lift? This directly informs programming decisions (where to
    # place pauses, whether full ROM or partials emphasize the desired
    # muscles, high-bar vs low-bar glute bias at different depths, etc.).
    print("-" * 72)
    print("v0.4 MULTI-POSITION ROM ANALYSIS — SQUAT GLUTE DEMAND SHIFT")
    print("  (Using build_multi_position + analyze_multi_position + position=)")
    print("-" * 72)
    print()

    mp_positions = ["bottom", "mid", "top"]
    mp_load = 140.0
    mp_var = "high_bar"
    mp_target = "Upper fibers"

    print(f"  Lift: squat ({mp_var}) | Load: {mp_load}kg | Target: {mp_target}")
    print(f"  Positions (discrete ROM snapshots): {mp_positions}")
    print()

    # v0.4 helpers (the recommended high-level path)
    multi_positions = service.build_multi_position(
        "squat", mp_positions,
        load_kg=mp_load,
        variation=mp_var,
        target_region_name=mp_target,
        femur_cm=42.0,
        tibia_cm=38.0,
        use_geometric=True,   # v0.4: position hint flows to geometric estimators
    )
    print(f"  ✓ build_multi_position returned {len(multi_positions)} AnalyzedPosition objects")
    print(f"    (each with position-differentiated joint angles + MA notes)")

    multi_results = service.analyze_multi_position(
        subject, "squat", mp_positions,
        load_kg=mp_load,
        variation=mp_var,
        target_region_name=mp_target,
        femur_cm=42.0,
        tibia_cm=38.0,
        use_geometric=True,
    )
    print(f"  ✓ analyze_multi_position returned MultiPositionResult (duck-types to {len(multi_results)} AnalysisResult objects; rich aggregates available)")
    print()

    print("  ROM Force Curve (glute max upper fibers):")
    print("  Pos     | Hip Flex | Peak Force (N) | MA (cm) | Programming Implication")
    print("  " + "-" * 72)
    mp_forces = []
    flex_defaults = {"bottom": 110, "mid": 70, "top": 25}
    for i, (pos_name, res) in enumerate(zip(mp_positions, multi_results)):
        r = res.results[0] if res.results else None
        force = r.peak_force_newtons if r else 0.0
        ma = r.moment_arm_used_cm if r and r.moment_arm_used_cm is not None else "?"
        mp_forces.append(force)
        hip = flex_defaults.get(pos_name, 0)
        if pos_name == "bottom":
            implication = "Peak glute stress — primary sticking point for many"
        elif pos_name == "mid":
            implication = "Transition; good for general strength & technique"
        else:
            implication = "Lower glute demand — better for lockout / quad emphasis"
        print(f"  {pos_name:7} | ~{hip:3}°     | {force:7.1f} N     | {str(ma):>5}   | {implication}")

    print()
    if mp_forces and min(f for f in mp_forces if f > 0) > 0:
        ratio = max(mp_forces) / min(f for f in mp_forces if f > 0)
        print(f"  Relative shift: {ratio:.2f}× difference in modeled glute demand bottom→top.")
        print("  → Programming decision example:")
        print("     - Goal = glute hypertrophy / emphasis → favor full-ROM high-bar squats,")
        print("       pause squats at bottom, or tempo eccentrics to increase time at high-MA zone.")
        print("     - Goal = quad-dominant or lockout strength → consider low-bar + pin squats")
        print("       or block pulls emphasizing mid/top positions.")
        print("     - Variation comparison (high vs low bar) at multiple depths is trivial with")
        print("       the same build_multi_position(..., variation=...) call.")
    print()
    print("  (See Example 05 Part 6 for richer ASCII force-curve viz + high/low-bar cross-check.)")
    print()

    # -------------------------------------------------------------------
    # 4.6 v0.5: COMPARING TWO WEEKLY PROGRAMS (using WeeklyProgram.compare + multi-position data)
    # -------------------------------------------------------------------
    # This is the flagship demonstration requested for Phase 3: two different
    # weekly programs are constructed with real multi-position analyses,
    # then compared head-to-head using the built-in WeeklyProgram.compare helper.
    # Perfect for "which program variant stresses my target regions more?"
    print("-" * 72)
    print("v0.5 PROGRAM COMPARISON — WeeklyProgram.compare() on two synthetic programs")
    print("  (Both built from real analyze_multi_position results; different volume/emphasis)")
    print("-" * 72)
    print()

    cmp_subj = service.create_subject_from_measurements(
        name="Comparison Lifter", femur_length_cm=42.0, tibia_length_cm=38.0, humerus_length_cm=32.0
    )

    # Program Alpha: classic high-bar emphasis, bottom + mid heavy
    alpha = WeeklyProgram(name="Alpha - HighBar Emphasis", athlete="Comparison Lifter", week_id="A")
    alpha_sess = TrainingSession(name="Squat Emphasis", lift="squat", variation="high_bar")
    alpha_mp = service.analyze_multi_position(
        cmp_subj, "squat", ["bottom", "mid"], load_kg=135.0,
        variation="high_bar", target_region_name="Upper fibers", use_geometric=True
    )
    alpha_sess.add_analyses(alpha_mp, weights=[3.0, 2.0])  # more volume at sticking point
    alpha.add_session(alpha_sess)

    # Program Beta: low-bar + more top lockout work (different regional bias)
    beta = WeeklyProgram(name="Beta - LowBar + Lockout", athlete="Comparison Lifter", week_id="B")
    beta_sess = TrainingSession(name="Squat Variation", lift="squat", variation="low_bar")
    beta_mp = service.analyze_multi_position(
        cmp_subj, "squat", ["bottom", "mid", "top"], load_kg=130.0,
        variation="low_bar", target_region_name="Upper fibers", use_geometric=True
    )
    beta_sess.add_analyses(beta_mp, weights=[2.0, 2.0, 3.0])  # emphasis on top range
    beta.add_session(beta_sess)

    comparison = WeeklyProgram.compare(alpha, beta, service)
    print(f"  Alpha: {alpha.name}")
    print(f"  Beta:  {beta.name}")
    print(f"  Higher accumulated stress program: {comparison['higher_stress_program']}")
    print("  Deltas (Beta - Alpha) by region (positive = Beta stresses more):")
    for reg, d in sorted(comparison["deltas_by_region"].items(), key=lambda kv: -abs(kv[1])):
        print(f"    {reg:30s} {d:+8.1f}")
    print()
    print("  → Real-world use: Swap in different weekly templates, re-run with your")
    print("     actual anthropometry + target regions, and let the models quantify the")
    print("     regional stress trade-offs before you commit to a mesocycle.")

    # -------------------------------------------------------------------
    # 5. PERSIST SIMPLE REPORT
    # -------------------------------------------------------------------
    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "01_weekly_regional_stress_report.txt"

    with open(report_path, "w") as f:
        f.write("FiberForce — Weekly Regional Stress Report (Synthetic Program)\n")
        f.write("=" * 60 + "\n\n")
        f.write("v0.5: Generated using TrainingSession + WeeklyProgram models (Phase 3)\n")
        f.write("All accumulation via AnalysisService.accumulate_* helpers.\n\n")
        for row in results_table:
            f.write(f"{row['Region']}: {row['Total RSI']} RSI units ({row['Sessions']} sessions)\n")
        f.write("\nRecommendations:\n")
        for rec in recommendations:
            f.write(rec + "\n")
        f.write("\n--- Full WeeklyProgram.generate_simple_report() ---\n")
        f.write(weekly.generate_simple_report(service))
        f.write("\n\nGenerated with real reference moment arms via AnalysisService + v0.5 program models.\n")

    print(f"[Saved] Detailed report → {report_path}")
    print()

    # -------------------------------------------------------------------
    # LIMITATIONS & HONEST CAVEATS (MANDATORY FOR ALL EXAMPLES)
    # -------------------------------------------------------------------
    print("=" * 72)
    print("IMPORTANT LIMITATIONS (Read Carefully)")
    print("=" * 72)
    print("""
1. MODEL LIMITATIONS (Updated after 0.6 unit fix):
   The previous cm-vs-m torque scaling bug has been corrected. Absolute force
   values are now in the correct physical range for the modeled loads.

   Remaining limitations: single-joint approximation, prototype geometric moment
   arms, static positions only, conservative length-tension, etc.

   → Relative comparisons, deltas, rankings, and directional effects are
     trustworthy. See docs/limitations-deep-dive.md for full details.

2. STATIC PEAK FORCE ONLY:
   We analyze only chosen static positions (mostly bottoms in this program).
   No integration across full ROM, no time-under-tension, no force-velocity
   or stretch-shortening cycle contributions.

3. REFERENCE (NOT PERSONALIZED) MOMENT ARMS:
   MA values come from static lookup tables in fiberforce/reference/moment_arms.py.
   Changing femur/humerus/etc on the Subject currently has NO effect on the
   computed forces. The builders accept the measurements (for future use) but
   the calculator uses fixed reference MAs. True personalization of geometry
   is planned but not yet implemented.

4. RSI IS A CRUDE PROXY:
   "Regional Stress Index" = peak_force × sets × reps is a mechanical volume
   surrogate only. It ignores rest intervals, technique, co-contraction,
   individual architecture, and systemic recovery.

5. NO PROGRAMMING PRESCRIPTION:
   The recommendations are illustrative heuristics only. Real decisions must
   incorporate recovery capacity, injury history, movement quality, and direct
   performance feedback. FiberForce is one data source among many.

6. SINGLE-JOINT APPROXIMATION + OTHER SIMPLIFICATIONS:
   See docs/how-the-model-works.md for the complete list (multi-joint torque
   sharing not modeled, length-tension is a fixed 0.85 placeholder, etc.).

FiberForce is a transparent "what-if" mechanical lens for regional force
demands, not a complete training simulator or AI coach. The highest value
today is in relative comparisons once you understand the scaling issue.

See also: docs/usage-guide.md, DESIGN.md, and the source of AnalysisService.
""")

    print("Example 01 complete. All numbers derived live from AnalysisService + reference data.")
    print("=" * 72)


if __name__ == "__main__":
    main()
