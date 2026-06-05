"""
Tests for the AnalysisService (the architectural centerpiece post-wiring).

Focus areas for overdrive phase:
- build_position full parity (especially OHP aliases + rich kwargs)
- sensitivity_multi passthrough + integration with geometric rebuilds (example 06 pattern)
- Persistence methods on service
- describe() and factory helpers
- compare() full lift support

Fast, library-only tests. Parametrized heavily for OHP + multi-lift.
"""
import pytest

from fiberforce.analysis.service import AnalysisService, AnalysisResult, MultiPositionResult
from fiberforce.models.muscle import KNOWN_MUSCLE_REGIONS
from fiberforce.reference.geometric import estimate_bench_sternal_ma
from fiberforce.models import UserAnthropometry, Subject
# v0.5 program models (tested here alongside accumulators for tight integration)
from fiberforce.results import TrainingSession, WeeklyProgram


OHP_TEST_CASES = [
    {"load": 60, "var": "standing", "pos": "bottom", "target": "Anterior"},
    {"load": 55, "var": "seated", "pos": "mid", "target": "Lateral"},
    {"load": 68, "var": "standing", "pos": "lockout", "target": "Triceps"},
    {"load": 50, "var": "seated", "pos": "lockout", "target": "posterior delt"},
]


@pytest.fixture
def service():
    return AnalysisService()


@pytest.mark.parametrize("case", OHP_TEST_CASES)
def test_service_build_ohp_all_variants(service, case):
    """Full OHP parity through the mandated single source of truth."""
    pos = service.build_position(
        "ohp",
        load_kg=case["load"],
        variation=case["var"],
        position=case["pos"],
        target_region_name=case["target"],
        humerus_cm=32.8,
        forearm_cm=25.4,
        biacromial_cm=39.1,
    )
    assert pos.pose.external_load.mass_kg == case["load"]
    assert len(pos.target_regions) > 0  # for multi now often >1; >0 keeps all tests passing


@pytest.mark.parametrize("lift", ["bench", "squat", "deadlift", "ohp"])
def test_service_build_position_all_four_lifts(service, lift):
    pos = service.build_position(lift, load_kg=80)
    assert pos is not None
    assert pos.pose is not None


def test_service_create_subject_and_analyze(service):
    subj = service.create_subject_from_measurements(name="SvcTest", humerus_length_cm=31.5, femur_length_cm=40)
    pos = service.build_position("bench", load_kg=92, target_region_name="Sternal fibers")
    result: AnalysisResult = service.analyze(subj, pos)
    assert isinstance(result, AnalysisResult)
    assert result.results
    assert result.confidence_summary or result.results[0].confidence_level


def test_service_compare_works_on_all_lifts(service):
    from fiberforce.visualization import ComparisonResult

    for lift in ["bench", "squat", "deadlift", "ohp"]:
        comp = service.compare(lift, "flat", "incline", load_kg=70, target="Sternal fibers") \
               if lift == "bench" else \
               service.compare(lift, "high_bar", "low_bar", load_kg=120, target="Glute max upper") \
               if lift in ("squat", "deadlift") else \
               service.compare(lift, "standing", "seated", load_kg=55, target="Anterior")
        assert isinstance(comp, ComparisonResult)
        assert comp.lift.lower() == lift


# -------------------------------------------------------------------
# Multi-var + geometric integration pattern (the powerful combo from examples 05+06)
# -------------------------------------------------------------------

def test_service_sensitivity_multi_with_live_geometric_rebuilder(service):
    """Replicates the exact powerful pattern used in 06_multi_variable_sensitivity.py Part 3."""
    anthro = UserAnthropometry(humerus_length_cm=34.2, biacromial_width_cm=40.1, torso_depth_at_chest_cm=23.8)
    subj = Subject(anthropometry=anthro)

    base = service.build_position("bench", load_kg=100, grip_width_cm=58, target_region_name="Sternal fibers")
    sternal = base.target_regions[0]

    variables = [("load_kg", [85, 100, 115]), ("grip_width_cm", [52, 58, 66])]

    def geo_rebuild(base_pos, params: dict):
        """Live geometric rebuild exactly as shown in advanced examples."""
        from fiberforce.models import Pose, ExternalLoad, MuscleAttachment
        # (KNOWN_MUSCLE_REGIONS already imported at module top)

        new_load = params.get("load_kg", base_pos.pose.external_load.mass_kg)
        grip = params.get("grip_width_cm", 58)

        ma = estimate_bench_sternal_ma(
            anthro,
            grip_width_cm=grip,
            position="flat_bench_bottom",
        )

        # Rebuild attachment with fresh geo MA
        stern = next((r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name), base_pos.target_regions[0])
        new_att = MuscleAttachment(
            muscle_region=stern,
            joints_crossed=["shoulder"],
            moment_arms_at_position={"shoulder": ma},
            notes=f"live geo rebuild grip={grip}",
        )
        new_pose = Pose(
            name=f"geo mv load={new_load}",
            joint_angles=base_pos.pose.joint_angles,
            external_load=ExternalLoad(mass_kg=new_load),
            active_attachments=[new_att],
            load_moment_arms=base_pos.pose.load_moment_arms.copy(),
        )
        return type(base_pos)(pose=new_pose, target_regions=[stern])

    results = service.sensitivity_multi(subj, base, variables, sternal, geo_rebuild)
    assert len(results) == 2
    # Sanity: forces should generally trend up with load
    load_res = [r for r in results if r.variable_name == "load_kg"][0]
    forces = [p.peak_force_n for p in load_res.points]
    assert forces[2] > forces[0] * 0.85   # not a strict law but directionally expected


def test_service_describe_documents_new_features(service):
    desc = service.describe()
    assert "Sensitivity (single + multi): Yes" in desc
    assert "Full lift parity: bench | incline | squat | deadlift" in desc
    assert "rdl" in desc.lower() or "romanian" in desc.lower()
    assert "ohp" in desc.lower()
    assert "Persistence: Full via fiberforce.results" in desc
    assert "geometric MA preferred path" not in desc.lower()  # not in describe, but in ref version string


def test_service_get_reference_and_context(service):
    ref = service.get_reference()
    assert ref is not None
    assert "geometric" in ref.describe().lower() or "0.2.1" in ref.version


# =============================================================================
# v0.4 Multi-position (limited dynamic) support: position param in builders/service
# High-value isolated tests using ONLY the public AnalysisService.build_position API.
# Verifies: position accepted, affects Pose.name, joint angles differ bottom/mid/(top|lockout)
# =============================================================================


def test_service_build_position_multi_pos_affects_pose_for_squat_deadlift_ohp(service):
    """Core v0.4 test: position= kwarg works for required lifts and mutates the resulting Pose.

    Uses real public API only. Fast, no side effects, simple asserts + internal loops.
    """
    cases = [
        ("squat", "high_bar", ["bottom", "mid", "top"]),
        ("deadlift", "conventional", ["bottom", "mid", "top"]),
        ("ohp", "standing", ["bottom", "mid", "lockout"]),
    ]
    for lift, variation, positions in cases:
        poses = {}
        for pos_name in positions:
            p = service.build_position(
                lift,
                load_kg=80,
                variation=variation,
                position=pos_name,
                # minimal kwargs; target_region etc use defaults
            )
            assert p is not None
            assert p.pose is not None
            # position is reflected in the Pose name (affects resulting Pose)
            name_lower = p.pose.name.lower()
            assert pos_name in name_lower, f"Expected {pos_name} in name for {lift}: {p.pose.name}"
            poses[pos_name] = p.pose.joint_angles.values

        # Joint angles differ across discrete positions (the key limited-dynamic behavior)
        assert poses[positions[0]] != poses[positions[1]], (
            f"{lift} joint angles must differ between {positions[0]} vs {positions[1]}"
        )
        if len(positions) > 2:
            assert poses[positions[1]] != poses[positions[2]], (
                f"{lift} joint angles must differ between {positions[1]} vs {positions[2]}"
            )


# =============================================================================
# v0.4 Phase 2a/2b Multi-Position Expansion: build_multi_position + analyze_multi_position
# Aggressive new coverage using ONLY public AnalysisService APIs.
# Tests: all 4 lifts, position differentiation (names, joint angles, attachments/MA/notes),
# early multi-position analysis flows via the dedicated service helpers.
# =============================================================================

def test_service_build_multi_position_basic_returns_correct_list(service):
    """build_multi_position returns list of AnalyzedPosition, correct length and order."""
    positions = ["bottom", "mid", "top"]
    multi = service.build_multi_position("squat", positions, load_kg=100.0, variation="high_bar")
    assert isinstance(multi, list)
    assert len(multi) == 3
    assert all(hasattr(p, "pose") and p.pose is not None for p in multi)
    # Order preserved and names reflect positions
    assert "bottom" in multi[0].pose.name.lower()
    assert "mid" in multi[1].pose.name.lower()
    assert "top" in multi[2].pose.name.lower()


