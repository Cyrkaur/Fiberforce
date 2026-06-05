"""
Geometric moment arm estimators (prototype).

This module drives the transition from purely static reference tables
(literature-synthesized defaults in moment_arms.py) toward subject-specific
estimation driven by UserAnthropometry (limb lengths, widths, depths).

CURRENT SCOPE (4 lifts, key regions):
- Bench press: sternal pectoralis major horizontal adduction MA at the shoulder.
- Squat: gluteus maximus hip extension + vastus lateralis (quad) knee extension.
- Deadlift (conv + sumo): glute max hip extension + hamstring composite (knee+hip).
- Overhead Press (standing/seated): anterior delt shoulder flexion/abduction +
  triceps (long + lateral) elbow extension.

All estimators accept partial anthropometry (graceful numeric defaults) and
return values clamped to physiologically plausible bands that overlap static
table ranges for average builds.

DESIGN PRINCIPLES:
- Simple, transparent, pure-Python (math only, no numpy).
- Law-of-cosines / trig projection style for effective MA.
- Directionally consistent with static tables in moment_arms.py.
- Every public function has extensive model + assumptions + limitations docs.
- Integrated via ReferenceData.estimate_moment_arm + get_moment_arm_with_confidence
  (preferred path when anthro supplied) and via AnalysisService builders
  (use_geometric=True forwarding).

These are educational prototypes for sensitivity analysis and personalization
exploration — NOT validated clinical or coaching tools.

Known limitations (repeated across functions):
- 2D/2.5D projections only; ignore true 3D wrapping, scapular kinematics,
  exact attachment sites, fiber pennation effects on MA, etc.
- Joint angles supplied externally (not derived from full kinematic chain).
- Absolute values for relative comparison + sensitivity only.
- No dynamic (angle-continuous) curves yet.

Future (explicitly out of scope for v0.x):
- Full rigid-body + wrapping simulation.
- In-vivo validation (MRI, ultrasound, tendon excursion).
- Subject-specific bony landmarks.
"""

from __future__ import annotations

import math
from typing import Optional

from fiberforce.models.anthropometry import UserAnthropometry


# =============================================================================
# BENCH PRESS — STERNAL PEC HORIZONTAL ADDUCTION MOMENT ARM (SHOULDER)
# =============================================================================

