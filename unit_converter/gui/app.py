"""
unit_converter.gui.app
=======================
PySide6 application entry point for the U Converter GUI.

Usage (installed)::

    unit-converter-gui

Usage (from source)::

    python -m unit_converter.gui.app

QApplication lifecycle (per research report Q3 / Finding F3.3):
- ``QApplication(sys.argv)`` constructs the application instance.
- High-DPI scaling is on by default in PySide6 6.x — no ``AA_EnableHighDpiScaling``
  boilerplate needed.
- ``app.exec()`` runs the event loop (NOT ``exec_()`` — that is the Qt5 spelling).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from unit_converter.gui.main_window import MainWindow


def main() -> int:
    """
    GUI console-scripts entry point.

    Returns the exit code from ``app.exec()`` so ``sys.exit(main())`` works
    correctly in all callers.
    """
    app = QApplication(sys.argv)
    # High-DPI scaling is on by default — no additional attribute needed.
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
