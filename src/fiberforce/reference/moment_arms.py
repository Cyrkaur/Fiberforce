"""
Reference moment arm data for common primary lifts (static positions).

These values are synthesized approximations based on typical published ranges
from biomechanical literature. They are **not** precise individual data.

Use only as defaults. Real use should rely on subject-specific measurements.

CONFIDENCE METADATA (added v0.2+ polish):
    Every major table now has a parallel *CONFIDENCE dict (or handled via
    ReferenceData for geometric). Levels:
        "high"     — Strong direct or consensus literature support for average adults
        "medium"   — Typical synthesized value drawn from published ranges
        "low"      — Rough approximation / sparse data for that exact position/variation
        "estimated" — Computed on-the-fly via the geometric prototype (anthropometry-driven)

    Query via ReferenceData.get_confidence_for_moment_arm(...) for a unified API
    that also covers geometric estimates.

All static tables remain backward-compatible (float values unchanged).
"""

from typing import Dict

# Shoulder horizontal adduction moment arms (cm) for sternal pectoralis major fibers
# at common static bench press positions.
BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "flat_bench_bottom": {"shoulder": 5.7},
    "flat_bench_mid": {"shoulder": 4.9},
    "flat_bench_near_lockout": {"shoulder": 3.3},
    "incline_30_bottom": {"shoulder": 4.9},
    "incline_30_mid": {"shoulder": 4.3},
    "decline_15_bottom": {"shoulder": 6.1},
}

# Approximate load moment arms (cm) from shoulder joint to bar path
BENCH_PRESS_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "flat_bench_bottom": 32.0,
    "flat_bench_mid": 27.0,
    "incline_30_bottom": 30.0,
    "decline_15_bottom": 29.0,
}

# Approximate MA for anterior deltoid shoulder horizontal adduction in bench (synthesized from literature ~3-4.5cm)
BENCH_PRESS_ANTERIOR_DELT_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "flat_bench_bottom": {"shoulder": 3.8},
    "flat_bench_mid": {"shoulder": 3.2},
    "flat_bench_near_lockout": {"shoulder": 2.5},
    "close_grip_bottom": {"shoulder": 3.6},
    "wide_grip_bottom": {"shoulder": 4.0},
}

# Triceps long head elbow extension MA for bench ( ~2.5cm typical)
BENCH_PRESS_TRICEPS_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "flat_bench_bottom": {"elbow": 2.6},
    "flat_bench_mid": {"elbow": 2.4},
    "flat_bench_near_lockout": {"elbow": 2.8},
    "close_grip_bottom": {"elbow": 2.7},
    "wide_grip_bottom": {"elbow": 2.5},
}

# Elbow load moment arms (cm) for bench press (from studies ~7cm)
BENCH_PRESS_ELBOW_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "flat_bench_bottom": 7.2,
    "flat_bench_mid": 6.5,
    "flat_bench_near_lockout": 5.0,
    "close_grip_bottom": 6.8,
    "wide_grip_bottom": 7.5,
}

# Per-joint load moment arms (cm) for squat (hip vs knee). Hip values from existing SQUAT_LOAD;
# knee smaller (typical ~5-8cm from lit on patellar tendon / quad MA inverse). Low-bar often
# slightly longer effective hip MA due to bar position + torso lean.
SQUAT_HIP_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "high_bar_bottom": 18.0,
    "low_bar_bottom": 22.0,
    "high_bar_parallel": 19.0,
    "low_bar_parallel": 23.0,
    "high_bar_mid": 15.0,
    "low_bar_mid": 18.0,
}
SQUAT_KNEE_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "high_bar_bottom": 6.8,
    "low_bar_bottom": 7.2,
    "high_bar_parallel": 7.0,
    "low_bar_parallel": 7.5,
}

