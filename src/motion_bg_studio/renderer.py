"""High-level render orchestration: build a generator, iterate frames, encode video."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .encoder import encode_video
from .generators import get_generator
from .palettes import get_palette
from .utils import make_rng


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


def iter_frames(job: RenderJob, generator=None):
    """Yield frames for the given job."""
    gen = generator if generator is not None else build_generator(job)
    n = job.total_frames()
    for i in range(n):
        t = i / n  # in [0, 1) — the next loop cycle starts at i = n
        yield gen.render(t)


def render_to_file(
    job: RenderJob,
    progress_cb: Callable[[int, int | None], None] | None = None,
) -> Path:
    gen = build_generator(job)
    n = job.total_frames()

    def _frames():
        for i in range(n):
            t = i / n
            yield gen.render(t)

    return encode_video(
        _frames(),
        output=job.output,
        width=job.width,
        height=job.height,
        fps=job.fps,
        crf=job.crf,
        preset=job.preset,
        progress_cb=progress_cb,
        total_frames=n,
    )


def render_preview_frame(job: RenderJob, t: float = 0.0) -> np.ndarray:
    gen = build_generator(job)
    return gen.render(t)
