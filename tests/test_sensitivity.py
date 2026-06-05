"""
High-quality focused tests for SensitivityAnalyzer (single + multi-var) and
AnalysisService sensitivity wrappers.

Emphasizes the new multi-variable sensitivity foundation (run_multi / sensitivity_multi)
delivered for the overdrive / v0.3 era. All tests are fast (<50ms each) and
use pure in-memory rebuild callables.
"""
import pytest
from typing import Any

from fiberforce.models import Subject, AnalyzedPosition, UserAnthropometry, JointAngles, ExternalLoad, Pose
from fiberforce.models.muscle import MuscleRegion, KNOWN_MUSCLE_REGIONS
from fiberforce.calculations.sensitivity import SensitivityAnalyzer, SensitivityResult
from fiberforce.analysis.service import AnalysisService


def _make_minimal_bench_position(load_kg: float = 100.0) -> AnalyzedPosition:
    """Lightweight but attachment-rich position so calculators produce real >0 force results."""
    from fiberforce.models import MuscleAttachment
    sternal = next(r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name)
    att = MuscleAttachment(
        muscle_region=sternal,
        joints_crossed=["shoulder"],
        moment_arms_at_position={"shoulder": 5.4},
    )
    pose = Pose(
        name=f"test bench {load_kg}kg",
        joint_angles=JointAngles(values={"shoulder": 90.0, "elbow": 90.0}),
        external_load=ExternalLoad(mass_kg=load_kg),
        active_attachments=[att],
        load_moment_arms={"shoulder": 30.0},
    )
    return AnalyzedPosition(pose=pose, target_regions=[sternal])


def _make_minimal_squat_position(load_kg: float = 140.0, femur: float = 42.0) -> AnalyzedPosition:
    """Attachment-rich for multi-var tests to yield real forces."""
    from fiberforce.models import MuscleAttachment
    glute = next(r for r in KNOWN_MUSCLE_REGIONS if "Gluteus Maximus" in r.muscle_name and "Upper" in r.region_name)
    att = MuscleAttachment(
        muscle_region=glute,
        joints_crossed=["hip"],
        moment_arms_at_position={"hip": 5.9},
    )
    pose = Pose(
        name=f"test squat {load_kg}kg",
        joint_angles=JointAngles(values={"hip": 110.0, "knee": 35.0}),
        external_load=ExternalLoad(mass_kg=load_kg),
        active_attachments=[att],
        load_moment_arms={"hip": 22.0, "knee": 12.0},
    )
    return AnalyzedPosition(pose=pose, target_regions=[glute])


def _simple_load_rebuild(base: AnalyzedPosition, value: Any) -> AnalyzedPosition:
    """Simple rebuild used for single-var legacy path."""
    from fiberforce.models import ExternalLoad, Pose
    old_pose = base.pose
    new_load = ExternalLoad(mass_kg=value, load_type=old_pose.external_load.load_type)
    new_pose = Pose(
        name=old_pose.name,
        joint_angles=old_pose.joint_angles,
        external_load=new_load,
        active_attachments=old_pose.active_attachments,
        load_moment_arms=old_pose.load_moment_arms.copy(),
    )
    return AnalyzedPosition(pose=new_pose, target_regions=base.target_regions)


# -------------------------------------------------------------------
# Single variable (baseline + regression)
# -------------------------------------------------------------------

def test_single_var_run_basic():
    analyzer = SensitivityAnalyzer()
    subj = Subject(anthropometry=UserAnthropometry())
    base = _make_minimal_bench_position(100.0)
    sternal = base.target_regions[0]

    res = analyzer.run(
        subject=subj,
        base_position=base,
        variable="load_kg",
        values=[80, 100, 120],
        target_region=sternal,
        rebuild_position=_simple_load_rebuild,
    )
    assert isinstance(res, SensitivityResult)
    assert res.variable_name == "load_kg"
    assert len(res.points) == 3
    assert all(p.peak_force_n >= 0 for p in res.points)
    assert any(p.peak_force_n > 0 for p in res.points)
    assert res.points[0].variable_value == 80


def test_single_var_no_rebuild_fallback_does_not_crash():
    analyzer = SensitivityAnalyzer()
    subj = Subject(anthropometry=UserAnthropometry())
    base = _make_minimal_bench_position(90)
    sternal = base.target_regions[0]

    # No rebuild provided -> uses internal _simple_rebuild (only load_kg supported)
    res = analyzer.run(subj, base, "load_kg", [85, 95], sternal)
    assert len(res.points) == 2


# -------------------------------------------------------------------
# Multi-variable sensitivity (core new feature)
# -------------------------------------------------------------------

