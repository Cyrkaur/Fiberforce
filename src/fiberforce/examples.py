"""
Example data builders and factories for FiberForce.

These are intended to make it easy to create realistic (or synthetic)
`Subject`, `Pose`, `AnalyzedPosition`, and `LiftConfiguration` objects
for development, testing, demonstration, and exploration.

This is especially useful while the project is in early stages and
real user measurement data may not yet be available.

GEOMETRIC INTEGRATION (v0.2.1 polish):
    The primary builders (build_bench_analyzed_position, build_squat_..., etc.)
    now automatically prefer the anthropometry-driven geometric moment arm
    estimators (via ReferenceData) when relevant limb measurements are supplied.
    Clear fallback to static tables with explanatory notes on the attachment.
    Use the new `use_geometric` parameter for explicit control.
"""

from typing import Optional

from fiberforce.models import (
    UserAnthropometry,
    Subject,
    Muscle,
    MuscleAttachment,
    JointAngles,
    ExternalLoad,
    LiftConfiguration,
    Pose,
    AnalyzedPosition,
    KNOWN_MUSCLE_REGIONS,
)
from fiberforce.reference.moment_arms import (
    BENCH_PRESS_LOAD_MOMENT_ARMS,
    # Per-joint loads for multi-muscle dominance % across all lifts (squat hip/knee, DL hip/lumbar, OHP sh/elbow etc)
    SQUAT_HIP_LOAD_MOMENT_ARMS,
    SQUAT_KNEE_LOAD_MOMENT_ARMS,
    DEADLIFT_HIP_LOAD_MOMENT_ARMS,
    DEADLIFT_LUMBAR_LOAD_MOMENT_ARMS,
    OHP_SHOULDER_LOAD_MOMENT_ARMS,
    OHP_ELBOW_LOAD_MOMENT_ARMS,
    RDL_HIP_LOAD_MOMENT_ARMS,
    RDL_LUMBAR_LOAD_MOMENT_ARMS,
    INCLINE_SHOULDER_LOAD_MOMENT_ARMS,
    INCLINE_ELBOW_LOAD_MOMENT_ARMS,
)
from fiberforce.reference import (
    get_default_sternal_pec_attachment,
    get_default_glute_max_attachment,
    get_default_vastus_lateralis_attachment,
    # Deadlift v0.2
    get_default_hamstring_attachment,
    get_default_erector_attachment,
    # OHP full parity (polish)
    get_default_anterior_delt_attachment,
    get_default_lateral_delt_attachment,
    get_default_posterior_delt_attachment,
    get_default_triceps_long_attachment,
    get_default_reference,
)
from fiberforce.reference.geometric import (
    estimate_bench_sternal_ma,
    estimate_squat_glute_ma,
    estimate_squat_quad_ma,
)
from fiberforce.calculations.utils import inches_to_cm, load_lbs_to_kg


def _resolve_target_region(target_region_name: Optional[str], lift_hint: Optional[str] = None) -> "MuscleRegion":
    """Robust resolver that understands the full 'Muscle::Region' strings used in the GUI
    dropdowns (and also bare region names or partials from CLI).

    This fixes cases where selecting "Deltoid::Anterior" for bench (or similar) was ignored
    and fell back to the default (e.g. Sternal fibers / pectoralis).
    """
    if not target_region_name:
        if lift_hint and ("bench" in lift_hint.lower() or "incline" in lift_hint.lower()):
            target_region_name = "Pectoralis Major::Sternal fibers"
        else:
            target_region_name = "Gluteus Maximus::Upper fibers"

    name = target_region_name.strip()
    lower = name.lower()

    # 1. Exact match on the nice display format we use in dropdowns
    for r in KNOWN_MUSCLE_REGIONS:
        if str(r).lower() == lower or f"{r.muscle_name}::{r.region_name}".lower() == lower:
            return r

    # 2. If it has :: , split and match parts against muscle + region
    if "::" in name:
        parts = [p.strip().lower() for p in name.split("::", 1)]
        for r in KNOWN_MUSCLE_REGIONS:
            m = r.muscle_name.lower()
            reg = r.region_name.lower()
            if any(p and (p in m or m in p) for p in parts) and any(p and (p in reg or reg in p) for p in parts):
                return r

    # 3. Exact region name match (bare "Anterior", "Upper fibers", etc.)
    for r in KNOWN_MUSCLE_REGIONS:
        if r.region_name.lower() == lower:
            return r

    # 4. Substring match on region (lenient)
    for r in KNOWN_MUSCLE_REGIONS:
        reg = r.region_name.lower()
        if lower in reg or reg in lower:
            return r

    # 5. Match on muscle name
    for r in KNOWN_MUSCLE_REGIONS:
        if lower in r.muscle_name.lower():
            return r

    # 6. Lift-specific sensible defaults
    if lift_hint:
        lh = lift_hint.lower()
        if "bench" in lh or "incline" in lh:
            for r in KNOWN_MUSCLE_REGIONS:
                if "Sternal" in r.region_name:
                    return r
        if "squat" in lh or "dead" in lh or "romanian" in lh or "front" in lh or "sumo" in lh:
            for r in KNOWN_MUSCLE_REGIONS:
                if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name:
                    return r
        if "ohp" in lh or "overhead" in lh:
            for r in KNOWN_MUSCLE_REGIONS:
                if r.muscle_name == "Deltoid" and "Anterior" in r.region_name:
                    return r

    # Ultimate fallback
    for r in KNOWN_MUSCLE_REGIONS:
        if "Sternal" in r.region_name:
            return r
    return KNOWN_MUSCLE_REGIONS[0]


def _normalize_anthro_kwargs(kwargs: dict) -> dict:
    """If units=imperial, convert common anthro inch keys to _cm for builders."""
    if kwargs.pop("units", "imperial") != "imperial":
        return kwargs
    for in_key, cm_key in [
        ("humerus_in", "humerus_length_cm"), ("humerus_cm", "humerus_length_cm"),
        ("forearm_in", "forearm_length_cm"), ("forearm_cm", "forearm_length_cm"),
        ("biacromial_in", "biacromial_width_cm"), ("biacromial_cm", "biacromial_width_cm"),
        ("torso_depth_in", "torso_depth_at_chest_cm"), ("torso_depth_cm", "torso_depth_at_chest_cm"),
        ("femur_in", "femur_length_cm"), ("femur_cm", "femur_length_cm"),
        ("tibia_in", "tibia_length_cm"), ("tibia_cm", "tibia_length_cm"),
        ("biiliac_in", "biiliac_width_cm"), ("biiliac_cm", "biiliac_width_cm"),
    ]:
        if in_key in kwargs and kwargs[in_key] is not None:
            val = kwargs.pop(in_key)
            if "in" in in_key:
                kwargs[cm_key] = inches_to_cm(val)
            else:
                kwargs[cm_key] = val
    return kwargs

def _normalize_load(load_kg: float, kwargs: dict) -> float:
    """Support load_lbs -> convert to kg."""
    if "load_lbs" in kwargs:
        lbs = kwargs.pop("load_lbs")
        return load_lbs_to_kg(lbs)
    return load_kg


def example_user_anthropometry() -> UserAnthropometry:
    """Returns a synthetic but realistic set of measurements for a lifter."""
    anthro = UserAnthropometry(
        name="Example Lifter",
        measurement_date="2026-05-26",
        humerus_length_cm=32.0,
        forearm_length_cm=25.5,
        biacromial_width_cm=38.0,
        torso_depth_at_chest_cm=22.0,
        femur_length_cm=42.0,
        tibia_length_cm=38.0,
        notes="Synthetic data for development and testing. Not real measurements.",
    )

    # Example muscle architecture for sternal pec fibers
    anthro.muscle_architecture["pectoralis_major_sternal"] = {
        "pcsa_cm2": 26.0,
        "pennation_angle_deg": 20.0,
        "optimal_fiber_length_cm": 11.5,
    }

    return anthro


def example_sternal_pec_attachment() -> MuscleAttachment:
    """Returns a MuscleAttachment for the sternal fibers using reference data."""
    return get_default_sternal_pec_attachment("flat_bench_bottom")


