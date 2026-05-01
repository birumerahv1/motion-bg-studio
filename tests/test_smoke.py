"""Smoke tests: every generator renders, every output is uint8 RGB, loops are seamless."""
from __future__ import annotations

import shutil

import numpy as np
import pytest

from motion_bg_studio.generators import GENERATORS, list_generators
from motion_bg_studio.palettes import list_palettes
from motion_bg_studio.renderer import RenderJob, build_generator, render_to_file


@pytest.mark.parametrize("style", list_generators())
def test_generator_shape_and_dtype(style: str) -> None:
    job = RenderJob(style=style, palette="midnight_blue", width=128, height=72, duration=1, fps=4, seed=3)
    gen = build_generator(job)
    f = gen.render(0.0)
    assert f.shape == (72, 128, 3)
    assert f.dtype == np.uint8


@pytest.mark.parametrize("style", list_generators())
def test_loop_is_seamless(style: str) -> None:
    """Rendering at t=0 and t=1.0 should produce (almost) identical frames."""
    job = RenderJob(style=style, palette="midnight_blue", width=160, height=90, duration=1, fps=4, seed=11)
    gen = build_generator(job)
    f0 = gen.render(0.0).astype(np.int16)
    f1 = gen.render(1.0).astype(np.int16)
    diff = np.max(np.abs(f0 - f1))
    # Tiny floating-point/rounding tolerance is fine.
    assert diff <= 2, f"{style} loop seam diff = {diff}"


def test_palette_registry_consistent() -> None:
    assert len(list_palettes()) > 0
    assert "midnight_blue" in list_palettes()


def test_generator_registry_consistent() -> None:
    assert set(GENERATORS) == set(list_generators())


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_to_file_produces_mp4(tmp_path) -> None:
    out = tmp_path / "out.mp4"
    job = RenderJob(
        style="gradient_waves",
        palette="midnight_blue",
        width=160,
        height=90,
        duration=1,
        fps=4,
        seed=1,
        output=out,
        preset="ultrafast",
    )
    p = render_to_file(job)
    assert p.exists()
    assert p.stat().st_size > 1000  # non-trivial size
