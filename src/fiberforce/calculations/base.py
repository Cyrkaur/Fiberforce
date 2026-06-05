"""
Base classes and protocols for calculations in FiberForce.

This module defines the contracts that all calculators should follow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol

from fiberforce.models import (
    AnalyzedPosition,
    Subject,
    MuscleForceResult,
)


@dataclass
class CalculationContext:
    """
    Additional context that can be passed to calculators.
    Useful for configuration, assumptions, reference data, etc.
    """
    assumptions: dict = None
    reference_data_source: str = "user-provided + simplified model"

    def __post_init__(self):
        if self.assumptions is None:
            self.assumptions = {}


class PeakForceCalculator(Protocol):
    """
    Protocol for anything that can calculate peak muscle force
    for target regions at a given AnalyzedPosition.
    """

    def calculate_peak_force(
        self,
        subject: Subject,
        position: AnalyzedPosition,
        context: "Optional[CalculationContext]" = None,
    ) -> list[MuscleForceResult]:
        """Calculate peak force results for the target regions in the position."""
        ...


class BaseCalculator(ABC):
    """
    Abstract base class for calculators.
    Provides common functionality and enforces the interface.
    """

    def __init__(self, context: "Optional[CalculationContext]" = None):
        self.context = context or CalculationContext()

    @abstractmethod
    def calculate_peak_force(
        self,
        subject: Subject,
        position: AnalyzedPosition,
        context: "Optional[CalculationContext]" = None,
    ) -> list[MuscleForceResult]:
        """Subclasses must implement this method."""
        raise NotImplementedError

    def _validate_inputs(self, subject: Subject, position: AnalyzedPosition) -> None:
        """Basic validation that can be reused by implementations."""
        if not subject.anthropometry:
            raise ValueError("Subject must have anthropometry data. Please provide measurements.")

        if not position.pose.joint_angles.values:
            raise ValueError("Pose must have joint angles defined for the analysis position.")

        if not position.target_regions:
            raise ValueError("AnalyzedPosition must specify at least one target MuscleRegion.")

        validation_issues = position.validate()
        if validation_issues:
            raise ValueError(
                f"AnalyzedPosition is not valid for calculation. Issues: {validation_issues}. "
                "Ensure the Pose has the required joint angles and load moment arms for the target regions."
            )