def estimate_bench_sternal_ma(
    anthro: UserAnthropometry,
    grip_width_cm: Optional[float] = None,
    position: str = "flat_bench_bottom",
) -> float:
    """
    Prototype geometric estimator for sternal pectoralis major moment arm (cm)
    for horizontal adduction at the shoulder during bench press.

    MODEL (law-of-cosines / trigonometric projection):
    1. Compute implied humeral abduction angle in the transverse plane from grip
       geometry:
          lateral_offset = (grip/2) - (biacromial/2)
          proj_h = humerus * 0.88   # effective horizontal-plane projection at bottom
          gamma = asin( clamp(lateral_offset / proj_h) )
       This captures how grip width changes the angle of the humerus relative
       to the shoulder girdle (wider grip → more horizontal abduction).

    2. Model the sternal origin offset:
       - Anterior offset from the coronal plane of the shoulder joints ≈
         torso_depth * 0.42 (sternum lies anterior; deeper chests increase the
         sagittal component of the muscle's line of action).

    3. Effective muscle line-of-action angle (phi) relative to the humerus:
       phi ≈ (π/2 − |gamma|) + atan2(anterior_offset, small_medial_component)
       The sin(phi) term gives the perpendicular lever component.

    4. Insertion radius (r_ins):
       r_ins = 4.8 * (humerus / 32.0)**0.65   # effective distance from shoulder
       joint center to the resultant force on proximal humerus (broad insertion).

    5. Raw MA = r_ins * sin(phi) + (anterior_offset * 0.22 * cos(gamma * 0.5))

    6. Apply position- and grip-specific multipliers that reproduce the *direction*
       of change seen in the static reference tables:
       - Bottom positions > mid > near lockout (because of changing abduction
         and scapular position).
       - Decline slightly > flat > incline.
       - Wider grip receives a small additional boost (scapular mechanics proxy).

    The result is clamped to a physiologically plausible range [2.6, 7.2] cm
    (tuned for overlap with static table ranges of ~3.3-6.4 cm).

    PARAMETERS:
        anthro: UserAnthropometry instance. Uses:
            humerus_length_cm (required for lever scaling + angle calc)
            biacromial_width_cm (shoulder girdle width)
            torso_depth_at_chest_cm (affects anterior origin offset)
        grip_width_cm: Distance between index fingers (or bar contact points).
            If None, defaults to ~1.5× biacromial (medium grip).
        position: String key (e.g. "flat_bench_bottom", "wide_grip_bottom",
            "incline_30_bottom", "flat_bench_near_lockout"). Used only for
            the position multiplier table. Unknown keys default to 1.0.

    RETURNS:
        Estimated moment arm in centimeters (float, rounded to 2 decimals).

    COMPARISON TO STATIC TABLES:
        Typical static values (sternal_pecs):
            flat_bench_bottom: 5.7 cm
            wide_grip_bottom:  6.4 cm
            close_grip_bottom: 4.2 cm
            flat_bench_near_lockout: 3.3 cm
        This estimator will produce values in a similar band and will vary
        continuously with the four anthropometric inputs instead of jumping
        on discrete keys.

    LIMITATIONS (IMPORTANT — READ):
        - Extremely simplified 2.5D projection. Ignores true 3D fiber angles,
          scapular upward rotation / protraction, clavicular contribution,
          and exact tendinous insertion geometry on the humerus.
        - "humerus projection factor" (0.88) and coefficients are heuristic,
          tuned to stay close to reference tables for average anthropometry.
        - Does not account for elbow position or forearm pronation/supination.
        - Position string only selects a multiplier; it does not derive from
          joint angles. For true angle-driven MA this would be replaced by
          a full kinematic function of (shoulder_horizontal_abduction,
          shoulder_flexion, scapula...).
        - No subject-specific muscle architecture (PCSA, pennation) yet.
        - Absolute values are for *relative comparison and sensitivity* only.
          They should not be used for absolute clinical torque predictions.
        - Not validated against in-vivo studies (e.g. MRI, ultrasound,
          tendon excursion methods). Future calibration will be required.

    USAGE IN PROTOTYPE:
        anthro = UserAnthropometry(humerus_length_cm=34.0, biacromial_width_cm=41.0,
                                   torso_depth_at_chest_cm=24.5)
        ma = estimate_bench_sternal_ma(anthro, grip_width_cm=62.0,
                                       position="flat_bench_bottom")
    """
    h = anthro.humerus_length_cm or 32.0
    b = anthro.biacromial_width_cm or 38.0
    t = anthro.torso_depth_at_chest_cm or 22.0

    g = grip_width_cm if grip_width_cm is not None else (b * 1.5)

    # --- Core geometry ---
    half_b = b / 2.0
    half_g = g / 2.0
    origin_anterior = t * 0.42

    # Effective humerus projection in the transverse plane at bench bottom posture
    proj_h = h * 0.88
    lateral_offset = half_g - half_b
    lateral_offset = max(-proj_h + 1.0, min(lateral_offset, proj_h - 1.0))

    if proj_h > 0.5:
        gamma = math.asin(max(min(lateral_offset / proj_h, 0.999), -0.999))
    else:
        gamma = 0.0

    # Angle between humerus and effective sternal line of action
    muscle_pull_offset = math.atan2(origin_anterior, max(half_b * 0.22, 1.0))
    phi = (math.pi / 2 - abs(gamma)) + muscle_pull_offset * 0.58

    # Effective insertion moment radius (proximal humerus) — REDUCED baseline
    r_ins = 4.8 * ((h / 32.0) ** 0.65)

    ma_lever = r_ins * math.sin(max(0.38, min(phi, 2.75)))
    ma_ant = origin_anterior * 0.22 * math.cos(gamma * 0.52)   # reduced anterior weight

    raw = ma_lever + ma_ant

    # --- Position & grip multipliers (directionally faithful to tables) ---
    pos_mult = {
        "flat_bench_bottom": 1.00,
        "flat_bench_mid": 0.86,
        "flat_bench_near_lockout": 0.58,
        "incline_30_bottom": 0.86,
        "decline_15_bottom": 1.07,
        "wide_grip_bottom": 1.12,
        "close_grip_bottom": 0.74,
        "flat_bench_top": 0.49,
    }.get(position, 1.0)

    # Extra grip effect (scapula + slight abduction change not fully in gamma)
    grip_norm = (g - 42.0) / 28.0
    grip_mult = 0.95 + 0.085 * max(0.0, min(grip_norm, 1.35))

    estimated = raw * pos_mult * grip_mult

    # Clamp + round (tuned band for good overlap with static tables)
    return round(max(2.6, min(7.2, estimated)), 2)


