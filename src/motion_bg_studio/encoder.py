"""ffmpeg-based MP4 encoder. Frames are piped as raw RGB24 to ffmpeg's stdin.

Designed to:
* Use H.264 (yuv420p) so the output is universally accepted by microstock sites.
* Pick a high-quality CRF by default (18) with veryslow-ish preset for delivery.
* Accept any (even-numbered) resolution; ffmpeg requires even dimensions for yuv420p.
* Optionally use a hardware H.264 encoder (NVENC / QSV / AMF) when available
  via auto-detection. Hardware encoders offload work from the CPU and free
  cores for the procedural frame generation, which is the real bottleneck.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# Mapping libx264 presets to NVENC preset names. NVENC has fewer levels
# and naming conventions differ; we collapse libx264's fine-grained
# presets onto NVENC's coarser ladder.
_NVENC_PRESET_MAP = {
    "ultrafast": "fast",
    "superfast": "fast",
    "veryfast": "fast",
    "faster": "fast",
    "fast": "fast",
    "medium": "medium",
    "slow": "slow",
    "slower": "slow",
    "veryslow": "slow",
}


def find_ffmpeg() -> str:
    """Locate ffmpeg binary. Order: bundled (next to executable), env, PATH."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        for cand in (base / "ffmpeg.exe", base / "ffmpeg", base / "bin" / "ffmpeg.exe", base / "bin" / "ffmpeg"):
            if cand.exists():
                return str(cand)
    env = os.environ.get("MOTION_BG_FFMPEG")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError(
        "ffmpeg not found. Install ffmpeg, place it next to the app executable, "
        "or set MOTION_BG_FFMPEG to its full path."
    )


def detect_gpu_encoder(ffmpeg_path: str | None = None) -> str | None:
    """Probe the ffmpeg binary for an available H.264 hardware encoder.

    Returns the codec string (``h264_nvenc`` / ``h264_qsv`` / ``h264_amf``)
    or ``None`` if no hardware encoder is available. Detection is purely
    capability-based — we still try a tiny test encode in the caller to
    confirm the GPU itself is functional, since some builds advertise
    encoders for hardware that isn't physically present on this machine.
    """
    if ffmpeg_path is None:
        try:
            ffmpeg_path = find_ffmpeg()
        except FileNotFoundError:
            return None
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    text = (result.stdout or "") + (result.stderr or "")
    for enc in ("h264_nvenc", "h264_qsv", "h264_amf"):
        if enc in text:
            if _hw_encode_works(ffmpeg_path, enc):
                return enc
    return None


def _hw_encode_works(ffmpeg_path: str, codec: str) -> bool:
    """Run a 1-frame dummy encode to confirm the hardware path actually works."""
    try:
        proc = subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel", "error",
                "-f", "lavfi",
                "-i", "color=black:s=64x64:d=0.1",
                "-c:v", codec,
                "-frames:v", "1",
                "-f", "null",
                "-",
            ],
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return proc.returncode == 0


def build_encoder_args(
    width: int,
    height: int,
    fps: int,
    crf: int,
    preset: str,
    pixel_format: str = "yuv420p",
    encoder: str = "auto",
    ffmpeg_path: str | None = None,
) -> tuple[list[str], str]:
    """Return (ffmpeg_codec_args, codec_name_used).

    ``encoder`` is one of:
    - ``"cpu"`` / ``"libx264"``: software libx264 (default fallback).
    - ``"gpu"`` / ``"auto"``: pick the first available HW encoder; otherwise libx264.
    - explicit codec name (``"h264_nvenc"`` etc.) to force.
    """
    chosen: str | None = None
    enc_norm = (encoder or "auto").lower()
    if enc_norm in {"cpu", "libx264", "x264"}:
        chosen = "libx264"
    elif enc_norm in {"gpu", "auto", "hw", "hardware"}:
        chosen = detect_gpu_encoder(ffmpeg_path)
        if chosen is None:
            chosen = "libx264"
    else:
        chosen = enc_norm

    args: list[str]
    if chosen == "h264_nvenc":
        nvenc_preset = _NVENC_PRESET_MAP.get(preset, "medium")
        args = [
            "-c:v", "h264_nvenc",
            "-preset", nvenc_preset,
            "-rc", "vbr",
            "-cq", str(crf),
            "-b:v", "0",
            "-pix_fmt", pixel_format,
            "-movflags", "+faststart",
        ]
    elif chosen == "h264_qsv":
        args = [
            "-c:v", "h264_qsv",
            "-global_quality", str(crf),
            "-look_ahead", "0",
            "-pix_fmt", pixel_format,
            "-movflags", "+faststart",
        ]
    elif chosen == "h264_amf":
        args = [
            "-c:v", "h264_amf",
            "-quality", "balanced",
            "-rc", "cqp",
            "-qp_i", str(crf),
            "-qp_p", str(crf),
            "-pix_fmt", pixel_format,
            "-movflags", "+faststart",
        ]
    else:
        chosen = "libx264"
        args = [
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", pixel_format,
            "-movflags", "+faststart",
        ]
    return args, chosen


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
    encoder: str = "auto",
) -> Path:
    """Encode an iterable of HxWx3 uint8 frames into an MP4 file.

    ``progress_cb(i, total)`` is called every frame.
    ``encoder`` controls the codec: ``"cpu"`` (libx264), ``"gpu"`` (first
    available HW encoder), ``"auto"`` (HW if available, else libx264),
    or an explicit codec name like ``"h264_nvenc"``.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if width % 2 or height % 2:
        raise ValueError(f"width/height must be even for yuv420p (got {width}x{height})")

    ffmpeg_path = find_ffmpeg()
    codec_args, codec_used = build_encoder_args(
        width=width,
        height=height,
        fps=fps,
        crf=crf,
        preset=preset,
        pixel_format=pixel_format,
        encoder=encoder,
        ffmpeg_path=ffmpeg_path,
    )

    cmd = [
        ffmpeg_path,
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        *codec_args,
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
            raise RuntimeError(f"ffmpeg failed (encoder={codec_used}, exit {rc}): {err.strip()}")
    return output
