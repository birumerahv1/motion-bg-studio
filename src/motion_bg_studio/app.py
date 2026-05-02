"""Desktop app entry point. Launches the Qt main window."""
from __future__ import annotations

import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

from motion_bg_studio.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Motion Background Studio")
    app.setOrganizationName("Motion BG Studio")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    # Required for PyInstaller .exe so multiprocessing child processes do not
    # re-launch the entire GUI; harmless on POSIX.
    multiprocessing.freeze_support()
    raise SystemExit(main())