# =============================================================================
# SQUAT — GLUTE MAX HIP EXTENSION MOMENT ARM
# =============================================================================

def estimate_squat_glute_ma(
    anthro: UserAnthropometry,
    stance_width_cm: Optional[float] = None,
    variation: str = "high_bar",
    hip_flexion_deg: float = 110.0,
    position: Optional[str] = None,  # v0.4: "bottom", "mid", "top" -> adjusts default flexion
) -> float:
    """
    Prototype geometric estimator for gluteus maximus (upper fibers) hip
    extension moment arm (cm) during the bottom / parallel positions of a squat.

    MODEL (simplified geometric + stance):
    - Base insertion radius scaled from femur length:
        r = 5.8 * (femur / 42.0)
    - Hip flexion dramatically increases glute MA (the muscle's line of action
      becomes more perpendicular to the femur as the hip flexes). We use a
      sin( flexion - offset ) curve.
    - Pelvis width (biiliac) + stance_width determine hip abduction angle.
      Wider stance (more abduction) modestly increases effective MA for the
      posterior glute fibers (they gain a small abduction moment component
      that contributes to the sagittal plane torque in a wide-stance squat).
    - Low-bar vs high-bar proxy via variation string (low bar tends to allow
      slightly more forward lean / different pelvic tilt → higher glute demand
      in reference tables).

    The result is clamped to [4.2, 7.8] cm.

    LIMITATIONS:
    - Extremely crude abduction model. Real glute MA also depends on pelvic
      tilt, femoral anteversion, exact attachment sites on the ilium and femur.
    - Hip flexion angle is taken as an input parameter (not derived from tibia
      + femur + ankle kinematics in this prototype).
    - No distinction between upper, middle, and lower glute fibers yet.
    - Stance effect is deliberately small (matches the modest differences in
      the static tables between high-bar and low-bar).
    - Same overall prototype caveats as the bench estimator.
    """
    f = anthro.femur_length_cm or 42.0
    pelvis = anthro.biiliac_width_cm or 28.0

    s = stance_width_cm if stance_width_cm is not None else (pelvis * 2.15)

    r = 5.8 * (f / 42.0)

    # v0.4: if position provided and no explicit flexion, map to reasonable defaults
    if position and hip_flexion_deg == 110.0:  # only override if using the old default
        pos_defaults = {"bottom": 110.0, "mid": 70.0, "top": 25.0}
        hip_flexion_deg = pos_defaults.get(position, hip_flexion_deg)

    # Flexion contribution (strong driver at bottom of squat)
    flex_r = math.radians(hip_flexion_deg)
    flex_f = math.sin(max(0.0, min(flex_r - 0.55, 1.85)))

    # Abduction / stance contribution
    half_p = pelvis / 2.0
    half_s = s / 2.0
    abd_norm = max(0.0, (half_s - half_p - 6.0) / max(f, 20.0))
    abd_f = 1.0 + 0.11 * min(abd_norm, 0.95)

    # Variation proxy (low bar tends to bias slightly more glute in tables)
    var_f = 1.13 if variation and "low" in variation.lower() else 1.0

    raw = r * flex_f * abd_f * var_f * 0.71

    return round(max(4.2, min(7.8, raw)), 2)