def example_bench_press_pose(variation: str = "flat_bench_bottom") -> Pose:
    """Returns a realistic example Pose for common bench press positions."""
    attachment = example_sternal_pec_attachment()

    joint_angles = JointAngles(
        values={
            "shoulder": 90.0,
            "elbow": 90.0,
        }
    )

    external_load = ExternalLoad(
        mass_kg=100.0,
        load_type="barbell",
        load_position="in hands",
    )

    load_ma = BENCH_PRESS_LOAD_MOMENT_ARMS.get(variation, 32.0)

    pose = Pose(
        name=f"100kg Bench - {variation}",
        joint_angles=joint_angles,
        external_load=external_load,
        active_attachments=[attachment],
        load_moment_arms={"shoulder": load_ma},
        notes=f"Synthetic example for {variation}.",
    )

    return pose


def example_analyzed_bench_press_position() -> AnalyzedPosition:
    """Returns a ready-to-analyze position for the bottom of a bench press."""
    pose = example_bench_press_pose()

    sternal_region = next(
        r for r in KNOWN_MUSCLE_REGIONS if r.region_name == "Sternal fibers"
    )

    return AnalyzedPosition(
        pose=pose,
        target_regions=[sternal_region],
    )


def example_subject() -> Subject:
    """Returns a complete example Subject with anthropometry and muscle data."""
    anthro = example_user_anthropometry()
    sternal = next(
        r for r in KNOWN_MUSCLE_REGIONS if r.region_name == "Sternal fibers"
    )

    pec_major = Muscle(
        name="Pectoralis Major",
        regions=[sternal],
        primary_joints=["shoulder"],
    )

    attachment = example_sternal_pec_attachment()

    return Subject(
        anthropometry=anthro,
        muscles=[pec_major],
        attachments=[attachment],
        name="Example Subject",
    )


def example_bench_press_configuration() -> LiftConfiguration:
    """Returns a sample LiftConfiguration for the bottom of a bench press."""
    sternal = next(
        r for r in KNOWN_MUSCLE_REGIONS if r.region_name == "Sternal fibers"
    )

    return LiftConfiguration(
        lift_name="Bench Press",
        variation="Flat",
        joint_angles=JointAngles(values={"shoulder": 90.0, "elbow": 90.0}),
        external_load=ExternalLoad(mass_kg=100.0),
        grip_width_cm=58.0,
        grip_orientation="pronated",
        target_regions=[sternal],
        notes="Example configuration for testing.",
    )


# -------------------------------------------------------------------
# Flexible builders for CLI / analysis use (v0.1.1+)
# -------------------------------------------------------------------

BENCH_POSITIONS = {
    "bottom": {"shoulder": 90.0, "elbow": 90.0},
    "mid": {"shoulder": 60.0, "elbow": 60.0},
    "near_lockout": {"shoulder": 30.0, "elbow": 20.0},
}

BENCH_VARIATIONS = ["flat", "incline_30", "decline_15"]