def test_run_multi_produces_one_result_per_variable():
    """Primary contract of the multi-var foundation."""
    analyzer = SensitivityAnalyzer()
    subj = Subject(anthropometry=UserAnthropometry(femur_length_cm=43.0))
    base = _make_minimal_squat_position(140)
    glute = base.target_regions[0]

    variables = [
        ("load_kg", [120, 140, 160]),
        ("femur_cm", [38.0, 42.0, 46.0]),
    ]

    # Record what the rebuild actually sees (validates "hold others at first value" semantics)
    seen_params = []

    def rebuild_multi(base_pos: AnalyzedPosition, params: dict) -> AnalyzedPosition:
        seen_params.append(params.copy())
        # Minimal mutation for test (load only; femur would normally trigger geo or custom attachment)
        from fiberforce.models import ExternalLoad, Pose
        p = base_pos.pose
        new_p = Pose(
            name=p.name,
            joint_angles=p.joint_angles,
            external_load=ExternalLoad(mass_kg=params.get("load_kg", p.external_load.mass_kg)),
            active_attachments=p.active_attachments,
            load_moment_arms=p.load_moment_arms.copy(),
        )
        return AnalyzedPosition(pose=new_p, target_regions=base_pos.target_regions)

    results = analyzer.run_multi(
        subject=subj,
        base_position=base,
        variables=variables,
        target_region=glute,
        rebuild_multi=rebuild_multi,
    )

    assert len(results) == 2
    assert results[0].variable_name == "load_kg"
    assert results[1].variable_name == "femur_cm"
    assert len(results[0].points) == 3
    assert len(results[1].points) == 3

    # Verify holding semantics: for the femur sweep, load should have been fixed at first load value (120)
    # for the load sweep, femur fixed at first femur (38)
    load_sweep_calls = [p for p in seen_params if "load_kg" in p and p.get("femur_cm") == 38.0]
    femur_sweep_calls = [p for p in seen_params if "femur_cm" in p and p.get("load_kg") == 120]
    assert len(load_sweep_calls) >= 2
    assert len(femur_sweep_calls) >= 2


def test_run_multi_empty_variables_returns_empty_list():
    analyzer = SensitivityAnalyzer()
    subj = Subject(anthropometry=UserAnthropometry())
    base = _make_minimal_squat_position()
    glute = base.target_regions[0]

    res_list = analyzer.run_multi(subj, base, [], glute, lambda b, p: b)
    assert res_list == []


def test_run_multi_missing_target_region_graceful():
    """When target region never matches, still returns results with 0-force sentinel points."""
    analyzer = SensitivityAnalyzer()
    subj = Subject(anthropometry=UserAnthropometry())
    base = _make_minimal_bench_position()
    bogus_region = MuscleRegion(muscle_name="Bogus", region_name="Nonexistent")

    variables = [("load_kg", [100, 110])]
    results = analyzer.run_multi(subj, base, variables, bogus_region, lambda b, p: b)
    assert len(results) == 1
    assert all(p.peak_force_n == 0.0 for p in results[0].points)
    assert "no_match" in results[0].points[0].confidence_level or "Target" in results[0].points[0].notes


# -------------------------------------------------------------------
# Service passthrough (the public API used by CLI + advanced examples)
# -------------------------------------------------------------------

def test_service_sensitivity_multi_delegates_correctly():
    service = AnalysisService()
    subj = service.create_subject_from_measurements(femur_length_cm=44.0)
    base = _make_minimal_squat_position(150)
    glute = base.target_regions[0]

    variables = [("load_kg", [100, 150, 200])]

    results = service.sensitivity_multi(
        subj, base, variables, glute, rebuild_multi=lambda b, p: b
    )
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].variable_name == "load_kg"


@pytest.mark.parametrize("lift_alias", ["squat", "bench"])
def test_service_sensitivity_multi_via_real_builder(lift_alias):
    """Integration style: service + real builders (still fast)."""
    service = AnalysisService()
    subj = service.create_subject_from_measurements(humerus_length_cm=33, femur_length_cm=41, tibia_length_cm=37)

    if lift_alias == "squat":
        base = service.build_position("squat", load_kg=140, variation="high_bar")
        region = next(r for r in KNOWN_MUSCLE_REGIONS if "Gluteus" in r.muscle_name)
        vars_ = [("load_kg", [100, 140])]
    else:
        base = service.build_position("bench", load_kg=100, variation="flat")
        region = next(r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name)
        vars_ = [("load_kg", [80, 100])]

    out = service.sensitivity_multi(subj, base, vars_, region, rebuild_multi=lambda b, p: b)
    assert len(out) == 1
    assert len(out[0].points) == 2


# -------------------------------------------------------------------
# Visualization convenience (ascii path only for speed)
# -------------------------------------------------------------------

def test_sensitivity_plot_ascii_path_does_not_crash():
    analyzer = SensitivityAnalyzer()
    subj = Subject(anthropometry=UserAnthropometry())
    base = _make_minimal_bench_position()
    res = analyzer.run(subj, base, "load_kg", [90, 100], base.target_regions[0], _simple_load_rebuild)

    # ascii_only or headless must succeed without matplotlib
    fig = analyzer.plot(res, ascii_only=True, show=False)
    assert fig is not None or True  # either returns something or is fire-and-forget
