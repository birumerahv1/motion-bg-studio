import type { Mode, ModelId, ResultKind } from "./types";

export interface ModelDescriptor {
  id: ModelId;
  label: string;
  vendor: string;
  mode: Mode;
  resultKind: ResultKind;
  postPath: string;
  taskBasePath: string;
  supports: {
    aspectRatio?: boolean;
    resolution?: boolean;
    duration?: boolean;
    negativePrompt?: boolean;
    startImage?: boolean;
    endImage?: boolean;
    referenceVideo?: boolean;
    audio?: boolean;
  };
  durationOptions?: (number | string)[];
  resolutionOptions?: string[];
  aspectRatioOptions?: string[];
  description: string;
}

export const MODELS: ModelDescriptor[] = [
  // ---- Text-to-image ----
  {
    id: "nano-banana-pro",
    label: "Nano Banana Pro",
    vendor: "Google · Gemini 3",
    mode: "text-to-image",
    resultKind: "image",
    postPath: "/v1/ai/text-to-image/nano-banana-pro",
    taskBasePath: "/v1/ai/text-to-image/nano-banana-pro",
    supports: { aspectRatio: true, resolution: true },
    aspectRatioOptions: ["1:1", "2:3", "3:2", "4:3", "3:4", "5:4", "4:5", "16:9", "9:16", "21:9"],
    resolutionOptions: ["1K", "2K", "4K"],
    description:
      "Highest fidelity text-to-image with complex composition and reference image support. Up to 4K.",
  },
  {
    id: "seedream-v4-5",
    label: "Seedream 4.5",
    vendor: "ByteDance",
    mode: "text-to-image",
    resultKind: "image",
    postPath: "/v1/ai/text-to-image/seedream-v4-5",
    taskBasePath: "/v1/ai/text-to-image/seedream-v4-5",
    supports: { aspectRatio: true, resolution: true },
    aspectRatioOptions: ["1:1", "2:3", "3:2", "4:3", "3:4", "16:9", "9:16", "21:9"],
    resolutionOptions: ["1k", "2k", "4k"],
    description:
      "Best for posters, branded visuals, typography. Latest Seedream tier on Freepik (4.5 is current GA).",
  },

  // ---- Text-to-video ----
  {
    id: "veo-3-1",
    label: "Veo 3.1",
    vendor: "Google",
    mode: "text-to-video",
    resultKind: "video",
    postPath: "/v1/ai/text-to-video/veo-3-1",
    taskBasePath: "/v1/ai/text-to-video/veo-3-1",
    supports: { aspectRatio: true, resolution: true, duration: true, negativePrompt: true, audio: true },
    aspectRatioOptions: ["16:9", "9:16"],
    resolutionOptions: ["720p", "1080p", "4k"],
    durationOptions: [4, 6, 8],
    description:
      "Cinematic Veo 3.1 with native audio. 4-8s, up to 4K. Great for marketing & narrative shots.",
  },
  {
    id: "kling-v3-pro-t2v",
    label: "Kling 3 Pro · T2V",
    vendor: "Kling",
    mode: "text-to-video",
    resultKind: "video",
    postPath: "/v1/ai/video/kling-v3-pro",
    taskBasePath: "/v1/ai/video/kling-v3-pro",
    supports: { aspectRatio: true, duration: true, negativePrompt: true, audio: true },
    aspectRatioOptions: ["16:9", "9:16", "1:1"],
    durationOptions: [3, 5, 10, 15],
    description:
      "Highest-quality Kling 3 Pro in pure text-to-video mode. Up to 1080p, 3-15s, multi-shot capable.",
  },

  // ---- Image-to-video ----
  {
    id: "kling-v3-pro-i2v",
    label: "Kling 3 Pro · I2V",
    vendor: "Kling",
    mode: "image-to-video",
    resultKind: "video",
    postPath: "/v1/ai/video/kling-v3-pro",
    taskBasePath: "/v1/ai/video/kling-v3-pro",
    supports: {
      aspectRatio: true,
      duration: true,
      negativePrompt: true,
      startImage: true,
      endImage: true,
      audio: true,
    },
    aspectRatioOptions: ["16:9", "9:16", "1:1"],
    durationOptions: [3, 5, 10, 15],
    description:
      "Animate a still image with Kling 3 Pro using start (and optional end) frame. 3-15s.",
  },
  {
    id: "kling-v2-6-pro-i2v",
    label: "Kling 2.6 Pro · I2V",
    vendor: "Kling",
    mode: "image-to-video",
    resultKind: "video",
    postPath: "/v1/ai/image-to-video/kling-v2-6-pro",
    taskBasePath: "/v1/ai/image-to-video/kling-v2-6-pro",
    supports: { duration: true, negativePrompt: true, startImage: true, endImage: true },
    durationOptions: [5, 10],
    description:
      "Stable Kling 2.6 Pro image-to-video. Good baseline at 5s or 10s.",
  },
  {
    id: "seedance-pro-720p",
    label: "Seedance Pro · 720p",
    vendor: "ByteDance",
    mode: "image-to-video",
    resultKind: "video",
    postPath: "/v1/ai/image-to-video/seedance-pro-720p",
    taskBasePath: "/v1/ai/image-to-video/seedance-pro-720p",
    supports: { aspectRatio: true, duration: true, startImage: true },
    aspectRatioOptions: ["16:9", "9:16", "1:1"],
    durationOptions: ["5", "10"],
    description:
      "Fast Seedance Pro at 720p for snappy 5s loops. (Latest GA Seedance tier on Freepik.)",
  },
  {
    id: "seedance-pro-1080p",
    label: "Seedance Pro · 1080p",
    vendor: "ByteDance",
    mode: "image-to-video",
    resultKind: "video",
    postPath: "/v1/ai/image-to-video/seedance-pro-1080p",
    taskBasePath: "/v1/ai/image-to-video/seedance-pro-1080p",
    supports: { aspectRatio: true, duration: true, startImage: true },
    aspectRatioOptions: ["16:9", "9:16", "1:1"],
    durationOptions: ["5", "10"],
    description: "Higher-quality 1080p Seedance Pro image-to-video.",
  },

  // ---- Motion Control ----
  {
    id: "kling-v2-6-motion-control-pro",
    label: "Kling 2.6 Pro · Motion Control",
    vendor: "Kling",
    mode: "motion-control",
    resultKind: "video",
    postPath: "/v1/ai/video/kling-v2-6-motion-control-pro",
    taskBasePath: "/v1/ai/video/kling-v2-6-motion-control-pro",
    supports: { startImage: true, referenceVideo: true, negativePrompt: true },
    description:
      "Transfer motion from a reference video onto a character image. Highest fidelity tier.",
  },
  {
    id: "kling-v2-6-motion-control-std",
    label: "Kling 2.6 Std · Motion Control",
    vendor: "Kling",
    mode: "motion-control",
    resultKind: "video",
    postPath: "/v1/ai/video/kling-v2-6-motion-control-std",
    taskBasePath: "/v1/ai/video/kling-v2-6-motion-control-std",
    supports: { startImage: true, referenceVideo: true, negativePrompt: true },
    description: "Faster Kling 2.6 Standard motion-control transfer.",
  },
  {
    id: "kling-v3-omni-pro",
    label: "Kling 3 Omni Pro · Motion Control",
    vendor: "Kling",
    mode: "motion-control",
    resultKind: "video",
    postPath: "/v1/ai/reference-to-video/kling-v3-omni-pro",
    taskBasePath: "/v1/ai/reference-to-video/kling-v3-omni-pro",
    supports: { startImage: true, referenceVideo: true, negativePrompt: true, duration: true },
    durationOptions: [3, 5, 10, 15],
    description:
      "Latest Kling 3 Omni Pro reference-to-video for motion/style transfer with optional image start.",
  },
];

export function getModel(id: ModelId): ModelDescriptor | undefined {
  return MODELS.find((m) => m.id === id);
}

export function modelsForMode(mode: Mode): ModelDescriptor[] {
  return MODELS.filter((m) => m.mode === mode);
}
