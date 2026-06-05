"""Reference biomechanical data for FiberForce.

This package exposes:
- ReferenceData (the recommended central query interface with rich API,
  full confidence metadata, and geometric-preferred estimation)
- All raw static moment arm tables (backward-compatible)
- Parallel confidence metadata tables for every major lift/region
- The geometric moment arm prototype (estimate_* functions)

DEEP POLISH (current):
    * Confidence (high/medium/low/estimated) on bench, squat, deadlift, OHP tables
    * Rich query methods on ReferenceData: get_confidence_for_moment_arm,
      get_moment_arm_with_confidence, list_available_regions_for_lift, etc.
    * Geometric estimators are the preferred path inside ReferenceData.estimate_moment_arm
      and the main high-level builders when anthropometry is supplied.
"""

from .data import ReferenceData, get_default_reference
from .moment_arms import (
    BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS,
    BENCH_PRESS_LOAD_MOMENT_ARMS,
    SQUAT_LOAD_MOMENT_ARMS,
    SQUAT_GLUTE_MAX_MOMENT_ARMS,
    SQUAT_QUAD_MOMENT_ARMS,
    SQUAT_HAMSTRING_MOMENT_ARMS,
    SQUAT_EREctor_MOMENT_ARMS,
    OVERHEAD_PRESS_LOAD_MOMENT_ARMS,
    OHP_ANTERIOR_DELT_MOMENT_ARMS,
    OHP_TRICEPS_LONG_MOMENT_ARMS,
    # Expanded OHP (full parity polish)
    OHP_LATERAL_DELT_MOMENT_ARMS,
    OHP_POSTERIOR_DELT_MOMENT_ARMS,
    OHP_TRICEPS_LATERAL_MOMENT_ARMS,
    OHP_TRAP_UPPER_MOMENT_ARMS,
    # Deadlift (v0.2)
    DEADLIFT_LOAD_MOMENT_ARMS,
    DEADLIFT_GLUTE_MAX_MOMENT_ARMS,
    DEADLIFT_HAMSTRING_MOMENT_ARMS,
    DEADLIFT_EREctor_MOMENT_ARMS,
    # NEW: Full confidence metadata (parallel tables)
    BENCH_PRESS_STERNAL_PEC_MA_CONFIDENCE,
    BENCH_PRESS_LOAD_MA_CONFIDENCE,
    SQUAT_GLUTE_MAX_MA_CONFIDENCE,
    SQUAT_QUAD_MA_CONFIDENCE,
    SQUAT_HAMSTRING_MA_CONFIDENCE,
    SQUAT_EREctor_MA_CONFIDENCE,
    SQUAT_LOAD_MA_CONFIDENCE,
    DEADLIFT_LOAD_MA_CONFIDENCE,
    DEADLIFT_GLUTE_MAX_MA_CONFIDENCE,
    DEADLIFT_HAMSTRING_MA_CONFIDENCE,
    DEADLIFT_EREctor_MA_CONFIDENCE,
    OVERHEAD_PRESS_LOAD_MA_CONFIDENCE,
    OHP_ANTERIOR_DELT_MA_CONFIDENCE,
    OHP_LATERAL_DELT_MA_CONFIDENCE,
    OHP_POSTERIOR_DELT_MA_CONFIDENCE,
    OHP_TRICEPS_LONG_MA_CONFIDENCE,
    OHP_TRICEPS_LATERAL_MA_CONFIDENCE,
    OHP_TRAP_UPPER_MA_CONFIDENCE,
)

# Geometric moment arm prototype (anthropometry-driven estimation)
from .geometric import (
    estimate_bench_sternal_ma,
    estimate_squat_glute_ma,
    estimate_squat_quad_ma,
    estimate_moment_arm,
)

# Re-export the helper function (defined here for now to avoid circular imports during early dev)
from fiberforce.models import MuscleAttachment, KNOWN_MUSCLE_REGIONS


def get_default_sternal_pec_attachment(position_key: str = "flat_bench_bottom") -> MuscleAttachment:
    sternal = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.region_name == "Sternal fibers"),
        None,
    )
    if sternal is None:
        raise ValueError("Sternal fibers region not found")

    moment_arms = BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS.get(position_key, {"shoulder": 5.0})

    return MuscleAttachment(
        muscle_region=sternal,
        joints_crossed=["shoulder"],
        moment_arms_at_position=moment_arms,
        notes=f"Default values for '{position_key}'.",
    )


