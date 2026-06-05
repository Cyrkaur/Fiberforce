from __future__ import annotations

"""
Pose and AnalyzedPosition models.

These represent a specific static configuration of the body during a lift,
at which we want to perform biomechanical analysis (e.g. peak force calculations).
"""

from dataclasses import dataclass, field
from typing import Optional

from .lift import JointAngles, ExternalLoad, LiftConfiguration
from .muscle import MuscleAttachment, MuscleRegion


@dataclass
class Pose:
    """
    Represents a specific static body position (pose) during a lift.

    This is the central object at which force and torque calculations
    will be performed. It ties together:
    - Joint angles at this position
    - The external load
    - The relevant muscle attachments and their moment arms *at this specific pose*
    """

    name: str = "Unnamed Pose"
    joint_angles: JointAngles = field(default_factory=JointAngles)
    external_load: Optional[ExternalLoad] = None

    # Muscle attachments that are relevant for analysis at this pose,
    # with their moment arms already resolved for these joint angles.
    active_attachments: list[MuscleAttachment] = field(default_factory=list)

    # External load moment arms at this specific pose (joint name -> cm).
    # This allows the load's mechanical effect to be resolved per joint
    # without requiring full dynamic geometry yet.
    load_moment_arms: dict[str, float] = field(default_factory=dict)

    # Optional reference back to the broader lift configuration this pose came from
    source_configuration: Optional[LiftConfiguration] = None

    notes: str = ""

    def get_attachment_for_region(self, region: MuscleRegion) -> Optional[MuscleAttachment]:
        """Return the attachment for a specific muscle region if present."""
        for attachment in self.active_attachments:
            if attachment.muscle_region.muscle_name == region.muscle_name and \
               attachment.muscle_region.region_name == region.region_name:
                return attachment
        return None

    def describe(self) -> str:
        load_str = f"{self.external_load.mass_kg}kg" if self.external_load else "No load"
        return f"{self.name} | {self.joint_angles.describe()} | {load_str}"

    def get_load_moment_arm(self, joint: str) -> Optional[float]:
        """Return the external load moment arm (cm) at a specific joint for this pose."""
        return self.load_moment_arms.get(joint)

    def get_muscle_moment_arms(self, joint: str) -> dict[MuscleRegion, float]:
        """Return a mapping of muscle regions to their moment arms at this joint."""
        result = {}
        for att in self.active_attachments:
            if joint in att.moment_arms_at_position:
                result[att.muscle_region] = att.moment_arms_at_position[joint]
        return result

    def validate_for_analysis(self, target_regions: "Optional[list[MuscleRegion]]" = None) -> list[str]:
        """
        Validate that this Pose has the necessary data for analysis.
        Returns a list of issues (empty list = valid).
        """
        issues: list[str] = []

        if not self.joint_angles.values:
            issues.append("No joint angles defined")

        if not self.external_load:
            issues.append("No external load defined")

        regions_to_check = target_regions or [att.muscle_region for att in self.active_attachments]

        for region in regions_to_check:
            attachment = self.get_attachment_for_region(region)
            if attachment is None:
                issues.append(f"No attachment found for region: {region}")
                continue

            for joint in attachment.joints_crossed:
                if joint not in self.joint_angles.values:
                    issues.append(f"Missing joint angle for attachment joint: {joint}")

                if joint not in self.load_moment_arms:
                    issues.append(f"Missing load moment arm for joint: {joint}")

        return issues

    def __str__(self) -> str:
        return self.describe()


@dataclass
class AnalyzedPosition:
    """
    A Pose that has been prepared for analysis, with additional context.

    This is the primary input object passed to calculators.
    """

    pose: Pose
    target_regions: list[MuscleRegion] = field(default_factory=list)

    def __post_init__(self):
        # If no targets specified, default to all active regions in the pose
        if not self.target_regions and self.pose.active_attachments:
            self.target_regions = [
                att.muscle_region for att in self.pose.active_attachments
            ]

    def describe(self) -> str:
        targets = ", ".join(str(r) for r in self.target_regions)
        return f"{self.pose.describe()} | Targets: [{targets}]"

    def validate(self) -> list[str]:
        """Validate this AnalyzedPosition for calculation."""
        issues = self.pose.validate_for_analysis(self.target_regions)
        if not self.target_regions:
            issues.append("No target regions specified for analysis")
        return issues