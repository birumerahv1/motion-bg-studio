# Freepik AI Studio

A Leonardo-style web AI studio that wraps the [Freepik B2B API](https://docs.freepik.com).
Bring your own Freepik API key(s) and generate images, motion-control clips, and
text-to-video / image-to-video right from your browser.

![banner](https://img.shields.io/badge/Next.js-14-black) ![api](https://img.shields.io/badge/Freepik%20API-BYOK-2937d4)

## Features

- **Text → Image**: Nano Banana Pro (Gemini 3) and Seedream 4.5
- **Text → Video**: Veo 3.1 and Kling 3 Pro
- **Image → Video**: Kling 3 Pro, Kling 2.6 Pro, Seedance Pro 720p, Seedance Pro 1080p
- **Motion Control**: Kling 2.6 Pro, Kling 2.6 Standard, and Kling 3 Omni Pro
  (transfer motion from a reference video onto a character image)
- **Multiple API keys + auto-failover**: configure several Freepik keys; the
  server-side proxy retries the next key automatically on `401 / 403 / 429 / 5xx`
- **Persistent gallery**: every generation is appended to a local-only gallery
  (kept in `localStorage`) — generating with prompt B never wipes prompt A's
  result. Status updates live via async polling.
- **One-click download**: each generated image / video has its own download
  button (served through a same-origin proxy so CORS-locked storage still works)
- **Professional dark UI**: built with Tailwind, lucide-react icons, and a
  responsive 3-pane layout (sidebar / workbench / gallery)

## Getting started

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and add at least one
Freepik API key in **Settings**. Get a key from
<https://www.freepik.com/api>.

## Scripts

| Script              | What it does                          |
| ------------------- | ------------------------------------- |
| `npm run dev`       | Start the dev server on port 3000     |
| `npm run build`     | Production build                      |
| `npm run start`     | Run the production build              |
| `npm run lint`      | ESLint via `next lint`                |
| `npm run typecheck` | `tsc --noEmit` strict type-check      |

## Architecture

```
web/
├── app/
│   ├── page.tsx                  # Main 3-pane studio UI
│   ├── api/generate/route.ts     # POST → Freepik (with key rotation)
│   ├── api/task/route.ts         # POST poll → Freepik task status
│   └── api/proxy/route.ts        # GET stream proxy for downloads
├── components/                   # Sidebar, ModelSelector, PromptPanel, …
├── lib/
│   ├── freepik.ts                # Multi-key fetch with auto-failover
│   ├── models.ts                 # Model registry (id → endpoint, params)
│   ├── storage.ts                # localStorage helpers
│   └── types.ts                  # Shared TypeScript types
```

### How key rotation works

Every browser request includes the *enabled* set of API keys (in order). The
Next.js route handler tries them sequentially; on auth, rate-limit, or 5xx it
moves to the next key. The successful key's index is returned to the client and
stored alongside the `task_id` so subsequent polling reuses the same key.

### How the gallery persists

The gallery is stored under `freepik_studio.gallery.v1` in `localStorage`
(capped at the most-recent 500 entries). Each new generation prepends an item
to the list — previous results are never overwritten when you submit a new
prompt. Pending tasks are resumed on page reload.

## Notes on model names

The user-requested wording vs. what is currently live on Freepik:

| Requested        | Available now in Freepik                                        |
| ---------------- | --------------------------------------------------------------- |
| Seedream 5.0     | **Seedream 4.5** (latest GA Seedream tier on Freepik)           |
| Seedance 2.0     | **Seedance Pro 720p / 1080p** (current Seedance generation)     |
| Kling 3.0 motion | **Kling 3 Omni Pro** (reference-to-video motion/style transfer) |

When Freepik ships newer model versions, just update `lib/models.ts` —
no other change required.

## License

MIT (same as the parent repository).