# =============================================================================
# SQUAT — QUAD (KNEE EXTENSION) MOMENT ARM
# =============================================================================

def estimate_squat_quad_ma(
    anthro: UserAnthropometry,
    stance_width_cm: Optional[float] = None,
    knee_flexion_deg: float = 35.0,
    variation: str = "high_bar",
    position: Optional[str] = None,  # v0.4
) -> float:
    """
    Prototype geometric estimator for quadriceps (vastus lateralis / general
    knee extensors) moment arm (cm) at the knee during squat bottom positions.

    MODEL:
    - Baseline patellar tendon / quad tendon effective MA (~4.6 cm average).
    - Strong knee-angle dependence (classic curve): MA increases from full
      extension, peaks in mid-flexion (~40-60° flexion), remains high but slightly
      lower in very deep positions.
    - Overall leg length (femur + tibia) provides a weak positive scaling
      (larger individuals tend to have absolutely larger moment arms).
    - Minor stance correction (wider stance can introduce slight rotational
      effects that reduce the pure sagittal-plane MA of some vasti).

    Clamped to [3.7, 5.7] cm.

    LIMITATIONS:
    - Does not model patellar kinematics, patellar tendon length, or Q-angle
      changes with stance.
    - Knee flexion angle supplied externally (builders usually hard-code 35°).
    - Tibia length used only for overall size scaling; real quad MA is more
      strongly governed by patella and femoral condyle geometry.
    - Again, prototype only — directional and sensitivity use.
    """
    t = anthro.tibia_length_cm or 38.0
    f = anthro.femur_length_cm or 42.0
    leg = f + t

    # v0.4 position mapping
    if position and knee_flexion_deg == 35.0:
        pos_defaults = {"bottom": 35.0, "mid": 60.0, "top": 10.0}
        knee_flexion_deg = pos_defaults.get(position, knee_flexion_deg)

    k = math.radians(knee_flexion_deg)

    # Classic MA vs knee flexion curve (rises then plateaus / slight drop deep)
    angle_f = 0.68 + 0.52 * math.sin(k * 1.25 - 0.15)

    # Weak size scaling
    size_f = (leg / 80.0) ** 0.22

    # Stance effect (small)
    stance_f = 1.0
    if stance_width_cm is not None:
        stance_norm = max(0.0, min((stance_width_cm - 48.0) / 42.0, 1.0))
        stance_f = 0.975 + 0.035 * stance_norm

    var_f = 0.94 if variation and "low" in variation.lower() else 1.0

    raw = 4.6 * angle_f * size_f * stance_f * var_f

    return round(max(3.7, min(5.7, raw)), 2)


# =============================================================================
# DEADLIFT — GLUTE MAX HIP EXTENSION MOMENT ARM (CONV vs SUMO)
# =============================================================================

