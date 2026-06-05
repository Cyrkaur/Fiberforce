"""
Enhanced persistence module for FiberForce analysis results and configurations.

Provides clean, versioned JSON save/load for:
- LiftConfiguration (full exercise setups)
- MuscleForceResult lists + AnalysisResult
- SensitivityResult (single + multi-var)
- ComparisonResult
- "Saved runs" that bundle config + results + profile association + metadata

Also hosts the v0.5 program-level models (TrainingSession / WeeklyProgram)
for accumulating multi-analysis and multi-position results into regional
stress/volume totals with simple reporting. These integrate directly with
AnalysisService.accumulate_regional_* helpers.

Designed to integrate seamlessly with the existing profiles.py (anthropometry)
and AnalysisService. All storage is human-readable JSON under
~/.fiberforce/results/ (or custom dir).

Key features:
- Robust dataclass <-> JSON roundtripping (no external deps like pydantic)
- Explicit __type__ tags + recursive reconstruction for nested models
- Profile-linked runs for "profile-based multi-var sensitivity and compare"
- Good error handling with specific exceptions
- Timestamps, versioning, notes for longitudinal tracking
- List / discover saved artifacts easily
- Program-level: TrainingSession + WeeklyProgram for Phase 3 weekly modeling

Usage (library):
    from fiberforce.results import (
        save_analysis_run, load_analysis_run, SavedAnalysisRun,
        save_sensitivity_run, run_profile_multi_sensitivity,
        TrainingSession, WeeklyProgram,
    )
    from fiberforce import AnalysisService
    from fiberforce.profiles import load_anthropometry

    service = AnalysisService()
    anthro = load_anthropometry("mybody")
    subj = service.create_subject_from_measurements(name="me", **anthro_dict...)

    # ... build pos, run analysis or sensitivity ...

    run = SavedAnalysisRun(
        run_id="bench_100kg_sternal_2026",
        profile_name="mybody",
        lift_configuration=some_config,
        analysis_result=service.analyze(subj, pos),
        notes="Session after deload week"
    )
    path = save_analysis_run(run, "bench_pr_100kg")

For CLI integration and profile-based workflows see cli.py and
the profile subcommands (save-result, multi-sens, compare-runs, etc).

For program-level usage see examples/01_program_level_insights.py and
the TrainingSession / WeeklyProgram classes below.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

# Core models we persist (import here to keep one clear dependency surface)
from fiberforce.models import (
    LiftConfiguration,
    JointAngles,
    ExternalLoad,
    MuscleForceResult,
    MuscleRegion,
    MuscleAttachment,
    Pose,
    AnalyzedPosition,
    UserAnthropometry,
)
from fiberforce.calculations.utils import nm_to_ftlb
from fiberforce.models.subject import Subject
from fiberforce.calculations.sensitivity import SensitivityResult, SensitivityPoint
from fiberforce.analysis.service import AnalysisResult, MultiPositionResult, AnalysisService
from fiberforce.visualization import ComparisonResult
# Note: SavedMultiPositionRun is defined locally later in this file (see below)


# -------------------------------------------------------------------
# Custom exceptions (good error handling)
# -------------------------------------------------------------------

class PersistenceError(Exception):
    """Base class for all persistence failures."""
    pass


class ProfileNotFoundError(PersistenceError):
    """Requested profile or associated run not found."""
    pass


class CorruptResultError(PersistenceError):
    """JSON file exists but is invalid, missing required fields, or failed reconstruction."""
    pass


class UnsupportedTypeError(PersistenceError):
    """Attempted to serialize an unsupported object type."""
    pass


# -------------------------------------------------------------------
# Directories (parallel to profiles.py)
# -------------------------------------------------------------------

DEFAULT_PROFILE_DIR = Path.home() / ".fiberforce" / "profiles"
DEFAULT_RESULTS_DIR = Path.home() / ".fiberforce" / "results"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# Type registry for reconstruction (extensible)
# NOTE: Populated after all dataclass definitions (including Saved* and v0.5 program models)
# to avoid forward-reference NameErrors on module import.
# -------------------------------------------------------------------

_KNOWN_DATACLASSES: dict[str, type] = {}  # populated at bottom of module after class defs


def register_dataclass(name: str, cls: type) -> None:
    """Allow future modules to register additional persistable dataclasses."""
    _KNOWN_DATACLASSES[name] = cls


# -------------------------------------------------------------------
# Recursive JSON-safe serialization / deserialization
# -------------------------------------------------------------------

def _to_jsonable(obj: Any) -> Any:
    """Convert arbitrary FiberForce objects (dataclasses, lists, etc.) to JSON-safe structure."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}

    if is_dataclass(obj) and not isinstance(obj, type):
        data: dict[str, Any] = {}
        for f in fields(obj):
            val = getattr(obj, f.name)
            data[f.name] = _to_jsonable(val)
        data["__type__"] = obj.__class__.__name__
        return data

    try:
        return str(obj)
    except Exception:
        raise UnsupportedTypeError(f"Cannot serialize object of type {type(obj)}")


def _from_jsonable(data: Any) -> Any:
    """
    Reconstruct native objects from our tagged JSON structure.
    Recursively rebuilds dataclasses using the known registry.
    """
    if isinstance(data, list):
        return [_from_jsonable(item) for item in data]
    if isinstance(data, dict):
        if "__type__" in data:
            type_name = data.pop("__type__")
            cls = _KNOWN_DATACLASSES.get(type_name)
            if cls is None:
                data["__type__"] = type_name
                return data

            clean_kwargs: dict[str, Any] = {}
            for k, v in data.items():
                if k == "__type__":
                    continue
                clean_kwargs[k] = _from_jsonable(v)

            try:
                return cls(**clean_kwargs)
            except TypeError:
                try:
                    inst = cls.__new__(cls)
                    for k, v in clean_kwargs.items():
                        setattr(inst, k, v)
                    if hasattr(inst, "__post_init__"):
                        inst.__post_init__()
                    return inst
                except Exception:
                    data["__type__"] = type_name
                    data.update(clean_kwargs)
                    return data
        return {k: _from_jsonable(v) for k, v in data.items()}
    return data


