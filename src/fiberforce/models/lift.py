from __future__ import annotations

"""Models for representing primary lifts and specific configurations."""

from dataclasses import dataclass, field
from typing import Optional

from .muscle import MuscleRegion


@dataclass
class JointAngles:
    """Joint angles (in degrees) at a specific static position during a lift."""
    values: dict[str, float] = field(default_factory=dict)

    def get(self, joint: str, default: Optional[float] = None) -> Optional[float]:
        return self.values.get(joint, default)

    def describe(self) -> str:
        if not self.values:
            return "No joint angles defined"
        return ", ".join(f"{k}={v:.1f}°" for k, v in sorted(self.values.items()))


@dataclass
class ExternalLoad:
    """Description of the external load being moved during a lift.

    Supports both metric (kg) and imperial (lbs) at construction time.
    Internally normalizes to mass_kg for calculations.
    """
    mass_kg: float
    load_type: str = "barbell"           # barbell, dumbbell, kettlebell, bodyweight, etc.
    load_position: Optional[str] = None  # e.g. "bar on back", "front rack", "in hands"

    @classmethod
    def from_lbs(cls, mass_lbs: float, load_type: str = "barbell", load_position: Optional[str] = None):
        """Create from imperial pounds (for v1 US units support)."""
        from fiberforce.calculations.utils import load_lbs_to_kg
        return cls(
            mass_kg=load_lbs_to_kg(mass_lbs),
            load_type=load_type,
            load_position=load_position,
        )

    @property
    def mass_lbs(self) -> float:
        """Approximate mass in pounds (for display in imperial mode)."""
        from fiberforce.calculations.utils import kg_to_lbs
        return kg_to_lbs(self.mass_kg)


@dataclass
class PrimaryLift:
    """
    A formal definition of a primary compound lift.

    This represents the *lift type* itself (not a specific performance of it).
    """

    name: str
    common_variations: list[str] = field(default_factory=list)
    primary_joints_involved: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class LiftConfiguration:
    """
    A specific setup of a primary lift at one static position.

    This is the main input object when requesting peak force calculations.
    """

    lift_name: str
    variation: str
    joint_angles: JointAngles
    external_load: ExternalLoad

    # Exercise setup variables that affect mechanics
    grip_width_cm: Optional[float] = None
    grip_orientation: Optional[str] = None
    stance_width: Optional[str] = None
    bar_position: Optional[str] = None
    rom_restriction: Optional[str] = None

    # Target muscle regions the user wants analyzed
    target_regions: list[MuscleRegion] = field(default_factory=list)

    notes: str = ""

    def short_description(self) -> str:
        load = f"{self.external_load.mass_kg} kg"
        return f"{self.variation} {self.lift_name} @ {self.joint_angles.describe()} ({load})"


# Registry of primary lifts we intend to support
PRIMARY_LIFTS: list[PrimaryLift] = [
    PrimaryLift("Bench Press", ["Flat", "Incline", "Decline", "Wide Grip", "Close Grip"],
                ["shoulder", "elbow"]),
    PrimaryLift("Incline Bench Press", ["Incline", "30 Degree", "45 Degree"],
                ["shoulder", "elbow"]),
    PrimaryLift("Overhead Press", ["Standing", "Seated", "Dumbbell", "Barbell"],
                ["shoulder", "elbow"]),
    PrimaryLift("Back Squat", ["High Bar", "Low Bar", "Safety Bar"],
                ["hip", "knee", "ankle"]),
    PrimaryLift("Front Squat", ["Olympic", "Cross-arm"],
                ["hip", "knee", "ankle"]),
    PrimaryLift("Conventional Deadlift", ["Conventional", "Deficit", "Block"],
                ["hip", "knee"]),
    PrimaryLift("Sumo Deadlift", ["Sumo", "Semi-sumo"],
                ["hip", "knee"]),
    PrimaryLift("Romanian Deadlift", ["RDL", "Romanian", "Stiff Leg"],
                ["hip", "knee"]),
]