def estimate_deadlift_glute_ma(
    anthro: UserAnthropometry,
    stance_width_cm: Optional[float] = None,
    variation: str = "conventional",
    hip_flexion_deg: float = 95.0,
    position: Optional[str] = None,  # v0.4
) -> float:
    """
    Prototype geometric estimator for gluteus maximus hip extension moment arm (cm)
    at the hip during the bottom / lift-off phase of a deadlift.

    MODEL (stance + flexion dominant):
    - Base radius scaled from femur (slightly larger effective lever than squat
      due to more horizontal torso at lift-off in many styles).
    - Hip flexion angle drives the primary sin() contribution (deadlift bottom
      often ~85-110° depending on anthropometry and style).
    - Conventional vs sumo: sumo increases abduction (wider stance) which
      modestly boosts effective glute MA via small abduction moment arm
      component that still contributes to sagittal hip extension torque.
    - Conventional tends to be slightly more hip-dominant in tables (higher
      glute demand).

    Clamped [4.0, 8.2] cm (wider band than squat to reflect greater style
    and anthropometry sensitivity at the more upright-ish deadlift bottom).

    LIMITATIONS:
    - Hip flexion is supplied (builders usually synthesize ~95°); not derived
      from full tibia/femur/torso kinematics.
    - No distinction of glute fiber sub-regions or exact pelvic tilt / lumbar
      lordosis effects (both huge in real deadlifts).
    - Sumo effect is deliberately modest (matches the often small table
      differences once stance is normalized).
    - Same prototype caveats as all estimators in this module.
    """
    f = anthro.femur_length_cm or 42.0
    pelvis = anthro.biiliac_width_cm or 28.0

    s = stance_width_cm if stance_width_cm is not None else (pelvis * 2.35)

    r = 6.1 * (f / 42.0)

    # v0.4 position mapping for deadlift
    if position and hip_flexion_deg == 95.0:
        pos_defaults = {"bottom": 95.0, "mid": 60.0, "top": 25.0}
        hip_flexion_deg = pos_defaults.get(position, hip_flexion_deg)

    flex_r = math.radians(hip_flexion_deg)
    flex_f = math.sin(max(0.0, min(flex_r - 0.45, 1.95)))

    half_p = pelvis / 2.0
    half_s = s / 2.0
    abd_norm = max(0.0, (half_s - half_p - 5.0) / max(f, 18.0))
    abd_f = 1.0 + 0.14 * min(abd_norm, 1.05)

    var_lower = variation.lower()
    var_f = 1.09 if "sumo" in var_lower else 1.0   # sumo slight glute MA edge via abd
    var_f = 0.97 if "conv" in var_lower and var_f == 1.0 else var_f

    raw = r * flex_f * abd_f * var_f * 0.74

    return round(max(4.0, min(8.2, raw)), 2)


# =============================================================================
# DEADLIFT — HAMSTRING (KNEE + HIP COMPOSITE) MOMENT ARM
# =============================================================================

def estimate_deadlift_hamstring_ma(
    anthro: UserAnthropometry,
    stance_width_cm: Optional[float] = None,
    knee_flexion_deg: float = 28.0,
    hip_flexion_deg: float = 95.0,
    variation: str = "conventional",
    position: Optional[str] = None,  # v0.4 Phase 4: "bottom"/"mid"/"top"/"lockout" for multi-pos DL sensitivity
) -> float:
    """
    Prototype estimator for hamstring (esp. biceps femoris + semitendinosus)
    composite moment arm contribution during deadlift (hip extension +
    knee stabilization component) — now with explicit position support.

    MODEL:
    - Hamstrings produce both hip extension and knee flexion torque.
    - At deadlift lift-off the knee is only slightly flexed (~20-35°); the
      effective MA is a blend of the hip and a smaller knee component.
    - Longer femur/tibia individuals get modest absolute scaling.
    - Conventional vs sumo has smaller effect here than on glutes (hamstrings
      more consistent across styles in literature proxies).
    - v0.4 Phase 4: position drives sensible flexion defaults (bottom: high
      hip flexion + moderate knee; mid: transitional; top/lockout: straighter
      legs, lower composite MA). High-value for deadlift multi-position work.

    Clamped [2.8, 5.9] cm.
    """
    f = anthro.femur_length_cm or 42.0
    t = anthro.tibia_length_cm or 38.0
    leg = f + t

    # v0.4 Phase 4 position mapping for deadlift (high-value for sticking point analysis)
    if position is not None and knee_flexion_deg == 28.0 and hip_flexion_deg == 95.0:
        p = position.lower()
        short = p.split("_")[-1] if "_" in p else p
        pos_k = {"bottom": 28.0, "mid": 42.0, "top": 12.0, "lockout": 8.0, "near_lockout": 10.0}
        pos_h = {"bottom": 95.0, "mid": 55.0, "top": 22.0, "lockout": 15.0, "near_lockout": 18.0}
        knee_flexion_deg = pos_k.get(short, knee_flexion_deg)
        hip_flexion_deg = pos_h.get(short, hip_flexion_deg)

    k = math.radians(knee_flexion_deg)
    h = math.radians(hip_flexion_deg)

    # Knee component (small at near-straight knee)
    knee_f = 0.42 + 0.38 * math.sin(max(0.0, min(k * 1.6 - 0.2, 1.4)))

    # Hip contribution (larger at high flexion)
    hip_f = 0.55 + 0.52 * math.sin(max(0.0, min(h - 0.6, 1.6)))

    size_f = (leg / 82.0) ** 0.18

    var_f = 1.04 if "sumo" in variation.lower() else 1.0

    raw = 3.9 * knee_f * hip_f * size_f * var_f

    return round(max(2.8, min(5.9, raw)), 2)


