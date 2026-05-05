"use client";

import clsx from "clsx";
import { modelsForMode } from "@/lib/models";
import type { Mode, ModelId } from "@/lib/types";

export function ModelSelector({
  mode,
  selected,
  onSelect,
}: {
  mode: Mode;
  selected: ModelId;
  onSelect: (id: ModelId) => void;
}) {
  const list = modelsForMode(mode);
  return (
    <div className="grid grid-cols-1 gap-2">
      {list.map((m) => {
        const active = m.id === selected;
        return (
          <button
            key={m.id}
            onClick={() => onSelect(m.id)}
            className={clsx(
              "text-left rounded-lg border p-3 transition-colors",
              active
                ? "border-brand-500/60 bg-brand-500/10 shadow-soft"
                : "border-bg-border bg-bg-raised/60 hover:bg-bg-raised",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold">{m.label}</div>
                <div className="text-[11px] text-white/40">{m.vendor}</div>
              </div>
              {active && <span className="pill bg-brand-500/20 text-brand-200">selected</span>}
            </div>
            <p className="text-xs text-white/55 mt-1.5 leading-snug">{m.description}</p>
          </button>
        );
      })}
    </div>
  );
}
