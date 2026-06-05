from __future__ import annotations

"""Models related to muscles and their sub-regions for regional hypertrophy modeling."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MuscleRegion:
    """A distinct anatomical or functional sub-region within a skeletal muscle."""

    muscle_name: str
    region_name: str
    fiber_orientation: Optional[str] = None
    primary_actions: list[str] = field(default_factory=list)
    notes: str = ""

    def __str__(self) -> str:
        return f"{self.muscle_name} — {self.region_name}"


@dataclass
class MuscleArchitecture:
    """Architectural parameters of a muscle region that affect force production."""

    physiological_cross_sectional_area_cm2: Optional[float] = None
    pennation_angle_deg: Optional[float] = None
    optimal_fiber_length_cm: Optional[float] = None
    tendon_slack_length_cm: Optional[float] = None
    max_isometric_force_n: Optional[float] = None
    notes: str = ""


@dataclass
class Muscle:
    """A whole skeletal muscle containing one or more regions."""

    name: str
    regions: list[MuscleRegion] = field(default_factory=list)
    primary_joints: list[str] = field(default_factory=list)

    def get_region(self, region_name: str) -> Optional[MuscleRegion]:
        for region in self.regions:
            if region.region_name.lower() == region_name.lower():
                return region
        return None

    def __str__(self) -> str:
        return f"Muscle({self.name}, {len(self.regions)} regions)"


@dataclass
class MuscleAttachment:
    """
    Describes how a MuscleRegion attaches to and produces force across joints.

    This is one of the most important foundational concepts for
    moment arm and force calculations.
    """

    muscle_region: MuscleRegion
    joints_crossed: list[str]  # e.g. ["shoulder", "elbow"]
    # Static moment arm values (cm) at a particular joint configuration.
    # Key = joint name, Value = moment arm length in cm at the analyzed position.
    moment_arms_at_position: dict[str, float] = field(default_factory=dict)

    notes: str = ""

    def __post_init__(self):
        # Basic validation
        if len(self.joints_crossed) != len(self.moment_arms_at_position):
            # This is a soft warning for now; strict validation can be added later
            pass

    def has_moment_arm_for(self, joint: str) -> bool:
        return joint in self.moment_arms_at_position


@dataclass
class MuscleForceResult:
    """
    Result of a peak force calculation for a specific muscle region at a
    particular static position during a lift.

    peak_torque_nm / peak_torque_ftlb: For muscles that are co-contributors on
    the same joint (e.g. pec + ant delt on shoulder during bench), this is the
    *modeled torque contribution/share* of *this muscle* (dominance_percent/100
    * full joint external torque), not the full joint torque. This makes the
    "ft-lb" numbers different per muscle on the joint (larger MA gets larger
    share). Sum of shares across co-movers on a joint equals the external joint
    torque. See calculations/peak_force.py for the MA-proportional partitioning
    model and assumptions.
    """

    muscle_region: MuscleRegion
    peak_force_newtons: float
    peak_torque_nm: Optional[float] = None
    joint: Optional[str] = None
    position_description: str = ""
    confidence_level: str = "estimate"   # estimate | model-based | literature-based
    moment_arm_used_cm: Optional[float] = None
    notes: str = ""
    dominance_percent: Optional[float] = None  # % mechanical dominance at joint (relative MA among co-contributors). Larger MA = higher dominance = larger share of the joint torque credited to this muscle (and lower force needed if sole actor). The reported peak_torque_ftlb for this result is now (dominance/100 * full joint torque).

    def __str__(self) -> str:
        if self.peak_torque_nm:
            from fiberforce.calculations.utils import nm_to_ftlb
            return f"{self.muscle_region}: {nm_to_ftlb(self.peak_torque_nm):.1f} ft-lb @ {self.joint}"
        return f"{self.muscle_region}: {self.peak_force_newtons:.1f} N @ {self.joint}"

    @property
    def peak_torque_ftlb(self) -> Optional[float]:
        """Torque in foot-pounds (v1 US units output)."""
        if self.peak_torque_nm is None:
            return None
        from fiberforce.calculations.utils import nm_to_ftlb
        return nm_to_ftlb(self.peak_torque_nm)


# Starting library of commonly referenced muscle regions for resistance training
KNOWN_MUSCLE_REGIONS: list[MuscleRegion] = [
    # Pectoralis Major
    MuscleRegion("Pectoralis Major", "Sternal fibers", "transverse", ["horizontal adduction", "internal rotation"]),
    MuscleRegion("Pectoralis Major", "Clavicular fibers", "oblique", ["flexion", "horizontal adduction"]),
    MuscleRegion("Pectoralis Major", "Abdominal fibers", "oblique", ["adduction", "internal rotation"]),

    # Deltoid
    MuscleRegion("Deltoid", "Anterior", "oblique", ["flexion", "horizontal adduction"]),
    MuscleRegion("Deltoid", "Lateral", "vertical", ["abduction"]),
    MuscleRegion("Deltoid", "Posterior", "oblique", ["extension", "horizontal abduction"]),

    # Triceps Brachii
    MuscleRegion("Triceps Brachii", "Long head", "vertical", ["elbow extension", "shoulder extension"]),
    MuscleRegion("Triceps Brachii", "Lateral head", "vertical", ["elbow extension"]),
    MuscleRegion("Triceps Brachii", "Medial head", "vertical", ["elbow extension"]),

    # Biceps Brachii
    MuscleRegion("Biceps Brachii", "Long head", "vertical", ["elbow flexion", "shoulder flexion"]),
    MuscleRegion("Biceps Brachii", "Short head", "vertical", ["elbow flexion"]),

    # Latissimus Dorsi
    MuscleRegion("Latissimus Dorsi", "Thoracic fibers", "vertical", ["adduction", "extension", "internal rotation"]),
    MuscleRegion("Latissimus Dorsi", "Lumbar fibers", "vertical", ["adduction", "extension"]),

    # Gluteus Maximus
    MuscleRegion("Gluteus Maximus", "Upper fibers", "oblique", ["hip extension", "external rotation"]),
    MuscleRegion("Gluteus Maximus", "Lower fibers", "vertical", ["hip extension"]),

    # Quadriceps
    MuscleRegion("Rectus Femoris", "Full", "vertical", ["knee extension", "hip flexion"]),
    MuscleRegion("Vastus Lateralis", "Full", "vertical", ["knee extension"]),
    MuscleRegion("Vastus Medialis", "Full", "vertical", ["knee extension"]),
    MuscleRegion("Vastus Intermedius", "Full", "vertical", ["knee extension"]),

    # Hamstrings
    MuscleRegion("Biceps Femoris (Long Head)", "Full", "vertical", ["knee flexion", "hip extension"]),
    MuscleRegion("Semitendinosus", "Full", "vertical", ["knee flexion", "hip extension"]),
    MuscleRegion("Semimembranosus", "Full", "vertical", ["knee flexion", "hip extension"]),

    # Gluteus Medius
    MuscleRegion("Gluteus Medius", "Anterior fibers", "oblique", ["hip abduction", "internal rotation"]),
    MuscleRegion("Gluteus Medius", "Posterior fibers", "oblique", ["hip abduction", "external rotation"]),

    # Erector Spinae (more granular)
    MuscleRegion("Erector Spinae", "Thoracic", "vertical", ["spinal extension"]),
    MuscleRegion("Erector Spinae", "Lumbar", "vertical", ["spinal extension"]),

    # Additional shoulder / upper back for OHP realism
    MuscleRegion("Deltoid", "Posterior (rear)", "oblique", ["horizontal abduction", "external rotation"]),
    MuscleRegion("Trapezius", "Upper", "vertical", ["scapular elevation"]),
    MuscleRegion("Trapezius", "Middle", "vertical", ["scapular retraction"]),

    # Rotator cuff starters (light coverage)
    MuscleRegion("Supraspinatus", "Full", "vertical", ["abduction"]),
    MuscleRegion("Infraspinatus", "Full", "oblique", ["external rotation"]),
]