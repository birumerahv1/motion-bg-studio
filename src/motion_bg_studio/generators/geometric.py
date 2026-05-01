"""Geometric shapes drifting/rotating, drawn with Pillow for clean antialiased edges."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from ..palettes import Palette
from .base import Generator


def _polygon(sides: int, radius: float, angle: float) -> list[tuple[float, float]]:
    return [
        (radius * math.cos(angle + 2 * math.pi * i / sides),
         radius * math.sin(angle + 2 * math.pi * i / sides))
        for i in range(sides)
    ]


class GeometricGenerator(Generator):
    name = "geometric"
    display_name = "Geometric Shapes"

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        n = int(rng.integers(18, 36))
        positions = rng.random((n, 2)).astype(np.float32)
        wrap_x = rng.choice([-1, 0, 0, 1], size=n).astype(np.float32)
        wrap_y = rng.choice([-1, 0, 0, 1], size=n).astype(np.float32)
        zero = (wrap_x == 0) & (wrap_y == 0)
        wrap_y[zero] = rng.choice([-1, 1], size=int(zero.sum())).astype(np.float32)
        sizes = rng.uniform(0.04, 0.16, size=n).astype(np.float32)
        rot_speed = rng.choice([-2, -1, 1, 1, 2], size=n).astype(np.float32)
        rot_phase = rng.uniform(0, 2 * math.pi, size=n).astype(np.float32)
        sides = rng.choice([3, 3, 4, 4, 5, 6, 6, 8], size=n).astype(np.int32)
        color_idx = rng.integers(0, len(palette.colors), size=n)
        alpha = rng.uniform(0.10, 0.35, size=n).astype(np.float32)
        outline = rng.random(n) > 0.4  # ~60% outline-only, the rest filled
        return {
            "n": n,
            "positions": positions,
            "wrap_x": wrap_x,
            "wrap_y": wrap_y,
            "sizes": sizes,
            "rot_speed": rot_speed,
            "rot_phase": rot_phase,
            "sides": sides,
            "color_idx": color_idx,
            "alpha": alpha,
            "outline": outline,
        }

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        super().__init__(params, palette, width, height)
        self._colors = [palette.colors[int(i)] for i in params["color_idx"]]

    def render(self, t: float) -> np.ndarray:
        p = self.params
        bg = self.palette.background
        img = Image.new("RGBA", (self.width, self.height), (*bg, 255))
        scale = max(self.width, self.height)
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for i in range(p["n"]):
            cx = (p["positions"][i, 0] + p["wrap_x"][i] * t) % 1.0 * self.width
            cy = (p["positions"][i, 1] + p["wrap_y"][i] * t) % 1.0 * self.height
            radius = p["sizes"][i] * scale * 0.5
            angle = p["rot_phase"][i] + 2 * math.pi * p["rot_speed"][i] * t
            verts = _polygon(int(p["sides"][i]), radius, angle)
            verts = [(cx + x, cy + y) for x, y in verts]
            r, g, b = self._colors[i]
            a = int(255 * p["alpha"][i])
            if p["outline"][i]:
                draw.polygon(verts, outline=(r, g, b, a), width=max(2, int(scale * 0.0015)))
            else:
                draw.polygon(verts, fill=(r, g, b, a))
        img.alpha_composite(layer)
        return np.asarray(img.convert("RGB"))