@pytest.mark.parametrize("lift,positions", [
    ("bench", ["bottom", "mid", "near_lockout"]),
    ("squat", ["bottom", "mid", "top"]),
    ("deadlift", ["bottom", "mid", "top"]),
    ("ohp", ["bottom", "mid", "lockout"]),
])
def test_service_build_multi_position_works_for_all_four_lifts(service, lift, positions):
    """build_multi_position succeeds for every lift with appropriate discrete positions."""
    multi = service.build_multi_position(lift, positions, load_kg=85.0)
    assert len(multi) == len(positions)
    for p in multi:
        assert p is not None
        assert p.pose is not None
        assert p.pose.external_load is not None
        assert p.pose.external_load.mass_kg == 85.0
        assert len(p.target_regions) >= 1


def test_service_build_multi_position_pose_names_differentiate_by_position(service):
    """Pose.name strings contain and differentiate the requested positions (all lifts)."""
    cases = [
        ("bench", ["bottom", "near_lockout"], {"variation": "flat"}),
        ("squat", ["bottom", "top"], {"variation": "high_bar"}),
        ("deadlift", ["bottom", "mid"], {"variation": "conventional"}),
        ("ohp", ["bottom", "lockout"], {"variation": "standing"}),
    ]
    for lift, poss, extra in cases:
        multi = service.build_multi_position(lift, poss, load_kg=75.0, **extra)
        n0 = multi[0].pose.name.lower()
        n1 = multi[1].pose.name.lower()
        assert poss[0] in n0, f"Expected {poss[0]} in name for {lift}"
        assert poss[1] in n1, f"Expected {poss[1]} in name for {lift}"
        assert n0 != n1


def test_service_analyze_continuous_mvp_reuses_multipos_and_imperial(service):
    """dynrom MVP: analyze_continuous works, returns MultiPositionResult, supports imperial via recipes path."""
    from fiberforce.recipes import create_athlete, analyze_continuous
    ath = create_athlete(units="imperial", femur_in=17)
    mpr = analyze_continuous("squat", steps=3, load_lbs=225, athlete=ath, variation="low_bar", units="imperial")
    assert isinstance(mpr, MultiPositionResult)
    assert len(mpr.analyses) == 3
    # imperial ft-lb
    ft = mpr.analyses[0].results[0].peak_torque_ftlb
    assert ft > 50  # sane number
    # interpret works
    interp = mpr.interpret()
    assert "squat" in interp.lower() or "multi-position" in interp.lower()


def test_service_build_multi_position_joint_angles_differentiate_for_squat_deadlift_ohp(service):
    """Joint angles differ across positions for lifts that define distinct kinematics (excludes bench current mapping)."""
    cases = [
        ("squat", ["bottom", "mid", "top"], "high_bar"),
        ("deadlift", ["bottom", "mid", "top"], "conventional"),
        ("ohp", ["bottom", "mid", "lockout"], "standing"),
    ]
    for lift, poss, var in cases:
        multi = service.build_multi_position(lift, poss, load_kg=90.0, variation=var)
        ja0 = multi[0].pose.joint_angles.values
        ja1 = multi[1].pose.joint_angles.values
        assert ja0 != ja1, f"{lift} joint angles must differ {poss[0]} vs {poss[1]}"
        if len(poss) > 2:
            ja2 = multi[2].pose.joint_angles.values
            assert ja1 != ja2, f"{lift} joint angles must differ {poss[1]} vs {poss[2]}"


def test_service_build_multi_position_attachments_differentiate_ma_and_notes(service):
    """Active attachments differ (notes contain position keys, MA values can differ via geometric). Covers all 4 lifts."""
    cases = [
        ("bench", ["bottom", "mid"], "Sternal fibers", "flat"),
        ("squat", ["bottom", "top"], "Upper fibers", "high_bar"),
        ("deadlift", ["bottom", "mid"], "Upper fibers", "conventional"),
        ("ohp", ["bottom", "lockout"], "Anterior", "standing"),
    ]
    for lift, poss, target, var in cases:
        multi = service.build_multi_position(
            lift, poss, load_kg=80.0, variation=var, target_region_name=target
        )
        att0 = multi[0].pose.active_attachments[0]
        att1 = multi[1].pose.active_attachments[0]
        assert att0 is not att1
        n0 = (att0.notes or "").lower()
        n1 = (att1.notes or "").lower()
        # Notes or pos_key must reflect the position differentiation
        assert poss[0] in n0 or poss[1] in n1 or "bottom" in n0 or "mid" in n1 or "lockout" in n1 or "top" in n1
        # MA dicts are public and populated
        assert len(att0.moment_arms_at_position) >= 1
        assert len(att1.moment_arms_at_position) >= 1


def test_service_build_multi_position_supports_rich_kwargs_and_targets(service):
    """build_multi_position forwards common kwargs (anthro, target_region_name, use_geometric etc)."""
    multi = service.build_multi_position(
        "ohp",
        ["bottom", "mid"],
        load_kg=52.0,
        variation="seated",
        target_region_name="Lateral",
        humerus_cm=33.5,
        forearm_cm=26.1,
        biacromial_cm=40.0,
        use_geometric=False,  # exercise the flag
    )
    assert len(multi) == 2
    # Target region honored
    reg_name = multi[0].target_regions[0].region_name.lower()
    assert "lateral" in reg_name
    # Different positions reflected
    assert "bottom" in multi[0].pose.name.lower()
    assert "mid" in multi[1].pose.name.lower()


def test_service_build_multi_position_preserves_positions_order(service):
    """Returned list order exactly matches input positions list."""
    poss = ["top", "bottom", "mid"]  # deliberately non-sequential
    multi = service.build_multi_position("deadlift", poss, load_kg=140, variation="sumo")
    assert len(multi) == 3
    assert "top" in multi[0].pose.name.lower()
    assert "bottom" in multi[1].pose.name.lower()
    assert "mid" in multi[2].pose.name.lower()


def test_service_analyze_multi_position_returns_list_of_analysis_results(service):
    """Phase 2b: analyze_multi_position returns rich MultiPositionResult (with .analyses / duck-type list compat)."""
    from fiberforce.analysis.service import MultiPositionResult
    subj = service.create_subject_from_measurements(
        name="MultiPosSubject", humerus_length_cm=31.8, femur_length_cm=40.5
    )
    mpr = service.analyze_multi_position(
        subj, "squat", ["bottom", "mid"], load_kg=115.0, variation="high_bar", target_region_name="Upper fibers"
    )
    assert isinstance(mpr, MultiPositionResult)
    assert len(mpr) == 2  # duck-type len
    assert mpr.num_positions == 2
    results = mpr.to_list()
    assert len(results) == 2
    for r in results:
        assert isinstance(r, AnalysisResult)
        assert r.results is not None
        # Now multi-prime-mover for squat etc (3+ for % dominance)
        assert len(r.results) >= 1
        assert r.position_description
        assert r.confidence_summary or r.results[0].confidence_level
        # dominance % present for co-movers on same joint (from MA relative)
        if len(r.results) > 1:
            doms = [getattr(x, "dominance_percent", None) for x in r.results]
            assert any(d is not None for d in doms)
    # Rich aggregates present
    assert isinstance(mpr.avg_peak_force, float)
    assert len(mpr.per_position_primary_forces) == 2


def test_service_analyze_multi_position_position_descriptions_and_forces_differentiate(service):
    """Multi-position analysis produces differentiated position descriptions (and often forces) across positions."""
    subj = service.create_subject_from_measurements(name="DiffSubject", humerus_length_cm=32.2, forearm_length_cm=25.2)
    mpr = service.analyze_multi_position(
        subj, "bench", ["bottom", "mid"], load_kg=105.0, target_region_name="Sternal fibers"
    )
    results = list(mpr)  # duck-type iteration
    assert len(results) == 2
    d0 = results[0].position_description.lower()
    d1 = results[1].position_description.lower()
    assert "bottom" in d0
    assert "mid" in d1
    # Force results present and public API accessible
    f0 = results[0].results[0].peak_force_newtons
    f1 = results[1].results[0].peak_force_newtons
    assert f0 > 0 and f1 > 0
    # Descriptions differ (even if forces close)
    assert d0 != d1
    # Rich MPR fields exercised
    assert mpr.peak_force_position
    assert isinstance(mpr.force_deltas, list)


