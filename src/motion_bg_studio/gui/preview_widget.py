"""Live preview widget: renders the current generator at a small size on a QTimer."""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..renderer import RenderJob, build_generator


class PreviewWidget(QWidget):
    """Animated preview of the current job. Frames are rendered on the GUI thread
    in 480x270 (or whatever fits) — that's fast enough for fluid playback for all
    six generators on a typical laptop CPU.
    """

    PREVIEW_W = 480
    PREVIEW_H = 270

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(QSize(self.PREVIEW_W, self.PREVIEW_H))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._t = 0.0
        self._duration = 15.0
        self._fps = 30
        self._frame: np.ndarray | None = None
        self._generator = None
        self._job: RenderJob | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._last_tick = time.monotonic()
        self.setStyleSheet("background: #0c0c10;")

    def set_job(self, job: RenderJob) -> None:
        # Build a low-res preview generator with the same parameters as the full job.
        preview_job = RenderJob(
            style=job.style,
            palette=job.palette,
            width=self.PREVIEW_W,
            height=self.PREVIEW_H,
            duration=job.duration,
            fps=24,
            seed=job.seed,
        )
        self._job = preview_job
        self._duration = job.duration
        self._fps = 24
        self._generator = build_generator(preview_job)
        self._t = 0.0
        self._render_current()
        self.update()
        if not self._timer.isActive():
            self._timer.start(1000 // self._fps)

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        if self._generator is None:
            return
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        # Advance phase based on real time so playback speed matches the final loop.
        self._t = (self._t + dt / max(0.1, self._duration)) % 1.0
        self._render_current()
        self.update()

    def _render_current(self) -> None:
        if self._generator is None:
            return
        try:
            frame = self._generator.render(self._t)
            # QImage requires contiguous data; numpy slices/views may not be.
            self._frame = np.ascontiguousarray(frame)
        except Exception:
            self._frame = None

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._frame is None:
            return
        h, w, _ = self._frame.shape
        img = QImage(self._frame.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        # Scale to fit while preserving aspect ratio, centred.
        sw, sh = self.width(), self.height()
        scale = min(sw / w, sh / h)
        dw, dh = w * scale, h * scale
        x = (sw - dw) / 2
        y = (sh - dh) / 2
        p.drawImage(QRectF(x, y, dw, dh), img)
