"""Command-line interface (companion to the GUI). Useful for batch / headless render."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from .generators import list_generators
from .palettes import list_palettes
from .renderer import RenderJob, render_to_file


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def main() -> None:
    """Motion Background Studio CLI."""


@main.command("list-styles")
def list_styles_cmd() -> None:
    for s in list_generators():
        click.echo(s)


@main.command("list-palettes")
def list_palettes_cmd() -> None:
    for p in list_palettes():
        click.echo(p)


@main.command("render")
@click.option("--style", required=True, type=click.Choice(list_generators(), case_sensitive=False))
@click.option("--palette", default="midnight_blue", type=click.Choice(list_palettes(), case_sensitive=False))
@click.option("--width", default=3840, type=int)
@click.option("--height", default=2160, type=int)
@click.option("--duration", default=15.0, type=float)
@click.option("--fps", default=30, type=int)
@click.option("--seed", default=None, type=int)
@click.option("--crf", default=18, type=int, show_default=True)
@click.option("--preset", default="medium", show_default=True)
@click.option("-o", "--output", default="out.mp4", type=click.Path(dir_okay=False, path_type=Path))
def render_cmd(style, palette, width, height, duration, fps, seed, crf, preset, output) -> None:
    """Render a single motion-background MP4."""
    job = RenderJob(
        style=style, palette=palette,
        width=width, height=height,
        duration=duration, fps=fps,
        seed=seed, crf=crf, preset=preset,
        output=output,
    )

    def progress(i: int, total: int | None) -> None:
        if not total:
            return
        bar = int(40 * i / total)
        sys.stdout.write(f"\r[{'#' * bar}{'.' * (40 - bar)}] {i}/{total}")
        sys.stdout.flush()

    out = render_to_file(job, progress_cb=progress)
    sys.stdout.write("\n")
    click.echo(f"Wrote {out}")


@main.command("batch")
@click.option("--style", required=True, type=click.Choice(list_generators(), case_sensitive=False))
@click.option("--palette", default=None,
              help="If omitted, cycles through every palette.")
@click.option("--count", default=4, type=int)
@click.option("--width", default=3840, type=int)
@click.option("--height", default=2160, type=int)
@click.option("--duration", default=15.0, type=float)
@click.option("--fps", default=30, type=int)
@click.option("--seed-start", default=1, type=int)
@click.option("--crf", default=18, type=int)
@click.option("--preset", default="medium")
@click.option("-d", "--out-dir", default="renders", type=click.Path(file_okay=False, path_type=Path))
def batch_cmd(style, palette, count, width, height, duration, fps, seed_start, crf, preset, out_dir) -> None:
    """Render many variations into a folder."""
    out_dir.mkdir(parents=True, exist_ok=True)
    palettes = [palette] if palette else list_palettes()
    rendered = 0
    for i in range(count):
        seed = seed_start + i
        pal = palettes[i % len(palettes)]
        job = RenderJob(
            style=style, palette=pal,
            width=width, height=height,
            duration=duration, fps=fps,
            seed=seed, crf=crf, preset=preset,
            output=out_dir / f"{style}_{pal}_seed{seed}_{width}x{height}.mp4",
        )

        def progress(idx: int, total: int | None, _job=job, _i=i) -> None:
            if not total:
                return
            bar = int(30 * idx / total)
            sys.stdout.write(f"\r[{_i+1}/{count}] {_job.output.name}: [{'#' * bar}{'.' * (30 - bar)}] {idx}/{total}")
            sys.stdout.flush()

        render_to_file(job, progress_cb=progress)
        sys.stdout.write("\n")
        rendered += 1
    click.echo(f"Done. Rendered {rendered} videos into {out_dir}")


if __name__ == "__main__":
    main()