def build_bench_analyzed_position(
    load_kg: float = 100.0,
    position: str = "bottom",
    variation: str = "flat",
    target_region_name: str = "Sternal fibers",
    humerus_cm: Optional[float] = None,
    forearm_cm: Optional[float] = None,
    biacromial_cm: Optional[float] = None,
    torso_depth_cm: Optional[float] = None,
    grip_width_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> AnalyzedPosition:
    """
    Build a ready-to-analyze bench press position from high-level parameters.
    Used by the CLI analyze command and for experimentation.

    GEOMETRIC PREFERRED PATH (new in ReferenceData polish):
        When humerus_cm / biacromial_cm / torso_depth_cm (or grip_width_cm) are
        supplied, the geometric estimator is preferred for the sternal pec
        moment arm. Falls back gracefully to static tables otherwise.
        The attachment notes clearly record which source was used.
        Pass use_geometric=False to force static reference tables.
    """
    kwargs = _normalize_anthro_kwargs(locals().copy())  # support imperial inches
    load_kg = _normalize_load(load_kg, locals().copy())

    from fiberforce.reference.moment_arms import (
        BENCH_PRESS_LOAD_MOMENT_ARMS,
        BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS,
        BENCH_PRESS_ANTERIOR_DELT_MOMENT_ARMS,
        BENCH_PRESS_TRICEPS_MOMENT_ARMS,
        BENCH_PRESS_ELBOW_LOAD_MOMENT_ARMS,
    )

    # Map user-friendly names to reference keys
    pos_key = {
        "bottom": "flat_bench_bottom",
        "mid": "flat_bench_mid",
        "near_lockout": "flat_bench_near_lockout",
    }.get(position, "flat_bench_bottom")

    if variation == "incline_30":
        pos_key = "incline_30_bottom"
    elif variation == "decline_15":
        pos_key = "decline_15_bottom"

    # Grip width support for demonstrating % dominance shifts (close grip increases triceps demand, wide increases pec leverage)
    var_l = (variation or "").lower()
    if "close" in var_l:
        pos_key = "close_grip_bottom" if "bottom" in pos_key else pos_key
    elif "wide" in var_l:
        pos_key = "wide_grip_bottom" if "bottom" in pos_key else pos_key

    # Find target region (robust to "Muscle::Region" GUI strings, bare names, etc.)
    target_region = _resolve_target_region(target_region_name, lift_hint="bench")

    # Build anthropometry (use overrides or defaults) — richer than before
    anthro = UserAnthropometry(
        name="CLI User",
        humerus_length_cm=humerus_cm or 32.0,
        forearm_length_cm=forearm_cm or 25.5,
        biacromial_width_cm=biacromial_cm or 38.0,
        torso_depth_at_chest_cm=torso_depth_cm or 22.0,
        notes="Built from CLI parameters (partial personalization).",
    )

    # Muscle + attachment
    Muscle(
        name="Pectoralis Major",
        regions=[target_region],
        primary_joints=["shoulder"],
    )

    ref = get_default_reference()

    # Determine MA table and joint based on target (to support deltoid/triceps as target)
    joint = "shoulder"
    ref_key = "sternal_pecs"
    ma_table = BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS
    default_ma = 5.7
    if target_region:
        mname = target_region.muscle_name.lower()
        rname = target_region.region_name.lower()
        if "deltoid" in mname and "anterior" in rname:
            ref_key = "anterior_delt"
            ma_table = BENCH_PRESS_ANTERIOR_DELT_MOMENT_ARMS
            default_ma = 3.8
        elif "triceps" in mname:
            joint = "elbow"
            ref_key = "triceps"
            ma_table = BENCH_PRESS_TRICEPS_MOMENT_ARMS
            default_ma = 2.6

    # === GEOMETRIC PREFERRED PATH (deep integration) ===
    muscle_ma = None
    ma_source_note = "static reference table"
    if use_geometric is not False:
        muscle_ma = ref.estimate_moment_arm(
            "bench", ref_key,
            anthro=anthro,
            grip_width_cm=grip_width_cm,
            position=pos_key,
        )
        if muscle_ma is not None:
            ma_source_note = "geometric (anthropometry-driven)"

    if muscle_ma is None:
        muscle_ma = ma_table.get(
            pos_key, {joint: default_ma}
        )[joint]
        ma_source_note = "static reference (fallback)"

    # If user chose a secondary mover (e.g. deltoid on flat bench), note that we are using
    # the primary mover's (pec) MA tables as a proxy where applicable. The region selection is now honored.
    if target_region and "pectoralis" not in target_region.muscle_name.lower():
        ma_source_note += " (primary mover MA used as proxy for this target)"

    attachment = MuscleAttachment(
        muscle_region=target_region,
        joints_crossed=[joint],
        moment_arms_at_position={joint: muscle_ma},
        notes=f"Reference moment arms for {pos_key} [{ma_source_note}]",
    )

    # Always include co-primary movers for full contribution % and grip width dominance demo
    # (pecs, anterior delt for shoulder; triceps for elbow)
    pec_region = next((r for r in KNOWN_MUSCLE_REGIONS if "Pectoralis Major" in r.muscle_name and "Sternal" in r.region_name), target_region)
    pec_ma = BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS.get(pos_key, {"shoulder": 5.7})["shoulder"]
    pec_att = MuscleAttachment(
        muscle_region=pec_region,
        joints_crossed=["shoulder"],
        moment_arms_at_position={"shoulder": pec_ma},
        notes=f"Sternal pec MA for {pos_key}",
    )

    delt_region = next((r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and r.region_name == "Anterior"), target_region)
    delt_ma = BENCH_PRESS_ANTERIOR_DELT_MOMENT_ARMS.get(pos_key, {"shoulder": 3.8})["shoulder"]
    delt_att = MuscleAttachment(
        muscle_region=delt_region,
        joints_crossed=["shoulder"],
        moment_arms_at_position={"shoulder": delt_ma},
        notes="Anterior delt MA (approx from literature)",
    )

    tri_region = next((r for r in KNOWN_MUSCLE_REGIONS if "Triceps Brachii" in r.muscle_name and "Long" in r.region_name), target_region)
    tri_ma = BENCH_PRESS_TRICEPS_MOMENT_ARMS.get(pos_key, {"elbow": 2.6})["elbow"]
    tri_att = MuscleAttachment(
        muscle_region=tri_region,
        joints_crossed=["elbow"],
        moment_arms_at_position={"elbow": tri_ma},
        notes="Triceps long head elbow MA (approx)",
    )

    active_attachments = [attachment]
    for extra in [pec_att, delt_att, tri_att]:
        if extra.muscle_region != target_region:
            active_attachments.append(extra)

    # Joint angles for the chosen position (using short joint identifiers to match attachment convention)
    raw_angles = BENCH_POSITIONS.get(position, BENCH_POSITIONS["bottom"])
    # Normalize to short keys expected by attachments and validation ("shoulder", "elbow")
    joint_angles = JointAngles(
        values={"shoulder": raw_angles.get("shoulder_flexion", 90.0), "elbow": raw_angles.get("elbow_flexion", 90.0)}
    )

    # External load
    external_load = ExternalLoad(mass_kg=load_kg, load_type="barbell", load_position="in hands")

    # Load moment arm (static tables — geometric focuses on muscle MA)
    load_ma = BENCH_PRESS_LOAD_MOMENT_ARMS.get(pos_key, 30.0)

    # Grip width affects shoulder demand (wider grip tends to increase shoulder NJM per studies)
    if "wide" in var_l:
        load_ma *= 1.06
    elif "close" in var_l:
        load_ma *= 0.96

    load_ma_elbow = BENCH_PRESS_ELBOW_LOAD_MOMENT_ARMS.get(pos_key, 7.2)

    active_attachments = [attachment, pec_att, delt_att, tri_att] if 'pec_att' in locals() else [attachment]

    pose = Pose(
        name=f"{load_kg}kg Bench {variation} @ {position}",
        joint_angles=joint_angles,
        external_load=external_load,
        active_attachments=active_attachments,
        load_moment_arms={"shoulder": load_ma, "elbow": load_ma_elbow},
        notes=f"Generated by build_bench_analyzed_position for analysis. MA source: {ma_source_note}. Multi-muscle for % contrib (grip affects dominance).",
    )

    # unique by name
    seen = set()
    target_regions = []
    for att in active_attachments:
        key = (att.muscle_region.muscle_name, att.muscle_region.region_name)
        if key not in seen:
            seen.add(key)
            target_regions.append(att.muscle_region)
    return AnalyzedPosition(pose=pose, target_regions=target_regions)


# -------------------------------------------------------------------
# Lower body / Squat builders (v0.1.2 foundation)
# -------------------------------------------------------------------

SQUAT_POSITIONS = {
    "bottom": {"hip": 110.0, "knee": 35.0, "ankle": 25.0},   # typical high-bar bottom / parallel
    "mid":    {"hip": 70.0,  "knee": 60.0, "ankle": 20.0},   # mid-ascent approximation
    "top":    {"hip": 20.0,  "knee": 10.0, "ankle": 5.0},    # near lockout / standing tall
}


def example_lower_body_anthropometry() -> UserAnthropometry:
    """Synthetic but realistic lower-body focused anthropometry."""
    return UserAnthropometry(
        name="Example Squatter",
        femur_length_cm=42.0,
        tibia_length_cm=38.0,
        biiliac_width_cm=28.0,
        leg_length_cm=92.0,
        notes="Synthetic data for squat/OHP development.",
    )


def build_squat_analyzed_position(
    load_kg: float = 140.0,
    variation: str = "high_bar",
    position: str = "bottom",   # NEW for v0.4 limited dynamic support: bottom, mid, top, etc.
    target_region_name: str = "Upper fibers",
    femur_cm: Optional[float] = None,
    tibia_cm: Optional[float] = None,
    stance_width_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> AnalyzedPosition:
    """
    Build a ready-to-analyze high-bar or low-bar squat position.
    Supports discrete positions (bottom, mid, top) for limited dynamic / multi-position analysis (v0.4).

    Targets glute max upper fibers by default (excellent for "glute emphasis" comparisons).

    GEOMETRIC PREFERRED PATH:
        Supplying femur_cm / tibia_cm (and optionally stance_width_cm) will
        cause the builder to prefer geometric estimates for glute and/or quad MA.
        Clear fallback + notes on the generated attachments.
    """
    from fiberforce.reference.moment_arms import (
        SQUAT_LOAD_MOMENT_ARMS,
    )

    # Position-aware key for reference tables (fallback to bottom if exact match not present)
    base = "high_bar" if variation == "high_bar" else "low_bar"
    pos_key = f"{base}_{position}" if position in ("bottom", "mid", "top") else f"{base}_bottom"

    target_region = _resolve_target_region(target_region_name, lift_hint="squat")

    anthro = UserAnthropometry(
        name="CLI Squat Subject",
        femur_length_cm=femur_cm or 42.0,
        tibia_length_cm=tibia_cm or 38.0,
    )

    ref = get_default_reference()

    # === Always build full prime-mover set for % dominance (glute hip + quad knee + ham co-hip).
    # Geo preferred for glute (primary); tables for others (or via getters which use tables).
    # Variation (high_bar vs low_bar) changes relative MAs -> shifts dominance % (low bar typically
    # increases glute MA and hip load demand per literature).
    glute_att = None
    ma_source = "static reference"
    if use_geometric is not False:
        geo_ma = ref.estimate_moment_arm(
            "squat", "glute_max",
            anthro=anthro,
            stance_width_cm=stance_width_cm,
            variation=variation,
            position=position,
        )
        if geo_ma is not None:
            ma_source = "geometric (anthropometry-driven)"
            g_reg = target_region if (target_region and "glute" in (target_region.muscle_name + target_region.region_name).lower()) else next(
                (r for r in KNOWN_MUSCLE_REGIONS if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name), target_region
            )
            glute_att = MuscleAttachment(
                muscle_region=g_reg,
                joints_crossed=["hip"],
                moment_arms_at_position={"hip": geo_ma},
                notes=f"Geometric glute MA for {pos_key} (stance={stance_width_cm})",
            )
    if glute_att is None:
        glute_att = get_default_glute_max_attachment(pos_key) or get_default_glute_max_attachment(f"{base}_bottom")
        if use_geometric and "static" in ma_source.lower():
            glute_att.notes = (glute_att.notes or "") + f" [geo fallback for {position}]"

    # Co-movers via getters (tables inside: low_bar has higher glute MA 7.1 vs high 6.2; quad inverse)
    quad_att = get_default_vastus_lateralis_attachment(pos_key)
    ham_att = get_default_hamstring_attachment(pos_key)

    active_attachments = [glute_att, quad_att, ham_att]
    # If target is quad or ham, still keep all for full % view; selection honored in result list.
    if target_region:
        # ensure target is first if matches one
        for i, att in enumerate(active_attachments):
            if att.muscle_region.muscle_name == target_region.muscle_name and att.muscle_region.region_name == target_region.region_name:
                active_attachments = [att] + [a for j,a in enumerate(active_attachments) if j!=i]
                break

    # Per-joint load MAs (hip larger, knee smaller; low bar higher hip demand)
    hip_load = SQUAT_HIP_LOAD_MOMENT_ARMS.get(pos_key, SQUAT_HIP_LOAD_MOMENT_ARMS.get(f"{base}_bottom", 20.0))
    knee_load = SQUAT_KNEE_LOAD_MOMENT_ARMS.get(pos_key, 7.0)
    if "low_bar" in pos_key:
        hip_load *= 1.08  # low bar bias to posterior/hip per studies

    # Angles + load
    pos_for_angles = position if position in SQUAT_POSITIONS else "bottom"
    joint_angles = JointAngles(values=SQUAT_POSITIONS[pos_for_angles].copy())
    external_load = ExternalLoad(mass_kg=load_kg, load_type="barbell", load_position="on back")

    pose = Pose(
        name=f"{load_kg}kg Squat {variation} @ {position}",
        joint_angles=joint_angles,
        external_load=external_load,
        active_attachments=active_attachments,
        load_moment_arms={"hip": hip_load, "knee": knee_load},
        notes=(
            f"Generated for squat analysis (multi-muscle for % contrib). "
            f"MA source: {ma_source}. low/high bar shifts glute vs quad dominance at hip (low bar +glute %). "
            f"Position: {position}"
        ),
    )

    # unique regions
    seen = set()
    target_regions = []
    for att in active_attachments:
        key = (att.muscle_region.muscle_name, att.muscle_region.region_name)
        if key not in seen:
            seen.add(key)
            target_regions.append(att.muscle_region)
    return AnalyzedPosition(pose=pose, target_regions=target_regions)


# Also expose a simple factory for a full lower-body Subject
def example_subject_with_lower_body() -> Subject:
    """Subject with anthropometry + glute and quad regions modeled."""
    anthro = example_lower_body_anthropometry()

    glute_upper = next(r for r in KNOWN_MUSCLE_REGIONS if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name)
    vastus_lat = next(r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Vastus Lateralis")

    glute_muscle = Muscle("Gluteus Maximus", regions=[glute_upper], primary_joints=["hip"])
    quad_muscle = Muscle("Vastus Lateralis", regions=[vastus_lat], primary_joints=["knee"])

    glute_att = get_default_glute_max_attachment("high_bar_bottom")
    quad_att = get_default_vastus_lateralis_attachment("high_bar_bottom")

    return Subject(
        anthropometry=anthro,
        muscles=[glute_muscle, quad_muscle],
        attachments=[glute_att, quad_att],
        name="Lower Body Example Subject",
    )


# -------------------------------------------------------------------
# Deadlift builders (v0.2) — Conventional and Sumo at bottom (floor)
# First-class support mirroring squat quality.
# -------------------------------------------------------------------

DEADLIFT_POSITIONS = {
    "bottom": {"hip": 92.0, "knee": 28.0, "ankle": 15.0, "lumbar": 22.0},      # conventional floor pull + slight lumbar flexion
    "mid":    {"hip": 60.0, "knee": 50.0, "ankle": 12.0, "lumbar": 15.0},      # mid pull approx
    "top":    {"hip": 25.0, "knee": 15.0, "ankle": 5.0, "lumbar": 5.0},       # near lockout
    "sumo_bottom": {"hip": 78.0, "knee": 38.0, "ankle": 18.0, "lumbar": 18.0},
}


def build_deadlift_analyzed_position(
    load_kg: float = 160.0,
    variation: str = "conventional",
    position: str = "bottom",   # v0.4: bottom, mid, top for limited multi-position
    target_region_name: str = "Upper fibers",
    femur_cm: Optional[float] = None,
    tibia_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> AnalyzedPosition:
    """
    Build a ready-to-analyze Conventional or Sumo deadlift position (supports bottom/mid/top
    for v0.4 limited dynamic / multi-position analysis; sumo limited to bottom kinematics).

    This is the key high-demand position for v0.2 scope: hip extension + lumbar anti-flexion.

    Default target: Glute max upper fibers (excellent for comparing conventional vs sumo glute demand).
    Supports:
      - "Upper fibers", glute* → glute max attachment (conventional/sumo keys)
      - ham*, "Biceps Femoris", semitend* etc → hamstring attachment
      - erect*, lumbar, "Erector Spinae" → erector (lumbar) attachment

    GEOMETRIC NOTE: Lower-body geometric estimators (glute) are available via
    ReferenceData when femur/tibia are supplied; the builder will prefer them
    for glute targets when use_geometric is not False.

    Example usage:
        pos = build_deadlift_analyzed_position(load_kg=180, variation="sumo", target_region_name="Lumbar")
        pos = build_deadlift_analyzed_position(165, "conventional", "Upper fibers")
        pos = build_deadlift_analyzed_position(160, "conventional", position="mid")
    """
    from fiberforce.reference.moment_arms import (
        DEADLIFT_LOAD_MOMENT_ARMS,
    )

    var_lower = variation.lower().replace("-", "").replace("_", "")
    if var_lower in ("sumo", "sumodeadlift"):
        pos_key = "sumo_bottom"
        var_display = "Sumo"
    else:
        pos_norm = position if position in ("bottom", "mid", "top") else "bottom"
        pos_key = f"conventional_{pos_norm}"
        var_display = "Conventional"

    # Always build full posterior chain for deadlift: glute (hip) + ham (hip) + erector (lumbar)
    # for % dominance demo. Sumo vs conventional changes load MA (sumo shorter) + slight MA diffs
    # (more upright in sumo -> different relative shares). Smart target still honored for primary.
    target_lower = (target_region_name or "").lower()
    ma_source = "static reference (multi)"

    # Resolve primary for notes/target first
    if "erect" in target_lower or "lumbar" in target_lower or "spinal" in target_lower:
        prim_reg = next((r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Erector Spinae" and "Lumbar" in r.region_name), None)
        if prim_reg is None:
            prim_reg = next(r for r in KNOWN_MUSCLE_REGIONS if "Erector Spinae" in r.muscle_name)
    elif "ham" in target_lower or "biceps fem" in target_lower or "semi" in target_lower:
        prim_reg = next((r for r in KNOWN_MUSCLE_REGIONS if "Biceps Femoris (Long Head)" in r.muscle_name), None)
        if prim_reg is None:
            prim_reg = next(r for r in KNOWN_MUSCLE_REGIONS if "Semitendinosus" in r.muscle_name)
    else:
        prim_reg = _resolve_target_region(target_region_name, lift_hint="deadlift")

    # Build the three co-movers (use getters for correct table per pos_key / sumo key)
    g_att = get_default_glute_max_attachment(pos_key)
    h_att = get_default_hamstring_attachment(pos_key)
    e_att = get_default_erector_attachment(pos_key)

    # Geo boost for glute if requested and matches primary-ish
    if use_geometric is not False and ("glute" in (target_region_name or "").lower() or prim_reg and "glute" in prim_reg.muscle_name.lower()):
        anthro = UserAnthropometry(name="CLI Deadlift Subject", femur_length_cm=femur_cm or 42.0, tibia_length_cm=tibia_cm or 38.0)
        geo = get_default_reference().estimate_moment_arm("squat", "glute_max", anthro=anthro, variation=variation)
        if geo is not None:
            g_att = MuscleAttachment(muscle_region=g_att.muscle_region, joints_crossed=["hip"], moment_arms_at_position={"hip": geo}, notes=f"Geometric glute (DL {pos_key})")
            ma_source = "geometric + static co-movers"

    active_attachments = [g_att, h_att, e_att]
    # Put primary-ish first if we can identify
    if prim_reg:
        for i, att in enumerate(active_attachments):
            if att.muscle_region.muscle_name == prim_reg.muscle_name and att.muscle_region.region_name == prim_reg.region_name:
                active_attachments = [att] + [a for j, a in enumerate(active_attachments) if j != i]
                break

    # Per-joint load (use new tables; sumo shorter overall)
    hip_load = DEADLIFT_HIP_LOAD_MOMENT_ARMS.get(pos_key, 23.0)
    lum_load = DEADLIFT_LUMBAR_LOAD_MOMENT_ARMS.get(pos_key, hip_load * 0.8)

    # Angles
    if var_lower in ("sumo", "sumodeadlift"):
        angles = DEADLIFT_POSITIONS.get("sumo_bottom", DEADLIFT_POSITIONS["bottom"]).copy()
    else:
        pos_for_angles = position if position in ("bottom", "mid", "top") else "bottom"
        angles = DEADLIFT_POSITIONS.get(pos_for_angles, DEADLIFT_POSITIONS["bottom"]).copy()
    joint_angles = JointAngles(values=angles)

    external_load = ExternalLoad(mass_kg=load_kg, load_type="barbell", load_position="in hands")

    pose = Pose(
        name=f"{load_kg}kg {var_display} Deadlift @ {position}",
        joint_angles=joint_angles,
        external_load=external_load,
        active_attachments=active_attachments,
        load_moment_arms={"hip": hip_load, "lumbar": lum_load},
        notes=(
            f"Generated by build_deadlift... (multi posterior chain for % dom). "
            f"conv vs sumo: sumo shorter load MA + different glute/ham share. MA source: {ma_source}."
        ),
    )

    seen = set()
    target_regions = []
    for att in active_attachments:
        key = (att.muscle_region.muscle_name, att.muscle_region.region_name)
        if key not in seen:
            seen.add(key)
            target_regions.append(att.muscle_region)
    return AnalyzedPosition(pose=pose, target_regions=target_regions)


# Simple factory exposing deadlift posterior chain (glutes + hams + erectors)
def example_subject_with_posterior_chain() -> Subject:
    """Subject with anthropometry + glute, hamstring, and lumbar erector modeled (ideal for deadlift)."""
    anthro = example_lower_body_anthropometry()

    glute_upper = next(r for r in KNOWN_MUSCLE_REGIONS if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name)
    hams = next(r for r in KNOWN_MUSCLE_REGIONS if "Biceps Femoris (Long Head)" in r.muscle_name)
    erector_lumbar = next(r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Erector Spinae" and r.region_name == "Lumbar")

    glute_muscle = Muscle("Gluteus Maximus", regions=[glute_upper], primary_joints=["hip"])
    ham_muscle = Muscle("Hamstrings (Long Head)", regions=[hams], primary_joints=["hip"])
    erector_muscle = Muscle("Erector Spinae", regions=[erector_lumbar], primary_joints=["lumbar"])

    glute_att = get_default_glute_max_attachment("conventional_bottom")
    ham_att = get_default_hamstring_attachment("conventional_bottom")
    erector_att = get_default_erector_attachment("conventional_bottom")

    return Subject(
        anthropometry=anthro,
        muscles=[glute_muscle, ham_muscle, erector_muscle],
        attachments=[glute_att, ham_att, erector_att],
        name="Posterior Chain Deadlift Example Subject",
    )


# -------------------------------------------------------------------
# OHP (Overhead Press) — FULL PARITY BUILDER (polish task)
# Standing / Seated + multiple ROM positions + smart delt/triceps dispatch.
# Matches deadlift/squat quality and ergonomics exactly.
# -------------------------------------------------------------------

OHP_POSITIONS = {
    "bottom": {"shoulder": 78.0, "elbow": 82.0},      # bar at upper chest / start of press
    "mid": {"shoulder": 125.0, "elbow": 52.0},       # ~90°+ shoulder elevation
    "lockout": {"shoulder": 172.0, "elbow": 12.0},   # full overhead lockout
}


# 4-6 representative OHP configurations (documented for users / tests / examples)
OHP_EXAMPLE_CONFIGS = [
    {"load_kg": 70, "variation": "standing", "position": "bottom", "target": "Anterior"},
    {"load_kg": 65, "variation": "seated", "position": "bottom", "target": "Anterior"},
    {"load_kg": 75, "variation": "standing", "position": "mid", "target": "Lateral"},
    {"load_kg": 60, "variation": "seated", "position": "lockout", "target": "Long head"},
    {"load_kg": 68, "variation": "standing", "position": "lockout", "target": "Triceps"},
    {"load_kg": 72, "variation": "strict_standing", "position": "bottom", "target": "Posterior"},
]


def build_ohp_analyzed_position(
    load_kg: float = 70.0,
    position: str = "bottom",
    variation: str = "standing",
    target_region_name: str = "Anterior",
    humerus_cm: Optional[float] = None,
    forearm_cm: Optional[float] = None,
    biacromial_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> AnalyzedPosition:
    """
    Build a ready-to-analyze overhead press (OHP) position.

    Full first-class support matching bench/squat/deadlift builders.

    Supports:
      - variation: "standing" (default), "seated", "strict_standing"
      - position: "bottom", "mid", "lockout"  (maps to rich reference keys)
      - target_region_name smart dispatch:
          • anterior*, delt*, "Anterior" → anterior delt (primary)
          • lateral*, "Lateral" → lateral delt (abduction emphasis)
          • rear*, posterior*, "Posterior" → posterior/rear delt (stabilizer)
          • triceps*, "Long head", elbow* → triceps long head (lockout focus)

    Uses dedicated OHP attachment getters + expanded reference tables.
    Personalization via humerus/forearm/biacromial.

    GEOMETRIC: Upper-body geometric support for delts is limited in the current
    prototype (focus is bench + squat). The builder will still route through
    ReferenceData.estimate for future extensibility.

    Example usage (6+ configs supported via OHP_EXAMPLE_CONFIGS):
        pos = build_ohp_analyzed_position(70, "bottom", "standing", "Anterior")
        pos = build_ohp_analyzed_position(load_kg=65, variation="seated", position="mid", target_region_name="Lateral")
    """
    from fiberforce.reference.moment_arms import (
        OVERHEAD_PRESS_LOAD_MOMENT_ARMS,
    )

    var_lower = (variation or "standing").lower().replace("-", "_")
    pos_lower = (position or "bottom").lower()

    # Map to canonical OHP reference position keys (6+ supported)
    if "seat" in var_lower:
        base = "seated"
    elif "strict" in var_lower:
        base = "strict_standing"
    else:
        base = "standing"

    pos_map = {
        "bottom": "bottom",
        "mid": "mid",
        "lockout": "lockout",
        "top": "lockout",
        "near_lockout": "lockout",
    }
    pos_suffix = pos_map.get(pos_lower, "bottom")
    pos_key = f"{base}_{pos_suffix}"

    # Multi-mover for OHP % dominance: always include ant_delt (shoulder) + tri (elbow) + lat as co-shoulder.
    # (post can be added similarly). Shoulder delts share % by relative MA; tri 100% at elbow.
    # Target selection puts chosen first, but all shown.
    target_lower = (target_region_name or "Anterior").lower()
    target_region = _resolve_target_region(target_region_name, lift_hint="ohp")

    ant_att = get_default_anterior_delt_attachment(pos_key)
    lat_att = get_default_lateral_delt_attachment(pos_key)
    post_att = get_default_posterior_delt_attachment(pos_key)
    tri_att = get_default_triceps_long_attachment(pos_key)

    active = [ant_att, lat_att, post_att, tri_att]
    if target_region:
        for i, a in enumerate(active):
            if a.muscle_region.muscle_name == target_region.muscle_name and a.muscle_region.region_name == target_region.region_name:
                active = [a] + [x for j,x in enumerate(active) if j != i]
                break
        # if target was tri, still have the delts for shoulder context
        if "triceps" in target_lower or "long" in target_lower:
            # already have tri, delts provide shoulder co
            pass

    # Angles
    raw_angles = OHP_POSITIONS.get(pos_lower, OHP_POSITIONS["bottom"]).copy()
    joint_angles = JointAngles(values=raw_angles)

    external_load = ExternalLoad(mass_kg=load_kg, load_type="barbell", load_position="in hands")
    shoulder_load = OHP_SHOULDER_LOAD_MOMENT_ARMS.get(pos_key, OVERHEAD_PRESS_LOAD_MOMENT_ARMS.get(pos_key, 14.0))
    elbow_load = OHP_ELBOW_LOAD_MOMENT_ARMS.get(pos_key, 5.0)

    load_moment_arms = {"shoulder": shoulder_load, "elbow": elbow_load}

    pose = Pose(
        name=f"{load_kg}kg {variation.title()} OHP @ {position}",
        joint_angles=joint_angles,
        external_load=external_load,
        active_attachments=active,
        load_moment_arms=load_moment_arms,
        notes=(
            f"Generated by build_ohp_analyzed_position multi (ant+lat+post delt + tri) for % dom. "
            f"Target: {target_region}. Variation/pos affects delt MA share. OHP parity."
        ),
    )

    seen = set()
    trs = []
    for a in active:
        k = (a.muscle_region.muscle_name, a.muscle_region.region_name)
        if k not in seen:
            seen.add(k)
            trs.append(a.muscle_region)
    return AnalyzedPosition(pose=pose, target_regions=trs)


def example_subject_with_shoulders() -> Subject:
    """Subject with anthropometry + anterior/lateral/posterior delts + triceps long modeled (ideal for OHP)."""
    anthro = UserAnthropometry(
        name="Example OHP Presser",
        humerus_length_cm=32.5,
        forearm_length_cm=25.0,
        biacromial_width_cm=39.0,
        notes="Synthetic upper-body data for OHP development and testing.",
    )

    ant = next(r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and r.region_name == "Anterior")
    lat = next(r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and r.region_name == "Lateral")
    post = next(r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and "Posterior" in r.region_name)
    tri_long = next(r for r in KNOWN_MUSCLE_REGIONS if "Triceps Brachii" in r.muscle_name and "Long" in r.region_name)

    delt_muscle = Muscle("Deltoid", regions=[ant, lat, post], primary_joints=["shoulder"])
    tri_muscle = Muscle("Triceps Brachii", regions=[tri_long], primary_joints=["elbow", "shoulder"])

    ant_att = get_default_anterior_delt_attachment("standing_bottom")
    lat_att = get_default_lateral_delt_attachment("standing_mid")
    post_att = get_default_posterior_delt_attachment("standing_bottom")
    tri_att = get_default_triceps_long_attachment("standing_lockout")

    return Subject(
        anthropometry=anthro,
        muscles=[delt_muscle, tri_muscle],
        attachments=[ant_att, lat_att, post_att, tri_att],
        name="Shoulder Complex OHP Example Subject",
    )


def example_ohp_configurations(count: int = 6) -> list[dict]:
    """Return at least 4-6 documented OHP example configurations (for docs/tests/CLI demos)."""
    return OHP_EXAMPLE_CONFIGS[:count]


# -------------------------------------------------------------------
# GEOMETRIC MOMENT ARM PROTOTYPE HELPERS (added for Example 05)
# -------------------------------------------------------------------
# These provide convenient factory functions that demonstrate direct
# integration of the new anthropometry-driven estimators. They are
# intentionally lightweight and documented here as the "official"
# examples-layer integration point for the geometric direction.
# Real usage should prefer AnalysisService + ReferenceData.estimate_moment_arm
# or the raw functions in fiberforce.reference.geometric.

def build_bench_position_with_geometric_ma(
    load_kg: float = 100.0,
    grip_width_cm: float = 60.0,
    humerus_cm: float = 32.0,
    biacromial_cm: float = 38.0,
    torso_depth_cm: float = 22.0,
    position_key: str = "flat_bench_bottom",
) -> AnalyzedPosition:
    """
    Demonstration builder that uses the geometric estimator for sternal pec MA
    instead of the static table. All other data (load MA, angles) still use
    reference tables for this prototype.

    This is the pattern future builders can adopt when use_geometric_ma=True.
    """
    from fiberforce.reference.moment_arms import BENCH_PRESS_LOAD_MOMENT_ARMS

    anthro = UserAnthropometry(
        name="Geometric Bench Demo",
        humerus_length_cm=humerus_cm,
        biacromial_width_cm=biacromial_cm,
        torso_depth_at_chest_cm=torso_depth_cm,
    )

    ma = estimate_bench_sternal_ma(anthro, grip_width_cm=grip_width_cm, position=position_key)

    sternal = next(r for r in KNOWN_MUSCLE_REGIONS if r.region_name == "Sternal fibers")

    attachment = MuscleAttachment(
        muscle_region=sternal,
        joints_crossed=["shoulder"],
        moment_arms_at_position={"shoulder": ma},
        notes=f"GEOMETRIC estimate_bench_sternal_ma (grip={grip_width_cm}cm, h={humerus_cm}cm)",
    )

    load_ma = BENCH_PRESS_LOAD_MOMENT_ARMS.get(position_key, 30.0)

    pose = Pose(
        name=f"{load_kg}kg Bench (geometric MA) grip={grip_width_cm:.0f}cm",
        joint_angles=JointAngles(values={"shoulder": 90.0, "elbow": 90.0}),
        external_load=ExternalLoad(mass_kg=load_kg, load_type="barbell"),
        active_attachments=[attachment],
        load_moment_arms={"shoulder": load_ma},
        notes="Prototype using geometric moment arm estimation from anthropometry.",
    )
    return AnalyzedPosition(pose=pose, target_regions=[sternal])


def build_squat_position_with_geometric_ma(
    load_kg: float = 140.0,
    stance_width_cm: float = 65.0,
    femur_cm: float = 42.0,
    tibia_cm: float = 38.0,
    variation: str = "high_bar",
) -> AnalyzedPosition:
    """
    Demonstration builder using geometric estimators for both glute (hip) and
    quad (knee) moment arms. Shows how a single Subject's lower-body anthro
    can drive multiple joints.
    """
    from fiberforce.reference.moment_arms import SQUAT_LOAD_MOMENT_ARMS

    anthro = UserAnthropometry(
        name="Geometric Squat Demo",
        femur_length_cm=femur_cm,
        tibia_length_cm=tibia_cm,
    )

    glute_ma = estimate_squat_glute_ma(anthro, stance_width_cm=stance_width_cm, variation=variation)
    quad_ma = estimate_squat_quad_ma(anthro, stance_width_cm=stance_width_cm, variation=variation)

    glute_region = next(r for r in KNOWN_MUSCLE_REGIONS if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name)
    quad_region = next(r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Vastus Lateralis")

    glute_att = MuscleAttachment(
        muscle_region=glute_region,
        joints_crossed=["hip"],
        moment_arms_at_position={"hip": glute_ma},
        notes=f"GEOMETRIC glute (stance={stance_width_cm}cm)",
    )
    quad_att = MuscleAttachment(
        muscle_region=quad_region,
        joints_crossed=["knee"],
        moment_arms_at_position={"knee": quad_ma},
        notes=f"GEOMETRIC quad (stance={stance_width_cm}cm)",
    )

    load_ma = SQUAT_LOAD_MOMENT_ARMS.get("high_bar_bottom" if variation == "high_bar" else "low_bar_bottom", 20.0)

    pose = Pose(
        name=f"{load_kg}kg Squat (geometric MA) stance={stance_width_cm:.0f}cm",
        joint_angles=JointAngles(values={"hip": 110.0, "knee": 35.0, "ankle": 25.0}),
        external_load=ExternalLoad(mass_kg=load_kg, load_type="barbell"),
        active_attachments=[glute_att, quad_att],
        load_moment_arms={"hip": load_ma, "knee": load_ma * 0.55},
        notes="Prototype using geometric glute + quad moment arm estimation.",
    )
    return AnalyzedPosition(pose=pose, target_regions=[glute_region, quad_region])


# -------------------------------------------------------------------
# Continuous / dynamic ROM builders (post-v1 modeling depth, Theme 1 MVP)
# Parameterize by primary joint angle (knee for squat, shoulder for bench).
# Use linear interp on MA via ReferenceData continuous helpers.
# Generate list[AnalyzedPosition] for reuse with MultiPositionResult (duck-type).
# Still computes peak force per interpolated snapshot (no true dynamics/velocity yet).
# Imperial support via existing _normalize helpers.
# -------------------------------------------------------------------

def build_squat_continuous_positions(
    load_kg: float = 140.0,
    variation: str = "high_bar",
    knee_start: float = 35.0,   # bottom (flexed)
    knee_end: float = 170.0,    # top (near straight) -- note: values follow existing SQUAT_POSITIONS convention
    steps: int = 5,
    target_region_name: str = "Upper fibers",
    femur_cm: Optional[float] = None,
    tibia_cm: Optional[float] = None,
    stance_width_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> list[AnalyzedPosition]:
    """
    MVP continuous ROM for squat: vary knee angle, interpolate joint angles + MA.
    Returns ordered list of AnalyzedPosition (compatible with MultiPositionResult).
    Uses ref.get_*_continuous for MA (linear on discrete tables) + heuristic angle interp.
    Geometric: falls back to discrete geometric call at nearest, or static interp.

    New Level (Theme 1 depth slice): primary knee angle is carried through so that
    the improved _compute_length_tension_factor (piecewise active plateau 0.9-1.1 L0 + passive)
    in PeakForceCalculator can modulate demand per step when arch_data or angle is available.
    This makes per-position torques richer/varying over ROM (better material for self-competition
    PRs/trends on "best angle under realistic L-T"). Still per-snapshot peak; no velocity/inertia yet.
    See peak_force.py for the curve and service/analyze_continuous for usage.
    Update notes + GUI curve label when wired.
    """
    from fiberforce.reference.moment_arms import SQUAT_LOAD_MOMENT_ARMS
    from fiberforce.reference.data import get_default_reference  # already imported usually

    results = []
    base = "high_bar" if variation == "high_bar" else "low_bar"

    # Discrete knee anchors for bracketing (from SQUAT_POSITIONS)
    anchors = [
        (35.0, f"{base}_bottom"),
        (60.0, f"{base}_mid"),   # approx mid
        (170.0, f"{base}_top"),  # top has low knee value in data, but we use end as "straight"
    ]

    ref = get_default_reference()

    for i in range(steps):
        t = i / (steps - 1.0) if steps > 1 else 0.0
        knee = knee_start + (knee_end - knee_start) * t

        # Find bracketing discrete for MA interp
        if knee <= 60.0:
            k1, pk1 = 35.0, f"{base}_bottom"
            k2, pk2 = 60.0, f"{base}_mid"
            tt = (knee - 35.0) / 25.0 if 25.0 > 0 else 0.0
        else:
            k1, pk1 = 60.0, f"{base}_mid"
            k2, pk2 = 170.0, f"{base}_top"
            tt = (knee - 60.0) / 110.0 if 110.0 > 0 else 0.0
        tt = max(0.0, min(1.0, tt))

        # Prefer geometric with explicit flexion angle for continuous (better for ROM)
        glute_ma = None
        ma_source = "table interp (continuous MVP)"
        if use_geometric is not False:
            try:
                geo_ma = ref.estimate_moment_arm(
                    "squat", "glute_max",
                    anthro=anthro,
                    stance_width_cm=stance_width_cm,
                    variation=variation,
                    hip_flexion_deg=hip,  # explicit continuous angle
                )
                if geo_ma is not None:
                    glute_ma = geo_ma
                    ma_source = "geometric (continuous angle)"
            except Exception:
                pass
        if glute_ma is None:
            glute_ma = ref.get_moment_arm_continuous("squat", "glute_max", pk1, pk2, tt, "hip") or 6.0
            ma_source = "table interp (continuous MVP)"
        load_ma = ref.get_load_moment_arm_continuous("squat", pk1, pk2, tt) or 20.0

        # Interp angles (simple linear between bottom and top anchors for other joints)
        # Use bottom and top for full range
        bottom_ang = SQUAT_POSITIONS["bottom"]
        top_ang = SQUAT_POSITIONS["top"]
        hip = bottom_ang["hip"] + (top_ang["hip"] - bottom_ang["hip"]) * t
        ankle = bottom_ang["ankle"] + (top_ang["ankle"] - bottom_ang["ankle"]) * t

        joint_angles = JointAngles(values={"hip": hip, "knee": knee, "ankle": ankle})

        # Target region (glute)
        target_region = _resolve_target_region(target_region_name, lift_hint="squat")

        # Attachment with interpolated MA (force static interp for MVP; geometric would require angle-param estimator)
        ma_source = "interpolated (continuous MVP)"
        attachment = MuscleAttachment(
            muscle_region=target_region,
            joints_crossed=["hip"],
            moment_arms_at_position={"hip": glute_ma},
            notes=f"{ma_source} knee={knee:.1f}° hip={hip:.1f}°",
        )

        external_load = ExternalLoad(mass_kg=load_kg, load_type="barbell", load_position="on back")

        pose = Pose(
            name=f"{load_kg}kg Squat {variation} continuous knee={knee:.0f}°",
            joint_angles=joint_angles,
            external_load=external_load,
            active_attachments=[attachment],
            load_moment_arms={"hip": load_ma},
            notes=f"Continuous ROM MVP (interp on tables). Knee range [{knee_start},{knee_end}].",
        )

        ap = AnalyzedPosition(pose=pose, target_regions=[target_region])
        # attach for better display in results
        setattr(ap, 'position_description', f"knee={knee:.0f}°")
        results.append(ap)

    return results


# Similar for bench (vary shoulder angle) -- abbreviated for MVP
def build_bench_continuous_positions(
    load_kg: float = 100.0,
    variation: str = "flat",
    shoulder_start: float = 60.0,  # rough bottom
    shoulder_end: float = 20.0,    # near lockout
    steps: int = 5,
    target_region_name: str = "Sternal fibers",
    humerus_cm: Optional[float] = None,
    biacromial_cm: Optional[float] = None,
    torso_depth_cm: Optional[float] = None,
    grip_width_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> list[AnalyzedPosition]:
    """MVP continuous for bench: vary shoulder angle, interp MA."""
    from fiberforce.reference.moment_arms import BENCH_PRESS_LOAD_MOMENT_ARMS, BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS

    results = []
    ref = get_default_reference()

    for i in range(steps):
        t = i / (steps - 1.0) if steps > 1 else 0.0
        shoulder = shoulder_start + (shoulder_end - shoulder_start) * t

        # Map to discrete for interp (use flat for MVP even if incline)
        # For simplicity, always use flat keys for bench continuous MVP
        pk1, pk2 = "flat_bench_bottom", "flat_bench_near_lockout"
        tt = t  # direct

        pec_ma = ref.get_moment_arm_continuous("bench", "sternal_pecs", pk1, pk2, tt, "shoulder")
        if pec_ma is None:
            pec_ma = 4.5
        load_ma = ref.get_load_moment_arm_continuous("bench", pk1, pk2, tt) or 28.0

        joint_angles = JointAngles(values={"shoulder": shoulder, "elbow": 70.0 - t*30})

        target_region = next(
            (r for r in KNOWN_MUSCLE_REGIONS if r.region_name.lower() == target_region_name.lower()),
            next(r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name),
        )

        attachment = MuscleAttachment(
            muscle_region=target_region,
            joints_crossed=["shoulder"],
            moment_arms_at_position={"shoulder": pec_ma},
            notes=f"interp continuous MVP t={tt:.2f}",
        )

        external_load = ExternalLoad(mass_kg=load_kg, load_type="barbell")

        pose = Pose(
            name=f"{load_kg}kg Bench continuous shoulder={shoulder:.0f}°",
            joint_angles=joint_angles,
            external_load=external_load,
            active_attachments=[attachment],
            load_moment_arms={"shoulder": load_ma},
            notes="Continuous ROM MVP (linear table interp).",
        )
        ap = AnalyzedPosition(pose=pose, target_regions=[target_region])
        setattr(ap, 'position_description', f"shoulder={shoulder:.0f}°")
        results.append(ap)

    return results


# =============================================================================
# NEW EXERCISES (post-v1 scope expansion)
# =============================================================================

def build_incline_bench_analyzed_position(
    load_kg: float = 80.0,
    position: str = "bottom",
    variation: str = "incline_30",
    target_region_name: str = "Sternal fibers",
    humerus_cm: Optional[float] = None,
    biacromial_cm: Optional[float] = None,
    torso_depth_cm: Optional[float] = None,
    grip_width_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> AnalyzedPosition:
    """
    Builder for Incline Bench Press (post-v1 expansion) -- now multi-mover like flat bench
    for % dominance (clavicular vs sternal + ant delt + tri). Incline shifts more to clav/upper.
    """
    kwargs = _normalize_anthro_kwargs(locals().copy())
    load_kg = _normalize_load(load_kg, locals().copy())

    pos_key = {
        "bottom": "incline_30_bottom",
        "mid": "incline_30_mid",
        "top": "incline_30_top",
    }.get(position, "incline_30_bottom")

    if "45" in variation:
        pos_key = pos_key.replace("30", "45")

    target_region = _resolve_target_region(target_region_name, lift_hint="incline") or next(
        (r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name), None
    )

    anthro = UserAnthropometry(
        name="Incline User",
        humerus_length_cm=humerus_cm or 32.0,
        biacromial_width_cm=biacromial_cm or 38.0,
        torso_depth_at_chest_cm=torso_depth_cm or 22.0,
    )

    ref = get_default_reference()
    ma_source = "static (incline tables + co-movers)"

    # Primary-ish MA (use geo proxy or table for target-ish)
    muscle_ma = None
    if use_geometric is not False:
        muscle_ma = ref.estimate_moment_arm("bench", "sternal_pecs", anthro=anthro, grip_width_cm=grip_width_cm, position=pos_key)
        if muscle_ma:
            ma_source = "geo proxy + static co"
    if muscle_ma is None:
        muscle_ma = ref.get_moment_arm("incline", "sternal_pecs", pos_key, "shoulder") or 4.5

    # Always include co-movers for % (clav for incline emphasis, ant delt, tri elbow)
    sternal_reg = next((r for r in KNOWN_MUSCLE_REGIONS if "Pectoralis Major" in r.muscle_name and "Sternal" in r.region_name), target_region)
    clav_reg = next((r for r in KNOWN_MUSCLE_REGIONS if "Pectoralis Major" in r.muscle_name and "Clavicular" in r.region_name), target_region)
    delt_reg = next((r for r in KNOWN_MUSCLE_REGIONS if r.muscle_name == "Deltoid" and r.region_name == "Anterior"), target_region)
    tri_reg = next((r for r in KNOWN_MUSCLE_REGIONS if "Triceps Brachii" in r.muscle_name and "Long" in r.region_name), target_region)

    # Use existing INCLINE tables if present, else approx
    sternal_ma = muscle_ma
    clav_ma = 4.3 if "45" in pos_key else 4.8
    delt_ma = 3.8
    tri_ma = 2.6

    atts = [
        MuscleAttachment(muscle_region=sternal_reg, joints_crossed=["shoulder"], moment_arms_at_position={"shoulder": sternal_ma}, notes="sternal (incline)"),
        MuscleAttachment(muscle_region=clav_reg, joints_crossed=["shoulder"], moment_arms_at_position={"shoulder": clav_ma}, notes="clavicular (higher on incline)"),
        MuscleAttachment(muscle_region=delt_reg, joints_crossed=["shoulder"], moment_arms_at_position={"shoulder": delt_ma}, notes="ant delt proxy"),
        MuscleAttachment(muscle_region=tri_reg, joints_crossed=["elbow"], moment_arms_at_position={"elbow": tri_ma}, notes="tri long elbow"),
    ]

    # order so target first if matches
    if target_region:
        for i, a in enumerate(atts):
            if a.muscle_region.muscle_name == target_region.muscle_name and a.muscle_region.region_name == target_region.region_name:
                atts = [a] + [x for j,x in enumerate(atts) if j!=i]
                break

    shoulder_load = INCLINE_SHOULDER_LOAD_MOMENT_ARMS.get(pos_key, 28.0)
    elbow_load = INCLINE_ELBOW_LOAD_MOMENT_ARMS.get(pos_key, 6.5)

    pose = Pose(
        name=f"{load_kg}kg Incline Bench @ {position}",
        joint_angles=JointAngles(values={"shoulder": 75.0 if "30" in variation else 85.0, "elbow": 70.0}),
        external_load=ExternalLoad(mass_kg=load_kg, load_type="barbell"),
        active_attachments=atts,
        load_moment_arms={"shoulder": shoulder_load, "elbow": elbow_load},
        notes=f"Incline ({variation}) multi-mover for % dom (clav % rises vs flat). {ma_source}",
    )

    seen = set()
    trs = []
    for a in atts:
        k = (a.muscle_region.muscle_name, a.muscle_region.region_name)
        if k not in seen:
            seen.add(k)
            trs.append(a.muscle_region)
    return AnalyzedPosition(pose=pose, target_regions=trs)


def build_romanian_deadlift_analyzed_position(
    load_kg: float = 120.0,
    position: str = "bottom",
    variation: str = "rdl",
    target_region_name: str = "Hamstrings",
    femur_cm: Optional[float] = None,
    tibia_cm: Optional[float] = None,
    use_geometric: Optional[bool] = None,
) -> AnalyzedPosition:
    """
    Builder for Romanian Deadlift (RDL) — now multi (ham + glute + erector) for % dominance.
    Hip hinge emphasis; less quad than squat/DL conv.
    """
    kwargs = _normalize_anthro_kwargs(locals().copy())
    load_kg = _normalize_load(load_kg, locals().copy())

    pos_key = {
        "bottom": "rdl_bottom",
        "mid": "rdl_mid",
        "top": "rdl_top",
    }.get(position, "rdl_bottom")

    target_region = _resolve_target_region(target_region_name, lift_hint="romanian") or next(
        (r for r in KNOWN_MUSCLE_REGIONS if "Biceps Femoris" in r.muscle_name or "Hamstring" in r.muscle_name), None
    )

    # Build 3 for RDL: ham (primary hip), glute, erector lumbar
    ham_att = get_default_hamstring_attachment(pos_key)
    g_att = get_default_glute_max_attachment(pos_key)
    e_att = get_default_erector_attachment(pos_key)

    # Geo for ham/glute proxy if asked
    if use_geometric is not False:
        anth = UserAnthropometry(name="RDL", femur_length_cm=femur_cm or 42.0, tibia_length_cm=tibia_cm or 38.0)
        geo = get_default_reference().estimate_moment_arm("deadlift", "glute_max", anthro=anth, position=pos_key)
        if geo:
            g_att = MuscleAttachment(muscle_region=g_att.muscle_region, joints_crossed=["hip"], moment_arms_at_position={"hip": geo}, notes="geo RDL glute")

    active = [ham_att, g_att, e_att]
    if target_region:
        for i, a in enumerate(active):
            if a.muscle_region.muscle_name == target_region.muscle_name and a.muscle_region.region_name == target_region.region_name:
                active = [a] + [x for j,x in enumerate(active) if j != i]
                break

    # Per joint load (RDL tables)
    hip_l = RDL_HIP_LOAD_MOMENT_ARMS.get(pos_key, 19.0)
    lum_l = RDL_LUMBAR_LOAD_MOMENT_ARMS.get(pos_key, 15.0)

    # Angles + lumbar for erector validate
    angles = {"hip": 95.0, "knee": 20.0, "lumbar": 25.0}
    if "top" in pos_key:
        angles = {"hip": 70.0, "knee": 10.0, "lumbar": 8.0}

    pose = Pose(
        name=f"{load_kg}kg RDL @ {position}",
        joint_angles=JointAngles(values=angles),
        external_load=ExternalLoad(mass_kg=load_kg, load_type="barbell"),
        active_attachments=active,
        load_moment_arms={"hip": hip_l, "lumbar": lum_l},
        notes="RDL multi (ham/glute/erect) for %; hip hinge, high ham demand vs conv DL.",
    )

    seen = set()
    trs = []
    for a in active:
        k = (a.muscle_region.muscle_name, a.muscle_region.region_name)
        if k not in seen:
            seen.add(k)
            trs.append(a.muscle_region)
    return AnalyzedPosition(pose=pose, target_regions=trs)