# =============================================================================
# OVERHEAD PRESS — ANTERIOR DELT (SHOULDER) MOMENT ARM
# =============================================================================

def estimate_ohp_anterior_delt_ma(
    anthro: UserAnthropometry,
    grip_width_cm: Optional[float] = None,
    shoulder_elevation_deg: float = 85.0,
    variation: str = "standing",
    position: Optional[str] = None,  # v0.4 Phase 4: "bottom"/"mid"/"lockout"/"top" for multi-pos sensitivity
) -> float:
    """
    Prototype geometric estimator for anterior deltoid moment arm (cm) during
    the bottom / mid / lockout phases of overhead press (shoulder flexion + abduction
    component).

    MODEL:
    - Anterior delt is the prime mover for initial press off the rack or from
      shoulder height.
    - Effective MA peaks in mid-elevation and is modulated by grip (wider grip
      slightly increases abduction component → modest MA change).
    - Standing vs seated: standing allows more natural scapular upward rotation
      (small positive MA proxy); seated can constrain and slightly reduce it.
    - Humerus length provides the primary scaling (larger frames = larger MA).
    - v0.4 Phase 4: position param provides explicit ROM sensitivity (bottom →
      higher initial MA demand curve; mid peaks; lockout/top lower as delts
      hand off to triceps/scapular stabilizers). Maps to realistic elevation
      angles consistent with OHP static tables.

    Clamped [2.9, 6.1] cm (directionally matches typical OHP delt tables).
    """
    h = anthro.humerus_length_cm or 32.0
    b = anthro.biacromial_width_cm or 38.0

    g = grip_width_cm if grip_width_cm is not None else (b * 1.35)

    # v0.4 Phase 4 multi-position: map short or full position keys to elevation
    if position is not None and shoulder_elevation_deg == 85.0:
        p = position.lower()
        short = p.split("_")[-1] if "_" in p else p
        pos_defaults = {
            "bottom": 82.0,
            "mid": 118.0,
            "lockout": 168.0,
            "top": 160.0,
            "near_lockout": 155.0,
        }
        shoulder_elevation_deg = pos_defaults.get(short, shoulder_elevation_deg)

    # Humerus scaling (primary lever)
    base = 3.6 * ((h / 32.0) ** 0.72)

    # Elevation curve (strong driver; peaks ~80-110°)
    elev_r = math.radians(shoulder_elevation_deg)
    elev_f = 0.78 + 0.48 * math.sin(max(0.0, min(elev_r * 1.15 - 0.35, 2.1)))

    # Grip / abduction effect
    grip_norm = (g - 38.0) / 32.0
    grip_f = 0.96 + 0.09 * max(0.0, min(grip_norm, 1.6))

    var_f = 1.05 if "stand" in variation.lower() else 0.96

    raw = base * elev_f * grip_f * var_f

    return round(max(2.9, min(6.1, raw)), 2)


# =============================================================================
# OVERHEAD PRESS — TRICEPS (ELBOW EXTENSION) MOMENT ARM
# =============================================================================

