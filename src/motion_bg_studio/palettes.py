"""Curated color palettes optimized for microstock motion backgrounds.

Each palette is a list of (R, G, B) tuples in 0-255 range. Palettes are tuned for
brand-friendly, calm, premium-looking backgrounds (avoid neon clash that looks AI-generated).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    colors: tuple[tuple[int, int, int], ...]
    background: tuple[int, int, int]


PALETTES: dict[str, Palette] = {
    "midnight_blue": Palette(
        "Midnight Blue",
        ((28, 50, 110), (52, 110, 200), (120, 180, 255), (200, 220, 255)),
        (8, 14, 38),
    ),
    "sunset_warm": Palette(
        "Sunset Warm",
        ((255, 120, 80), (255, 170, 90), (250, 210, 130), (255, 240, 200)),
        (40, 18, 30),
    ),
    "emerald_forest": Palette(
        "Emerald Forest",
        ((20, 80, 60), (50, 140, 100), (110, 200, 150), (200, 240, 210)),
        (8, 22, 18),
    ),
    "rose_gold": Palette(
        "Rose Gold",
        ((180, 100, 110), (220, 150, 140), (240, 190, 170), (250, 220, 200)),
        (30, 18, 22),
    ),
    "deep_purple": Palette(
        "Deep Purple",
        ((60, 30, 90), (110, 60, 160), (180, 120, 220), (220, 200, 240)),
        (14, 8, 28),
    ),
    "monochrome": Palette(
        "Monochrome",
        ((40, 40, 40), (90, 90, 90), (160, 160, 160), (230, 230, 230)),
        (8, 8, 8),
    ),
    "teal_cyan": Palette(
        "Teal Cyan",
        ((10, 80, 100), (40, 150, 170), (100, 210, 220), (200, 240, 245)),
        (4, 18, 26),
    ),
    "amber_gold": Palette(
        "Amber Gold",
        ((140, 80, 20), (210, 140, 40), (240, 190, 80), (255, 230, 160)),
        (30, 18, 8),
    ),
    "arctic_ice": Palette(
        "Arctic Ice",
        ((150, 200, 230), (200, 230, 250), (230, 245, 255), (255, 255, 255)),
        (50, 80, 110),
    ),
    "crimson_red": Palette(
        "Crimson Red",
        ((100, 20, 30), (180, 40, 50), (230, 90, 100), (250, 180, 180)),
        (30, 6, 10),
    ),
}


def list_palettes() -> list[str]:
    return list(PALETTES.keys())


def get_palette(name: str) -> Palette:
    if name not in PALETTES:
        raise KeyError(f"Unknown palette '{name}'. Available: {', '.join(PALETTES)}")
    return PALETTES[name]
