"""Desktop app entry point. Launches the Qt main window."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Motion Background Studio")
    app.setOrganizationName("Motion BG Studio")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