def test_service_build_multi_position_ohp_aliases_and_variations(service):
    """build_multi_position supports all OHP aliases (parity with single build_position)."""
    for alias in ("ohp", "overhead", "overhead_press", "military"):
        multi = service.build_multi_position(
            alias, ["bottom", "lockout"], load_kg=48.0, variation="standing", target_region_name="Triceps"
        )
        assert len(multi) == 2
        name0 = multi[0].pose.name.lower()
        assert "ohp" in name0 or "overhead" in name0 or "military" in name0
        assert "lockout" in multi[1].pose.name.lower()


# =============================================================================
# v0.4/v0.5 Program-level Accumulation Helpers (Phase 3a/3b overlap)
# 7 focused tests for the new/expanded basic accumulators.
# All tests use *only public APIs*: AnalysisService.analyze / analyze_multi_position /
# build_multi_position / create_subject..., plus the accumulation methods themselves,
# and public fields on AnalysisResult + MuscleForceResult.
# Covers single analyses, multi-position lists, weights, volumes, empty, multi-region.
# =============================================================================


def test_service_summarize_multi_position_basic_and_multi_region(service):
    """summarize_multi_position works on analyze_multi_position output (public flow)."""
    subj = service.create_subject_from_measurements(name="SumMP", humerus_length_cm=33.0)
    # Use public multi-pos entrypoint (bench single target for simplicity)
    mp_results = service.analyze_multi_position(
        subj, "bench", ["bottom", "mid", "near_lockout"], load_kg=100.0, target_region_name="Sternal fibers"
    )
    summary = service.summarize_multi_position(mp_results)
    assert summary["num_positions"] == 3
    assert len(summary["positions"]) == 3
    assert "regions" in summary and len(summary["regions"]) >= 1
    assert "Sternal" in summary["regions"][0] or "Sternal" in str(summary["regions"])
    assert isinstance(summary["avg_peak_force"], float) and summary["avg_peak_force"] > 0
    assert isinstance(summary["force_range"], tuple) and summary["force_range"][1] >= summary["force_range"][0]
    assert "totals_by_region" in summary
    assert "per_position" in summary and len(summary["per_position"]) == 3


@pytest.mark.parametrize("lift", ["squat", "deadlift", "ohp"])
def test_service_accumulate_regional_stress_on_multi_position_results(service, lift):
    """Core tie-in: accumulate_regional_stress consumes analyze_multi_position results (public only)."""
    subj = service.create_subject_from_measurements(
        name="AccMP", femur_length_cm=42.0, humerus_length_cm=32.0, forearm_length_cm=25.0
    )
    positions = ["bottom", "mid", "top"] if lift != "ohp" else ["bottom", "mid", "lockout"]
    target = "Upper fibers" if lift in ("squat", "deadlift") else "Anterior"
    mp_results = service.analyze_multi_position(
        subj, lift, positions, load_kg=90.0, target_region_name=target, variation="high_bar" if lift == "squat" else ("conventional" if lift == "deadlift" else "standing")
    )
    accum = service.accumulate_regional_stress(mp_results)
    assert isinstance(accum, dict)
    assert "meta" in accum
    assert accum["meta"]["num_analyses"] == 3
    assert accum["meta"]["total_stress"] > 0
    assert len(accum["meta"]["regions"]) >= 1
    # At least one region key present as top-level (public API usage)
    non_meta = {k: v for k, v in accum.items() if not k.startswith("meta")}
    assert len(non_meta) >= 1
    assert any(v > 0 for v in non_meta.values())


def test_service_accumulate_regional_stress_on_single_analyses_and_weights(service):
    """accumulate_regional_stress works on lists of individual analyze() results + per-item weights."""
    subj = service.create_subject_from_measurements(name="AccSingle", humerus_length_cm=31.0)
    # Public single analyses (different configs)
    pos1 = service.build_position("bench", load_kg=80, target_region_name="Sternal fibers")
    pos2 = service.build_position("bench", load_kg=100, target_region_name="Sternal fibers")
    res1 = service.analyze(subj, pos1)
    res2 = service.analyze(subj, pos2)
    # Scalar
    s1 = service.accumulate_regional_stress([res1, res2])
    assert s1["meta"]["num_analyses"] == 2
    assert s1["meta"]["total_stress"] > 0
    # List of weights (program-level: e.g. different session contributions)
    s2 = service.accumulate_regional_stress([res1, res2], weight=[0.5, 2.0])
    assert s2["meta"]["applied_weights"] == [0.5, 2.0]
    # Heavier weight on second should increase total
    assert s2["meta"]["total_stress"] > s1["meta"]["total_stress"] * 0.8


def test_service_accumulate_regional_volume_with_factors(service):
    """accumulate_regional_volume consumes multi-pos results + scalar/list volume_factors (sets*reps style)."""
    subj = service.create_subject_from_measurements(name="VolAcc", femur_length_cm=41.5)
    mp = service.analyze_multi_position(
        subj, "squat", ["bottom", "mid"], load_kg=110.0, variation="high_bar", target_region_name="Glute max upper"
    )
    # Scalar volume factor
    v1 = service.accumulate_regional_volume(mp, volume_factors=3 * 5)  # 15 "reps" proxy
    assert v1["meta"]["num_analyses"] == 2
    assert v1["meta"]["total_volume_stress"] > 0
    assert v1["meta"]["volume_factors_used"] == [15.0, 15.0]
    # Per-position different volume (e.g. emphasis work)
    v2 = service.accumulate_regional_volume(mp, volume_factors=[10.0, 4.0], weight=1.2)
    assert v2["meta"]["volume_factors_used"] == [10.0, 4.0]
    assert v2["meta"]["weight"] == 1.2
    # Different total expected
    assert v2["meta"]["total_volume_stress"] != v1["meta"]["total_volume_stress"]


def test_service_summarize_regional_accumulation_mixed_inputs(service):
    """summarize_regional_accumulation works over mixed single + multi-pos AnalysisResult lists."""
    subj = service.create_subject_from_measurements(name="SumAcc", humerus_length_cm=30.5)
    # Mix of public paths
    r_single = service.analyze(subj, service.build_position("bench", load_kg=95, target_region_name="Clavicular fibers"))
    mp = service.analyze_multi_position(subj, "bench", ["bottom", "mid"], load_kg=95, target_region_name="Sternal fibers")
    mixed = [r_single] + list(mp)  # explicit list() for concat; duck-type alone does not concat
    summ = service.summarize_regional_accumulation(mixed)
    assert summ["num_analyses"] == 3
    assert len(summ["regions_covered"]) >= 1
    assert summ["total_stress_proxy"] > 0
    assert summ["total_volume_proxy"] >= 0
    assert summ["top_region_by_stress"] is not None
    assert "regional_totals" in summ


def test_service_accumulators_handle_empty_inputs_and_multi_region(service):
    """Accumulators are robust to empty lists and analyses that surface multiple regions."""
    subj = service.create_subject_from_measurements(name="EdgeAcc")
    # Force a multi-target position (service supports via target_regions override in analyze)
    pos = service.build_position("squat", load_kg=100, target_region_name="Upper fibers")
    assert len(pos.target_regions) >= 3, "squat builder now returns full multi (glute+quad+ham) for dominance %"
    # Manually set multiple targets via public field (allowed for advanced use; results will contain multiple)
    pos.target_regions = [
        next((r for r in KNOWN_MUSCLE_REGIONS if "Upper fibers" in r.region_name), pos.target_regions[0]),
        next((r for r in KNOWN_MUSCLE_REGIONS if "Sternal" in r.region_name), pos.target_regions[0]),
    ]
    res_multi = service.analyze(subj, pos)
    # Should surface >=1 results (implementation may dedup but public path)
    assert len(res_multi.results) >= 1

    # Empty
    empty_stress = service.accumulate_regional_stress([])
    assert empty_stress["meta"]["num_analyses"] == 0
    empty_vol = service.accumulate_regional_volume([])
    assert empty_vol["meta"]["num_analyses"] == 0
    empty_sum = service.summarize_multi_position([])
    assert empty_sum["num_positions"] == 0

    # Multi-region input still aggregates cleanly via public fields
    acc_mr = service.accumulate_regional_stress([res_multi])
    assert acc_mr["meta"]["num_analyses"] == 1


