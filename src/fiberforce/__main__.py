"""Entry point for running FiberForce as a module: `python -m fiberforce`

This launches the native PySide6 GUI by default.

It is used by the macOS .app bundle created with Briefcase (the executable
runs the package as a module), and is convenient for users.

The `fiberforce` console script (from [project.scripts]) still runs the
Typer CLI (with subcommands like `gui`, `smoke`, etc.).
"""

from fiberforce.gui.app import main

if __name__ == "__main__":
    main()