# Deadlift per-joint load (hip dominant; lumbar shorter effective for erectors).
# Sumo shorter overall (more upright).
DEADLIFT_HIP_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "conventional_bottom": 26.5,
    "sumo_bottom": 20.5,
    "conventional_mid": 18.0,
    "sumo_mid": 14.0,
}
DEADLIFT_LUMBAR_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "conventional_bottom": 21.0,
    "sumo_bottom": 16.0,
    "conventional_mid": 14.0,
    "sumo_mid": 11.0,
}

# OHP per-joint (shoulder for delts; elbow for triceps). Load MA shorter overhead.
OHP_SHOULDER_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "standing_bottom": 14.0,
    "seated_bottom": 13.5,
    "strict_standing_bottom": 14.2,
    "standing_mid": 10.0,
    "standing_lockout": 6.5,
    "seated_lockout": 6.0,
}
OHP_ELBOW_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "standing_bottom": 5.8,
    "seated_bottom": 5.5,
    "strict_standing_bottom": 6.0,
    "standing_mid": 4.5,
    "standing_lockout": 3.8,
}

# RDL / romanian similar to DL but hip hinge, less knee, more ham emphasis.
RDL_HIP_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "rdl_mid": 19.0,
    "rdl_top": 12.0,
    "stiff_leg_bottom": 21.0,
}
RDL_LUMBAR_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "rdl_mid": 15.0,
    "rdl_top": 10.0,
}

# Incline (reuse bench style + slight clavicular shift; shoulder primary, elbow co)
INCLINE_SHOULDER_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "incline_30_bottom": 29.0,
    "incline_45_bottom": 28.0,
    "incline_30_mid": 25.0,
}
INCLINE_ELBOW_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "incline_30_bottom": 6.5,
    "incline_45_bottom": 6.3,
}

# Example values for other lifts (very rough starting points)
SQUAT_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "high_bar_bottom": 18.0,
    "low_bar_bottom": 22.0,
    "high_bar_parallel": 19.0,
    "low_bar_parallel": 23.0,
}

# -------------------------------------------------------------------
# Overhead Press reference data — expanded for full parity (v0.2 polish)
# Positions cover standing vs seated, and key points in the ROM:
# bottom (bar at upper chest/clavicle), mid (~90° shoulder), lockout (full overhead).
# Different emphases (anterior delt primary, lateral delt abduction bias,
# rear delt for stability/anti-shear, triceps long head + lateral for lockout).
# Load MAs reflect bar path distance from shoulder (shorter at top).
# All values are synthesized approximations.
# -------------------------------------------------------------------

OVERHEAD_PRESS_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "standing_bottom": 15.0,
    "standing_mid": 12.5,
    "standing_lockout": 8.0,
    "seated_bottom": 14.0,
    "seated_mid": 11.5,
    "seated_lockout": 7.5,
    "strict_standing_bottom": 15.5,  # slightly longer due to stricter torso
}

# Anterior deltoid (primary shoulder flexor) — strongest contributor in OHP
OHP_ANTERIOR_DELT_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "standing_bottom": {"shoulder": 3.8},
    "standing_mid": {"shoulder": 4.2},
    "standing_lockout": {"shoulder": 2.9},
    "seated_bottom": {"shoulder": 3.6},
    "seated_mid": {"shoulder": 4.0},
    "seated_lockout": {"shoulder": 2.7},
    "strict_standing_bottom": {"shoulder": 3.9},
}

# Lateral deltoid — abduction emphasis (more prominent in wide-grip or DB variations)
OHP_LATERAL_DELT_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "standing_bottom": {"shoulder": 4.1},
    "standing_mid": {"shoulder": 4.5},
    "standing_lockout": {"shoulder": 3.2},
    "seated_bottom": {"shoulder": 3.9},
    "seated_mid": {"shoulder": 4.3},
    "seated_lockout": {"shoulder": 3.0},
}