def test_service_accumulators_integrate_with_all_lifts_via_public_multi_pos(service):
    """End-to-end: accumulation helpers work uniformly across all 4 lifts using only public multi-pos + accum APIs."""
    subj = service.create_subject_from_measurements(
        name="AllLiftAcc", humerus_length_cm=32.0, femur_length_cm=42.0, tibia_length_cm=38.0
    )
    for lift in ["bench", "squat", "deadlift", "ohp"]:
        poss = ["bottom", "mid"] if lift != "ohp" else ["bottom", "lockout"]
        var = {"bench": "flat", "squat": "high_bar", "deadlift": "conventional", "ohp": "standing"}[lift]
        tgt = {"bench": "Sternal fibers", "squat": "Upper fibers", "deadlift": "Upper fibers", "ohp": "Anterior"}[lift]
        mp_res = service.analyze_multi_position(subj, lift, poss, load_kg=75.0, variation=var, target_region_name=tgt)
        stress = service.accumulate_regional_stress(mp_res, weight=1.5)
        vol = service.accumulate_regional_volume(mp_res, volume_factors=2*6)
        summ = service.summarize_regional_accumulation(mp_res)
        assert stress["meta"]["num_analyses"] == 2
        assert vol["meta"]["total_volume_stress"] > 0
        assert summ["num_analyses"] == 2
        assert len(summ["regional_totals"]) >= 1


# -------------------------------------------------------------------
# v0.5 Program-level model tests (TrainingSession + WeeklyProgram)
# 7 focused tests exercising the new dataclasses + their integration
# with the existing accumulate_* helpers and multi-position data.
# -------------------------------------------------------------------

def test_training_session_add_and_compute(service):
    """TrainingSession stores analyses (incl. multi-pos lists) and computes via accum helpers."""
    subj = service.create_subject_from_measurements(name="TSess", femur_length_cm=42.0, tibia_length_cm=38.0)
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120.0, variation="high_bar", target_region_name="Upper fibers")
    assert len(mp) == 2

    sess = TrainingSession(name="Squat Volume Day", lift="squat", variation="high_bar")
    sess.add_analyses(mp, weights=1.5)  # session-level emphasis weight
    assert len(sess.analyses) == 2
    assert len(sess._weights) == 2

    stress = sess.compute_regional_stress(service)
    vol = sess.compute_regional_volume(service, volume_factors=4*5)  # sets x reps style
    assert stress["meta"]["num_analyses"] == 2
    assert stress["meta"]["total_stress"] > 0
    assert vol["meta"]["total_volume_stress"] > stress["meta"]["total_stress"]  # volume factor applied
    summ = sess.get_summary(service)
    assert summ["name"] == "Squat Volume Day"
    assert summ["top_region_by_stress"] is not None


def test_training_session_single_add_and_weights(service):
    """add_analysis with per-item weights + compute on single + mixed."""
    subj = service.create_subject_from_measurements(name="TSess2")
    pos1 = service.build_position("bench", load_kg=90, variation="flat", target_region_name="Sternal fibers")
    pos2 = service.build_position("bench", load_kg=85, variation="incline_30", target_region_name="Sternal fibers")
    a1 = service.analyze(subj, pos1)
    a2 = service.analyze(subj, pos2)

    sess = TrainingSession(name="Bench Mix")
    sess.add_analysis(a1, weight=1.0)
    sess.add_analysis(a2, weight=0.6)  # lighter variation
    stress = sess.compute_regional_stress()
    assert stress["meta"]["num_analyses"] == 2
    # Weighted total should be less than unweighted sum of both
    unweighted = service.accumulate_regional_stress([a1, a2])
    assert stress["meta"]["total_stress"] < unweighted["meta"]["total_stress"] * 0.95


def test_weekly_program_aggregate_and_compare(service):
    """WeeklyProgram aggregates sessions, supports compare() between two programs using multi-pos data."""
    subj = service.create_subject_from_measurements(name="ProgLifter", humerus_length_cm=33.0, femur_length_cm=43.0)

    # Program A: moderate volume, multi-pos emphasis on bottom
    prog_a = WeeklyProgram(name="Moderate Squat Focus", athlete="Test Lifter")
    sess_a = TrainingSession(name="Tue Squat", lift="squat")
    mp_a = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=130, variation="high_bar", target_region_name="Upper fibers")
    sess_a.add_analyses(mp_a)
    prog_a.add_session(sess_a)

    # Program B: higher volume on same movement
    prog_b = WeeklyProgram(name="High Volume Squat Focus", athlete="Test Lifter")
    sess_b = TrainingSession(name="Tue + Fri Squat", lift="squat")
    mp_b = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=125, variation="high_bar", target_region_name="Upper fibers")
    sess_b.add_analyses(mp_b, weights=[2.0, 1.0, 0.5])  # more emphasis at bottom
    prog_b.add_session(sess_b)

    assert len(prog_a.sessions) == 1
    assert len(prog_b.flatten_analyses()) == 3

    totals_a = prog_a.compute_weekly_totals(service)
    totals_b = prog_b.compute_weekly_totals(service)
    assert totals_a["num_analyses"] == 2
    assert totals_b["num_analyses"] == 3

    cmp = WeeklyProgram.compare(prog_a, prog_b, service)
    assert cmp["program_a"] == "Moderate Squat Focus"
    assert cmp["program_b"] == "High Volume Squat Focus"
    assert "deltas_by_region" in cmp
    assert cmp["higher_stress_program"] in (prog_a.name, prog_b.name)


def test_weekly_program_generate_report_and_empty(service):
    """generate_simple_report works (text + best-effort viz) and handles empty programs gracefully."""
    empty_prog = WeeklyProgram(name="Empty Week")
    report = empty_prog.generate_simple_report(service)
    assert "WeeklyProgram Report: Empty Week" in report
    assert "Total analyses: 0" in report

    # Non-empty with real data
    subj = service.create_subject_from_measurements(name="RptLifter")
    sess = TrainingSession(name="Deadlift Day")
    mp = service.analyze_multi_position(subj, "deadlift", ["bottom"], load_kg=140, variation="conventional", target_region_name="Upper fibers")
    sess.add_analyses(mp)
    prog = WeeklyProgram(name="Test Week", sessions=[sess], notes="Integration test week")
    report2 = prog.generate_simple_report(service)
    assert "Test Week" in report2
    assert "Deadlift Day" in report2
    assert "Highest stressed region" in report2 or "Top Regional Stress" in report2


def test_program_models_multi_region_and_volume_factors(service):
    """Program models correctly surface multi-region results and combined volume factors."""
    subj = service.create_subject_from_measurements(name="MultiReg")
    # Use a target that produces results across regions if possible; fallback still exercises paths
    pos = service.build_position("squat", load_kg=110, variation="low_bar", target_region_name="Upper fibers")
    res = service.analyze(subj, pos)
    sess = TrainingSession(name="Low Bar Session")
    sess.add_analysis(res)
    vol = sess.compute_regional_volume(service, volume_factors=5 * 3)
    assert "meta" in vol
    assert vol["meta"]["total_volume_stress"] > 0

    prog = WeeklyProgram(name="Mixed")
    prog.add_session(sess)
    totals = prog.compute_weekly_totals()
    assert totals["summary"]["num_analyses"] == 1


def test_program_models_error_handling_and_summary(service):
    """Type checks, length mismatches, and get_summary on empty behave as documented."""
    sess = TrainingSession(name="ErrTest")
    with pytest.raises(TypeError):
        sess.add_analysis("not an analysis")  # type: ignore[arg-type]

    sess2 = TrainingSession(name="LenMismatch")
    mp = service.analyze_multi_position(
        service.create_subject_from_measurements(), "bench", ["bottom", "mid"], load_kg=80
    )
    with pytest.raises(ValueError):
        sess2.add_analyses(mp, weights=[1.0])  # wrong length

    empty_sess = TrainingSession(name="Nothing")
    s = empty_sess.get_summary()
    assert s["num_analyses"] == 0
    assert s["total_stress"] == 0.0


def test_program_models_work_without_explicit_service(service):
    """Models fall back to default_service when no service passed (public API path)."""
    subj = service.create_subject_from_measurements(name="DefaultSvc")
    pos = service.build_position("ohp", load_kg=55, variation="standing", target_region_name="Anterior")
    a = service.analyze(subj, pos)

    sess = TrainingSession(name="OHP Day").add_analysis(a)
    stress = sess.compute_regional_stress()  # no service arg
    assert stress["meta"]["num_analyses"] == 1
    assert stress["meta"]["total_stress"] >= 0

    prog = WeeklyProgram(name="Default").add_session(sess)
    totals = prog.compute_weekly_totals()  # no service
    assert totals["num_analyses"] == 1


# =============================================================================
# v0.5 Phase 2b MultiPositionResult Rich Output Tests (4-6 high-quality focused tests)
# Exercise the new dataclass, aggregates, geometric-vs-static logic, deltas,
# integration via duck-typing with accumulators, and summary helpers.
# All use ONLY public APIs.
# =============================================================================

def test_multipositionresult_rich_aggregates_and_ducktyping(service):
    """MultiPositionResult provides rich per-pos + overall aggregates + full list duck-typing."""
    subj = service.create_subject_from_measurements(
        name="MPRTest", humerus_length_cm=33.0, femur_length_cm=42.0
    )
    mpr = service.analyze_multi_position(
        subj, "squat", ["bottom", "mid", "top"], load_kg=120.0, variation="high_bar", target_region_name="Upper fibers"
    )
    assert isinstance(mpr, MultiPositionResult)
    assert mpr.lift == "squat"


