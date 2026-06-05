"""
AnalysisService — high-level facade for FiberForce (v0.3 foreshadowing, delivered massively).

This is the recommended entry point for most library usage and CLI work.
It provides a clean, opinionated API over:
- Peak force calculation
- Sensitivity analysis
- Comparisons
- Reference data access
- Subject / position construction helpers (via examples + reference)

Goals:
- Hide complexity of builders, reference tables, and low-level calculator calls.
- Provide consistent error handling and result enrichment.
- Become the single place where features (multi-position, program-level analysis, persistence) are composed.

Current scope (v0.5): Full 4-lift orchestration, geometric MA integration, rich persistence, sensitivity (single + multi), multi-position (limited dynamic), program-level accumulation helpers, and first-class TrainingSession / WeeklyProgram models (in results) that compose the accumulators into session + weekly aggregates + comparison + reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, List

from fiberforce.models import (
    Subject,
    AnalyzedPosition,
    MuscleRegion,
    UserAnthropometry,
    JointAngles,
    ExternalLoad,
    LiftConfiguration,
)
from fiberforce.calculations import (
    SimplePeakForceCalculator,
    SensitivityAnalyzer,
    SensitivityResult,
    CalculationContext,
)
from fiberforce.reference import ReferenceData, get_default_reference
from fiberforce.examples import (
    build_bench_analyzed_position,
    build_squat_analyzed_position,
    build_deadlift_analyzed_position,
    build_ohp_analyzed_position,
    # NEW post-v1
    build_incline_bench_analyzed_position,
    build_romanian_deadlift_analyzed_position,
    # dynrom continuous MVP
    build_squat_continuous_positions,
    build_bench_continuous_positions,
)


@dataclass
class AnalysisResult:
    """Enriched container for a single peak force analysis."""
    results: list  # list[MuscleForceResult]
    target_regions: list[MuscleRegion]
    position_description: str
    confidence_summary: str = ""
    assumptions: dict = field(default_factory=dict)


@dataclass
class MultiPositionResult:
    """
    Lightweight rich container for multi-position (Phase 2b) analysis results.

    Wraps the ordered list of per-position AnalysisResult objects plus
    computed aggregates useful for program-level work:
    - per-position and overall force summaries + deltas (absolute + relative %)
    - identification of peak/min force positions
    - explicit geometric (anthropometry-driven) vs static table provenance across the ROM
    - region totals, variation metrics, and human-readable notes

    Designed to be drop-in friendly with existing accumulation helpers via
    duck-typing (__len__, __iter__, __getitem__ delegate to .analyses) and
    explicit .analyses / .to_list() for clarity. All fields use/derive from
    public APIs only.

    Note (v0.5): The canonical high-level program/session models (TrainingSession,
    WeeklyProgram) live in fiberforce.results and compose over lists of
    AnalysisResult (or MultiPositionResult via .analyses flattening).
    """

    analyses: list[AnalysisResult] = field(default_factory=list)

    # Context (lightweight capture of call)
    lift: str = ""
    variation: str = ""
    load_kg: float = 0.0
    target_region_name: str = ""

    # Core aggregates (populated by analyze_multi_position)
    positions: list[str] = field(default_factory=list)
    num_positions: int = 0

    # Primary region force curve (N) in position order; falls back to first result per pos
    per_position_primary_forces: list[float] = field(default_factory=list)

    # Overall stats
    avg_peak_force: float = 0.0
    force_range: tuple[float, float] = (0.0, 0.0)
    total_force_across_positions: float = 0.0
    force_deltas: list[float] = field(default_factory=list)  # consecutive differences
    relative_deltas_pct: list[float] = field(default_factory=list)

    # Geometric vs static across positions (rich Phase 2b addition)
    geometric_positions: list[str] = field(default_factory=list)
    static_positions: list[str] = field(default_factory=list)
    geometric_vs_static_summary: str = ""

    # Program-friendly highlights
    peak_force_position: str = ""
    min_force_position: str = ""
    force_variation_coefficient: float = 0.0  # simple (range/mean) proxy

    # Cross-position region totals (public key format "Muscle::Region")
    region_totals: dict[str, float] = field(default_factory=dict)

    # Free-form notes / provenance summary
    notes: str = ""

    def __post_init__(self):
        # Ensure num_positions matches if not explicitly set
        if self.num_positions == 0 and self.analyses:
            self.num_positions = len(self.analyses)

    def __len__(self) -> int:
        """Support len(mpr) and duck-typing for accumulation helpers."""
        return len(self.analyses)

    def __iter__(self):
        """Iterate over the underlying AnalysisResult list (enables for res in mpr)."""
        return iter(self.analyses)

    def __getitem__(self, index):
        """Index access (enables mpr[0], slicing in some contexts)."""
        return self.analyses[index]

    def to_list(self) -> list[AnalysisResult]:
        """Explicit public accessor for the list of per-position results."""
        return list(self.analyses)

    # Backward-compat aliases (some early tests / CLI paths used .results)
    @property
    def results(self) -> list[AnalysisResult]:
        return self.analyses

    def summary_dict(self) -> dict:
        """Return a compact dict view of the key aggregates (useful for logging/CLI)."""
        return {
            "lift": self.lift,
            "variation": self.variation,
            "load_kg": self.load_kg,
            "num_positions": self.num_positions,
            "positions": self.positions,
            "avg_peak_force": self.avg_peak_force,
            "force_range": self.force_range,
            "peak_force_position": self.peak_force_position,
            "min_force_position": self.min_force_position,
            "geometric_vs_static_summary": self.geometric_vs_static_summary,
            "region_totals": self.region_totals,
            "notes": self.notes,
        }

    def interpret(self) -> str:
        """
        0.7→0.8 usability helper: turn the rich aggregates into concise,
        non-prescriptive coaching language.

        Focuses on the most useful signals for programming decisions:
        - Where force peaked / bottomed out
        - How much variation existed across positions
        - Geometric vs static provenance (trust / limitation signal)
        - Relative insight vs single-position analysis
        """
        parts: list[str] = []

        # Core context - try hard to produce readable short position names
        def _short(p: str) -> str:
            if not p: return p
            # Common patterns from builders
            p = p.split("|")[0].strip()
            # Take last meaningful token if very long (e.g. "140kg Squat ... @ bottom")
            if len(p) > 28:
                tokens = p.split()
                if "bottom" in p.lower(): return "bottom"
                if "mid" in p.lower(): return "mid"
                if "top" in p.lower() or "lockout" in p.lower(): return "top/lockout"
                return tokens[-1] if tokens else p[:20]
            return p
        short_pos = [_short(p) for p in self.positions]
        ctx = f"{self.lift} ({self.variation}) @ {self.load_kg}kg targeting '{self.target_region_name}'"
        pos_str = ", ".join(short_pos) if short_pos else "n/a"
        parts.append(f"Multi-position analysis for {ctx} across {self.num_positions} positions ({pos_str}).")

        # Peak / min location insight (clean labels)
        def _clean(pos: str) -> str:
            return pos.split("|")[0].strip() if "|" in pos else pos

        peak = _clean(self.peak_force_position) if self.peak_force_position else ""
        mn = _clean(self.min_force_position) if self.min_force_position else ""

        if peak and mn:
            if peak == mn:
                parts.append(f"  • Force demand was very stable (peak and minimum both observed at {peak}).")
            else:
                parts.append(f"  • Highest demand at {peak}, lowest at {mn}.")
                if self.force_deltas:
                    d = min(self.force_deltas)
                    if abs(d) > 50:
                        parts.append(f"    Largest consecutive change: {abs(d):.0f} N.")

        # Variation signal (more nuanced language)
        vc = self.force_variation_coefficient
        if vc > 0.20:
            parts.append(f"  • High variation across the ROM (variation coeff ≈ {vc:.2f}). Position choice likely matters significantly for this target.")
        elif vc > 0.10:
            parts.append(f"  • Moderate variation across positions (coeff ≈ {vc:.2f}). Different depths or joint angles change stress meaningfully.")
        elif vc > 0.03:
            parts.append(f"  • Relatively stable demand (coeff ≈ {vc:.2f}).")
        else:
            parts.append("  • Extremely flat force profile across the tested positions.")

        # Dominance % and efficiency (from multi-prime-mover expansion + PR layer; higher dom = better leverage)
        if self.analyses and self.analyses[0].results:
            first_res = self.analyses[0].results[0] if self.analyses[0].results else None
            if first_res:
                dom = getattr(first_res, "dominance_percent", None)
                if dom is not None:
                    parts.append(f"  • Peak modeled dominance % for primary target in first position: {dom:.1f}% (relative MA share vs co-movers at the joint; larger = higher mechanical advantage / lower force needed). Variation/grip/stance shifts this (see PRs in History for your personal bests).")
                # Simple eff if load known
                ft = getattr(first_res, "peak_torque_ftlb", None)
                if ft and self.load_kg:
                    eff = ft / (self.load_kg * 2.20462) if self.load_kg else None
                    if eff:
                        parts.append(f"    Efficiency proxy (ft-lb per lb load): ~{eff:.2f} (modeled; for relative tracking).")

        # Geometric provenance (critical honesty + trust signal)
        geo = self.geometric_vs_static_summary.lower()
        if "all" in geo and "geometric" in geo:
            parts.append("  • All positions used geometric (user anthropometry-driven) moment arms — best personalization available in current model.")
        elif "geometric" in geo:
            parts.append(f"  • Mixed: {self.geometric_vs_static_summary}. Check per-position notes for which relied on your measurements.")
        else:
            parts.append("  • Static reference tables only (no personal anthropometry applied to moment arms).")

        # Program / decision value
        parts.append("  • This data shows how stress on the target changes with position — useful for choosing exercise variations or emphasis points (e.g. pause reps, partials, or stance tweaks).")
        parts.append("    Always combine with technique quality, joint comfort, and actual performance data before making training changes.")

        if self.notes:
            parts.append(f"  Additional notes: {self.notes}")

        return "\n".join(parts)


@dataclass
class TrainingSession:
    """
    v0.5 lightweight program-level container (Phase 3a/3b).

    Holds a sequence of analyses (single-position or MultiPositionResult)
    representing a training session or week, plus accumulated regional stress/volume.

    Designed for early program-level work: weekly volume tracking, comparing
    programs, simple periodization signals. Uses the existing accumulation
    helpers under the hood.
    """
    name: str = "Training Session"
    analyses: List[Union[AnalysisResult, "MultiPositionResult"]] = field(default_factory=list)
    notes: str = ""

    def add(self, analysis: Union[AnalysisResult, "MultiPositionResult"], weight: float = 1.0):
        """Add a single analysis or multi-position result to the session."""
        self.analyses.append(analysis)

    def regional_stress(self) -> dict:
        """Aggregate regional stress across all contained analyses."""
        flat = []
        for a in self.analyses:
            if hasattr(a, "results"):
                flat.extend(a.results)
            else:
                flat.append(a)
        return AnalysisService().accumulate_regional_stress(flat) if flat else {}

    def summary(self) -> dict:
        """High-level session summary."""
        return {
            "name": self.name,
            "num_analyses": len(self.analyses),
            "regional_stress": self.regional_stress(),
        }


class AnalysisService:
    """
    High-level service for biomechanical analysis.

    Example usage:
        service = AnalysisService()
        subject = service.create_subject_from_measurements(humerus=32, ...)
        pos = service.build_position("ohp", load_kg=70, variation="standing", position="bottom", target_region_name="Anterior")
        result = service.analyze(subject, pos)

        sens = service.sensitivity(subject, pos, variable="load_kg", values=[60,70,80])

        # Program-level (v0.4/v0.5): accumulate over multi-position or batch results
        # v0.5 Phase 2b: returns rich MultiPositionResult (duck-types as list of AnalysisResult for compat)
        mpr = service.analyze_multi_position(subject, "squat", ["bottom", "mid", "top"], load_kg=120)
        stress = service.accumulate_regional_stress(mpr)
        vol = service.accumulate_regional_volume(mpr, volume_factors=3*8)
        print(mpr.geometric_vs_static_summary)  # rich aggregates example
    """

    def __init__(
        self,
        calculator: Optional[SimplePeakForceCalculator] = None,
        sensitivity_analyzer: Optional[SensitivityAnalyzer] = None,
        reference: Optional[ReferenceData] = None,
    ):
        self.calculator = calculator or SimplePeakForceCalculator()
        self.sensitivity_analyzer = sensitivity_analyzer or SensitivityAnalyzer(self.calculator)
        self.reference = reference or get_default_reference()
        self.context = CalculationContext(
            reference_data_source=f"ReferenceData v{self.reference.version}"
        )

    # ------------------------------------------------------------------
    # High-level analysis methods
    # ------------------------------------------------------------------

    def analyze(
        self,
        subject: Subject,
        position: AnalyzedPosition,
        target_regions: Optional[list[MuscleRegion]] = None,
    ) -> AnalysisResult:
        """Run peak force analysis with rich result packaging."""
        if target_regions:
            position.target_regions = target_regions

        raw_results = self.calculator.calculate_peak_force(
            subject, position, self.context
        )

        # Build confidence summary
        conf_levels = [r.confidence_level for r in raw_results]
        conf_summary = ", ".join(sorted(set(conf_levels)))

        return AnalysisResult(
            results=raw_results,
            target_regions=position.target_regions,
            position_description=position.pose.describe(),
            confidence_summary=conf_summary,
            assumptions=self.context.assumptions,
        )

    def sensitivity(
        self,
        subject: Subject,
        base_position: AnalyzedPosition,
        variable: str,
        values: list[Any],
        target_region: MuscleRegion,
        rebuild_position: Optional[callable] = None,
    ) -> SensitivityResult:
        """Convenience wrapper around SensitivityAnalyzer."""
        return self.sensitivity_analyzer.run(
            subject=subject,
            base_position=base_position,
            variable=variable,
            values=values,
            target_region=target_region,
            rebuild_position=rebuild_position,
            context=self.context,
        )

    def sensitivity_multi(
        self,
        subject: Subject,
        base_position: AnalyzedPosition,
        variables: list[tuple[str, list[Any]]],
        target_region: MuscleRegion,
        rebuild_multi: callable,
    ) -> list[SensitivityResult]:
        """Multi-variable sensitivity (sequential sweeps)."""
        return self.sensitivity_analyzer.run_multi(
            subject=subject,
            base_position=base_position,
            variables=variables,
            target_region=target_region,
            rebuild_multi=rebuild_multi,
            context=self.context,
        )

    def _detect_geometric_usage(self, analyzed_position: "AnalyzedPosition", analysis_result: AnalysisResult) -> bool:
        """Helper extracted during 0.6 polish for clarity."""
        # Rich geometric vs static detection using PUBLIC fields only
        # (attachment notes set by builders + reference; fallback to result fields)
        for att in (getattr(analyzed_position.pose, "active_attachments", []) or []):
            n = (getattr(att, "notes", "") or "").lower()
            if "geometric" in n or "anthropometry-driven" in n:
                return True
        for r in (analysis_result.results or []):
            cl = (getattr(r, "confidence_level", "") or "").lower()
            rn = (getattr(r, "notes", "") or "").lower()
            if "geometric" in cl or "geometric" in rn or "anthropometry" in rn:
                return True
        return False

    def analyze_multi_position(
        self,
        subject: Subject,
        lift: str,
        positions: list[str],
        load_kg: float = 100.0,
        variation: str = "flat",
        target_region_name: str = "Sternal fibers",
        **kwargs,
    ) -> MultiPositionResult:
        """v0.5 Phase 2b: Analyze the same lift at multiple discrete positions in one call.

        Returns a rich MultiPositionResult containing the ordered list[AnalysisResult]
        plus computed aggregates: force curves, deltas (abs + %), peak/min identification,
        explicit geometric-vs-static provenance per position (via attachment notes + confidence),
        region totals, and program-useful summaries.

        The returned object duck-types as a list of AnalysisResult for seamless integration
        with accumulate_regional_stress/volume, summarize_* etc. (len, iter, getitem supported).

        All aggregation uses only public fields on AnalysisResult / MuscleForceResult /
        AnalyzedPosition (attachments, notes, confidence_level).
        """
        multi_pos = self.build_multi_position(
            lift, positions,
            load_kg=load_kg,
            variation=variation,
            target_region_name=target_region_name,
            **kwargs
        )

        analyses: list[AnalysisResult] = []
        geo_flags: list[bool] = []
        pos_descriptions: list[str] = []

        for p in multi_pos:
            res = self.analyze(subject, p)
            analyses.append(res)

            # Position description (public)
            desc = res.position_description or getattr(p.pose, "name", "unknown")
            pos_descriptions.append(desc)

            # Rich geometric vs static detection using PUBLIC fields only
            used_geo = self._detect_geometric_usage(p, res)
            geo_flags.append(used_geo)

        # --- Build rich aggregates (delegated to helper for 0.6 polish) ---
        aggregates = self._assemble_multi_position_aggregates(
            analyses=analyses,
            pos_descriptions=pos_descriptions,
            geo_flags=geo_flags,
            lift=lift,
            variation=variation,
            load_kg=load_kg,
            target_region_name=target_region_name,
        )

        return MultiPositionResult(
            analyses=analyses,
            lift=lift,
            variation=variation,
            load_kg=load_kg,
            target_region_name=target_region_name,
            **aggregates,
        )

    def _assemble_multi_position_aggregates(
        self,
        analyses: list[AnalysisResult],
        pos_descriptions: list[str],
        geo_flags: list[bool],
        lift: str,
        variation: str,
        load_kg: float,
        target_region_name: str,
    ) -> dict:
        """Helper extracted during 0.6 polish to reduce length of analyze_multi_position."""
        num = len(analyses)
        positions_list = pos_descriptions[:]

        primary_forces: list[float] = []
        all_overall_forces: list[float] = []
        per_pos_forces_map: list[dict] = []
        all_region_keys: set[str] = set()

        for res in analyses:
            pos_forces: dict[str, float] = {}
            primary = 0.0
            if res.results:
                primary = res.results[0].peak_force_newtons
                primary_forces.append(primary)
            else:
                primary_forces.append(0.0)

            for r in (res.results or []):
                key = f"{r.muscle_region.muscle_name}::{r.muscle_region.region_name}"
                all_region_keys.add(key)
                val = r.peak_force_newtons
                pos_forces[key] = val
                all_overall_forces.append(val)
            per_pos_forces_map.append(pos_forces)

        region_totals: dict[str, float] = {}
        for key in all_region_keys:
            region_totals[key] = sum(pf.get(key, 0.0) for pf in per_pos_forces_map)

        if primary_forces:
            avg = sum(primary_forces) / len(primary_forces)
            fmin = min(primary_forces)
            fmax = max(primary_forces)
            force_range = (fmin, fmax)
            total = sum(primary_forces)
        else:
            avg = 0.0
            force_range = (0.0, 0.0)
            total = 0.0
            primary_forces = []

        deltas: list[float] = []
        rel_deltas: list[float] = []
        for i in range(1, len(primary_forces)):
            d = primary_forces[i] - primary_forces[i-1]
            deltas.append(round(d, 2))
            prev = primary_forces[i-1]
            rp = (d / prev * 100.0) if prev != 0 else 0.0
            rel_deltas.append(round(rp, 1))

        peak_idx = primary_forces.index(max(primary_forces)) if primary_forces else 0
        min_idx = primary_forces.index(min(primary_forces)) if primary_forces else 0
        peak_pos = positions_list[peak_idx] if positions_list and peak_idx < len(positions_list) else ""
        min_pos = positions_list[min_idx] if positions_list and min_idx < len(positions_list) else ""

        if avg > 0 and force_range[1] > force_range[0]:
            var_coeff = (force_range[1] - force_range[0]) / avg
        else:
            var_coeff = 0.0

        geo_pos_names: list[str] = []
        static_pos_names: list[str] = []
        for i, is_geo in enumerate(geo_flags):
            pname = positions_list[i] if i < len(positions_list) else f"pos{i}"
            if is_geo:
                geo_pos_names.append(pname)
            else:
                static_pos_names.append(pname)

        if num > 0:
            gcount = len(geo_pos_names)
            scount = len(static_pos_names)
            if gcount and not scount:
                geo_summary = f"All {num} positions used geometric (anthropometry-driven) MA estimates."
            elif scount and not gcount:
                geo_summary = f"All {num} positions used static reference table MA values."
            else:
                geo_summary = (
                    f"Geometric estimates used in {gcount}/{num} positions (anthropometry-driven MA); "
                    f"{scount} static table fallback(s)."
                )
        else:
            geo_summary = "No positions analyzed."

        notes_parts = [
            f"Multi-position analysis for {lift} ({variation}) @ {load_kg}kg targeting '{target_region_name}'.",
            geo_summary,
        ]
        if deltas:
            notes_parts.append(f"Force deltas observed: {deltas}")
        notes = " ".join(notes_parts)

        return {
            "positions": positions_list,
            "num_positions": num,
            "per_position_primary_forces": primary_forces,
            "avg_peak_force": round(avg, 2),
            "force_range": (round(force_range[0], 2), round(force_range[1], 2)),
            "total_force_across_positions": round(total, 2),
            "force_deltas": deltas,
            "relative_deltas_pct": rel_deltas,
            "geometric_positions": geo_pos_names,
            "static_positions": static_pos_names,
            "geometric_vs_static_summary": geo_summary,
            "peak_force_position": peak_pos,
            "min_force_position": min_pos,
            "force_variation_coefficient": round(var_coeff, 3),
            "region_totals": region_totals,
            "notes": notes,
        }

    def summarize_multi_position(self, results: Union[list[AnalysisResult], "MultiPositionResult"]) -> dict:
        """v0.4/v0.5 lightweight helper for multi-position results: given list[AnalysisResult] (or
        a MultiPositionResult from analyze_multi_position), return useful aggregates over the ROM.

        Works for both single-region and multi-region. Reports per-position breakdowns + overall stats.
        Uses only public AnalysisResult + MuscleForceResult fields. Enhanced for Phase 2b.
        """
        # Normalize MPR or list (public duck-type support)
        if hasattr(results, "analyses") and not isinstance(results, (list, tuple)):
            results = results.analyses

        if not results:
            return {"num_positions": 0, "positions": [], "regions": [], "totals_by_region": {}}

        positions = []
        all_region_keys = set()
        per_pos_forces: list[dict] = []
        overall_forces: list[float] = []

        for res in results:
            pos_desc = res.position_description or "unknown"
            positions.append(pos_desc)
            pos_forces = {}
            for r in (res.results or []):
                key = f"{r.muscle_region.muscle_name}::{r.muscle_region.region_name}"
                all_region_keys.add(key)
                val = r.peak_force_newtons
                pos_forces[key] = val
                overall_forces.append(val)
            per_pos_forces.append(pos_forces)

        # Aggregate totals per region across positions
        totals_by_region: dict[str, float] = {}
        for key in all_region_keys:
            totals_by_region[key] = sum(pf.get(key, 0.0) for pf in per_pos_forces)

        avg = sum(overall_forces) / len(overall_forces) if overall_forces else 0.0
        force_range = (min(overall_forces), max(overall_forces)) if overall_forces else (0.0, 0.0)
        deltas = (
            [overall_forces[i] - overall_forces[i-1] for i in range(1, len(overall_forces))]
            if len(overall_forces) > 1 else []
        )

        return {
            "num_positions": len(results),
            "positions": positions,
            "regions": sorted(all_region_keys),
            "avg_peak_force": avg,
            "force_range": force_range,
            "force_deltas": deltas,
            "totals_by_region": totals_by_region,
            "per_position": per_pos_forces,
        }

    # ------------------------------------------------------------------
    # v0.4/v0.5 Program-level accumulation helpers (Phase 3a/3b overlap with multi-position)
    # These consume lists of AnalysisResult (from analyze(), analyze_multi_position(),
    # or batched runs) and provide simple regional stress/volume proxies.
    # All use *only public APIs* on AnalysisResult / MuscleForceResult and integrate
    # naturally with build_multi_position + analyze_multi_position results.
    # ------------------------------------------------------------------

    def accumulate_regional_stress(
        self,
        analyses: list[AnalysisResult],
        weight: Union[float, list[float]] = 1.0,
    ) -> dict:
        """Basic accumulation helper: consumes list[AnalysisResult] (single analyses or
        multi-position results) and accumulates weighted peak forces per muscle region
        as a simple stress proxy (units: N * weight).

        Supports scalar weight or per-analysis weights (list of same length).
        Fully supports multi-region AnalysisResults and empty inputs.
        Designed for program-level patterns: weekly volume, session accumulation, ROM totals.

        Returns: {"<Muscle::Region>": total_stress, ... , "meta": {...}}
        """
        from collections import defaultdict

        # v0.5 Phase 2b: accept list[AnalysisResult] or MultiPositionResult (duck + explicit)
        if hasattr(analyses, "analyses") and not isinstance(analyses, (list, tuple)):
            analyses = analyses.analyses

        if not analyses:
            return {"meta": {"num_analyses": 0, "applied_weights": []}}

        n = len(analyses)
        if isinstance(weight, (int, float)):
            weights = [float(weight)] * n
        else:
            weights = list(weight)
            if len(weights) != n:
                raise ValueError(f"weight list length {len(weights)} must match analyses length {n}")
            weights = [float(w) for w in weights]

        accumulator: dict[str, float] = defaultdict(float)
        contribs = []
        for i, res in enumerate(analyses):
            w = weights[i]
            analysis_contrib = {}
            for r in (res.results or []):
                key = f"{r.muscle_region.muscle_name}::{r.muscle_region.region_name}"
                delta = r.peak_force_newtons * w
                accumulator[key] += delta
                analysis_contrib[key] = analysis_contrib.get(key, 0.0) + delta
            contribs.append(analysis_contrib)

        return {
            **dict(accumulator),
            "meta": {
                "num_analyses": n,
                "regions": sorted(accumulator.keys()),
                "applied_weights": weights,
                "total_stress": sum(accumulator.values()),
                "per_analysis_contribs": contribs,
            },
        }

    def accumulate_regional_volume(
        self,
        analyses: list[AnalysisResult],
        volume_factors: Optional[Union[float, list[float]]] = None,
        weight: float = 1.0,
    ) -> dict:
        """Basic volume-aware regional accumulator for program-level / session modeling.

        Consumes lists of AnalysisResult (ideal for results of analyze_multi_position or
        batched single-position runs). Computes proxy "volume stress" = peak_force * vol_factor * weight
        per region. 

        volume_factors: scalar (e.g. sets*reps or 1.0) applied to all, or list matching len(analyses)
        for position/session-specific volume (e.g. different emphasis or rep schemes per depth).
        Ties cleanly into existing multi-position helpers.

        Returns structured accumulation dict with meta (public API only).
        """
        from collections import defaultdict

        # v0.5 Phase 2b: accept list or MultiPositionResult
        if hasattr(analyses, "analyses") and not isinstance(analyses, (list, tuple)):
            analyses = analyses.analyses
        elif hasattr(analyses, "results") and not isinstance(analyses, (list, tuple)):
            analyses = analyses.results

        if not analyses:
            return {"meta": {"num_analyses": 0}}

        n = len(analyses)
        if volume_factors is None:
            vols = [1.0] * n
        elif isinstance(volume_factors, (int, float)):
            vols = [float(volume_factors)] * n
        else:
            vols = [float(v) for v in volume_factors]
            if len(vols) != n:
                raise ValueError(f"volume_factors list length must match analyses ({n})")

        accumulator: dict[str, float] = defaultdict(float)
        for i, res in enumerate(analyses):
            vol = vols[i]
            for r in (res.results or []):
                key = f"{r.muscle_region.muscle_name}::{r.muscle_region.region_name}"
                accumulator[key] += r.peak_force_newtons * vol * weight

        return {
            **dict(accumulator),
            "meta": {
                "num_analyses": n,
                "regions": sorted(accumulator.keys()),
                "volume_factors_used": vols,
                "weight": weight,
                "total_volume_stress": sum(accumulator.values()),
            },
        }

    def summarize_regional_accumulation(self, analyses: list[AnalysisResult]) -> dict:
        """Convenience high-level summary over a list of AnalysisResults (from multi-pos or mixed).
        Combines regional stress accumulation + basic stats. Uses public APIs exclusively.
        Perfect bridge between analyze_multi_position outputs and program-level insights.
        """
        # v0.5 Phase 2b normalize for len + pass-through (duck-typing also works)
        if hasattr(analyses, "analyses") and not isinstance(analyses, (list, tuple)):
            norm_analyses = analyses.analyses
        else:
            norm_analyses = analyses

        stress = self.accumulate_regional_stress(analyses)
        vol = self.accumulate_regional_volume(analyses)  # defaults to 1x

        # Simple top region extraction (public keys)
        totals = {k: v for k, v in stress.items() if not k.startswith("meta")}
        top_region = max(totals.items(), key=lambda kv: kv[1])[0] if totals else None

        return {
            "num_analyses": len(norm_analyses),
            "regions_covered": stress.get("meta", {}).get("regions", []),
            "total_stress_proxy": stress.get("meta", {}).get("total_stress", 0.0),
            "total_volume_proxy": vol.get("meta", {}).get("total_volume_stress", 0.0),
            "regional_totals": totals,
            "top_region_by_stress": top_region,
            "accumulation_meta": stress.get("meta", {}),
        }

    def compare(
        self,
        lift: str,
        config_a: str,
        config_b: str,
        load_kg: float = 100.0,
        target: str = "Sternal fibers",
        **anthro_overrides,
    ):
        """
        High-level two-way comparison, fully routed through the service.

        Returns a ComparisonResult (from visualization) for direct use by CLI + plot_comparison.
        Now supports all lifts (bench, squat, deadlift, ohp) via unified build_position.
        """
        # Local import prevents potential import cycles and keeps viz concerns in viz layer
        from fiberforce.visualization import ComparisonResult
        from fiberforce.models import KNOWN_MUSCLE_REGIONS as MODEL_REGIONS, Subject, UserAnthropometry

        target_region = next(
            (r for r in MODEL_REGIONS if r.region_name.lower() == target.lower()),
            MODEL_REGIONS[0],
        )

        # Route through our own build_position (the single source of truth)
        pos_a = self.build_position(
            lift, load_kg=load_kg, variation=config_a, target_region_name=target, **anthro_overrides
        )
        pos_b = self.build_position(
            lift, load_kg=load_kg, variation=config_b, target_region_name=target, **anthro_overrides
        )

        # Reasonable default anthropometry based on lift family
        lift_l = lift.lower()
        if lift_l in ("squat", "deadlift", "backsquat", "dl", "dlift"):
            anthro = UserAnthropometry(
                femur_length_cm=anthro_overrides.get("femur_cm", anthro_overrides.get("femur", 42.0)),
                tibia_length_cm=anthro_overrides.get("tibia_cm", anthro_overrides.get("tibia", 38.0)),
            )
        else:
            anthro = UserAnthropometry(
                humerus_length_cm=anthro_overrides.get("humerus_cm", anthro_overrides.get("humerus", 32.0)),
                forearm_length_cm=anthro_overrides.get("forearm_cm", anthro_overrides.get("forearm", 25.5)),
                biacromial_width_cm=anthro_overrides.get("biacromial_cm", anthro_overrides.get("biacromial", 38.0)),
            )

        subject = Subject(anthropometry=anthro)

        # Use our analyze path for consistency (enriched results)
        res_a = self.analyze(subject, pos_a).results
        res_b = self.analyze(subject, pos_b).results

        match_a = next((r for r in res_a if r.muscle_region.region_name == target_region.region_name), None)
        match_b = next((r for r in res_b if r.muscle_region.region_name == target_region.region_name), None)

        force_a = match_a.peak_force_newtons if match_a else 0.0
        force_b = match_b.peak_force_newtons if match_b else 0.0
        conf_a = match_a.confidence_level if match_a else ""
        conf_b = match_b.confidence_level if match_b else ""

        return ComparisonResult(
            lift=lift,
            config_a=config_a,
            config_b=config_b,
            load_kg=load_kg,
            target=target,
            force_a_n=force_a,
            force_b_n=force_b,
            confidence_a=conf_a,
            confidence_b=conf_b,
        )

    # ------------------------------------------------------------------
    # Convenience builders (delegating to examples + reference)
    # ------------------------------------------------------------------

    def build_position(
        self,
        lift: str,
        **kwargs,
    ) -> AnalyzedPosition:
        """
        High-level position builder. **Primary/only** way the CLI and high-level code
        should construct AnalyzedPosition objects.

        Supported lifts: "bench", "incline", "squat", "deadlift", "romanian"/"rdl", "ohp" (and common aliases).

        All kwargs are forwarded (load_kg, variation, position, target_region_name,
        humerus_cm/forearm_cm/biacromial_cm for OHP+bench, femur/tibia for squat+dl).

        OHP examples:
            service.build_position("ohp", load_kg=70, variation="standing", position="bottom", target_region_name="Anterior")
            service.build_position("ohp", 65, "seated", "mid", "Lateral")
            service.build_position("ohp", load_kg=60, variation="standing", position="lockout", target_region_name="Triceps")
        """
        lift = lift.lower()

        # Basic validation for common mistakes (improved UX for 0.6)
        variation = kwargs.get("variation")
        target = kwargs.get("target_region_name")

        if lift in ("squat", "backsquat") and variation and variation not in ("high_bar", "low_bar"):
            # Still allow it (builders are permissive), but we could warn in future
            pass

        if lift in ("bench", "benchpress", "squat", "backsquat", "deadlift", "dl", "ohp"):
            # These lifts are supported; proceed
            pass

        if lift in ("bench", "benchpress"):
            return build_bench_analyzed_position(**kwargs)
        elif lift in ("incline", "incline_bench", "inclinebench"):
            return build_incline_bench_analyzed_position(**kwargs)
        elif lift in ("squat", "backsquat", "front", "front_squat"):
            # front -> squat with appropriate var (caller can pass variation="olympic" etc)
            if lift in ("front", "front_squat") and not kwargs.get("variation"):
                kwargs = dict(kwargs)
                kwargs["variation"] = "olympic"
            return build_squat_analyzed_position(**kwargs)
        elif lift in ("deadlift", "dl", "deadlifts", "sumo"):
            if lift == "sumo" and not kwargs.get("variation"):
                kwargs = dict(kwargs)
                kwargs["variation"] = "sumo"
            return build_deadlift_analyzed_position(**kwargs)
        elif lift in ("romanian", "rdl", "romanian_deadlift"):
            return build_romanian_deadlift_analyzed_position(**kwargs)
        elif lift in ("ohp", "overhead", "overheadpress", "overhead_press", "military"):
            return build_ohp_analyzed_position(**kwargs)
        else:
            raise ValueError(
                f"Unsupported lift for build_position: {lift}. "
                "Supported: bench, incline, squat, deadlift, rdl/romanian, ohp. "
                "Use the specific build_*_analyzed_position functions only for advanced low-level control."
            )

    def create_subject_from_measurements(
        self,
        name: str = "Analysis Subject",
        units: str = "metric",  # internal default "metric"; user-facing (CLI/GUI/recipes) override to "imperial"
        **measurements,
    ) -> Subject:
        """Quick Subject factory from keyword anthropometry measurements.

        units: "imperial" (inches -> internal cm, default for user-friendliness) or "metric" (cm).
        For loads, use ExternalLoad.from_lbs() or pass mass_kg.
        """
        if units == "imperial":
            anthro = UserAnthropometry.from_inches(name=name, **measurements)
        else:
            anthro = UserAnthropometry(name=name, **measurements)
        return Subject(anthropometry=anthro, name=name)

    def get_reference(self) -> ReferenceData:
        """Direct access to the reference data backing this service."""
        return self.reference

    def describe(self) -> str:
        return (
            f"AnalysisService (FiberForce 0.5+ with 0.6 polish)\n"
            f"  Calculator: {type(self.calculator).__name__}\n"
            f"  Reference: {self.reference.describe()}\n"
            f"  Sensitivity (single + multi): Yes\n"
            f"  Compare: Yes (routed through build+analyze)\n"
            f"  Full lift parity: bench | incline | squat | deadlift (conv+sumo) | rdl/romanian | ohp (standing/seated/strict + bottom/mid/lockout + multi-delt + triceps)\n  Multi-position + continuous ROM (MVP dynrom): rich MultiPositionResult; build/analyze_continuous for dynamics\n"
            f"  Program-level accumulation: Yes (accumulate_regional_stress, accumulate_regional_volume, summarize_multi_position, summarize_regional_accumulation)\n"
            f"  Persistence: Full via fiberforce.results + profiles (Saved*Run, profile-based multi-var)\n"
            f"  CLI primary backend: Yes"
        )

    def interpret(self, mpr: "MultiPositionResult") -> str:
        """0.7→0.8 convenience wrapper: rich human-language interpretation of a MultiPositionResult."""
        if mpr is None:
            return "No multi-position result provided."
        return mpr.interpret()

    def sensitivity_insight(self, result) -> str:
        """0.7→0.8 convenience: human takeaway from a SensitivityResult."""
        if result is None:
            return "No sensitivity result provided."
        return result.insight() if hasattr(result, "insight") else str(result)

    def build_multi_position(
        self,
        lift: str,
        positions: list[str],
        **common_kwargs,
    ) -> list[AnalyzedPosition]:
        """v0.4 convenience: build the same lift at multiple discrete positions in one call.

        Returns list of AnalyzedPosition in the order of `positions`.
        Common kwargs (load_kg, variation, target, anthro flags, use_geometric) are forwarded.
        """
        return [
            self.build_position(lift, position=pos, **common_kwargs)
            for pos in positions
        ]

    # ------------------------------------------------------------------
    # Continuous / dynamic ROM (post-v1 Theme 1 MVP: full dynamics/ROM curves)
    # ------------------------------------------------------------------

    def build_continuous_positions(
        self,
        lift: str,
        steps: int = 5,
        **kwargs,
    ) -> list[AnalyzedPosition]:
        """
        High-level continuous ROM builder (MVP).
        Supports knee-driven for squat/romanian, shoulder for bench/incline.
        Returns list[AnalyzedPosition] ready for analyze loop or MultiPositionResult.
        """
        lift_l = lift.lower()
        if lift_l in ("squat", "backsquat"):
            return build_squat_continuous_positions(steps=steps, **kwargs)
        elif lift_l in ("bench", "benchpress"):
            return build_bench_continuous_positions(steps=steps, **kwargs)
        # For new lifts (incline, rdl) fall back to squat/bench proxy for MVP or error
        elif lift_l in ("incline", "incline_bench"):
            return build_bench_continuous_positions(steps=steps, **kwargs)  # reuse bench continuous for now
        elif lift_l in ("romanian", "rdl", "romanian_deadlift"):
            return build_squat_continuous_positions(steps=steps, **kwargs)  # hip hinge proxy
        else:
            # fallback to discrete multi for other lifts
            poss = kwargs.pop("positions", ["bottom", "mid", "top"])
            return self.build_multi_position(lift, poss, **kwargs)

    def analyze_continuous(
        self,
        subject: Subject,
        lift: str,
        steps: int = 5,
        target_regions: Optional[list[MuscleRegion]] = None,
        tempo_s_per_step: float = 0.75,
        **kwargs,
    ) -> "MultiPositionResult":
        """
        Analyze over continuous ROM (MVP + Wave 3 fuller).
        tempo_s_per_step: assumed time per ROM step for velocity estimate (exposes 'tempo' for F-V demo; real lifters vary).
        Returns MultiPositionResult (reused for aggregates, interpret, deltas, etc.).
        Adds 'continuous': True and range info to context.
        """
        multi_pos = self.build_continuous_positions(lift, steps=steps, **kwargs)
        analyses: list[AnalysisResult] = []
        lift_l = lift.lower()
        primary = "knee" if any(x in lift_l for x in ("squat", "romanian", "front", "rdl")) else "shoulder"
        prev_angle = None
        time_per_step = tempo_s_per_step  # now exposed for better v est and user control in future GUI
        for i, pos in enumerate(multi_pos):
            if target_regions:
                pos.target_regions = target_regions
            res = self.analyze(subject, pos)
            # angle for velocity estimate (for F-V demo in continuous)
            angle = 90.0
            if hasattr(pos, "pose") and hasattr(pos.pose, "joint_angles"):
                angle = pos.pose.joint_angles.values.get(primary, 90.0)
            est_v = 0.0
            if prev_angle is not None:
                delta = abs(angle - prev_angle)
                excursion_cm_per_deg = 0.4  # rough for many muscles
                est_v = (delta * excursion_cm_per_deg) / time_per_step
            fv = 1.0
            if hasattr(self, "calculator") and est_v > 0:
                fv = self.calculator._force_velocity_multiplier(est_v)
            # Make L-T / F-V / continuous modeling visible and apply F-V scaling for richer ROM profile
            for r in (res.results or []):
                base_note = getattr(r, "notes", "") or ""
                r.notes = base_note + f" [L-T (angle-dep) applied in continuous ROM; F-V={fv:.2f} for est v={est_v:.1f} cm/s (tempo ~{time_per_step}s/step demo)]"
                if est_v > 0 and hasattr(r, "peak_force_newtons") and r.peak_force_newtons:
                    r.peak_force_newtons = round(r.peak_force_newtons * fv, 2)
                # Note: do not scale joint torque (external load demand is fixed); muscle force is what L-T/F-V modulates. ft-lb display in GUI/recipes derives from it where needed.
            prev_angle = angle
            analyses.append(res)

        mpr = MultiPositionResult(
            analyses=analyses,
            lift=lift,
            variation=kwargs.get("variation", "flat"),
            load_kg=kwargs.get("load_kg", kwargs.get("load_lbs", 100.0) * 0.453592 if "load_lbs" in kwargs else 100.0),
            target_region_name=kwargs.get("target_region_name", "Sternal fibers"),
            positions=[getattr(p, 'position_description', f"step_{i}") for i, p in enumerate(multi_pos)],
            num_positions=len(analyses),
        )
        # Continuous-specific note for the wave (L-T + F-V scaling applied per step)
        mpr.notes = (getattr(mpr, "notes", "") or "") + " [Continuous ROM: angle-dependent L-T + estimated F-V scaling (from step deltas) applied to per-position muscle forces for richer demand profile. Velocity is demo (assumed tempo); see individual result notes for factors. Still per-snapshot peaks (no full kinetics/inertia).] [Lit cross-check example (from audit): for ~100kg bench bottom static max shoulder torque, typical ranges ~220-350 Nm (dynamic lower; see limitations + LIT_VALIDATION_RANGES).]"
        # The internal _assemble... is private; call public path or duplicate minimal aggregates
        # For MVP reuse the enrichment from analyze_multi_position by faking
        # Simpler: let caller use the list, or trigger aggregation
        # To keep compatible, we can manually set some fields or call internal if exposed.
        # For now, return and let MultiPositionResult's interpret etc work on analyses list (it does via duck in many places)
        # Enrich a bit
        if analyses:
            forces = []
            for a in analyses:
                if a.results:
                    forces.append(a.results[0].peak_force_newtons)
            if forces:
                mpr.per_position_primary_forces = forces
                mpr.avg_peak_force = sum(forces) / len(forces)
                mpr.force_range = (min(forces), max(forces))
        return mpr

    # ------------------------------------------------------------------
    # Persistence integration (new in enhanced persistence phase)
    # ------------------------------------------------------------------

    def save_current_analysis(
        self,
        subject: Subject,
        position: AnalyzedPosition,
        run_id: Optional[str] = None,
        profile_name: Optional[str] = None,
        notes: str = "",
    ) -> tuple[AnalysisResult, Path]:
        """
        Run analyze(...) then immediately persist as a SavedAnalysisRun.
        Returns (AnalysisResult, path_to_saved_json).
        """
        from fiberforce.results import SavedAnalysisRun, save_analysis_run

        analysis_res = self.analyze(subject, position)

        # Best-effort LiftConfiguration snapshot
        pose = position.pose
        config = LiftConfiguration(
            lift_name=getattr(pose, "name", "unknown-lift").split()[0] if pose else "custom",
            variation="custom",
            joint_angles=pose.joint_angles if pose else JointAngles(),
            external_load=pose.external_load or ExternalLoad(mass_kg=0.0),
            target_regions=position.target_regions,
            notes="Saved via AnalysisService.save_current_analysis",
        )

        run = SavedAnalysisRun(
            run_id=run_id or f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            profile_name=profile_name,
            lift_configuration=config,
            analysis_result=analysis_res,
            subject_name=subject.name,
            notes=notes,
        )
        path = save_analysis_run(run, run.run_id)
        return analysis_res, path

    def run_and_save_profile_sensitivity(
        self,
        profile_name: str,
        lift: str,
        variable: str,
        values: list[Any],
        target_region_name: str,
        **kwargs,
    ) -> tuple[SensitivityResult, Path]:
        """
        Convenience wrapper that loads a profile and runs + saves a (single-var) sensitivity.
        Delegates heavy lifting to the dedicated profile helpers in results module for multi-var.
        """
        from fiberforce.results import SavedSensitivityRun, save_sensitivity_run, load_profile_for_analysis

        _, subject = load_profile_for_analysis(profile_name)
        pos = self.build_position(
            lift,
            load_kg=kwargs.get("load_kg", 100.0),
            variation=kwargs.get("variation", "flat"),
            target_region_name=target_region_name,
        )

        # Robust target region lookup
        target_region = next(
            (r for r in KNOWN_MUSCLE_REGIONS if target_region_name.lower() in r.region_name.lower()),
            pos.target_regions[0] if pos.target_regions else KNOWN_MUSCLE_REGIONS[0],
        )

        sens = self.sensitivity(
            subject,
            pos,
            variable=variable,
            values=values,
            target_region=target_region,
            rebuild_position=kwargs.get("rebuild_position"),
        )

        base_config = LiftConfiguration(
            lift_name=lift,
            variation=kwargs.get("variation", "flat"),
            joint_angles=pos.pose.joint_angles,
            external_load=pos.pose.external_load or ExternalLoad(mass_kg=kwargs.get("load_kg", 100)),
            target_regions=[target_region],
        )

        srun = SavedSensitivityRun(
            run_id=f"{profile_name}_{lift}_{variable}_{datetime.now().strftime('%Y%m%d_%H%M')}",
            profile_name=profile_name,
            base_lift_configuration=base_config,
            variable=variable,
            sensitivity_results=[sens],
            notes=kwargs.get("notes", "Saved via service"),
        )
        path = save_sensitivity_run(srun, srun.run_id)
        return sens, path

    def run_profile_multi_sensitivity(
        self, profile_name: str, lift: str, variables: list[tuple[str, list[Any]]], **kwargs
    ):
        """Direct passthrough to the powerful profile-based multi-var implementation (results module)."""
        from fiberforce.results import run_profile_multi_sensitivity
        return run_profile_multi_sensitivity(profile_name, lift, variables, **kwargs)


# Default global service for convenience (library users + CLI use this exclusively)
service = AnalysisService()
