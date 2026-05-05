"use client";

import type { ApiKeyEntry, GalleryItem } from "./types";

const KEYS_STORAGE = "freepik_studio.api_keys.v1";
const GALLERY_STORAGE = "freepik_studio.gallery.v1";

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function loadApiKeys(): ApiKeyEntry[] {
  if (typeof window === "undefined") return [];
  return safeParse<ApiKeyEntry[]>(localStorage.getItem(KEYS_STORAGE), []);
}

export function saveApiKeys(keys: ApiKeyEntry[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEYS_STORAGE, JSON.stringify(keys));
}

export function loadGallery(): GalleryItem[] {
  if (typeof window === "undefined") return [];
  return safeParse<GalleryItem[]>(localStorage.getItem(GALLERY_STORAGE), []);
}

export function saveGallery(items: GalleryItem[]): void {
  if (typeof window === "undefined") return;
  // Cap to ~500 most-recent items so localStorage doesn't blow up.
  const capped = items.slice(0, 500);
  localStorage.setItem(GALLERY_STORAGE, JSON.stringify(capped));
}

export function uid(prefix = ""): string {
  const t = Date.now().toString(36);
  const r = Math.random().toString(36).slice(2, 10);
  return `${prefix}${t}_${r}`;
}