# Posterior (rear) deltoid — stabilizer / anti-shear, smaller primary MA in press
OHP_POSTERIOR_DELT_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "standing_bottom": {"shoulder": 2.4},
    "standing_mid": {"shoulder": 2.6},
    "standing_lockout": {"shoulder": 2.1},
    "seated_bottom": {"shoulder": 2.3},
    "seated_mid": {"shoulder": 2.5},
    "seated_lockout": {"shoulder": 2.0},
}

# Triceps Brachii (long head) — elbow extension + shoulder stabilizer
OHP_TRICEPS_LONG_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "standing_bottom": {"elbow": 1.8},
    "standing_mid": {"elbow": 2.1},
    "standing_lockout": {"elbow": 2.4},
    "seated_bottom": {"elbow": 1.7},
    "seated_mid": {"elbow": 2.0},
    "seated_lockout": {"elbow": 2.3},
}

# Triceps lateral head (pure elbow extensor, prominent near lockout)
OHP_TRICEPS_LATERAL_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "standing_bottom": {"elbow": 1.5},
    "standing_mid": {"elbow": 1.9},
    "standing_lockout": {"elbow": 2.2},
    "seated_bottom": {"elbow": 1.4},
    "seated_mid": {"elbow": 1.8},
    "seated_lockout": {"elbow": 2.1},
}

# Upper trapezius / scapular elevators (for overhead stability, smaller direct contribution)
OHP_TRAP_UPPER_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "standing_bottom": {"scapula": 1.2},
    "standing_mid": {"scapula": 1.4},
    "standing_lockout": {"scapula": 1.1},
    "seated_bottom": {"scapula": 1.1},
    "seated_mid": {"scapula": 1.3},
}

# -------------------------------------------------------------------
# Squat reference data (high-bar and low-bar at bottom position)
# These are synthesized approximations. Real values vary with depth,
# stance width, bar position, and individual anthropometry.
# -------------------------------------------------------------------

SQUAT_GLUTE_MAX_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "high_bar_bottom": {"hip": 6.2},
    "low_bar_bottom": {"hip": 7.1},
    "high_bar_parallel": {"hip": 5.8},
    "low_bar_parallel": {"hip": 6.8},
}

SQUAT_QUAD_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "high_bar_bottom": {"knee": 4.8},
    "low_bar_bottom": {"knee": 4.3},
    "high_bar_parallel": {"knee": 5.1},
    "low_bar_parallel": {"knee": 4.5},
}

SQUAT_HAMSTRING_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "high_bar_bottom": {"hip": 4.9},
    "low_bar_bottom": {"hip": 5.4},
}

SQUAT_EREctor_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "high_bar_bottom": {"lumbar": 5.5},
    "low_bar_bottom": {"lumbar": 6.0},
}

# -------------------------------------------------------------------
# Deadlift reference data — Conventional vs Sumo at bottom position (floor pull)
# Key addition for v0.2 scope. Bottom position is the most mechanically demanding
# for posterior chain (glutes, hamstrings, erectors).
#
# Values synthesized from typical published biomechanical ranges (hip extension
# moment arms, lumbar erector MA, and bar-to-hip horizontal distances).
# Conventional: greater forward lean → longer load MA at hip.
# Sumo: wider stance + more upright torso possible → shorter effective load MA.
# -------------------------------------------------------------------

DEADLIFT_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "conventional_bottom": 26.5,
    "sumo_bottom": 20.5,
}

DEADLIFT_GLUTE_MAX_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "conventional_bottom": {"hip": 7.9},
    "sumo_bottom": {"hip": 7.3},
}

DEADLIFT_HAMSTRING_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "conventional_bottom": {"hip": 7.1},  # Biceps femoris long head, semitendinosus, semimembranosus
    "sumo_bottom": {"hip": 6.6},
}

DEADLIFT_EREctor_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "conventional_bottom": {"lumbar": 5.9},
    "sumo_bottom": {"lumbar": 5.4},
}

