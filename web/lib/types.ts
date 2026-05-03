export type Mode =
  | "text-to-image"
  | "text-to-video"
  | "image-to-video"
  | "motion-control";

export type ModelId =
  // text-to-image
  | "nano-banana-pro"
  | "seedream-v4-5"
  // text-to-video
  | "veo-3-1"
  | "kling-v3-pro-t2v"
  // image-to-video
  | "kling-v3-pro-i2v"
  | "seedance-pro-720p"
  | "seedance-pro-1080p"
  | "kling-v2-6-pro-i2v"
  // motion-control
  | "kling-v2-6-motion-control-pro"
  | "kling-v2-6-motion-control-std"
  | "kling-v3-omni-pro";

export type AspectRatio =
  | "1:1"
  | "2:3"
  | "3:2"
  | "4:3"
  | "3:4"
  | "5:4"
  | "4:5"
  | "16:9"
  | "9:16"
  | "21:9";

export type TaskStatus = "CREATED" | "IN_PROGRESS" | "COMPLETED" | "FAILED";

export interface FreepikTaskResponse {
  data: {
    task_id: string;
    status: TaskStatus;
    generated?: string[];
  };
}

export type ResultKind = "image" | "video";

export interface GalleryItem {
  id: string;
  mode: Mode;
  modelId: ModelId;
  prompt: string;
  negativePrompt?: string;
  aspectRatio?: AspectRatio;
  duration?: number | string;
  resolution?: string;
  startImageUrl?: string;
  endImageUrl?: string;
  referenceVideoUrl?: string;
  taskId: string;
  apiKeyFingerprint: string;
  status: TaskStatus | "QUEUED";
  resultKind: ResultKind;
  resultUrls: string[];
  errorMessage?: string;
  createdAt: number;
  updatedAt: number;
}

export interface ApiKeyEntry {
  id: string;
  label: string;
  value: string;
  enabled: boolean;
  lastError?: string;
  cooldownUntil?: number;
}
