"use client";

import { useEffect, useRef, useState } from "react";
import { Eye, EyeOff, Plus, Trash2, X, Check } from "lucide-react";
import clsx from "clsx";
import type { ApiKeyEntry } from "@/lib/types";
import { uid } from "@/lib/storage";

export function ApiKeysModal({
  open,
  onClose,
  keys,
  onChange,
}: {
  open: boolean;
  onClose: () => void;
  keys: ApiKeyEntry[];
  onChange: (next: ApiKeyEntry[]) => void;
}) {
  const [draft, setDraft] = useState({ label: "", value: "" });
  const [reveal, setReveal] = useState<Record<string, boolean>>({});
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  if (!open) return null;

  function addKey() {
    const value = draft.value.trim();
    if (!value) return;
    const entry: ApiKeyEntry = {
      id: uid("k_"),
      label: draft.label.trim() || `Key #${keys.length + 1}`,
      value,
      enabled: true,
    };
    onChange([...keys, entry]);
    setDraft({ label: "", value: "" });
  }

  function removeKey(id: string) {
    onChange(keys.filter((k) => k.id !== id));
  }

  function toggleEnabled(id: string) {
    onChange(keys.map((k) => (k.id === id ? { ...k, enabled: !k.enabled } : k)));
  }

  function masked(v: string) {
    if (v.length <= 8) return "•".repeat(v.length);
    return `${v.slice(0, 4)}${"•".repeat(Math.max(0, v.length - 8))}${v.slice(-4)}`;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="panel w-full max-w-2xl shadow-soft"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between p-5 border-b border-bg-border">
          <div>
            <h2 className="text-lg font-semibold">Freepik API Keys</h2>
            <p className="text-sm text-white/50 mt-1">
              Add one or more keys. Studio will auto-rotate to the next key if a request fails with
              auth, rate-limit, or server errors.
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost !p-1.5">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr_auto] gap-3 items-end">
            <div>
              <label className="label">Label (optional)</label>
              <input
                className="input"
                placeholder="Personal · Production · Backup"
                value={draft.label}
                onChange={(e) => setDraft((d) => ({ ...d, label: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">API Key</label>
              <input
                ref={inputRef}
                className="input font-mono"
                placeholder="FPSXXXXXXXXXXXXXXXXXXXXXXXX"
                value={draft.value}
                onChange={(e) => setDraft((d) => ({ ...d, value: e.target.value }))}
                onKeyDown={(e) => e.key === "Enter" && addKey()}
              />
            </div>
            <button className="btn-primary" onClick={addKey} disabled={!draft.value.trim()}>
              <Plus size={16} /> Add key
            </button>
          </div>

          <div>
            <div className="text-xs uppercase tracking-wide text-white/40 mb-2">
              Configured keys ({keys.length})
            </div>
            {keys.length === 0 ? (
              <div className="rounded-lg border border-dashed border-bg-border bg-bg-subtle/60 p-6 text-center text-sm text-white/50">
                No API keys yet. Get one from{" "}
                <a
                  className="text-brand-300 underline underline-offset-2"
                  href="https://www.freepik.com/api"
                  target="_blank"
                  rel="noreferrer"
                >
                  freepik.com/api
                </a>
                .
              </div>
            ) : (
              <ul className="space-y-2">
                {keys.map((k, idx) => {
                  const isRevealed = reveal[k.id];
                  return (
                    <li
                      key={k.id}
                      className={clsx(
                        "flex items-center gap-3 rounded-lg border p-3",
                        k.enabled ? "border-bg-border bg-bg-raised" : "border-bg-border bg-bg-subtle/60 opacity-60",
                      )}
                    >
                      <div className="shrink-0 w-7 h-7 rounded-md bg-brand-500/20 text-brand-200 text-xs font-semibold flex items-center justify-center">
                        {idx + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <div className="text-sm font-medium truncate">{k.label}</div>
                          {k.enabled ? (
                            <span className="pill bg-emerald-500/15 text-emerald-300">
                              <Check size={11} /> active
                            </span>
                          ) : (
                            <span className="pill bg-white/5 text-white/40">disabled</span>
                          )}
                          {k.lastError && (
                            <span className="pill bg-amber-500/15 text-amber-300" title={k.lastError}>
                              recent error
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-white/50 font-mono mt-1 truncate">
                          {isRevealed ? k.value : masked(k.value)}
                        </div>
                      </div>
                      <button
                        className="btn-ghost !p-2"
                        onClick={() =>
                          setReveal((r) => ({ ...r, [k.id]: !r[k.id] }))
                        }
                        title={isRevealed ? "Hide" : "Reveal"}
                      >
                        {isRevealed ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                      <label className="inline-flex items-center gap-2 text-xs text-white/60 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          className="accent-brand-500"
                          checked={k.enabled}
                          onChange={() => toggleEnabled(k.id)}
                        />
                        enabled
                      </label>
                      <button
                        className="btn-ghost !p-2 text-red-400 hover:!bg-red-500/10"
                        onClick={() => removeKey(k.id)}
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="rounded-lg border border-bg-border bg-bg-subtle/60 p-4 text-xs text-white/50 leading-relaxed">
            Keys live only in your browser&apos;s localStorage. They are sent to this app&apos;s
            server-side proxy on each request and forwarded to{" "}
            <span className="font-mono text-white/70">api.freepik.com</span>. Nothing is logged or
            stored remotely.
          </div>
        </div>

        <div className="px-5 py-4 border-t border-bg-border flex items-center justify-end">
          <button className="btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