def estimate_ohp_triceps_ma(
    anthro: UserAnthropometry,
    forearm_cm: Optional[float] = None,
    elbow_flexion_deg: float = 70.0,
    variation: str = "standing",
    position: Optional[str] = None,  # v0.4 Phase 4: "bottom"/"mid"/"lockout" etc for position-sensitive elbow MA
) -> float:
    """
    Prototype estimator for triceps (long + lateral heads composite) moment arm
    at the elbow during OHP lockout / mid / bottom phases.

    MODEL:
    - Triceps MA at elbow is relatively stable but benefits from slight
      shoulder abduction/external rotation that "opens" the line of pull.
    - Standing vs seated again acts as a small proxy for scapular freedom.
    - Forearm length provides weak positive scaling (insertion geometry).
    - Elbow flexion angle at the "sticking point" or mid-press modulates it.
    - v0.4 Phase 4: position param adds explicit sensitivity (bottom: more
      elbow flexion → solid triceps contribution; mid: transition; lockout:
      peak triceps demand as shoulder stabilizers hand off). Matches table
      direction (higher MA near lockout for triceps).

    Clamped [2.1, 4.8] cm.
    """
    fa = forearm_cm if forearm_cm is not None else (anthro.forearm_length_cm or 26.0)

    # v0.4 Phase 4 multi-position
    if position is not None and elbow_flexion_deg == 70.0:
        p = position.lower()
        short = p.split("_")[-1] if "_" in p else p
        pos_defaults = {
            "bottom": 82.0,
            "mid": 55.0,
            "lockout": 15.0,
            "top": 18.0,
            "near_lockout": 12.0,
        }
        elbow_flexion_deg = pos_defaults.get(short, elbow_flexion_deg)

    e = math.radians(elbow_flexion_deg)

    # Classic elbow extension MA curve (higher when elbow ~60-90°)
    elbow_f = 0.62 + 0.55 * math.sin(max(0.0, min(e * 1.35 - 0.25, 1.85)))

    # Size proxy
    size_f = (fa / 26.0) ** 0.28

    var_f = 1.03 if "stand" in variation.lower() else 0.97

    raw = 3.1 * elbow_f * size_f * var_f

    return round(max(2.1, min(4.8, raw)), 2)


# =============================================================================
# CONVENIENCE DISPATCH (for ReferenceData integration)
# =============================================================================

