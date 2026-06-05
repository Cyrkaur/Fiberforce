"""
FiberForce GUI package.

Launch with:
    python -m fiberforce.gui
or
    fiberforce gui   (after installing the package)

Note: python -m fiberforce.gui (not .app) is preferred to avoid the RuntimeWarning about 'fiberforce.gui.app' found in sys.modules after import of package 'fiberforce.gui'.
"""

from .app import main, FiberForceMainWindow

__all__ = ["main", "FiberForceMainWindow"]
