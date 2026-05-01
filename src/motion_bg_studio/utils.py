"""Shared math utilities: seeded RNG, easing, vectorized loop-friendly noise."""
from __future__ import annotations

import math

import numpy as np


def make_rng(seed: int | None) -> np.random.Generator:
    return np.random.default_rng(seed)


def smoothstep(x: np.ndarray | float) -> np.ndarray | float:
    """Smooth Hermite interpolation in [0, 1]."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def ease_in_out(x: np.ndarray | float) -> np.ndarray | float:
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0.0, 1.0))


def lerp(a, b, t):
    return a + (b - a) * t


def hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError("hex color must be #RRGGBB")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


# ---------------------------------------------------------------------------
# Vectorized value noise that is seamless along a "time" axis. We sample 2D
# value noise at flowing coordinates that trace a circle in noise-space, so
# advancing t by a full loop returns to the starting point exactly.
# ---------------------------------------------------------------------------


class LoopNoise2D:
    """Cosine-interpolated value noise on a periodic 2D grid.

    Sampling at (x + dx, y + dy) where (dx, dy) traces a closed loop over the
    animation duration gives a seamless animation. We use a hash-based pseudo-
    random gradient grid; the grid is finite (period * period) and the lookup
    wraps modularly so the noise is also tileable.
    """

    def __init__(self, period: int = 256, seed: int | None = None):
        self.period = int(period)
        rng = np.random.default_rng(seed)
        self.grid = rng.random((self.period, self.period), dtype=np.float32)

    def sample(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Sample noise at fractional coordinates. Output in [0, 1]."""
        p = self.period
        x = x % p
        y = y % p
        x0 = np.floor(x).astype(np.int32)
        y0 = np.floor(y).astype(np.int32)
        xf = x - x0
        yf = y - y0
        x1 = (x0 + 1) % p
        y1 = (y0 + 1) % p
        x0 %= p
        y0 %= p

        v00 = self.grid[y0, x0]
        v10 = self.grid[y0, x1]
        v01 = self.grid[y1, x0]
        v11 = self.grid[y1, x1]

        # Cosine interpolation for visually smoother result than linear.
        u = (1.0 - np.cos(xf * math.pi)) * 0.5
        v = (1.0 - np.cos(yf * math.pi)) * 0.5

        a = v00 + (v10 - v00) * u
        b = v01 + (v11 - v01) * u
        return a + (b - a) * v


def fbm(
    noise: LoopNoise2D,
    x: np.ndarray,
    y: np.ndarray,
    octaves: int = 4,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> np.ndarray:
    """Fractal Brownian motion built on top of LoopNoise2D."""
    total = np.zeros_like(x, dtype=np.float32)
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += amp * noise.sample(x * freq, y * freq)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / max(norm, 1e-9)


def loop_offset(t: float, radius: float = 1.0) -> tuple[float, float]:
    """Return (dx, dy) on a circle of given radius parameterised by t in [0, 1].

    Sampling 2D noise at coordinates offset by this loop yields a perfectly
    seamless animation: when t goes from 0 to 1, the offset returns to itself.
    """
    a = 2.0 * math.pi * t
    return radius * math.cos(a), radius * math.sin(a)
