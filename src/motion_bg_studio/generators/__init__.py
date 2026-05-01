"""Registry of all generators."""
from __future__ import annotations

from .base import Generator
from .geometric import GeometricGenerator
from .gradient_waves import GradientWavesGenerator
from .light_leaks import LightLeaksGenerator
from .liquid import LiquidGenerator
from .particles import ParticlesGenerator
from .plexus import PlexusGenerator

GENERATORS: dict[str, type[Generator]] = {
    g.name: g
    for g in [
        ParticlesGenerator,
        GradientWavesGenerator,
        GeometricGenerator,
        LightLeaksGenerator,
        PlexusGenerator,
        LiquidGenerator,
    ]
}


def list_generators() -> list[str]:
    return list(GENERATORS.keys())


def get_generator(name: str) -> type[Generator]:
    if name not in GENERATORS:
        raise KeyError(f"Unknown generator '{name}'. Available: {', '.join(GENERATORS)}")
    return GENERATORS[name]


__all__ = ["GENERATORS", "Generator", "get_generator", "list_generators"]
