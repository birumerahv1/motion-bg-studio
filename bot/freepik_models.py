"""Freepik model catalog — Python port of web/lib/models.ts.

Keep this file in sync with web/lib/models.ts. The web app and the bot must
agree on the exact `postPath` / `taskBasePath` / payload field names so a key
that works in one works in the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["text-to-image", "text-to-video", "image-to-video", "motion-control"]
ResultKind = Literal["image", "video"]


@dataclass(frozen=True)
class Supports:
    aspect_ratio: bool = False
    resolution: bool = False
    duration: bool = False
    negative_prompt: bool = False
    start_image: bool = False
    end_image: bool = False
    reference_video: bool = False
    audio: bool = False


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    vendor: str
    mode: Mode
    result_kind: ResultKind
    post_path: str
    task_base_path: str
    description: str
    supports: Supports = field(default_factory=Supports)
    aspect_ratio_options: tuple[str, ...] = ()
    resolution_options: tuple[str, ...] = ()
    duration_options: tuple[str, ...] = ()


MODELS: tuple[Model, ...] = (
    # ---- Text-to-image ----
    Model(
        id="nano-banana-pro",
        label="Nano Banana Pro",
        vendor="Google · Gemini 3",
        mode="text-to-image",
        result_kind="image",
        post_path="/v1/ai/text-to-image/nano-banana-pro",
        task_base_path="/v1/ai/text-to-image/nano-banana-pro",
        description="Highest fidelity text-to-image. Up to 4K.",
        supports=Supports(aspect_ratio=True, resolution=True),
        aspect_ratio_options=("1:1", "2:3", "3:2", "4:3", "3:4", "16:9", "9:16", "21:9"),
        resolution_options=("1K", "2K", "4K"),
    ),
    Model(
        id="seedream-v4-5",
        label="Seedream 4.5",
        vendor="ByteDance",
        mode="text-to-image",
        result_kind="image",
        post_path="/v1/ai/text-to-image/seedream-v4-5",
        task_base_path="/v1/ai/text-to-image/seedream-v4-5",
        description="Best for posters, branded visuals, typography.",
        supports=Supports(aspect_ratio=True, resolution=True),
        aspect_ratio_options=("1:1", "2:3", "3:2", "4:3", "3:4", "16:9", "9:16", "21:9"),
        resolution_options=("1k", "2k", "4k"),
    ),
    # ---- Text-to-video ----
    Model(
        id="veo-3-1",
        label="Veo 3.1",
        vendor="Google",
        mode="text-to-video",
        result_kind="video",
        post_path="/v1/ai/text-to-video/veo-3-1",
        task_base_path="/v1/ai/text-to-video/veo-3-1",
        description="Cinematic Veo 3.1 with native audio. 4-8s, up to 4K.",
        supports=Supports(
            aspect_ratio=True,
            resolution=True,
            duration=True,
            negative_prompt=True,
            audio=True,
        ),
        aspect_ratio_options=("16:9", "9:16"),
        resolution_options=("720p", "1080p", "4k"),
        duration_options=("4", "6", "8"),
    ),
    Model(
        id="kling-v3-pro-t2v",
        label="Kling 3 Pro · T2V",
        vendor="Kling",
        mode="text-to-video",
        result_kind="video",
        post_path="/v1/ai/video/kling-v3-pro",
        task_base_path="/v1/ai/video/kling-v3-pro",
        description="Highest-quality Kling 3 Pro text-to-video.",
        supports=Supports(
            aspect_ratio=True, duration=True, negative_prompt=True, audio=True
        ),
        aspect_ratio_options=("16:9", "9:16", "1:1"),
        duration_options=("3", "5", "10", "15"),
    ),
    # ---- Image-to-video ----
    Model(
        id="kling-v3-pro-i2v",
        label="Kling 3 Pro · I2V",
        vendor="Kling",
        mode="image-to-video",
        result_kind="video",
        post_path="/v1/ai/video/kling-v3-pro",
        task_base_path="/v1/ai/video/kling-v3-pro",
        description="Animate a still with Kling 3 Pro.",
        supports=Supports(
            aspect_ratio=True,
            duration=True,
            negative_prompt=True,
            start_image=True,
            end_image=True,
            audio=True,
        ),
        aspect_ratio_options=("16:9", "9:16", "1:1"),
        duration_options=("3", "5", "10", "15"),
    ),
    Model(
        id="kling-v2-6-pro-i2v",
        label="Kling 2.6 Pro · I2V",
        vendor="Kling",
        mode="image-to-video",
        result_kind="video",
        post_path="/v1/ai/image-to-video/kling-v2-6-pro",
        task_base_path="/v1/ai/image-to-video/kling-v2-6-pro",
        description="Stable Kling 2.6 Pro image-to-video. 5s or 10s.",
        supports=Supports(
            duration=True, negative_prompt=True, start_image=True, end_image=True
        ),
        duration_options=("5", "10"),
    ),
    Model(
        id="seedance-pro-720p",
        label="Seedance Pro · 720p",
        vendor="ByteDance",
        mode="image-to-video",
        result_kind="video",
        post_path="/v1/ai/image-to-video/seedance-pro-720p",
        task_base_path="/v1/ai/image-to-video/seedance-pro-720p",
        description="Fast Seedance Pro at 720p.",
        supports=Supports(aspect_ratio=True, duration=True, start_image=True),
        aspect_ratio_options=("16:9", "9:16", "1:1"),
        duration_options=("5", "10"),
    ),
    Model(
        id="seedance-pro-1080p",
        label="Seedance Pro · 1080p",
        vendor="ByteDance",
        mode="image-to-video",
        result_kind="video",
        post_path="/v1/ai/image-to-video/seedance-pro-1080p",
        task_base_path="/v1/ai/image-to-video/seedance-pro-1080p",
        description="Higher-quality 1080p Seedance Pro image-to-video.",
        supports=Supports(aspect_ratio=True, duration=True, start_image=True),
        aspect_ratio_options=("16:9", "9:16", "1:1"),
        duration_options=("5", "10"),
    ),
    # ---- Motion Control ----
    Model(
        id="kling-v2-6-motion-control-pro",
        label="Kling 2.6 Pro · Motion Control",
        vendor="Kling",
        mode="motion-control",
        result_kind="video",
        post_path="/v1/ai/video/kling-v2-6-motion-control-pro",
        task_base_path="/v1/ai/video/kling-v2-6-motion-control-pro",
        description="Transfer motion from a reference video onto a character image.",
        supports=Supports(
            start_image=True, reference_video=True, negative_prompt=True
        ),
    ),
    Model(
        id="kling-v2-6-motion-control-std",
        label="Kling 2.6 Std · Motion Control",
        vendor="Kling",
        mode="motion-control",
        result_kind="video",
        post_path="/v1/ai/video/kling-v2-6-motion-control-std",
        task_base_path="/v1/ai/video/kling-v2-6-motion-control-std",
        description="Faster Kling 2.6 Standard motion-control.",
        supports=Supports(
            start_image=True, reference_video=True, negative_prompt=True
        ),
    ),
    Model(
        id="kling-v3-omni-pro",
        label="Kling 3 Omni Pro · Motion Control",
        vendor="Kling",
        mode="motion-control",
        result_kind="video",
        post_path="/v1/ai/reference-to-video/kling-v3-omni-pro",
        task_base_path="/v1/ai/reference-to-video/kling-v3-omni-pro",
        description="Latest Kling 3 Omni Pro reference-to-video.",
        supports=Supports(
            start_image=True,
            reference_video=True,
            negative_prompt=True,
            duration=True,
        ),
        duration_options=("3", "5", "10", "15"),
    ),
)


def get_model(model_id: str) -> Model | None:
    for m in MODELS:
        if m.id == model_id:
            return m
    return None


def models_for_mode(mode: Mode) -> list[Model]:
    return [m for m in MODELS if m.mode == mode]


def build_post_body(model: Model, payload: dict) -> dict:
    """Mirror of buildPostBody in web/lib/freepik.ts.

    Field names diverge per endpoint per Freepik's OpenAPI spec, so we
    handle each one explicitly rather than passing through a generic shape.
    """
    body: dict = {}
    p = payload

    if model.id == "nano-banana-pro":
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("aspect_ratio"):
            body["aspect_ratio"] = p["aspect_ratio"]
        if p.get("resolution"):
            body["resolution"] = p["resolution"]
        return body

    if model.id == "seedream-v4-5":
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("aspect_ratio"):
            body["aspect_ratio"] = p["aspect_ratio"]
        if p.get("resolution"):
            body["resolution"] = p["resolution"].lower()
        return body

    if model.id == "veo-3-1":
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("negative_prompt"):
            body["negative_prompt"] = p["negative_prompt"]
        if p.get("duration") is not None:
            body["duration"] = int(p["duration"])
        if p.get("resolution"):
            body["resolution"] = p["resolution"]
        if p.get("aspect_ratio"):
            body["aspect_ratio"] = p["aspect_ratio"]
        if p.get("generate_audio") is not None:
            body["generate_audio"] = bool(p["generate_audio"])
        return body

    if model.id in ("kling-v3-pro-t2v", "kling-v3-pro-i2v"):
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("negative_prompt"):
            body["negative_prompt"] = p["negative_prompt"]
        if p.get("aspect_ratio"):
            body["aspect_ratio"] = p["aspect_ratio"]
        if p.get("duration") is not None:
            body["duration"] = int(p["duration"])
        if p.get("start_image_url"):
            body["start_image_url"] = p["start_image_url"]
        if p.get("end_image_url"):
            body["end_image_url"] = p["end_image_url"]
        if p.get("generate_audio") is not None:
            body["generate_audio"] = bool(p["generate_audio"])
        return body

    if model.id == "kling-v2-6-pro-i2v":
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("negative_prompt"):
            body["negative_prompt"] = p["negative_prompt"]
        if p.get("duration") is not None:
            body["duration"] = str(p["duration"])
        if p.get("start_image_url"):
            body["image_url"] = p["start_image_url"]
        if p.get("end_image_url"):
            body["image_tail_url"] = p["end_image_url"]
        return body

    if model.id in ("seedance-pro-720p", "seedance-pro-1080p"):
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("start_image_url"):
            body["image"] = p["start_image_url"]
        if p.get("duration") is not None:
            body["duration"] = str(p["duration"])
        if p.get("aspect_ratio"):
            body["aspect_ratio"] = p["aspect_ratio"]
        return body

    if model.id in ("kling-v2-6-motion-control-pro", "kling-v2-6-motion-control-std"):
        if p.get("start_image_url"):
            body["image_url"] = p["start_image_url"]
        if p.get("reference_video_url"):
            body["video_url"] = p["reference_video_url"]
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("negative_prompt"):
            body["negative_prompt"] = p["negative_prompt"]
        return body

    if model.id == "kling-v3-omni-pro":
        if p.get("reference_video_url"):
            body["video_url"] = p["reference_video_url"]
        if p.get("start_image_url"):
            body["image_url"] = p["start_image_url"]
        if p.get("prompt"):
            body["prompt"] = p["prompt"]
        if p.get("negative_prompt"):
            body["negative_prompt"] = p["negative_prompt"]
        if p.get("duration") is not None:
            body["duration"] = int(p["duration"])
        if p.get("aspect_ratio"):
            body["aspect_ratio"] = p["aspect_ratio"]
        return body

    return body


def extract_result_urls(task_data: object) -> list[str]:
    """Extract every http(s) URL from a Freepik task payload, dedup-preserving."""
    urls: list[str] = []
    seen: set[str] = set()

    def walk(v: object) -> None:
        if isinstance(v, str) and v.startswith("http"):
            if v not in seen:
                seen.add(v)
                urls.append(v)
        elif isinstance(v, list):
            for item in v:
                walk(item)
        elif isinstance(v, dict):
            for value in v.values():
                walk(value)

    if isinstance(task_data, dict):
        for key in ("generated", "output_url", "video_url", "images", "results"):
            if key in task_data:
                walk(task_data[key])
        # Fallback: walk the whole payload if nothing was found in the
        # well-known keys (some endpoints nest results unexpectedly).
        if not urls:
            walk(task_data)
    return urls
