"""Tests for the perf-related additions: encoder selection + multiprocessing.

These tests check correctness rather than speed — the actual speedup is
hardware-dependent (NVENC needs an NVIDIA GPU; multiprocessing needs >1 core).
"""
from __future__ import annotations

import shutil

import pytest

from motion_bg_studio.encoder import _NVENC_PRESET_MAP, build_encoder_args, detect_gpu_encoder
from motion_bg_studio.renderer import RenderJob, _resolve_workers, render_to_file

# ---- Encoder argument builder ------------------------------------------------


def test_build_encoder_cpu_uses_libx264() -> None:
    args, name = build_encoder_args(1920, 1080, 30, 18, "medium", encoder="cpu")
    assert name == "libx264"
    assert "-c:v" in args
    assert args[args.index("-c:v") + 1] == "libx264"
    assert "-crf" in args
    assert "-preset" in args


def test_build_encoder_explicit_nvenc() -> None:
    args, name = build_encoder_args(1920, 1080, 30, 20, "medium", encoder="h264_nvenc")
    assert name == "h264_nvenc"
    assert args[args.index("-c:v") + 1] == "h264_nvenc"
    assert "-cq" in args
    assert args[args.index("-cq") + 1] == "20"


def test_build_encoder_explicit_qsv() -> None:
    args, name = build_encoder_args(1920, 1080, 30, 22, "fast", encoder="h264_qsv")
    assert name == "h264_qsv"
    assert "-global_quality" in args


def test_build_encoder_explicit_amf() -> None:
    args, name = build_encoder_args(1920, 1080, 30, 22, "fast", encoder="h264_amf")
    assert name == "h264_amf"
    assert "-qp_i" in args


def test_build_encoder_auto_falls_back_to_libx264_when_no_gpu(monkeypatch) -> None:
    # Force detect_gpu_encoder to return None (simulate no GPU).
    monkeypatch.setattr("motion_bg_studio.encoder.detect_gpu_encoder", lambda *a, **k: None)
    args, name = build_encoder_args(1920, 1080, 30, 18, "medium", encoder="auto")
    assert name == "libx264"


def test_build_encoder_gpu_falls_back_to_libx264_when_no_gpu(monkeypatch) -> None:
    # 'gpu' should also fall back gracefully (rather than producing a broken cmd).
    monkeypatch.setattr("motion_bg_studio.encoder.detect_gpu_encoder", lambda *a, **k: None)
    args, name = build_encoder_args(1920, 1080, 30, 18, "medium", encoder="gpu")
    assert name == "libx264"


def test_nvenc_preset_map_covers_all_libx264_presets() -> None:
    expected = {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"}
    assert expected.issubset(set(_NVENC_PRESET_MAP))


def test_detect_gpu_encoder_handles_missing_ffmpeg(monkeypatch) -> None:
    # If ffmpeg binary isn't found, detect should return None, not raise.
    def _raise(*a, **k):
        raise FileNotFoundError("no ffmpeg")
    monkeypatch.setattr("motion_bg_studio.encoder.find_ffmpeg", _raise)
    assert detect_gpu_encoder() is None


# ---- Worker resolution -------------------------------------------------------


def test_resolve_workers_explicit_passes_through() -> None:
    assert _resolve_workers(1) == 1
    assert _resolve_workers(2) == 2
    assert _resolve_workers(4) == 4


def test_resolve_workers_auto_uses_cpu_minus_one(monkeypatch) -> None:
    monkeypatch.setattr("motion_bg_studio.renderer.os.cpu_count", lambda: 4)
    assert _resolve_workers(0) == 3


def test_resolve_workers_auto_caps_at_8(monkeypatch) -> None:
    monkeypatch.setattr("motion_bg_studio.renderer.os.cpu_count", lambda: 32)
    assert _resolve_workers(0) == 8


def test_resolve_workers_auto_min_one(monkeypatch) -> None:
    monkeypatch.setattr("motion_bg_studio.renderer.os.cpu_count", lambda: 1)
    assert _resolve_workers(0) == 1


# ---- End-to-end: serial vs parallel produce identical output ----------------


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_serial_and_parallel_render_match(tmp_path) -> None:
    """Multiprocessing must not change the produced MP4 bytes vs serial mode."""
    out_serial = tmp_path / "serial.mp4"
    out_parallel = tmp_path / "parallel.mp4"
    common = dict(
        style="gradient_waves",
        palette="midnight_blue",
        width=160,
        height=90,
        duration=1,
        fps=4,
        seed=21,
        preset="ultrafast",
        encoder="cpu",  # force CPU so test is reproducible everywhere
    )
    render_to_file(RenderJob(workers=1, output=out_serial, **common))
    render_to_file(RenderJob(workers=2, output=out_parallel, **common))
    assert out_serial.read_bytes() == out_parallel.read_bytes()
