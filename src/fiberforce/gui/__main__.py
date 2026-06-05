"""Allow running as: python -m fiberforce.gui

This avoids the submodule import warning from python -m fiberforce.gui.app
"""
from .app import main

if __name__ == "__main__":
    main()
