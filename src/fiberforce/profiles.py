"""
Simple user profile persistence (JSON) for FiberForce (massive phase).

Allows saving/loading of UserAnthropometry + named configurations.
This makes the tool feel persistent and personal — a key step toward v0.2 "real tool" feel.

Current scope: Basic JSON save/load in user config dir or explicit path.
Enhanced (this version): Full integration with the new results persistence layer.
Users can now save full LiftConfiguration + AnalysisResult / SensitivityResult runs
directly associated with their anthropometry profiles.

See fiberforce.results for the powerful Saved*Run classes and
profile-based multi-var / compare helpers.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fiberforce.models import UserAnthropometry

# Re-export the powerful new results layer so users can `from fiberforce.profiles import ...`
# and get both anthro profiles + result persistence in one import.
# The following are intentional re-exports so users can do:
#   from fiberforce.profiles import SavedMultiPositionRun, run_profile_..., etc.
# ruff: noqa: F401
from fiberforce.results import (
    SavedAnalysisRun,
    SavedSensitivityRun,
    SavedCompareRun,
    SavedMultiPositionRun,
    save_analysis_run,
    load_analysis_run,
    save_sensitivity_run,
    load_sensitivity_run,
    save_compare_run,
    load_compare_run,
    save_multi_position_run,
    load_multi_position_run,
    save_lift_config,
    load_lift_config,
    list_saved_runs,
    list_configs,
    run_profile_analysis,
    run_profile_multi_sensitivity,
    run_profile_compare,
    run_profile_multi_position,
    DEFAULT_RESULTS_DIR,
    PersistenceError,
    ProfileNotFoundError,
    CorruptResultError,
    TrainingSession,
    WeeklyProgram,
)


DEFAULT_PROFILE_DIR = Path.home() / ".fiberforce" / "profiles"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_anthropometry(
    anthro: UserAnthropometry,
    name: str,
    profile_dir: Optional[Path] = None,
) -> Path:
    """Save a UserAnthropometry object as JSON."""
    profile_dir = profile_dir or DEFAULT_PROFILE_DIR
    _ensure_dir(profile_dir)
    file_path = profile_dir / f"{name}.json"
    data = asdict(anthro)
    file_path.write_text(json.dumps(data, indent=2))
    return file_path


def load_anthropometry(
    name: str,
    profile_dir: Optional[Path] = None,
) -> UserAnthropometry:
    """Load a UserAnthropometry from JSON."""
    profile_dir = profile_dir or DEFAULT_PROFILE_DIR
    file_path = profile_dir / f"{name}.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Profile '{name}' not found at {file_path}")
    try:
        data = json.loads(file_path.read_text())
    except json.JSONDecodeError as e:
        raise CorruptResultError(f"Corrupt profile JSON for '{name}': {e}") from e
    return UserAnthropometry(**data)


def list_profiles(profile_dir: Optional[Path] = None) -> list[str]:
    """List available profile names."""
    profile_dir = profile_dir or DEFAULT_PROFILE_DIR
    if not profile_dir.exists():
        return []
    return [p.stem for p in profile_dir.glob("*.json")]


# Convenience functions for CLI / service integration
def get_or_create_default_profile(name: str = "default") -> UserAnthropometry:
    """Load default profile or create a reasonable synthetic one."""
    try:
        return load_anthropometry(name)
    except (FileNotFoundError, json.JSONDecodeError, CorruptResultError):
        anthro = UserAnthropometry(
            name="Default User",
            humerus_length_cm=32.0,
            forearm_length_cm=25.5,
            biacromial_width_cm=38.0,
            femur_length_cm=42.0,
            tibia_length_cm=38.0,
        )
        save_anthropometry(anthro, name)
        return anthro


# -------------------------------------------------------------------
# New profile + results integration helpers (enhanced persistence)
# -------------------------------------------------------------------

def save_profile_with_run(
    anthro: UserAnthropometry,
    profile_name: str,
    analysis_run: Optional[SavedAnalysisRun] = None,
    sensitivity_run: Optional[SavedSensitivityRun] = None,
    profile_dir: Optional[Path] = None,
    results_dir: Optional[Path] = None,
) -> tuple[Path, Optional[Path], Optional[Path]]:
    """
    Save anthropometry profile + optionally attach full analysis/sensitivity results.
    Returns (profile_path, analysis_path_or_None, sensitivity_path_or_None).
    This is the "one call does everything" persistence API.
    """
    p_path = save_anthropometry(anthro, profile_name, profile_dir)

    a_path = None
    if analysis_run:
        if not analysis_run.profile_name:
            analysis_run.profile_name = profile_name
        a_path = save_analysis_run(analysis_run, analysis_run.run_id or profile_name, results_dir)

    s_path = None
    if sensitivity_run:
        if not sensitivity_run.profile_name:
            sensitivity_run.profile_name = profile_name
        s_path = save_sensitivity_run(sensitivity_run, sensitivity_run.run_id or f"{profile_name}_sens", results_dir)

    return p_path, a_path, s_path


def list_all_for_profile(
    profile_name: str,
    profile_dir: Optional[Path] = None,
    results_dir: Optional[Path] = None,
) -> dict[str, list[str]]:
    """
    Discover everything stored for a given profile:
    - its anthropometry profile
    - all associated analysis runs, sensitivity runs, configs, etc.
    """
    profile_dir = profile_dir or DEFAULT_PROFILE_DIR
    has_profile = (profile_dir / f"{profile_name}.json").exists()

    runs = list_saved_runs(results_dir=results_dir, profile_name=profile_name)

    return {
        "profile_exists": has_profile,
        "associated_runs": runs,
        "configs": list_configs(results_dir),
    }


# Note: migrate_old_profile_if_needed was removed in the v0.5 cleanup pass.
# It was a no-op placeholder. If schema migration is ever needed in the future,
# it can be re-introduced with real logic.