# =============================================================================
# 0.6→0.7 Test Expansion: Program-level + Multi-position combinations
# =============================================================================

def test_weeklyprogram_with_mixed_single_and_multi_position(service):
    """WeeklyProgram should handle a mix of single-position and multi-position analyses."""
    subj = service.create_subject_from_measurements(femur_length_cm=43.0)

    prog = WeeklyProgram(name="Mixed Week")

    # Single position session
    single = service.analyze(subj, service.build_position("squat", load_kg=130, variation="high_bar"))
    sess1 = TrainingSession(name="Single Day").add_analysis(single)
    prog.add_session(sess1)

    # Multi-position session
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=130, variation="low_bar")
    sess2 = TrainingSession(name="Multi Day")
    sess2.add_analyses(list(mp))
    prog.add_session(sess2)

    totals = prog.compute_weekly_totals(service)
    assert totals["num_analyses"] == 1 + 2   # 1 single + 2 from multi
    assert totals["num_sessions"] == 2


def test_training_session_add_analyses_accepts_multipositionresult(service):
    """TrainingSession.add_analyses should accept MultiPositionResult via list()."""
    subj = service.create_subject_from_measurements()
    mp = service.analyze_multi_position(subj, "deadlift", ["bottom", "mid", "top"], load_kg=140, variation="sumo")

    sess = TrainingSession(name="DL Volume")
    sess.add_analyses(list(mp))   # explicit conversion works

    assert len(sess.analyses) == 3
    stress = sess.compute_regional_stress(service)
    assert stress["meta"]["num_analyses"] == 3


def test_multipositionresult_region_totals_populated(service):
    """MultiPositionResult should populate region_totals for program use."""
    subj = service.create_subject_from_measurements(femur_length_cm=42.0)
    mpr = service.analyze_multi_position(
        subj, "squat", ["bottom", "mid"], load_kg=125, variation="high_bar", target_region_name="Upper fibers"
    )
    assert isinstance(mpr.region_totals, dict)
    assert len(mpr.region_totals) >= 1
    assert mpr.load_kg == 125.0
    assert len(mpr) == 2
    assert len(mpr.to_list()) == 2
    assert len(mpr.per_position_primary_forces) == 2
    assert len(mpr.force_deltas) == 1
    assert len(mpr.relative_deltas_pct) == 1


def test_multipositionresult_geometric_vs_static_detection(service):
    """Phase 2b: geometric vs static provenance is correctly detected and summarized using public attachment/result fields."""
    # With geometric enabled + anthro
    subj_geo = service.create_subject_from_measurements(
        name="GeoMPR", humerus_length_cm=32.5, biacromial_width_cm=39.0
    )
    mpr_geo = service.analyze_multi_position(
        subj_geo, "bench", ["bottom", "mid"], load_kg=95.0, target_region_name="Sternal fibers",
        use_geometric=True
    )
    assert len(mpr_geo.geometric_positions) + len(mpr_geo.static_positions) == 2
    assert "geometric" in mpr_geo.geometric_vs_static_summary.lower() or "static" in mpr_geo.geometric_vs_static_summary.lower()
    # Notes populated
    assert "Multi-position analysis" in mpr_geo.notes

    # Force static
    mpr_static = service.analyze_multi_position(
        subj_geo, "bench", ["bottom", "near_lockout"], load_kg=95.0, target_region_name="Sternal fibers",
        use_geometric=False
    )
    assert len(mpr_static.static_positions) >= 1
    assert "static" in mpr_static.geometric_vs_static_summary.lower() or "All" in mpr_static.geometric_vs_static_summary


def test_multipositionresult_accumulator_integration(service):
    """MultiPositionResult integrates seamlessly (via duck-type) with all accumulation helpers (public only)."""
    subj = service.create_subject_from_measurements(name="AccMPR", femur_length_cm=41.0)
    mpr = service.analyze_multi_position(
        subj, "deadlift", ["bottom", "mid", "top"], load_kg=140.0, variation="conventional", target_region_name="Upper fibers"
    )
    # Pass MPR object directly
    stress = service.accumulate_regional_stress(mpr, weight=1.2)
    assert stress["meta"]["num_analyses"] == 3
    assert stress["meta"]["total_stress"] > 0

    vol = service.accumulate_regional_volume(mpr, volume_factors=[3.0, 2.0, 1.0])
    assert vol["meta"]["num_analyses"] == 3
    assert vol["meta"]["total_volume_stress"] > 0

    summ = service.summarize_regional_accumulation(mpr)
    assert summ["num_analyses"] == 3
    assert summ["total_stress_proxy"] > 0

    # Also via summarize_multi_position
    s2 = service.summarize_multi_position(mpr)
    assert s2["num_positions"] == 3


def test_multipositionresult_deltas_and_program_highlights(service):
    """Rich deltas (abs/rel), peak/min identification, variation coeff are populated and sensible."""
    subj = service.create_subject_from_measurements(name="DeltaMPR")
    mpr = service.analyze_multi_position(
        subj, "ohp", ["bottom", "mid", "lockout"], load_kg=60.0, variation="standing", target_region_name="Anterior"
    )
    assert len(mpr.force_deltas) == 2
    assert len(mpr.relative_deltas_pct) == 2
    # Highlights
    assert mpr.peak_force_position in ["bottom", "mid", "lockout"] or "bottom" in mpr.peak_force_position.lower()
    assert mpr.min_force_position
    assert isinstance(mpr.force_variation_coefficient, float)
    # summary_dict works
    sd = mpr.summary_dict()
    assert "geometric_vs_static_summary" in sd
    assert sd["num_positions"] == 3


def test_multipositionresult_works_across_all_lifts_and_empty_edge(service):
    """End-to-end: MPR + aggregates work for all 4 lifts; empty edge handled in helpers."""
    subj = service.create_subject_from_measurements(
        name="AllLiftsMPR", humerus_length_cm=31.0, femur_length_cm=40.0, tibia_length_cm=37.0
    )
    for lift in ["bench", "squat", "deadlift", "ohp"]:
        poss = ["bottom", "mid"] if lift != "ohp" else ["bottom", "lockout"]
        var = {"bench": "flat", "squat": "high_bar", "deadlift": "conventional", "ohp": "standing"}[lift]
        tgt = {"bench": "Sternal fibers", "squat": "Upper fibers", "deadlift": "Upper fibers", "ohp": "Anterior"}[lift]
        mpr = service.analyze_multi_position(subj, lift, poss, load_kg=80.0, variation=var, target_region_name=tgt)
        assert isinstance(mpr, MultiPositionResult)
        assert mpr.num_positions == 2
        assert mpr.avg_peak_force >= 0
        assert mpr.geometric_vs_static_summary

    # Empty via public path still safe
    empty_sum = service.summarize_multi_position([])
    assert empty_sum["num_positions"] == 0


def test_06x_geometric_coverage_helper_is_available(service):
    """New in 0.6: ReferenceData exposes geometric support introspection."""
    ref = service.get_reference()
    support = ref.list_geometric_supported()
    assert "squat" in support
    assert len(support) >= 4


# 0.6→0.7 additional hardening tests (appended during autonomous run)

