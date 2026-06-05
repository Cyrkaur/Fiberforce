"""
Domain models for FiberForce.

These models form the foundation of the personalized biomechanical
modeling system. We are intentionally building these with significant
depth because the project aims to go beyond generic fitness tools.
"""

from .anthropometry import UserAnthropometry, BodySegment
from .muscle import (
    MuscleRegion,
    MuscleArchitecture,
    Muscle,
    MuscleAttachment,
    MuscleForceResult,
    KNOWN_MUSCLE_REGIONS,
)
from .lift import JointAngles, LiftConfiguration, ExternalLoad, PrimaryLift, PRIMARY_LIFTS
from .biomechanics import MomentArm, Force, Torque, Lever, Joint
from .pose import Pose, AnalyzedPosition
from .subject import Subject

__all__ = [
    # Anthropometry
    "UserAnthropometry",
    "BodySegment",
    # Muscle
    "MuscleRegion",
    "MuscleArchitecture",
    "Muscle",
    "MuscleAttachment",
    "MuscleForceResult",
    "KNOWN_MUSCLE_REGIONS",
    # Lift
    "JointAngles",
    "LiftConfiguration",
    "ExternalLoad",
    "PrimaryLift",
    "PRIMARY_LIFTS",
    # Biomechanics
    "MomentArm",
    "Force",
    "Torque",
    "Lever",
    "Joint",
    # Pose
    "Pose",
    "AnalyzedPosition",
    # Subject
    "Subject",
]