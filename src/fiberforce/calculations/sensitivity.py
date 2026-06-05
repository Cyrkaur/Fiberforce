"""
Sensitivity Analysis for FiberForce (v0.1.4 early foundation, landed in big push).

This module provides the first "what if" capability:
- Vary one variable (load, body measurement, moment arm, etc.) across a range.
- Re-run peak force calculations.
- Return structured results suitable for tables or further analysis.

Current scope (MVP for this run):
- Single-variable sensitivity only.
- Works with existing builders (bench + squat primarily).
- Simple, extensible design.

Visualization support added: SensitivityAnalyzer now has a .plot() convenience method
that delegates to fiberforce.visualization (matplotlib with rich+ASCII fallback).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from fiberforce.models import Subject, AnalyzedPosition, MuscleRegion
from fiberforce.calculations.base import CalculationContext
from fiberforce.calculations.peak_force import SimplePeakForceCalculator


@dataclass
class SensitivityPoint:
    """One point in a sensitivity analysis."""
    variable_name: str
    variable_value: Any
    peak_force_n: float
    confidence_level: str
    notes: str = ""


@dataclass
class SensitivityResult:
    """Full result of a single-variable sensitivity run."""
    variable_name: str
    target_region: str
    points: list[SensitivityPoint] = field(default_factory=list)
    base_value: Optional[Any] = None
    summary: str = ""

    def to_table_rows(self) -> list[dict]:
        """Simple dict rows for rich table or printing."""
        rows = []
        for p in self.points:
            rows.append({
                self.variable_name: p.variable_value,
                "Peak Force (N)": round(p.peak_force_n, 1),
                "Confidence": p.confidence_level,
            })
        return rows

    def insight(self) -> str:
        """
        0.7→0.8 simple usability helper: human-readable takeaway from the sensitivity sweep.
        Example: "grip_width_cm had a 14.3% effect on sternal stress across the tested range.
        Lowest stress at 78 cm."
        """
        if not self.points:
            return "No sensitivity points."

        forces = [p.peak_force_n for p in self.points]
        fmin, fmax = min(forces), max(forces)
        spread = ((fmax - fmin) / fmax * 100) if fmax else 0.0

        # Find the value that produced min stress (often the "best" for that target)
        min_point = min(self.points, key=lambda p: p.peak_force_n)
        max_point = max(self.points, key=lambda p: p.peak_force_n)

        var = self.variable_name
        region = self.target_region

        msg = (
            f"{var} had a {spread:.1f}% modeled effect on {region} across the tested range.\n"
            f"  Lowest stress observed at {min_point.variable_value} ({min_point.peak_force_n:.0f} N).\n"
            f"  Highest at {max_point.variable_value} ({max_point.peak_force_n:.0f} N)."
        )
        return msg


class SensitivityAnalyzer:
    """
    First-cut sensitivity analyzer.

    Usage example (will be wired to CLI):
        analyzer = SensitivityAnalyzer()
        result = analyzer.run(
            subject=subj,
            base_position=base_pos,
            variable="load_kg",
            values=[80, 90, 100, 110, 120],
            target_region=sternal,
            rebuild_position=some_callable_that_takes_new_load_and_returns_new_pos
        )

    Visualization:
        result = analyzer.run(...)
        analyzer.plot(result)                 # uses matplotlib if available, else rich+ASCII
        analyzer.plot(result, save_path="sweep.png", show=False)
    """

    def __init__(self, calculator: Optional[SimplePeakForceCalculator] = None):
        self.calculator = calculator or SimplePeakForceCalculator()

    def run(
        self,
        subject: Subject,
        base_position: AnalyzedPosition,
        variable: str,
        values: list[Any],
        target_region: MuscleRegion,
        rebuild_position: Optional[Callable[[AnalyzedPosition, Any], AnalyzedPosition]] = None,
        context: Optional[CalculationContext] = None,
    ) -> SensitivityResult:
        """
        Run sensitivity analysis by varying one variable.

        If no rebuild_position is provided, we attempt simple in-place mutation
        for known easy variables (load_kg on the external load).
        """
        points: list[SensitivityPoint] = []

        for val in values:
            if rebuild_position:
                pos = rebuild_position(base_position, val)
            else:
                pos = self._simple_rebuild(base_position, variable, val)

            results = self.calculator.calculate_peak_force(subject, pos, context)
            # Find the result for our target region
            match = next((r for r in results if r.muscle_region.region_name == target_region.region_name), None)

            if match:
                points.append(SensitivityPoint(
                    variable_name=variable,
                    variable_value=val,
                    peak_force_n=match.peak_force_newtons,
                    confidence_level=match.confidence_level,
                    notes=match.notes[:80] if match.notes else "",
                ))
            else:
                points.append(SensitivityPoint(
                    variable_name=variable,
                    variable_value=val,
                    peak_force_n=0.0,
                    confidence_level="no_match",
                    notes="Target region not found in results",
                ))

        result = SensitivityResult(
            variable_name=variable,
            target_region=str(target_region),
            points=points,
            base_value=values[0] if values else None,
            summary=f"Sensitivity on {variable} across {len(values)} points for {target_region}",
        )
        return result

    def run_multi(
        self,
        subject: Subject,
        base_position: AnalyzedPosition,
        variables: list[tuple[str, list[Any]]],
        target_region: MuscleRegion,
        rebuild_multi: Callable[[AnalyzedPosition, dict], AnalyzedPosition],
        context: Optional[CalculationContext] = None,
    ) -> list[SensitivityResult]:
        """
        Multi-variable sensitivity (simple sequential sweeps for now).

        variables: list of (name, values_list)
        rebuild_multi: function that takes base_position + dict of {var_name: value} and returns new position.

        Returns one SensitivityResult per variable (varying one while holding others at first value).
        This is a pragmatic starting point; true 2D grids can be added later.
        """
        results_list: list[SensitivityResult] = []

        for var_name, values in variables:
            # For this sweep, hold other variables at their first value
            fixed = {name: vals[0] for name, vals in variables if name != var_name}

            points: list[SensitivityPoint] = []
            for val in values:
                params = {**fixed, var_name: val}
                pos = rebuild_multi(base_position, params)

                calc_results = self.calculator.calculate_peak_force(subject, pos, context)
                match = next((r for r in calc_results if r.muscle_region.region_name == target_region.region_name), None)

                if match:
                    points.append(SensitivityPoint(
                        variable_name=var_name,
                        variable_value=val,
                        peak_force_n=match.peak_force_newtons,
                        confidence_level=match.confidence_level,
                        notes=match.notes[:70] if match.notes else "",
                    ))
                else:
                    points.append(SensitivityPoint(
                        variable_name=var_name,
                        variable_value=val,
                        peak_force_n=0.0,
                        confidence_level="no_match",
                        notes="Target not found",
                    ))

            res = SensitivityResult(
                variable_name=var_name,
                target_region=str(target_region),
                points=points,
                base_value=values[0],
                summary=f"Multi-var sweep on {var_name} (others fixed at first value) for {target_region}",
            )
            results_list.append(res)

        return results_list

    def plot(self, result: SensitivityResult, **kwargs):
        """
        Visualize this sensitivity result.

        Thin convenience wrapper around fiberforce.visualization.plot_sensitivity.
        Supports save_path, show, ascii_only, etc.

        Example:
            result = analyzer.run(...)
            analyzer.plot(result, save_path="my_sweep.png")
        """
        from fiberforce.visualization import plot_sensitivity
        return plot_sensitivity(result, **kwargs)

    def _simple_rebuild(self, base: AnalyzedPosition, variable: str, new_value: Any) -> AnalyzedPosition:
        """Very lightweight in-place style rebuild for common cases."""
        # We work on a copy of the pose data
        pose = base.pose
        # Better: mutate a shallow copy of relevant parts (TODO for future optimization)

        # For load_kg we can often just change the external load
        if variable == "load_kg" and pose.external_load:
            from fiberforce.models import ExternalLoad
            new_load = ExternalLoad(
                mass_kg=new_value,
                load_type=pose.external_load.load_type,
                load_position=pose.external_load.load_position,
            )
            # Create a new Pose with updated load (simple approach)
            from fiberforce.models import Pose
            updated_pose = Pose(
                name=pose.name + f" (load={new_value})",
                joint_angles=pose.joint_angles,
                external_load=new_load,
                active_attachments=pose.active_attachments,
                load_moment_arms=pose.load_moment_arms.copy(),
                notes=pose.notes,
            )
            return AnalyzedPosition(pose=updated_pose, target_regions=base.target_regions)

        # Fallback: return original (user should provide rebuild func for complex vars)
        return base