def get_default_glute_max_attachment(position_key: str = "high_bar_bottom") -> MuscleAttachment:
    """Return a MuscleAttachment for glute max upper fibers.

    Supports squat keys (high_bar_bottom etc) and deadlift keys
    (conventional_bottom, sumo_bottom) for first-class deadlift support.
    """
    glute_upper = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.region_name == "Upper fibers" and "Gluteus Maximus" in r.muscle_name),
        None,
    )
    if glute_upper is None:
        # Fallback to any glute max region
        glute_upper = next(r for r in KNOWN_MUSCLE_REGIONS if "Gluteus Maximus" in r.muscle_name)

    # Prefer deadlift table when deadlift position key is requested
    if "conventional" in position_key or "sumo" in position_key or position_key.endswith("_bottom") and "bar" not in position_key:
        moment_arms = DEADLIFT_GLUTE_MAX_MOMENT_ARMS.get(position_key, {"hip": 7.5})
    else:
        moment_arms = SQUAT_GLUTE_MAX_MOMENT_ARMS.get(position_key, {"hip": 6.0})

    return MuscleAttachment(
        muscle_region=glute_upper,
        joints_crossed=["hip"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference glute max moment arm for {position_key}",
    )


def get_default_vastus_lateralis_attachment(position_key: str = "high_bar_bottom") -> MuscleAttachment:
    """Return attachment for vastus lateralis (knee extension) at squat bottom."""
    vl = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Vastus Lateralis"),
        None,
    )
    if vl is None:
        vl = next(r for r in KNOWN_MUSCLE_REGIONS if "Vastus" in r.muscle_name)

    moment_arms = SQUAT_QUAD_MOMENT_ARMS.get(position_key, {"knee": 4.5})
    return MuscleAttachment(
        muscle_region=vl,
        joints_crossed=["knee"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference VL moment arm for {position_key}",
    )


def get_default_hamstring_attachment(position_key: str = "conventional_bottom") -> MuscleAttachment:
    """Return attachment for a primary hamstring (hip extension focus) suitable for deadlift/squat.

    Targets Biceps Femoris (Long Head) by default (common for DL literature).
    Falls back gracefully.
    """
    hams = next(
        (r for r in KNOWN_MUSCLE_REGIONS if "Biceps Femoris" in r.muscle_name and "Long" in r.region_name),
        None,
    )
    if hams is None:
        hams = next(
            (r for r in KNOWN_MUSCLE_REGIONS if "Semitendinosus" in r.muscle_name or "Semimembranosus" in r.muscle_name),
            None,
        )
    if hams is None:
        # last resort any hamstring
        hams = next(r for r in KNOWN_MUSCLE_REGIONS if "Biceps Femoris" in r.muscle_name)

    # Support deadlift keys primarily, fall back to squat table
    if "conventional" in position_key or "sumo" in position_key:
        moment_arms = DEADLIFT_HAMSTRING_MOMENT_ARMS.get(position_key, {"hip": 6.8})
    else:
        moment_arms = SQUAT_HAMSTRING_MOMENT_ARMS.get(position_key, {"hip": 5.0})

    return MuscleAttachment(
        muscle_region=hams,
        joints_crossed=["hip"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference hamstring (hip extension) moment arm for {position_key}",
    )


def get_default_erector_attachment(position_key: str = "conventional_bottom") -> MuscleAttachment:
    """Return attachment for lumbar erector spinae (anti-flexion / spinal extension).

    Critical for deadlift bottom position analysis. Uses lumbar region.
    """
    erector = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Erector Spinae" and r.region_name == "Lumbar"),
        None,
    )
    if erector is None:
        erector = next(r for r in KNOWN_MUSCLE_REGIONS if "Erector Spinae" in r.muscle_name and "Lumbar" in r.region_name)
    if erector is None:
        erector = next(r for r in KNOWN_MUSCLE_REGIONS if "Erector Spinae" in r.muscle_name)

    moment_arms = DEADLIFT_EREctor_MOMENT_ARMS.get(position_key, {"lumbar": 5.5})
    # Also allow squat erector keys as fallback
    if position_key not in DEADLIFT_EREctor_MOMENT_ARMS:
        moment_arms = SQUAT_EREctor_MOMENT_ARMS.get(position_key, {"lumbar": 5.5})

    return MuscleAttachment(
        muscle_region=erector,
        joints_crossed=["lumbar"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference lumbar erector moment arm for {position_key} (deadlift/squat)",
    )


# -------------------------------------------------------------------
# OHP-specific attachment getters (new for full parity)
# These enable clean smart dispatch in build_ohp_analyzed_position and CLI.
# -------------------------------------------------------------------

def get_default_anterior_delt_attachment(position_key: str = "standing_bottom") -> MuscleAttachment:
    """Return MuscleAttachment for Deltoid — Anterior (primary OHP flexor)."""
    anterior = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and r.region_name == "Anterior"),
        None,
    )
    if anterior is None:
        anterior = next(r for r in KNOWN_MUSCLE_REGIONS if "Deltoid" in r.muscle_name and "Anterior" in r.region_name)

    moment_arms = OHP_ANTERIOR_DELT_MOMENT_ARMS.get(position_key, {"shoulder": 3.5})
    return MuscleAttachment(
        muscle_region=anterior,
        joints_crossed=["shoulder"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference anterior delt moment arm for OHP {position_key}",
    )


def get_default_lateral_delt_attachment(position_key: str = "standing_bottom") -> MuscleAttachment:
    """Return attachment for Deltoid — Lateral (abduction emphasis in OHP)."""
    lateral = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and r.region_name == "Lateral"),
        None,
    )
    if lateral is None:
        lateral = next(r for r in KNOWN_MUSCLE_REGIONS if "Deltoid" in r.muscle_name and "Lateral" in r.region_name)

    moment_arms = OHP_LATERAL_DELT_MOMENT_ARMS.get(position_key, {"shoulder": 4.0})
    return MuscleAttachment(
        muscle_region=lateral,
        joints_crossed=["shoulder"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference lateral delt moment arm for OHP {position_key}",
    )


def get_default_posterior_delt_attachment(position_key: str = "standing_bottom") -> MuscleAttachment:
    """Return attachment for Deltoid — Posterior (rear) as OHP stabilizer."""
    posterior = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and ("Posterior" in r.region_name or "rear" in r.region_name.lower())),
        None,
    )
    if posterior is None:
        posterior = next(r for r in KNOWN_MUSCLE_REGIONS if "Deltoid" in r.muscle_name and "Posterior" in r.region_name)

    moment_arms = OHP_POSTERIOR_DELT_MOMENT_ARMS.get(position_key, {"shoulder": 2.3})
    return MuscleAttachment(
        muscle_region=posterior,
        joints_crossed=["shoulder"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference posterior/rear delt moment arm (stabilizer) for OHP {position_key}",
    )


def get_default_triceps_long_attachment(position_key: str = "standing_bottom") -> MuscleAttachment:
    """Return attachment for Triceps Brachii — Long head (elbow extension in OHP).

    Long head has shoulder extension component too; primary lockout contributor.
    """
    triceps_long = next(
        (r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Triceps Brachii" and "Long" in r.region_name),
        None,
    )
    if triceps_long is None:
        triceps_long = next(r for r in KNOWN_MUSCLE_REGIONS if "Triceps" in r.muscle_name and "Long" in r.region_name)

    moment_arms = OHP_TRICEPS_LONG_MOMENT_ARMS.get(position_key, {"elbow": 2.0})
    return MuscleAttachment(
        muscle_region=triceps_long,
        joints_crossed=["elbow"],
        moment_arms_at_position=moment_arms,
        notes=f"Reference triceps long head moment arm for OHP {position_key}",
    )


__all__ = [
    "ReferenceData",
    "get_default_reference",
    # Value tables (backward-compatible)
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
    # Expanded OHP full-parity exports
    "OHP_LATERAL_DELT_MOMENT_ARMS",
    "OHP_POSTERIOR_DELT_MOMENT_ARMS",
    "OHP_TRICEPS_LATERAL_MOMENT_ARMS",
    "OHP_TRAP_UPPER_MOMENT_ARMS",
    # Deadlift v0.2 first-class support
    "DEADLIFT_LOAD_MOMENT_ARMS",
    "DEADLIFT_GLUTE_MAX_MOMENT_ARMS",
    "DEADLIFT_HAMSTRING_MOMENT_ARMS",
    "DEADLIFT_EREctor_MOMENT_ARMS",
    # NEW: Confidence metadata exports (all major tables)
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
    # Attachment factories
    "get_default_sternal_pec_attachment",
    "get_default_glute_max_attachment",
    "get_default_vastus_lateralis_attachment",
    "get_default_hamstring_attachment",
    "get_default_erector_attachment",
    # New OHP attachment getters (parity with deadlift/squat)
    "get_default_anterior_delt_attachment",
    "get_default_lateral_delt_attachment",
    "get_default_posterior_delt_attachment",
    "get_default_triceps_long_attachment",
    # Geometric moment arm prototype (new — anthropometry driven)
    "estimate_bench_sternal_ma",
    "estimate_squat_glute_ma",
    "estimate_squat_quad_ma",
    "estimate_moment_arm",
    # Core models re-export
    "MuscleAttachment",
    "KNOWN_MUSCLE_REGIONS",
]