# -------------------------------------------------------------------
# Additional / extended reference data (added for sensitivity + CLI use)
# These .update() calls must come AFTER all base dict definitions above.
# -------------------------------------------------------------------

# Additional squat depth / stance variations (more granular)
SQUAT_GLUTE_MAX_MOMENT_ARMS.update({
    "high_bar_parallel": {"hip": 5.8},
    "low_bar_parallel": {"hip": 6.8},
})

SQUAT_QUAD_MOMENT_ARMS.update({
    "high_bar_parallel": {"knee": 5.1},
    "low_bar_parallel": {"knee": 4.5},
})

# Extra bench positions for sensitivity / grip work (appended to original dict)
BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS["wide_grip_bottom"] = {"shoulder": 6.4}
BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS["close_grip_bottom"] = {"shoulder": 4.2}
BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS["flat_bench_top"] = {"shoulder": 2.8}

BENCH_PRESS_LOAD_MOMENT_ARMS["wide_grip_bottom"] = 34.0
BENCH_PRESS_LOAD_MOMENT_ARMS["close_grip_bottom"] = 28.0
BENCH_PRESS_LOAD_MOMENT_ARMS["flat_bench_top"] = 22.0

# Deadlift extra positions / sensitivity keys (future expansion)
DEADLIFT_LOAD_MOMENT_ARMS["conventional_mid"] = 18.0
DEADLIFT_LOAD_MOMENT_ARMS["sumo_mid"] = 14.0

# OHP extras for sensitivity / more granular work (appended for parity)
OVERHEAD_PRESS_LOAD_MOMENT_ARMS.update({
    "standing_top": 6.5,
    "seated_top": 6.0,
})

OHP_ANTERIOR_DELT_MOMENT_ARMS.update({
    "standing_top": {"shoulder": 2.5},
    "seated_top": {"shoulder": 2.4},
})

OHP_TRICEPS_LONG_MOMENT_ARMS.update({
    "standing_top": {"elbow": 2.5},
    "seated_top": {"elbow": 2.4},
})

OHP_LATERAL_DELT_MOMENT_ARMS.update({
    "standing_top": {"shoulder": 2.8},
    "seated_top": {"shoulder": 2.6},
})


# =============================================================================
# CONFIDENCE METADATA FOR ALL MAJOR TABLES
# (high/medium/low/estimated) — added for deep ReferenceData polish
# =============================================================================

# Muscle moment arm confidence (position_key -> level)
# Bench (sternal pecs)
BENCH_PRESS_STERNAL_PEC_MA_CONFIDENCE: Dict[str, str] = {
    "flat_bench_bottom": "medium",
    "flat_bench_mid": "medium",
    "flat_bench_near_lockout": "medium",
    "incline_30_bottom": "medium",
    "incline_30_mid": "low",
    "decline_15_bottom": "medium",
    "wide_grip_bottom": "medium",
    "close_grip_bottom": "medium",
    "flat_bench_top": "low",
}

# Bench load arms
BENCH_PRESS_LOAD_MA_CONFIDENCE: Dict[str, str] = {
    "flat_bench_bottom": "medium",
    "flat_bench_mid": "medium",
    "incline_30_bottom": "low",
    "decline_15_bottom": "low",
    "wide_grip_bottom": "medium",
    "close_grip_bottom": "medium",
    "flat_bench_top": "low",
}

# Squat muscle MAs
SQUAT_GLUTE_MAX_MA_CONFIDENCE: Dict[str, str] = {
    "high_bar_bottom": "medium",
    "low_bar_bottom": "medium",
    "high_bar_parallel": "medium",
    "low_bar_parallel": "medium",
}

SQUAT_QUAD_MA_CONFIDENCE: Dict[str, str] = {
    "high_bar_bottom": "medium",
    "low_bar_bottom": "medium",
    "high_bar_parallel": "medium",
    "low_bar_parallel": "medium",
}