def _add_metadata(data: dict[str, Any], obj_type: str) -> dict[str, Any]:
    """Wrap payload with version + timestamp for robustness."""
    return {
        "version": "1.0",
        "type": obj_type,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def _unwrap_metadata(raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract version/type and the inner data. Raises on bad structure."""
    if not isinstance(raw, dict):
        raise CorruptResultError("Saved file is not a JSON object")
    version = raw.get("version", "unknown")
    typ = raw.get("type", "unknown")
    if "data" not in raw:
        raise CorruptResultError(f"Missing 'data' payload (version={version}, type={typ})")
    return typ, raw["data"]


# -------------------------------------------------------------------
# Public dataclasses for saved artifacts (the "results" story)
# -------------------------------------------------------------------

@dataclass
class SavedAnalysisRun:
    """A complete persisted peak-force analysis tied to (optional) profile + config."""
    run_id: str
    profile_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    lift_configuration: Optional[LiftConfiguration] = None
    analysis_result: Optional[AnalysisResult] = None
    subject_name: Optional[str] = None
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def short_summary(self) -> str:
        force = "N/A"
        if self.analysis_result and self.analysis_result.results:
            first = self.analysis_result.results[0]
            force = f"{first.peak_force_newtons:.1f} N"
        return f"{self.run_id} | {self.profile_name or 'no-profile'} | {force}"


@dataclass
class SavedSensitivityRun:
    """Persisted sensitivity analysis (supports both single-var and multi-var via list of results)."""
    run_id: str
    profile_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    base_lift_configuration: Optional[LiftConfiguration] = None
    variable: str = ""
    sensitivity_results: list[SensitivityResult] = field(default_factory=list)
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def is_multi_var(self) -> bool:
        return len(self.sensitivity_results) > 1

    def short_summary(self) -> str:
        n_points = sum(len(r.points) for r in self.sensitivity_results)
        return f"{self.run_id} ({self.variable}) — {len(self.sensitivity_results)} result(s), {n_points} points"


@dataclass
class SavedCompareRun:
    """Persisted two-way comparison (useful for longitudinal tracking of technique changes)."""
    run_id: str
    profile_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    comparison_result: Optional[ComparisonResult] = None
    notes: str = ""


@dataclass
class SavedMultiPositionRun:
    """Persisted multi-position (limited dynamic / ROM snapshot) run.
    Stores the full ordered list of AnalysisResult + derived summary.
    Phase 2c deliverable for CLI + profile workflows.
    """
    run_id: str
    profile_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    lift: str = ""
    positions: list[str] = field(default_factory=list)
    load_kg: float = 0.0
    variation: str = "flat"
    target_region_name: str = ""
    analysis_results: list[AnalysisResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def short_summary(self) -> str:
        n = len(self.analysis_results)
        npos = len(self.positions) or n
        return f"{self.run_id} | {self.lift} × {npos} pos | {n} results | {self.profile_name or 'no-profile'}"


# -------------------------------------------------------------------
# v0.5 Program-level models (Phase 3): TrainingSession / WeeklyProgram
# These are simple, focused dataclasses for holding and aggregating
# multiple AnalysisResult (including from analyze_multi_position) plus
# accumulated regional stress/volume proxies. They delegate computation
# to the existing AnalysisService accumulation helpers for consistency.
# -------------------------------------------------------------------

@dataclass
class TrainingSession:
    """Represents one training session or discrete training block.

    Holds a list of AnalysisResult objects (from single-position analyze() calls
    or from analyze_multi_position() which returns list[AnalysisResult] for
    bottom/mid/top etc. snapshots).

    Supports incremental addition of results (with optional per-result weights
    for e.g. different emphasis or RPE in a session) and on-demand computation
    of regional stress and volume using the service accumulators.

    This is the basic building block for WeeklyProgram and higher-level
    program modeling / comparison.
    """
    name: str
    date: Optional[str] = None
    lift: Optional[str] = None
    variation: Optional[str] = None
    notes: str = ""
    # Source of truth: the raw analyses (order-preserving)
    analyses: list[AnalysisResult] = field(default_factory=list)
    # Parallel weights (same length as analyses when set; defaults to 1.0 per item)
    _weights: list[float] = field(default_factory=list, repr=False)

    def add_analysis(
        self,
        analysis: AnalysisResult,
        weight: float = 1.0,
    ) -> "TrainingSession":
        """Append a single AnalysisResult (single lift instance or position)."""
        if not isinstance(analysis, AnalysisResult):
            raise TypeError("analysis must be an AnalysisResult")
        self.analyses.append(analysis)
        self._weights.append(float(weight))
        return self

    def add_analyses(
        self,
        analyses: list[AnalysisResult],
        weights: Optional[Union[float, list[float]]] = None,
    ) -> "TrainingSession":
        """Append multiple analyses (ideal for multi-position results lists).

        weights: scalar (applied to all) or list matching len(analyses).
        """
        if not analyses:
            return self
        n = len(analyses)
        if weights is None:
            wlist = [1.0] * n
        elif isinstance(weights, (int, float)):
            wlist = [float(weights)] * n
        else:
            wlist = [float(w) for w in weights]
            if len(wlist) != n:
                raise ValueError(f"weights list length must match analyses ({n})")
        for a, w in zip(analyses, wlist):
            self.add_analysis(a, w)
        return self

    def _get_weights(self) -> Union[float, list[float]]:
        """Internal: return effective weights for accumulation (scalar if uniform)."""
        if not self._weights:
            return 1.0
        # If all 1.0, scalar is fine for the accumulator API
        if all(abs(w - 1.0) < 1e-9 for w in self._weights):
            return 1.0
        return list(self._weights)

    def compute_regional_stress(
        self, service: Optional[AnalysisService] = None
    ) -> dict:
        """Compute accumulated regional stress for this session.

        Delegates to AnalysisService.accumulate_regional_stress (supports weights).
        Returns the standard accumulation dict with 'meta'.
        """
        svc = service or _get_default_service()
        if not self.analyses:
            return {"meta": {"num_analyses": 0, "applied_weights": []}}
        return svc.accumulate_regional_stress(self.analyses, weight=self._get_weights())

    def compute_regional_volume(
        self,
        service: Optional[AnalysisService] = None,
        volume_factors: Optional[Union[float, list[float]]] = None,
    ) -> dict:
        """Compute volume-weighted regional accumulation for the session.

        volume_factors are applied *in addition* to any per-analysis weights
        already stored (e.g. sets*reps style factors per position in a session).
        """
        svc = service or _get_default_service()
        if not self.analyses:
            return {"meta": {"num_analyses": 0}}
        n = len(self.analyses)
        base_weights = self._weights if self._weights else [1.0] * n

        if volume_factors is None:
            vols = [1.0] * n
        elif isinstance(volume_factors, (int, float)):
            vols = [float(volume_factors)] * n
        else:
            vols = [float(v) for v in volume_factors]
            if len(vols) != n:
                raise ValueError("volume_factors length must match session analyses")

        # Combine: effective = base_weight * vol_factor for each item
        combined = [bw * vf for bw, vf in zip(base_weights, vols)]
        # Use accumulate_regional_volume with combined as the "volume_factors" and weight=1
        # (since we already baked base weights in)
        return svc.accumulate_regional_volume(
            self.analyses, volume_factors=combined, weight=1.0
        )

    def get_summary(self, service: Optional[AnalysisService] = None) -> dict:
        """Convenience: stress + volume + simple stats for this session."""
        stress = self.compute_regional_stress(service)
        vol = self.compute_regional_volume(service)
        totals = {k: v for k, v in stress.items() if not k.startswith("meta")}
        top = max(totals.items(), key=lambda kv: kv[1])[0] if totals else None
        return {
            "name": self.name,
            "num_analyses": len(self.analyses),
            "top_region_by_stress": top,
            "total_stress": stress.get("meta", {}).get("total_stress", 0.0),
            "total_volume_stress": vol.get("meta", {}).get("total_volume_stress", 0.0),
            "regional_stress": totals,
        }

    def interpret(self, service: Optional["AnalysisService"] = None) -> str:
        """Light 0.7→0.8 interpretation for a single session."""
        summary = self.get_summary(service)
        lines = [f"TrainingSession '{self.name}': {summary['num_analyses']} analyses."]
        if summary.get("top_region_by_stress"):
            lines.append(f"  • Top stressed region: {summary['top_region_by_stress']}.")
        lines.append("  • Use as building block for weekly aggregates and comparisons.")
        return "\n".join(lines)


@dataclass
class WeeklyProgram:
    """A collection of TrainingSession objects representing a week (or training block).

    Provides:
    - Adding sessions (each session may contain single or multi-position analyses)
    - Computing aggregate weekly regional stress/volume totals (via service helpers)
    - Generating simple, readable text reports (with optional ASCII visualization)
    - Basic support for comparing two programs (via classmethod or external use of totals)

    Designed as the primary v0.5 program-level abstraction. All heavy lifting
    is delegated to AnalysisService accumulators for consistency with the rest
    of the system. Source of truth remains the contained sessions' analyses.
    """
    name: str
    athlete: Optional[str] = None
    week_id: Optional[str] = None
    notes: str = ""
    sessions: list[TrainingSession] = field(default_factory=list)

    def add_session(self, session: TrainingSession) -> "WeeklyProgram":
        """Append a TrainingSession (supports chaining)."""
        if not isinstance(session, TrainingSession):
            raise TypeError("session must be a TrainingSession")
        self.sessions.append(session)
        return self

    def add_sessions(self, sessions: list[TrainingSession]) -> "WeeklyProgram":
        for s in sessions:
            self.add_session(s)
        return self

    def flatten_analyses(self) -> list[AnalysisResult]:
        """Return a flat list of all AnalysisResult across every session."""
        out: list[AnalysisResult] = []
        for sess in self.sessions:
            out.extend(sess.analyses)
        return out

    def compute_weekly_totals(
        self, service: Optional[AnalysisService] = None
    ) -> dict:
        """Aggregate stress, volume, and summary across the entire program.

        Uses the service's public accumulation helpers on the flattened analyses.
        """
        svc = service or _get_default_service()
        all_analyses = self.flatten_analyses()
        if not all_analyses:
            return {
                "name": self.name,
                "num_sessions": len(self.sessions),
                "num_analyses": 0,
                "meta": {"num_sessions": len(self.sessions), "num_analyses": 0},
                "weekly_stress": {"meta": {"num_analyses": 0}},
                "weekly_volume": {"meta": {"num_analyses": 0}},
                "summary": {"num_analyses": 0},
            }

        stress = svc.accumulate_regional_stress(all_analyses)
        vol = svc.accumulate_regional_volume(all_analyses)
        summary = svc.summarize_regional_accumulation(all_analyses)

        # Per-session breakdown (lightweight)
        per_session = [s.get_summary(svc) for s in self.sessions]

        # 0.7→0.8: lightweight interpretation metadata for library consumers
        interpretation = {
            "note": "Stress/volume are mechanical proxies only. Prefer relative deltas within the same athlete.",
            "multi_position_contrib": any(hasattr(a, "positions") or len(getattr(a, "results", [])) > 1 for a in all_analyses),
            "data_sources": "mix of single-position + MultiPositionResult analyses",
        }

        return {
            "name": self.name,
            "num_sessions": len(self.sessions),
            "num_analyses": len(all_analyses),
            "weekly_stress": stress,
            "weekly_volume": vol,
            "summary": summary,
            "per_session": per_session,
            "interpretation": interpretation,
        }

    def generate_simple_report(
        self, service: Optional[AnalysisService] = None, max_regions: int = 8
    ) -> str:
        """Produce a human-readable plain-text report for the weekly program.

        Includes totals, top stressed regions, and basic per-session notes.
        Safe in headless environments (falls back gracefully if viz unavailable).
        """
        totals = self.compute_weekly_totals(service)
        lines: list[str] = []
        lines.append(f"WeeklyProgram Report: {self.name}")
        if self.athlete:
            lines.append(f"Athlete: {self.athlete}")
        if self.week_id:
            lines.append(f"Week: {self.week_id}")
        lines.append(f"Sessions: {totals['num_sessions']} | Total analyses: {totals['num_analyses']}")
        lines.append("")

        # Regional stress summary (top N)
        stress = totals.get("weekly_stress", {})
        regional = {k: v for k, v in stress.items() if not k.startswith("meta")}
        if regional:
            sorted_regions = sorted(regional.items(), key=lambda kv: -kv[1])[:max_regions]
            lines.append("Top Regional Torque Demand (ft-lb accumulated proxy):")
            for region, val in sorted_regions:
                lines.append(f"  {region:30s} {val:10.1f}")
            total_s = stress.get("meta", {}).get("total_stress", 0.0)
            lines.append(f"  {'TOTAL':30s} {total_s:10.1f}")
            lines.append("")

        # Volume proxy
        vol_meta = totals.get("weekly_volume", {}).get("meta", {})
        lines.append(f"Total volume-stress proxy: {vol_meta.get('total_volume_stress', 0.0):.1f}")
        lines.append("")

        # Simple top region insight
        summ = totals.get("summary", {})
        top = summ.get("top_region_by_stress")
        if top:
            lines.append(f"Highest stressed region: {top}")
        lines.append("")

        # Per-session highlights (very brief)
        if totals.get("per_session"):
            lines.append("Per-session highlights:")
            for ps in totals["per_session"]:
                lines.append(f"  - {ps['name']}: {ps['num_analyses']} analyses, top={ps['top_region_by_stress'] or 'n/a'}")

        # Optional ASCII bars for top regions (best effort)
        try:
            from fiberforce.visualization import ascii_bars
            if regional:
                labels = [r for r, _ in sorted_regions]
                values = [v for _, v in sorted_regions]
                chart = ascii_bars(labels, values, width=48, unit="stress", max_bar_width=28)
                lines.append("\nRegional distribution (ASCII):")
                lines.append(chart)
        except Exception:
            pass  # headless / unavailable is fine

        if self.notes:
            lines.append(f"\nNotes: {self.notes}")

        # 0.7→0.8 Usability polish: richer interpretation guidance
        lines.append("")
        lines.append("Interpretation & Usage Notes (v1 units: imperial / ft-lbs torque):")
        lines.append("  • Regional 'stress' values are accumulated peak *torque demand* proxies (ft-lb × weighting).")
        lines.append("    (Converted from internal Nm using standard factor; compare relatively within athlete.)")
        lines.append("    Higher values mean the model estimates greater mechanical demand on that region")
        lines.append("    across the included analyses/positions. Compare relative to the same athlete's")
        lines.append("    other sessions or programs — absolute numbers are best treated as directional.")
        lines.append("  • Multi-position data (bottom/mid/top) contributes more granular load than single-position")
        lines.append("    snapshots. A week heavy on 3-position squat work will naturally show different")
        lines.append("    regional distribution than a week using only mid-thigh pin pulls.")
        lines.append("  • Geometric moment-arm data (when UserAnthropometry was supplied) is used where")
        lines.append("    available. Check individual AnalysisResult notes or MultiPositionResult summaries")
        lines.append("    for 'geometric' vs 'reference table' provenance on specific lifts.")
        lines.append("  • Top stressed region is useful for programming emphasis decisions (e.g., 'this")
        lines.append("    low-bar week loaded glutes ~X% more than the high-bar week for this lifter').")
        lines.append("    Use individual result.peak_torque_ftlb for exact ft-lbs torque at joint.")
        lines.append("  • Measurements default to inches/ft/lbs in v1; forces/torques reported in ft-lbs.")
        lines.append("  • These numbers intentionally ignore recovery, sleep, nutrition, joint tolerance,")
        lines.append("    and technique. They are one mechanical data layer to combine with real-world")
        lines.append("    athlete feedback, not a complete training prescription system.")

        lines.append("\n(Computed via AnalysisService accumulation helpers + real reference data + geometric estimators)")
        lines.append("Strong recommendation: Use for relative comparisons within one athlete across variations,")
        lines.append("not for cross-athlete or absolute 'volume prescriptions'.")
        return "\n".join(lines)

    def interpret(self, service: Optional["AnalysisService"] = None) -> str:
        """
        0.7→0.8 usability: produce a concise, non-prescriptive human interpretation
        of the entire weekly program based on the computed aggregates.

        Complements generate_simple_report() by focusing on insights rather than raw numbers.
        """
        from fiberforce.analysis.service import AnalysisService as _AS  # local to avoid circulars at import time

        totals = self.compute_weekly_totals(service)
        lines: list[str] = []

        name = self.name
        n_sess = totals.get("num_sessions", 0)
        n_anal = totals.get("num_analyses", 0)
        lines.append(f"WeeklyProgram '{name}' interpretation: {n_sess} sessions, {n_anal} total analyses.")

        # Top stress insight
        stress = totals.get("weekly_stress", {})
        regional = {k: v for k, v in stress.items() if not k.startswith("meta")}
        if regional:
            top = max(regional.items(), key=lambda kv: kv[1])
            lines.append(f"  • Highest accumulated stress on {top[0]} ({top[1]:.0f} N proxy).")
            # Simple relative note
            total_proxy = stress.get("meta", {}).get("total_stress", 0.0)
            if total_proxy > 0:
                pct = (top[1] / total_proxy) * 100
                lines.append(f"    This region accounts for ~{pct:.0f}% of the week's modeled target stress.")

        # Multi-position vs single insight
        interp_meta = totals.get("interpretation", {})
        if interp_meta.get("multi_position_contrib"):
            lines.append("  • Contains multi-position (limited-dynamic) data — gives position-specific stress signals beyond single snapshots.")
        else:
            lines.append("  • Primarily single-position analyses. Consider multi-pos for ROM insights on key lifts.")

        # Session diversity
        per_sess = totals.get("per_session", [])
        if len(per_sess) > 1:
            unique_lifts = set(ps.get("name", "").split()[0] for ps in per_sess if ps.get("name"))
            if len(unique_lifts) > 1:
                lines.append(f"  • Mix of lifts across sessions ({', '.join(sorted(unique_lifts)[:4])}) — good for balanced regional development.")

        # General guidance
        lines.append("  • All numbers are mechanical proxies. Use deltas and relative rankings within the same athlete.")
        lines.append("    Cross-reference with recovery, technique, and performance before adjusting training variables.")

        if self.notes:
            lines.append(f"  Program notes: {self.notes}")

        return "\n".join(lines)

    @classmethod
    def compare(cls, p1: "WeeklyProgram", p2: "WeeklyProgram", service: Optional[AnalysisService] = None) -> dict:
        """Compare two WeeklyProgram instances and return delta-focused summary.

        Useful for "A vs B program" questions (different volume, different position emphasis,
        high-bar vs low-bar dominant weeks, etc.).
        """
        svc = service or _get_default_service()
        t1 = p1.compute_weekly_totals(svc)
        t2 = p2.compute_weekly_totals(svc)

        s1 = t1["weekly_stress"]
        s2 = t2["weekly_stress"]
        r1 = {k: v for k, v in s1.items() if not k.startswith("meta")}
        r2 = {k: v for k, v in s2.items() if not k.startswith("meta")}

        all_regions = sorted(set(r1) | set(r2))
        deltas = {}
        for reg in all_regions:
            v1 = r1.get(reg, 0.0)
            v2 = r2.get(reg, 0.0)
            deltas[reg] = v2 - v1

        winner = p2.name if t2.get("summary", {}).get("total_stress_proxy", 0) > t1.get("summary", {}).get("total_stress_proxy", 0) else p1.name

        return {
            "program_a": p1.name,
            "program_b": p2.name,
            "a_totals": t1["summary"],
            "b_totals": t2["summary"],
            "deltas_by_region": deltas,
            "higher_stress_program": winner,
            "note": "Positive delta means Program B has higher accumulated stress on that region.",
        }


def _get_default_service() -> AnalysisService:
    """Internal helper: return the module-level default service without top-level cycle risk."""
    # Lazy to be extra safe
    from fiberforce.analysis.service import service as _default
    return _default


# -------------------------------------------------------------------
# Core save / load primitives (used by everything else)
# -------------------------------------------------------------------

def save_json(
    data: dict[str, Any],
    name: str,
    results_dir: Optional[Path] = None,
    subdir: Optional[str] = None,
) -> Path:
    """Low-level: write a versioned JSON artifact. Returns path."""
    base = results_dir or DEFAULT_RESULTS_DIR
    if subdir:
        base = base / subdir
    _ensure_dir(base)
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    if not safe_name.endswith(".json"):
        safe_name += ".json"
    path = base / safe_name
    wrapped = _add_metadata(data, data.get("__artifact_type__", "generic"))
    path.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False))
    return path


def load_json(path: Path) -> dict[str, Any]:
    """Low-level loader with good diagnostics."""
    if not path.exists():
        raise FileNotFoundError(f"No saved artifact at {path}")
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise CorruptResultError(f"Invalid JSON in {path}: {e}") from e
    typ, payload = _unwrap_metadata(raw)
    payload["__artifact_type__"] = typ
    return payload


# -------------------------------------------------------------------
# High-level save/load for configurations and results
# -------------------------------------------------------------------

def save_lift_config(
    config: LiftConfiguration,
    name: str,
    results_dir: Optional[Path] = None,
) -> Path:
    """Save a LiftConfiguration as standalone JSON (useful for reuse across profiles)."""
    payload = _to_jsonable(config)
    payload["__artifact_type__"] = "lift_config"
    return save_json(payload, name, results_dir, subdir="configs")


def load_lift_config(
    name: str,
    results_dir: Optional[Path] = None,
) -> LiftConfiguration:
    """Load a previously saved LiftConfiguration."""
    base = results_dir or DEFAULT_RESULTS_DIR
    path = base / "configs" / (name if name.endswith(".json") else f"{name}.json")
    if not path.exists():
        path = base / (name if name.endswith(".json") else f"{name}.json")
    raw = load_json(path)
    obj = _from_jsonable(raw)
    if isinstance(obj, LiftConfiguration):
        return obj
    if isinstance(raw, dict) and "lift_name" in raw:
        return LiftConfiguration(**{k: _from_jsonable(v) for k, v in raw.items() if not k.startswith("__")})
    raise CorruptResultError(f"Loaded object is not a LiftConfiguration (got {type(obj)})")


def save_analysis_run(
    run: SavedAnalysisRun,
    name: str,
    results_dir: Optional[Path] = None,
) -> Path:
    """Persist a full analysis run (config + MuscleForceResult list via AnalysisResult)."""
    payload = _to_jsonable(run)
    payload["__artifact_type__"] = "analysis_run"
    return save_json(payload, name, results_dir, subdir="analyses")


def load_analysis_run(
    name: str,
    results_dir: Optional[Path] = None,
) -> SavedAnalysisRun:
    """Load a SavedAnalysisRun with full reconstruction of results."""
    base = results_dir or DEFAULT_RESULTS_DIR
    candidates = [
        base / "analyses" / (name if name.endswith(".json") else f"{name}.json"),
        base / (name if name.endswith(".json") else f"{name}.json"),
    ]
    last_err = None
    for path in candidates:
        if not path.exists():
            continue
        try:
            raw = load_json(path)
            obj = _from_jsonable(raw)
            if isinstance(obj, SavedAnalysisRun):
                return obj
            if isinstance(raw, dict):
                return SavedAnalysisRun(**{k: _from_jsonable(v) for k, v in raw.items() if not k.startswith("__")})
        except Exception as e:
            last_err = e
    raise CorruptResultError(f"Could not load analysis run '{name}': {last_err or 'file not found'}")


def save_sensitivity_run(
    run: SavedSensitivityRun,
    name: str,
    results_dir: Optional[Path] = None,
) -> Path:
    """Persist single- or multi-variable sensitivity results."""
    payload = _to_jsonable(run)
    payload["__artifact_type__"] = "sensitivity_run"
    return save_json(payload, name, results_dir, subdir="sensitivities")


def load_sensitivity_run(
    name: str,
    results_dir: Optional[Path] = None,
) -> SavedSensitivityRun:
    """Load saved sensitivity (multi-var supported)."""
    base = results_dir or DEFAULT_RESULTS_DIR
    candidates = [
        base / "sensitivities" / (name if name.endswith(".json") else f"{name}.json"),
        base / (name if name.endswith(".json") else f"{name}.json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        raw = load_json(path)
        obj = _from_jsonable(raw)
        if isinstance(obj, SavedSensitivityRun):
            return obj
        if isinstance(raw, dict):
            return SavedSensitivityRun(**{k: _from_jsonable(v) for k, v in raw.items() if not k.startswith("__")})
    raise CorruptResultError(f"Sensitivity run '{name}' not found or corrupt")


def save_compare_run(
    run: SavedCompareRun,
    name: str,
    results_dir: Optional[Path] = None,
) -> Path:
    payload = _to_jsonable(run)
    payload["__artifact_type__"] = "compare_run"
    return save_json(payload, name, results_dir, subdir="comparisons")


def load_compare_run(
    name: str,
    results_dir: Optional[Path] = None,
) -> SavedCompareRun:
    base = results_dir or DEFAULT_RESULTS_DIR
    candidates = [
        base / "comparisons" / (name if name.endswith(".json") else f"{name}.json"),
        base / (name if name.endswith(".json") else f"{name}.json"),
    ]
    for path in candidates:
        if path.exists():
            raw = load_json(path)
            obj = _from_jsonable(raw)
            if isinstance(obj, SavedCompareRun):
                return obj
            if isinstance(raw, dict):
                return SavedCompareRun(**{k: _from_jsonable(v) for k, v in raw.items() if not k.startswith("__")})
    raise CorruptResultError(f"Compare run '{name}' not found or corrupt")


def save_multi_position_run(
    run: SavedMultiPositionRun,
    name: str,
    results_dir: Optional[Path] = None,
) -> Path:
    """Persist a multi-position ROM run (full list[AnalysisResult] + summary)."""
    payload = _to_jsonable(run)
    payload["__artifact_type__"] = "multi_position_run"
    return save_json(payload, name, results_dir, subdir="multi_pos")


def load_multi_position_run(
    name: str,
    results_dir: Optional[Path] = None,
) -> SavedMultiPositionRun:
    """Load a previously saved SavedMultiPositionRun (reconstructs nested AnalysisResults)."""
    base = results_dir or DEFAULT_RESULTS_DIR
    candidates = [
        base / "multi_pos" / (name if name.endswith(".json") else f"{name}.json"),
        base / (name if name.endswith(".json") else f"{name}.json"),
    ]
    for path in candidates:
        if path.exists():
            raw = load_json(path)
            obj = _from_jsonable(raw)
            if isinstance(obj, SavedMultiPositionRun):
                return obj
            if isinstance(raw, dict):
                return SavedMultiPositionRun(**{k: _from_jsonable(v) for k, v in raw.items() if not k.startswith("__")})
    raise CorruptResultError(f"Multi-position run '{name}' not found or corrupt")


# -------------------------------------------------------------------
# Discovery helpers
# -------------------------------------------------------------------

def list_saved_runs(
    results_dir: Optional[Path] = None,
    profile_name: Optional[str] = None,
    run_type: Optional[str] = None,
) -> list[str]:
    """List saved run names (stems). Optionally filter by associated profile or type."""
    base = results_dir or DEFAULT_RESULTS_DIR
    subdirs = ["analyses", "sensitivities", "comparisons", "configs", "multi_pos"]
    names: list[str] = []

    for sub in subdirs:
        d = base / sub
        if not d.exists():
            continue
        for p in d.glob("*.json"):
            if profile_name:
                try:
                    raw = json.loads(p.read_text())
                    data = raw.get("data", {})
                    if data.get("profile_name") != profile_name:
                        continue
                except Exception:
                    continue
            names.append(p.stem)

    if base.exists():
        for p in base.glob("*.json"):
            names.append(p.stem)

    names = sorted(set(names))
    return names


def list_configs(results_dir: Optional[Path] = None) -> list[str]:
    """List saved LiftConfiguration names."""
    base = results_dir or DEFAULT_RESULTS_DIR
    d = base / "configs"
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


# -------------------------------------------------------------------
# Profile-based high-level operations (the key new capability)
# -------------------------------------------------------------------

def load_profile_for_analysis(profile_name: str) -> tuple[UserAnthropometry, Subject]:
    """Convenience: load anthro profile and return ready-to-use Subject via default service logic."""
    from fiberforce.profiles import load_anthropometry
    from fiberforce.analysis.service import AnalysisService

    anthro = load_anthropometry(profile_name)
    svc = AnalysisService()
    subject = svc.create_subject_from_measurements(
        name=anthro.name or profile_name,
        **{k: v for k, v in asdict(anthro).items() if v is not None and k not in ("id", "name", "measurement_date", "notes", "muscle_architecture")}
    )
    subject.anthropometry = anthro
    return anthro, subject


def run_profile_analysis(
    profile_name: str,
    lift: str,
    load_kg: float = 100.0,
    variation: str = "flat",
    target_region_name: str = "Sternal fibers",
    notes: str = "",
    results_dir: Optional[Path] = None,
) -> tuple[SavedAnalysisRun, Path]:
    """
    Profile-based end-to-end analysis + automatic persistence.
    Returns the SavedAnalysisRun and the path it was written to.
    """
    from fiberforce import AnalysisService

    _, subject = load_profile_for_analysis(profile_name)
    svc = AnalysisService()

    pos = svc.build_position(
        lift,
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name,
    )

    analysis_res = svc.analyze(subject, pos)

    config = LiftConfiguration(
        lift_name=lift,
        variation=variation,
        joint_angles=pos.pose.joint_angles,
        external_load=pos.pose.external_load or ExternalLoad(mass_kg=load_kg),
        target_regions=pos.target_regions,
        notes=f"Auto-generated from profile run on {datetime.now().date()}",
    )

    run = SavedAnalysisRun(
        run_id=f"{profile_name}_{lift}_{variation}_{int(load_kg)}kg_{datetime.now().strftime('%Y%m%d_%H%M')}",
        profile_name=profile_name,
        lift_configuration=config,
        analysis_result=analysis_res,
        subject_name=subject.name,
        notes=notes,
    )
    path = save_analysis_run(run, run.run_id, results_dir)
    return run, path


def run_profile_multi_sensitivity(
    profile_name: str,
    lift: str,
    variables: list[tuple[str, list[Any]]],
    target_region_name: str = "Sternal fibers",
    load_kg: float = 100.0,
    variation: str = "flat",
    rebuild_multi: Optional[Any] = None,
    notes: str = "",
    results_dir: Optional[Path] = None,
) -> tuple[SavedSensitivityRun, Path]:
    """
    The requested "profile-based multi-var sensitivity".

    Uses AnalysisService.sensitivity_multi under the hood.
    If no custom rebuild_multi is supplied, the service will use sensible defaults
    for common variables (load_kg etc.). You can supply a callable for advanced cases.
    """
    from fiberforce import AnalysisService

    _, subject = load_profile_for_analysis(profile_name)
    svc = AnalysisService()

    base_pos = svc.build_position(
        lift,
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name,
    )

    from fiberforce.reference import KNOWN_MUSCLE_REGIONS
    target_region = next(
        (r for r in KNOWN_MUSCLE_REGIONS if target_region_name.lower() in r.region_name.lower()),
        base_pos.target_regions[0] if base_pos.target_regions else KNOWN_MUSCLE_REGIONS[0],
    )

    if rebuild_multi is None:
        def default_rebuild(base: AnalyzedPosition, params: dict) -> AnalyzedPosition:
            new_load = params.get("load_kg", load_kg)
            new_var = params.get("variation", variation)
            return svc.build_position(
                lift,
                load_kg=new_load,
                variation=new_var,
                target_region_name=target_region_name,
            )
        rebuild_multi = default_rebuild

    sens_list: list[SensitivityResult] = svc.sensitivity_multi(
        subject=subject,
        base_position=base_pos,
        variables=variables,
        target_region=target_region,
        rebuild_multi=rebuild_multi,
    )

    base_config = LiftConfiguration(
        lift_name=lift,
        variation=variation,
        joint_angles=base_pos.pose.joint_angles,
        external_load=base_pos.pose.external_load or ExternalLoad(mass_kg=load_kg),
        target_regions=[target_region],
    )

    var_names = ",".join(v[0] for v in variables)
    run = SavedSensitivityRun(
        run_id=f"{profile_name}_multi_{lift}_{var_names}_{datetime.now().strftime('%Y%m%d_%H%M')}",
        profile_name=profile_name,
        base_lift_configuration=base_config,
        variable=var_names,
        sensitivity_results=sens_list,
        notes=notes or f"Multi-var sensitivity on profile '{profile_name}' for {lift}",
    )
    path = save_sensitivity_run(run, run.run_id, results_dir)
    return run, path


def run_profile_compare(
    profile_name: str,
    lift: str,
    config_a: str,
    config_b: str,
    load_kg: float = 100.0,
    target: str = "Sternal fibers",
    notes: str = "",
    results_dir: Optional[Path] = None,
    **anthro_overrides,
) -> tuple[SavedCompareRun, Path]:
    """Profile-based compare that also persists the result."""
    from fiberforce import AnalysisService

    _, subject = load_profile_for_analysis(profile_name)
    svc = AnalysisService()

    comp = svc.compare(
        lift=lift,
        config_a=config_a,
        config_b=config_b,
        load_kg=load_kg,
        target=target,
        **anthro_overrides,
    )

    run = SavedCompareRun(
        run_id=f"{profile_name}_compare_{lift}_{config_a}_vs_{config_b}_{int(load_kg)}kg",
        profile_name=profile_name,
        comparison_result=comp,
        notes=notes,
    )
    path = save_compare_run(run, run.run_id, results_dir)
    return run, path


def run_profile_multi_position(
    profile_name: str,
    lift: str,
    positions: list[str],
    load_kg: float = 100.0,
    variation: str = "flat",
    target_region_name: str = "Sternal fibers",
    notes: str = "",
    results_dir: Optional[Path] = None,
) -> tuple[SavedMultiPositionRun, Path]:
    """Profile-backed multi-position analysis + automatic persistence as SavedMultiPositionRun.

    This completes the Phase 2c persistence story for the polished multi-pos CLI surface.
    """
    from fiberforce import AnalysisService

    _, subject = load_profile_for_analysis(profile_name)
    svc = AnalysisService()

    results_list = svc.analyze_multi_position(
        subject,
        lift,
        positions,
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name,
    )

    summary = svc.summarize_multi_position(results_list)

    run = SavedMultiPositionRun(
        run_id=f"{profile_name}_multipos_{lift}_{datetime.now().strftime('%Y%m%d_%H%M')}",
        profile_name=profile_name,
        lift=lift,
        positions=list(positions),
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name,
        analysis_results=results_list,
        summary=summary,
        notes=notes or f"Multi-position ROM via profile '{profile_name}'",
    )
    # Note: we don't store the full config on SavedMultiPositionRun (kept lean), but could extend later
    path = save_multi_position_run(run, run.run_id, results_dir)
    return run, path


# -------------------------------------------------------------------
# Convenience: export any result object directly
# -------------------------------------------------------------------

def export_result_json(obj: Any, name: str, results_dir: Optional[Path] = None) -> Path:
    """Generic export of any persistable object (AnalysisResult, SensitivityResult, etc)."""
    payload = _to_jsonable(obj)
    return save_json(payload, name, results_dir)


# -------------------------------------------------------------------
# Late population of the dataclass registry (after ALL class definitions)
# This guarantees forward refs (SavedMultiPositionRun, our v0.5 TrainingSession etc.)
# are resolved. Safe because _to/_from_jsonable are only called after full module load.
# -------------------------------------------------------------------

_KNOWN_DATACLASSES.update({
    "LiftConfiguration": LiftConfiguration,
    "JointAngles": JointAngles,
    "ExternalLoad": ExternalLoad,
    "MuscleRegion": MuscleRegion,
    "MuscleForceResult": MuscleForceResult,
    "MuscleAttachment": MuscleAttachment,
    "Pose": Pose,
    "AnalyzedPosition": AnalyzedPosition,
    "AnalysisResult": AnalysisResult,
    "MultiPositionResult": MultiPositionResult,
    "SensitivityResult": SensitivityResult,
    "SensitivityPoint": SensitivityPoint,
    "ComparisonResult": ComparisonResult,
    "UserAnthropometry": UserAnthropometry,
    "SavedAnalysisRun": SavedAnalysisRun,
    "SavedSensitivityRun": SavedSensitivityRun,
    "SavedCompareRun": SavedCompareRun,
    "SavedMultiPositionRun": SavedMultiPositionRun,
    # v0.5 Phase 3 program models
    "TrainingSession": TrainingSession,
    "WeeklyProgram": WeeklyProgram,
})

# Also expose the new models for register_dataclass users
register_dataclass("TrainingSession", TrainingSession)
register_dataclass("WeeklyProgram", WeeklyProgram)


# ------------------------------------------------------------------
# New Level: self-competition / PRs / trends helpers (Theme 1 + engagement layer)
# Pure functions over public data (Saved* runs, live MultiPositionResult / AnalysisResult lists,
# or WeeklyProgram). All values are *modeled estimates* (see interpret(), limitations, reports).
# Intended for History tab "Progress", post-run callouts, and future richer depth data (L-T curves etc).
# No side effects, no new persistence, easy to test.
# Post all-muscles/% dominance delivery: extended to first-class dominance % (mechanical leverage share
# at joint) + efficiency (ft-lb per lb) PRs/trends via flags (variation-aware keys for close/wide etc.).
# ------------------------------------------------------------------

from typing import Any, Iterable

def compute_personal_records(
    runs_or_analyses: Iterable[Any],
    *,
    by_region: bool = True,
    by_lift: bool = True,
    include_dominance: bool = False,
    include_efficiency: bool = False,
) -> dict[str, dict]:
    """
    Compute personal modeled peak torque records (ft-lb) from history or live results.
    Extended (post all-muscles + % dominance work) to support dominance % (mechanical leverage share
    at joint among co-movers; higher = better leverage for that muscle) and efficiency (ft-lb per lb load)
    as first-class PR-able metrics when flags are passed. Keys now include variation (e.g. wide_grip) when
    present for differentiated PRs (close vs wide bench dom % are separate).

    Accepts:
      - list of SavedMultiPositionRun (or similar with .analysis_results)
      - list of AnalysisResult or MultiPositionResult (duck)
      - or raw list of MuscleForceResult

    Returns nested dict (extras only if flags):
      {
        "Gluteus Maximus::Upper fibers|squat|bottom": {
          "peak_ftlb": 238.4,
          "timestamp": "...",
          "lift": "squat",
          "position": "bottom",
          "source": "run_id or live",
          "dominance_percent": 46.4,  # if include_dominance
          "efficiency_ftlb_per_lb": 0.78,  # if include_efficiency
          "variation": "low_bar",
          "load_lbs": 315.0,
          "region": "..."
        },
        ...
      }
    Keys are "region|lift|pos" (or finer with variation). Highest kept per metric.
    All numbers are modeled estimates from the current engine (reference tables + optional geo).
    """
    records: dict[str, dict] = {}
    for item in runs_or_analyses or []:
        ts = getattr(item, "timestamp", None) or getattr(item, "saved_at", None)
        lift = getattr(item, "lift", None) or getattr(item, "lift_name", "unknown")
        variation = getattr(item, "variation", None) or getattr(item, "var", "") or ""
        load_kg = getattr(item, "load_kg", 0.0) or 0.0
        load_lbs = getattr(item, "load_lbs", None) or (load_kg * 2.20462 if load_kg else 0.0)
        # Handle Saved* with .analysis_results
        analyses = getattr(item, "analysis_results", None) or []
        if not analyses and hasattr(item, "analyses"):  # live MPR
            analyses = getattr(item, "analyses", []) or []
        if not analyses and hasattr(item, "results"):  # single AnalysisResult
            analyses = [item]

        for a in analyses or []:
            pos_desc = getattr(a, "position_description", None)
            for r in getattr(a, "results", []) or []:
                region = str(getattr(r, "muscle_region", "unknown"))
                ft = getattr(r, "peak_torque_ftlb", None)
                if ft is None:
                    continue
                dom = getattr(r, "dominance_percent", None) if include_dominance else None
                eff = None
                if include_efficiency and load_lbs > 0 and ft is not None:
                    eff = round(float(ft) / float(load_lbs), 3)
                key_parts = []
                if by_region:
                    key_parts.append(region)
                if by_lift:
                    key_parts.append(lift)
                if variation:
                    key_parts.append(str(variation)[:20])
                if pos_desc:
                    key_parts.append(str(pos_desc)[:20])
                key = "|".join(key_parts) or region
                current = records.get(key)
                if not current or ft > current.get("peak_ftlb", -1):
                    rec = {
                        "peak_ftlb": round(float(ft), 1),
                        "timestamp": ts,
                        "lift": lift,
                        "position": pos_desc,
                        "region": region,
                        "source": getattr(item, "run_id", "live"),
                        "variation": variation,
                        "load_lbs": round(float(load_lbs), 1) if load_lbs else None,
                    }
                    if include_dominance and dom is not None:
                        rec["dominance_percent"] = round(float(dom), 1)
                    if include_efficiency and eff is not None:
                        rec["efficiency_ftlb_per_lb"] = eff
                    records[key] = rec
    return records


def compute_simple_trend(
    current_value: float,
    history_values: list[float],
    *,
    label: str = "value",
) -> dict[str, Any]:
    """
    Simple delta vs personal best / avg from history (for PRs/trends display).
    Returns dict with deltas, pct, direction notes. All modeled.
    """
    if not history_values:
        return {"current": current_value, "note": "no history yet"}
    best = max(history_values)
    avg = sum(history_values) / len(history_values)
    delta_best = current_value - best
    pct_best = (delta_best / best * 100) if best != 0 else 0.0
    direction = "new best" if delta_best > 0 else ("below best" if delta_best < -0.1 else "near best")
    return {
        "current": round(current_value, 1),
        "personal_best": round(best, 1),
        "history_avg": round(avg, 1),
        "delta_vs_best": round(delta_best, 1),
        "pct_vs_best": round(pct_best, 1),
        "direction": direction,
        "label": label,
        "note": "modeled estimate — relative to your saved runs only",
    }


def get_milestones(history_runs: list[Any]) -> list[str]:
    """
    Count-based and quality milestones from persisted history (self-competition flavor).
    Returns list of short honest strings, e.g. "ROM Explorer (10+ multi-pos runs logged)".
    Uses num positions, geo usage (from notes or summary), timestamps for "this month" etc.
    """
    if not history_runs:
        return []
    milestones = []
    n = len(history_runs)
    if n >= 5:
        milestones.append(f"Consistent Analyst ({n} saved analyses)")
    multi_count = 0
    geo_count = 0
    for r in history_runs:
        pos = getattr(r, "positions", []) or []
        if len(pos) >= 2:
            multi_count += 1
        summary = getattr(r, "summary", {}) or {}
        if "geometric" in str(summary).lower() or "geo" in str(getattr(r, "notes", "")).lower():
            geo_count += 1
    if multi_count >= 5:
        milestones.append("ROM Explorer (5+ multi-position or continuous runs)")
    if geo_count >= 3:
        milestones.append("Anthropometry User (3+ runs using your measurements for geometric MA)")
    # Simple recency (if timestamps present)
    recent = 0
    for r in history_runs:
        ts = getattr(r, "timestamp", "")
        if ts and "2026-06" in str(ts):  # rough; real code could parse
            recent += 1
    if recent >= 3:
        milestones.append("Active this month (3+ logged runs)")
    return milestones or ["Build some history — run & save a few multi-pos analyses"]


def compute_rom_consistency(mpr_or_analyses: Any) -> dict[str, Any]:
    """
    Wave 3: simple ROM consistency / efficiency helper for PRs (lower variation = better consistency, stable demand).
    Uses precomputed force_variation_coefficient if present (from MPR), else rough from ft-lbs.
    Returns dict with coeff, note (modeled estimate — relative to your runs only).
    """
    analyses = []
    if hasattr(mpr_or_analyses, "analyses"):
        analyses = mpr_or_analyses.analyses or []
    elif hasattr(mpr_or_analyses, "results"):
        analyses = [mpr_or_analyses]
    coeffs = []
    for a in analyses:
        if hasattr(a, "force_variation_coefficient"):
            c = getattr(a, "force_variation_coefficient", None)
            if c is not None:
                coeffs.append(float(c))
        elif hasattr(a, "results") and a.results:
            fts = [getattr(r, "peak_torque_ftlb", 0) or 0 for r in a.results]
            fts = [f for f in fts if f > 0]
            if len(fts) > 1:
                import statistics
                mean = statistics.mean(fts)
                if mean > 0:
                    coeffs.append(statistics.stdev(fts) / mean)
    if not coeffs:
        return {"avg_variation_coeff": None, "note": "no variation data — run multi-pos or continuous for coeff (lower = more consistent ROM demand)"}
    avg = sum(coeffs) / len(coeffs)
    return {
        "avg_variation_coeff": round(avg, 3),
        "note": "modeled estimate — lower coeff = more stable/consistent demand across positions/ROM (PR tracking target; your history only)",
    }


# -------------------------------------------------------------------
# Workout Logging Layer (end-goal foundation for tracking + modeled force overlay)
# Per user vision: track real workouts (sets/reps/weight), attach the existing
# biomechanical force/torque/dominance calculations per set for the supported
# exercises, then derive the usual training metrics (volume, e1RM, top-set volume,
# per-muscle "work") on top of the modeled data.
#
# Scoped start (user choice): deep quality on the main compounds we already model
# well (barbells, dumbbells, common machines that map to our 8 lifts + variations).
# Other exercises can be logged for real volume/1RM tracking with a note that
# full regional force modeling is not yet available.
#
# All values are modeled estimates when force data is attached.
# -------------------------------------------------------------------

from datetime import date as _date

# Simple mapping for the first ~10-12 common bb/db/machine exercises that map
# cleanly to our existing builders/variations (the 8 lifts + grip/stance/pos).
# For "every muscle": we leverage the multi-prime-mover results (pecs+delt+tri for
# pressing, glute+quad+ham+erector for lower body, etc.).
EXERCISE_MAP: dict[str, dict] = {
    # Barbell compounds (best modeled)
    "barbell_bench_flat": {
        "lift": "bench", "variation": "flat",
        "display": "Barbell Bench Press (Flat)",
        "default_target": "Pectoralis Major::Sternal fibers",
    },
    "barbell_bench_close": {
        "lift": "bench", "variation": "flat_close",
        "display": "Close-Grip Barbell Bench Press",
        "default_target": "Pectoralis Major::Sternal fibers",
    },
    "barbell_bench_wide": {
        "lift": "bench", "variation": "flat_wide",
        "display": "Wide-Grip Barbell Bench Press",
        "default_target": "Pectoralis Major::Sternal fibers",
    },
    "barbell_incline_30": {
        "lift": "incline", "variation": "incline_30",
        "display": "Barbell Incline Press (~30°)",
        "default_target": "Pectoralis Major::Clavicular fibers",
    },
    "barbell_squat_high": {
        "lift": "squat", "variation": "high_bar",
        "display": "High-Bar Back Squat",
        "default_target": "Gluteus Maximus::Upper fibers",
    },
    "barbell_squat_low": {
        "lift": "squat", "variation": "low_bar",
        "display": "Low-Bar Back Squat",
        "default_target": "Gluteus Maximus::Upper fibers",
    },
    "barbell_deadlift_conv": {
        "lift": "deadlift", "variation": "conventional",
        "display": "Conventional Deadlift",
        "default_target": "Gluteus Maximus::Upper fibers",
    },
    "barbell_ohp": {
        "lift": "ohp", "variation": "standing",
        "display": "Standing Barbell Overhead Press",
        "default_target": "Deltoid::Anterior",
    },
    # A few dumbbell / machine proxies (use closest modeled + note)
    "dumbbell_bench_flat": {
        "lift": "bench", "variation": "flat",
        "display": "Dumbbell Bench Press (Flat) — modeled via barbell flat proxy",
        "default_target": "Pectoralis Major::Sternal fibers",
        "note": "proxy",
    },
    "machine_chest_press": {
        "lift": "bench", "variation": "flat",
        "display": "Machine Chest Press — modeled via barbell flat proxy",
        "default_target": "Pectoralis Major::Sternal fibers",
        "note": "proxy",
    },
}

def estimate_one_rep_max(weight_lbs: float, reps: int, formula: str = "epley") -> float:
    """Standard e1RM estimators from working sets (for logged top sets)."""
    if reps <= 1:
        return float(weight_lbs)
    w = float(weight_lbs)
    if formula == "epley":
        return w * (1 + reps / 30.0)
    if formula == "brzycki":
        return w / (1.0278 - 0.0278 * reps)
    # default epley
    return w * (1 + reps / 30.0)

@dataclass
class LoggedSet:
    """One performed set with optional attached modeled force data.

    When you log a real set you did in the gym (e.g. 225 lb x 5 on flat bench),
    we can run the current athlete + lift model and attach the full
    AnalysisResult (which contains the list of MuscleForceResult for all prime
    movers) plus convenience scalars.

    This lets us compute "what this set actually demanded from your muscles"
    (your proportions, the grip/stance/position) alongside the usual training log
    numbers (volume = weight*reps).
    """
    exercise_key: str                 # e.g. "barbell_bench_flat" (must be in EXERCISE_MAP or treated as volume-only)
    weight_lbs: float
    reps: int
    rpe: Optional[float] = None
    notes: str = ""

    # Attached from the model (if exercise is supported). We store the full
    # AnalysisResult so regional accumulators (which expect list[AnalysisResult])
    # work directly.
    analysis_result: Optional["AnalysisResult"] = None
    modeled_peak_torque_ftlb: float = 0.0          # max across the results for this set
    modeled_dominance_percent: Optional[float] = None  # for the primary/target if present

    # Real training metrics for this set
    set_volume_lbs: float = 0.0                    # weight_lbs * reps
    modeled_work_ftlb: float = 0.0                 # sum(peak_torque_ftlb * reps) across movers (proxy "work")

    # For convenience / backward views
    modeled_force_results: list[MuscleForceResult] = field(default_factory=list)

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.set_volume_lbs == 0.0 and self.weight_lbs and self.reps:
            self.set_volume_lbs = self.weight_lbs * self.reps

        if self.analysis_result and getattr(self.analysis_result, "results", None):
            self.modeled_force_results = list(self.analysis_result.results)
        if not self.modeled_force_results:
            return

        self.modeled_peak_torque_ftlb = max(
            (getattr(r, "peak_torque_ftlb", 0) or 0 for r in self.modeled_force_results),
            default=0.0
        )
        self.modeled_work_ftlb = self.modeled_peak_torque_ftlb * self.reps
        if self.modeled_force_results:
            dom = getattr(self.modeled_force_results[0], "dominance_percent", None)
            if dom is not None:
                self.modeled_dominance_percent = dom

@dataclass
class LoggedWorkout:
    """A real training session you performed.

    Contains the actual sets you did (with weight/reps/RPE you used), plus
    any modeled force data we could attach for the supported exercises.
    """
    name: str = "Workout"
    date: str = field(default_factory=lambda: _date.today().isoformat())
    athlete_name: Optional[str] = None
    notes: str = ""
    sets: list[LoggedSet] = field(default_factory=list)

    def add_set(self, s: LoggedSet) -> "LoggedWorkout":
        self.sets.append(s)
        return self

    def real_volume_lbs(self) -> float:
        return sum(s.set_volume_lbs for s in self.sets)

    def modeled_total_work_ftlb(self) -> float:
        return sum(s.modeled_work_ftlb for s in self.sets)

    def get_exercise_summary(self) -> dict[str, dict]:
        """Group by exercise_key: real volume, modeled work, top set, e1RM est."""
        out: dict[str, dict] = {}
        for s in self.sets:
            key = s.exercise_key
            if key not in out:
                out[key] = {
                    "display": EXERCISE_MAP.get(key, {}).get("display", key),
                    "sets": 0,
                    "total_reps": 0,
                    "real_volume_lbs": 0.0,
                    "modeled_work_ftlb": 0.0,
                    "top_set_weight_lbs": 0.0,
                    "top_set_reps": 0,
                    "e1rm_lbs": 0.0,
                }
            o = out[key]
            o["sets"] += 1
            o["total_reps"] += s.reps
            o["real_volume_lbs"] += s.set_volume_lbs
            o["modeled_work_ftlb"] += s.modeled_work_ftlb
            if s.weight_lbs > o["top_set_weight_lbs"]:
                o["top_set_weight_lbs"] = s.weight_lbs
                o["top_set_reps"] = s.reps
                o["e1rm_lbs"] = round(estimate_one_rep_max(s.weight_lbs, s.reps), 1)
        return out

    def get_regional_modeled_summary(self, service: Optional[AnalysisService] = None) -> dict:
        """If any sets had modeled results, aggregate regional stress/volume
        across the whole workout using the existing accumulators.
        This is how we get 'this workout hit your sternal pecs with X ft-lb total modeled demand'.
        """
        svc = service or _get_default_service()
        all_analyses = [s.analysis_result for s in self.sets if getattr(s, "analysis_result", None)]
        if not all_analyses:
            return {"note": "no modeled force results attached (exercise may be volume-only for now)"}
        stress = svc.accumulate_regional_stress(all_analyses)
        vol = svc.accumulate_regional_volume(all_analyses)
        return {
            "regional_stress": {k: v for k, v in stress.items() if not k.startswith("meta")},
            "total_stress": stress.get("meta", {}).get("total_stress", 0.0),
            "total_volume_stress": vol.get("meta", {}).get("total_volume_stress", 0.0),
            "num_modeled_sets": len(all_analyses),
        }

def create_logged_set(
    athlete: Optional[Subject],
    exercise_key: str,
    weight_lbs: float,
    reps: int,
    rpe: Optional[float] = None,
    notes: str = "",
    target_region_name: Optional[str] = None,
) -> LoggedSet:
    """Convenience: create a LoggedSet and (if possible) attach the modeled force results
    for that exercise using the current athlete + our existing analyze pipeline.

    If the exercise_key is not in EXERCISE_MAP or no athlete, we still create a
    volume-only LoggedSet (real training metrics are always captured).
    """
    s = LoggedSet(
        exercise_key=exercise_key,
        weight_lbs=weight_lbs,
        reps=reps,
        rpe=rpe,
        notes=notes,
    )

    mapping = EXERCISE_MAP.get(exercise_key)
    if not mapping or not athlete:
        if not mapping:
            s.notes = (s.notes + " [volume-only: no full force model for this exercise key yet]").strip()
        return s

    try:
        from fiberforce.recipes import analyze
        res = analyze(
            mapping["lift"],
            load_lbs=weight_lbs,
            variation=mapping.get("variation", "flat"),
            target_region_name=target_region_name or mapping.get("default_target"),
            athlete=athlete,
            use_geometric=True,
            units="imperial",
        )
        s.analysis_result = res
        # post_init will pull the force_results list and compute scalars/dominance
        s.__post_init__()
        if mapping.get("note") == "proxy":
            s.notes = (s.notes + " [modeled via proxy to closest barbell variation]").strip()
    except Exception as e:
        s.notes = (s.notes + f" [modeling failed: {e}]").strip()

    return s

# Persistence for logged workouts (same JSON style as the rest of the layer)
def save_logged_workout(
    workout: LoggedWorkout,
    name: Optional[str] = None,
    results_dir: Optional[Path] = None,
) -> Path:
    """Persist a LoggedWorkout (real performed sets + any attached modeled force data)."""
    if not name:
        name = f"workout_{workout.date}_{workout.name.lower().replace(' ', '_')[:30]}"
    payload = _to_jsonable(workout)
    payload["__artifact_type__"] = "logged_workout"
    return save_json(payload, name, results_dir, subdir="logged_workouts")

def load_logged_workout(
    name: str,
    results_dir: Optional[Path] = None,
) -> LoggedWorkout:
    base = results_dir or DEFAULT_RESULTS_DIR
    path = base / "logged_workouts" / (name if name.endswith(".json") else f"{name}.json")
    if not path.exists():
        # fallback
        path = base / (name if name.endswith(".json") else f"{name}.json")
    if not path.exists():
        raise CorruptResultError(f"Logged workout '{name}' not found")
    raw = load_json(path)
    obj = _from_jsonable(raw)
    if isinstance(obj, LoggedWorkout):
        return obj
    if isinstance(raw, dict):
        return LoggedWorkout(**{k: _from_jsonable(v) for k, v in raw.items() if not k.startswith("__")})
    raise CorruptResultError(f"Could not reconstruct LoggedWorkout from {name}")

def list_logged_workouts(results_dir: Optional[Path] = None) -> list[str]:
    base = results_dir or DEFAULT_RESULTS_DIR
    d = base / "logged_workouts"
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))

# End of results.py — clean, practical, integrated persistence layer (now with v0.5 program models + workout logging foundation).
