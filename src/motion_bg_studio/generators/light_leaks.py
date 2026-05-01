"""Light leaks / lens flares: large, soft, additive colorful blobs drifting across the frame."""
from __future__ import annotations

from typing import Any

import numpy as np

from ..palettes import Palette
from .base import Generator, background_canvas
from .particles import _make_sprite


class LightLeaksGenerator(Generator):
    name = "light_leaks"
    display_name = "Light Leaks"

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        n = int(rng.integers(6, 14))
        positions = rng.random((n, 2)).astype(np.float32)
        # Slow drift mostly horizontal, like real film leaks.
        wrap_x = rng.choice([-1, 1], size=n).astype(np.float32)
        wrap_y = np.zeros(n, dtype=np.float32)
        # Big radii (relative to frame).
        rel_r = rng.uniform(0.18, 0.45, size=n).astype(np.float32)
        cycles = rng.choice([1, 1, 2], size=n).astype(np.float32)
        phase = rng.random(n).astype(np.float32)
        intensity = rng.uniform(0.55, 1.0, size=n).astype(np.float32)
        color_idx = rng.integers(0, len(palette.colors), size=n)
        return {
            "n": n,
            "positions": positions,
            "wrap_x": wrap_x,
            "wrap_y": wrap_y,
            "rel_r": rel_r,
            "cycles": cycles,
            "phase": phase,
            "intensity": intensity,
            "color_idx": color_idx,
        }

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        super().__init__(params, palette, width, height)
        scale = min(width, height)
        self._radii = np.maximum(8, np.round(params["rel_r"] * scale * 0.5).astype(np.int32))
        self._sprites = {int(r): _make_sprite(int(r), softness=2.4) for r in self._radii}
        self._colors = np.array(palette.colors, dtype=np.float32)[params["color_idx"]]

    def render(self, t: float) -> np.ndarray:
        canvas = background_canvas(self.palette, self.width, self.height).astype(np.float32)
        p = self.params
        x = (p["positions"][:, 0] + p["wrap_x"] * t) % 1.0
        y = (p["positions"][:, 1] + p["wrap_y"] * t) % 1.0
        alpha = (0.5 + 0.5 * np.sin(2 * np.pi * (p["cycles"] * t + p["phase"]))) * p["intensity"]

        h, w = self.height, self.width
        for i in range(p["n"]):
            r = int(self._radii[i])
            sprite = self._sprites[r]
            sx = int(round(x[i] * w))
            sy = int(round(y[i] * h))
            x0, y0 = sx - r, sy - r
            x1, y1 = x0 + sprite.shape[1], y0 + sprite.shape[0]
            dx0 = max(0, x0)
            dy0 = max(0, y0)
            dx1 = min(w, x1)
            dy1 = min(h, y1)
            if dx1 <= dx0 or dy1 <= dy0:
                continue
            sx0 = dx0 - x0
            sy0 = dy0 - y0
            sx1 = sx0 + (dx1 - dx0)
            sy1 = sy0 + (dy1 - dy0)
            mask = sprite[sy0:sy1, sx0:sx1, None] * alpha[i]
            color = self._colors[i]
            region = canvas[dy0:dy1, dx0:dx1]
            # Additive screen blend tinted with leak color.
            region[:] = 255.0 - (255.0 - region) * (1.0 - mask) + color * mask * 0.4
        return np.clip(canvas, 0, 255).astype(np.uint8)
