from __future__ import annotations

"""
Fundamental biomechanical concepts used throughout FiberForce.

These are the low-level building blocks for reasoning about force
production, levers, and muscle mechanics.
"""

from dataclasses import dataclass


@dataclass
class MomentArm:
    """
    The perpendicular distance (in cm) from a joint's axis of rotation
    to the line of action of a force (either muscle or external load).
    """
    value_cm: float
    joint: str
    force_type: str = ""          # "muscle" or "external"
    description: str = ""


@dataclass
class Force:
    """A linear force."""
    magnitude_newtons: float
    direction: str = ""           # Description of direction (e.g. "vertical", "along muscle")


@dataclass
class Torque:
    """A rotational force (moment) around a joint."""
    magnitude_nm: float           # Newton-meters
    joint: str
    direction: str = ""           # e.g. "elbow extension torque"


@dataclass
class Lever:
    """
    A simple representation of a lever system in the body.

    In lifting, we often deal with Class 1, 2, and 3 levers
    depending on the joint and movement.
    """
    fulcrum: str                  # The joint acting as the fulcrum
    effort_arm_cm: float          # Distance from fulcrum to effort (usually muscle)
    load_arm_cm: float            # Distance from fulcrum to external load
    lever_class: int = 3          # 1, 2, or 3

    def mechanical_advantage(self) -> float:
        if self.load_arm_cm == 0:
            return float('inf')
        return self.effort_arm_cm / self.load_arm_cm


@dataclass
class Joint:
    """Represents a joint in the body for modeling purposes."""
    name: str
    description: str = ""