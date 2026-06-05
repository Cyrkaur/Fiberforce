"""
Utility functions for biomechanical calculations.

These are small, focused helpers that can be used across different
calculators and models.
"""

from fiberforce.models import ExternalLoad

# =============================================================================
# Unit conversion helpers (for v1 US customary support)
# Internal calculations stay in metric (kg, cm, N, Nm) for precision.
# All conversions are approximate but sufficient for this prototype.
# =============================================================================

LBS_TO_KG = 0.45359237
INCH_TO_CM = 2.54
FT_TO_M = 0.3048
NM_TO_FTLB = 0.737562149277

def lbs_to_kg(lbs: float) -> float:
    return round(lbs * LBS_TO_KG, 4)

def kg_to_lbs(kg: float) -> float:
    return round(kg / LBS_TO_KG, 2)

def inches_to_cm(inches: float) -> float:
    return round(inches * INCH_TO_CM, 2)

def cm_to_inches(cm: float) -> float:
    return round(cm / INCH_TO_CM, 2)

def ft_to_m(ft: float) -> float:
    return round(ft * FT_TO_M, 4)

def nm_to_ftlb(nm: float) -> float:
    """Convert Newton-meters to foot-pounds (torque)."""
    return round(nm * NM_TO_FTLB, 2)

def ftlb_to_nm(ftlb: float) -> float:
    return round(ftlb / NM_TO_FTLB, 2)

def load_lbs_to_kg(lbs: float) -> float:
    """Convert load in lbs to kg (for ExternalLoad.mass_kg)."""
    return lbs_to_kg(lbs)


def estimate_joint_torque_from_load(
    external_load: ExternalLoad,
    load_moment_arm_cm: float,
) -> float:
    """
    Estimate the torque (N·m) produced by an external load about a joint.

    Args:
        external_load: The external load being moved.
        load_moment_arm_cm: Perpendicular distance (cm) from the joint
                            to the line of action of the load at the
                            position of interest.

    Returns:
        Torque in Newton-meters.
    """
    if external_load is None or external_load.mass_kg <= 0:
        return 0.0

    g = 9.81  # m/s²
    force_n = external_load.mass_kg * g
    moment_arm_m = load_moment_arm_cm / 100.0

    return round(force_n * moment_arm_m, 2)


def gravity_force(mass_kg: float) -> float:
    """Return the force due to gravity in Newtons."""
    return round(mass_kg * 9.81, 2)