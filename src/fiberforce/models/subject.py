from __future__ import annotations

"""
Top-level model representing a person (the 'Subject') in the biomechanical system.

This aggregates anthropometry, muscle architecture, and attachments into one coherent model
that can be used for analysis.
"""

from dataclasses import dataclass, field
from typing import Optional

from .anthropometry import UserAnthropometry
from .muscle import Muscle, MuscleAttachment, MuscleRegion


@dataclass
class Subject:
    """
    Represents an individual lifter with their personal anthropometric data
    and muscle architecture model.

    This is the highest-level domain object for personalized analysis.
    """

    anthropometry: UserAnthropometry
    muscles: list[Muscle] = field(default_factory=list)

    # Attachments can be stored here or derived. For flexibility in v1,
    # we allow them to be stored explicitly.
    attachments: list[MuscleAttachment] = field(default_factory=list)

    name: Optional[str] = None
    notes: str = ""

    def get_muscle(self, muscle_name: str) -> Optional[Muscle]:
        for muscle in self.muscles:
            if muscle.name.lower() == muscle_name.lower():
                return muscle
        return None

    def get_attachments_for_region(self, region: MuscleRegion) -> list[MuscleAttachment]:
        """Return all attachments that match a given muscle region."""
        return [
            att for att in self.attachments
            if att.muscle_region.muscle_name == region.muscle_name
            and att.muscle_region.region_name == region.region_name
        ]

    def get_attachments_for_muscle(self, muscle_name: str) -> list[MuscleAttachment]:
        return [
            att for att in self.attachments
            if att.muscle_region.muscle_name.lower() == muscle_name.lower()
        ]

    def get_attachments_for_joint(self, joint: str) -> list[MuscleAttachment]:
        """Return all attachments that cross a given joint."""
        return [att for att in self.attachments if joint in att.joints_crossed]

    def get_all_regions(self) -> list[MuscleRegion]:
        """Return all unique muscle regions this subject has attachments for."""
        seen = set()
        regions = []
        for att in self.attachments:
            key = (att.muscle_region.muscle_name, att.muscle_region.region_name)
            if key not in seen:
                seen.add(key)
                regions.append(att.muscle_region)
        return regions

    def get_moment_arms_for_joint(self, joint: str) -> dict[MuscleRegion, float]:
        """Aggregate moment arms for a joint across all attachments."""
        result = {}
        for att in self.get_attachments_for_joint(joint):
            if joint in att.moment_arms_at_position:
                result[att.muscle_region] = att.moment_arms_at_position[joint]
        return result

    def describe_model(self) -> str:
        """Return a human-readable summary of the subject's model."""
        regions = self.get_all_regions()
        return (
            f"Subject: {self.name or 'Unnamed'}\n"
            f"  Anthropometry complete (upper body): {self.anthropometry.has_basic_upper_body_measurements()}\n"
            f"  Muscles modeled: {len(self.muscles)}\n"
            f"  Attachments: {len(self.attachments)}\n"
            f"  Unique regions: {len(regions)}"
        )

    def __str__(self) -> str:
        return f"Subject({self.name or 'Unnamed'}, {len(self.attachments)} attachments)"