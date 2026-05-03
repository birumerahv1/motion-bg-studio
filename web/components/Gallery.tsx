"use client";

import { Download, Trash2, RefreshCcw, ImageOff, FilmIcon, Clock, AlertTriangle, Loader2 } from "lucide-react";
import clsx from "clsx";
import type { GalleryItem } from "@/lib/types";
import { getModel } from "@/lib/models";

function statusPill(item: GalleryItem) {
  const s = item.status;
  if (s === "COMPLETED") return <span className="pill bg-emerald-500/15 text-emerald-300">completed</span>;
  if (s === "FAILED") return <span className="pill bg-red-500/15 text-red-300"><AlertTriangle size={11} /> failed</span>;
  if (s === "QUEUED") return <span className="pill bg-white/5 text-white/60"><Clock size={11} /> queued</span>;
  return <span className="pill bg-amber-500/15 text-amber-300"><Loader2 size={11} className="animate-spin" /> generating</span>;
}

function fileExt(url: string, kind: "image" | "video"): string {
  try {
    const u = new URL(url);
    const m = u.pathname.match(/\.([a-z0-9]{2,5})(?:$|\?)/i);
    if (m) return m[1].toLowerCase();
  } catch {
    // ignore
  }
  return kind === "video" ? "mp4" : "png";
}

function downloadHref(url: string, item: GalleryItem, idx: number): string {
  const ext = fileExt(url, item.resultKind);
  const safe = (item.prompt || item.modelId).slice(0, 40).replace(/[^a-zA-Z0-9]+/g, "_");
  const name = `${item.modelId}_${safe}_${idx + 1}.${ext}`;
  return `/api/proxy?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(name)}`;
}

export function Gallery({
  items,
  onDelete,
  onRetryPoll,
  onClearAll,
}: {
  items: GalleryItem[];
  onDelete: (id: string) => void;
  onRetryPoll: (id: string) => void;
  onClearAll: () => void;
}) {
  return (
    <div className="flex-1 flex flex-col">
      <div className="flex items-center justify-between px-1 pb-3">
        <div className="text-sm text-white/70">
          <span className="text-white font-semibold">Gallery</span>
          <span className="text-white/40"> · {items.length} item{items.length === 1 ? "" : "s"}</span>
          <span className="text-white/30 ml-2 text-xs">history persists across generations</span>
        </div>
        {items.length > 0 && (
          <button
            className="btn-ghost text-xs text-white/50 hover:text-red-300"
            onClick={() => {
              if (confirm(`Clear all ${items.length} items from the gallery? This cannot be undone.`)) {
                onClearAll();
              }
            }}
          >
            <Trash2 size={14} /> Clear all
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="panel flex-1 flex flex-col items-center justify-center text-center p-10 text-white/40">
          <ImageOff size={28} className="mb-3" />
          <div className="text-sm">No generations yet.</div>
          <div className="text-xs mt-1">Pick a model and click Generate to begin.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4 pb-8">
          {items.map((item) => (
            <GalleryCard
              key={item.id}
              item={item}
              onDelete={onDelete}
              onRetryPoll={onRetryPoll}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function GalleryCard({
  item,
  onDelete,
  onRetryPoll,
}: {
  item: GalleryItem;
  onDelete: (id: string) => void;
  onRetryPoll: (id: string) => void;
}) {
  const model = getModel(item.modelId);
  const isPending = item.status === "CREATED" || item.status === "IN_PROGRESS" || item.status === "QUEUED";
  const isImg = item.resultKind === "image";

  return (
    <div className={clsx("panel overflow-hidden flex flex-col", isPending && "opacity-95")}>
      <div className="relative aspect-[4/5] bg-bg-subtle flex items-center justify-center overflow-hidden">
        {item.resultUrls[0] ? (
          isImg ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={item.resultUrls[0]}
              alt={item.prompt}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          ) : (
            <video
              src={item.resultUrls[0]}
              className="w-full h-full object-cover"
              controls
              playsInline
              preload="metadata"
            />
          )
        ) : (
          <div className="flex flex-col items-center justify-center text-white/40 text-xs gap-2 p-6 text-center">
            {item.status === "FAILED" ? (
              <>
                <AlertTriangle size={22} className="text-red-300" />
                <div className="text-red-300 text-xs font-medium">Generation failed</div>
                <div className="text-[11px] text-white/50 break-all">{item.errorMessage || "unknown error"}</div>
              </>
            ) : (
              <>
                <Loader2 size={22} className="animate-spin text-brand-300" />
                <div>Working with Freepik…</div>
                <div className="text-[10px] text-white/30 font-mono">task {item.taskId.slice(0, 8)}</div>
              </>
            )}
          </div>
        )}
        <div className="absolute top-2 left-2 flex gap-1.5">
          {statusPill(item)}
          <span className="pill bg-black/40 text-white/70 backdrop-blur-sm">
            {isImg ? "image" : <span className="inline-flex items-center gap-1"><FilmIcon size={10} /> video</span>}
          </span>
        </div>
      </div>

      <div className="p-3 flex flex-col gap-2 flex-1">
        <div>
          <div className="text-xs font-semibold text-white/80 truncate" title={model?.label || item.modelId}>
            {model?.label || item.modelId}
          </div>
          <div className="text-[11px] text-white/40 truncate">
            {model?.vendor} · {fmtTime(item.createdAt)}
          </div>
        </div>
        <p className="text-xs text-white/60 line-clamp-3 leading-relaxed" title={item.prompt}>
          {item.prompt || <span className="italic text-white/30">(no prompt)</span>}
        </p>

        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-1">
            {isPending && (
              <button
                className="btn-ghost !p-1.5 text-white/60 hover:text-white"
                title="Refresh status"
                onClick={() => onRetryPoll(item.id)}
              >
                <RefreshCcw size={14} />
              </button>
            )}
            <button
              className="btn-ghost !p-1.5 text-white/50 hover:text-red-300"
              title="Delete from gallery"
              onClick={() => onDelete(item.id)}
            >
              <Trash2 size={14} />
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            {item.resultUrls.map((url, idx) => (
              <a
                key={url}
                href={downloadHref(url, item, idx)}
                download
                className="btn-secondary !py-1.5 !px-2.5 text-xs"
                title={`Download ${idx + 1}`}
              >
                <Download size={13} />
                {item.resultUrls.length > 1 ? `#${idx + 1}` : "Download"}
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function fmtTime(ts: number): string {
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch {
    return "";
  }
}
