"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ApiKeysModal } from "@/components/ApiKeysModal";
import { ModelSelector } from "@/components/ModelSelector";
import { PromptPanel, type PromptValues } from "@/components/PromptPanel";
import { Gallery } from "@/components/Gallery";
import { MODELS, getModel, modelsForMode } from "@/lib/models";
import { loadApiKeys, saveApiKeys, loadGallery, saveGallery, uid } from "@/lib/storage";
import type { ApiKeyEntry, GalleryItem, Mode, ModelId, TaskStatus } from "@/lib/types";

const DEFAULT_VALUES: PromptValues = {
  prompt: "",
  negativePrompt: "",
  aspectRatio: "",
  resolution: "",
  duration: "",
  startImageUrl: "",
  endImageUrl: "",
  referenceVideoUrl: "",
  generateAudio: true,
};

function defaultModelFor(mode: Mode): ModelId {
  return modelsForMode(mode)[0].id;
}

export default function Page() {
  const [mode, setMode] = useState<Mode>("text-to-image");
  const [modelId, setModelId] = useState<ModelId>(defaultModelFor("text-to-image"));
  const [values, setValues] = useState<PromptValues>(DEFAULT_VALUES);
  const [keys, setKeys] = useState<ApiKeyEntry[]>([]);
  const [keysOpen, setKeysOpen] = useState(false);
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [busy, setBusy] = useState(false);
  // Guard so the save effects don't overwrite localStorage with the empty
  // initial state before the load effect has run (which is especially nasty
  // under React.StrictMode, where every effect fires twice on mount).
  const [hydrated, setHydrated] = useState(false);

  const galleryRef = useRef<GalleryItem[]>([]);
  galleryRef.current = gallery;

  // -------- hydrate from localStorage --------
  useEffect(() => {
    const k = loadApiKeys();
    setKeys(k);
    const g = loadGallery();
    setGallery(g);
    setHydrated(true);
    if (k.length === 0) setKeysOpen(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveApiKeys(keys);
  }, [keys, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    saveGallery(gallery);
  }, [gallery, hydrated]);

  // When mode changes, reset to first model in that mode and clear ephemeral fields.
  useEffect(() => {
    const first = defaultModelFor(mode);
    setModelId(first);
  }, [mode]);

  const currentModel = useMemo(() => getModel(modelId), [modelId]);

  // Resync sensible defaults when model changes (only if empty).
  useEffect(() => {
    const m = getModel(modelId);
    if (!m) return;
    setValues((v) => ({
      ...v,
      aspectRatio: m.aspectRatioOptions?.[0] ?? "",
      resolution: m.resolutionOptions?.[0] ?? "",
      duration: m.durationOptions ? String(m.durationOptions[0]) : "",
    }));
  }, [modelId]);

  const enabledKeys = useMemo(() => keys.filter((k) => k.enabled).map((k) => k.value), [keys]);

  // -------- generation flow --------
  const updateItem = useCallback((id: string, patch: Partial<GalleryItem>) => {
    setGallery((g) => g.map((it) => (it.id === id ? { ...it, ...patch, updatedAt: Date.now() } : it)));
  }, []);

  const pollItem = useCallback(
    async (itemId: string) => {
      const POLL_INTERVAL = 4000;
      // Poll until Freepik itself reports COMPLETED or FAILED, the user deletes
      // the card, or the user clicks Stop (which sets status to FAILED). There
      // is no client-side timeout — generation lifetime depends only on the
      // upstream task / API key.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const current = galleryRef.current.find((g) => g.id === itemId);
        if (!current) return; // deleted by user
        if (current.status === "COMPLETED" || current.status === "FAILED") return;

        try {
          const res = await fetch("/api/task", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              modelId: current.modelId,
              taskId: current.taskId,
              apiKeys: enabledKeys,
            }),
          });
          const json = await res.json();
          if (!res.ok || !json.ok) {
            // Transient error — keep polling.
            await wait(POLL_INTERVAL);
            continue;
          }
          const status = (json.status as TaskStatus) || "IN_PROGRESS";
          const urls: string[] = json.urls || [];
          if (status === "COMPLETED" && urls.length > 0) {
            updateItem(itemId, { status, resultUrls: urls });
            return;
          }
          if (status === "FAILED") {
            updateItem(itemId, { status, errorMessage: "Freepik reported FAILED" });
            return;
          }
          updateItem(itemId, { status });
        } catch {
          // network blip — keep polling.
        }
        await wait(POLL_INTERVAL);
      }
    },
    [enabledKeys, updateItem],
  );

  const onSubmit = useCallback(async () => {
    if (!currentModel) return;
    if (enabledKeys.length === 0) {
      setKeysOpen(true);
      return;
    }

    setBusy(true);
    const newId = uid("g_");
    const placeholder: GalleryItem = {
      id: newId,
      mode,
      modelId,
      prompt: values.prompt,
      negativePrompt: values.negativePrompt || undefined,
      aspectRatio: values.aspectRatio as GalleryItem["aspectRatio"],
      duration: values.duration || undefined,
      resolution: values.resolution || undefined,
      startImageUrl: values.startImageUrl || undefined,
      endImageUrl: values.endImageUrl || undefined,
      referenceVideoUrl: values.referenceVideoUrl || undefined,
      taskId: "",
      apiKeyFingerprint: "",
      status: "QUEUED",
      resultKind: currentModel.resultKind,
      resultUrls: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setGallery((g) => [placeholder, ...g]);

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modelId,
          apiKeys: enabledKeys,
          payload: {
            prompt: values.prompt || undefined,
            negativePrompt: values.negativePrompt || undefined,
            aspectRatio: values.aspectRatio || undefined,
            resolution: values.resolution || undefined,
            duration: values.duration || undefined,
            startImageUrl: values.startImageUrl || undefined,
            endImageUrl: values.endImageUrl || undefined,
            referenceVideoUrl: values.referenceVideoUrl || undefined,
            generateAudio: values.generateAudio,
          },
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        updateItem(newId, {
          status: "FAILED",
          errorMessage: json?.error || `HTTP ${res.status}`,
        });
        // Update which key failed (best-effort)
        return;
      }
      updateItem(newId, {
        taskId: json.taskId,
        status: (json.status as TaskStatus) || "CREATED",
        apiKeyFingerprint: json.apiKeyFingerprint || "",
      });
      pollItem(newId);
    } catch (err) {
      updateItem(newId, {
        status: "FAILED",
        errorMessage: (err as Error).message,
      });
    } finally {
      setBusy(false);
    }
  }, [currentModel, enabledKeys, mode, modelId, values, updateItem, pollItem]);

  // Resume polling for any pending items once we've hydrated from localStorage.
  const resumedRef = useRef(false);
  useEffect(() => {
    if (!hydrated || resumedRef.current) return;
    resumedRef.current = true;
    const pending = gallery.filter(
      (g) => (g.status === "CREATED" || g.status === "IN_PROGRESS") && g.taskId,
    );
    pending.forEach((p) => pollItem(p.id));
    // We intentionally only resume once, right after hydration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  // -------- gallery actions --------
  const onDelete = useCallback((id: string) => {
    setGallery((g) => g.filter((x) => x.id !== id));
  }, []);
  const onRetryPoll = useCallback(
    (id: string) => {
      pollItem(id);
    },
    [pollItem],
  );
  const onStop = useCallback(
    (id: string) => {
      updateItem(id, { status: "FAILED", errorMessage: "Stopped by user" });
    },
    [updateItem],
  );
  const onClearAll = useCallback(() => setGallery([]), []);

  const canSubmit = useMemo(() => {
    if (!currentModel) return false;
    if (enabledKeys.length === 0) return false;
    if (currentModel.mode !== "motion-control" && !values.prompt.trim()) return false;
    if (currentModel.supports.startImage && !values.startImageUrl.trim()) {
      // start image required for motion-control + image-to-video flows
      return false;
    }
    if (currentModel.supports.referenceVideo && !values.referenceVideoUrl.trim()) {
      return false;
    }
    return true;
  }, [currentModel, enabledKeys, values]);

  return (
    <div className="flex min-h-screen">
      <Sidebar
        mode={mode}
        onChange={setMode}
        onOpenSettings={() => setKeysOpen(true)}
        apiKeyCount={keys.filter((k) => k.enabled).length}
      />

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-[420px_1fr] min-h-screen">
        {/* Left workbench */}
        <section className="border-r border-bg-border bg-bg-subtle/40 p-5 flex flex-col gap-5 overflow-y-auto max-h-screen">
          <header>
            <h1 className="text-lg font-semibold tracking-tight">{titleFor(mode)}</h1>
            <p className="text-xs text-white/50 mt-1">{subtitleFor(mode)}</p>
          </header>

          <div>
            <div className="label">Model</div>
            <ModelSelector mode={mode} selected={modelId} onSelect={setModelId} />
          </div>

          <div className="border-t border-bg-border pt-5">
            <PromptPanel
              model={currentModel}
              values={values}
              onChange={setValues}
              onSubmit={onSubmit}
              busy={busy}
              canSubmit={canSubmit}
              apiKeyCount={enabledKeys.length}
            />
          </div>

          <footer className="mt-auto pt-3 border-t border-bg-border text-[11px] text-white/30 leading-relaxed">
            {MODELS.length} models available · powered by Freepik API · BYOK with auto-failover
          </footer>
        </section>

        {/* Right gallery */}
        <section className="p-5 overflow-y-auto max-h-screen">
          <Gallery
            items={gallery}
            onDelete={onDelete}
            onRetryPoll={onRetryPoll}
            onStop={onStop}
            onClearAll={onClearAll}
          />
        </section>
      </main>

      <ApiKeysModal open={keysOpen} onClose={() => setKeysOpen(false)} keys={keys} onChange={setKeys} />
    </div>
  );
}

function wait(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

function titleFor(mode: Mode): string {
  switch (mode) {
    case "text-to-image":
      return "Text → Image";
    case "text-to-video":
      return "Text → Video";
    case "image-to-video":
      return "Image → Video";
    case "motion-control":
      return "Motion Control";
  }
}

function subtitleFor(mode: Mode): string {
  switch (mode) {
    case "text-to-image":
      return "Generate stills with Nano Banana Pro or Seedream. Re-run as many times as you like — every result stays in the gallery.";
    case "text-to-video":
      return "Veo 3.1 and Kling 3 Pro generate video from prompts. Async tasks; the gallery updates automatically when done.";
    case "image-to-video":
      return "Animate a still with Kling or Seedance. Provide a publicly reachable image URL.";
    case "motion-control":
      return "Transfer motion from a reference video onto a character image with Kling 2.6 or Kling 3 Omni Pro.";
  }
}
