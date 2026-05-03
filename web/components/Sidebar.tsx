"use client";

import { ImageIcon, Film, Wand2, Video, KeyRound } from "lucide-react";
import clsx from "clsx";
import type { Mode } from "@/lib/types";

const NAV: { id: Mode; label: string; icon: React.ReactNode; hint: string }[] = [
  {
    id: "text-to-image",
    label: "Text to Image",
    icon: <ImageIcon size={18} />,
    hint: "Nano Banana Pro, Seedream",
  },
  {
    id: "text-to-video",
    label: "Text to Video",
    icon: <Film size={18} />,
    hint: "Veo 3.1, Kling 3 Pro",
  },
  {
    id: "image-to-video",
    label: "Image to Video",
    icon: <Video size={18} />,
    hint: "Kling 3 Pro, Seedance",
  },
  {
    id: "motion-control",
    label: "Motion Control",
    icon: <Wand2 size={18} />,
    hint: "Kling 2.6 / Kling 3 Omni",
  },
];

export function Sidebar({
  mode,
  onChange,
  onOpenSettings,
  apiKeyCount,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
  onOpenSettings: () => void;
  apiKeyCount: number;
}) {
  return (
    <aside className="w-[260px] shrink-0 border-r border-bg-border bg-bg-subtle/60 backdrop-blur flex flex-col">
      <div className="px-5 pt-5 pb-4 border-b border-bg-border">
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-lg shadow-glow flex items-center justify-center text-white font-bold"
            style={{ background: "linear-gradient(135deg,#4a63ff,#a855f7)" }}
          >
            FS
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">Freepik AI Studio</div>
            <div className="text-[11px] text-white/40">Powered by Freepik API</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-3 flex flex-col gap-1">
        <div className="px-2 pt-1 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-white/30">
          Generate
        </div>
        {NAV.map((n) => {
          const active = mode === n.id;
          return (
            <button
              key={n.id}
              onClick={() => onChange(n.id)}
              className={clsx(
                "w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors group",
                active
                  ? "bg-brand-500/15 text-white border border-brand-500/30 shadow-soft"
                  : "text-white/70 hover:bg-white/5 hover:text-white border border-transparent",
              )}
            >
              <span
                className={clsx(
                  "shrink-0 w-7 h-7 rounded-md flex items-center justify-center",
                  active ? "bg-brand-500/30 text-brand-200" : "bg-bg-raised text-white/60 group-hover:text-white",
                )}
              >
                {n.icon}
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium leading-tight">{n.label}</span>
                <span className="block text-[11px] text-white/40 mt-0.5">{n.hint}</span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-4 pt-2 border-t border-bg-border">
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left bg-bg-raised hover:bg-bg-border transition-colors border border-bg-border"
        >
          <span className="shrink-0 w-7 h-7 rounded-md bg-bg-subtle text-white/70 flex items-center justify-center">
            <KeyRound size={16} />
          </span>
          <span className="flex-1">
            <span className="block text-sm font-medium">API Keys</span>
            <span className="block text-[11px] text-white/40">
              {apiKeyCount === 0
                ? "Add a key to start"
                : `${apiKeyCount} configured · auto-failover`}
            </span>
          </span>
        </button>
      </div>
    </aside>
  );
}
