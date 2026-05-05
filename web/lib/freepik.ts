import type { ModelDescriptor } from "./models";

export const FREEPIK_BASE = "https://api.freepik.com";

export interface FreepikCallResult<T = unknown> {
  ok: boolean;
  status: number;
  data?: T;
  errorMessage?: string;
  apiKeyIndex?: number;
  apiKeyFingerprint?: string;
}

/**
 * Fingerprints an API key with a non-reversible short hash for identifying
 * which key was used for a given task without leaking the key itself.
 */
export function fingerprintKey(key: string): string {
  let h = 5381;
  for (let i = 0; i < key.length; i++) {
    h = ((h << 5) + h + key.charCodeAt(i)) | 0;
  }
  // Append the last 4 chars (visible in UI) so users can identify the key.
  const tail = key.slice(-4);
  return `${(h >>> 0).toString(16)}:${tail}`;
}

/**
 * Attempts an authenticated request against Freepik, rotating through the
 * provided API keys when one fails with auth/rate-limit/server errors.
 */
export async function callFreepik<T = unknown>(opts: {
  method: "GET" | "POST";
  path: string;
  body?: unknown;
  apiKeys: string[];
  preferredIndex?: number;
}): Promise<FreepikCallResult<T>> {
  const { method, path, body, apiKeys } = opts;
  if (!apiKeys.length) {
    return { ok: false, status: 0, errorMessage: "no_api_keys_configured" };
  }

  // If a preferredIndex is provided, try that key first; otherwise try them in order.
  const order: number[] = [];
  if (typeof opts.preferredIndex === "number" && opts.preferredIndex >= 0 && opts.preferredIndex < apiKeys.length) {
    order.push(opts.preferredIndex);
  }
  for (let i = 0; i < apiKeys.length; i++) {
    if (!order.includes(i)) order.push(i);
  }

  let lastError = "all_keys_failed";
  let lastStatus = 0;

  for (const idx of order) {
    const key = apiKeys[idx];
    if (!key) continue;
    try {
      const res = await fetch(`${FREEPIK_BASE}${path}`, {
        method,
        headers: {
          "x-freepik-api-key": key,
          Accept: "application/json",
          ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
        },
        body: method === "POST" && body !== undefined ? JSON.stringify(body) : undefined,
        // Allow long polling timeouts; Next.js runtime handles it.
        cache: "no-store",
      });
      lastStatus = res.status;

      // 401/403: auth -> try next key
      // 429: rate limit -> try next key
      // 5xx: try next key
      if (res.status === 401 || res.status === 403 || res.status === 429 || res.status >= 500) {
        try {
          const errBody = await res.text();
          lastError = `key_${idx + 1}_failed:${res.status}:${errBody.slice(0, 200)}`;
        } catch {
          lastError = `key_${idx + 1}_failed:${res.status}`;
        }
        continue;
      }

      // Anything else: return as-is (success or 4xx user error that won't be fixed by rotation)
      let parsed: T | undefined;
      try {
        parsed = (await res.json()) as T;
      } catch {
        parsed = undefined;
      }
      return {
        ok: res.ok,
        status: res.status,
        data: parsed,
        errorMessage: res.ok ? undefined : `freepik_${res.status}`,
        apiKeyIndex: idx,
        apiKeyFingerprint: fingerprintKey(key),
      };
    } catch (err) {
      lastError = `network_error:${(err as Error).message}`;
      continue;
    }
  }

  return {
    ok: false,
    status: lastStatus || 0,
    errorMessage: lastError,
  };
}

