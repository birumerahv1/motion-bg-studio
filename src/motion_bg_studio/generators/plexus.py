"""Plexus: floating points connected by lines when they're close enough."""
from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from ..palettes import Palette
from .base import Generator


class PlexusGenerator(Generator):
    name = "plexus"
    display_name = "Plexus Network"

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        n = int(rng.integers(80, 140))
        positions = rng.random((n, 2)).astype(np.float32)
        wrap_x = rng.choice([-1, 0, 0, 1], size=n).astype(np.float32)
        wrap_y = rng.choice([-1, 0, 0, 1], size=n).astype(np.float32)
        zero = (wrap_x == 0) & (wrap_y == 0)
        wrap_y[zero] = rng.choice([-1, 1], size=int(zero.sum())).astype(np.float32)
        return {
            "n": n,
            "positions": positions,
            "wrap_x": wrap_x,
            "wrap_y": wrap_y,
            "link_dist": float(rng.uniform(0.10, 0.16)),
            "node_color_idx": int(rng.integers(0, len(palette.colors))),
            "line_color_idx": int(rng.integers(0, len(palette.colors))),
        }

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        super().__init__(params, palette, width, height)
        self._node_color = palette.colors[params["node_color_idx"]]
        self._line_color = palette.colors[params["line_color_idx"]]

    def render(self, t: float) -> np.ndarray:
        p = self.params
        bg = self.palette.background
        img = Image.new("RGBA", (self.width, self.height), (*bg, 255))
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        x = (p["positions"][:, 0] + p["wrap_x"] * t) % 1.0
        y = (p["positions"][:, 1] + p["wrap_y"] * t) % 1.0
        # Compute pairwise distances in normalized space.
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        # Toroidal-aware distance so points near edges still link sensibly.
        dx = np.minimum(np.abs(dx), 1.0 - np.abs(dx))
        dy = np.minimum(np.abs(dy), 1.0 - np.abs(dy))
        dist = np.sqrt(dx * dx + dy * dy)
        link = p["link_dist"]
        ii, jj = np.where((dist < link) & (np.tri(p["n"], k=-1, dtype=bool)))
        scale = max(self.width, self.height)
        # Lines first (so nodes draw on top).
        lr, lg, lb = self._line_color
        for i, j in zip(ii, jj, strict=False):
            if abs(x[i] - x[j]) > 0.5 or abs(y[i] - y[j]) > 0.5:
                continue  # avoid lines wrapping across the frame
            a = int(255 * (1.0 - dist[i, j] / link) * 0.7)
            draw.line(
                [(x[i] * self.width, y[i] * self.height), (x[j] * self.width, y[j] * self.height)],
                fill=(lr, lg, lb, a),
                width=max(1, int(scale * 0.0008)),
            )
        nr, ng, nb = self._node_color
        node_r = max(2, int(scale * 0.0024))
        for i in range(p["n"]):
            cx = x[i] * self.width
            cy = y[i] * self.height
            draw.ellipse(
                [cx - node_r, cy - node_r, cx + node_r, cy + node_r],
                fill=(nr, ng, nb, 220),
            )
        img.alpha_composite(layer)
        return np.asarray(img.convert("RGB"))
