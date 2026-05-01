"""ffmpeg-based MP4 encoder. Frames are piped as raw RGB24 to ffmpeg's stdin.

Designed to:
* Use H.264 (yuv420p) so the output is universally accepted by microstock sites.
* Pick a high-quality CRF by default (18) with veryslow-ish preset for delivery.
* Accept any (even-numbered) resolution; ffmpeg requires even dimensions for yuv420p.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path


def find_ffmpeg() -> str:
    """Locate ffmpeg binary. Order: bundled (next to executable), env, PATH."""
    # 1. Bundled with the PyInstaller-built app.
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        for cand in (base / "ffmpeg.exe", base / "ffmpeg", base / "bin" / "ffmpeg.exe", base / "bin" / "ffmpeg"):
            if cand.exists():
                return str(cand)
    # 2. Explicit override.
    env = os.environ.get("MOTION_BG_FFMPEG")
    if env and Path(env).exists():
        return env
    # 3. PATH.
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError(
        "ffmpeg not found. Install ffmpeg, place it next to the app executable, "
        "or set MOTION_BG_FFMPEG to its full path."
    )


def encode_video(
    frames: Iterable,
    output: str | Path,
    width: int,
    height: int,
    fps: int = 30,
    crf: int = 18,
    preset: str = "medium",
    pixel_format: str = "yuv420p",
    extra_args: list[str] | None = None,
    progress_cb=None,
    total_frames: int | None = None,
) -> Path:
    """Encode an iterable of HxWx3 uint8 frames into an MP4 file.

    progress_cb(i, total) is called every frame.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if width % 2 or height % 2:
        raise ValueError(f"width/height must be even for yuv420p (got {width}x{height})")

    cmd = [
        find_ffmpeg(),
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", pixel_format,
        "-movflags", "+faststart",
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(str(output))

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i, frame in enumerate(frames):
            if frame.shape != (height, width, 3):
                raise ValueError(f"frame {i} has shape {frame.shape}, expected {(height, width, 3)}")
            if frame.dtype.name != "uint8":
                raise ValueError(f"frame {i} dtype {frame.dtype} is not uint8")
            proc.stdin.write(frame.tobytes())
            if progress_cb is not None:
                progress_cb(i + 1, total_frames)
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        rc = proc.wait()
        err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed (exit {rc}): {err.strip()}")
    return output
