"""
FiberForce Recipes & Common Patterns (0.7+ Usability)

This module collects the most common, high-value usage patterns so you don't
have to remember the exact service + builder + geometric incantations every time.

It is intentionally lightweight — mostly documented functions + a few thin
convenience wrappers around AnalysisService.

Recommended import:
    from fiberforce.recipes import (
        create_athlete,
        analyze,
        analyze_multi_position,
        build_weekly_program,
        sensitivity_sweep,
    )

All functions accept **kwargs that are passed through to the underlying
AnalysisService / builders, so you can always drop down to full power.
"""

from typing import Any, Optional, Sequence, Union

# Use relative imports to avoid circular import when fiberforce.__init__ is loading
from .analysis.service import AnalysisService, AnalysisResult, MultiPositionResult
from .models import Subject, UserAnthropometry
from .results import TrainingSession, WeeklyProgram
from .calculations.utils import load_lbs_to_kg, inches_to_cm


def create_athlete(
    name: str = "Athlete",
    units: str = "imperial",  # v1 default: inches for lengths
    **measurements: float
) -> Subject:
    """
    Quick way to create a Subject with measurements.

    units="imperial" (default): pass femur_in, humerus_in, etc. (converted internally)
    units="metric": pass _cm as before.

    Example (imperial):
        athlete = create_athlete(
            name="Long Femur Guy",
            femur_in=18.1,
            tibia_in=15.7,
            humerus_in=13.8,
            biacromial_in=16.5,
        )
    """
    svc = AnalysisService()
    return svc.create_subject_from_measurements(name=name, units=units, **measurements)


def analyze(
    lift: str,
    load_kg: float = 100.0,
    load_lbs: Optional[float] = None,
    variation: str = "flat",
    target_region_name: Optional[str] = None,
    athlete: Optional[Subject] = None,
    use_geometric: bool = True,
    units: str = "imperial",
    **kwargs,
) -> AnalysisResult:
    """
    One-liner for a single-position analysis with sensible defaults + geometric.

    v1: supports load_lbs (imperial default), units for athlete.
    """
    svc = AnalysisService()
    if athlete is None:
        athlete = create_athlete(units=units)

    if load_lbs is not None:
        load_kg = load_lbs_to_kg(load_lbs)  # from utils? import at top if needed

    pos = svc.build_position(
        lift,
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name or "Sternal fibers",
        use_geometric=use_geometric,
        **kwargs,
    )
    return svc.analyze(athlete, pos)


def analyze_multi_position(
    lift: str,
    positions: Sequence[str] = ("bottom", "mid", "top"),
    load_kg: float = 100.0,
    load_lbs: Optional[float] = None,
    variation: str = "flat",
    target_region_name: Optional[str] = None,
    athlete: Optional[Subject] = None,
    use_geometric: bool = True,
    units: str = "imperial",
    **kwargs,
) -> MultiPositionResult:
    """
    Convenient multi-position analysis (the 0.5+ flagship).

    Example:
        mpr = analyze_multi_position("bench", ["bottom", "mid", "top"],
                                     load_kg=105, athlete=my_athlete, use_geometric=True)
        print(mpr.interpret())
    """
    svc = AnalysisService()
    if athlete is None:
        athlete = create_athlete(units=units)

    if load_lbs is not None:
        load_kg = load_lbs_to_kg(load_lbs)

    return svc.analyze_multi_position(
        athlete,
        lift,
        list(positions),
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name or "Sternal fibers",
        use_geometric=use_geometric,
        **kwargs,
    )


