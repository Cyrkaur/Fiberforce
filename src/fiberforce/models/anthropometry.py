from __future__ import annotations

"""Models for user anthropometric (body measurement) data.

This module is intentionally detailed because accurate personalized
biomechanical modeling depends heavily on good anthropometric input.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BodySegment:
    """A rigid body segment, usually corresponding to a long bone or combination of bones."""
    name: str
    length_cm: float
    notes: str = ""


@dataclass
class JointCenter:
    """Approximate location of a joint center relative to other landmarks."""
    name: str
    description: str = ""


@dataclass
class UserAnthropometry:
    """
    Detailed personal body measurements for biomechanical calculations.

    All linear measurements are stored internally in centimeters (for calculation precision).
    Use UserAnthropometry.from_inches(...) for US customary inputs (inches).
    Outputs and displays can be converted to inches/lbs via to_imperial_dict() and helpers.

    Angles are in degrees.

    This class is designed to be as complete as the user is willing to measure.
    Missing values should be handled gracefully in the calculation layer.
    """

    # --- Identification & Metadata ---
    id: Optional[str] = None
    name: Optional[str] = None
    measurement_date: Optional[str] = None
    notes: str = ""

    # --- Upper Extremity ---
    # Arm
    humerus_length_cm: Optional[float] = None          # Shoulder to elbow
    forearm_length_cm: Optional[float] = None          # Elbow to wrist (ulna/radius approx)
    hand_length_cm: Optional[float] = None             # Wrist to middle finger tip

    # Shoulder girdle
    biacromial_width_cm: Optional[float] = None        # Distance between acromia
    clavicle_length_cm: Optional[float] = None

    # Torso reference for pressing
    torso_depth_at_chest_cm: Optional[float] = None    # Anterior-posterior depth
    sternum_length_cm: Optional[float] = None          # Jugular notch to xiphoid

    # --- Lower Extremity (for squat/deadlift work) ---
    femur_length_cm: Optional[float] = None            # Hip to knee
    tibia_length_cm: Optional[float] = None            # Knee to ankle
    foot_length_cm: Optional[float] = None

    # Pelvis / hip reference
    biiliac_width_cm: Optional[float] = None           # Hip bone width
    leg_length_cm: Optional[float] = None              # Greater trochanter to floor (standing)

    # --- Advanced / Muscle Architecture Parameters ---
    # These are more advanced and can be populated per muscle region.
    # Key: region identifier (e.g. "pectoralis_major_sternal")
    muscle_architecture: dict[str, dict[str, float]] = field(default_factory=dict)

    # Example entry:
    # "pectoralis_major_sternal": {
    #     "pcsa_cm2": 28.5,
    #     "pennation_angle_deg": 18.0,
    #     "optimal_fiber_length_cm": 11.2,
    #     "tendon_slack_length_cm": 4.8,
    # }

    def get_upper_arm_length(self) -> Optional[float]:
        return self.humerus_length_cm

    def get_forearm_length(self) -> Optional[float]:
        return self.forearm_length_cm

    def has_basic_upper_body_measurements(self) -> bool:
        """Minimum required for basic upper body pressing calculations."""
        return (
            self.humerus_length_cm is not None and
            self.forearm_length_cm is not None and
            self.biacromial_width_cm is not None
        )

    def has_basic_lower_body_measurements(self) -> bool:
        """Minimum required for basic lower body calculations."""
        return (
            self.femur_length_cm is not None and
            self.tibia_length_cm is not None
        )

    # --- v1 Imperial support (inches, ft, lbs) ---
    @classmethod
    def from_inches(
        cls,
        name: Optional[str] = None,
        humerus_in: Optional[float] = None,
        forearm_in: Optional[float] = None,
        hand_in: Optional[float] = None,
        biacromial_in: Optional[float] = None,
        clavicle_in: Optional[float] = None,
        torso_depth_in: Optional[float] = None,
        sternum_in: Optional[float] = None,
        femur_in: Optional[float] = None,
        tibia_in: Optional[float] = None,
        foot_in: Optional[float] = None,
        biiliac_in: Optional[float] = None,
        leg_in: Optional[float] = None,
        **kwargs,
    ) -> "UserAnthropometry":
        """Create anthropometry using inches (US customary) instead of cm.

        All _in params are converted to _cm internally.
        """
        from fiberforce.calculations.utils import inches_to_cm
        return cls(
            name=name,
            humerus_length_cm=inches_to_cm(humerus_in) if humerus_in is not None else None,
            forearm_length_cm=inches_to_cm(forearm_in) if forearm_in is not None else None,
            hand_length_cm=inches_to_cm(hand_in) if hand_in is not None else None,
            biacromial_width_cm=inches_to_cm(biacromial_in) if biacromial_in is not None else None,
            clavicle_length_cm=inches_to_cm(clavicle_in) if clavicle_in is not None else None,
            torso_depth_at_chest_cm=inches_to_cm(torso_depth_in) if torso_depth_in is not None else None,
            sternum_length_cm=inches_to_cm(sternum_in) if sternum_in is not None else None,
            femur_length_cm=inches_to_cm(femur_in) if femur_in is not None else None,
            tibia_length_cm=inches_to_cm(tibia_in) if tibia_in is not None else None,
            foot_length_cm=inches_to_cm(foot_in) if foot_in is not None else None,
            biiliac_width_cm=inches_to_cm(biiliac_in) if biiliac_in is not None else None,
            leg_length_cm=inches_to_cm(leg_in) if leg_in is not None else None,
            **kwargs,
        )

    def to_imperial_dict(self) -> dict:
        """Return a dict of key measurements converted to inches (for display/reports)."""
        from fiberforce.calculations.utils import cm_to_inches
        return {
            "humerus_in": cm_to_inches(self.humerus_length_cm) if self.humerus_length_cm else None,
            "forearm_in": cm_to_inches(self.forearm_length_cm) if self.forearm_length_cm else None,
            "biacromial_in": cm_to_inches(self.biacromial_width_cm) if self.biacromial_width_cm else None,
            "torso_depth_in": cm_to_inches(self.torso_depth_at_chest_cm) if self.torso_depth_at_chest_cm else None,
            "femur_in": cm_to_inches(self.femur_length_cm) if self.femur_length_cm else None,
            "tibia_in": cm_to_inches(self.tibia_length_cm) if self.tibia_length_cm else None,
            "biiliac_in": cm_to_inches(self.biiliac_width_cm) if self.biiliac_width_cm else None,
        }