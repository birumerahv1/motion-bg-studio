"use client";

import clsx from "clsx";
import { Sparkles, Wand2 } from "lucide-react";
import type { ModelDescriptor } from "@/lib/models";

export interface PromptValues {
  prompt: string;
  negativePrompt: string;
  aspectRatio: string;
  resolution: string;
  duration: string;
  startImageUrl: string;
  endImageUrl: string;
  referenceVideoUrl: string;
  generateAudio: boolean;
}

export function PromptPanel({
  model,
  values,
  onChange,
  onSubmit,
  busy,
  canSubmit,
  apiKeyCount,
}: {
  model: ModelDescriptor | undefined;
  values: PromptValues;
  onChange: (next: PromptValues) => void;
  onSubmit: () => void;
  busy: boolean;
  canSubmit: boolean;
  apiKeyCount: number;
}) {
  function set<K extends keyof PromptValues>(k: K, v: PromptValues[K]) {
    onChange({ ...values, [k]: v });
  }

  if (!model) return null;

  const showPrompt = model.mode !== "motion-control" || model.id === "kling-v3-omni-pro";
  const promptRequired = model.mode !== "motion-control";

  return (
    <div className="flex flex-col gap-4">
      {showPrompt && (
        <div>
          <label className="label flex items-center justify-between">
            <span>Prompt {promptRequired && <span className="text-red-400">*</span>}</span>
            <span className="text-[10px] text-white/30 normal-case tracking-normal">
              {values.prompt.length} chars
            </span>
          </label>
          <textarea
            className="textarea"
            placeholder={
              model.mode === "text-to-image"
                ? "A cinematic photo of a misty Tokyo street at dusk, neon reflections on wet pavement, 35mm film, ultra-detailed"
                : model.mode === "motion-control"
                ? "Optional descriptive context for the motion transfer (style, lighting, etc.)"
                : "A serene mountain landscape at sunset with clouds moving slowly, gentle camera push-in"
            }
            value={values.prompt}
            onChange={(e) => set("prompt", e.target.value)}
          />
        </div>
      )}

      {model.supports.negativePrompt && (
        <div>
          <label className="label">Negative prompt</label>
          <input
            className="input"
            placeholder="blurry, low quality, distorted, watermark"
            value={values.negativePrompt}
            onChange={(e) => set("negativePrompt", e.target.value)}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {model.supports.aspectRatio && model.aspectRatioOptions && (
          <div>
            <label className="label">Aspect ratio</label>
            <select
              className="select"
              value={values.aspectRatio || model.aspectRatioOptions[0]}
              onChange={(e) => set("aspectRatio", e.target.value)}
            >
              {model.aspectRatioOptions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        )}

        {model.supports.resolution && model.resolutionOptions && (
          <div>
            <label className="label">Resolution</label>
            <select
              className="select"
              value={values.resolution || model.resolutionOptions[0]}
              onChange={(e) => set("resolution", e.target.value)}
            >
              {model.resolutionOptions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
        )}

        {model.supports.duration && model.durationOptions && (
          <div>
            <label className="label">Duration</label>
            <select
              className="select"
              value={values.duration || String(model.durationOptions[0])}
              onChange={(e) => set("duration", e.target.value)}
            >
              {model.durationOptions.map((d) => (
                <option key={String(d)} value={String(d)}>
                  {d}s
                </option>
              ))}
            </select>
          </div>
        )}

        {model.supports.audio && (
          <label className="flex items-end gap-2 pb-2 cursor-pointer select-none">
            <input
              type="checkbox"
              className="accent-brand-500"
              checked={values.generateAudio}
              onChange={(e) => set("generateAudio", e.target.checked)}
            />
            <span className="text-sm text-white/80">Generate native audio</span>
          </label>
        )}
      </div>

      {model.supports.startImage && (
        <div>
          <label className="label">
            {model.mode === "motion-control" ? "Character image URL" : "Start frame image URL"}{" "}
            <span className="text-red-400">*</span>
          </label>
          <input
            className="input"
            placeholder="https://… (publicly reachable image URL)"
            value={values.startImageUrl}
            onChange={(e) => set("startImageUrl", e.target.value)}
          />
        </div>
      )}

      {model.supports.endImage && (
        <div>
          <label className="label">End frame image URL (optional)</label>
          <input
            className="input"
            placeholder="https://…"
            value={values.endImageUrl}
            onChange={(e) => set("endImageUrl", e.target.value)}
          />
        </div>
      )}

      {model.supports.referenceVideo && (
        <div>
          <label className="label">
            Reference motion video URL <span className="text-red-400">*</span>
          </label>
          <input
            className="input"
            placeholder="https://… (mp4/webm publicly reachable URL)"
            value={values.referenceVideoUrl}
            onChange={(e) => set("referenceVideoUrl", e.target.value)}
          />
        </div>
      )}

      <div className="pt-2 flex flex-col gap-2">
        <button
          className={clsx(
            "btn-primary w-full !py-3 text-base",
            busy && "animate-pulse",
          )}
          onClick={onSubmit}
          disabled={!canSubmit || busy}
        >
          {busy ? (
            <>
              <Sparkles size={16} className="animate-spin" /> Generating…
            </>
          ) : (
            <>
              <Wand2 size={16} /> Generate
            </>
          )}
        </button>
        {apiKeyCount === 0 && (
          <p className="text-xs text-amber-300/80 text-center">
            Add a Freepik API key in Settings before generating.
          </p>
        )}
        {apiKeyCount > 0 && (
          <p className="text-[11px] text-white/40 text-center">
            Using {apiKeyCount} key{apiKeyCount === 1 ? "" : "s"} with auto-failover.
            Re-running with a new prompt keeps previous results in the gallery.
          </p>
        )}
      </div>
    </div>
  );
}