def analyze_continuous(
    lift: str,
    steps: int = 5,
    load_kg: float = 100.0,
    load_lbs: Optional[float] = None,
    variation: str = "flat",
    target_region_name: Optional[str] = None,
    athlete: Optional[Subject] = None,
    use_geometric: bool = True,
    units: str = "imperial",
    tempo_s_per_step: float = 0.75,
    **kwargs,
) -> MultiPositionResult:
    """
    High-level continuous ROM analysis (post-v1 dynamics MVP + Wave 3 fuller).
    Vary primary joint angle over range (knee for squat/rdl, shoulder for bench).
    tempo_s_per_step: for F-V velocity estimate (exposes tempo control).
    Defaults: squat knee 35->170 deg, 5 steps.
    Returns MultiPositionResult (full .interpret(), aggregates, ft-lb etc.).
    """
    svc = AnalysisService()
    if athlete is None:
        athlete = create_athlete(units=units)

    if load_lbs is not None:
        load_kg = load_lbs_to_kg(load_lbs)

    # Pass range hints via kwargs; service/builders interpret knee_start etc.
    # For convenience, if not provided, set defaults per lift
    if "knee_start" not in kwargs and lift.lower() in ("squat", "backsquat", "romanian", "rdl"):
        kwargs.setdefault("knee_start", 35.0)
        kwargs.setdefault("knee_end", 170.0)
    if "shoulder_start" not in kwargs and lift.lower() in ("bench", "incline", "benchpress"):
        kwargs.setdefault("shoulder_start", 60.0)
        kwargs.setdefault("shoulder_end", 20.0)

    return svc.analyze_continuous(
        athlete,
        lift,
        steps=steps,
        load_kg=load_kg,
        variation=variation,
        target_region_name=target_region_name or "Sternal fibers",
        use_geometric=use_geometric,
        tempo_s_per_step=tempo_s_per_step,
        **kwargs,
    )


def sensitivity_sweep(
    lift: str,
    variable: str,
    values: Sequence[Any],
    load_kg: float = 100.0,
    athlete: Optional[Subject] = None,
    target_region_name: Optional[str] = None,
    use_geometric: bool = True,
    **kwargs,
):
    """
    Run a sensitivity sweep with geometric support and return both the result
    and a human insight string.

    Example:
        res, insight = sensitivity_sweep(
            "bench", "grip_width_cm", [48, 58, 68, 78],
            load_kg=110, athlete=athlete
        )
        print(insight)
        # or res.insight()
    """
    svc = AnalysisService()
    if athlete is None:
        athlete = create_athlete()

    base = svc.build_position(
        lift,
        load_kg=load_kg,
        target_region_name=target_region_name or "Sternal fibers",
        use_geometric=use_geometric,
        **kwargs,
    )

    # Get the region
    from .reference import KNOWN_MUSCLE_REGIONS
    target = next(
        (r for r in KNOWN_MUSCLE_REGIONS if (target_region_name or "Sternal") in r.region_name),
        KNOWN_MUSCLE_REGIONS[0],
    )

    result = svc.sensitivity(
        athlete,
        base,
        variable=variable,
        values=list(values),
        target_region=target,
        rebuild_position=None,  # let the service handle common cases + our build_position kwargs
    )

    insight = result.insight() if hasattr(result, "insight") else ""
    return result, insight


def build_weekly_program(
    name: str,
    sessions_data: list[dict],
    athlete: Optional[Subject] = None,
    service: Optional[AnalysisService] = None,
) -> WeeklyProgram:
    """
    Build a WeeklyProgram from a simple list of dicts describing sessions.

    sessions_data example:
    [
        {"name": "Mon Bench", "lift": "bench", "load_kg": 100, "positions": ["bottom", "mid"]},
        {"name": "Tue Squat", "lift": "squat", "load_kg": 140, "variation": "low_bar", "positions": ["bottom", "mid", "top"]},
    ]

    This is a very common "I want to model my week" pattern.
    """
    svc = service or AnalysisService()
    if athlete is None:
        athlete = create_athlete()

    prog = WeeklyProgram(name=name)

    for sess_data in sessions_data:
        sess = TrainingSession(name=sess_data.get("name", "Session"))
        lift = sess_data["lift"]
        load = sess_data.get("load_kg", 100.0)
        variation = sess_data.get("variation", "flat")
        positions = sess_data.get("positions", ["bottom"])

        if len(positions) > 1:
            mpr = svc.analyze_multi_position(
                athlete, lift, positions, load_kg=load, variation=variation,
                use_geometric=sess_data.get("use_geometric", True),
            )
            sess.add_analyses(list(mpr))
        else:
            res = analyze(
                lift, load_kg=load, variation=variation,
                athlete=athlete, use_geometric=sess_data.get("use_geometric", True),
            )
            sess.add_analysis(res)

        prog.add_session(sess)

    return prog


# Convenience re-exports of the interpret methods for discoverability
from fiberforce.results import WeeklyProgram as _WP, TrainingSession as _TS
from fiberforce.analysis.service import MultiPositionResult as _MPR

# These are already instance methods; the module just makes the pattern obvious.
__all__ = [
    "create_athlete",
    "analyze",
    "analyze_multi_position",
    "sensitivity_sweep",
    "build_weekly_program",
]
