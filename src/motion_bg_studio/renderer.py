"""High-level render orchestration: build a generator, iterate frames, encode video.

For non-trivial resolutions the procedural frame generation (per-pixel numpy work
in the style generator) is the dominant cost, often more than the H.264 encoder.
A ProcessPoolExecutor parallelizes frame generation across CPU cores; combined
with a hardware H.264 encoder (NVENC / QSV / AMF) the wall time drops by 3-6×
on a typical 4-core machine for 4K renders.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from motion_bg_studio.encoder import encode_video
from motion_bg_studio.generators import get_generator
from motion_bg_studio.palettes import get_palette
from motion_bg_studio.utils import make_rng


@dataclass
class RenderJob:
    style: str = "particles"
    palette: str = "midnight_blue"
    width: int = 3840
    height: int = 2160
    duration: float = 15.0
    fps: int = 30
    seed: int | None = None
    crf: int = 18
    preset: str = "medium"
    encoder: str = "auto"  # "auto" / "cpu" / "gpu" / explicit codec name
    workers: int = 0  # 0 = auto (cpu_count - 1), 1 = serial (no multiprocessing)
    output: Path = field(default_factory=lambda: Path("out.mp4"))

    def total_frames(self) -> int:
        return int(round(self.duration * self.fps))

    def filename_stem(self) -> str:
        return f"{self.style}_{self.palette}_{self.width}x{self.height}_{int(round(self.duration))}s_{self.seed}"


def build_generator(job: RenderJob):
    palette = get_palette(job.palette)
    cls = get_generator(job.style)
    rng = make_rng(job.seed)
    params = cls.random_params(rng, palette)
    return cls(params, palette, job.width, job.height)


def _build_params(job: RenderJob):
    """Build the deterministic params dict shared by all workers."""
    palette = get_palette(job.palette)
    cls = get_generator(job.style)
    rng = make_rng(job.seed)
    return cls.random_params(rng, palette)


def iter_frames(job: RenderJob, generator=None):
    """Yield frames serially. Used by tests and previews; not the render hot path."""
    gen = generator if generator is not None else build_generator(job)
    n = job.total_frames()
    for i in range(n):
        t = i / n
        yield gen.render(t)


# --- multiprocessing worker ---------------------------------------------------
# Workers re-build the generator once at startup (initializer) and then
# render frames on demand. This avoids re-building per-frame.

_WORKER_GEN = None


def _worker_init(style: str, palette_name: str, width: int, height: int, params) -> None:
    """ProcessPoolExecutor initializer — sets up the generator in the worker."""
    global _WORKER_GEN
    palette = get_palette(palette_name)
    cls = get_generator(style)
    _WORKER_GEN = cls(params, palette, width, height)


def _worker_render(t: float):
    """Render a single frame in the worker process."""
    assert _WORKER_GEN is not None, "worker not initialized"
    return _WORKER_GEN.render(t)


def _resolve_workers(requested: int) -> int:
    if requested >= 1:
        return requested
    # auto: cpu_count - 1, capped at a sensible number to keep IPC overhead low
    cpu = os.cpu_count() or 2
    return max(1, min(8, cpu - 1))


def _frames_serial(job: RenderJob):
    gen = build_generator(job)
    n = job.total_frames()
    for i in range(n):
        yield gen.render(i / n)


def _frames_parallel(job: RenderJob, num_workers: int):
    """Yield frames in order, generated in parallel across workers."""
    n = job.total_frames()
    params = _build_params(job)
    ts = [i / n for i in range(n)]
    chunksize = max(1, n // (num_workers * 4))
    with ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=_worker_init,
        initargs=(job.style, job.palette, job.width, job.height, params),
    ) as ex:
        # ex.map preserves submission order, so frames stream out in time order.
        yield from ex.map(_worker_render, ts, chunksize=chunksize)


def render_to_file(
    job: RenderJob,
    progress_cb: Callable[[int, int | None], None] | None = None,
) -> Path:
    n = job.total_frames()
    workers = _resolve_workers(job.workers)

    # Single-frame jobs and serial mode skip the pool entirely.
    if workers <= 1 or n <= 2 or _running_in_pyinstaller_subprocess():
        frames = _frames_serial(job)
    else:
        try:
            frames = _frames_parallel(job, workers)
        except (RuntimeError, OSError):
            # Fall back to serial if pool spawning fails for any reason.
            frames = _frames_serial(job)

    return encode_video(
        frames,
        output=job.output,
        width=job.width,
        height=job.height,
        fps=job.fps,
        crf=job.crf,
        preset=job.preset,
        progress_cb=progress_cb,
        total_frames=n,
        encoder=job.encoder,
    )


def _running_in_pyinstaller_subprocess() -> bool:
    """Detect if we are inside a multiprocessing child of a PyInstaller app.

    multiprocessing.freeze_support() at the entry point is supposed to short-circuit
    those processes, but as a belt-and-suspenders we also avoid spawning further pools
    from inside an already-frozen worker.
    """
    return bool(getattr(sys, "frozen", False) and os.environ.get("MOTION_BG_INSIDE_WORKER"))


def render_preview_frame(job: RenderJob, t: float = 0.0) -> np.ndarray:
    gen = build_generator(job)
    return gen.render(t)
