"""Background QThread that renders one or more jobs to disk without blocking the UI."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ..renderer import RenderJob, render_to_file


class RenderWorker(QThread):
    progress = Signal(int, int, int, int)  # job_idx, total_jobs, frame, total_frames
    job_started = Signal(int, int, str)    # job_idx, total_jobs, output_path
    job_finished = Signal(int, int, str)   # job_idx, total_jobs, output_path
    error = Signal(int, str)               # job_idx, message
    all_done = Signal(int)                 # total_jobs

    def __init__(self, jobs: list[RenderJob], parent=None):
        super().__init__(parent)
        self._jobs = jobs
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D401
        total = len(self._jobs)
        for idx, job in enumerate(self._jobs):
            if self._cancel:
                break
            self.job_started.emit(idx, total, str(job.output))

            def cb(frame: int, total_frames: int | None, idx=idx) -> None:
                if total_frames is None:
                    return
                self.progress.emit(idx, total, frame, total_frames)
                if self._cancel:
                    raise KeyboardInterrupt

            try:
                render_to_file(job, progress_cb=cb)
                self.job_finished.emit(idx, total, str(job.output))
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.error.emit(idx, str(e))
        self.all_done.emit(total)