SQUAT_HAMSTRING_MA_CONFIDENCE: Dict[str, str] = {
    "high_bar_bottom": "low",
    "low_bar_bottom": "low",
}

SQUAT_EREctor_MA_CONFIDENCE: Dict[str, str] = {
    "high_bar_bottom": "low",
    "low_bar_bottom": "low",
}

SQUAT_LOAD_MA_CONFIDENCE: Dict[str, str] = {
    "high_bar_bottom": "medium",
    "low_bar_bottom": "medium",
    "high_bar_parallel": "low",
    "low_bar_parallel": "low",
}

# Deadlift (first-class v0.2)
DEADLIFT_LOAD_MA_CONFIDENCE: Dict[str, str] = {
    "conventional_bottom": "medium",
    "sumo_bottom": "medium",
    "conventional_mid": "low",
    "sumo_mid": "low",
}

DEADLIFT_GLUTE_MAX_MA_CONFIDENCE: Dict[str, str] = {
    "conventional_bottom": "medium",
    "sumo_bottom": "medium",
}

DEADLIFT_HAMSTRING_MA_CONFIDENCE: Dict[str, str] = {
    "conventional_bottom": "medium",
    "sumo_bottom": "medium",
}

DEADLIFT_EREctor_MA_CONFIDENCE: Dict[str, str] = {
    "conventional_bottom": "medium",
    "sumo_bottom": "medium",
}

# OHP full parity
OVERHEAD_PRESS_LOAD_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "medium",
    "standing_mid": "medium",
    "standing_lockout": "medium",
    "seated_bottom": "medium",
    "seated_mid": "medium",
    "seated_lockout": "medium",
    "strict_standing_bottom": "low",
    "standing_top": "low",
    "seated_top": "low",
}

OHP_ANTERIOR_DELT_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "medium",
    "standing_mid": "medium",
    "standing_lockout": "medium",
    "seated_bottom": "medium",
    "seated_mid": "medium",
    "seated_lockout": "medium",
    "strict_standing_bottom": "low",
    "standing_top": "low",
    "seated_top": "low",
}

OHP_LATERAL_DELT_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "medium",
    "standing_mid": "medium",
    "standing_lockout": "low",
    "seated_bottom": "medium",
    "seated_mid": "medium",
    "seated_lockout": "low",
    "standing_top": "low",
    "seated_top": "low",
}

OHP_POSTERIOR_DELT_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "low",
    "standing_mid": "low",
    "standing_lockout": "low",
    "seated_bottom": "low",
    "seated_mid": "low",
    "seated_lockout": "low",
    "standing_top": "low",
    "seated_top": "low",
}

OHP_TRICEPS_LONG_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "medium",
    "standing_mid": "medium",
    "standing_lockout": "medium",
    "seated_bottom": "medium",
    "seated_mid": "medium",
    "seated_lockout": "medium",
    "standing_top": "low",
    "seated_top": "low",
}

OHP_TRICEPS_LATERAL_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "low",
    "standing_mid": "low",
    "standing_lockout": "low",
    "seated_bottom": "low",
    "seated_mid": "low",
    "seated_lockout": "low",
    "standing_top": "low",
    "seated_top": "low",
}

OHP_TRAP_UPPER_MA_CONFIDENCE: Dict[str, str] = {
    "standing_bottom": "low",
    "standing_mid": "low",
    "standing_lockout": "low",
    "seated_bottom": "low",
    "seated_mid": "low",
    "seated_lockout": "low",
    "standing_top": "low",
    "seated_top": "low",
}

# Geometric estimates always receive "estimated" (or "model-based (geometric)")
# confidence. Handled dynamically in ReferenceData / geometric.py rather than
# a static table here. See estimate_* functions and
# ReferenceData.get_confidence_for_moment_arm for unified access.