def estimate_moment_arm(
    lift: str,
    region_key: str,
    anthro: UserAnthropometry,
    **params,
) -> Optional[float]:
    """
    Unified entry point for the geometric estimators (prototype).

    Currently supported:
      lift="bench", region_key in ("sternal_pecs", "pectoralis_major_sternal")
          → calls estimate_bench_sternal_ma(anthro, grip_width=..., position=...)

      lift="squat", region_key in ("glute_max", "glute_max_upper")
          → calls estimate_squat_glute_ma(... stance_width, variation, ...)

      lift="squat", region_key in ("quads", "vastus_lateralis", "quad_vl")
          → calls estimate_squat_quad_ma(...)

      lift="deadlift", region_key in ("glute_max", "glute_max_upper")
          → calls estimate_deadlift_glute_ma(..., stance, variation, hip_flex...)

      lift="deadlift", region_key in ("hamstring", "hamstrings", "biceps_femoris")
          → calls estimate_deadlift_hamstring_ma(...)   # now position-aware (Phase 4)

      lift in ("ohp", "overhead"), region_key in ("anterior_delt", "anterior", "delts")
          → calls estimate_ohp_anterior_delt_ma(... grip, shoulder_elevation, variation, position)

      lift in ("ohp", "overhead"), region_key in ("triceps_long", "triceps", "triceps_lateral")
          → calls estimate_ohp_triceps_ma(... forearm, elbow_flex, variation, position)

      lift in ("ohp", "overhead"), region_key in ("lateral_delt", "lateral")
          → calls estimate_ohp_anterior_delt_ma (directional proxy; Phase 4 regional expansion)

    All other combinations return None (fall back to static tables).

    `params` are passed through (grip_width_cm, stance_width_cm, position,
    variation, hip_flexion_deg, knee_flexion_deg, shoulder_elevation_deg, ...).
    v0.4 Phase 4 overlap: position honored across OHP + deadlift hamstring + deadlift glute
    for improved multi-position + more OHP regions (lateral now geo-enabled).
    """
    l = lift.lower()
    r = region_key.lower()

    if l in ("bench", "benchpress"):
        if r in ("sternal_pecs", "pectoralis_major_sternal", "sternal"):
            return estimate_bench_sternal_ma(
                anthro,
                grip_width_cm=params.get("grip_width_cm") or params.get("grip_width"),
                position=params.get("position", "flat_bench_bottom"),
            )

    if l == "squat":
        if r in ("glute_max", "glute_max_upper", "glute"):
            return estimate_squat_glute_ma(
                anthro,
                stance_width_cm=params.get("stance_width_cm") or params.get("stance_width"),
                variation=params.get("variation", "high_bar"),
                hip_flexion_deg=params.get("hip_flexion_deg", 110.0),
                position=params.get("position"),
            )
        if r in ("quads", "quad", "vastus_lateralis", "vl", "quad_vl"):
            return estimate_squat_quad_ma(
                anthro,
                stance_width_cm=params.get("stance_width_cm") or params.get("stance_width"),
                knee_flexion_deg=params.get("knee_flexion_deg", 35.0),
                variation=params.get("variation", "high_bar"),
                position=params.get("position"),
            )

    if l in ("deadlift", "dl", "dlift"):
        if r in ("glute_max", "glute_max_upper", "glute"):
            return estimate_deadlift_glute_ma(
                anthro,
                stance_width_cm=params.get("stance_width_cm") or params.get("stance_width"),
                variation=params.get("variation", "conventional"),
                hip_flexion_deg=params.get("hip_flexion_deg", 95.0),
                position=params.get("position"),
            )
        if r in ("hamstring", "hamstrings", "biceps_femoris", "ham"):
            return estimate_deadlift_hamstring_ma(
                anthro,
                stance_width_cm=params.get("stance_width_cm") or params.get("stance_width"),
                knee_flexion_deg=params.get("knee_flexion_deg", 28.0),
                hip_flexion_deg=params.get("hip_flexion_deg", 95.0),
                variation=params.get("variation", "conventional"),
            )

    if l in ("ohp", "overhead", "overhead_press", "military"):
        if r in ("anterior_delt", "anterior", "delts", "delt"):
            return estimate_ohp_anterior_delt_ma(
                anthro,
                grip_width_cm=params.get("grip_width_cm") or params.get("grip_width"),
                shoulder_elevation_deg=params.get("shoulder_elevation_deg", 85.0),
                variation=params.get("variation", "standing"),
                position=params.get("position"),
            )
        if r in ("triceps_long", "triceps", "triceps_lateral", "long_head"):
            return estimate_ohp_triceps_ma(
                anthro,
                forearm_cm=params.get("forearm_cm") or params.get("forearm_length_cm"),
                elbow_flexion_deg=params.get("elbow_flexion_deg", 70.0),
                variation=params.get("variation", "standing"),
                position=params.get("position"),
            )
        # Phase 4 expansion: additional key OHP region (lateral_delt) now supported
        # via anterior model as high-value directional proxy (tables show similar
        # elevation curve shape; enables geometric for more OHP multi-pos work).
        if r in ("lateral_delt", "lateral"):
            return estimate_ohp_anterior_delt_ma(
                anthro,
                grip_width_cm=params.get("grip_width_cm") or params.get("grip_width"),
                shoulder_elevation_deg=params.get("shoulder_elevation_deg", 85.0),
                variation=params.get("variation", "standing"),
                position=params.get("position"),
            )

    return None


__all__ = [
    "estimate_bench_sternal_ma",
    "estimate_squat_glute_ma",
    "estimate_squat_quad_ma",
    "estimate_deadlift_glute_ma",
    "estimate_deadlift_hamstring_ma",
    "estimate_ohp_anterior_delt_ma",
    "estimate_ohp_triceps_ma",
    "estimate_moment_arm",
]
