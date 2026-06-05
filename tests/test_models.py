def test_ref_ohp_tables():
    from fiberforce.reference.moment_arms import OVERHEAD_PRESS_LOAD_MOMENT_ARMS
    from fiberforce.reference.data import get_default_reference
    assert len(OVERHEAD_PRESS_LOAD_MOMENT_ARMS) >= 6
    assert get_default_reference().get_load_moment_arm("ohp", "seated_lockout") is not None
    # Also verify expanded tables via ReferenceData
    ref = get_default_reference()
    assert ref.get_moment_arm("ohp", "triceps_long", "standing_lockout", "elbow") is not None
    assert ref.get_moment_arm("ohp", "posterior_delt", "seated_mid", "shoulder") is not None


# =============================================================================
# OHP Parity + Builder Smoke Tests (full OHP parity expansion)
# =============================================================================

import pytest


OHP_CONFIGS = [
    (70, "standing", "bottom", "Anterior"),
    (65, "seated", "bottom", "Anterior"),
    (75, "standing", "mid", "Lateral"),
    (60, "seated", "mid", "Lateral"),
    (80, "standing", "lockout", "Triceps"),
    (55, "seated", "lockout", "Triceps long head"),
    (68, "strict", "bottom", "Anterior delt"),
    (72, "standing", "top", "posterior"),
]


@pytest.mark.parametrize("load_kg,variation,position,target", OHP_CONFIGS)
def test_build_ohp_variants_produce_valid_position(load_kg, variation, position, target):
    """Full OHP parity: every supported variation/position/target combo builds without error and has sane structure."""
    from fiberforce.examples import build_ohp_analyzed_position
    from fiberforce.models import AnalyzedPosition

    pos = build_ohp_analyzed_position(
        load_kg=load_kg,
        variation=variation,
        position=position,
        target_region_name=target,
        humerus_cm=33.0,
        forearm_cm=26.0,
    )
    assert isinstance(pos, AnalyzedPosition)
    assert len(pos.target_regions) >= 1
    assert pos.pose is not None
    assert pos.pose.external_load.mass_kg == load_kg
    assert any(j in pos.pose.joint_angles.values for j in ("shoulder", "elbow"))
    # Notes should reflect OHP generation
    assert "OHP" in (pos.pose.notes or "")


def test_ohp_via_service_build_position_aliases():
    """Service is the single source; all OHP aliases route correctly (parity)."""
    from fiberforce.analysis.service import AnalysisService
    service = AnalysisService()

    for alias in ("ohp", "overhead", "overhead_press", "military"):
        pos = service.build_position(
            alias, load_kg=62, variation="seated", position="mid", target_region_name="Lateral"
        )
        assert pos is not None
        assert "OHP" in pos.pose.name or "overhead" in pos.pose.name.lower()


def test_ohp_analysis_yields_results_with_confidence():
    """End-to-end analyze on OHP must produce MuscleForceResults with confidence tags."""
    from fiberforce.analysis.service import AnalysisService
    from fiberforce.examples import example_subject_with_shoulders

    service = AnalysisService()
    subject = example_subject_with_shoulders()
    pos = service.build_position("ohp", load_kg=70, variation="standing", position="bottom", target_region_name="Anterior")

    res = service.analyze(subject, pos)
    assert res.results
    for r in res.results:
        assert r.peak_force_newtons > 0
        assert r.confidence_level  # not empty
        # multi now includes all delts + tri; each must be a known OHP mover
        name = str(r.muscle_region).lower()
        assert "delt" in name or "triceps" in name or "trap" in name


# =============================================================================
# Additional ReferenceData + Model Basics (parity + robustness)
# =============================================================================

def test_reference_data_ohp_and_all_lifts_available():
    from fiberforce.reference.data import get_default_reference

    ref = get_default_reference()
    lifts = ref.list_available_lifts()
    assert "ohp" in lifts or any("ohp" in l.lower() for l in lifts)
    assert "bench" in lifts
    assert "squat" in lifts
    assert "deadlift" in lifts

    # OHP specific getters
    assert ref.get_load_moment_arm("ohp", "standing_lockout") is not None


@pytest.mark.parametrize("lift", ["bench", "squat", "deadlift", "ohp"])
def test_reference_get_moment_arm_fallbacks_for_all_lifts(lift):
    from fiberforce.reference.data import get_default_reference

    ref = get_default_reference()
    # Exercise the static path (no anthro) for several common regions/positions
    val = ref.get_moment_arm(lift, "glute_max", "conventional_bottom", "hip") if lift == "deadlift" else \
          ref.get_moment_arm(lift, "sternal_pecs", "flat_bench_bottom", "shoulder") if lift == "bench" else \
          ref.get_moment_arm(lift, "quads", "high_bar_bottom", "knee") if lift == "squat" else \
          ref.get_moment_arm(lift, "anterior_delt", "standing_bottom", "shoulder")
    # Some may legitimately be None for non-matching; the call must not explode
    assert val is None or isinstance(val, (int, float))


def test_lift_configuration_construction_and_description():
    from fiberforce.models.lift import LiftConfiguration, JointAngles, ExternalLoad
    from fiberforce.models.muscle import KNOWN_MUSCLE_REGIONS

    config = LiftConfiguration(
        lift_name="Overhead Press",
        variation="seated",
        joint_angles=JointAngles(values={"shoulder": 90, "elbow": 70}),
        external_load=ExternalLoad(mass_kg=65),
        target_regions=[r for r in KNOWN_MUSCLE_REGIONS if "Deltoid" in r.muscle_name][:2],
        notes="OHP parity test config",
    )
    desc = config.short_description()
    assert "65" in desc and "seated" in desc.lower()


def test_subject_and_anthro_roundtrip_fields():
    from fiberforce.models.subject import Subject
    from fiberforce.models.anthropometry import UserAnthropometry

    anthro = UserAnthropometry(
        name="Test OHP Athlete",
        humerus_length_cm=34.1,
        forearm_length_cm=26.2,
        biacromial_width_cm=40.5,
    )
    subj = Subject(anthropometry=anthro, name="Test Athlete")
    assert subj.anthropometry.humerus_length_cm == 34.1
    assert "OHP" not in (subj.name or "")  # just sanity
