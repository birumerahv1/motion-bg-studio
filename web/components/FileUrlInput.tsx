"use client";

import clsx from "clsx";
import { Upload, X, FileImage, FileVideo, Link2, AlertTriangle } from "lucide-react";
import { useRef, useState } from "react";

export type FileKind = "image" | "video";

const ACCEPT: Record<FileKind, string> = {
  image: "image/png,image/jpeg,image/jpg,image/webp",
  video: "video/mp4,video/webm,video/quicktime,video/x-m4v",
};

// Conservative client-side caps. Freepik documents <= 10MB for images. Videos
// have to fit inside the JSON body sent to /api/generate (Next.js route
// handler has its own internal cap), so we bound them too.
const MAX_BYTES: Record<FileKind, number> = {
  image: 10 * 1024 * 1024,
  video: 15 * 1024 * 1024,
};

function bytesToHuman(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

export interface FileUrlInputProps {
  kind: FileKind;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  disabled?: boolean;
  /**
   * If true, surface a yellow warning explaining that Freepik may reject
   * base64-encoded payloads for this field (specifically motion-control
   * `video_url`, which the docs say must be a publicly reachable URL).
   */
  warnBase64?: boolean;
}

export function FileUrlInput({
  kind,
  value,
  onChange,
  placeholder,
  disabled,
  warnBase64,
}: FileUrlInputProps) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [meta, setMeta] = useState<{ name: string; size: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isDataUrl = value.startsWith("data:");

  function pick() {
    setError(null);
    fileRef.current?.click();
  }

  function clear() {
    setError(null);
    setMeta(null);
    onChange("");
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setError(null);

    if (f.size > MAX_BYTES[kind]) {
      setError(
        `File terlalu besar (${bytesToHuman(f.size)}). Maksimum ${bytesToHuman(
          MAX_BYTES[kind],
        )} untuk ${kind === "image" ? "gambar" : "video"}.`,
      );
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("read_failed"));
        reader.readAsDataURL(f);
      });
      onChange(dataUrl);
      setMeta({ name: f.name, size: f.size });
    } catch (err) {
      setError(`Gagal membaca file: ${(err as Error).message}`);
    }
  }

  // Display version of the value in the URL field. Data URLs are huge so we
  // collapse them to a placeholder; the user keeps the textbox-as-source for
  // pasting normal https URLs.
  const visibleValue = isDataUrl ? "" : value;
  const Icon = kind === "image" ? FileImage : FileVideo;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-stretch gap-2">
        <input
          className={clsx("input flex-1", isDataUrl && "opacity-60")}
          placeholder={
            isDataUrl
              ? "Local file uploaded — clear to type a URL"
              : placeholder ||
                (kind === "image"
                  ? "https://… (publicly reachable image URL)"
                  : "https://… (publicly reachable video URL)")
          }
          value={visibleValue}
          onChange={(e) => {
            setMeta(null);
            onChange(e.target.value);
          }}
          disabled={disabled || isDataUrl}
          spellCheck={false}
        />
        <button
          type="button"
          className="btn-secondary !px-3 shrink-0"
          onClick={pick}
          disabled={disabled}
          title={kind === "image" ? "Upload local image" : "Upload local video"}
        >
          <Upload size={14} /> Upload
        </button>
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT[kind]}
          className="hidden"
          onChange={onFile}
        />
      </div>

      {isDataUrl && meta && (
        <div className="flex items-center justify-between gap-2 rounded-md border border-bg-border bg-bg-subtle px-2.5 py-1.5 text-[11px] text-white/70">
          <span className="flex items-center gap-1.5 truncate">
            <Icon size={13} className="text-brand-300 shrink-0" />
            <span className="truncate" title={meta.name}>
              {meta.name}
            </span>
            <span className="text-white/40">· {bytesToHuman(meta.size)}</span>
          </span>
          <button
            type="button"
            className="text-white/40 hover:text-red-300 transition-colors shrink-0"
            onClick={clear}
            title="Remove file"
          >
            <X size={13} />
          </button>
        </div>
      )}

      {!isDataUrl && value && (
        <div className="flex items-center gap-1.5 text-[11px] text-white/40">
          <Link2 size={11} />
          Using URL
        </div>
      )}

      {error && (
        <div className="flex items-start gap-1.5 text-[11px] text-red-300">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {warnBase64 && isDataUrl && (
        <div className="flex items-start gap-1.5 text-[11px] text-amber-300/90 leading-relaxed">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          <span>
            Freepik mungkin menolak file lokal di sini (endpoint butuh URL publik).
            Jika gagal, upload video ke layanan public hosting dan tempel URL-nya.
          </span>
        </div>
      )}
    </div>
  );
}