__all__ = [
    # Core tables (unchanged for backward compat)
    "BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS",
    "BENCH_PRESS_LOAD_MOMENT_ARMS",
    "SQUAT_LOAD_MOMENT_ARMS",
    "SQUAT_GLUTE_MAX_MOMENT_ARMS",
    "SQUAT_QUAD_MOMENT_ARMS",
    "SQUAT_HAMSTRING_MOMENT_ARMS",
    "SQUAT_EREctor_MOMENT_ARMS",
    "OVERHEAD_PRESS_LOAD_MOMENT_ARMS",
    "OHP_ANTERIOR_DELT_MOMENT_ARMS",
    "OHP_TRICEPS_LONG_MOMENT_ARMS",
    "OHP_LATERAL_DELT_MOMENT_ARMS",
    "OHP_POSTERIOR_DELT_MOMENT_ARMS",
    "OHP_TRICEPS_LATERAL_MOMENT_ARMS",
    "OHP_TRAP_UPPER_MOMENT_ARMS",
    "DEADLIFT_LOAD_MOMENT_ARMS",
    "DEADLIFT_GLUTE_MAX_MOMENT_ARMS",
    "DEADLIFT_HAMSTRING_MOMENT_ARMS",
    "DEADLIFT_EREctor_MOMENT_ARMS",
    # NEW: Confidence metadata tables (parallel structure)
    "BENCH_PRESS_STERNAL_PEC_MA_CONFIDENCE",
    "BENCH_PRESS_LOAD_MA_CONFIDENCE",
    "SQUAT_GLUTE_MAX_MA_CONFIDENCE",
    "SQUAT_QUAD_MA_CONFIDENCE",
    "SQUAT_HAMSTRING_MA_CONFIDENCE",
    "SQUAT_EREctor_MA_CONFIDENCE",
    "SQUAT_LOAD_MA_CONFIDENCE",
    "DEADLIFT_LOAD_MA_CONFIDENCE",
    "DEADLIFT_GLUTE_MAX_MA_CONFIDENCE",
    "DEADLIFT_HAMSTRING_MA_CONFIDENCE",
    "DEADLIFT_EREctor_MA_CONFIDENCE",
    "OVERHEAD_PRESS_LOAD_MA_CONFIDENCE",
    "OHP_ANTERIOR_DELT_MA_CONFIDENCE",
    "OHP_LATERAL_DELT_MA_CONFIDENCE",
    "OHP_POSTERIOR_DELT_MA_CONFIDENCE",
    "OHP_TRICEPS_LONG_MA_CONFIDENCE",
    "OHP_TRICEPS_LATERAL_MA_CONFIDENCE",
    "OHP_TRAP_UPPER_MA_CONFIDENCE",
    # Per-joint load MAs for multi-prime-mover % dominance (added for full 8-lift expansion)
    "SQUAT_HIP_LOAD_MOMENT_ARMS",
    "SQUAT_KNEE_LOAD_MOMENT_ARMS",
    "DEADLIFT_HIP_LOAD_MOMENT_ARMS",
    "DEADLIFT_LUMBAR_LOAD_MOMENT_ARMS",
    "OHP_SHOULDER_LOAD_MOMENT_ARMS",
    "OHP_ELBOW_LOAD_MOMENT_ARMS",
    "RDL_HIP_LOAD_MOMENT_ARMS",
    "RDL_LUMBAR_LOAD_MOMENT_ARMS",
    "INCLINE_SHOULDER_LOAD_MOMENT_ARMS",
    "INCLINE_ELBOW_LOAD_MOMENT_ARMS",
]

# =============================================================================
# NEW EXERCISES (post-v1 scope expansion)
# Incline Bench Press + Romanian Deadlift (RDL)
# =============================================================================

