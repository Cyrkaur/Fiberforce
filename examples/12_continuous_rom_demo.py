#!/usr/bin/env python
"""
Example 12: Continuous ROM / Dynamic Analysis Demo (post-v1 dynrom)

Demonstrates the new continuous ROM support (MVP for full dynamics/ROM curves).
Uses high-level recipes.analyze_continuous to analyze over a joint angle range
(knee for squat/RDL, shoulder for bench/incline), producing a MultiPositionResult
with full .interpret(), ft-lb torques, aggregates.

This is the first step beyond discrete static + multi-position: interpolated
snapshots over ROM, still peak-force per position but now continuous coverage.

Run:
    PYTHONPATH=src python examples/12_continuous_rom_demo.py

Outputs report to examples/outputs/12_continuous_rom_report.txt
"""

from datetime import datetime
from pathlib import Path

from fiberforce.recipes import create_athlete, analyze_continuous

def main():
    print("FiberForce Example 12 — Continuous ROM (dynrom MVP)")
    print("=" * 60)

    # Realistic athlete (17" femur as in coaching examples)
    ath = create_athlete(
        name="Continuous Demo Athlete",
        units="imperial",
        femur_in=17.0,
        tibia_in=15.0,
        humerus_in=13.4,
        biacromial_in=15.7,
        torso_depth_in=9.4,
    )
    print(f"Athlete: {ath.name} (imperial measurements, geometric ready)")

    # 1. Squat continuous over knee ROM (bottom ~35° to near lockout ~170°)
    print("\n--- Squat continuous ROM (low bar, 5 steps, 315 lb) ---")
    mpr_squat = analyze_continuous(
        "squat",
        steps=5,
        load_lbs=315,
        athlete=ath,
        variation="low_bar",
        units="imperial",
        # knee range explicit (can omit for defaults)
        knee_start=35.0,
        knee_end=170.0,
    )
    print(mpr_squat.interpret())
    print("Per-step ft-lb (first result):", [
        round(a.results[0].peak_torque_ftlb, 1) for a in mpr_squat.analyses
    ])

    # 2. Bench continuous (shoulder angle range)
    print("\n--- Bench continuous ROM (flat, 4 steps, 225 lb) ---")
    mpr_bench = analyze_continuous(
        "bench",
        steps=4,
        load_lbs=225,
        athlete=ath,
        variation="flat",
        units="imperial",
    )
    print(mpr_bench.interpret()[:400] + "...")
    print("Per-step ft-lb:", [
        round(a.results[0].peak_torque_ftlb, 1) for a in mpr_bench.analyses
    ])

    # Summary
    print("\n" + "=" * 60)
    print("Key points (dynrom MVP):")
    print("- analyze_continuous returns MultiPositionResult (full interpret, ft-lb, etc.)")
    print("- Parameterized by primary joint (knee/shoulder) over range")
    print("- Uses table interp + geometric with explicit angles where available")
    print("- Still discrete snapshots (peak per position); true velocity/inertia next")
    print("- Works with imperial, geometric, programs, persistence, etc.")
    print("- See limitations-deep-dive.md for honest scope.")

    # Write report
    out_dir = Path("examples/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "12_continuous_rom_report.txt"
    with open(report_path, "w") as f:
        f.write(f"FiberForce Example 12 Report — {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        f.write("SQUAT CONTINUOUS:\n")
        f.write(mpr_squat.interpret() + "\n\n")
        f.write("BENCH CONTINUOUS (truncated):\n")
        f.write(mpr_bench.interpret()[:600] + "...\n\n")
        f.write("See source for more. This demonstrates post-v1 continuous ROM MVP.\n")

    print(f"\nReport written to {report_path}")
    print("Example 12 complete.")

if __name__ == "__main__":
    main()