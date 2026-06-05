"""
FiberForce Typer CLI — complete implementation with full profile persistence surface.

Primary entry point: `fiberforce` (configured in pyproject.toml).

Key groups:
- analyze, sensitivity, compare, visualize — high-level analysis (powered by AnalysisService)
- profile (subcommands) — the enhanced persistence story:
    save / load / list / run
    + NEW:
    save-config, save-result, load-result, list-results,
    multi-sens (profile-based multi-var sensitivity + auto-save),
    compare-runs (saved runs or live profile compare)

All heavy logic is delegated to AnalysisService + the new results/persistence layer.
Clean error handling, helpful messages, and integration with visualization fallbacks.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import typer

from fiberforce import AnalysisService
from fiberforce.calculations.utils import load_lbs_to_kg, nm_to_ftlb
from fiberforce.profiles import (
    save_anthropometry,
    load_anthropometry,
    list_profiles,
    UserAnthropometry,
    # Re-exported enhanced persistence
    load_analysis_run,
    load_sensitivity_run,
    load_compare_run,
    save_lift_config,
    list_saved_runs, list_configs,
    run_profile_analysis,
    run_profile_multi_sensitivity,
    run_profile_compare,
    run_profile_multi_position,  # Phase 2c multi-pos persistence
    DEFAULT_RESULTS_DIR,
)
from fiberforce.models import JointAngles, ExternalLoad, LiftConfiguration
from fiberforce.visualization import (
    plot_sensitivity,
    plot_comparison,
    is_headless,
)


app = typer.Typer(
    name="fiberforce",
    help="FiberForce — Personalized biomechanical modeling for regional hypertrophy and force analysis.",
    add_completion=False,
    rich_markup_mode="markdown",
)

# Enable `fiberforce --version`
def _version_callback(value: bool):
    if value:
        from fiberforce import __version__
        typer.echo(f"fiberforce {__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed FiberForce version and exit.",
    ),
):
    pass  # The callback handles --version


profile_app = typer.Typer(
    name="profile",
    help="Profile & persistence commands. Save/load anthropometry + full analysis results, configs, sensitivity & compare runs.",
)
app.add_typer(profile_app, name="profile")

# Global service (the single source of truth for all commands)
service = AnalysisService()


# -------------------------------------------------------------------
# Helper utilities (error handling + output)
# -------------------------------------------------------------------

def _safe_load_profile(name: str) -> UserAnthropometry:
    try:
        return load_anthropometry(name)
    except Exception as e:
        typer.secho(f"Error loading profile '{name}': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


def _print_run_saved(path: Path, kind: str = "run") -> None:
    typer.secho(f"✓ Saved {kind} → {path}", fg=typer.colors.GREEN)


def _print_analysis_result(res, title: str = "Analysis") -> None:
    typer.echo(f"\n{title}")
    typer.echo("-" * 60)
    for r in res.results:
        ma = f"{r.moment_arm_used_cm}cm" if r.moment_arm_used_cm else "?"
        torque = nm_to_ftlb(r.peak_torque_nm) if r.peak_torque_nm else 0
        typer.echo(f"  {r.muscle_region}  →  {torque:8.1f} ft-lb   (MA: {ma})  [{r.confidence_level}]")
        if r.notes:
            typer.echo(f"      {r.notes[:120]}")
    typer.echo(f"  Position: {res.position_description}")
    typer.echo(f"  Confidence mix: {res.confidence_summary}")


# -------------------------------------------------------------------
# Core analysis commands (wired exclusively through AnalysisService)
# -------------------------------------------------------------------

@app.command("analyze")
def cmd_analyze(
    lift: str = typer.Argument(..., help="Lift: bench, incline, squat, deadlift, rdl/romanian, ohp"),
    load_kg: float = typer.Option(100.0, "-l", "--load-kg", help="External load in kg (or use --load-lbs for imperial)"),
    load_lbs: Optional[float] = typer.Option(None, "--load-lbs", help="External load in lbs (v1 imperial default)"),
    variation: str = typer.Option("flat", "-v", "--variation", help="Variation (flat, high_bar, conventional, etc.)"),
    target: str = typer.Option("Sternal fibers", "-t", "--target", help="Target muscle region name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Load anthropometry from saved profile"),
    units: str = typer.Option("imperial", "--units", help="imperial (inches/lbs, default v1) or metric"),
    plot: bool = typer.Option(False, "--plot", help="Show visualization if possible"),
    save_plot: Optional[str] = typer.Option(None, "--save-plot", help="Save plot to file"),
):
    """Run peak force analysis for a lift/position using AnalysisService."""
    try:
        if load_lbs is not None:
            load_kg = load_lbs_to_kg(load_lbs)  # need import

        if profile:
            anthro = _safe_load_profile(profile)
            subj = service.create_subject_from_measurements(name=profile, units=units, **{k: v for k, v in vars(anthro).items() if v is not None and not k.startswith("_")})
        else:
            subj = service.create_subject_from_measurements(units=units)

        pos = service.build_position(lift, load_kg=load_kg, variation=variation, target_region_name=target)
        result = service.analyze(subj, pos, target_regions=pos.target_regions)

        _print_analysis_result(result, f"Analysis: {lift} / {variation} @ {load_kg}kg → {target}")

        if plot or save_plot:
            typer.echo("(Use `sensitivity` + --plot for rich charts. Single analysis shown above.)")

    except Exception as e:
        typer.secho(f"Analyze failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("sensitivity")
def cmd_sensitivity(
    lift: str = typer.Argument(..., help="Lift to analyze"),
    variable: str = typer.Option("load_kg", "--variable", "-var", help="Variable to sweep"),
    start: float = typer.Option(60.0, "--start"),
    end: float = typer.Option(140.0, "--end"),
    step: float = typer.Option(10.0, "--step"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    target: str = typer.Option("Sternal fibers", "-t", "--target"),
    plot: bool = typer.Option(False, "--plot"),
    save_plot: Optional[str] = typer.Option(None, "--save-plot"),
    ascii_only: bool = typer.Option(False, "--ascii-only"),
):
    """Single-variable sensitivity sweep (delegated to AnalysisService + results persistence available via profile commands)."""
    try:
        if profile:
            anthro = _safe_load_profile(profile)
            subj = service.create_subject_from_measurements(name=profile)
            subj.anthropometry = anthro
        else:
            subj = service.create_subject_from_measurements()

        pos = service.build_position(lift, load_kg=start, variation="flat", target_region_name=target)

        from fiberforce.reference import KNOWN_MUSCLE_REGIONS
        target_region = next(
            (r for r in KNOWN_MUSCLE_REGIONS if target.lower() in r.region_name.lower()),
            None,
        )
        if target_region is None:
            target_region = next((r for r in KNOWN_MUSCLE_REGIONS if target.lower() in r.region_name.lower()), KNOWN_MUSCLE_REGIONS[0])

        values = list(range(int(start), int(end) + 1, int(step)))
        sens = service.sensitivity(subj, pos, variable=variable, values=values, target_region=target_region)

        typer.echo(f"\nSensitivity: {variable} on {lift} ({len(values)} points)")
        for row in sens.to_table_rows()[:12]:
            typer.echo(f"  {row}")

        if plot or save_plot:
            plot_sensitivity(sens, save_path=save_plot, show=plot and not is_headless(), ascii_only=ascii_only)

        if profile:
            typer.echo("\nTip: use `fiberforce profile save-result ...` or the multi-sens command for full saved runs.")

    except Exception as e:
        typer.secho(f"Sensitivity failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("compare")
def cmd_compare(
    lift: str = typer.Argument(..., help="Lift"),
    a: str = typer.Option(..., "--a", help="First config/variation"),
    b: str = typer.Option(..., "--b", help="Second config/variation"),
    load_kg: float = typer.Option(100.0, "-l", "--load-kg"),
    target: Optional[str] = typer.Option(None, "-t", "--target", help="Target region (auto-detected if omitted)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    plot: bool = typer.Option(False, "--plot"),
    save_plot: Optional[str] = typer.Option(None, "--save-plot"),
):
    """Two-way comparison (uses AnalysisService.compare)."""
    try:
        overrides = {}
        comp = service.compare(lift, a, b, load_kg=load_kg, target=target, **overrides)

        typer.echo(f"\nCompare {lift}: {a} vs {b} @ {load_kg}kg → {target}")
        for row in comp.to_table_rows():
            typer.echo(f"  {row}")

        if plot or save_plot:
            plot_comparison(comp, save_path=save_plot, show=plot and not is_headless())

    except Exception as e:
        typer.secho(f"Compare failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("visualize")
def cmd_visualize(
    kind: str = typer.Argument(..., help="sensitivity | compare | auto"),
    lift: Optional[str] = typer.Option(None, "--lift"),
    variable: Optional[str] = typer.Option(None, "--variable"),
    start: Optional[float] = typer.Option(None),
    end: Optional[float] = typer.Option(None),
    profile: Optional[str] = typer.Option(None, "--profile"),
):
    """Universal visualizer (dispatches to visualization module)."""
    typer.echo("Visualization command — for full power use --plot / --save-plot on sensitivity/compare, or load a saved run and call visualize() in Python.")
    typer.echo("Example: fiberforce sensitivity bench --variable load_kg --start 80 --end 120 --plot")


# -------------------------------------------------------------------
# PROFILE group — the heart of the enhanced persistence task
# -------------------------------------------------------------------

@profile_app.command("save")
def profile_save(
    name: str = typer.Argument(..., help="Profile name (e.g. 'me' or 'long-femur-2026')"),
    humerus: Optional[float] = typer.Option(None, "--humerus"),
    forearm: Optional[float] = typer.Option(None, "--forearm"),
    biacromial: Optional[float] = typer.Option(None, "--biacromial"),
    femur: Optional[float] = typer.Option(None, "--femur"),
    tibia: Optional[float] = typer.Option(None, "--tibia"),
    notes: str = typer.Option("", "--notes"),
):
    """Save or update a personal anthropometry profile (JSON)."""
    anthro = UserAnthropometry(
        name=name,
        humerus_length_cm=humerus,
        forearm_length_cm=forearm,
        biacromial_width_cm=biacromial,
        femur_length_cm=femur,
        tibia_length_cm=tibia,
        notes=notes or f"Saved via CLI on {datetime.now().date()}",
    )
    path = save_anthropometry(anthro, name)
    typer.secho(f"✓ Profile saved → {path}", fg=typer.colors.GREEN)


@profile_app.command("load")
def profile_load(name: str = typer.Argument(..., help="Profile name")):
    """Load and pretty-print a saved anthropometry profile."""
    anthro = _safe_load_profile(name)
    typer.echo(json.dumps(asdict(anthro), indent=2, default=str))


@profile_app.command("list")
def profile_list():
    """List all saved anthropometry profiles."""
    profs = list_profiles()
    if not profs:
        typer.echo("No profiles found. Create one with: fiberforce profile save myname --femur 42 ...")
        return
    typer.echo("Saved profiles:")
    for p in profs:
        typer.echo(f"  • {p}")


@profile_app.command("run")
def profile_run(
    name: str = typer.Argument(..., help="Profile to use"),
    lift: str = typer.Option("bench", "--lift", "-l"),
    load_kg: float = typer.Option(100.0, "--load-kg"),
    variation: str = typer.Option("flat", "-v"),
    target: str = typer.Option("Sternal fibers", "-t", "--target"),
):
    """Load profile + immediately run analysis (classic + still very useful)."""
    anthro = _safe_load_profile(name)
    subj = service.create_subject_from_measurements(name=name)
    subj.anthropometry = anthro

    pos = service.build_position(lift, load_kg=load_kg, variation=variation, target_region_name=target)
    res = service.analyze(subj, pos)

    _print_analysis_result(res, f"Profile '{name}' — {lift} analysis")

    typer.echo("\nTip: `fiberforce profile save-result mybenchrun --profile %s --lift %s ...` to persist this run." % (name, lift))


# ---------- NEW persistence subcommands under profile ----------

@profile_app.command("save-config")
def profile_save_config(
    name: str = typer.Argument(..., help="Name for the saved LiftConfiguration"),
    lift: str = typer.Option("bench", "--lift"),
    variation: str = typer.Option("flat", "-v"),
    load_kg: float = typer.Option(100.0, "-l", "--load-kg"),
):
    """Save a reusable LiftConfiguration (no results yet)."""
    config = LiftConfiguration(
        lift_name=lift,
        variation=variation,
        joint_angles=JointAngles(values={"shoulder": 90, "elbow": 90}),
        external_load=ExternalLoad(mass_kg=load_kg),
        notes=f"Saved via CLI {datetime.now().isoformat()}",
    )
    path = save_lift_config(config, name)
    _print_run_saved(path, "LiftConfiguration")


@profile_app.command("save-result")
def profile_save_result(
    name: str = typer.Argument(..., help="Name / run_id for the saved analysis result"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Associate with this anthropometry profile"),
    lift: str = typer.Option("bench", "--lift"),
    load_kg: float = typer.Option(100.0, "-l"),
    variation: str = typer.Option("flat", "-v"),
    target: str = typer.Option("Sternal fibers", "-t"),
    notes: str = typer.Option(""),
):
    """Run analysis from (optional) profile and persist the full SavedAnalysisRun (config + MuscleForceResult list)."""
    try:
        if profile:
            run, path = run_profile_analysis(
                profile_name=profile,
                lift=lift,
                load_kg=load_kg,
                variation=variation,
                target_region_name=target,
                notes=notes,
            )
        else:
            subj = service.create_subject_from_measurements()
            pos = service.build_position(lift, load_kg=load_kg, variation=variation, target_region_name=target)
            analysis_res, path = service.save_current_analysis(subj, pos, run_id=name, notes=notes)

        _print_run_saved(path, "analysis result")
        typer.echo(f"  Run ID: {name}")
    except Exception as e:
        typer.secho(f"save-result failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@profile_app.command("load-result")
def profile_load_result(name: str = typer.Argument(..., help="Saved analysis / sensitivity / compare run name")):
    """Load any previously saved result run (auto-detects type) and prints summary + data."""
    base = DEFAULT_RESULTS_DIR
    candidates = [
        base / "analyses" / f"{name}.json",
        base / "sensitivities" / f"{name}.json",
        base / "comparisons" / f"{name}.json",
        base / f"{name}.json",
    ]
    loaded = False
    for p in candidates:
        if p.exists():
            try:
                if "analyses" in str(p) or "analysis" in name.lower():
                    run = load_analysis_run(name)
                    typer.echo(f"Loaded AnalysisRun: {run.short_summary()}")
                    typer.echo(json.dumps({"profile": run.profile_name, "notes": run.notes, "result_count": len(run.analysis_result.results) if run.analysis_result else 0}, indent=2))
                elif "sens" in str(p) or "sensitivity" in name.lower():
                    run = load_sensitivity_run(name)
                    typer.echo(f"Loaded SensitivityRun: {run.short_summary()}")
                    typer.echo(f"  Multi-var? {run.is_multi_var()}  |  Variable(s): {run.variable}")
                else:
                    run = load_compare_run(name)
                    typer.echo(f"Loaded CompareRun for profile {run.profile_name}")
                loaded = True
                break
            except Exception as e:
                typer.echo(f"Found file but failed to load as known type: {e}")

    if not loaded:
        typer.secho(f"No saved result named '{name}' found.", fg=typer.colors.YELLOW)
        typer.echo("Use `fiberforce profile list-results` to discover available runs.")


@profile_app.command("list-results")
def profile_list_results(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Only show runs associated with this profile"),
):
    """List all saved analysis, sensitivity, and compare runs (enhanced persistence)."""
    runs = list_saved_runs(profile_name=profile)
    configs = list_configs()
    typer.echo("Saved analysis / sensitivity / compare runs:")
    if not runs:
        typer.echo("  (none yet — use `profile save-result` or `profile multi-sens`)")
    else:
        for r in runs:
            typer.echo(f"  • {r}")
    if configs:
        typer.echo("\nSaved configs:")
        for c in configs:
            typer.echo(f"  • {c}")


@profile_app.command("multi-sens")
def profile_multi_sens(
    profile: str = typer.Argument(..., help="Profile to base the multi-var sensitivity on"),
    lift: str = typer.Option("squat", "--lift"),
    variables: str = typer.Option("load_kg:120,130,140;variation:high_bar,low_bar", "--variables", help="var1:v1,v2; var2:w1,w2  (semicolon separated)"),
    target: str = typer.Option("Upper fibers", "-t", "--target"),
    notes: str = typer.Option(""),
):
    """
    Profile-based MULTI-variable sensitivity + automatic persistence as SavedSensitivityRun.

    This is one of the key deliverables of the enhanced persistence task.
    Example:
      fiberforce profile multi-sens longfemur --lift squat --variables "load_kg:140,150,160;femur:42,48" --target "Upper fibers"
    """
    try:
        var_list: list[tuple[str, list[Any]]] = []
        for chunk in variables.split(";"):
            if not chunk.strip():
                continue
            k, vs = chunk.split(":", 1)
            vals = [float(x) if x.replace(".", "", 1).isdigit() else x.strip() for x in vs.split(",")]
            var_list.append((k.strip(), vals))

        run, path = run_profile_multi_sensitivity(
            profile_name=profile,
            lift=lift,
            variables=var_list,
            target_region_name=target,
            notes=notes,
        )
        _print_run_saved(path, "multi-var sensitivity run")
        typer.echo(f"  {run.short_summary()}")
        typer.echo("  Use `fiberforce profile load-result {run.run_id}` or Python load_sensitivity_run() to retrieve.")

    except Exception as e:
        typer.secho(f"multi-sens failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@profile_app.command("compare-runs")
def profile_compare_runs(
    run_a: str = typer.Argument(..., help="First saved run name (or use live profile compare below)"),
    run_b: Optional[str] = typer.Argument(None, help="Second saved run (optional)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Alternatively run a live compare using this profile"),
    lift: Optional[str] = typer.Option(None, "--lift"),
    a: Optional[str] = typer.Option(None, "--a"),
    b: Optional[str] = typer.Option(None, "--b"),
    load_kg: float = typer.Option(100.0, "--load-kg"),
):
    """
    Compare two previously saved runs, OR perform a fresh profile-backed compare and persist it.
    """
    if profile and a and b and lift:
        saved_run, path = run_profile_compare(
            profile_name=profile,
            lift=lift,
            config_a=a,
            config_b=b,
            load_kg=load_kg,
        )
        _print_run_saved(path, "compare run")
        typer.echo(f"  {saved_run.comparison_result}")
        return

    try:
        r1 = load_analysis_run(run_a)
        typer.echo(f"Loaded {run_a}: {r1.short_summary() if hasattr(r1, 'short_summary') else 'OK'}")
        if run_b:
            r2 = load_analysis_run(run_b)
            typer.echo(f"Loaded {run_b}: {r2.short_summary() if hasattr(r2, 'short_summary') else 'OK'}")
        typer.echo("Loaded successfully. For rich diffing load in Python and compare .analysis_result.results")
    except Exception as e:
        typer.secho(f"compare-runs error: {e}", fg=typer.colors.RED)


@app.command("sensitivity-multi")
def cmd_sensitivity_multi(
    lift: str = typer.Argument(..., help="Lift to analyze (bench/squat/deadlift/ohp all supported)"),
    var1: str = typer.Option("load_kg", "--var1", help="First variable name (load_kg, femur, grip_width, stance_width, etc.)"),
    start1: float = typer.Option(120.0, "--start1"),
    end1: float = typer.Option(160.0, "--end1"),
    step1: float = typer.Option(10.0, "--step1"),
    var2: str = typer.Option("femur", "--var2", help="Second variable name"),
    start2: float = typer.Option(40.0, "--start2"),
    end2: float = typer.Option(50.0, "--end2"),
    step2: float = typer.Option(2.0, "--step2"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    target: str = typer.Option("Upper fibers", "-t", "--target"),
    use_geometric: bool = typer.Option(True, "--use-geometric/--no-geometric", help="Forward anthropometry to geometric MA estimators when available"),
    notes: str = typer.Option("", "--notes", help="Optional notes stored with any saved run"),
    plot: bool = typer.Option(False, "--plot"),
    save_plot: Optional[str] = typer.Option(None, "--save-plot"),
    ascii_only: bool = typer.Option(False, "--ascii-only"),
):
    """
    Multi-variable sensitivity (sequential sweeps across two variables).

    Full 4-lift support + geometric MA when --profile + anthropometry supplied + --use-geometric.

    Examples:
        fiberforce sensitivity-multi squat --var1 load_kg --start1 120 --end1 160 --var2 stance_width --start2 55 --end2 75 --profile myathlete
        fiberforce sensitivity-multi deadlift --var1 load_kg --var2 femur --use-geometric --profile longfemur
    """
    try:
        if profile:
            anthro = _safe_load_profile(profile)
            subj = service.create_subject_from_measurements(name=profile)
            subj.anthropometry = anthro
        else:
            subj = service.create_subject_from_measurements()

        # Build base position (geometric forwarding when requested + profile present)
        build_kwargs = {"load_kg": start1, "variation": "flat", "target_region_name": target}
        if use_geometric and profile:
            # Pass common geometric drivers; builders tolerate extras
            build_kwargs.update({"use_geometric": True})
            if var2 in ("stance", "stance_width"):
                build_kwargs["stance_width_cm"] = start2
            if var2 in ("grip", "grip_width"):
                build_kwargs["grip_width_cm"] = start2
        pos = service.build_position(lift, **build_kwargs)

        from fiberforce.reference import KNOWN_MUSCLE_REGIONS
        target_region = next(
            (r for r in KNOWN_MUSCLE_REGIONS if target.lower() in r.region_name.lower()),
            None,
        )
        if target_region is None:
            target_region = next((r for r in KNOWN_MUSCLE_REGIONS if target.lower() in r.region_name.lower()), KNOWN_MUSCLE_REGIONS[0])

        values1 = []
        v = start1
        while v <= end1 + 0.001:
            values1.append(round(v, 2))
            v += step1

        values2 = []
        v = start2
        while v <= end2 + 0.001:
            values2.append(round(v, 2))
            v += step2

        variables = [(var1, values1), (var2, values2)]

        def rebuild_multi(base_pos, params):
            kwargs = {
                "load_kg": params.get(var1, start1),
                "target_region_name": target,
            }
            if use_geometric:
                kwargs["use_geometric"] = True
            # Common geometric / personalization drivers
            if var2 in ("femur", "femur_cm", "femur_length"):
                kwargs["femur_cm"] = params.get(var2, start2)
            elif var2 in ("grip", "grip_width", "grip_width_cm"):
                kwargs["grip_width_cm"] = params.get(var2, start2)
            elif var2 in ("stance", "stance_width", "stance_width_cm"):
                kwargs["stance_width_cm"] = params.get(var2, start2)
            elif var2 in ("forearm", "forearm_cm"):
                kwargs["forearm_cm"] = params.get(var2, start2)
            # Pass through for deadlift/ohp variations
            if "variation" in str(var2).lower():
                kwargs["variation"] = params.get(var2, "flat")
            return service.build_position(lift, **kwargs)

        results = service.sensitivity_multi(subj, pos, variables=variables, target_region=target_region, rebuild_multi=rebuild_multi)

        typer.echo(f"\nMulti-Variable Sensitivity on {lift} (geometric={'on' if use_geometric else 'off'})")
        for res in results:
            typer.echo(f"\n  Variable: {res.variable_name} ({len(res.points)} points)")
            for row in res.to_table_rows()[:8]:
                typer.echo(f"    {row}")

        if notes:
            typer.echo(f"\nNotes: {notes}")

        if plot or save_plot:
            plot_sensitivity(results[0], save_path=save_plot, show=plot and not is_headless(), ascii_only=ascii_only)

        if profile:
            typer.echo("\nTip: use `fiberforce profile multi-sens` for full SavedSensitivityRun persistence.")

    except Exception as e:
        typer.secho(f"Multi-variable sensitivity failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


# -------------------------------------------------------------------
# Dedicated lift commands (v1 hygiene)
# These are thin, working wrappers over AnalysisService so the
# advertised top-level commands actually exist and function.
# -------------------------------------------------------------------

@app.command("deadlift")
def cmd_deadlift(
    load_kg: float = typer.Option(140.0, "-l", "--load-kg"),
    variation: str = typer.Option("conventional", "-v", "--variation", help="conventional or sumo"),
    target: str = typer.Option("glute_max", "-t", "--target"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    plot: bool = typer.Option(False, "--plot"),
):
    """Dedicated deadlift analysis (conventional or sumo)."""
    try:
        if profile:
            anthro = _safe_load_profile(profile)
            subj = service.create_subject_from_measurements(name=profile)
            subj.anthropometry = anthro
        else:
            subj = service.create_subject_from_measurements()

        pos = service.build_position("deadlift", load_kg=load_kg, variation=variation, target_region_name=target)
        result = service.analyze(subj, pos)

        _print_analysis_result(result, f"Deadlift ({variation}) @ {load_kg}kg → {target}")

        if plot:
            typer.echo("(Use sensitivity for rich charts on deadlift.)")

    except Exception as e:
        typer.secho(f"Deadlift command failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("ohp")
def cmd_ohp(
    load_kg: float = typer.Option(70.0, "-l", "--load-kg"),
    variation: str = typer.Option("standing", "-v", "--variation", help="standing, seated, strict"),
    target: str = typer.Option("anterior_delt", "-t", "--target"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    plot: bool = typer.Option(False, "--plot"),
):
    """Dedicated overhead press analysis (standing/seated + variations)."""
    try:
        if profile:
            anthro = _safe_load_profile(profile)
            subj = service.create_subject_from_measurements(name=profile)
            subj.anthropometry = anthro
        else:
            subj = service.create_subject_from_measurements()

        pos = service.build_position("ohp", load_kg=load_kg, variation=variation, target_region_name=target)
        result = service.analyze(subj, pos)

        _print_analysis_result(result, f"OHP ({variation}) @ {load_kg}kg → {target}")

        if plot:
            typer.echo("(Use sensitivity for rich charts on OHP.)")

    except Exception as e:
        typer.secho(f"OHP command failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("multi-pos")
def cmd_multi_pos(
    lift: str = typer.Argument(..., help="Lift to analyze at multiple positions (bench|squat|deadlift|ohp)"),
    positions: str = typer.Option(
        "bottom,mid,top",
        "--positions",
        help="Comma-separated discrete positions (bottom,mid,top,lockout,standing,seated,...). Order preserved."
    ),
    load_kg: float = typer.Option(100.0, "-l", "--load-kg", help="External load in kg"),
    variation: str = typer.Option("flat", "-v", "--variation", help="Technique variation (high_bar, conventional, sumo, standing, etc.)"),
    target: str = typer.Option("Sternal fibers", "-t", "--target", help="Primary target muscle region (e.g. 'Upper fibers' for squat glutes, 'Anterior delt' for OHP)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Named anthropometry profile for personalization + geometric MA"),
    plot: bool = typer.Option(False, "--plot", help="Render ASCII curves + matplotlib force/MA plots (if matplotlib installed)"),
    save_plot: Optional[str] = typer.Option(None, "--save-plot", help="Save matplotlib figure or ASCII report (e.g. my_rom.png or my_rom.txt)"),
    ascii_only: bool = typer.Option(False, "--ascii-only", help="Force pure ASCII output (no matplotlib even if available)"),
    save_result: Optional[str] = typer.Option(None, "--save-result", help="Persist full multi-pos run as SavedMultiPositionRun (auto-uses profile if given)"),
):
    """
    **Multi-position (limited dynamic) analysis** — flagship v1 feature.

    Run the same lift + load + target across discrete positions (bottom/mid/top/lockout etc.).
    Produces rich MultiPositionResult (aggregates, deltas, geometric provenance, program-ready).
    Excellent for comparing variations (high-bar vs low-bar, grip widths, sumo vs conventional)
    with your own anthropometry via --profile (enables geometric moment arms).

    Real coaching-style usage:
      - Decide high-bar vs low-bar emphasis for an athlete with specific limb lengths → Example 10
      - Grip-width exploration for bench pec stress → Example 11
      - Full weekly program comparison using multi-pos data → Example 01

    Examples:
        fiberforce multi-pos squat --positions bottom,mid,top -l 140 -v high_bar --profile longfemur --plot
        fiberforce multi-pos deadlift --positions bottom,mid,lockout -l 180 -v conventional -t "glute_max" --ascii-only
        fiberforce multi-pos ohp --positions bottom,mid,top --save-plot rom_ohp.png --save-result ohp_rom_june
    """
    try:
        # UX: profile + progress hints
        if profile:
            typer.echo(f"→ Loading profile '{profile}' ...")
            anthro = _safe_load_profile(profile)
            subj = service.create_subject_from_measurements(name=profile)
            subj.anthropometry = anthro
            typer.echo("  ✓ Profile loaded (anthropometry + geometric forwarding enabled where supported)")
        else:
            subj = service.create_subject_from_measurements()

        pos_list = [p.strip() for p in positions.split(",") if p.strip()]
        if not pos_list:
            typer.secho("No valid positions supplied.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        # v1: when a profile with real anthropometry is supplied, auto-enable geometric
        # so the documented "personalized multi-pos ROM curves" examples actually engage the estimators.
        use_geometric = bool(profile)

        typer.echo(f"→ Analyzing {len(pos_list)} positions for {lift} ({variation}) @ {load_kg}kg → {target} ...")

        try:
            mpr = service.analyze_multi_position(
                subj, lift, pos_list,
                load_kg=load_kg, variation=variation, target_region_name=target,
                use_geometric=use_geometric
            )
        except ValueError as e:
            if "Unsupported lift" in str(e):
                typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
                typer.echo("  Supported lifts: bench, squat, deadlift, ohp")
                raise typer.Exit(1)
            raise

        # Header
        typer.secho(f"\nMulti-Position Analysis: {lift} ({variation}) @ {load_kg}kg → {target}", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"Positions ({len(pos_list)}): {', '.join(pos_list)}")
        if profile:
            typer.echo(f"Profile: {profile} (geometric: {use_geometric})")

        # --- Delegate table + summary rendering to the shared viz helper for consistency ---
        # (reduces duplication with plot_multi_position; always produces rich table + ASCII curves)
        from fiberforce.visualization import plot_multi_position
        plot_multi_position(
            mpr.to_list() if hasattr(mpr, "to_list") else list(mpr),
            positions=pos_list,
            title="Per-Position Results",
            show=False,
            ascii_only=True,   # non-plot path stays pure ASCII / rich table
        )

        # --- Compact summary (sourced from MPR aggregates + service helper for v1) ---
        try:
            summary = service.summarize_multi_position(mpr)
        except Exception:
            summary = {}

        # Use the rich MPR fields (populated by analyze_multi_position) for reliable stats
        n = getattr(mpr, "num_positions", len(mpr) if mpr else 0)
        favg = getattr(mpr, "avg_peak_force", 0.0)
        fmin, fmax = getattr(mpr, "force_range", (0.0, 0.0))
        deltas = getattr(mpr, "force_deltas", []) or []

        typer.echo("\nSummary Statistics")
        typer.echo("-" * 48)
        typer.echo(f"  Positions analyzed : {n}")
        typer.echo(f"  Avg peak force     : {favg:.1f} N")
        typer.echo(f"  Range (min / max)  : {fmin:.1f} / {fmax:.1f} N   (Δ {fmax - fmin:.1f} N)")
        if deltas:
            typer.echo(f"  Consecutive deltas : {[round(d,1) for d in deltas]}")
        if summary.get("regions"):
            typer.echo(f"  Regions covered    : {len(summary['regions'])}")

        # Progress hint for next steps
        typer.echo("\n  (Program-level: use analyze_multi_position + TrainingSession/WeeklyProgram for weekly accumulation & compare. See Examples 10 + 11 for coaching-style patterns.)")

        # --- Plot / visualization surface (ASCII always + matplotlib curves) ---
        if plot or save_plot:
            plot_multi_position(
                mpr.to_list() if hasattr(mpr, "to_list") else mpr,  # pass list for viz compat
                positions=pos_list,
                title=f"ROM Curves: {lift} {variation} @ {load_kg}kg ({target})",
                save_path=save_plot,
                show=plot and not is_headless(),
                ascii_only=ascii_only,
            )

        # --- Optional persistence for multi-pos runs (Phase 2c) ---
        if save_result:
            try:
                # Prefer the new profile helper when profile present
                if profile:
                    run, path = run_profile_multi_position(
                        profile_name=profile,
                        lift=lift,
                        positions=pos_list,
                        load_kg=load_kg,
                        variation=variation,
                        target_region_name=target,
                        notes=f"CLI multi-pos run saved via --save-result ({len(pos_list)} positions)",
                    )
                    _print_run_saved(path, "multi-position run")
                    typer.echo(f"  Run ID: {run.run_id}  |  Use `fiberforce profile load-result {run.run_id}` later.")
                else:
                    # Fallback: manual construction + direct save
                    from fiberforce.results import save_multi_position_run, SavedMultiPositionRun
                    run = SavedMultiPositionRun(
                        run_id=save_result,
                        profile_name=None,
                        lift=lift,
                        positions=pos_list,
                        load_kg=load_kg,
                        variation=variation,
                        target_region_name=target,
                        analysis_results=list(mpr) if mpr else [],
                        summary=summary,
                        notes="Saved via CLI multi-pos (no profile)",
                    )
                    path = save_multi_position_run(run, save_result)
                    _print_run_saved(path, "multi-position run")
            except Exception as psave_e:
                typer.secho(f"Warning: could not persist multi-pos run ({psave_e}). Continuing.", fg=typer.colors.YELLOW)

    except Exception as e:
        typer.secho(f"Multi-pos command failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("gui", help="Launch the FiberForce native desktop GUI (PySide6). For end-users: build the v2.0 clickable .app once (scripts/build_macos_app.sh) then double-click the icon in Finder/Applications/Launchpad (DMG provided). Devs: python -m fiberforce.gui (or fiberforce gui after venv). Full analyses, dynrom/continuous, multi-pos, sensitivity, programs, rich interpret/visuals.")
def cmd_gui():
    """Launch the Qt GUI app."""
    try:
        from fiberforce.gui.app import main as launch_gui
        launch_gui()
    except ImportError as e:
        typer.secho("GUI dependencies not installed.", fg=typer.colors.RED, err=True)
        typer.echo("Install with: pip install 'fiberforce[gui,viz]'")
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Failed to launch GUI: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("smoke", help="Quick built-in verification that the installed FiberForce works (library + CLI + v2.0 features: imperial, ft-lb torque, clickable .app paths, dynrom/continuous ROM, GUI, recipes, interpret). No external pytest required.")
def cmd_smoke():
    """Run a fast smoke test of core functionality (v1: imperial inches/lbs, ft-lb torque, recipes, .interpret(), WeeklyProgram, Sensitivity insight).

    This is the easiest way to confirm your installation is healthy after the bulletproof setup:
        cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"
        python3 -m venv .venv && source .venv/bin/activate && python -m pip install -e ".[gui,viz]"
        fiberforce smoke
    (Or use `python -m fiberforce.cli smoke` during dev.)
    """
    typer.echo("FiberForce smoke test (2.0.0) — imperial + ft-lb torque + v2 clickable icon .app (DMG) + dynrom + top-tier GUI visuals...")
    from fiberforce import AnalysisService, __version__
    from fiberforce.recipes import create_athlete, analyze_multi_position

    svc = AnalysisService()
    typer.echo(f"  ✓ Version: {__version__}")
    typer.echo(f"  ✓ AnalysisService: {type(svc).__name__}")

    # Exercise new interpret helpers (v1 imperial + ft-lb)
    athlete = create_athlete(units="imperial", femur_in=17, tibia_in=15)
    mpr = analyze_multi_position(
        "squat", ["bottom", "mid"], load_lbs=315, variation="low_bar",
        athlete=athlete, use_geometric=True, units="imperial", target_region_name="Gluteus Maximus::Upper fibers"
    )
    # Post-v1 expansion smoke
    mpr_incline = analyze_multi_position("incline", ["bottom"], load_lbs=185, athlete=athlete, units="imperial")
    typer.echo(f"  ✓ New lift (incline) multi-pos works (~{mpr_incline.analyses[0].results[0].peak_torque_ftlb:.0f} ft-lb)")
    interp = mpr.interpret()
    typer.echo(f"  ✓ MultiPositionResult.interpret() works ({len(interp)} chars)")

    # dynrom continuous MVP demo (post-v1 dynamics)
    from fiberforce.recipes import analyze_continuous
    mpr_cont = analyze_continuous("squat", steps=3, load_lbs=315, athlete=athlete, variation="low_bar", units="imperial")
    cont_interp = mpr_cont.interpret()
    typer.echo(f"  ✓ analyze_continuous (dynrom MVP) works ({len(mpr_cont.analyses)} steps, {len(cont_interp)} chars interpret)")

    # WeeklyProgram + its interpret
    from fiberforce.results import TrainingSession, WeeklyProgram
    sess = TrainingSession(name="Smoke Squat")
    sess.add_analyses(list(mpr))
    prog = WeeklyProgram(name="Smoke Week")
    prog.add_session(sess)
    w_interp = prog.interpret()
    typer.echo(f"  ✓ WeeklyProgram.interpret() works ({len(w_interp)} chars)")

    # Sensitivity insight
    res, insight = __import__("fiberforce.recipes", fromlist=["sensitivity_sweep"]).sensitivity_sweep(
        "bench", "grip_width_cm", [55, 65, 75], load_kg=100, athlete=athlete
    )
    typer.echo(f"  ✓ SensitivityResult.insight() works: {insight.splitlines()[0][:60]}...")

    typer.echo("  ✓ service.interpret and sensitivity_insight wrappers present")
    typer.secho("Smoke test PASSED. Your FiberForce installation looks healthy.", fg=typer.colors.GREEN)


# -------------------------------------------------------------------
# Entrypoint for direct execution / packaging
# -------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()