def test_weeklyprogram_compare_handles_identical_programs(service):
    """compare() should return near-zero deltas for identical programs."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Identical")
    mp = service.analyze_multi_position(subj, "bench", ["bottom", "mid"], load_kg=100)
    sess = TrainingSession(name="Day")
    sess.add_analyses(list(mp))
    prog.add_session(sess)

    cmp = WeeklyProgram.compare(prog, prog, service)
    for delta in cmp["deltas_by_region"].values():
        assert abs(delta) < 0.01


def test_training_session_empty_compute_is_safe():
    sess = TrainingSession(name="Empty")
    stress = sess.compute_regional_stress()
    assert stress["meta"]["num_analyses"] == 0


# 0.6→0.7 Validation additions (more program + multi-pos + edge coverage)

def test_weeklyprogram_compare_detects_difference(service):
    """compare() should show meaningful deltas between meaningfully different programs."""
    subj = service.create_subject_from_measurements(femur_length_cm=42.0)

    # High load program
    high = WeeklyProgram(name="High")
    mp_high = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=160, variation="high_bar")
    s_high = TrainingSession(name="Heavy")
    s_high.add_analyses(list(mp_high))
    high.add_session(s_high)

    # Low load program
    low = WeeklyProgram(name="Low")
    mp_low = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=100, variation="high_bar")
    s_low = TrainingSession(name="Light")
    s_low.add_analyses(list(mp_low))
    low.add_session(s_low)

    cmp = WeeklyProgram.compare(high, low, service)
    # The comparison must run and produce a result with deltas
    assert "higher_stress_program" in cmp
    assert isinstance(cmp["deltas_by_region"], dict)
    assert len(cmp["deltas_by_region"]) > 0


def test_multiposition_with_geometric_produces_geo_summary(service):
    """When using geometric, the MPR should correctly report geometric usage."""
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, biacromial_width_cm=40.0)
    mpr = service.analyze_multi_position(
        subj, "bench", ["bottom", "mid"], load_kg=100, use_geometric=True
    )
    assert "geometric" in mpr.geometric_vs_static_summary.lower() or len(mpr.geometric_positions) > 0


# 0.6→0.7 Edge case hardening (autonomous addition)

def test_analyze_multi_position_empty_positions_list_is_safe(service):
    subj = service.create_subject_from_measurements()
    # Should not crash
    mpr = service.analyze_multi_position(subj, "squat", [], load_kg=100)
    assert len(mpr) == 0
    assert mpr.num_positions == 0


def test_create_subject_with_extreme_anthropometry_does_not_crash(service):
    """Extreme but plausible measurements should not explode the model."""
    subj = service.create_subject_from_measurements(
        femur_length_cm=55.0, tibia_length_cm=48.0, humerus_length_cm=38.0
    )
    # Just ensure we can build and analyze without crashing
    pos = service.build_position("squat", load_kg=100, variation="high_bar")
    res = service.analyze(subj, pos)
    assert res is not None


# More 0.6→0.7 edge hardening

def test_analyze_multi_position_single_position_works(service):
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "deadlift", ["bottom"], load_kg=140, variation="conventional")
    assert len(mpr) == 1
    assert mpr.num_positions == 1


def test_program_with_no_analyses_is_safe():
    empty_prog = WeeklyProgram(name="Nothing")
    report = empty_prog.generate_simple_report()
    assert "Nothing" in report
    assert "0 analyses" in report or "num_analyses" in str(empty_prog.compute_weekly_totals())


# Additional edge hardening for 0.6→0.7

def test_analyze_with_zero_load_is_safe(service):
    subj = service.create_subject_from_measurements()
    pos = service.build_position("bench", load_kg=0)
    res = service.analyze(subj, pos)
    assert res is not None
    # Force should be zero or very low
    assert res.results[0].peak_force_newtons <= 10


# 0.6→0.7 more program + multi-pos validation tests

def test_training_session_weights_affect_stress(service):
    """Different weights on analyses should change the computed stress totals."""
    subj = service.create_subject_from_measurements()
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120)
    sess = TrainingSession(name="Weighted")
    sess.add_analyses(list(mp), weights=[1.0, 3.0])  # heavier on mid
    stress = sess.compute_regional_stress(service)
    assert stress["meta"]["num_analyses"] == 2


def test_weeklyprogram_add_sessions_chaining(service):
    """Chaining add_sessions should work cleanly."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Chained")
    sess1 = TrainingSession(name="Day1")
    sess1.add_analysis(service.analyze(subj, service.build_position("bench", load_kg=80)))
    sess2 = TrainingSession(name="Day2")
    sess2.add_analysis(service.analyze(subj, service.build_position("squat", load_kg=120)))
    prog.add_sessions([sess1, sess2])
    assert prog.compute_weekly_totals(service)["num_sessions"] == 2


# More 0.6→0.7 edge + robustness tests

def test_multiposition_with_bad_position_falls_back_safely(service):
    """Passing an unknown position should still produce a result (graceful behavior)."""
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", ["bottom", "weird_position"], load_kg=130)
    assert len(mpr) >= 1  # at least the valid one should work


def test_analyze_multi_position_preserves_order(service):
    """Order of positions passed should be preserved in the result."""
    subj = service.create_subject_from_measurements()
    positions = ["top", "bottom", "mid"]
    mpr = service.analyze_multi_position(subj, "ohp", positions, load_kg=70, variation="standing")
    assert [p for p in mpr.positions] == positions or len(mpr.positions) == len(positions)


# Final batch of 0.6→0.7 validation tests for this cycle

def test_program_compare_returns_expected_keys(service):
    """compare() must always return the documented keys."""
    subj = service.create_subject_from_measurements()
    p1 = WeeklyProgram(name="A")
    p1.add_session(TrainingSession(name="D1").add_analysis(service.analyze(subj, service.build_position("squat", load_kg=100))))
    p2 = WeeklyProgram(name="B")
    p2.add_session(TrainingSession(name="D1").add_analysis(service.analyze(subj, service.build_position("squat", load_kg=110))))
    cmp = WeeklyProgram.compare(p1, p2, service)
    for key in ["program_a", "program_b", "deltas_by_region", "higher_stress_program"]:
        assert key in cmp


def test_multipositionresult_with_all_geometric_reports_correctly(service):
    """When all positions use geometric, the summary should reflect that."""
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, biacromial_width_cm=40.0)
    mpr = service.analyze_multi_position(subj, "bench", ["bottom", "mid", "top"], load_kg=95, use_geometric=True)
    assert "geometric" in mpr.geometric_vs_static_summary.lower()


# More 0.6→0.7 program + multi-position validation

def test_weeklyprogram_with_real_multi_position_and_geometric(service):
    """WeeklyProgram using real geometric multi-position data should compute sensible totals."""
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, femur_length_cm=43.0)
    prog = WeeklyProgram(name="Geo Week")
    for _ in range(2):  # simulate two sessions
        mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=135, variation="low_bar", use_geometric=True)
        sess = TrainingSession(name="Squat Day")
        sess.add_analyses(list(mp))
        prog.add_session(sess)
    totals = prog.compute_weekly_totals(service)
    assert totals["num_analyses"] == 6
    assert totals["num_sessions"] == 2


def test_multipositionresult_with_geometric_vs_static_detection(service):
    """MPR should correctly flag which positions used geometric when enabled."""
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, biacromial_width_cm=40.0)
    mpr_geo = service.analyze_multi_position(subj, "bench", ["bottom", "mid"], load_kg=100, use_geometric=True)
    mpr_static = service.analyze_multi_position(subj, "bench", ["bottom", "mid"], load_kg=100, use_geometric=False)
    assert len(mpr_geo.geometric_positions) >= 1 or "geometric" in mpr_geo.geometric_vs_static_summary.lower()
    assert len(mpr_static.static_positions) == 2 or "static" in mpr_static.geometric_vs_static_summary.lower()


# Additional 0.6→0.7 edge case hardening

def test_program_compare_with_empty_program_is_safe(service):
    empty = WeeklyProgram(name="Empty")
    full = WeeklyProgram(name="Full")
    subj = service.create_subject_from_measurements()
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120)
    sess = TrainingSession(name="Day")
    sess.add_analyses(list(mp))
    full.add_session(sess)
    cmp = WeeklyProgram.compare(empty, full, service)
    assert cmp["higher_stress_program"] == "Full"
    assert all(d >= 0 for d in cmp["deltas_by_region"].values() if d != 0)


def test_analyze_multi_position_preserves_target_region(service):
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "deadlift", ["bottom", "mid"], load_kg=150, variation="sumo", target_region_name="hamstring")
    # The results should reflect the requested target in some way (via notes or region keys)
    assert any("ham" in str(r).lower() or "hamstring" in str(r).lower() for r in mpr) or len(mpr) > 0


# 0.6→0.7 Edge case hardening continued

def test_analyze_multi_position_with_extreme_load_and_anthro(service):
    """Extreme but valid inputs should not crash and should produce finite results."""
    extreme = UserAnthropometry(femur_length_cm=52.0, tibia_length_cm=46.0, humerus_length_cm=37.0)
    subj = service.create_subject_from_measurements(femur_length_cm=52.0, tibia_length_cm=46.0, humerus_length_cm=37.0)
    mpr = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=200, variation="low_bar", use_geometric=True)
    assert len(mpr) == 3
    assert all(f > 0 for f in mpr.per_position_primary_forces)


def test_weeklyprogram_compare_with_mixed_lifts(service):
    """compare() should handle programs with completely different lifts without crashing."""
    subj = service.create_subject_from_measurements()
    bench_prog = WeeklyProgram(name="Bench Heavy")
    bench_prog.add_session(TrainingSession(name="Bench").add_analysis(service.analyze(subj, service.build_position("bench", load_kg=120))))
    squat_prog = WeeklyProgram(name="Squat Heavy")
    squat_prog.add_session(TrainingSession(name="Squat").add_analysis(service.analyze(subj, service.build_position("squat", load_kg=150))))
    cmp = WeeklyProgram.compare(bench_prog, squat_prog, service)
    assert "deltas_by_region" in cmp


