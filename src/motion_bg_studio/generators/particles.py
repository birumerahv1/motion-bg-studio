"""Particles / bokeh generator: drifting soft glowing dots, classic microstock look."""
from __future__ import annotations

from typing import Any

import numpy as np

from ..palettes import Palette
from .base import Generator, background_canvas


def _make_sprite(radius: int, softness: float = 1.6) -> np.ndarray:
    """Radial gaussian sprite normalized to [0, 1]."""
    yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1].astype(np.float32)
    r2 = xx * xx + yy * yy
    sigma = radius / softness
    sprite = np.exp(-r2 / (2.0 * sigma * sigma))
    sprite[r2 > (radius * radius)] = 0.0
    return sprite.astype(np.float32)


class ParticlesGenerator(Generator):
    name = "particles"
    display_name = "Particles / Bokeh"

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        n = int(rng.integers(120, 240))
        positions = rng.random((n, 2)).astype(np.float32)
        # Integer wrap counts -> seamless loop. Bias to slow drift.
        wrap_x = rng.choice([-1, 0, 0, 0, 1], size=n).astype(np.float32)
        wrap_y = rng.choice([-1, 0, 0, 0, 1], size=n).astype(np.float32)
        # Avoid all-zero motion: ensure at least one axis moves for half of them.
        zero_mask = (wrap_x == 0) & (wrap_y == 0)
        wrap_y[zero_mask] = rng.choice([-1, 1], size=int(zero_mask.sum())).astype(np.float32)
        radii = rng.uniform(8.0, 38.0, size=n).astype(np.float32)
        # A few large, soft bokeh blurs.
        radii[: max(1, n // 12)] *= rng.uniform(2.5, 4.0)
        color_idx = rng.integers(0, len(palette.colors), size=n)
        # Phase for alpha pulse (so brightness twinkles loop-seamlessly).
        phase = rng.random(n).astype(np.float32)
        cycles = rng.choice([1, 1, 2, 2, 3], size=n).astype(np.float32)
        intensity = rng.uniform(0.55, 1.0, size=n).astype(np.float32)
        return {
            "n": n,
            "positions": positions,
            "wrap_x": wrap_x,
            "wrap_y": wrap_y,
            "radii": radii,
            "color_idx": color_idx,
            "phase": phase,
            "cycles": cycles,
            "intensity": intensity,
        }

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        super().__init__(params, palette, width, height)
        # Precompute a small bank of sprites bucketed by radius.
        self._radius_buckets = sorted({int(r) for r in np.round(params["radii"]).astype(int)})
        self._sprites = {r: _make_sprite(max(1, r)) for r in self._radius_buckets}
        # Map every particle to its sprite via integer-rounded radius.
        self._part_radius = np.round(params["radii"]).astype(np.int32)
        self._colors = np.array(palette.colors, dtype=np.float32)[params["color_idx"]]  # (n, 3)

    def render(self, t: float) -> np.ndarray:
        canvas = background_canvas(self.palette, self.width, self.height).astype(np.float32)
        p = self.params
        # Position at time t (normalized 0..1).
        x = (p["positions"][:, 0] + p["wrap_x"] * t) % 1.0
        y = (p["positions"][:, 1] + p["wrap_y"] * t) % 1.0
        # Alpha pulse 0..1 loop-perfect:
        alpha = 0.5 + 0.5 * np.sin(2.0 * np.pi * (p["cycles"] * t + p["phase"]))
        alpha = alpha * p["intensity"]

        h, w = self.height, self.width
        for i in range(p["n"]):
            r = int(self._part_radius[i])
            if r < 1:
                continue
            sprite = self._sprites[r]
            sx = int(round(x[i] * w))
            sy = int(round(y[i] * h))
            x0 = sx - r
            y0 = sy - r
            x1 = x0 + sprite.shape[1]
            y1 = y0 + sprite.shape[0]
            # Compute clipped destination region.
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
            # Plates of color over background (alpha blend) plus a touch of additive glow at the core.
            region[:] = region * (1.0 - mask) + color * mask
            region[:] = np.minimum(region + color * (mask * mask) * 0.35, 255.0)
        return np.clip(canvas, 0, 255).astype(np.uint8)
