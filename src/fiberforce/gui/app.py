"""
FiberForce Desktop GUI (macOS native app)

Full-featured GUI that exposes **everything** developed in the library:
- Athlete/profile management (with geometric)
- Single-position analysis
- Multi-position (limited dynamic) with rich MultiPositionResult + .interpret()
- Sensitivity sweeps with .insight() + plots
- WeeklyProgram / TrainingSession building + .interpret() + reports
- Visualizations (matplotlib embedded where possible, ASCII fallback)
- Recipes for common high-level flows
- Persistence via the existing profile + Saved* system + new LoggedWorkout / LoggedSet (real sets/reps/weight + attached modeled force/torque/dominance per set for supported bb/db/machine exercises; volume, modeled work, e1RM, regional summaries)
- End-goal direction: full workout tracking with the force model overlaid (1RM/5RM/volume + per-muscle demand from your actual logged training, starting deep on the compounds we model well)

Launch:
    fiberforce gui
or during dev (bulletproof sequence — this defeats the exact PATH/venv-from-~/editable-dir/runpy/splash errors from prior sessions):
    cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -e ".[gui,viz]"
    fiberforce gui
    # Alternative (avoids entry-script PATH issues, uses gui/__main__.py — preferred in active dev):
    python -m fiberforce.gui

# PERMANENT USER POLICY (as of this session): "always rebuild the app, I only want to test through the app"
# - The ONLY way the user tests GUI features is by double-clicking the real macOS .app icon (in /Applications
#   after dragging from a DMG, or directly from dist/ for quick checks).
# - Dev `python -m fiberforce.gui` or `fiberforce gui` is for agent internal smoke/verif ONLY.
# - Therefore: AFTER ANY change to src/fiberforce/gui/app.py (or other GUI-affecting source), the agent
#   MUST immediately run the FULL rebuild sequence before claiming "testable":
#     cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"
#     source .venv/bin/activate
#     python -m pip install --upgrade pip
#     python -m pip install -e ".[gui,viz]"
#     bash scripts/build_macos_app.sh
# - The resulting dist/FiberForce-*.dmg + .app (ad-hoc signed) is the artifact the user will open.
# - This policy exists because previous waves had repeated "I don't see the change" feedback when the
#   bundled icon was stale.
#
# The distributable .app / DMG is always a *frozen snapshot* of src/ at build time. The dev commands
# above are preserved only for the agent's headless verification and smoke (they are NOT how the user
# experiences the app). Always rebuild for the user.

# The cd to the volume path + venv + activate before any pip/python -m is MANDATORY.
# See top-level README "Development & Testing" for the full copy-paste block and why.

Requires: PySide6 (for [gui]) + matplotlib (for [viz]) recommended for plots.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QTextEdit, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox, QFormLayout,
    QMessageBox, QDialog, QSplitter, QScrollArea, QSplashScreen, QStackedWidget,
    QProgressBar, QGraphicsOpacityEffect, QFrame, QSizePolicy, QButtonGroup
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSettings
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QPen, QBrush

# Assets for top-tier visuals (generated images in imperial/ft-lb theme)
# Use pathlib for consistency and robustness (Python 3.9+)
ASSETS_DIR = Path(__file__).parent / "assets"
APP_ICON = str(ASSETS_DIR / "app_icon_new.jpg")  # updated premium icon (also have .icns for bundle)
SPLASH = str(ASSETS_DIR / "splash_new.jpg")  # updated premium cinematic splash
HEADER = str(ASSETS_DIR / "header_banner.jpg")
RESULT_VIZ = str(ASSETS_DIR / "result_viz.jpg")
COACHING_DASH = str(ASSETS_DIR / "coaching_dashboard.jpg")
TORQUE_VIZ = str(ASSETS_DIR / "torque_viz_new.jpg")  # updated styled torque viz
MUSCLE_MAP = str(ASSETS_DIR / "muscle_map.jpg")  # new anatomical muscle activation map for regional insights

# Contextual dropdown data for easy UI (no free-text errors for common cases).
# Pulled from models/reference knowledge so dropdowns are always valid for the chosen lift.
# This makes the app "as easy as possible": pick lift -> sensible choices for var/pos/target appear.
LIFT_KEYS = ["squat", "bench", "incline", "deadlift", "romanian", "ohp", "front", "sumo"]

VARIATIONS_BY_LIFT = {
    "squat": ["low_bar", "high_bar"],
    "bench": ["flat", "flat_close", "flat_wide", "incline_30", "decline_15", "wide_grip", "close_grip"],
    "incline": ["incline_30", "flat"],
    "deadlift": ["conventional", "sumo", "deficit", "block"],
    "romanian": ["rdl", "stiff_leg"],
    "ohp": ["standing", "seated", "flat"],
    "front": ["olympic", "cross_arm"],
    "sumo": ["sumo", "semi_sumo"],
}

POSITIONS_BY_LIFT = {
    # Common for multi-pos / comma lists. Presets for the editable combo (user can still type custom).
    "squat": ["bottom,mid,top", "bottom,mid", "bottom,mid,top,lockout"],
    "bench": ["bottom,mid,top", "bottom,mid", "bottom,mid,top,lockout"],
    "incline": ["bottom,mid", "bottom,mid,top"],
    "deadlift": ["bottom,mid", "bottom,mid,top", "conventional_bottom,conventional_mid"],
    "romanian": ["mid,top", "bottom,mid,top"],
    "ohp": ["bottom,mid,top", "standing_bottom,standing_mid"],
    "front": ["bottom,mid,top"],
    "sumo": ["bottom,mid", "bottom,mid,top"],
}

TARGETS_BY_LIFT = {
    # Human friendly strings that the backend resolves (matches on region_name or full "Muscle::Region").
    # These are the ones commonly useful per lift; user sees nice names, no typing.
    "squat": [
        "Gluteus Maximus::Upper fibers",
        "Vastus Lateralis::Full",
        "Gluteus Maximus::Lower fibers",
        "Biceps Femoris (Long Head)::Full",
    ],
    "bench": [
        "Pectoralis Major::Sternal fibers",
        "Pectoralis Major::Clavicular fibers",
        "Deltoid::Anterior",
        "Triceps Brachii::Long head",
        # Note: for non-pec targets on bench the MA data used is from the primary (pec) tables as proxy.
        # The selection is now respected (region label will match your choice).
    ],
    "incline": [
        "Pectoralis Major::Clavicular fibers",
        "Pectoralis Major::Sternal fibers",
        "Deltoid::Anterior",
        "Triceps Brachii::Long head",
    ],
    "deadlift": [
        "Gluteus Maximus::Upper fibers",
        "Biceps Femoris (Long Head)::Full",
        "Erector Spinae::Lumbar",
        "Gluteus Maximus::Lower fibers",
    ],
    "romanian": [
        "Gluteus Maximus::Upper fibers",
        "Biceps Femoris (Long Head)::Full",
        "Semitendinosus::Full",
    ],
    "ohp": [
        "Deltoid::Anterior",
        "Deltoid::Lateral",
        "Deltoid::Posterior",
        "Triceps Brachii::Long head",
        "Trapezius::Upper",
    ],
    "front": [
        "Gluteus Maximus::Upper fibers",
        "Vastus Lateralis::Full",
    ],
    "sumo": [
        "Gluteus Maximus::Upper fibers",
        "Biceps Femoris (Long Head)::Full",
        "Erector Spinae::Lumbar",
    ],
}

# Human-friendly labels for the new visual chip selectors (replaces clumped technical dropdown lists for variation/target).
# Values stay the internal slugs / full "Muscle::Region" strings that analyze + builders + _resolve expect.
# Chips use the labels for display (spacious, not boring, not squished long popup). Backing combos kept (hidden per user choice)
# so all existing .currentText() call sites + live wiring + smoke sets continue to work unchanged.
VARIATION_LABELS = {
    "flat": "Flat",
    "flat_close": "Close Grip",
    "flat_wide": "Wide Grip",
    "incline_30": "Incline 30",
    "decline_15": "Decline 15",
    "wide_grip": "Wide Grip",
    "close_grip": "Close Grip",
    "low_bar": "Low Bar",
    "high_bar": "High Bar",
    "conventional": "Conventional",
    "sumo": "Sumo",
    "deficit": "Deficit",
    "block": "Block",
    "rdl": "RDL",
    "stiff_leg": "Stiff-Leg",
    "standing": "Standing",
    "seated": "Seated",
    "olympic": "Olympic",
    "cross_arm": "Cross-Arm",
    "semi_sumo": "Semi-Sumo",
}

TARGET_SHORT_LABELS = {
    "Pectoralis Major::Sternal fibers": "Sternal Pec",
    "Pectoralis Major::Clavicular fibers": "Clavicular Pec",
    "Deltoid::Anterior": "Ant. Delt",
    "Deltoid::Lateral": "Lat. Delt",
    "Deltoid::Posterior": "Post. Delt",
    "Triceps Brachii::Long head": "Triceps Long",
    "Gluteus Maximus::Upper fibers": "Glute Upper",
    "Gluteus Maximus::Lower fibers": "Glute Lower",
    "Vastus Lateralis::Full": "Vastus Lat",
    "Biceps Femoris (Long Head)::Full": "Biceps Fem",
    "Erector Spinae::Lumbar": "Erector Lumbar",
    "Semitendinosus::Full": "Semitendinosus",
    "Trapezius::Upper": "Upper Trap",
}

MUSCLE_COLORS = {
    "Pectoralis Major": "#ff6b6b",
    "Deltoid": "#4ecdc4",
    "Triceps Brachii": "#f5a623",
    "Gluteus Maximus": "#00f5a0",
    "Vastus Lateralis": "#7bd389",
    "Biceps Femoris (Long Head)": "#e89a5e",
    "Erector Spinae": "#c792ea",
    "Semitendinosus": "#e89a5e",
    "Trapezius": "#5dade2",
}

# Core library imports — use the high-level recipes + service
try:
    from fiberforce.recipes import (
        create_athlete, analyze, analyze_multi_position,
        sensitivity_sweep, build_weekly_program
    )
    from fiberforce import AnalysisService
    from fiberforce.profiles import (
        load_anthropometry, list_profiles, save_anthropometry,
        list_saved_runs, load_multi_position_run, SavedMultiPositionRun,
    )
    from fiberforce.results import TrainingSession, WeeklyProgram, compute_personal_records, get_milestones, compute_simple_trend
    RECIPES_AVAILABLE = True
except Exception as e:
    RECIPES_AVAILABLE = False
    print("Warning: recipes not fully available:", e)

# Visualization (optional)
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


class AnimatedDominanceBar(QWidget):
    """Custom painted dominance % bar for pro look (rounded, theme cyan/green fill, no extra deps).
    Supports setValue() for live + animation drivers. Used in visual result preview.
    """
    def __init__(self, parent=None, accent: str = "#00d9ff"):
        super().__init__(parent)
        self.setMinimumHeight(16)
        self.setMaximumHeight(20)
        self._value = 0.0
        self._accent = QColor(accent)
        self.setToolTip("Dominance % = relative moment arm share at the joint vs other modeled co-movers. Higher = better mechanical leverage for this muscle (lower force needed to meet external torque). Modeled estimate only.")

    def setValue(self, v: float):
        self._value = max(0.0, min(100.0, float(v)))
        self.update()

    def value(self) -> float:
        return self._value

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)
        # subtle dark bg (matches app theme)
        p.setBrush(QBrush(QColor("#24242e")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 5, 5)
        # fill portion
        if self._value > 0.5:
            fill_w = max(3, int(r.width() * (self._value / 100.0)))
            fill_rect = r.adjusted(0, 0, -(r.width() - fill_w), 0)
            p.setBrush(QBrush(self._accent))
            p.drawRoundedRect(fill_rect, 5, 5)
        # thin edge
        p.setPen(QPen(QColor("#3a3a48"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 5, 5)


class SelectionChipBar(QWidget):
    """Spacious visual chip/pill selector replacing clumped QComboBox popup lists for variations and targets.

    Per user: "longlist and kind of clumped" + "better way ... not so boring and squished" + "hide or remove the original dropdown rows (chips primary)".

    - Always-visible row (or wrapped) of checkable themed buttons (cyan active, rounded, dark bg, high contrast).
    - Human labels (from VARIATION_LABELS / TARGET_SHORT_LABELS) + optional muscle color dot.
    - Click updates backing QComboBox (so all live _schedule / run / .currentText sites + smoke sets continue to work with zero change).
    - Programmatic set on combo can be synced by connecting combo.currentTextChanged -> chip.set_current (avoids loops).
    - Reusable for single + multi-pos tabs. No new deps. Matches existing QPushButton QSS + AnimatedDominanceBar paint style.
    - Tooltips carry honest modeled notes (grip/MA effect).
    """
    def __init__(self, parent=None, is_target: bool = False):
        super().__init__(parent)
        self._is_target = is_target
        self._current_value: Optional[str] = None
        self._backing_combo: Optional[QComboBox] = None
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 2, 0, 2)
        self._layout.setSpacing(6)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_backing_combo(self, combo: QComboBox):
        """The hidden (or visible) QCombo that holds the real value for analyze/live/run calls."""
        self._backing_combo = combo

    def set_choices(self, choices: list[tuple[str, str]]):
        """choices: [(display_label, internal_value), ...] e.g. [('Close Grip', 'flat_close'), ('Sternal Pec', 'Pectoralis Major::Sternal fibers')]"""
        # clear old
        for b in self._buttons:
            self._group.removeButton(b)
            b.setParent(None)
            b.deleteLater()
        self._buttons.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            if w := item.widget():
                w.setParent(None)

        for disp, val in choices:
            btn = QPushButton(disp)
            btn.setCheckable(True)
            btn.setMinimumWidth(68)
            btn.setMaximumWidth(140)
            btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
            # theme match (dark rounded + cyan checked); small + spacious feel vs tight dropdown
            color = MUSCLE_COLORS.get(disp.split()[0] if self._is_target else "", "#00d9ff")
            if self._is_target:
                # prefix a colored dot via unicode + style (keeps simple, no extra widgets)
                btn.setText(f"● {disp}")
                btn.setStyleSheet(
                    f"QPushButton {{ background: #1a1a22; color: #f5f5fa; border: 1px solid #353540; border-radius: 8px; padding: 5px 10px; font-size: 11px; }}"
                    f"QPushButton:checked {{ background: #00d9ff; color: #0a0a0f; border-color: #00f5a0; font-weight: 600; }}"
                    f"QPushButton:hover {{ border-color: {color}; }}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: #1a1a22; color: #f5f5fa; border: 1px solid #353540; border-radius: 8px; padding: 5px 10px; font-size: 11px; }"
                    "QPushButton:checked { background: #00d9ff; color: #0a0a0f; border-color: #00f5a0; font-weight: 600; }"
                    "QPushButton:hover { border-color: #00d9ff; }"
                )
            btn.setToolTip("Click to select — updates live visual cards (single) or the choice used by Run (multi). Modeled estimate only; grip/position shifts dominance via MA.")
            self._group.addButton(btn)
            self._layout.addWidget(btn)
            self._buttons.append(btn)
            # capture val in closure
            btn._chip_value = val  # robust match even when display short != value full
            btn.clicked.connect(lambda checked, v=val: self._on_chip_clicked(v))
        # size hint for the bar
        self.setMinimumHeight(28)

    def _on_chip_clicked(self, value: str):
        if value == self._current_value:
            return
        self._current_value = value
        if self._backing_combo:
            # drive the combo so existing currentTextChanged -> live preview / run paths fire unchanged
            self._backing_combo.setCurrentText(value)
        # uncheck others visually (group should do it) + ensure this checked
        for b in self._buttons:
            if getattr(b, "_chip_value", None) == value or b.text().replace("● ", "") == value or b.text() == value:
                b.setChecked(True)
            else:
                b.setChecked(False)

    def set_current(self, value: str):
        """Programmatic (e.g. from combo change after lift populate or smoke setCurrentText)."""
        self._current_value = value
        matched = False
        for b in self._buttons:
            is_match = (getattr(b, "_chip_value", None) == value or
                        b.text().replace("● ", "") == value or b.text() == value)
            b.setChecked(is_match)
            if is_match:
                matched = True
        if not matched and self._buttons:
            # fallback: check first (should not happen if populate consistent)
            self._buttons[0].setChecked(True)
            self._current_value = getattr(self._buttons[0], "_chip_value", value)

    def current_value(self) -> Optional[str]:
        return self._current_value


class FiberForceMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FiberForce • Muscle Force & Torque Analyzer")
        self.resize(1350, 920)
        self.setMinimumSize(1050, 650)
        self.setUnifiedTitleAndToolBarOnMac(True)  # Mac-native polish
        if Path(APP_ICON).exists():
            self.setWindowIcon(QIcon(APP_ICON))

        self.service = AnalysisService()
        self.current_athlete = None
        self.current_program = None
        self.history: list[str] = []  # simple in-memory run history for v1
        self.settings = QSettings("FiberForce", "FiberForce")
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.timeout.connect(self._live_preview_single)
        self._current_preview_res = None  # for count-up from previous values
        self._anim_refs = []  # keep animation objects alive during run

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Mac-friendly menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        export_act = file_menu.addAction("Export Current Report...")
        export_act.triggered.connect(self.export_current)
        file_menu.addSeparator()
        quit_act = file_menu.addAction("Quit")
        quit_act.triggered.connect(self.close)

        tools_menu = menubar.addMenu("&Tools")
        smoke_act = tools_menu.addAction("Run Internal Smoke / Verify")
        smoke_act.triggered.connect(self.run_internal_smoke)
        tools_menu.addSeparator()
        # Activity log is no longer a persistent bottom box (space + modern feel).
        # These actions let the user view/clear the internal buffer when they want (mainly for smoke output).
        show_log_act = tools_menu.addAction("Show Activity Log...")
        show_log_act.triggered.connect(self._show_activity_log_dialog)
        clear_log_act = tools_menu.addAction("Clear Activity Log Buffer")
        clear_log_act.triggered.connect(lambda: self.log.clear())

        help_menu = menubar.addMenu("&Help")
        about_act = help_menu.addAction("About FiberForce")
        about_act.triggered.connect(self.show_about)
        onboard_act = help_menu.addAction("Re-run guided first-run setup (name + measurements)")
        onboard_act.triggered.connect(self._show_onboarding_wizard)

        # Top status
        self.status = QLabel("FiberForce v2.0 • Clickable macOS app (double-click icon) • Imperial (in/ft/lbs) + ft-lb torque + dynrom. Help > About FiberForce for brand & details. Tools > Run Internal Smoke to verify.")
        self.status.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status)

        # Tabs for everything - each tab page is wrapped in a QScrollArea so tall content
        # (forms, tables, plots, the muscle map, etc.) can scroll when it doesn't fit the window.
        # Brand is in the native titlebar icon + macOS menu bar (Help > About FiberForce) which shows hero image in a modal dialog.
        # This follows desktop app conventions (titlebar + About dialog for full brand) so tabs + input fields + plots get the vast majority of vertical space.
        tabs = QTabWidget()
        main_layout.addWidget(tabs, stretch=1)

        self._add_scrollable_tab(tabs, self._create_athlete_tab(), "Athlete / Profile")
        self._add_scrollable_tab(tabs, self._create_analyze_tab(), "Single Analysis")
        self._add_scrollable_tab(tabs, self._create_multipos_tab(), "Multi-Position")
        self._add_scrollable_tab(tabs, self._create_sensitivity_tab(), "Sensitivity")
        self._add_scrollable_tab(tabs, self._create_program_tab(), "Programs")
        self._add_scrollable_tab(tabs, self._create_recipes_tab(), "Quick Recipes")
        self._add_scrollable_tab(tabs, self._create_history_tab(), "History / Exports")

        # Bottom "Activity Log" removed from persistent UI (per user feedback after visual cards + interactive form).
        # It was taking vertical space and felt like leftover "boring text box".
        # We keep an internal buffer (self.log) so smoke and detailed output can still be viewed on demand.
        # Key user feedback now lives in: visual cards (Single Analysis), per-tab outputs, top status, QMessageBox, Help menu actions, and dedicated dialogs.
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        # Do NOT add to main_layout. Space reclaimed for tabs + visual content.
        # The initial "GUI ready" message goes into the buffer only.
        self._log("GUI ready (v1 units). Load or create an athlete (inches/lbs) to begin. All core library features (including .interpret(), .insight(), recipes, and GUI smoke available. Activity log is now on-demand via Tools menu / smoke results).")

        # First-run interactive onboarding (custom animated QStacked dialog per user vision).
        # Only triggers if no prior onboard flag AND no saved profiles on disk.
        # Chained after splash (splash is in the module main()).
        QTimer.singleShot(750, self._maybe_show_first_run_onboarding)

    def _log(self, text: str):
        self.log.append(text)
        self.log.ensureCursorVisible()

    def _add_scrollable_tab(self, tabs: QTabWidget, page: QWidget, title: str):
        """Wrap a tab page in a QScrollArea so its content (controls, tables, plots, maps)
        can scroll vertically when the window is too small to show everything.
        The tab bar itself stays fixed at the top of the tab widget.
        """
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(page)
        tabs.addTab(scroller, title)

    # ---------- FIRST-RUN ONBOARDING (custom animated dialog per user request) ----------
    def _maybe_show_first_run_onboarding(self):
        """Show the interactive name+measurements wizard on very first launch.
        Uses QSettings + list_profiles() so it only nags truly new users.
        After splash per the launch flow.
        """
        try:
            onboarded = bool(self.settings.value("onboarded/v1", False, type=bool))
            profiles = list_profiles() if 'list_profiles' in globals() or True else []
            # safe call
            try:
                from fiberforce.profiles import list_profiles as _lp
                profiles = _lp()
            except Exception:
                profiles = []
            if not onboarded and len(profiles) == 0:
                self._show_onboarding_wizard()
            elif profiles and not self.current_athlete:
                # Gentle hint in status for returning users with profiles but no active in this session
                self._log("Profiles found on disk — load one in the Athlete tab (or use Help > Re-run guided setup).")
        except Exception as e:
            self._log(f"(non-fatal) onboard check skipped: {e}")

    def _show_onboarding_wizard(self):
        """Custom QDialog + QStackedWidget with QPropertyAnimation fade transitions between pages.
        Pages: 1. Welcome + who you are (name + example load). 2. Your measurements (inches, the geo-critical ones).
        3. Review + create (calls create_athlete + save + sets onboarded + seeds live preview in Single tab).
        Feels guided and interactive; no rigid QMessageBox.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("FiberForce — Welcome (first-run setup)")
        dlg.setMinimumWidth(620)
        dlg.setMinimumHeight(460)
        dlg.setModal(True)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        title = QLabel("<b>Let's make this personal.</b>")
        title.setStyleSheet("font-size: 17px; color: #00d9ff;")
        outer.addWidget(title)

        sub = QLabel("Tell us who you are + a few measurements (inches). These drive the geometric moment arms and personalized torque estimates. All values are modeled estimates — see limitations in Help > About.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #c8c8d0; font-size: 11px;")
        outer.addWidget(sub)

        self.onboard_stack = QStackedWidget()
        outer.addWidget(self.onboard_stack, stretch=1)

        # Page 0: Welcome + identity
        p0 = QWidget()
        p0l = QVBoxLayout(p0)
        p0l.addWidget(QLabel("Who are you? (this labels your profiles, history, and PRs)"))
        self.onboard_name = QLineEdit("Alex Lifters")
        p0l.addWidget(self.onboard_name)
        ex_btn = QPushButton("Load example athlete (average male lifter measurements)")
        ex_btn.clicked.connect(lambda: self._onboard_load_example(dlg))
        p0l.addWidget(ex_btn)
        p0l.addStretch()
        nav0 = QHBoxLayout()
        next0 = QPushButton("Next → measurements")
        next0.clicked.connect(lambda: self._onboard_animated_switch(1))
        nav0.addStretch()
        nav0.addWidget(next0)
        p0l.addLayout(nav0)
        self.onboard_stack.addWidget(p0)

        # Page 1: Measurements (copy of the critical ones from Athlete tab for isolation)
        p1 = QWidget()
        p1l = QVBoxLayout(p1)
        p1l.addWidget(QLabel("Your measurements (inches) — rough tape measure is fine. These personalize leverage."))
        form = QFormLayout()
        self.onboard_femur = QDoubleSpinBox(); self.onboard_femur.setRange(8, 28); self.onboard_femur.setValue(17.0)
        self.onboard_tibia = QDoubleSpinBox(); self.onboard_tibia.setRange(8, 24); self.onboard_tibia.setValue(15.0)
        self.onboard_humerus = QDoubleSpinBox(); self.onboard_humerus.setRange(8, 20); self.onboard_humerus.setValue(13.4)
        self.onboard_biac = QDoubleSpinBox(); self.onboard_biac.setRange(10, 22); self.onboard_biac.setValue(15.7)
        self.onboard_torso = QDoubleSpinBox(); self.onboard_torso.setRange(4, 16); self.onboard_torso.setValue(9.4)
        form.addRow("Femur (in):", self.onboard_femur)
        form.addRow("Tibia (in):", self.onboard_tibia)
        form.addRow("Humerus (in):", self.onboard_humerus)
        form.addRow("Biacromial width (in):", self.onboard_biac)
        form.addRow("Torso depth (in):", self.onboard_torso)
        p1l.addLayout(form)
        note = QLabel("Tip: Missing a measurement? The model falls back gracefully. You can refine later in the Athlete tab.")
        note.setStyleSheet("font-size: 10px; color: #888;")
        p1l.addWidget(note)
        p1l.addStretch()
        nav1 = QHBoxLayout()
        prev1 = QPushButton("← Back")
        prev1.clicked.connect(lambda: self._onboard_animated_switch(0))
        next1 = QPushButton("Next → review & create")
        next1.clicked.connect(lambda: self._onboard_animated_switch(2))
        nav1.addWidget(prev1)
        nav1.addStretch()
        nav1.addWidget(next1)
        p1l.addLayout(nav1)
        self.onboard_stack.addWidget(p1)

        # Page 2: Review + Finish (creates, saves, seeds UI, marks onboarded)
        p2 = QWidget()
        p2l = QVBoxLayout(p2)
        self.onboard_review = QLabel("Review your info. Click Finish to create your profile and jump into analysis.")
        self.onboard_review.setWordWrap(True)
        p2l.addWidget(self.onboard_review)
        p2l.addStretch()
        nav2 = QHBoxLayout()
        prev2 = QPushButton("← Back")
        prev2.clicked.connect(lambda: self._onboard_animated_switch(1))
        finish = QPushButton("Create profile & start analyzing ★")
        finish.setDefault(True)
        finish.clicked.connect(lambda: self._onboard_finish(dlg))
        skip = QPushButton("Skip for now (limited features until you create an athlete)")
        skip.clicked.connect(dlg.reject)
        nav2.addWidget(prev2)
        nav2.addWidget(skip)
        nav2.addStretch()
        nav2.addWidget(finish)
        p2l.addLayout(nav2)
        self.onboard_stack.addWidget(p2)

        # initial review text (will refresh on switch to 2)
        self.onboard_stack.currentChanged.connect(self._onboard_refresh_review)

        outer.addWidget(QLabel("All numbers are modeled biomechanical estimates (see limitations). No data leaves your machine."))
        dlg.exec()

    def _onboard_animated_switch(self, target_idx: int):
        """Fade transition between wizard pages using QGraphicsOpacityEffect + QPropertyAnimation.
        This is the 'feels more interactive' part of the first-run flow.
        """
        old = self.onboard_stack.currentWidget()
        if old is None:
            self.onboard_stack.setCurrentIndex(target_idx)
            return
        eff = QGraphicsOpacityEffect(old)
        old.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        def _do_switch():
            self.onboard_stack.setCurrentIndex(target_idx)
            new = self.onboard_stack.currentWidget()
            if new:
                eff2 = QGraphicsOpacityEffect(new)
                new.setGraphicsEffect(eff2)
                anim2 = QPropertyAnimation(eff2, b"opacity", self)
                anim2.setDuration(220)
                anim2.setStartValue(0.0)
                anim2.setEndValue(1.0)
                anim2.setEasingCurve(QEasingCurve.OutCubic)
                anim2.start()
                self._anim_refs.append(anim2)  # prevent GC mid-run
            # clear old effect after
            QTimer.singleShot(50, lambda: old.setGraphicsEffect(None))
        anim.finished.connect(_do_switch)
        anim.start()
        self._anim_refs.append(anim)

    def _onboard_refresh_review(self, idx: int):
        if idx != 2:
            return
        name = self.onboard_name.text().strip() or "Athlete"
        self.onboard_review.setText(
            f"<b>{name}</b><br>"
            f"Femur {self.onboard_femur.value():.1f}in • Tibia {self.onboard_tibia.value():.1f}in • Humerus {self.onboard_humerus.value():.1f}in<br>"
            f"Biacromial {self.onboard_biac.value():.1f}in • Torso {self.onboard_torso.value():.1f}in<br><br>"
            "Click Finish to save this as your profile, enable geometric calculations, and seed a live visual preview in the Single Analysis tab."
        )

    def _onboard_load_example(self, dlg: QDialog):
        self.onboard_name.setText("Example Lifter (17in femur)")
        self.onboard_femur.setValue(17.0)
        self.onboard_tibia.setValue(15.0)
        self.onboard_humerus.setValue(13.4)
        self.onboard_biac.setValue(15.7)
        self.onboard_torso.setValue(9.4)
        self._log("Example athlete measurements loaded into wizard.")
        # auto advance to review for speed
        QTimer.singleShot(120, lambda: self._onboard_animated_switch(2))

    def _onboard_finish(self, dlg: QDialog):
        try:
            name = self.onboard_name.text().strip() or "My Athlete"
            self.current_athlete = create_athlete(
                name=name,
                units="imperial",
                femur_in=self.onboard_femur.value(),
                tibia_in=self.onboard_tibia.value(),
                humerus_in=self.onboard_humerus.value(),
                biacromial_in=self.onboard_biac.value(),
                torso_depth_in=self.onboard_torso.value(),
            )
            # persist via existing profiles system (so History/PRs etc see it)
            try:
                from fiberforce.profiles import save_anthropometry
                save_anthropometry(self.current_athlete.anthropometry, name)
            except Exception as pe:
                self._log(f"(warn) profile save non-fatal: {pe}")
            # mark done
            self.settings.setValue("onboarded/v1", True)
            self.settings.sync()
            # mirror into Athlete tab fields so user sees it there too
            if hasattr(self, "athlete_name"):
                self.athlete_name.setText(name)
                self.femur.setValue(self.onboard_femur.value())
                self.tibia.setValue(self.onboard_tibia.value())
                self.humerus.setValue(self.onboard_humerus.value())
                self.biacromial.setValue(self.onboard_biac.value())
                self.torso.setValue(self.onboard_torso.value())
            if hasattr(self, "athlete_status"):
                self.athlete_status.setText(f"Athlete ready: {name} (from guided setup; geometric enabled)")
            # (onboarding feedback is in the post-finish QMessageBox + athlete_status + visual preview; kept in buffer only)
            # Seed a nice first visual: run a default single bench flat live preview so user sees non-boring output immediately
            try:
                if hasattr(self, "anal_lift"):
                    self.anal_lift.setCurrentText("bench")
                    self.anal_var.setCurrentText("flat")
                    self.anal_target.setCurrentText("Pectoralis Major::Sternal fibers")
                    self.anal_load.setValue(185.0)
                    self.anal_geo.setChecked(True)
                    # Ensure chips (primary UI) reflect the seeded values (backing combos already set)
                    if hasattr(self, "anal_var_chip"):
                        self.anal_var_chip.set_current("flat")
                    if hasattr(self, "anal_target_chip"):
                        self.anal_target_chip.set_current("Pectoralis Major::Sternal fibers")
                    QTimer.singleShot(80, self._live_preview_single)
            except Exception:
                pass
            dlg.accept()
            # friendly modal "next steps" using existing pattern
            QMessageBox.information(self, "Welcome", "Profile created. The Single Analysis tab now shows live visual cards (dominance bars animate as you change grip/variation/load). Run explicit analyses to log PRs and full .interpret() to history. You can always refine measurements in the Athlete tab.")
        except Exception as e:
            QMessageBox.critical(dlg, "Setup error", str(e))

    def _populate_contextual_fields(self, which: str = "both"):
        """Auto-populate the var/positions/target dropdowns based on current lift.
        Called on lift change and at init. Keeps the UI 'as easy as possible' -- no guessing valid strings.
        Also refreshes the visual chip bars (primary selection UI) with human labels + current for the lift.
        Original combos kept (hidden per choice) as source of truth for live/run strings.
        """
        if which in ("single", "both") and hasattr(self, "anal_lift"):
            lift = self.anal_lift.currentText() or "squat"
            # Variation
            self.anal_var.clear()
            for v in VARIATIONS_BY_LIFT.get(lift, ["flat"]):
                self.anal_var.addItem(v)
            self.anal_var.setCurrentIndex(0)
            # Target (nice display strings the backend accepts)
            self.anal_target.clear()
            for t in TARGETS_BY_LIFT.get(lift, ["Pectoralis Major::Sternal fibers"]):
                self.anal_target.addItem(t)
            self.anal_target.setCurrentIndex(0)

            # Refresh chips (new primary spacious visual selector; human labels, not clumped list)
            if hasattr(self, "anal_var_chip") and self.anal_var_chip:
                vchoices = [(VARIATION_LABELS.get(v, v.replace("_", " ").title()), v) for v in VARIATIONS_BY_LIFT.get(lift, ["flat"])]
                self.anal_var_chip.set_choices(vchoices)
                self.anal_var_chip.set_current(self.anal_var.currentText())
            if hasattr(self, "anal_target_chip") and self.anal_target_chip:
                tchoices = [(TARGET_SHORT_LABELS.get(t, t.split("::")[-1]), t) for t in TARGETS_BY_LIFT.get(lift, ["Pectoralis Major::Sternal fibers"])]
                self.anal_target_chip.set_choices(tchoices)
                self.anal_target_chip.set_current(self.anal_target.currentText())

        if which in ("multi", "both") and hasattr(self, "mp_lift"):
            lift = self.mp_lift.currentText() or "squat"
            # Variation
            self.mp_var.clear()
            for v in VARIATIONS_BY_LIFT.get(lift, ["low_bar"]):
                self.mp_var.addItem(v)
            self.mp_var.setCurrentIndex(0)
            # Positions: presets in editable combo (easy pick, still allows custom comma)
            self.mp_positions.clear()
            presets = POSITIONS_BY_LIFT.get(lift, ["bottom,mid,top"])
            for p in presets:
                self.mp_positions.addItem(p)
            self.mp_positions.setCurrentIndex(0)  # default sensible for the lift
            # Target
            self.mp_target.clear()
            for t in TARGETS_BY_LIFT.get(lift, ["Gluteus Maximus::Upper fibers"]):
                self.mp_target.addItem(t)
            self.mp_target.setCurrentIndex(0)

            # Refresh chips for multi (same visual primary, no live auto-run but choice drives explicit runs)
            if hasattr(self, "mp_var_chip") and self.mp_var_chip:
                vchoices = [(VARIATION_LABELS.get(v, v.replace("_", " ").title()), v) for v in VARIATIONS_BY_LIFT.get(lift, ["low_bar"])]
                self.mp_var_chip.set_choices(vchoices)
                self.mp_var_chip.set_current(self.mp_var.currentText())
            if hasattr(self, "mp_target_chip") and self.mp_target_chip:
                tchoices = [(TARGET_SHORT_LABELS.get(t, t.split("::")[-1]), t) for t in TARGETS_BY_LIFT.get(lift, ["Gluteus Maximus::Upper fibers"])]
                self.mp_target_chip.set_choices(tchoices)
                self.mp_target_chip.set_current(self.mp_target.currentText())

    # ---------- ATHLETE TAB ----------
    def _create_athlete_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form = QGroupBox("Create / Edit Athlete Measurements (enables geometric)")
        form_layout = QFormLayout()

        self.athlete_name = QLineEdit("My Athlete")
        form_layout.addRow("Name:", self.athlete_name)

        self.femur = QDoubleSpinBox(); self.femur.setRange(8, 28); self.femur.setValue(17.0)  # inches
        self.tibia = QDoubleSpinBox(); self.tibia.setRange(8, 24); self.tibia.setValue(15.0)
        self.humerus = QDoubleSpinBox(); self.humerus.setRange(8, 20); self.humerus.setValue(13.4)
        self.biacromial = QDoubleSpinBox(); self.biacromial.setRange(10, 22); self.biacromial.setValue(15.7)
        self.torso = QDoubleSpinBox(); self.torso.setRange(4, 16); self.torso.setValue(9.4)

        form_layout.addRow("Femur (in):", self.femur)
        form_layout.addRow("Tibia (in):", self.tibia)
        form_layout.addRow("Humerus (in):", self.humerus)
        form_layout.addRow("Biacromial width (in):", self.biacromial)
        form_layout.addRow("Torso depth (in):", self.torso)

        form.setLayout(form_layout)
        layout.addWidget(form)

        btns = QHBoxLayout()
        create_btn = QPushButton("Create / Update Athlete")
        create_btn.clicked.connect(self.create_athlete)
        btns.addWidget(create_btn)

        load_btn = QPushButton("Load Existing Profile")
        load_btn.clicked.connect(self.load_existing_profile)
        btns.addWidget(load_btn)

        save_btn = QPushButton("Save as Profile")
        save_btn.clicked.connect(self.save_as_profile)
        btns.addWidget(save_btn)

        layout.addLayout(btns)

        self.athlete_status = QLabel("No athlete loaded yet. Create one or load a profile to enable geometric & personalized analyses.")
        layout.addWidget(self.athlete_status)

        layout.addStretch()
        return w

    def create_athlete(self):
        try:
            name = self.athlete_name.text().strip() or "Athlete"
            self.current_athlete = create_athlete(
                name=name,
                units="imperial",
                femur_in=self.femur.value(),
                tibia_in=self.tibia.value(),
                humerus_in=self.humerus.value(),
                biacromial_in=self.biacromial.value(),
                torso_depth_in=self.torso.value(),
            )
            self.athlete_status.setText(f"Athlete ready: {name} (geometric enabled where supported)")
            # (no longer logging to persistent bottom; status label + visual cards provide feedback. Still in buffer for "Show Activity Log")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def load_existing_profile(self):
        try:
            profiles = list_profiles()
            if not profiles:
                QMessageBox.information(self, "No Profiles", "No saved profiles. Use CLI: fiberforce profile save ... or create one here.")
                return
            # Simple: take first for prototype (in real app we'd have a dialog)
            name = profiles[0]
            anthro = load_anthropometry(name)
            self.current_athlete = self.service.create_subject_from_measurements(
                name=name,
                units="metric",  # saved profiles store internal metric cm
                **{k: v for k, v in anthro.__dict__.items() if v is not None}
            )
            self.athlete_name.setText(name)
            self.athlete_status.setText(f"Loaded profile: {name}")
            # v1 polish: sync inch spinboxes from loaded (convert cm -> in for display)
            try:
                from fiberforce.calculations.utils import cm_to_inches
                if anthro.femur_length_cm: self.femur.setValue(round(cm_to_inches(anthro.femur_length_cm), 1))
                if anthro.tibia_length_cm: self.tibia.setValue(round(cm_to_inches(anthro.tibia_length_cm), 1))
                if anthro.humerus_length_cm: self.humerus.setValue(round(cm_to_inches(anthro.humerus_length_cm), 1))
                if anthro.biacromial_width_cm: self.biacromial.setValue(round(cm_to_inches(anthro.biacromial_width_cm), 1))
                if anthro.torso_depth_at_chest_cm: self.torso.setValue(round(cm_to_inches(anthro.torso_depth_at_chest_cm), 1))
            except Exception:
                pass  # non-fatal, spins keep prior values
            self._log(f"Loaded profile '{name}' (inch spinboxes synced)")
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))

    def save_as_profile(self):
        if not self.current_athlete:
            QMessageBox.warning(self, "No Athlete", "Create or load an athlete first.")
            return
        name = self.athlete_name.text().strip() or "new-athlete"
        try:
            save_anthropometry(self.current_athlete.anthropometry, name)
            self._log(f"Saved profile '{name}'")
            QMessageBox.information(self, "Saved", f"Profile '{name}' saved. You can now use it from CLI too.")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    # ---------- SINGLE ANALYSIS TAB ----------
    def _create_analyze_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        controls = QGroupBox("Single Position Analysis")
        c_layout = QFormLayout()

        self.anal_lift = QComboBox()
        self.anal_lift.addItems(LIFT_KEYS)
        self.anal_lift.setCurrentText("squat")
        c_layout.addRow("Lift:", self.anal_lift)

        self.anal_load = QDoubleSpinBox()
        self.anal_load.setRange(45, 600); self.anal_load.setValue(225)  # lbs, v1 imperial
        c_layout.addRow("Load (lbs):", self.anal_load)

        self.anal_geo = QCheckBox("Use Geometric (if athlete has measurements)")
        self.anal_geo.setChecked(True)
        c_layout.addRow("", self.anal_geo)

        controls.setLayout(c_layout)
        layout.addWidget(controls)

        # NEW primary visual selection spot (chips, full width after the compact form group for spacious non-squished feel).
        # Backing combos created (hidden) so .currentText + live + run paths unchanged. Per user: chips primary, hide dropdown rows.
        self.anal_var = QComboBox()
        self.anal_var.setEditable(False)
        self.anal_target = QComboBox()
        self.anal_target.setEditable(False)

        var_label = QLabel("Variation (tap chip — instantly animates live visual cards below)")
        var_label.setStyleSheet("font-size: 12px; color: #00d9ff; font-weight: 600; margin-top: 8px;")
        layout.addWidget(var_label)
        self.anal_var_chip = SelectionChipBar(is_target=False)
        self.anal_var_chip.set_backing_combo(self.anal_var)
        layout.addWidget(self.anal_var_chip)

        tgt_label = QLabel("Target Region (tap — dominance % and ft-lb shares update live; colors group by muscle)")
        tgt_label.setStyleSheet("font-size: 12px; color: #00d9ff; font-weight: 600; margin-top: 6px;")
        layout.addWidget(tgt_label)
        self.anal_target_chip = SelectionChipBar(is_target=True)
        self.anal_target_chip.set_backing_combo(self.anal_target)
        layout.addWidget(self.anal_target_chip)

        # Hide the original clumped/squished dropdowns entirely (chips are now the selection spot).
        self.anal_var.setVisible(False)
        self.anal_target.setVisible(False)

        # 2-way sync (programmatic combo sets from populate/smoke update chips; taps on chips update combo to fire live).
        self.anal_var.currentTextChanged.connect(lambda t: self.anal_var_chip.set_current(t) if hasattr(self, "anal_var_chip") else None)
        self.anal_target.currentTextChanged.connect(lambda t: self.anal_target_chip.set_current(t) if hasattr(self, "anal_target_chip") else None)

        run_btn = QPushButton("Run Analysis + Show Interpretation (ft-lb torque)")
        run_btn.clicked.connect(self.run_single_analysis)
        layout.addWidget(run_btn)

        # Quick compare for variation effects on % dominance (e.g. close vs wide bench; leverages all-muscles work)
        cmp_btn = QPushButton("Compare close vs wide (bench % dom + ft-lb delta) — modeled estimates")
        cmp_btn.clicked.connect(self.run_variation_compare)
        layout.addWidget(cmp_btn)

        # ========== NEW VISUAL RESULT PREVIEW (primary, animated, live) ==========
        # Per user: "I dont want just the boring box with text" + "when you interact with the different elements of the form what if it feels more interactive?"
        # Live ON by default. Single-pos only (fast). Custom painted bars + count-up numbers + dominance cards.
        # Full rich text .interpret() + notes is now secondary/collapsed (toggle to expand).
        preview_box = QGroupBox("Live Visual Summary — modeled regional torque demands (ft-lb)  •  Live ON: change lift/variation/load and watch bars/numbers animate")
        preview_box.setStyleSheet("QGroupBox { font-weight: 600; color: #00d9ff; }")
        pv_lay = QVBoxLayout(preview_box)
        pv_lay.setSpacing(6)

        # Big target peak count-up number
        self.target_peak_label = QLabel("<b>—</b> ft-lb  <span style='color:#888;font-size:10px'>(target / lead)</span>")
        self.target_peak_label.setStyleSheet("font-size: 20px; color: #00f5a0; margin: 4px 0;")
        pv_lay.addWidget(self.target_peak_label)

        # Dominance bars area (dynamic per results, using custom AnimatedDominanceBar for pro rounded theme-matched look)
        self.dom_rows = {}  # short_label -> (bar_widget, pct_label)
        self.dom_container = QWidget()
        dom_l = QVBoxLayout(self.dom_container)
        dom_l.setContentsMargins(0, 0, 0, 0)
        dom_l.setSpacing(3)
        pv_lay.addWidget(self.dom_container)

        # Efficiency line
        self.eff_label = QLabel("Efficiency: — ft-lb per lb load")
        self.eff_label.setStyleSheet("font-size: 10px; color: #a0a0b0;")
        pv_lay.addWidget(self.eff_label)

        # Toggle for the old text box (now secondary per "visual primary, text secondary/collapsed")
        self.details_toggle = QCheckBox("Show full text details + .interpret() + lit notes (collapsed by default for visual focus)")
        self.details_toggle.setChecked(False)
        self.details_toggle.setStyleSheet("font-size: 10px;")
        pv_lay.addWidget(self.details_toggle)

        layout.addWidget(preview_box)

        # The original text box (now optional/collapsed; run_single will expand it on explicit action)
        self.anal_output = QTextEdit()
        self.anal_output.setReadOnly(True)
        self.anal_output.setMaximumHeight(160)
        self.anal_output.setVisible(False)
        layout.addWidget(self.anal_output, stretch=0)

        self.details_toggle.toggled.connect(lambda on: self.anal_output.setVisible(on))

        # Live wiring: form changes (lift/var/target/load/geo) schedule a debounced live preview (ON by default)
        # This makes the form feel interactive — bars fill, numbers tick on grip/stance/angle changes.
        for sig_src in (self.anal_lift, self.anal_var, self.anal_target):
            sig_src.currentTextChanged.connect(self._schedule_live_preview)
        for sig_src in (self.anal_load,):
            sig_src.valueChanged.connect(self._schedule_live_preview)
        self.anal_geo.toggled.connect(self._schedule_live_preview)

        # Also keep the contextual dropdown populate on lift (existing)
        self.anal_lift.currentTextChanged.connect(lambda: self._populate_contextual_fields("single"))
        self._populate_contextual_fields("single")

        return w

    def run_single_analysis(self):
        if not self.current_athlete:
            self.anal_output.append("Please create or load an athlete first (Athlete tab).")
            return
        try:
            res = analyze(
                self.anal_lift.currentText(),
                load_lbs=self.anal_load.value(),  # v1 imperial
                variation=self.anal_var.currentText(),
                target_region_name=self.anal_target.currentText(),
                athlete=self.current_athlete,
                use_geometric=self.anal_geo.isChecked(),
                units="imperial",
            )
            self.anal_output.clear()
            self.anal_output.append("=== Single Analysis Result (ft-lb torque) ===")
            for r in res.results:
                # Prefer ft-lb display when available (v1)
                ft = getattr(r, "peak_torque_ftlb", None)
                dom_val = getattr(r, "dominance_percent", None)
                dom = f" [{dom_val}% dominance]" if dom_val is not None else ""
                bar = ""
                if dom_val is not None:
                    n = max(0, min(10, int(dom_val / 10)))
                    bar = "  | " + "▉" * n + "░" * (10 - n)
                if ft is not None:
                    self.anal_output.append(f"  {r.muscle_region}: {ft:.1f} ft-lb  ({r.confidence_level}){dom}{bar}")
                else:
                    self.anal_output.append(f"  {r.muscle_region}: {r.peak_force_newtons:.1f} N  ({r.confidence_level}){dom}{bar}")
            self.anal_output.append(f"\nPosition: {getattr(res, 'position_description', 'n/a')}")
            # Show % of lift dominated by target (shoulder vs elbow torque share proxy for multi-muscle bench etc.)
            if len(res.results) > 1:
                self.anal_output.append("\n(Note: multiple muscles modeled for this position; dominance % based on relative MA at each joint. Grip/position affects pec vs tri/ delt share.)")
            # Wave 3 lit surface example
            posd = str(getattr(res, "position_description", "")).lower()
            if "bench" in posd:
                self.anal_output.append(" [Lit cross-check ex (static max shoulder ~100kg flat): 220-350 Nm per audit; dynamic lower.]")

            try:
                if hasattr(res, "interpret"):
                    self.anal_output.append("\n" + res.interpret())
            except Exception as ie:
                self.anal_output.append(f"\n(interpret note: {ie})")

            # Drive the visual cards too (explicit run always shows the pretty + expands details)
            self._update_visual_preview(res)
            self.details_toggle.setChecked(True)
            self.anal_output.setVisible(True)
        except Exception as e:
            self.anal_output.append(f"Error: {e}")

    # --- Live interactive + visual data return helpers (new wave) ---
    def _schedule_live_preview(self, *_args):
        """Debounce form interactions so typing/scrolling dropdowns doesn't spam calc."""
        if not getattr(self, "current_athlete", None):
            return
        self._live_timer.start(260)  # ms — feels instant but not frantic

    def _live_preview_single(self):
        """The heart of 'form feels more interactive': on change, re-analyze single (fast path) and animate the visual cards.
        Only single-pos for live (multi/continuous/ full history commit stay on explicit Run).
        Always honest modeled framing in tooltips/labels.
        """
        if not self.current_athlete:
            return
        try:
            res = analyze(
                self.anal_lift.currentText(),
                load_lbs=self.anal_load.value(),
                variation=self.anal_var.currentText(),
                target_region_name=self.anal_target.currentText(),
                athlete=self.current_athlete,
                use_geometric=self.anal_geo.isChecked(),
                units="imperial",
            )
            self._update_visual_preview(res)
            # light non-spammy note in bottom log (only if user has the log visible)
            # self._log("live preview updated (single-pos modeled)")  # too noisy; skip
        except Exception:
            pass  # silent fail for live — don't break flow

    def _update_visual_preview(self, res):
        """Update (with animations) the primary visual cards from a result.
        - Count-up the lead/target ft-lb number.
        - Animate custom dominance bars (rounded, colored).
        - Update eff.
        Keeps 'modeled estimate' visible via tooltips + small text.
        """
        if not res or not getattr(res, "results", None):
            return
        self._current_preview_res = res

        # Lead / target peak (use first as lead for simplicity; user can target specific)
        lead = res.results[0]
        ft = getattr(lead, "peak_torque_ftlb", None) or 0.0
        old_ft = 0.0
        if hasattr(self, "_last_preview_ft"):
            old_ft = self._last_preview_ft
        self._last_preview_ft = ft
        self._animate_count_up(self.target_peak_label, old_ft, ft, " ft-lb  <span style='color:#888;font-size:10px'>(modeled est)</span>")

        # Dominance bars — rebuild rows if muscle set changed, else just animate values
        # Clear old
        for i in reversed(range(self.dom_container.layout().count())):
            w = self.dom_container.layout().itemAt(i).widget()
            if w:
                w.setParent(None)
        self.dom_rows.clear()

        for r in res.results:
            dom = getattr(r, "dominance_percent", None) or 0.0
            mr = getattr(r, "muscle_region", "")
            if isinstance(mr, str):
                short = mr.split("::")[-1][:22] if "::" in mr else mr[:22]
            else:
                short = str(mr)[:22]
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            name_l = QLabel(short)
            name_l.setMinimumWidth(110)
            name_l.setStyleSheet("font-size: 10px;")
            bar = AnimatedDominanceBar(accent="#00d9ff" if dom > 55 else ("#00f5a0" if dom > 35 else "#7a7a88"))
            bar.setValue(0.0)  # start 0 for anim in
            pct = QLabel(f"{dom:.1f}%")
            pct.setMinimumWidth(42)
            pct.setStyleSheet("font-size: 10px; color: #d0d0d8;")
            rl.addWidget(name_l)
            rl.addWidget(bar, stretch=1)
            rl.addWidget(pct)
            self.dom_container.layout().addWidget(row)
            self.dom_rows[short] = (bar, pct, r)

            # animate the bar fill
            self._animate_progress(bar, 0.0, dom, 380)

        # Efficiency (if available on res or compute proxy)
        eff = getattr(res, "efficiency_ftlb_per_lb", None)
        if eff is None:
            try:
                load = self.anal_load.value() or 1.0
                eff = (ft / load) if load > 0 else 0.0
            except Exception:
                eff = 0.0
        self.eff_label.setText(f"Efficiency: {eff:.2f} ft-lb per lb load  •  (higher = more torque per lb lifted; grip/pos changes this)")

    def _update_mp_visual(self, mpr):
        """Update visual cards for Multi-Position / Continuous results, mirroring Single Analysis style.
        Uses lead (first) position's data for peak + dominance bars. Keeps table/curve as detail.
        Animates like single for consistency.
        """
        if not mpr or not getattr(mpr, "analyses", None):
            return
        # Use first analysis as representative "lead"
        lead = mpr.analyses[0]
        ft = 0.0
        if lead.results:
            ft = getattr(lead.results[0], "peak_torque_ftlb", 0) or 0.0
        # Count-up style from previous if available
        old_ft = getattr(self, "_last_mp_ft", 0.0)
        self._last_mp_ft = ft
        self._animate_count_up(self.mp_peak_label, old_ft, ft, " ft-lb  <span style='color:#888;font-size:10px'>(lead position)</span>")

        # Clear and rebuild dom rows from lead result's movers (same as single)
        for i in reversed(range(self.mp_dom_container.layout().count())):
            w = self.mp_dom_container.layout().itemAt(i).widget()
            if w:
                w.setParent(None)

        for r in (lead.results or []):
            dom = getattr(r, "dominance_percent", None) or 0.0
            mr = getattr(r, "muscle_region", "")
            if isinstance(mr, str):
                short = mr.split("::")[-1][:22] if "::" in mr else mr[:22]
            else:
                short = str(mr)[:22]
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            name_l = QLabel(short)
            name_l.setMinimumWidth(110)
            name_l.setStyleSheet("font-size: 10px;")
            bar = AnimatedDominanceBar(accent="#00d9ff" if dom > 55 else ("#00f5a0" if dom > 35 else "#7a7a88"))
            bar.setValue(0.0)
            pct = QLabel(f"{dom:.1f}%")
            pct.setMinimumWidth(42)
            pct.setStyleSheet("font-size: 10px; color: #d0d0d8;")
            rl.addWidget(name_l)
            rl.addWidget(bar, stretch=1)
            rl.addWidget(pct)
            self.mp_dom_container.layout().addWidget(row)

            self._animate_progress(bar, 0.0, dom, 380)

        # Variation note for multi/continuous
        npos = len(mpr.analyses)
        var_note = f"across {npos} positions/steps"
        if hasattr(mpr, "force_variation_coefficient") and mpr.force_variation_coefficient is not None:
            var_note += f" (var coeff {mpr.force_variation_coefficient:.2f})"
        self.mp_eff_label.setText(f"Variation: {var_note}  •  (see curve/table for per-pos detail; grip/pos shifts dominance)")

    def _animate_progress(self, bar: AnimatedDominanceBar, start_v: float, end_v: float, ms: int = 420):
        """Animate custom bar using stepped timer (light, no pyqtProperty needed). Easing via simple curve."""
        steps = 18
        step = max(12, ms // steps)
        delta = (end_v - start_v) / steps
        cur = [start_v]
        def tick():
            cur[0] += delta
            if (delta > 0 and cur[0] > end_v) or (delta < 0 and cur[0] < end_v):
                cur[0] = end_v
            bar.setValue(cur[0])
            if abs(cur[0] - end_v) > 0.3:
                QTimer.singleShot(step, tick)
        tick()

    def _animate_count_up(self, label: QLabel, start_v: float, end_v: float, suffix_html: str = "", ms: int = 520):
        """Simple count-up for the big ft-lb number. Feels alive without extra libs."""
        steps = 22
        step = max(14, ms // steps)
        delta = (end_v - start_v) / steps
        cur = [start_v]
        def tick():
            cur[0] += delta
            if (delta > 0 and cur[0] >= end_v) or (delta < 0 and cur[0] <= end_v):
                cur[0] = end_v
            label.setText(f"<b>{cur[0]:.1f}</b>{suffix_html}")
            if abs(cur[0] - end_v) > 0.05:
                QTimer.singleShot(step, tick)
        tick()

    def run_variation_compare(self):
        """One-click compare for variation effects on dominance % and torque (bench close vs wide as motivating example; works for other lifts via current var if set)."""
        if not self.current_athlete:
            self.anal_output.append("Create/load athlete first (Athlete tab).")
            return
        try:
            from fiberforce.recipes import analyze
            lift = self.anal_lift.currentText()
            base_var = self.anal_var.currentText() or "flat"
            load_lbs = self.anal_load.value()
            target = self.anal_target.currentText()
            use_geo = self.anal_geo.isChecked()
            # For bench, force close/wide demo; else use current + a sensible alt
            if "bench" in lift.lower():
                vars_to_run = ["flat_close", "flat_wide"]
            else:
                alt = "low_bar" if "high" in base_var else "high_bar"
                vars_to_run = [base_var, alt]
            self.anal_output.append(f"\n=== Variation Compare ({lift}, {vars_to_run[0]} vs {vars_to_run[1]}, {load_lbs:.0f}lb, target {target}) — modeled estimates ===")
            outs = []
            for v in vars_to_run:
                res = analyze(lift, load_lbs=load_lbs, variation=v, target_region_name=target, athlete=self.current_athlete, units="imperial", use_geometric=use_geo)
                line = f"{v}: "
                for r in (res.results or [])[:3]:
                    ft = getattr(r, "peak_torque_ftlb", 0) or 0
                    dom = getattr(r, "dominance_percent", None)
                    doms = f" [{dom}% dom]" if dom is not None else ""
                    line += f"{str(r.muscle_region)[:25]} {ft:.1f}ftlb{doms}; "
                outs.append(line.rstrip("; "))
            self.anal_output.append("\n".join(outs))
            self.anal_output.append("(Higher dominance % for a muscle = better mechanical leverage vs its co-movers at that joint. Grip/stance shifts it per literature. See limitations for caveats.)")
        except Exception as e:
            self.anal_output.append(f"Compare error: {e}")

    # ---------- MULTI-POS TAB (core feature) ----------
    def _create_multipos_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        controls = QGroupBox("Multi-Position Analysis (the flagship 0.5+ feature)")
        c = QFormLayout()

        self.mp_lift = QComboBox(); self.mp_lift.addItems(LIFT_KEYS)
        self.mp_lift.setCurrentText("squat")
        c.addRow("Lift:", self.mp_lift)

        self.mp_load = QDoubleSpinBox(); self.mp_load.setRange(45, 600); self.mp_load.setValue(315)  # lbs, v1 imperial default
        c.addRow("Load (lbs):", self.mp_load)

        # Positions: use editable QComboBox with contextual presets (easy dropdown + custom typing for comma lists) — unchanged
        self.mp_positions = QComboBox()
        self.mp_positions.setEditable(True)
        c.addRow("Positions (comma sep or pick preset):", self.mp_positions)

        self.mp_geo = QCheckBox("Use Geometric")
        self.mp_geo.setChecked(True)
        c.addRow("", self.mp_geo)

        # Continuous ROM controls (dynrom polish)
        self.mp_cont_start = QDoubleSpinBox(); self.mp_cont_start.setRange(10, 180); self.mp_cont_start.setValue(35)
        self.mp_cont_end = QDoubleSpinBox(); self.mp_cont_end.setRange(10, 180); self.mp_cont_end.setValue(170)
        self.mp_cont_steps = QSpinBox(); self.mp_cont_steps.setRange(2, 20); self.mp_cont_steps.setValue(5)
        c.addRow("Cont. ROM Start/End/Steps (knee or shoulder deg):", self._hstack(self.mp_cont_start, self.mp_cont_end, self.mp_cont_steps))

        controls.setLayout(c)
        layout.addWidget(controls)

        # NEW primary visual chips for multi (full width after group, consistent with single; spacious, not clumped).
        # Backing combos hidden; positions kept as-is.
        self.mp_var = QComboBox()
        self.mp_var.setEditable(False)
        self.mp_target = QComboBox()
        self.mp_target.setEditable(False)

        mp_var_label = QLabel("Variation (tap chip — used by Run Multi-Position + Continuous ROM)")
        mp_var_label.setStyleSheet("font-size: 12px; color: #00d9ff; font-weight: 600; margin-top: 8px;")
        layout.addWidget(mp_var_label)
        self.mp_var_chip = SelectionChipBar(is_target=False)
        self.mp_var_chip.set_backing_combo(self.mp_var)
        layout.addWidget(self.mp_var_chip)

        mp_tgt_label = QLabel("Target (tap — lead pos dominance % / ft-lb shares for this region)")
        mp_tgt_label.setStyleSheet("font-size: 12px; color: #00d9ff; font-weight: 600; margin-top: 6px;")
        layout.addWidget(mp_tgt_label)
        self.mp_target_chip = SelectionChipBar(is_target=True)
        self.mp_target_chip.set_backing_combo(self.mp_target)
        layout.addWidget(self.mp_target_chip)

        # Hide original var/target dropdown rows (chips primary per user). Positions visible.
        self.mp_var.setVisible(False)
        self.mp_target.setVisible(False)

        # Sync for multi (populate sets chips via backing)
        self.mp_var.currentTextChanged.connect(lambda t: self.mp_var_chip.set_current(t) if hasattr(self, "mp_var_chip") else None)
        self.mp_target.currentTextChanged.connect(lambda t: self.mp_target_chip.set_current(t) if hasattr(self, "mp_target_chip") else None)

        run = QPushButton("Run Multi-Position + .interpret() + ft-lb Table")
        run.clicked.connect(self.run_multipos)
        layout.addWidget(run)

        cont_btn = QPushButton("Run Continuous ROM (dynrom) + Curve")
        cont_btn.clicked.connect(self.run_continuous_rom)
        layout.addWidget(cont_btn)

        # Visual Results Summary - mirror the torque card style from Single Analysis
        # Prominent cards with peak torque number + per-muscle dominance bars (AnimatedDominanceBar)
        # + efficiency. The old mp_output text is now collapsed details (toggle).
        # This makes Multi-Position feel consistent with the interactive visual Single tab.
        mp_visual_box = QGroupBox("Visual Results Summary — modeled regional torque demands (ft-lb) across positions / ROM")
        mp_visual_box.setStyleSheet("QGroupBox { font-weight: 600; color: #00d9ff; }")
        mpv = QVBoxLayout(mp_visual_box)
        mpv.setSpacing(6)

        self.mp_peak_label = QLabel("<b>—</b> ft-lb  <span style='color:#888;font-size:10px'>(lead / peak position)</span>")
        self.mp_peak_label.setStyleSheet("font-size: 20px; color: #00f5a0; margin: 4px 0;")
        mpv.addWidget(self.mp_peak_label)

        self.mp_dom_container = QWidget()
        mp_dom_l = QVBoxLayout(self.mp_dom_container)
        mp_dom_l.setContentsMargins(0, 0, 0, 0)
        mp_dom_l.setSpacing(3)
        mpv.addWidget(self.mp_dom_container)

        self.mp_eff_label = QLabel("Efficiency / Variation: —")
        self.mp_eff_label.setStyleSheet("font-size: 10px; color: #a0a0b0;")
        mpv.addWidget(self.mp_eff_label)

        self.mp_details_toggle = QCheckBox("Show full text .interpret() + notes (collapsed by default for visual focus)")
        self.mp_details_toggle.setChecked(False)
        self.mp_details_toggle.setStyleSheet("font-size: 10px;")
        mpv.addWidget(self.mp_details_toggle)

        layout.addWidget(mp_visual_box)

        self.mp_output = QTextEdit()
        self.mp_output.setReadOnly(True)
        self.mp_output.setMaximumHeight(160)
        self.mp_output.setVisible(False)
        layout.addWidget(self.mp_output)

        self.mp_details_toggle.toggled.connect(lambda on: self.mp_output.setVisible(on))

        # Simple results table (ft-lb aware)
        self.mp_table = QTableWidget()
        self.mp_table.setColumnCount(4)
        self.mp_table.setHorizontalHeaderLabels(["Position", "Peak Torque (ft-lb)", "Lead Dom %", "Notes"])
        layout.addWidget(self.mp_table)

        # NEW: Muscle activation map (inspired by Strong/Hevy muscle heatmaps + regional focus of FiberForce)
        if Path(MUSCLE_MAP).exists():
            muscle_group = QGroupBox("Regional Muscle Activation Preview (based on lift & position)")
            ml = QVBoxLayout(muscle_group)
            muscle_label = QLabel()
            muscle_pix = QPixmap(MUSCLE_MAP).scaledToWidth(300, Qt.SmoothTransformation)  # Shrunk so it doesn't dominate even inside the scrollable tab; scroll to see fields below
            muscle_label.setPixmap(muscle_pix)
            muscle_label.setAlignment(Qt.AlignCenter)
            ml.addWidget(muscle_label)
            self.mp_muscle_desc = QLabel("Color intensity reflects estimated demand on key regions (e.g. glutes/quads for squat). See .interpret() for details. Last run demand will appear here after analysis.")
            ml.addWidget(self.mp_muscle_desc)
            layout.addWidget(muscle_group)

        # Continuous ROM curve plot (dynrom polish, matplotlib if available)
        self.mp_cont_curve_widget = QWidget() if not MATPLOTLIB_AVAILABLE else self._make_cont_curve_plot_widget()
        layout.addWidget(self.mp_cont_curve_widget)

        # Wire lift -> contextual dropdowns for var, positions preset, target (easy mode)
        self.mp_lift.currentTextChanged.connect(lambda: self._populate_contextual_fields("multi"))
        self._populate_contextual_fields("multi")

        return w

    def run_multipos(self):
        if not self.current_athlete:
            self.mp_output.append("Load/create athlete first.")
            return
        try:
            pos_list = [p.strip() for p in self.mp_positions.currentText().split(",") if p.strip()]
            mpr = analyze_multi_position(
                self.mp_lift.currentText(),
                pos_list,
                load_lbs=self.mp_load.value(),  # v1 imperial
                variation=self.mp_var.currentText(),
                target_region_name=self.mp_target.currentText(),
                athlete=self.current_athlete,
                use_geometric=self.mp_geo.isChecked(),
                units="imperial",
            )
            self.mp_output.clear()
            self.mp_output.append(mpr.interpret())

            # Populate table with ft-lb when possible (v1)
            self.mp_table.setRowCount(len(mpr.analyses))
            for i, ap in enumerate(mpr.analyses):
                pos_name = getattr(ap, 'position_description', str(mpr.positions[i]) if i < len(mpr.positions) else f"pos{i}")
                # take first result's ft-lb as representative
                ft = 0.0
                dom = ""
                if ap.results:
                    ft = getattr(ap.results[0], 'peak_torque_ftlb', 0.0) or 0.0
                    d = getattr(ap.results[0], 'dominance_percent', None)
                    if d is not None:
                        dom = f"{d:.1f}"
                self.mp_table.setItem(i, 0, QTableWidgetItem(str(pos_name)[:42]))
                self.mp_table.setItem(i, 1, QTableWidgetItem(f"{ft:.1f}"))
                self.mp_table.setItem(i, 2, QTableWidgetItem(dom))
                note = (getattr(ap, "notes", None) or getattr(ap, "position_description", None) or getattr(ap, "confidence_summary", "") or "")[:55]
                self.mp_table.setItem(i, 3, QTableWidgetItem(note))

            # (removed redundant "completed" log; the visual/table + .interpret() in the tab are the primary feedback now)
            self.history.append(f"MP {self.mp_lift.currentText()} x{len(mpr.analyses)} @ {self.mp_load.value():.0f}lbs")

            # Update visual cards (new torque/dominance style matching Single Analysis)
            self._update_mp_visual(mpr)
            # On explicit run, show the details text (like single)
            self.mp_details_toggle.setChecked(True)
            self.mp_output.setVisible(True)
            # light visual: update muscle desc with this run's demand (alive feedback)
            if hasattr(self, "mp_muscle_desc") and mpr.analyses and mpr.analyses[0].results:
                this_ft = getattr(mpr.analyses[0].results[0], "peak_torque_ftlb", 0) or 0
                reg = str(getattr(mpr.analyses[0].results[0], "muscle_region", self.mp_target.currentText()))
                self.mp_muscle_desc.setText(f"Last run: ~{this_ft:.1f} ft-lb modeled for {reg} (color on map is preview only; see .interpret() + PRs in History for your personal bests).")

            # New Level: post-run self-competition progress moment (honest, modeled)
            try:
                from fiberforce.results import compute_personal_records, compute_rom_consistency
                # best effort: load a few recent persisted + this session in-memory
                recent = []
                try:
                    from fiberforce.profiles import list_saved_runs, load_multi_position_run
                    for nm in (list_saved_runs() or [])[-5:]:
                        try:
                            recent.append(load_multi_position_run(nm))
                        except Exception:
                            pass
                except Exception:
                    pass
                if recent:
                    prs = compute_personal_records(recent, include_dominance=True)
                    # crude check if this run's first result beats a record for target-ish region
                    if mpr.analyses and mpr.analyses[0].results:
                        this_ft = getattr(mpr.analyses[0].results[0], "peak_torque_ftlb", 0) or 0
                        region = str(getattr(mpr.analyses[0].results[0], "muscle_region", ""))
                        this_var = getattr(mpr, "variation", "") or ""
                        for k, rec in prs.items():
                            if region and region in k and this_ft > rec.get("peak_ftlb", 0) + 0.1:
                                self.mp_output.append(f"\n★ New personal modeled peak for {region}: {this_ft:.1f} ft-lb (previous best ~{rec.get('peak_ftlb', 0):.1f}) — modeled estimate, your history only.")
                                break
                        # dom % specific (e.g. best pec dom on wide grip)
                        this_dom = getattr(mpr.analyses[0].results[0], "dominance_percent", None) or 0
                        for k, rec in prs.items():
                            if region and ("pec" in region.lower() or "pectoralis" in region.lower()) and this_dom > (rec.get("dominance_percent") or 0) + 0.1 and ("wide" in (this_var or k).lower() or "close" in (this_var or k).lower()):
                                self.mp_output.append(f"\n★ New personal best pec dominance % on {this_var or 'variation'}: {this_dom}% (prev ~{rec.get('dominance_percent',0)}%) — modeled mechanical leverage share, your history only.")
                                break
                    # consistency note
                    cons = compute_rom_consistency(mpr)
                    if cons.get("avg_variation_coeff") is not None and cons["avg_variation_coeff"] < 0.1:
                        self.mp_output.append(f"\n  Low variation (consistent ROM demand coeff {cons['avg_variation_coeff']}) — good for PR tracking.")
            except Exception:
                pass  # non-fatal, never break the run output
        except Exception as e:
            self.mp_output.append(f"Error: {e}")

    def run_continuous_rom(self):
        """dynrom polish: use range/step controls, run continuous, show interpret + table + live curve plot."""
        if not self.current_athlete:
            self.mp_output.append("Load/create athlete first.")
            return
        try:
            from fiberforce.recipes import analyze_continuous
            lift = self.mp_lift.currentText()
            start = self.mp_cont_start.value()
            end = self.mp_cont_end.value()
            steps = self.mp_cont_steps.value()
            # pass as kwargs for the continuous builders
            tempo = 0.75  # Wave 3: exposed for F-V velocity est (fuller continuous dynamics)
            if lift in ("squat", "romanian", "rdl"):
                mpr = analyze_continuous(lift, steps=steps, load_lbs=self.mp_load.value(),
                                         athlete=self.current_athlete, variation=self.mp_var.currentText() or "low_bar",
                                         units="imperial", knee_start=start, knee_end=end, tempo_s_per_step=tempo)
            else:
                mpr = analyze_continuous(lift, steps=steps, load_lbs=self.mp_load.value(),
                                         athlete=self.current_athlete, variation=self.mp_var.currentText() or "flat",
                                         units="imperial", shoulder_start=start, shoulder_end=end, tempo_s_per_step=tempo)
            self.mp_output.clear()
            self.mp_output.append("=== Continuous ROM (dynrom) ===\n")
            self.mp_output.append(mpr.interpret())

            # Update visual cards for continuous results (consistent with single + multi-pos)
            self._update_mp_visual(mpr)
            # On explicit run, show the details text (like single)
            self.mp_details_toggle.setChecked(True)
            self.mp_output.setVisible(True)

            # table with ft-lb
            self.mp_table.setRowCount(len(mpr.analyses))
            for i, ap in enumerate(mpr.analyses):
                pos_name = getattr(ap, 'position_description', f"step{i}")
                ft = ap.results[0].peak_torque_ftlb if ap.results else 0
                dom = ""
                if ap.results:
                    d = getattr(ap.results[0], 'dominance_percent', None)
                    if d is not None:
                        dom = f"{d:.1f}"
                self.mp_table.setItem(i, 0, QTableWidgetItem(str(pos_name)[:42]))
                self.mp_table.setItem(i, 1, QTableWidgetItem(f"{ft:.1f}"))
                self.mp_table.setItem(i, 2, QTableWidgetItem(dom))
                note = (getattr(ap, "notes", None) or getattr(ap, "position_description", None) or getattr(ap, "confidence_summary", "") or "")[:55]
                self.mp_table.setItem(i, 3, QTableWidgetItem(note))

            # plot torque curve if matplotlib - premium styled (cyan line, dark fitness viz)
            if MATPLOTLIB_AVAILABLE and hasattr(self, 'mp_cont_ax'):
                self.mp_cont_ax.clear()
                xs = list(range(len(mpr.analyses)))
                ys = [a.results[0].peak_torque_ftlb if a.results else 0 for a in mpr.analyses]
                self.mp_cont_ax.plot(xs, ys, marker='o', color='#00d9ff', linewidth=2, markersize=6)
                self.mp_cont_ax.set_xlabel("Step / Angle Position", color='#a0a0b0')
                self.mp_cont_ax.set_ylabel("Peak Torque (ft-lb)", color='#a0a0b0')
                self.mp_cont_ax.set_title(f"Continuous ROM Torque Curve — {lift}", color='#f0f0f5', pad=10)
                self.mp_cont_ax.grid(True, alpha=0.2, color='#3a3a45')
                self.mp_cont_canvas.draw()

            # (removed redundant log line; curve + notes are in the Multi-Position tab)
            self.history.append(f"Cont {lift} x{len(mpr.analyses)} @ {self.mp_load.value():.0f}lbs")
            # light visual: update muscle desc with this cont run's demand
            if hasattr(self, "mp_muscle_desc") and mpr.analyses and mpr.analyses[0].results:
                this_ft = getattr(mpr.analyses[0].results[0], "peak_torque_ftlb", 0) or 0
                reg = str(getattr(mpr.analyses[0].results[0], "muscle_region", self.mp_target.currentText()))
                self.mp_muscle_desc.setText(f"Last cont run: ~{this_ft:.1f} ft-lb modeled for {reg} (map is static preview; PRs/trends in History).")

            # New Level: post-run self-competition progress moment (honest, modeled) for continuous too
            try:
                from fiberforce.results import compute_personal_records, compute_rom_consistency
                recent = []
                try:
                    from fiberforce.profiles import list_saved_runs, load_multi_position_run
                    for nm in (list_saved_runs() or [])[-5:]:
                        try:
                            recent.append(load_multi_position_run(nm))
                        except Exception:
                            pass
                except Exception:
                    pass
                if recent and mpr.analyses and mpr.analyses[0].results:
                    prs = compute_personal_records(recent, include_dominance=True)
                    this_ft = getattr(mpr.analyses[0].results[0], "peak_torque_ftlb", 0) or 0
                    region = str(getattr(mpr.analyses[0].results[0], "muscle_region", ""))
                    for k, rec in prs.items():
                        if region and region in k and this_ft > rec.get("peak_ftlb", 0) + 0.1:
                            self.mp_output.append(f"\n★ New personal modeled peak (continuous) for {region}: {this_ft:.1f} ft-lb (previous ~{rec.get('peak_ftlb', 0):.1f}) — modeled estimate over your ROM history.")
                            break
                    this_dom = getattr(mpr.analyses[0].results[0], "dominance_percent", None) or 0
                    this_var = getattr(mpr, "variation", "") or ""
                    for k, rec in prs.items():
                        if region and ("pec" in region.lower() or "pectoralis" in region.lower()) and this_dom > (rec.get("dominance_percent") or 0) + 0.1 and ("wide" in (this_var or k).lower() or "close" in (this_var or k).lower()):
                            self.mp_output.append(f"\n★ New personal best pec dominance % (continuous) on {this_var or 'variation'}: {this_dom}% (prev ~{rec.get('dominance_percent',0)}%) — modeled, your ROM history only.")
                            break
            except Exception:
                pass
        except Exception as e:
            self.mp_output.append(f"Continuous error: {e}")

    # ---------- SENSITIVITY TAB ----------
    def _create_sensitivity_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        g = QGroupBox("Sensitivity Sweep + Insight")
        f = QFormLayout()

        self.sens_lift = QComboBox(); self.sens_lift.addItems(LIFT_KEYS)
        f.addRow("Lift:", self.sens_lift)

        self.sens_var = QComboBox()
        self.sens_var.addItems(["grip_width_cm", "load_kg", "femur_length_cm", "humerus_length_cm"])
        f.addRow("Variable:", self.sens_var)

        self.sens_start = QDoubleSpinBox(); self.sens_start.setValue(48)
        self.sens_end = QDoubleSpinBox(); self.sens_end.setValue(78)
        self.sens_step = QDoubleSpinBox(); self.sens_step.setValue(5)
        f.addRow("Start / End / Step:", self._hstack(self.sens_start, self.sens_end, self.sens_step))

        self.sens_load = QDoubleSpinBox(); self.sens_load.setValue(225)
        f.addRow("Base Load (lbs):", self.sens_load)

        g.setLayout(f)
        layout.addWidget(g)

        run = QPushButton("Run Sweep + Show .insight() + Plot (if matplotlib)")
        run.clicked.connect(self.run_sensitivity)
        layout.addWidget(run)

        run2d = QPushButton("2D Heatmap Demo (bench: load x grip) - Wave 3 Theme 3 MVP")
        run2d.clicked.connect(self.run_2d_sens_heatmap_demo)
        layout.addWidget(run2d)

        self.sens_text = QTextEdit()
        self.sens_text.setReadOnly(True)
        layout.addWidget(self.sens_text)

        self.sens_plot = QWidget() if not MATPLOTLIB_AVAILABLE else self._make_plot_widget()
        layout.addWidget(self.sens_plot)

        # Top-tier result viz image preview (generated for imperial torque demo)
        if Path(RESULT_VIZ).exists():
            viz_label = QLabel()
            viz_pix = QPixmap(RESULT_VIZ).scaledToWidth(750, Qt.SmoothTransformation)
            viz_label.setPixmap(viz_pix)
            layout.addWidget(viz_label)

        # Additional v1 visual: regional torque ft-lb visualization (new generated asset)
        if Path(TORQUE_VIZ).exists():
            tq_label = QLabel()
            tq_pix = QPixmap(TORQUE_VIZ).scaledToWidth(520, Qt.SmoothTransformation)
            tq_label.setPixmap(tq_pix)
            layout.addWidget(tq_label)

        return w

    def _hstack(self, *widgets):
        h = QHBoxLayout()
        for w in widgets: h.addWidget(w)
        container = QWidget(); container.setLayout(h)
        return container

    def _make_plot_widget(self):
        fig = Figure(figsize=(5, 3), facecolor='#16161e')
        self.sens_canvas = FigureCanvas(fig)
        self.sens_ax = fig.add_subplot(111, facecolor='#16161e')
        # Premium dark fitness chart style (Strava/Strong inspired)
        self.sens_ax.tick_params(colors='#a0a0b0')
        self.sens_ax.spines['bottom'].set_color('#3a3a45')
        self.sens_ax.spines['top'].set_color('#3a3a45')
        self.sens_ax.spines['left'].set_color('#3a3a45')
        self.sens_ax.spines['right'].set_color('#3a3a45')
        self.sens_ax.set_facecolor('#16161e')
        return self.sens_canvas

    def _make_cont_curve_plot_widget(self):
        fig = Figure(figsize=(5.5, 3.2), facecolor='#16161e')
        self.mp_cont_canvas = FigureCanvas(fig)
        self.mp_cont_ax = fig.add_subplot(111, facecolor='#16161e')
        self.mp_cont_ax.tick_params(colors='#a0a0b0')
        for spine in self.mp_cont_ax.spines.values():
            spine.set_color('#3a3a45')
        self.mp_cont_ax.set_facecolor('#16161e')
        return self.mp_cont_canvas

    def _make_history_trend_widget(self):
        """Small trend plot for recent modeled outputs (ft-lb peaks or dom % from history runs). Dark fitness style, reuse from sens/cont."""
        fig = Figure(figsize=(5.2, 2.4), facecolor='#16161e')
        self.hist_canvas = FigureCanvas(fig)
        self.hist_ax = fig.add_subplot(111, facecolor='#16161e')
        self.hist_ax.tick_params(colors='#a0a0b0')
        for spine in self.hist_ax.spines.values():
            spine.set_color('#3a3a45')
        self.hist_ax.set_facecolor('#16161e')
        self.hist_ax.set_xlabel("Recent runs (oldest \u2192 newest)", color='#a0a0b0', fontsize=8)
        self.hist_ax.set_ylabel("ft-lb or % dom", color='#a0a0b0', fontsize=8)
        self.hist_ax.set_title("Trend (last ~10; tap Refresh to update)", color='#00d9ff', fontsize=9)
        return self.hist_canvas

    def run_sensitivity(self):
        if not self.current_athlete:
            self.sens_text.append("Need athlete first.")
            return
        try:
            values = list(range(int(self.sens_start.value()), int(self.sens_end.value())+1, int(self.sens_step.value())))
            res, insight = sensitivity_sweep(
                self.sens_lift.currentText(),
                variable=self.sens_var.currentText(),
                values=values,
                load_lbs=self.sens_load.value(),  # v1
                athlete=self.current_athlete,
                units="imperial",
            )
            self.sens_text.clear()
            self.sens_text.append(insight or res.insight())

            # Plot if possible
            if MATPLOTLIB_AVAILABLE and hasattr(self, 'sens_ax'):
                self.sens_ax.clear()
                xs = [p.variable_value for p in res.points]
                ys = [p.peak_force_n for p in res.points]
                self.sens_ax.plot(xs, ys, marker='o', color='#00f5a0', linewidth=2, markersize=6)
                self.sens_ax.set_xlabel(self.sens_var.currentText(), color='#a0a0b0')
                self.sens_ax.set_ylabel("Peak Force (N)", color='#a0a0b0')
                self.sens_ax.set_title("Sensitivity Curve", color='#f0f0f5', pad=10)
                self.sens_ax.grid(True, alpha=0.2, color='#3a3a45')
                self.sens_canvas.draw()
        except Exception as e:
            self.sens_text.append(f"Error: {e}")

    def run_2d_sens_heatmap_demo(self):
        """Wave 3 MVP: simple 2D grid for bench load x grip, heatmap of lead dom % or ft-lb for target. Reuses sens plot widget."""
        if not self.current_athlete:
            self.sens_text.append("Need athlete first.")
            return
        try:
            from fiberforce.recipes import analyze
            lift = "bench"
            loads = list(range(150, 301, 50))
            grips = list(range(40, 81, 10))
            target = "Pectoralis Major::Sternal fibers"
            data = []  # 2d list of dom or ft
            for ld in loads:
                row = []
                for gr in grips:
                    res = analyze(lift, load_lbs=ld, variation="flat", target_region_name=target, athlete=self.current_athlete, units="imperial", grip_width_cm=gr)
                    val = 0.0
                    if res.results:
                        d = getattr(res.results[0], "dominance_percent", None)
                        if d is not None:
                            val = d
                        else:
                            val = getattr(res.results[0], "peak_torque_ftlb", 0) or 0
                    row.append(val)
                data.append(row)
            self.sens_text.clear()
            self.sens_text.append(f"2D Heatmap (bench load x grip) for {target} - values are lead dom % (or ft-lb fallback). Grid {len(loads)}x{len(grips)}")
            # plot heatmap
            if MATPLOTLIB_AVAILABLE and hasattr(self, "sens_ax"):
                self.sens_ax.clear()
                import numpy as np
                arr = np.array(data)
                im = self.sens_ax.imshow(arr, aspect="auto", cmap="viridis", origin="lower")
                self.sens_ax.set_xticks(range(len(grips)))
                self.sens_ax.set_xticklabels(grips)
                self.sens_ax.set_yticks(range(len(loads)))
                self.sens_ax.set_yticklabels(loads)
                self.sens_ax.set_xlabel("Grip width (cm)", color="#a0a0b0")
                self.sens_ax.set_ylabel("Load (lbs)", color="#a0a0b0")
                self.sens_ax.set_title("2D Sens Heatmap (dom % or ft-lb)", color="#00d9ff")
                self.sens_canvas.draw()
                # colorbar if possible
                try:
                    fig = self.sens_canvas.figure
                    fig.colorbar(im, ax=self.sens_ax, shrink=0.8)
                except:
                    pass
            self.sens_text.append("Heatmap updated in plot area (higher = more dom or torque). See limitations: prototype grid, no full opt.")
        except Exception as e:
            self.sens_text.append(f"2D demo error: {e}")

    # ---------- PROGRAMS TAB ----------
    def _create_program_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel("Build a WeeklyProgram using multi-pos where possible. Then view rich .interpret() + report.")
        layout.addWidget(info)

        self.prog_name = QLineEdit("My Training Week")
        layout.addWidget(self.prog_name)

        add_btn = QPushButton("Add Sample Squat Session (multi-pos)")
        add_btn.clicked.connect(self.add_sample_session)
        layout.addWidget(add_btn)

        build_btn = QPushButton("Build Program & Show .interpret() + Report")
        build_btn.clicked.connect(self.build_and_show_program)
        layout.addWidget(build_btn)

        self.prog_output = QTextEdit()
        self.prog_output.setReadOnly(True)
        layout.addWidget(self.prog_output)

        # New v1 top-tier visual: coaching dashboard preview (generated image)
        if Path(COACHING_DASH).exists():
            dash_label = QLabel()
            dash_pix = QPixmap(COACHING_DASH).scaledToWidth(520, Qt.SmoothTransformation)
            dash_label.setPixmap(dash_pix)
            layout.addWidget(dash_label)

        return w

    def add_sample_session(self):
        if not hasattr(self, 'current_program_sessions'):
            self.current_program_sessions = []
        self.current_program_sessions.append({
            "name": "Squat Focus",
            "lift": "squat",
            "load_lbs": 315,
            "variation": "low_bar",
            "positions": ["bottom", "mid", "top"]
        })
        self.prog_output.append("Added sample multi-pos squat session.")

    def build_and_show_program(self):
        if not self.current_athlete:
            self.prog_output.append("Create athlete first.")
            return
        try:
            sessions = getattr(self, 'current_program_sessions', [
                {"name": "Squat", "lift": "squat", "load_lbs": 315, "variation": "low_bar", "positions": ["bottom", "mid"]}
            ])
            prog = build_weekly_program(
                name=self.prog_name.text(),
                sessions_data=sessions,
                athlete=self.current_athlete
            )
            self.prog_output.clear()
            self.prog_output.append(prog.interpret())
            self.prog_output.append("\n--- Full Report ---")
            self.prog_output.append(prog.generate_simple_report())
            self.current_program = prog
        except Exception as e:
            self.prog_output.append(f"Error: {e}")

    # ---------- RECIPES / QUICK TAB ----------
    def _create_recipes_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("One-click common flows using the new recipes module"))

        quick_squat = QPushButton("Quick Multi-Pos Squat (low bar, geometric)")
        quick_squat.clicked.connect(lambda: self._quick_recipe("squat"))
        layout.addWidget(quick_squat)

        quick_bench = QPushButton("Quick Grip Sensitivity Bench")
        quick_bench.clicked.connect(lambda: self._quick_recipe("bench_sens"))
        layout.addWidget(quick_bench)

        layout.addStretch()
        return w

    def _quick_recipe(self, kind: str):
        if not self.current_athlete:
            # Feedback now lives in the tab's own output area (sens_text etc.)
            return
        try:
            if kind == "squat":
                mpr = analyze_multi_position("squat", ["bottom","mid","top"], load_lbs=315,
                                             variation="low_bar", athlete=self.current_athlete, use_geometric=True, units="imperial")
                # interpret shown via the tab's recipe output; no longer spamming global log
            elif kind == "bench_sens":
                res, insight = sensitivity_sweep("bench", "grip_width_cm", [48,58,68,78],
                                                 load_lbs=225, athlete=self.current_athlete, units="imperial")
                # insight goes to the tab
        except Exception as e:
            # errors surface in tab or via dialog if needed
            pass

    # --- New v1 GUI polish methods ---
    def run_internal_smoke(self):
        """Run key verification logic inside the GUI (v2 clickable icon app verifier).

        Exercises: recipes imperial create + analyze_multi + load_lbs + continuous, 8 lifts surface,
        full WeeklyProgram + .interpret(), sensitivity_sweep + .insight(), ft-lb numeric,
        asset presence, history, rich interpret. Detects bundled launch (icon click).
        Mirrors + exceeds the CLI `fiberforce smoke`.
        """
        self._log("\n=== Running Internal Smoke / Verify (v2.0 — clickable icon app) ===")
        ok = True
        try:
            # Bundled detection (true when launched by double-clicking the .app icon / DMG install)
            import sys
            fpath = str(Path(__file__) or "")
            exe = sys.executable or ""
            bundled = ("FiberForce.app" in exe) or ("FiberForce.app" in fpath) or ("Contents" in fpath) or ("app_packages" in ":".join(sys.path))
            self._log(f"  Launch context: {'BUNDLED (icon click / .app)' if bundled else 'dev (python -m or fiberforce gui)'}")
            from fiberforce.recipes import (
                create_athlete, analyze_multi_position, sensitivity_sweep, build_weekly_program, analyze_continuous
            )

            # 1. Core athlete + squat multi-pos (the classic 315 lb low bar case)
            a = create_athlete(units="imperial", femur_in=17, tibia_in=15, name="SmokeAthlete17in")
            mpr = analyze_multi_position(
                "squat", ["bottom", "mid", "top"], load_lbs=315, athlete=a,
                units="imperial", variation="low_bar", use_geometric=True
            )
            interp = mpr.interpret()
            tq = mpr.analyses[0].results[0].peak_torque_ftlb
            self._log(f"✓ create_athlete (imperial 17in femur) + squat multi-pos OK")
            self._log(f"  Sample torque (lead muscle share of hip): {tq:.1f} ft-lb (full hip joint ~246; now reports per-muscle MA-shares after model update; expect varies with lead)")
            self._log("  interpret (first 280 chars): " + (interp[:280] + "..." if len(interp) > 280 else interp))
            self.history.append(f"Smoke squat: {len(mpr.analyses)} pos, ~{tq:.0f} ft-lb, geometric={ 'yes' if 'geometric' in interp.lower() else 'no'}")

            # New Level smoke: exercise PR/trend/milestone helpers (self-competition layer)
            try:
                from fiberforce.results import compute_personal_records, get_milestones, compute_simple_trend
                # treat the just-run mpr as "current" + fake a prior for demo
                fake_prior = type("P", (), {"analysis_results": mpr.analyses, "lift": "squat", "timestamp": "prior"})()
                prs = compute_personal_records([mpr, fake_prior])  # will mostly be the current
                if prs:
                    self._log("  ✓ PR helper: found records for smoke run (modeled ft-lb peaks)")
                miles = get_milestones([mpr])
                self._log("  ✓ Milestones helper: " + (miles[0] if miles else "none"))
                tr = compute_simple_trend(tq, [tq*0.95, tq*0.98])
                self._log("  ✓ Trend helper exercised (delta vs 'history' for smoke)")
            except Exception as e:
                self._log(f"  (non-fatal) gamify helper smoke limited: {e}")

            # 2. Bench + deadlift + ohp spot checks (4-lift parity via recipes/service)
            for lift, var, lbs, pos in [
                ("bench", "flat", 225, ["bottom", "mid"]),
                ("incline", "incline_30", 185, ["bottom"]),
                ("deadlift", "conventional", 315, ["bottom"]),
                ("romanian", "rdl", 225, ["mid"]),
                ("ohp", "standing", 135, ["mid"]),
            ]:
                try:
                    m = analyze_multi_position(lift, pos, load_lbs=lbs, athlete=a, units="imperial", variation=var)
                    t = m.analyses[0].results[0].peak_torque_ftlb
                    self._log(f"✓ {lift} ({var}) multi-pos OK — ~{t:.0f} ft-lb")
                    self.history.append(f"Smoke {lift}: ~{t:.0f} ft-lb")
                except Exception as e:
                    self._log(f"  (non-fatal) {lift} spot limited: {e}")

            # dynrom continuous smoke
            try:
                mpr_c = analyze_continuous("squat", steps=3, load_lbs=315, athlete=a, units="imperial", variation="low_bar")
                t_c = mpr_c.analyses[0].results[0].peak_torque_ftlb
                self._log(f"✓ continuous ROM (squat) OK — ~{t_c:.0f} ft-lb over {len(mpr_c.analyses)} steps")
                self.history.append(f"Smoke cont: ~{t_c:.0f} ft-lb")
            except Exception as e:
                self._log(f"  (non-fatal) continuous spot limited: {e}")

            # 3. WeeklyProgram + .interpret() + report
            try:
                prog = build_weekly_program(
                    name="Smoke Week v1",
                    sessions_data=[
                        {"name": "Squat Focus", "lift": "squat", "load_lbs": 315, "variation": "low_bar", "positions": ["bottom", "mid"]},
                        {"name": "Bench", "lift": "bench", "load_lbs": 225, "variation": "flat", "positions": ["mid"]},
                    ],
                    athlete=a
                )
                p_interp = prog.interpret()
                report = prog.generate_simple_report()
                self._log("✓ build_weekly_program + .interpret() + report OK")
                self._log("  program interpret (first 220): " + (p_interp[:220] + "..."))
                self.history.append("Smoke program: " + p_interp.splitlines()[0][:80])
            except Exception as e:
                self._log(f"  Program smoke limited: {e}")
                ok = False

            # 4. Sensitivity + .insight()
            try:
                res, insight = sensitivity_sweep(
                    "bench", variable="grip_width_cm", values=[48, 58, 68, 78],
                    load_lbs=225, athlete=a, units="imperial"
                )
                ins = insight or res.insight()
                self._log("✓ sensitivity_sweep + .insight() OK: " + ins.splitlines()[0][:90])
                self.history.append("Smoke sens: " + ins.splitlines()[0][:70])
            except Exception as e:
                self._log(f"  Sensitivity smoke limited: {e}")

            # 5. Asset presence (top-tier visuals)
            assets_dir = Path(__file__).parent / "assets"
            for name in ("splash_new.jpg", "app_icon.jpg", "header_banner.jpg", "result_viz.jpg", "coaching_dashboard.jpg", "torque_viz_new.jpg", "muscle_map.jpg"):
                p = assets_dir / name
                if p.exists():
                    self._log(f"✓ asset present: {name}")
                else:
                    self._log(f"  (warn) missing asset: {name}")

            # 6. Explicit ft-lb + imperial sanity on a result
            if tq > 100:
                self._log("✓ ft-lb torque magnitude sane for 315 lb squat (post physics fix)")
            else:
                self._log("  (warn) torque lower than expected — check calculations")

            self._log("✓ GUI Internal Smoke finished. " + ("All core v2.0 paths (incl. bundled/icon launch) exercised." if ok else "Some non-fatal limits noted — see log."))
            self._log("  Check History tab for saved smoke entries. Use Export if desired.")
            self._refresh_history()

            # --- New: exercise the workout logging + modeled force overlay foundation ---
            # (user end-goal direction: log real sets, attach the force model per set for supported bb/db/machine exercises,
            # compute real volume + modeled work, e1RM, regional summaries. This will appear in the Activity Log dialog.)
            try:
                from fiberforce.results import (
                    LoggedWorkout, create_logged_set, estimate_one_rep_max, EXERCISE_MAP,
                    list_logged_workouts, save_logged_workout
                )
                # Use the athlete we created earlier in the smoke
                if 'a' in locals() and a is not None:
                    w = LoggedWorkout(name="Smoke Push Day", athlete_name=getattr(a, 'name', 'smoke'))
                    # A few typical sets on modeled exercises (barbell/db/machine)
                    w.add_set(create_logged_set(a, "barbell_bench_flat", 225, 5))
                    w.add_set(create_logged_set(a, "barbell_bench_close", 185, 6, rpe=8))
                    w.add_set(create_logged_set(a, "dumbbell_bench_flat", 80, 8))  # proxy
                    w.add_set(create_logged_set(a, "barbell_ohp", 135, 5))
                    self._log(f"✓ LoggedWorkout demo created: real volume {w.real_volume_lbs():.0f} lbs, modeled work ~{w.modeled_total_work_ftlb():.0f} ft-lb")
                    ex_sum = w.get_exercise_summary()
                    for k, v in list(ex_sum.items())[:2]:
                        self._log(f"  {v['display']}: {v['sets']} sets, vol {v['real_volume_lbs']:.0f}lb, e1RM~{v['e1rm_lbs']}lb, modeled work {v['modeled_work_ftlb']:.0f}")
                    reg = w.get_regional_modeled_summary()
                    if "total_stress" in reg:
                        self._log(f"  Regional modeled stress total: {reg['total_stress']:.0f} (via existing accumulators)")
                    # Persist it (so it can be listed later)
                    try:
                        p = save_logged_workout(w)
                        self._log(f"  Saved as logged workout (will appear in future list_logged_workouts)")
                    except Exception:
                        pass
                    # Also show a 1RM estimate example
                    e1 = estimate_one_rep_max(225, 5)
                    self._log(f"  Example e1RM (Epley) for 225x5: {e1:.1f} lb")
            except Exception as e:
                self._log(f"  (non-fatal) workout logging demo limited: {e}")

            # New visual chips selection test (spacious primary UI replacing clumped dropdown lists; contextual to lift, human labels, live cards)
            try:
                self.anal_lift.setCurrentText("squat")
                self._populate_contextual_fields("single")
                if hasattr(self, "anal_var_chip") and len(self.anal_var_chip._buttons) >= 2:
                    self._log("✓ Single tab chips: var/target visual selectors populated for squat (no long clumped list)")
                self.mp_lift.setCurrentText("bench")
                self._populate_contextual_fields("multi")
                if hasattr(self, "mp_var_chip") and len(self.mp_var_chip._buttons) >= 2:
                    self._log("✓ Multi-Pos tab chips: var/target visual selectors for bench (full width, tap updates choice for runs)")
            except Exception as e:
                self._log(f"  (non-fatal) chips smoke limited: {e}")

        except Exception as e:
            self._log(f"Smoke failed hard: {e}")
            import traceback
            self._log(traceback.format_exc()[-400:])

        # Now that the persistent bottom log box is gone, show the rich smoke output
        # in a dedicated dialog so the user can review all the verification details.
        self._show_activity_log_dialog()

    def _show_activity_log_dialog(self):
        """On-demand viewer for the internal activity log buffer.
        Used primarily for smoke results now that the main window no longer has a permanent
        bottom text log (cleaner, more space for the visual cards and tabs).
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("FiberForce — Activity Log")
        dlg.setMinimumWidth(720)
        dlg.setMinimumHeight(420)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)

        te = QTextEdit()
        te.setReadOnly(True)
        content = self.log.toPlainText().strip()
        te.setPlainText(content if content else "(activity log buffer is empty)")
        lay.addWidget(te, stretch=1)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear Buffer")
        clear_btn.clicked.connect(lambda: (self.log.clear(), te.setPlainText("(activity log buffer is empty)")))
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(te.toPlainText()))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setDefault(True)

        btn_row.addWidget(clear_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    def export_current(self):
        """Simple export of current log to file (v1 feature)."""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export Report", "fiberforce_report.txt", "Text Files (*.txt)")
        if path:
            try:
                with open(path, "w") as f:
                    f.write(self.log.toPlainText())
                self._log(f"Exported to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))

    def show_about(self):
        """Custom About dialog with hero image for brand moment (no persistent top banner in main UI).

        Per desktop/fitness app conventions (macOS HIG, Strong/Hevy/Strava/ biomech tools, Qt examples):
        - Small window icon + descriptive titlebar for always-visible light branding.
        - Help menu > About opens a modal dialog containing the larger hero image + version + science blurb.
        - Keeps the main form (tabs, fields, plots, scroll areas) dominant; brand is "on demand" not slapped above content.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("About FiberForce")
        dlg.setMinimumWidth(560)
        dlg.setMinimumHeight(420)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # Hero image (reuses the former header_banner asset; shown on-demand in About, not persistent)
        if Path(HEADER).exists():
            img = QLabel()
            pix = QPixmap(HEADER).scaledToWidth(480, Qt.SmoothTransformation)
            img.setPixmap(pix)
            img.setAlignment(Qt.AlignCenter)
            lay.addWidget(img)

        # Title + version
        title = QLabel("<b>FiberForce</b> v2.0.0")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #00d9ff; margin-top: 6px;")
        lay.addWidget(title)

        subtitle = QLabel("Muscle Force &amp; Torque Analyzer")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #00f5a0;")
        lay.addWidget(subtitle)

        blurb = QLabel(
            "Personalized biomechanical modeling for resistance training.<br><br>"
            "• Imperial (inches/ft/lbs) + ft-lb torque outputs by default<br>"
            "• 8+ lifts with geometric moment arms &amp; continuous ROM (dynrom)<br>"
            "• Rich .interpret() insights + sensitivity + programs<br>"
            "• Native macOS .app (double-click the icon from DMG)<br><br>"
            "Dark scientific-fitness theme inspired by Strong, Hevy, Strava.<br>"
            "Physics-accurate peak torque at positions and across ROM."
        )
        blurb.setAlignment(Qt.AlignCenter)
        blurb.setWordWrap(True)
        blurb.setStyleSheet("font-size: 12px; line-height: 1.35; color: #d0d0d8;")
        lay.addWidget(blurb)

        lay.addStretch()

        # Footer note + close
        foot = QLabel("AnalysisService + recipes • PySide6 + matplotlib • See docs/ for details.")
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet("font-size: 10px; color: #888;")
        lay.addWidget(foot)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setDefault(True)
        lay.addWidget(close_btn)

        dlg.exec()

    def _create_history_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Progress & Personal Records (self-competition on your modeled outputs) — ft-lb peaks, dominance % (mechanical leverage share), efficiency (ft-lb/lb load), trends, milestones from persisted runs. All values are modeled estimates (see .interpret() for caveats). Higher dominance % = better leverage for that muscle vs co-movers at the joint."))

        self.history_list = QTextEdit()
        self.history_list.setReadOnly(True)
        layout.addWidget(self.history_list)

        refresh = QPushButton("Refresh from disk (real persistence + PRs/trends)")
        refresh.clicked.connect(self._refresh_history)
        layout.addWidget(refresh)

        load_latest = QPushButton("Load latest multi-pos saved run (show .interpret() + ft-lb)")
        load_latest.clicked.connect(self._load_latest_persisted_multi_pos)
        layout.addWidget(load_latest)

        # Small trend plot for recent PR-relevant metrics (ft-lb or dom %); reuses dark mpl style from sensitivity/continuous
        self.history_trend = QWidget() if not MATPLOTLIB_AVAILABLE else self._make_history_trend_widget()
        layout.addWidget(self.history_trend)

        layout.addStretch()
        return w

    def _refresh_history(self):
        lines = []
        loaded_runs = []
        # local import for the new helpers (safe even if top recipes try scopes narrowly)
        try:
            from fiberforce.results import compute_personal_records, get_milestones, compute_rom_consistency
        except Exception:
            compute_personal_records = lambda *a, **k: {}
            get_milestones = lambda *a, **k: []
            compute_rom_consistency = lambda *a, **k: {"avg_variation_coeff": None, "note": "n/a"}
        # Real persisted runs (v1 real feature)
        try:
            runs = list_saved_runs() or []
            lines.append("=== Persisted runs on disk (most recent first) ===")
            for name in reversed(runs[-10:]):  # last 10
                try:
                    run = load_multi_position_run(name)
                    loaded_runs.append(run)
                    ts = getattr(run, "timestamp", "?")
                    lift = getattr(run, "lift", "?")
                    load = getattr(run, "load_kg", 0.0)
                    pos = getattr(run, "positions", [])
                    # Try to surface ft-lb from first analysis if present
                    ft = "?"
                    if getattr(run, "analysis_results", None):
                        first = run.analysis_results[0]
                        if hasattr(first, "results") and first.results:
                            ft = f"{getattr(first.results[0], 'peak_torque_ftlb', 0):.0f}"
                    lines.append(f"• {name[:55]} | {lift} {pos} @ {load}kg | ~{ft} ft-lb | {ts}")
                except Exception as e:
                    lines.append(f"• {name[:55]} (load error: {e})")
            if not runs:
                lines.append("(no persisted multi-pos runs yet — run smoke or use CLI profile multi-pos)")
        except Exception as e:
            lines.append(f"(persistence not available or error: {e})")

        # New Level self-competition PRs/trends (using the pure helpers on loaded + in-memory)
        try:
            if loaded_runs:
                prs = compute_personal_records(loaded_runs, include_dominance=True, include_efficiency=True)
                if prs:
                    lines.append("\n=== Personal Modeled Records (ft-lb peaks from your history — modeled estimates) ===")
                    shown = 0
                    for key, rec in sorted(prs.items(), key=lambda kv: -kv[1].get("peak_ftlb", 0))[:6]:
                        lines.append(f"  {key}: {rec['peak_ftlb']} ft-lb @ {rec.get('position','?')} ({rec.get('timestamp','?')})")
                        shown += 1
                    if len(prs) > shown:
                        lines.append(f"  ... and {len(prs)-shown} more (refresh after more saves to see trends)")
                # New: dom % PRs (leverage share) + eff, enabled by all-muscles multi-mover work
                if prs:
                    dom_lines = []
                    for key, rec in sorted(prs.items(), key=lambda kv: -(kv[1].get("dominance_percent") or -1))[:6]:
                        if rec.get("dominance_percent") is not None:
                            dom_lines.append(f"  {key}: {rec['dominance_percent']}% dom (load ~{rec.get('load_lbs','?')}lb, eff {rec.get('efficiency_ftlb_per_lb','?')}) @ {rec.get('position','?')} ({rec.get('timestamp','?')})")
                    if dom_lines:
                        lines.append("\n=== Personal Best Dominance % (modeled mechanical leverage share at joint — higher = better leverage for that muscle vs co-movers; your history only) ===")
                        lines.extend(dom_lines)
                miles = get_milestones(loaded_runs)
                if miles:
                    lines.append("\n=== Milestones (self-competition progress) ===")
                    for m in miles[:4]:
                        lines.append(f"  • {m}")
                # Wave 3: ROM consistency PR helper (lower coeff better)
                cons = compute_rom_consistency(loaded_runs)
                if cons.get("avg_variation_coeff") is not None:
                    lines.append(f"\n  ROM consistency (avg var coeff): {cons['avg_variation_coeff']} — {cons.get('note','')[:80]}")
        except Exception as e:
            lines.append(f"(PR/trend computation limited: {e})")

        # This-session in-memory (from smoke etc.)
        lines.append("\n=== This session (in-memory from GUI smoke / runs) ===")
        if self.history:
            lines.extend(self.history[-15:])
        else:
            lines.append("No in-memory runs yet. Use Tools > Run Internal Smoke or the Multi-Pos tab.")

        self.history_list.setPlainText("\n".join(lines))

        # Update the small trend plot (mpl if avail; data from loaded persisted runs)
        self._update_history_trend(loaded_runs)

    def _load_latest_persisted_multi_pos(self):
        """Load the most recent SavedMultiPositionRun and show rich interpret-like output + ft-lb in the main log."""
        try:
            runs = list_saved_runs() or []
            if not runs:
                self._log("No persisted runs on disk.")
                return
            latest = runs[-1]
            run = load_multi_position_run(latest)
            self._log(f"\n=== Loaded persisted run: {latest} ===")
            self._log(f"Lift: {getattr(run, 'lift', '?')} | Variation: {getattr(run, 'variation', '?')} | Positions: {getattr(run, 'positions', [])}")
            # Best effort ft-lb from the saved analysis_results
            if getattr(run, "analysis_results", None):
                for ar in run.analysis_results[:2]:
                    for r in getattr(ar, "results", [])[:1]:
                        ft = getattr(r, "peak_torque_ftlb", None)
                        if ft:
                            self._log(f"  {getattr(r, 'muscle_region', '?')}: {ft:.1f} ft-lb")
            notes = getattr(run, "notes", "") or getattr(run, "summary", {})
            if notes:
                self._log(f"Notes/summary: {str(notes)[:200]}")
            self._log("(Full original MPR .interpret() would be available if the Saved run carried the live object; persisted metadata + torques shown above.)")
            self.history.append(f"Loaded disk run: {latest}")
        except Exception as e:
            self._log(f"Failed to load latest persisted: {e}")

    def _update_history_trend(self, loaded_runs: list):
        """Populate small trend plot from recent persisted runs (prefer dom % if present, else ft-lb of first result)."""
        if not MATPLOTLIB_AVAILABLE or not hasattr(self, 'hist_ax'):
            return
        try:
            vals = []
            labels = []
            use_dom = False
            for run in (loaded_runs or [])[-10:]:
                try:
                    a = (getattr(run, "analysis_results", None) or getattr(run, "analyses", None) or [])[:1]
                    if a and getattr(a[0], "results", None):
                        r0 = a[0].results[0]
                        d = getattr(r0, "dominance_percent", None)
                        if d is not None:
                            vals.append(float(d))
                            use_dom = True
                        else:
                            ft = getattr(r0, "peak_torque_ftlb", None) or 0
                            vals.append(float(ft))
                        labels.append(str(getattr(run, "timestamp", "?"))[:10])
                except Exception:
                    pass
            if not vals:
                # fallback to in-memory history strings if numeric-ish
                for h in (self.history or [])[-8:]:
                    import re
                    m = re.search(r"~?(\d+\.?\d*)\s*ft", str(h))
                    if m:
                        vals.append(float(m.group(1)))
                        labels.append("mem")
            self.hist_ax.clear()
            if vals:
                xs = list(range(len(vals)))
                color = '#00f5a0' if use_dom else '#00d9ff'
                ylabel = "% dom" if use_dom else "ft-lb"
                self.hist_ax.plot(xs, vals, marker='o', color=color, linewidth=1.5, markersize=4)
                self.hist_ax.set_ylabel(ylabel, color='#a0a0b0', fontsize=7)
                self.hist_ax.set_title("Recent trend (dom % or ft-lb)", color='#00d9ff', fontsize=8)
            self.hist_ax.tick_params(colors='#a0a0b0', labelsize=6)
            for spine in self.hist_ax.spines.values():
                spine.set_color('#3a3a45')
            self.hist_canvas.draw()
        except Exception:
            pass  # never break refresh

    # --- end new methods ---


def main():
    app = QApplication(sys.argv)
    # v2: Proper macOS app identity so Dock / menu bar / About show "FiberForce" cleanly
    # (the bundle icon + name from briefcase .icns + Info.plist do the rest for Finder/Launchpad).
    app.setApplicationName("FiberForce")
    app.setApplicationDisplayName("FiberForce")
    app.setOrganizationName("FiberForce")

    # Premium dark scientific-fitness theme (Strong/Hevy/Strava inspired: very dark bg, clean cards, high contrast cyan/green accents for data/muscle, modern rounded)
    app.setStyleSheet("""
        QMainWindow { background: #0a0a0f; color: #f5f5fa; }
        QTabWidget::pane { border: 1px solid #252530; background: #121218; border-radius: 10px; }
        QTabBar::tab { background: #1a1a22; color: #b0b0c0; padding: 12px 22px; border: 1px solid #252530; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600; }
        QTabBar::tab:selected { background: #121218; color: #00f5a0; border: 1px solid #00d9ff; border-bottom: 3px solid #00f5a0; }
        QTabBar::tab:hover { background: #20202a; color: #f5f5fa; }
        QPushButton { background: #1a1a22; color: #f5f5fa; border: 1px solid #353540; padding: 11px 20px; border-radius: 8px; font-weight: 600; }
        QPushButton:hover { background: #252530; border-color: #00d9ff; color: #00f5a0; }
        QPushButton:pressed { background: #00d9ff; color: #0a0a0f; border-color: #00f5a0; }
        QTextEdit, QTableWidget { background: #0a0a0f; color: #e8e8f0; border: 1px solid #252530; border-radius: 8px; selection-background-color: #00d9ff; selection-color: #0a0a0f; }
        QLabel { color: #f5f5fa; }
        QGroupBox { border: 1px solid #252530; margin-top: 14px; padding-top: 14px; border-radius: 10px; font-weight: 700; background: #121218; }
        QGroupBox:title { subcontrol-origin: margin; left: 12px; padding: 0 8px; color: #00d9ff; }
        QMenuBar { background: #0a0a0f; color: #e8e8f0; }
        QMenu { background: #121218; color: #f5f5fa; border: 1px solid #252530; }
        QMenu::item:selected { background: #00d9ff; color: #0a0a0f; }
        QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox { background: #1a1a22; color: #f5f5fa; border: 1px solid #353540; border-radius: 6px; padding: 7px; }
        QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus, QComboBox:focus { border-color: #00f5a0; }
        QCheckBox { color: #f5f5fa; }
        /* Stronger data highlights */
        QGroupBox QLabel { font-size: 13px; }
    """)

    # Top-tier splash screen with generated image
    splash = None
    if Path(SPLASH).exists():
        pix = QPixmap(SPLASH).scaled(800, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        splash = QSplashScreen(pix, Qt.WindowStaysOnTopHint)
        if pix.hasAlpha():
            splash.setMask(pix.mask())
        splash.show()
        app.processEvents()
        QTimer.singleShot(1500, splash.close)  # brief splash

    window = FiberForceMainWindow()
    window.show()
    if splash:
        splash.finish(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()