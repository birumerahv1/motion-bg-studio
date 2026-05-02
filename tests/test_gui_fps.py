"""GUI tests for the editable FPS combo (offscreen Qt)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from motion_bg_studio.gui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    inst = QApplication.instance() or QApplication([])
    return inst


@pytest.fixture()
def window(app: QApplication) -> MainWindow:  # noqa: ARG001
    w = MainWindow()
    yield w
    w.close()


def test_fps_combo_is_editable(window: MainWindow) -> None:
    assert window.fps_cb.isEditable()
    assert window.fps_cb.lineEdit() is not None


def test_fps_presets_are_present(window: MainWindow) -> None:
    presets = [window.fps_cb.itemData(i) for i in range(window.fps_cb.count())]
    assert presets == [24, 25, 30, 50, 60]


def test_fps_default_is_30(window: MainWindow) -> None:
    assert window._current_fps() == 30
    assert window._current_job().fps == 30


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("120", 120),
        ("90", 90),
        ("60", 60),
        ("24", 24),
        ("  72  ", 72),
        ("999", 999),
    ],
)
def test_fps_accepts_valid_custom_values(window: MainWindow, typed: str, expected: int) -> None:
    window.fps_cb.setCurrentText(typed)
    assert window._current_fps() == expected
    assert window._current_job().fps == expected


@pytest.mark.parametrize("typed", ["", "abc", "12.5", "-3", "0"])
def test_fps_invalid_input_falls_back_to_30(window: MainWindow, typed: str) -> None:
    window.fps_cb.setCurrentText(typed)
    assert window._current_fps() == 30
