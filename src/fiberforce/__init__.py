"""FiberForce - Personalized biomechanical modeling for advanced resistance training.

v2.0 (The Clickable Icon App):
- Primary GUI experience: double-click the FiberForce icon (build via scripts/build_macos_app.sh produces DMG + self-contained .app with custom .icns; drag to /Applications).
- AnalysisService + recipes as primary (analyze, analyze_continuous/dynrom, multi-pos, sensitivity, interpret/insight, programs)
- Imperial-first default (inches/ft/lbs + ft-lb torque via from_inches, load_lbs, peak_torque_ftlb)
- Full native GUI (icon-click .app primary for end users; fiberforce gui / python -m fiberforce.gui for dev): all features + 9 generated visuals, real persisted History, "Run Internal Smoke", dark Mac QSS, continuous ROM curves with live plot.
- Packaging: briefcase + polished build script (create/build/package, .icns generation, ad-hoc sign, DMG). Real bundle artifacts.
- Persistence, visualization, 8-lift (incl. Incline/RDL/Front/Sumo), dynrom MVP, geometric prototype, 170+ tests, 12 examples, bulletproof launch docs (volume + venv).

All core is in src/fiberforce/. See docs/, examples/, GAMEPLANS (v2 section), NEXT_LEVEL_ROADMAP, and AGENT_FEEDBACK for the journey.
"""

__version__ = "2.0.0"

from . import models
from . import calculations
from . import examples
from . import reference
from . import analysis
from . import visualization
from . import profiles
from . import results
from . import recipes
from .recipes import analyze_continuous  # dynrom continuous at top level
from .analysis.service import (
    AnalysisService,
    AnalysisResult,
    MultiPositionResult,
    service as default_service,
)

# Re-export key visualization symbols at top level for convenience
from .visualization import (
    plot_sensitivity,
    plot_comparison,
    visualize,
    ascii_sparkline,
    ascii_bars,
    ComparisonResult,
    is_headless,
    MATPLOTLIB_AVAILABLE,
    RICH_AVAILABLE,
)

# Re-export the most important persistence + program symbols
from .profiles import (
    save_anthropometry,
    load_anthropometry,
    list_profiles,
    get_or_create_default_profile,
    # Saved run persistence
    SavedAnalysisRun,
    SavedSensitivityRun,
    SavedCompareRun,
    SavedMultiPositionRun,
    run_profile_multi_sensitivity,
    run_profile_compare,
    # Program-level models (0.5+)
    TrainingSession,
    WeeklyProgram,
)

# v1 public API polish: first-class access to key usability features
# .interpret() / .insight() on rich result objects (call on instances or via service.interpret / service.sensitivity_insight)
# Imperial units via UserAnthropometry.from_inches(...) and ExternalLoad.from_lbs(...)
# recipes module for common high-level flows (default imperial)

__all__ = [
    "__version__",
    "models",
    "calculations",
    "examples",
    "reference",
    "analysis",
    "visualization",
    "profiles",
    "results",
    "recipes",
    "analyze_continuous",  # dynrom MVP continuous ROM
    "AnalysisService",
    "AnalysisResult",
    "MultiPositionResult",
    "default_service",
    "plot_sensitivity",
    "plot_comparison",
    "visualize",
    "ascii_sparkline",
    "ascii_bars",
    "ComparisonResult",
    "is_headless",
    "MATPLOTLIB_AVAILABLE",
    "RICH_AVAILABLE",
    "save_anthropometry",
    "load_anthropometry",
    "list_profiles",
    "get_or_create_default_profile",
    "SavedAnalysisRun",
    "SavedSensitivityRun",
    "SavedCompareRun",
    "SavedMultiPositionRun",
    "run_profile_multi_sensitivity",
    "run_profile_compare",
    "TrainingSession",
    "WeeklyProgram",
]
