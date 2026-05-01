"""Gradient waves: smooth abstract color flow."""
from __future__ import annotations

from typing import Any

import numpy as np

from ..palettes import Palette
from .base import Generator, palette_gradient


class GradientWavesGenerator(Generator):
    name = "gradient_waves"
    display_name = "Gradient Waves"

    @classmethod
    def random_params(cls, rng: np.random.Generator, palette: Palette) -> dict[str, Any]:
        n_waves = int(rng.integers(3, 6))
        # Integer cycles per loop -> seamless.
        cycles = rng.integers(1, 4, size=n_waves).astype(np.float32)
        # Spatial frequencies (cycles across width/height).
        sx = rng.uniform(-2.0, 2.0, size=n_waves).astype(np.float32)
        sy = rng.uniform(-2.0, 2.0, size=n_waves).astype(np.float32)
        phase = rng.uniform(0.0, 2.0 * np.pi, size=n_waves).astype(np.float32)
        amps = rng.uniform(0.4, 1.0, size=n_waves).astype(np.float32)
        amps /= amps.sum()
        return {
            "cycles": cycles,
            "sx": sx,
            "sy": sy,
            "phase": phase,
            "amps": amps,
            "vignette": float(rng.uniform(0.10, 0.30)),
        }

    def __init__(self, params: dict[str, Any], palette: Palette, width: int, height: int):
        super().__init__(params, palette, width, height)
        # Coordinate grid normalized to [-1, 1] on the longer axis.
        scale = max(width, height)
        ys = (np.arange(height) - height / 2) / scale
        xs = (np.arange(width) - width / 2) / scale
        self._xx, self._yy = np.meshgrid(xs, ys)
        self._gradient = palette_gradient(palette, 1024)
        # Vignette mask.
        rr = np.sqrt(self._xx ** 2 + self._yy ** 2)
        rr /= rr.max() + 1e-9
        self._vignette = (1.0 - params["vignette"] * (rr ** 2)).astype(np.float32)

    def render(self, t: float) -> np.ndarray:
        p = self.params
        field = np.zeros_like(self._xx, dtype=np.float32)
        for i in range(len(p["cycles"])):
            field += p["amps"][i] * np.sin(
                2.0 * np.pi * (p["sx"][i] * self._xx + p["sy"][i] * self._yy + p["cycles"][i] * t)
                + p["phase"][i]
            )
        # Map field from approximately [-1, 1] into [0, 1].
        field = (field + 1.0) * 0.5
        field = np.clip(field, 0.0, 1.0)
        idx = (field * (self._gradient.shape[0] - 1)).astype(np.int32)
        rgb = self._gradient[idx].astype(np.float32)
        rgb *= self._vignette[..., None]
        return np.clip(rgb, 0, 255).astype(np.uint8)