export function buildPostBody(
  model: ModelDescriptor,
  payload: {
    prompt?: string;
    negativePrompt?: string;
    aspectRatio?: string;
    resolution?: string;
    duration?: number | string;
    startImageUrl?: string;
    endImageUrl?: string;
    referenceVideoUrl?: string;
    seed?: number;
    generateAudio?: boolean;
  },
): Record<string, unknown> {
  const body: Record<string, unknown> = {};

  // Text-to-image
  if (model.id === "nano-banana-pro") {
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.aspectRatio) body.aspect_ratio = payload.aspectRatio;
    if (payload.resolution) body.resolution = payload.resolution;
    return body;
  }

  if (model.id === "seedream-v4-5") {
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.aspectRatio) body.aspect_ratio = payload.aspectRatio;
    if (payload.resolution) body.resolution = payload.resolution.toLowerCase();
    return body;
  }

  // Text-to-video Veo 3.1
  if (model.id === "veo-3-1") {
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.negativePrompt) body.negative_prompt = payload.negativePrompt;
    if (payload.duration !== undefined) body.duration = Number(payload.duration);
    if (payload.resolution) body.resolution = payload.resolution;
    if (payload.aspectRatio) body.aspect_ratio = payload.aspectRatio;
    if (payload.generateAudio !== undefined) body.generate_audio = payload.generateAudio;
    if (payload.seed !== undefined) body.seed = payload.seed;
    return body;
  }

  // Kling 3 Pro (T2V or I2V via same endpoint)
  if (model.id === "kling-v3-pro-t2v" || model.id === "kling-v3-pro-i2v") {
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.negativePrompt) body.negative_prompt = payload.negativePrompt;
    if (payload.aspectRatio) body.aspect_ratio = payload.aspectRatio;
    if (payload.duration !== undefined) body.duration = Number(payload.duration);
    if (payload.startImageUrl) body.start_image_url = payload.startImageUrl;
    if (payload.endImageUrl) body.end_image_url = payload.endImageUrl;
    if (payload.generateAudio !== undefined) body.generate_audio = payload.generateAudio;
    return body;
  }

  // Kling 2.6 Pro I2V
  if (model.id === "kling-v2-6-pro-i2v") {
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.negativePrompt) body.negative_prompt = payload.negativePrompt;
    if (payload.duration !== undefined) body.duration = String(payload.duration);
    if (payload.startImageUrl) body.image_url = payload.startImageUrl;
    if (payload.endImageUrl) body.image_tail_url = payload.endImageUrl;
    return body;
  }

  // Seedance Pro 720p / 1080p — image-to-video
  if (model.id === "seedance-pro-720p" || model.id === "seedance-pro-1080p") {
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.startImageUrl) body.image = payload.startImageUrl;
    if (payload.duration !== undefined) body.duration = String(payload.duration);
    if (payload.aspectRatio) body.aspect_ratio = payload.aspectRatio;
    if (payload.seed !== undefined) body.seed = payload.seed;
    return body;
  }

  // Motion control - Kling 2.6 std/pro
  // Endpoint requires `image_url` (character) and `video_url` (motion source).
  if (model.id === "kling-v2-6-motion-control-pro" || model.id === "kling-v2-6-motion-control-std") {
    if (payload.startImageUrl) body.image_url = payload.startImageUrl;
    if (payload.referenceVideoUrl) body.video_url = payload.referenceVideoUrl;
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.negativePrompt) body.negative_prompt = payload.negativePrompt;
    return body;
  }

  // Kling 3 Omni Pro reference-to-video for motion/style transfer.
  // Endpoint requires `video_url` and accepts optional `image_url` start frame.
  if (model.id === "kling-v3-omni-pro") {
    if (payload.referenceVideoUrl) body.video_url = payload.referenceVideoUrl;
    if (payload.startImageUrl) body.image_url = payload.startImageUrl;
    if (payload.prompt) body.prompt = payload.prompt;
    if (payload.negativePrompt) body.negative_prompt = payload.negativePrompt;
    if (payload.duration !== undefined) body.duration = Number(payload.duration);
    if (payload.aspectRatio) body.aspect_ratio = payload.aspectRatio;
    return body;
  }

  return body;
}

/**
 * Pulls the result urls out of a Freepik task response. Different model
 * responses can use different keys (`generated`, `output_url`, etc.).
 */
export function extractResultUrls(taskData: unknown): string[] {
  if (!taskData || typeof taskData !== "object") return [];
  const t = taskData as Record<string, unknown>;
  const candidates: string[] = [];
  const push = (v: unknown) => {
    if (typeof v === "string" && v.startsWith("http")) candidates.push(v);
    if (Array.isArray(v)) v.forEach(push);
    if (v && typeof v === "object") {
      Object.values(v as Record<string, unknown>).forEach(push);
    }
  };
  push(t.generated);
  push(t.output_url);
  push(t.video_url);
  push(t.images);
  push(t.results);
  // Deduplicate while preserving order.
  return Array.from(new Set(candidates));
}
