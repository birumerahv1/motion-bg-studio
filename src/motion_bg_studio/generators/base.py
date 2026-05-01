"""Base generator interface."""
from __future__ import annotations

from typing import Any

import numpy as np

from ..palettes import Palette


class Generator:
    """Base class for all motion-background generators.

    Subclasses must implement :meth:`render` and :meth:`random_params`.
    Each generator is instantiated once per render job; expensive setup belongs
    in ``__init__``.
    """

    name: str = ""
    display_name: str = ""

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        self.params = params
        self.palette = palette
        self.width = int(width)
        self.height = int(height)

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        """Return a randomized but tasteful set of parameters."""
        raise NotImplementedError

    def render(self, t: float) -> np.ndarray:
        """Return the frame at normalized time ``t`` in ``[0, 1)`` as HxWx3 uint8."""
        raise NotImplementedError


def palette_gradient(palette: Palette, n: int = 256) -> np.ndarray:
    """Build a smooth Nx3 gradient by linearly interpolating palette colors."""
    colors = np.array(palette.colors, dtype=np.float32)  # (k, 3)
    k = len(colors)
    if k == 1:
        return np.tile(colors[0], (n, 1)).astype(np.uint8)
    xp = np.linspace(0.0, 1.0, k)
    fp_r, fp_g, fp_b = colors[:, 0], colors[:, 1], colors[:, 2]
    x = np.linspace(0.0, 1.0, n)
    grad = np.stack(
        [np.interp(x, xp, fp_r), np.interp(x, xp, fp_g), np.interp(x, xp, fp_b)],
        axis=1,
    )
    return np.clip(grad, 0, 255).astype(np.uint8)


def background_canvas(palette: Palette, width: int, height: int) -> np.ndarray:
    bg = np.array(palette.background, dtype=np.uint8)
    return np.broadcast_to(bg, (height, width, 3)).copy()
