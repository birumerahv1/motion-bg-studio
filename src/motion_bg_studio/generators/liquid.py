"""Liquid / fluid: warped FBM noise sampled along a circular time-loop path."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from ..palettes import Palette
from ..utils import LoopNoise2D, fbm
from .base import Generator, palette_gradient


class LiquidGenerator(Generator):
    name = "liquid"
    display_name = "Liquid Flow"

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        return {
            "scale": float(rng.uniform(2.5, 5.0)),
            "warp": float(rng.uniform(0.4, 1.0)),
            "loop_radius": float(rng.uniform(0.8, 1.6)),
            "octaves": int(rng.integers(3, 5)),
            "noise_seed": int(rng.integers(0, 2**31 - 1)),
            "warp_seed": int(rng.integers(0, 2**31 - 1)),
            "contrast": float(rng.uniform(0.85, 1.25)),
        }

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        super().__init__(params, palette, width, height)
        scale = params["scale"]
        ys = np.linspace(0.0, scale * height / max(width, height), height, dtype=np.float32)
        xs = np.linspace(0.0, scale * width / max(width, height), width, dtype=np.float32)
        self._xx, self._yy = np.meshgrid(xs, ys)
        self._noise = LoopNoise2D(period=64, seed=params["noise_seed"])
        self._warp_noise = LoopNoise2D(period=64, seed=params["warp_seed"])
        self._gradient = palette_gradient(palette, 1024)

    def render(self, t: float) -> np.ndarray:
        p = self.params
        a = 2.0 * math.pi * t
        ox, oy = p["loop_radius"] * math.cos(a), p["loop_radius"] * math.sin(a)
        ox2, oy2 = p["loop_radius"] * math.cos(a + 1.7), p["loop_radius"] * math.sin(a + 1.7)

        # Warp coordinates with a slow-moving noise field.
        warp = fbm(self._warp_noise, self._xx + ox2, self._yy + oy2, octaves=2)
        warp2 = fbm(self._warp_noise, self._xx + 5.2 + oy2, self._yy + 1.3 + ox2, octaves=2)
        wx = self._xx + p["warp"] * (warp - 0.5) * 2.0
        wy = self._yy + p["warp"] * (warp2 - 0.5) * 2.0

        field = fbm(self._noise, wx + ox, wy + oy, octaves=p["octaves"])
        field = (field - 0.5) * p["contrast"] + 0.5
        field = np.clip(field, 0.0, 1.0)
        idx = (field * (self._gradient.shape[0] - 1)).astype(np.int32)
        return self._gradient[idx]