# Incline Bench (30-45°) — greater upper pec / clavicular demand, slightly different
# shoulder MA vs flat bench. Positions use "incline_30_" or "incline_45_" prefix.
INCLINE_BENCH_STERNAL_PEC_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "incline_30_bottom": {"shoulder": 4.8},
    "incline_30_mid": {"shoulder": 4.2},
    "incline_30_top": {"shoulder": 2.9},
    "incline_45_bottom": {"shoulder": 4.3},
    "incline_45_mid": {"shoulder": 3.8},
    "incline_45_top": {"shoulder": 2.6},
}

INCLINE_BENCH_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "incline_30_bottom": 29.5,
    "incline_30_mid": 25.0,
    "incline_30_top": 19.0,
    "incline_45_bottom": 28.0,
    "incline_45_mid": 24.0,
    "incline_45_top": 18.5,
}

# Clavicular (upper) pec emphasis is stronger on incline — add dedicated table
INCLINE_BENCH_CLAVICULAR_PEC_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "incline_30_bottom": {"shoulder": 3.9},
    "incline_30_mid": {"shoulder": 4.5},
    "incline_45_bottom": {"shoulder": 4.2},
    "incline_45_mid": {"shoulder": 4.8},
}

# Romanian Deadlift (RDL) — hip dominant hinge, straighter knees, high hamstring
# demand throughout. Positions: "rdl_bottom" (near floor with slight knee bend),
# "rdl_mid" (parallel-ish shin), "rdl_top" (near lockout but controlled).
RDL_LOAD_MOMENT_ARMS: Dict[str, float] = {
    "rdl_bottom": 21.0,
    "rdl_mid": 17.5,
    "rdl_top": 11.0,
}

RDL_GLUTE_MAX_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "rdl_bottom": {"hip": 6.8},
    "rdl_mid": {"hip": 5.9},
    "rdl_top": {"hip": 3.8},
}

RDL_HAMSTRING_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "rdl_bottom": {"hip": 4.8, "knee": 2.1},
    "rdl_mid": {"hip": 5.5, "knee": 1.6},
    "rdl_top": {"hip": 3.2, "knee": 1.1},
}

RDL_EREctor_MOMENT_ARMS: Dict[str, Dict[str, float]] = {
    "rdl_bottom": {"hip": 3.5},
    "rdl_mid": {"hip": 2.9},
    "rdl_top": {"hip": 1.8},
}

# Confidence for new tables (prototype-grade for the new exercises)
INCLINE_BENCH_STERNAL_PEC_MA_CONFIDENCE: Dict[str, str] = {
    "incline_30_bottom": "medium",
    "incline_30_mid": "medium",
    "incline_30_top": "low",
    "incline_45_bottom": "medium",
    "incline_45_mid": "low",
    "incline_45_top": "low",
}

INCLINE_BENCH_LOAD_MA_CONFIDENCE: Dict[str, str] = {
    "incline_30_bottom": "medium",
    "incline_30_mid": "medium",
    "incline_30_top": "low",
    "incline_45_bottom": "low",
    "incline_45_mid": "low",
    "incline_45_top": "low",
}

INCLINE_BENCH_CLAVICULAR_MA_CONFIDENCE: Dict[str, str] = {
    "incline_30_bottom": "low",
    "incline_30_mid": "low",
    "incline_45_bottom": "low",
    "incline_45_mid": "low",
}

RDL_LOAD_MA_CONFIDENCE: Dict[str, str] = {
    "rdl_bottom": "medium",
    "rdl_mid": "medium",
    "rdl_top": "low",
}

RDL_GLUTE_MAX_MA_CONFIDENCE: Dict[str, str] = {
    "rdl_bottom": "medium",
    "rdl_mid": "medium",
    "rdl_top": "low",
}

RDL_HAMSTRING_MA_CONFIDENCE: Dict[str, str] = {
    "rdl_bottom": "medium",
    "rdl_mid": "medium",
    "rdl_top": "low",
}

RDL_EREctor_MA_CONFIDENCE: Dict[str, str] = {
    "rdl_bottom": "low",
    "rdl_mid": "low",
    "rdl_top": "low",
}