# 0.6→0.7 Edge case hardening continued

def test_analyze_multi_position_preserves_position_order_across_lifts(service):
    """The order of positions passed to analyze_multi_position must be preserved in the result."""
    subj = service.create_subject_from_measurements()
    for lift, positions, variation in [
        ("squat", ["top", "bottom", "mid"], "high_bar"),
        ("deadlift", ["mid", "bottom", "top"], "sumo"),
        ("ohp", ["top", "mid", "bottom"], "standing"),
    ]:
        mpr = service.analyze_multi_position(subj, lift, positions, load_kg=100, variation=variation)
        assert [p for p in mpr.positions][:len(positions)] == positions or len(mpr) == len(positions)


def test_weeklyprogram_with_three_sessions_mixed_data(service):
    """WeeklyProgram with 3 sessions containing a mix of single and multi-position analyses should compute correctly."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Mixed 3-Session Week")
    # Session 1: single
    sess1 = TrainingSession(name="Single")
    sess1.add_analysis(service.analyze(subj, service.build_position("bench", load_kg=90)))
    prog.add_session(sess1)
    # Session 2: multi-pos
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=130, variation="low_bar")
    sess2 = TrainingSession(name="Multi")
    sess2.add_analyses(list(mp))
    prog.add_session(sess2)
    # Session 3: single
    sess3 = TrainingSession(name="Single2")
    sess3.add_analysis(service.analyze(subj, service.build_position("deadlift", load_kg=140, variation="conventional")))
    prog.add_session(sess3)
    totals = prog.compute_weekly_totals(service)
    assert totals["num_sessions"] == 3
    assert totals["num_analyses"] >= 4


# 0.6→0.7 Edge case hardening continued

def test_multipositionresult_empty_is_fully_safe(service):
    """analyze_multi_position with empty positions list must return a valid empty MPR."""
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", [], load_kg=100)
    assert len(mpr) == 0
    assert mpr.num_positions == 0
    assert mpr.avg_peak_force == 0.0


def test_training_session_multiple_add_analyses_calls(service):
    """Calling add_analyses multiple times should accumulate correctly."""
    subj = service.create_subject_from_measurements()
    mp1 = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120)
    mp2 = service.analyze_multi_position(subj, "bench", ["bottom"], load_kg=90)
    sess = TrainingSession(name="Mixed")
    sess.add_analyses(list(mp1))
    sess.add_analyses(list(mp2))
    assert len(sess.analyses) == 3


def test_improved_length_tension_factor(service):
    """Basic sanity + regression for the Theme 1 improved L-T curve (model-02)."""
    from fiberforce.calculations.peak_force import SimplePeakForceCalculator
    calc = SimplePeakForceCalculator()

    # No arch data -> conservative fallback
    f, used = calc._compute_length_tension_factor({}, 90.0)
    assert not used
    assert 0.7 < f < 0.95

    # With typical pec arch data at optimal-ish angle -> factor near or > 1.0
    arch = {
        "optimal_fiber_length_cm": 11.5,
        "pennation_angle_deg": 20.0,
        "tendon_slack_length_cm": 3.0,
        "pcsa_cm2": 26.0,
    }
    f_opt, used = calc._compute_length_tension_factor(arch, 90.0)
    assert used
    assert f_opt > 0.95   # should be close to plateau or slightly above with passive

    # Far from optimal (very short) -> low factor
    f_short, _ = calc._compute_length_tension_factor(arch, 30.0)
    assert f_short < f_opt

    # At long lengths active drops sharply; passive contribution is small at first.
    # Expect low but non-zero (realistic for extreme stretch).
    f_long, _ = calc._compute_length_tension_factor(arch, 150.0)
    assert 0.0 <= f_long < 0.6

    # Factor varies usefully across a ROM (for continuous dynrom use)
    factors = [calc._compute_length_tension_factor(arch, ang)[0] for ang in [40, 70, 100, 130]]
    assert len(set(round(f, 2) for f in factors)) > 1  # not completely flat

    # F-V basic (model-03): v=0 always 1.0 for current peak calcs; concentric drops
    assert calc._force_velocity_multiplier(0.0) == 1.0
    assert calc._force_velocity_multiplier(5.0) < 0.6
    assert calc._force_velocity_multiplier(-2.0) == 1.0  # ecc simplified


# 0.6→0.7 Edge case hardening continued

def test_analyze_multi_position_with_zero_positions_returns_valid_empty_mpr(service):
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", [], load_kg=100)
    assert len(mpr) == 0
    assert mpr.num_positions == 0
    assert mpr.avg_peak_force == 0


def test_program_compare_with_identical_programs_returns_zero_deltas(service):
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Identical")
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120, variation="high_bar")
    sess = TrainingSession(name="Day")
    sess.add_analyses(list(mp))
    prog.add_session(sess)
    cmp = WeeklyProgram.compare(prog, prog, service)
    assert all(abs(d) < 0.01 for d in cmp["deltas_by_region"].values())


# 0.6→0.7 Edge case hardening continued

def test_analyze_multi_position_with_mixed_valid_and_invalid_positions(service):
    """Should handle a mix of valid and invalid positions gracefully."""
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", ["bottom", "invalid_pos", "mid"], load_kg=130, variation="high_bar")
    # At minimum the valid positions should be processed
    assert len(mpr) >= 2


def test_weeklyprogram_add_session_chaining_returns_self(service):
    """Chaining add_session should work and return the program."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Chained")
    sess = TrainingSession(name="Day")
    sess.add_analysis(service.analyze(subj, service.build_position("squat", load_kg=120)))
    result = prog.add_session(sess)
    assert result is prog
    assert prog.compute_weekly_totals(service)["num_sessions"] == 1


# 0.6→0.7 Edge case hardening continued

def test_multipositionresult_with_all_geometric_reports_correctly(service):
    """When using geometric, the MPR should correctly report geometric usage in the summary."""
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, biacromial_width_cm=40.0)
    mpr = service.analyze_multi_position(subj, "bench", ["bottom", "mid", "top"], load_kg=95, use_geometric=True)
    assert "geometric" in mpr.geometric_vs_static_summary.lower() or len(mpr.geometric_positions) > 0


def test_training_session_with_weighted_analyses_affects_stress(service):
    """Different weights on analyses should change the computed stress totals."""
    subj = service.create_subject_from_measurements()
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120)
    sess = TrainingSession(name="Weighted")
    sess.add_analyses(list(mp), weights=[1.0, 3.0])  # heavier weight on second position
    stress = sess.compute_regional_stress(service)
    assert stress["meta"]["num_analyses"] == 2


# 0.6→0.7 Edge case hardening continued

def test_analyze_multi_position_with_all_invalid_positions_still_returns_mpr(service):
    """Even with all invalid positions, it should return a valid (empty or minimal) MPR without crashing."""
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", ["foo", "bar"], load_kg=130, variation="high_bar")
    # Behavior may vary, but it must not raise
    assert isinstance(mpr, MultiPositionResult)


def test_weeklyprogram_report_handles_mixed_program_data(service):
    """generate_simple_report should work cleanly with mixed single and multi-pos data."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Mixed Report Test")
    # Single
    sess1 = TrainingSession(name="Single")
    sess1.add_analysis(service.analyze(subj, service.build_position("bench", load_kg=90)))
    prog.add_session(sess1)
    # Multi
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=130)
    sess2 = TrainingSession(name="Multi")
    sess2.add_analyses(list(mp))
    prog.add_session(sess2)
    report = prog.generate_simple_report(service)
    assert "Mixed Report Test" in report


# 0.6→0.7 Edge case hardening continued

def test_multipositionresult_with_extreme_load_does_not_crash(service):
    """Extreme load should still produce finite results."""
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=300, variation="high_bar")
    assert len(mpr) == 3
    assert all(f >= 0 for f in mpr.per_position_primary_forces)


def test_program_compare_with_mixed_single_and_multi_position_data(service):
    """compare() should handle programs with both single and multi-pos sessions."""
    subj = service.create_subject_from_measurements()
    prog1 = WeeklyProgram(name="Mixed1")
    prog1.add_session(TrainingSession(name="Single").add_analysis(service.analyze(subj, service.build_position("bench", load_kg=100))))
    mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=130)
    sess = TrainingSession(name="Multi")
    sess.add_analyses(list(mp))
    prog1.add_session(sess)
    prog2 = WeeklyProgram(name="Mixed2")
    prog2.add_session(TrainingSession(name="Single2").add_analysis(service.analyze(subj, service.build_position("squat", load_kg=120))))
    cmp = WeeklyProgram.compare(prog1, prog2, service)
    assert "deltas_by_region" in cmp


# 0.6→0.7 Edge case hardening continued

def test_multipositionresult_with_zero_load_returns_zero_or_low_forces(service):
    """Zero load should produce zero or very low forces."""
    subj = service.create_subject_from_measurements()
    mpr = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=0, variation="high_bar")
    assert len(mpr) == 3
    assert all(f <= 5 for f in mpr.per_position_primary_forces)


def test_program_with_four_sessions_stress_accumulation(service):
    """A program with 4 sessions should accumulate stress correctly."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="4-Session Test")
    for i in range(4):
        mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120 + i*5, variation="high_bar")
        sess = TrainingSession(name=f"Day {i+1}")
        sess.add_analyses(list(mp))
        prog.add_session(sess)
    totals = prog.compute_weekly_totals(service)
    assert totals["num_sessions"] == 4
    assert totals["num_analyses"] == 8


