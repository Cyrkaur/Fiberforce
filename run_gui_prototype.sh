#!/bin/bash
# Launch the full FiberForce GUI on macOS (or any platform with PySide6) — DEV / fast iteration path.
# v2 note: This is still the best way for active development (edit → instant launch).
# For the primary *end-user* "click the icon" experience (no terminal, DMG, custom icon):
#   see scripts/build_macos_app.sh + the v2.0 Packaging section in README.
#
# v1 bulletproofed (still true): always uses the canonical volume workspace + venv to prevent
# the exact errors seen before (pip from ~, "Directory cannot...", command not found, PATH, runpy, splash mask).
#
# Usage (from anywhere):
#   bash run_gui_prototype.sh
#
# Or the manual sequence (see README "Development" for the authoritative copy-paste):
#   cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"
#   python3 -m venv .venv && source .venv/bin/activate
#   python -m pip install -e ".[gui,viz]"
#   fiberforce gui   # or: python -m fiberforce.gui

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=== FiberForce GUI launcher (v1) — volume workspace + venv enforced ==="
echo "Workspace: $SCRIPT_DIR"

# Ensure venv exists (create if missing — one-time cost)
if [ ! -d ".venv" ]; then
  echo "No .venv found — creating (python3 -m venv .venv)..."
  python3 -m venv .venv
fi

# Activate (this puts the venv bin first on PATH so "pip" and "fiberforce" resolve correctly)
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Upgrading pip and installing editable with [gui,viz] (PySide6 + matplotlib)..."
python -m pip install --upgrade pip -q
python -m pip install -e ".[gui,viz]" -q

echo "Launching FiberForce GUI with custom top-tier visuals (splash, app_icon, header_banner, result_viz + dark QSS, imperial inches + ft-lb)..."
echo "Tip: if you ever see command-not-found after this, re-run the script or manually source .venv/bin/activate after cd to the volume path."
echo "Manual fallback after this script: source .venv/bin/activate && fiberforce gui"
PYTHONPATH=src python -m fiberforce.gui
# Note: -m fiberforce.gui (via __main__.py) avoids the RuntimeWarning about 'fiberforce.gui.app' found in sys.modules.

