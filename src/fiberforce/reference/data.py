"""
ReferenceData loader and central access point (v0.2.1 polished).

This provides a clean way to access all literature-inspired default values
for moment arms, load arms, and (in future) muscle architecture parameters.

The goal is to move away from scattered imports of individual dicts and
toward a single, queryable, versioned reference source that the rest of the
system (builders, calculators, CLI) can depend on.

POLISH (this revision):
- Full confidence metadata (high/medium/low/estimated) attached to **all**
  major tables: bench, squat, deadlift, OHP (muscle + load arms).
- Richer public query API:
    * get_confidence_for_moment_arm(...)
    * get_moment_arm_with_confidence(...)
    * list_available_lifts()
    * list_available_regions_for_lift(lift)
    * list_available_positions(lift, region_key=None)
- Deeper geometric integration: estimate_moment_arm is the **preferred path**
  whenever valid anthropometry is supplied for supported (lift, region) pairs.
  Clear fallback to static tables with appropriate confidence tagging.
- Excellent docstrings + usage examples throughout.

GEOMETRIC PROTOTYPE INTEGRATION:
    When UserAnthropometry with relevant measurements is provided to
    estimate_moment_arm (or via the high-level builders), the geometric
    estimators are consulted first for bench sternal pecs + squat (glute/quad) +
    deadlift + ohp (including Phase 4 multi-pos + lateral_delt expansion).
    Results are tagged with confidence "estimated (geometric prototype)".

    All static tables remain 100% backward-compatible.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List

from .moment_arms import (
    # Value tables (backward-compatible)
    BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS,
    BENCH_PRESS_LOAD_MOMENT_ARMS,
    SQUAT_LOAD_MOMENT_ARMS,
    SQUAT_GLUTE_MAX_MOMENT_ARMS,
    SQUAT_QUAD_MOMENT_ARMS,
    SQUAT_HAMSTRING_MOMENT_ARMS,
    SQUAT_EREctor_MOMENT_ARMS,
    OVERHEAD_PRESS_LOAD_MOMENT_ARMS,
    OHP_ANTERIOR_DELT_MOMENT_ARMS,
    OHP_TRICEPS_LONG_MOMENT_ARMS,
    OHP_LATERAL_DELT_MOMENT_ARMS,
    OHP_POSTERIOR_DELT_MOMENT_ARMS,
    OHP_TRICEPS_LATERAL_MOMENT_ARMS,
    OHP_TRAP_UPPER_MOMENT_ARMS,
    DEADLIFT_LOAD_MOMENT_ARMS,
    DEADLIFT_GLUTE_MAX_MOMENT_ARMS,
    DEADLIFT_HAMSTRING_MOMENT_ARMS,
    DEADLIFT_EREctor_MOMENT_ARMS,
    # Per-joint load MAs for multi-muscle % dominance (squat hip/knee, DL hip/lumbar, OHP shoulder/elbow, etc.)
    SQUAT_HIP_LOAD_MOMENT_ARMS,
    SQUAT_KNEE_LOAD_MOMENT_ARMS,
    DEADLIFT_HIP_LOAD_MOMENT_ARMS,
    DEADLIFT_LUMBAR_LOAD_MOMENT_ARMS,
    OHP_SHOULDER_LOAD_MOMENT_ARMS,
    OHP_ELBOW_LOAD_MOMENT_ARMS,
    RDL_HIP_LOAD_MOMENT_ARMS,
    RDL_LUMBAR_LOAD_MOMENT_ARMS,
    INCLINE_SHOULDER_LOAD_MOMENT_ARMS,
    INCLINE_ELBOW_LOAD_MOMENT_ARMS,
    # NEW post-v1 scope expansion
    INCLINE_BENCH_STERNAL_PEC_MOMENT_ARMS,
    INCLINE_BENCH_LOAD_MOMENT_ARMS,
    INCLINE_BENCH_CLAVICULAR_PEC_MOMENT_ARMS,
    RDL_LOAD_MOMENT_ARMS,
    RDL_GLUTE_MAX_MOMENT_ARMS,
    RDL_HAMSTRING_MOMENT_ARMS,
    RDL_EREctor_MOMENT_ARMS,
    # NEW: Parallel confidence metadata tables
    BENCH_PRESS_STERNAL_PEC_MA_CONFIDENCE,
    BENCH_PRESS_LOAD_MA_CONFIDENCE,
    SQUAT_GLUTE_MAX_MA_CONFIDENCE,
    SQUAT_QUAD_MA_CONFIDENCE,
    SQUAT_HAMSTRING_MA_CONFIDENCE,
    SQUAT_EREctor_MA_CONFIDENCE,
    SQUAT_LOAD_MA_CONFIDENCE,
    DEADLIFT_LOAD_MA_CONFIDENCE,
    DEADLIFT_GLUTE_MAX_MA_CONFIDENCE,
    DEADLIFT_HAMSTRING_MA_CONFIDENCE,
    DEADLIFT_EREctor_MA_CONFIDENCE,
    OVERHEAD_PRESS_LOAD_MA_CONFIDENCE,
    OHP_ANTERIOR_DELT_MA_CONFIDENCE,
    OHP_LATERAL_DELT_MA_CONFIDENCE,
    OHP_POSTERIOR_DELT_MA_CONFIDENCE,
    OHP_TRICEPS_LONG_MA_CONFIDENCE,
    OHP_TRICEPS_LATERAL_MA_CONFIDENCE,
    OHP_TRAP_UPPER_MA_CONFIDENCE,
    # NEW confidence for expanded lifts
    INCLINE_BENCH_STERNAL_PEC_MA_CONFIDENCE,
    INCLINE_BENCH_LOAD_MA_CONFIDENCE,
    INCLINE_BENCH_CLAVICULAR_MA_CONFIDENCE,
    RDL_LOAD_MA_CONFIDENCE,
    RDL_GLUTE_MAX_MA_CONFIDENCE,
    RDL_HAMSTRING_MA_CONFIDENCE,
    RDL_EREctor_MA_CONFIDENCE,
)

# Geometric prototype (anthropometry-driven MA estimation)
from .geometric import estimate_moment_arm as _geometric_estimate_moment_arm


@dataclass
class ReferenceData:
    """
    Central container + rich query interface for all reference biomechanical data.

    PREFERRED USAGE (post-polish):
        ref = get_default_reference()   # or ReferenceData()

        # Static table access (always available, backward-compatible)
        ma = ref.get_moment_arm("bench", "sternal_pecs", "flat_bench_bottom", "shoulder")

        # With explicit confidence
        ma, conf = ref.get_moment_arm_with_confidence("squat", "glute_max", "high_bar_bottom", "hip")

        # List what is available
        lifts = ref.list_available_lifts()                    # ['bench', 'squat', 'deadlift', 'ohp']
        regions = ref.list_available_regions_for_lift("deadlift")  # ['glute_max_upper', ...]
        positions = ref.list_available_positions("bench", "sternal_pecs")

        conf = ref.get_confidence_for_moment_arm("ohp", "anterior_delt", "standing_bottom", "shoulder")

    GEOMETRIC PREFERRED PATH (recommended when you have anthropometry):
        anthro = UserAnthropometry(humerus_length_cm=34.0, biacromial_width_cm=40.5,
                                   torso_depth_at_chest_cm=23.0, femur_length_cm=43.0, ...)
        ma = ref.estimate_moment_arm(
            "bench", "sternal_pecs",
            anthro=anthro,
            grip_width_cm=62.0,
            position="flat_bench_bottom"
        )
        # ma will be a geometric estimate (confidence "estimated (geometric prototype)")
        # Falls back cleanly to the closest static table value otherwise.

        # Unified high-level helper (tries geometric first when anthro supplied)
        ma2, conf2 = ref.get_moment_arm_with_confidence(
            "squat", "quads", "high_bar_bottom", "knee",
            anthro=anthro, stance_width_cm=68.0
        )

    All methods are safe, well-documented, and preserve every previous behavior.
    """

    version: str = "0.2.2-phase4-multi-pos-geo-hardening"

    # Raw value tables (for power users / migration / direct inspection)
    bench_sternal_pec_moment_arms: dict = None
    bench_load_moment_arms: dict = None
    squat_load_moment_arms: dict = None
    squat_glute_max_moment_arms: dict = None
    squat_quad_moment_arms: dict = None
    squat_hamstring_moment_arms: dict = None
    squat_erector_moment_arms: dict = None
    ohp_load_moment_arms: dict = None
    ohp_anterior_delt_moment_arms: dict = None
    ohp_triceps_long_moment_arms: dict = None
    ohp_lateral_delt_moment_arms: dict = None
    ohp_posterior_delt_moment_arms: dict = None
    ohp_triceps_lateral_moment_arms: dict = None
    ohp_trap_upper_moment_arms: dict = None
    deadlift_load_moment_arms: dict = None
    deadlift_glute_max_moment_arms: dict = None
    deadlift_hamstring_moment_arms: dict = None
    deadlift_erector_moment_arms: dict = None

    # Parallel confidence metadata (new polished surface)
    bench_sternal_pec_ma_confidence: dict = None
    bench_load_ma_confidence: dict = None
    squat_glute_max_ma_confidence: dict = None
    squat_quad_ma_confidence: dict = None
    squat_hamstring_ma_confidence: dict = None
    squat_erector_ma_confidence: dict = None
    squat_load_ma_confidence: dict = None
    ohp_load_ma_confidence: dict = None
    ohp_anterior_delt_ma_confidence: dict = None
    ohp_lateral_delt_ma_confidence: dict = None
    ohp_posterior_delt_ma_confidence: dict = None
    ohp_triceps_long_ma_confidence: dict = None
    ohp_triceps_lateral_ma_confidence: dict = None
    ohp_trap_upper_ma_confidence: dict = None
    deadlift_load_ma_confidence: dict = None
    deadlift_glute_max_ma_confidence: dict = None
    deadlift_hamstring_ma_confidence: dict = None
    deadlift_erector_ma_confidence: dict = None

    def __post_init__(self):
        """Load all value tables + their confidence metadata (static + geometric ready)."""
        # Value tables (unchanged behavior)
        self.bench_sternal_pec_moment_arms = BENCH_PRESS_STERNAL_PEC_MOMENT_ARMS
        self.bench_load_moment_arms = BENCH_PRESS_LOAD_MOMENT_ARMS
        self.squat_load_moment_arms = SQUAT_LOAD_MOMENT_ARMS
        self.squat_glute_max_moment_arms = SQUAT_GLUTE_MAX_MOMENT_ARMS
        self.squat_quad_moment_arms = SQUAT_QUAD_MOMENT_ARMS
        self.squat_hamstring_moment_arms = SQUAT_HAMSTRING_MOMENT_ARMS
        self.squat_erector_moment_arms = SQUAT_EREctor_MOMENT_ARMS
        self.ohp_load_moment_arms = OVERHEAD_PRESS_LOAD_MOMENT_ARMS
        self.ohp_anterior_delt_moment_arms = OHP_ANTERIOR_DELT_MOMENT_ARMS
        self.ohp_triceps_long_moment_arms = OHP_TRICEPS_LONG_MOMENT_ARMS
        self.ohp_lateral_delt_moment_arms = OHP_LATERAL_DELT_MOMENT_ARMS
        self.ohp_posterior_delt_moment_arms = OHP_POSTERIOR_DELT_MOMENT_ARMS
        self.ohp_triceps_lateral_moment_arms = OHP_TRICEPS_LATERAL_MOMENT_ARMS
        self.ohp_trap_upper_moment_arms = OHP_TRAP_UPPER_MOMENT_ARMS
        self.deadlift_load_moment_arms = DEADLIFT_LOAD_MOMENT_ARMS
        self.deadlift_glute_max_moment_arms = DEADLIFT_GLUTE_MAX_MOMENT_ARMS
        self.deadlift_hamstring_moment_arms = DEADLIFT_HAMSTRING_MOMENT_ARMS
        self.deadlift_erector_moment_arms = DEADLIFT_EREctor_MOMENT_ARMS

        # NEW post-v1 scope expansion tables
        self.incline_bench_sternal_pec_moment_arms = INCLINE_BENCH_STERNAL_PEC_MOMENT_ARMS
        self.incline_bench_load_moment_arms = INCLINE_BENCH_LOAD_MOMENT_ARMS
        self.incline_bench_clavicular_moment_arms = INCLINE_BENCH_CLAVICULAR_PEC_MOMENT_ARMS
        self.rdl_load_moment_arms = RDL_LOAD_MOMENT_ARMS
        self.rdl_glute_max_moment_arms = RDL_GLUTE_MAX_MOMENT_ARMS
        self.rdl_hamstring_moment_arms = RDL_HAMSTRING_MOMENT_ARMS
        self.rdl_erector_moment_arms = RDL_EREctor_MOMENT_ARMS

        # Confidence tables (new)
        self.bench_sternal_pec_ma_confidence = BENCH_PRESS_STERNAL_PEC_MA_CONFIDENCE
        self.bench_load_ma_confidence = BENCH_PRESS_LOAD_MA_CONFIDENCE
        self.squat_glute_max_ma_confidence = SQUAT_GLUTE_MAX_MA_CONFIDENCE
        self.squat_quad_ma_confidence = SQUAT_QUAD_MA_CONFIDENCE
        self.squat_hamstring_ma_confidence = SQUAT_HAMSTRING_MA_CONFIDENCE
        self.squat_erector_ma_confidence = SQUAT_EREctor_MA_CONFIDENCE
        self.squat_load_ma_confidence = SQUAT_LOAD_MA_CONFIDENCE
        self.ohp_load_ma_confidence = OVERHEAD_PRESS_LOAD_MA_CONFIDENCE
        self.ohp_anterior_delt_ma_confidence = OHP_ANTERIOR_DELT_MA_CONFIDENCE
        self.ohp_lateral_delt_ma_confidence = OHP_LATERAL_DELT_MA_CONFIDENCE
        self.ohp_posterior_delt_ma_confidence = OHP_POSTERIOR_DELT_MA_CONFIDENCE
        self.ohp_triceps_long_ma_confidence = OHP_TRICEPS_LONG_MA_CONFIDENCE
        self.ohp_triceps_lateral_ma_confidence = OHP_TRICEPS_LATERAL_MA_CONFIDENCE
        self.ohp_trap_upper_ma_confidence = OHP_TRAP_UPPER_MA_CONFIDENCE
        self.deadlift_load_ma_confidence = DEADLIFT_LOAD_MA_CONFIDENCE
        self.deadlift_glute_max_ma_confidence = DEADLIFT_GLUTE_MAX_MA_CONFIDENCE
        self.deadlift_hamstring_ma_confidence = DEADLIFT_HAMSTRING_MA_CONFIDENCE
        self.deadlift_erector_ma_confidence = DEADLIFT_EREctor_MA_CONFIDENCE

        # NEW post-v1
        self.incline_bench_sternal_pec_ma_confidence = INCLINE_BENCH_STERNAL_PEC_MA_CONFIDENCE
        self.incline_bench_load_ma_confidence = INCLINE_BENCH_LOAD_MA_CONFIDENCE
        self.incline_bench_clavicular_ma_confidence = INCLINE_BENCH_CLAVICULAR_MA_CONFIDENCE
        self.rdl_load_ma_confidence = RDL_LOAD_MA_CONFIDENCE
        self.rdl_glute_max_ma_confidence = RDL_GLUTE_MAX_MA_CONFIDENCE
        self.rdl_hamstring_ma_confidence = RDL_HAMSTRING_MA_CONFIDENCE
        self.rdl_erector_ma_confidence = RDL_EREctor_MA_CONFIDENCE

    # ------------------------------------------------------------------
    # Core static accessors (preserved exactly for backward compatibility)
    # ------------------------------------------------------------------

    def get_moment_arm(
        self,
        lift: str,
        region_key: str,
        position_key: str,
        joint: str,
        default: Optional[float] = None,
    ) -> Optional[float]:
        """
        Unified accessor for muscle moment arms from static reference tables only.

        This method **never** invokes the geometric prototype.
        For anthropometry-aware estimation (preferred when data available), use
        `estimate_moment_arm` or `get_moment_arm_with_confidence`.

        Returns the value in cm or `default`.
        """
        table = self._get_muscle_ma_table(lift, region_key)
        if table and position_key in table:
            return table[position_key].get(joint, default)
        return default

    def get_load_moment_arm(
        self, lift: str, position_key: str, default: Optional[float] = None
    ) -> Optional[float]:
        """Unified accessor for external load moment arms (static tables only)."""
        if lift == "bench":
            return self.bench_load_moment_arms.get(position_key, default)
        if lift == "squat":
            return self.squat_load_moment_arms.get(position_key, default)
        if lift in ("ohp", "overhead", "overhead_press"):
            return self.ohp_load_moment_arms.get(position_key, default)
        if lift in ("deadlift", "dl", "dlift"):
            return self.deadlift_load_moment_arms.get(position_key, default)
        if lift in ("incline", "incline_bench"):
            return self.incline_bench_load_moment_arms.get(position_key, default)
        if lift in ("romanian", "rdl", "romanian_deadlift"):
            return self.rdl_load_moment_arms.get(position_key, default)
        return default

    # ------------------------------------------------------------------
    # NEW: Rich query API + confidence access
    # ------------------------------------------------------------------

    def get_confidence_for_moment_arm(
        self,
        lift: str,
        region_key: str,
        position_key: str,
        joint: Optional[str] = None,
        anthro: Optional["UserAnthropometry"] = None,
        **params,
    ) -> str:
        """
        Return confidence level for a moment arm lookup.

        When `anthro` is supplied **and** the (lift, region_key) pair is
        supported by the geometric prototype, returns
        "estimated (geometric prototype)".

        Otherwise returns the static table confidence ("high"/"medium"/"low").

        Example:
            conf = ref.get_confidence_for_moment_arm("deadlift", "glute_max", "conventional_bottom", "hip")
            # -> "medium"
        """
        if anthro is not None:
            geo_val = _geometric_estimate_moment_arm(lift, region_key, anthro, **params)
            if geo_val is not None:
                return "estimated (geometric prototype)"

        # Static path
        conf_table = self._get_confidence_table(lift, region_key)
        if conf_table and position_key in conf_table:
            return conf_table[position_key]

        # Sensible fallbacks for load arms or unknown
        if "load" in (region_key or "").lower() or joint is None:
            load_conf = self._get_load_confidence_table(lift)
            if load_conf and position_key in load_conf:
                return load_conf[position_key]
        return "estimated"

    def get_moment_arm_with_confidence(
        self,
        lift: str,
        region_key: str,
        position_key: str,
        joint: str,
        anthro: Optional["UserAnthropometry"] = None,
        default: Optional[float] = None,
        **params,
    ) -> Tuple[Optional[float], str]:
        """
        Combined accessor that returns (moment_arm_cm, confidence_level).

        This is the **recommended high-level query method**.

        - If `anthro` is provided and the combination is geometrically supported,
          the geometric estimate is used and confidence will be
          "estimated (geometric prototype)".
        - Otherwise the static table value + its documented confidence is returned.

        Example (preferred pattern when personalization data exists):
            ma, conf = ref.get_moment_arm_with_confidence(
                "bench", "sternal_pecs",
                "flat_bench_bottom", "shoulder",
                anthro=subject.anthropometry,
                grip_width_cm=64.0
            )
            print(f"Using {ma} cm ({conf})")
        """
        if anthro is not None:
            geo = _geometric_estimate_moment_arm(lift, region_key, anthro, **params)
            if geo is not None:
                return geo, "estimated (geometric prototype)"

        # Fallback to static
        val = self.get_moment_arm(lift, region_key, position_key, joint, default)
        conf = self.get_confidence_for_moment_arm(
            lift, region_key, position_key, joint, anthro=None
        )
        return val, conf

    def list_available_lifts(self) -> List[str]:
        """Return the canonical list of supported lifts with reference coverage."""
        return ["bench", "incline", "squat", "deadlift", "ohp", "romanian", "rdl"]

    def list_available_regions_for_lift(self, lift: str) -> List[str]:
        """
        Return known region keys that have moment arm data for the given lift.

        Useful for UI, CLI help, and validation.

        Example:
            for r in ref.list_available_regions_for_lift("ohp"):
                print(r)
            # anterior_delt, lateral_delt, posterior_delt, triceps_long, ...
        """
        l = lift.lower()
        if l in ("bench", "benchpress"):
            return ["sternal_pecs", "pectoralis_major_sternal", "anterior_delt", "deltoid_anterior", "triceps_long", "triceps"]
        if l in ("squat", "backsquat"):
            return ["glute_max_upper", "glute_max", "vastus_lateralis", "quads", "vl", "hamstring", "biceps_femoris", "erector", "lumbar"]
        if l in ("deadlift", "dl"):
            return ["glute_max_upper", "glute_max", "hamstring", "biceps_femoris", "erector", "erector_lumbar", "lumbar"]
        if l in ("ohp", "overhead", "overhead_press"):
            return [
                "anterior_delt", "delts", "anterior",
                "lateral_delt", "lateral",
                "posterior_delt", "rear_delt", "posterior", "rear",
                "triceps_long", "triceps", "long_head",
                "triceps_lateral",
                "trap_upper",
            ]
        if l in ("incline", "incline_bench"):
            return ["sternal_pecs", "clavicular_pecs", "upper_pecs", "pectoralis_major_sternal", "anterior_delt", "deltoid_anterior", "triceps_long", "triceps"]
        if l in ("romanian", "rdl", "romanian_deadlift"):
            return ["glute_max_upper", "glute_max", "hamstring", "biceps_femoris", "erector", "erector_lumbar", "lumbar"]
        if l in ("front", "front_squat"):
            return ["glute_max_upper", "glute_max", "vastus_lateralis", "quads", "hamstring"]
        return []

    def list_available_positions(self, lift: str, region_key: Optional[str] = None) -> List[str]:
        """Return known position keys for a lift (and optionally a region).

        Phase 4 / v0.4+ multi-position hardening: explicit support for bottom/mid/top/lockout
        (and full canonical forms like standing_lockout, conventional_mid, flat_bench_top).
        Returns actual table keys + short discoverable variants + synthesized families for
        high-value multi-pos use in build_multi_position / analyze_multi_position etc.
        """
        l = lift.lower()
        # Base table-driven keys (respect region when helpful)
        base = []
        tables_to_scan = []
        if l in ("bench", "benchpress"):
            if region_key and "load" in (region_key or "").lower():
                tables_to_scan = [self.bench_load_moment_arms]
            else:
                tables_to_scan = [self.bench_sternal_pec_moment_arms, self.bench_load_moment_arms]
        elif l in ("squat", "backsquat"):
            if region_key and "glute" in region_key.lower():
                tables_to_scan = [self.squat_glute_max_moment_arms]
            elif region_key and ("quad" in region_key.lower() or "vl" in region_key.lower()):
                tables_to_scan = [self.squat_quad_moment_arms]
            else:
                tables_to_scan = [self.squat_glute_max_moment_arms, self.squat_quad_moment_arms, self.squat_load_moment_arms]
        elif l in ("deadlift", "dl"):
            if region_key and "glute" in region_key.lower():
                tables_to_scan = [self.deadlift_glute_max_moment_arms]
            elif region_key and "ham" in region_key.lower():
                tables_to_scan = [self.deadlift_hamstring_moment_arms]
            elif region_key and "erect" in region_key.lower():
                tables_to_scan = [self.deadlift_erector_moment_arms]
            else:
                tables_to_scan = [self.deadlift_glute_max_moment_arms, self.deadlift_hamstring_moment_arms,
                                  self.deadlift_erector_moment_arms, self.deadlift_load_moment_arms]
        elif l in ("ohp", "overhead", "overhead_press"):
            if region_key and "anterior" in region_key.lower():
                tables_to_scan = [self.ohp_anterior_delt_moment_arms]
            elif region_key and "lateral" in region_key.lower():
                tables_to_scan = [self.ohp_lateral_delt_moment_arms]
            elif region_key and ("posterior" in region_key.lower() or "rear" in region_key.lower()):
                tables_to_scan = [self.ohp_posterior_delt_moment_arms]
            elif region_key and "triceps" in region_key.lower():
                tables_to_scan = [self.ohp_triceps_long_moment_arms, self.ohp_triceps_lateral_moment_arms]
            else:
                tables_to_scan = [self.ohp_anterior_delt_moment_arms, self.ohp_lateral_delt_moment_arms,
                                  self.ohp_load_moment_arms, self.ohp_triceps_long_moment_arms]
        elif l in ("incline", "incline_bench"):
            tables_to_scan = [self.incline_bench_sternal_pec_moment_arms, self.incline_bench_load_moment_arms,
                              self.incline_bench_clavicular_moment_arms]
        elif l in ("romanian", "rdl", "romanian_deadlift"):
            tables_to_scan = [self.rdl_glute_max_moment_arms, self.rdl_hamstring_moment_arms,
                              self.rdl_erector_moment_arms, self.rdl_load_moment_arms]

        for t in tables_to_scan:
            if t:
                base.extend(list(t.keys()))

        base = list(dict.fromkeys(base))  # dedup preserve order

        # Phase 4 explicit multi-pos: short variants always surfaced for discoverability
        # (used by service.build_multi_position etc.)
        short_variants = ["bottom", "mid", "top", "lockout", "near_lockout"]
        expanded = set(base)
        expanded.update(short_variants)

        # Synthesize full variants for known families (OHP standing/seated, DL conv/sumo, bench/squat)
        common_families = ["standing", "seated", "strict_standing", "conventional", "sumo",
                           "high_bar", "low_bar", "flat_bench", "incline_30", "decline_15"]
        for fam in common_families:
            for v in ["bottom", "mid", "top", "lockout"]:
                expanded.add(f"{fam}_{v}")

        # Legacy / table-derived synthetic (kept for compat)
        common_variants = ["bottom", "mid", "top", "near_lockout", "lockout"]
        for b in base:
            for v in common_variants:
                if v not in b:
                    expanded.add(f"{b.split('_')[0]}_{v}" if "_" in b else f"{b}_{v}")

        return sorted(list(expanded)) if expanded else (base or [])

    # ------------------------------------------------------------------
    # GEOMETRIC INTEGRATION (preferred when anthropometry supplied)
    # ------------------------------------------------------------------

    def estimate_moment_arm(
        self,
        lift: str,
        region_key: str,
        anthro: Optional["UserAnthropometry"] = None,
        **params,
    ) -> Optional[float]:
        """
        Return a moment arm, preferring the geometric (anthropometry-driven)
        prototype when possible. This is the primary recommended entry point
        for personalized analyses.

        GEOMETRIC PREFERRED PATH:
            When a valid UserAnthropometry object with relevant measurements
            (humerus/biacromial/torso for bench, femur/tibia for squat) is
            supplied **and** the (lift, region_key) pair is supported by the
            geometric estimators, a subject-specific value is returned.

            Confidence for such values is always "estimated (geometric prototype)".

        CLEAR FALLBACK:
            If anthro is None, missing required measurements, or the
            (lift, region) combination is not yet implemented in geometric.py,
            this method falls back to the static reference table using
            `position` / `position_key` from params (or a sensible default).

        Supported geometric cases (see geometric.py for full equations, assumptions, limits):
            - bench + sternal_pecs / pectoralis_major_sternal
            - squat + glute_max / glute_max_upper / glute
            - squat + quads / vastus_lateralis / vl

        Full example with personalization:
            ref = get_default_reference()
            anthro = UserAnthropometry(humerus_length_cm=33.8, biacromial_width_cm=39.5,
                                       torso_depth_at_chest_cm=24.0)
            ma = ref.estimate_moment_arm(
                "bench", "sternal_pecs",
                anthro=anthro,
                grip_width_cm=60.0,
                position="flat_bench_bottom"
            )
            print(ma)   # e.g. 5.82 (continuous, body-specific)

        When you also want the confidence tag in one call, prefer:
            ma, conf = ref.get_moment_arm_with_confidence(..., anthro=anthro, ...)
        """
        if anthro is not None:
            geo = _geometric_estimate_moment_arm(lift, region_key, anthro, **params)
            if geo is not None:
                return geo

        # v0.4 / Phase 4 multi-position aware fallback (hardened for OHP standing/seated/lockout + DL)
        requested_pos = params.get("position") or params.get("position_key")
        candidates = []
        if requested_pos:
            candidates.append(requested_pos)
            # Expanded bases for OHP (seated/standing/lockout), DL, squat, bench
            for base in ["high_bar", "low_bar", "flat_bench", "conventional", "sumo", "standing", "seated", "strict_standing"]:
                short = requested_pos.split("_")[-1] if "_" in requested_pos else requested_pos
                for variant in [requested_pos, f"{base}_{short}", f"{base}_bottom", f"{base}_mid", f"{base}_lockout", f"{base}_top"]:
                    if variant not in candidates:
                        candidates.append(variant)
        candidates.append("flat_bench_bottom")  # ultimate default
        candidates.append("standing_bottom")
        candidates.append("conventional_bottom")

        joint = self._infer_joint_for_region(lift, region_key)
        for pos in candidates:
            val = self.get_moment_arm(lift, region_key, pos, joint, default=None)
            if val is not None:
                return val
        return None

    # ------------------------------------------------------------------
    # Introspection / helpers
    # ------------------------------------------------------------------

    def describe(self) -> str:
        return (
            f"ReferenceData v{self.version} — "
            f"full confidence metadata on all tables (bench/squat/deadlift/ohp + post-v1: incline, rdl) + "
            f"geometric MA preferred path when anthro provided. "
            f"Lifts: {', '.join(self.list_available_lifts())}. "
            f"Geometric support: bench sternal + squat (glute/quad) + deadlift (glute/ham) + ohp (anterior + triceps; lateral via proxy)"
        )

    def list_geometric_supported(self) -> dict:
        """
        Return a summary of which (lift, region) combinations have direct geometric estimator support.

        This is useful for users and for the 0.6+ coverage audit.
        Returns a dict like:
            {
                "bench": ["sternal_pecs"],
                "squat": ["glute_max", "quads"],
                ...
            }
        """
        return {
            "bench": ["sternal_pecs / pectoralis_major_sternal"],
            "squat": ["glute_max / glute_max_upper", "quads / vastus_lateralis / vl"],
            "deadlift": ["glute_max", "hamstring"],
            "ohp": [
                "anterior_delt / anterior",
                "triceps (long + lateral)",
                "lateral_delt (directional proxy via anterior estimator)"
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers (not part of public contract but useful)
    # ------------------------------------------------------------------

    def _get_muscle_ma_table(self, lift: str, region_key: str) -> Optional[dict]:
        l = lift.lower()
        r = (region_key or "").lower()
        if l in ("bench", "benchpress") and r in ("sternal_pecs", "pectoralis_major_sternal", "sternal"):
            return self.bench_sternal_pec_moment_arms
        if l in ("squat", "backsquat"):
            if r in ("glute_max_upper", "glute_max", "glute"):
                return self.squat_glute_max_moment_arms
            if r in ("vastus_lateralis", "quads", "vl", "quad"):
                return self.squat_quad_moment_arms
        if l in ("ohp", "overhead", "overhead_press"):
            if r in ("anterior_delt", "delts", "anterior"):
                return self.ohp_anterior_delt_moment_arms
            if r in ("lateral_delt", "lateral"):
                return self.ohp_lateral_delt_moment_arms
            if r in ("posterior_delt", "rear_delt", "posterior", "rear"):
                return self.ohp_posterior_delt_moment_arms
            if r in ("triceps_long", "triceps", "long_head"):
                return self.ohp_triceps_long_moment_arms
            if r in ("triceps_lateral", "lateral_triceps"):
                return self.ohp_triceps_lateral_moment_arms
        if l in ("deadlift", "dl", "dlift"):
            if r in ("glute_max_upper", "glute_max", "glute"):
                return self.deadlift_glute_max_moment_arms
            if r in ("hamstring", "hamstrings", "biceps_femoris"):
                return self.deadlift_hamstring_moment_arms
            if r in ("erector", "erector_lumbar", "lumbar"):
                return self.deadlift_erector_moment_arms
        if l in ("incline", "incline_bench"):
            if r in ("sternal_pecs", "pectoralis_major_sternal", "sternal"):
                return self.incline_bench_sternal_pec_moment_arms
            if r in ("clavicular_pecs", "upper_pecs", "clavicular"):
                return self.incline_bench_clavicular_moment_arms
            return self.incline_bench_sternal_pec_moment_arms  # default
        if l in ("romanian", "rdl", "romanian_deadlift"):
            if r in ("glute_max_upper", "glute_max", "glute"):
                return self.rdl_glute_max_moment_arms
            if r in ("hamstring", "hamstrings", "biceps_femoris"):
                return self.rdl_hamstring_moment_arms
            if r in ("erector", "erector_lumbar", "lumbar"):
                return self.rdl_erector_moment_arms
            return self.rdl_hamstring_moment_arms  # default for RDL
        return None

    def _get_confidence_table(self, lift: str, region_key: str) -> Optional[dict]:
        l = lift.lower()
        r = (region_key or "").lower()
        if l in ("bench", "benchpress") and r in ("sternal_pecs", "pectoralis_major_sternal", "sternal"):
            return self.bench_sternal_pec_ma_confidence
        if l in ("squat", "backsquat"):
            if r in ("glute_max_upper", "glute_max", "glute"):
                return self.squat_glute_max_ma_confidence
            if r in ("vastus_lateralis", "quads", "vl", "quad"):
                return self.squat_quad_ma_confidence
            if r in ("hamstring", "hamstrings"):
                return self.squat_hamstring_ma_confidence
        if l in ("ohp", "overhead"):
            if r in ("anterior_delt", "delts", "anterior"):
                return self.ohp_anterior_delt_ma_confidence
            if r in ("lateral_delt", "lateral"):
                return self.ohp_lateral_delt_ma_confidence
            if r in ("posterior_delt", "rear_delt", "posterior", "rear"):
                return self.ohp_posterior_delt_ma_confidence
            if r in ("triceps_long", "triceps", "long_head"):
                return self.ohp_triceps_long_ma_confidence
            if r in ("triceps_lateral", "lateral_triceps"):
                return self.ohp_triceps_lateral_ma_confidence
            if r in ("trap_upper",):
                return self.ohp_trap_upper_ma_confidence
        if l in ("deadlift", "dl"):
            if r in ("glute_max_upper", "glute_max", "glute"):
                return self.deadlift_glute_max_ma_confidence
            if r in ("hamstring", "hamstrings", "biceps_femoris"):
                return self.deadlift_hamstring_ma_confidence
            if r in ("erector", "erector_lumbar", "lumbar"):
                return self.deadlift_erector_ma_confidence
        if l in ("incline", "incline_bench"):
            if r in ("sternal_pecs", "pectoralis_major_sternal", "sternal"):
                return self.incline_bench_sternal_pec_ma_confidence
            if r in ("clavicular_pecs", "upper_pecs", "clavicular"):
                return self.incline_bench_clavicular_ma_confidence
            return self.incline_bench_sternal_pec_ma_confidence
        if l in ("romanian", "rdl", "romanian_deadlift"):
            if r in ("glute_max_upper", "glute_max", "glute"):
                return self.rdl_glute_max_ma_confidence
            if r in ("hamstring", "hamstrings", "biceps_femoris"):
                return self.rdl_hamstring_ma_confidence
            if r in ("erector", "erector_lumbar", "lumbar"):
                return self.rdl_erector_ma_confidence
            return self.rdl_hamstring_ma_confidence
        return None

    def _get_load_confidence_table(self, lift: str) -> Optional[dict]:
        l = lift.lower()
        if l in ("bench", "benchpress"):
            return self.bench_load_ma_confidence
        if l in ("squat", "backsquat"):
            return self.squat_load_ma_confidence
        if l in ("ohp", "overhead"):
            return self.ohp_load_ma_confidence
        if l in ("deadlift", "dl"):
            return self.deadlift_load_ma_confidence
        if l in ("incline", "incline_bench"):
            return self.incline_bench_load_ma_confidence
        if l in ("romanian", "rdl", "romanian_deadlift"):
            return self.rdl_load_ma_confidence
        return None

    # ------------------------------------------------------------------
    # Continuous / dynamic ROM support (post-v1 modeling depth wave, MVP)
    # ------------------------------------------------------------------

    def _interpolate_value(self, table: dict, key1: str, key2: str, t: float, default: Optional[float] = None) -> Optional[float]:
        """
        Simple linear interp between two discrete table entries for MVP continuous ROM.
        t in [0,1]. Assumes numeric values (for load MA) or per-joint dicts (for muscle MA).
        For muscle MA dicts, interps per joint.
        Falls back gracefully.
        """
        if key1 not in table or key2 not in table:
            return default
        v1 = table[key1]
        v2 = table[key2]
        if isinstance(v1, dict) and isinstance(v2, dict):
            # per-joint dict, e.g. {"hip": 5.8, "knee": 4.2}
            out = {}
            for j in set(v1) | set(v2):
                a = v1.get(j, default)
                b = v2.get(j, default)
                if a is None or b is None:
                    out[j] = default
                else:
                    out[j] = a + (b - a) * t
            return out
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            return v1 + (v2 - v1) * t
        return default

    def get_moment_arm_continuous(
        self,
        lift: str,
        region_key: str,
        pos_key1: str,
        pos_key2: str,
        t: float,
        joint: str,
        default: Optional[float] = None,
    ) -> Optional[float]:
        """
        MVP continuous MA: linear interp between two discrete reference positions.
        t=0 -> pos_key1, t=1 -> pos_key2.
        Uses static tables (geometric callers should handle their own param variation).
        """
        table = self._get_muscle_ma_table(lift, region_key) or {}
        val = self._interpolate_value(table, pos_key1, pos_key2, t, default)
        if isinstance(val, dict):
            return val.get(joint, default)
        return val

    def get_load_moment_arm_continuous(
        self, lift: str, pos_key1: str, pos_key2: str, t: float, default: Optional[float] = None
    ) -> Optional[float]:
        """MVP continuous load MA interp."""
        if lift in ("bench", "benchpress", "incline", "incline_bench"):
            table = self.bench_load_moment_arms if lift in ("bench", "benchpress") else self.incline_bench_load_moment_arms
        elif lift in ("squat", "backsquat"):
            table = self.squat_load_moment_arms
        elif lift in ("ohp", "overhead", "overhead_press"):
            table = self.ohp_load_moment_arms
        elif lift in ("deadlift", "dl", "dlift", "romanian", "rdl", "romanian_deadlift"):
            table = self.deadlift_load_moment_arms if lift not in ("romanian", "rdl", "romanian_deadlift") else self.rdl_load_moment_arms
        else:
            return default
        return self._interpolate_value(table, pos_key1, pos_key2, t, default)

    def _infer_joint_for_region(self, lift: str, region_key: str) -> str:
        r = (region_key or "").lower()
        if lift in ("bench", "benchpress"):
            return "shoulder"
        if "glute" in r or "hamstring" in r or "erector" in r:
            return "hip" if "glute" in r or "ham" in r else "lumbar"
        if "quad" in r or "vl" in r:
            return "knee"
        if "triceps" in r:
            return "elbow"
        if "delt" in r or "trap" in r:
            return "shoulder"
        return "hip"   # reasonable last resort

    def _lookup_static_confidence(self, lift: str, region_key: str, position_key: str) -> str:
        """Internal helper used by confidence methods."""
        conf_table = self._get_confidence_table(lift, region_key)
        if conf_table and position_key in conf_table:
            return conf_table[position_key]
        load_table = self._get_load_confidence_table(lift)
        if load_table and position_key in load_table:
            return load_table[position_key]
        return "estimated"


# Convenience singleton for early use
_default_reference = ReferenceData()


def get_default_reference() -> ReferenceData:
    """Returns the shared default ReferenceData instance (recommended way to obtain reference data)."""
    return _default_reference


# Simple literature validation ranges (modeled estimates vs published proxies/ranges; for education + honesty only).
# Populated from prior math/science audit (Ackland MA, Mausehund NJM, grip EMG studies, etc.).
# Used for surfacing cross-check notes in interpret/continuous results (see wave 2).
LIT_VALIDATION_RANGES = {
    "bench_flat_bottom_~100kg_shoulder_torque_static_max_nm": (220, 350, "Mausehund et al. / typical NJM ranges (dynamic 6RM peaks often ~120Nm; static theoretical max higher)"),
    "squat_high_bar_bottom_~140kg_hip_torque_nm": (180, 320, "synthesized from squat biomech lit (varies with depth/stance/anthro)"),
    "deadlift_conventional_bottom_~180kg_hip_torque_nm": (250, 420, "posterior chain demand proxies (sumo lower overall load MA)"),
}