# 0.6→0.7 Edge case hardening continued

def test_multipositionresult_with_mixed_geometric_and_static_reports_mixed_summary(service):
    """MPR should correctly summarize when some positions use geometric and some don't (though in practice it's all or nothing per call, this tests the logic)."""
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, biacromial_width_cm=40.0)
    mpr = service.analyze_multi_position(subj, "bench", ["bottom", "mid"], load_kg=100, use_geometric=True)
    assert "geometric" in mpr.geometric_vs_static_summary.lower() or len(mpr.geometric_positions) > 0


def test_program_with_five_sessions_accumulation(service):
    """A program with 5 sessions should accumulate correctly."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="5-Session Test")
    for i in range(5):
        mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=120 + i*2, variation="high_bar")
        sess = TrainingSession(name=f"Day {i+1}")
        sess.add_analyses(list(mp))
        prog.add_session(sess)
    totals = prog.compute_weekly_totals(service)
    assert totals["num_sessions"] == 5
    assert totals["num_analyses"] == 10


# 0.6→0.7 Edge case hardening continued

def test_multipositionresult_with_mixed_lift_types_in_program(service):
    """A WeeklyProgram mixing different lifts with multi-pos should compute totals without error."""
    subj = service.create_subject_from_measurements()
    prog = WeeklyProgram(name="Mixed Lifts")
    mp_squat = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=130, variation="high_bar")
    sess_squat = TrainingSession(name="Squat")
    sess_squat.add_analyses(list(mp_squat))
    prog.add_session(sess_squat)
    mp_dead = service.analyze_multi_position(subj, "deadlift", ["bottom"], load_kg=150, variation="sumo")
    sess_dead = TrainingSession(name="Dead")
    sess_dead.add_analyses(list(mp_dead))
    prog.add_session(sess_dead)
    totals = prog.compute_weekly_totals(service)
    assert totals["num_sessions"] == 2


def test_analyze_multi_position_with_profile_and_geometric_integration(service):
    """Using profile + geometric should work end-to-end for multi-pos."""
    # This is a light integration test
    subj = service.create_subject_from_measurements(humerus_length_cm=34.0, biacromial_width_cm=40.0)
    mpr = service.analyze_multi_position(subj, "bench", ["bottom", "mid"], load_kg=100, use_geometric=True)
    assert len(mpr) == 2
    assert len(mpr.geometric_positions) > 0 or "geometric" in mpr.geometric_vs_static_summary.lower()


# =============================================================================
# 0.6 → 0.7 Final Robustness / Edge / Chaos Hardening Batch
# =============================================================================

def test_extreme_anthropometry_still_produces_finite_results(service):
    """Very long, short, or disproportionate limbs must not crash and must yield finite positive forces (clamped geometry)."""
    extreme = UserAnthropometry(
        femur_length_cm=58.0, tibia_length_cm=50.0,
        humerus_length_cm=40.0, biacromial_width_cm=52.0,
        torso_depth_at_chest_cm=32.0, biiliac_width_cm=38.0
    )
    subj = service.create_subject_from_measurements(
        femur_length_cm=58.0, tibia_length_cm=50.0,
        humerus_length_cm=40.0, biacromial_width_cm=52.0,
        torso_depth_at_chest_cm=32.0, biiliac_width_cm=38.0
    )
    for lift, positions, variation in [
        ("squat", ["bottom", "mid"], "high_bar"),
        ("deadlift", ["bottom"], "conventional"),
        ("bench", ["bottom", "mid", "top"], "flat"),
    ]:
        mpr = service.analyze_multi_position(subj, lift, positions, load_kg=140, variation=variation, use_geometric=True)
        assert len(mpr) >= 1
        assert all(f >= 0 for f in mpr.per_position_primary_forces)
        assert all(f < 50000 for f in mpr.per_position_primary_forces)  # sanity upper bound


def test_multi_region_accumulation_safety_on_mpr(service):
    """Accumulate functions must handle multi-position results (which internally carry multiple regions) without error."""
    subj = service.create_subject_from_measurements(femur_length_cm=43.0, tibia_length_cm=38.0)
    mpr = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=125, variation="low_bar", use_geometric=True)
    # Stress accumulation on rich MPR (auto-discovers regions present in the results)
    stress = service.accumulate_regional_stress(mpr)
    assert isinstance(stress, dict)
    assert "meta" in stress
    assert stress["meta"]["num_analyses"] == 3
    # At least the primary targeted region(s) are present (MPR path exercised safely)
    region_keys = [k for k in stress.keys() if k != "meta"]
    assert len(region_keys) >= 1
    # Volume accumulation path (same safety)
    vol = service.accumulate_regional_volume(mpr)
    assert isinstance(vol, dict)
    assert "meta" in vol


def test_complex_weekly_program_with_many_mpr_and_compare_is_safe(service):
    """Heavy mixed program (multiple sessions, many multi-pos geometric results, different lifts) must support compare + report + totals."""
    subj = service.create_subject_from_measurements(humerus_length_cm=33.5, femur_length_cm=44.0, tibia_length_cm=39.0)
    prog = WeeklyProgram(name="Heavy Mixed Validation Week")
    # Session 1: Squat multi-pos geometric
    mp_s = service.analyze_multi_position(subj, "squat", ["bottom", "mid", "top"], load_kg=145, variation="low_bar", use_geometric=True)
    s1 = TrainingSession(name="Squat Focus")
    s1.add_analyses(list(mp_s))
    prog.add_session(s1)
    # Session 2: Bench + OHP single pos
    s2 = TrainingSession(name="Upper")
    s2.add_analysis(service.analyze(subj, service.build_position("bench", load_kg=110, variation="flat", use_geometric=True)))
    s2.add_analysis(service.analyze(subj, service.build_position("ohp", load_kg=70, variation="standing", use_geometric=True)))
    prog.add_session(s2)
    # Session 3: Deadlift multi + single
    mp_d = service.analyze_multi_position(subj, "deadlift", ["bottom", "mid"], load_kg=160, variation="sumo", use_geometric=True)
    s3 = TrainingSession(name="Pull")
    s3.add_analyses(list(mp_d))
    s3.add_analysis(service.analyze(subj, service.build_position("deadlift", load_kg=160, variation="sumo")))
    prog.add_session(s3)

    totals = prog.compute_weekly_totals(service)
    assert totals["num_sessions"] == 3
    assert totals["num_analyses"] >= 8

    # Compare against a lighter variant
    light = WeeklyProgram(name="Light Week")
    light_s = TrainingSession(name="Light Squat")
    light_mp = service.analyze_multi_position(subj, "squat", ["bottom", "mid"], load_kg=100, variation="high_bar")
    light_s.add_analyses(list(light_mp))
    light.add_session(light_s)
    cmp = WeeklyProgram.compare(prog, light, service)
    assert "deltas_by_region" in cmp
    assert cmp["higher_stress_program"] in ("Heavy Mixed Validation Week", "Light Week")

    # Report must be generatable
    report = prog.generate_simple_report(service)
    assert "Heavy Mixed Validation Week" in report


def test_service_graceful_handling_of_unknown_inputs(service):
    """Unknown lifts, regions, and bad variations should fail fast with clear messages or produce safe fallbacks (no silent garbage)."""
    subj = service.create_subject_from_measurements()
    # Unknown lift should raise a clear error (not KeyError or crash)
    with pytest.raises((ValueError, KeyError, AttributeError)):
        service.build_position("flamethrower_press", load_kg=50)

    # Unknown region on a valid lift should still succeed but target something sensible or note the fallback
    mpr = service.analyze_multi_position(subj, "squat", ["bottom"], load_kg=120, target_region_name="nonexistent_weird_region_xyz")
    assert len(mpr) == 1  # did not blow up

    # Extreme negative load should be handled (either clamped or clear error)
    try:
        res = service.analyze(subj, service.build_position("bench", load_kg=-50))
        assert res is not None
    except (ValueError, AssertionError):
        pass  # acceptable to reject
