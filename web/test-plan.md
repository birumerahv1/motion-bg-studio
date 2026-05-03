# Freepik AI Studio – Test Plan (PR #3)

Run against the local dev server at `http://localhost:3000`, using the Freepik
API key the user provided.

## What changed (user-visible)

A brand-new Next.js studio under `web/` exposing four generation modes wired to
the Freepik API. The four user-visible promises that need proof:

1. Generate works end-to-end against the real Freepik API (Nano Banana Pro is the
   most reliable, fastest model — it's the right canary for the whole stack).
2. **History persists across generations**: re-running with prompt B does not
   wipe prompt A's result.
3. **Each result has its own working download button** that returns a real image
   file (not an HTML error page).
4. **Multi-key auto-failover**: a deliberately broken key in slot #1 followed by
   the real key in slot #2 still completes a generation.

## Primary end-to-end test (this is what the recording shows)

**Setup (off-camera, before recording):** dev server already running, browser
maximized, gallery cleared.

| #    | Action                                                                                              | Pass criterion (concrete)                                                                                                                                                                                                                                                                  |
| ---- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1.1 | Open Settings → Add the user's real Freepik API key with label "Real". Click **Done**.              | Settings list shows 1 active key with masked value `FPSX•••••••••••2325`.                                                                                                                                                                                                                  |
| T1.2 | On Text → Image with **Nano Banana Pro** selected, prompt = `"A cinematic photo of a misty Tokyo street at dusk, neon reflections on wet pavement, 35mm film, ultra-detailed"`. Click **Generate**. | Within 2 seconds a placeholder card appears in the Gallery with status `generating` (amber pill, spinner) and pill `image`. Within ~90 seconds it transitions to `completed` (emerald pill) and shows the rendered image.        |
| T1.3 | **Without clearing**, change prompt to `"A studio portrait of a corgi wearing aviator goggles, soft window light, 85mm"`. Click **Generate** again. | A *second* placeholder card prepends above the prompt-A card. The prompt-A card **must still be visible** with its image. Both cards eventually show two distinct images. |
| T1.4 | Click the **Download** button on the prompt-A card.                                                 | Browser downloads a file whose name starts with `nano-banana-pro_A_cinematic_photo_of_a_misty_Tokyo_street_` and whose size is > 50 KB. Opening the file in an image viewer shows a real image, not an error page.                                                                       |
| T1.5 | Click **Settings** again, toggle off the real key, and try to Generate.                             | Generate button is greyed out + amber hint "Add a Freepik API key in Settings before generating." appears under the button.                                                                                                                                                                  |
| T1.6 | Re-enable the real key, **add a junk key as slot #1** with value `FPS_INVALID_KEY_FAKE_FOR_FAILOVER` (label "Bad"), drag (or just leave) the real one as slot #2. Generate with prompt `"A neon cyberpunk alley with rain and steam, vertical 9:16"` and aspect ratio `9:16`. | Generation still completes (proves slot #2 took over). The new card appears with the bad key's failure absorbed silently — no FAILED card, history from T1.2 / T1.3 still present.                                            |

### Why these steps would fail if the change were broken

- T1.3 is the *adversarial* step: a naive implementation that does
  `setGallery([newItem])` instead of `setGallery((g) => [newItem, ...g])` would
  visibly drop the prompt-A card the moment Generate is clicked again. We watch
  for that drop on screen.
- T1.4 verifies the **download proxy** actually streams the upstream file. If
  the proxy were broken, the browser would either save an empty file or an HTML
  error page. We open the file to confirm.
- T1.6 verifies multi-key auto-failover. If rotation were broken, the card
  would land in `failed` because slot #1's invalid key would surface.

## T2: Stop button + no client-side timeout + hydration fix (this round's diff)

> Hydration bug found and fixed during testing: under React.StrictMode the save
> effect was overwriting `localStorage` with the empty initial state before the
> load effect populated it, so any persisted gallery would silently disappear on
> page reload. The fix gates both save effects on a `hydrated` flag set by the
> load effect.

The previous version had a 12-minute client-side timeout that would mark a pending
card as `FAILED` with the message "Polling timed out after 12 minutes." That has
been removed; the only ways out of pending are now:

1. Freepik returns `COMPLETED`
2. Freepik returns `FAILED`
3. The user clicks the new **Stop** icon on the pending card
4. The user deletes the card

We can't trigger (1)/(2) end-to-end with the user's key (free trial 429), and we
won't wait 12+ minutes. So we deterministically validate (3) by seeding a
pending card directly into `localStorage` from the devtools console, reloading,
and exercising the Stop button in the UI.

| #    | Action                                                                                                                                      | Pass criterion (concrete)                                                                                                                                                                            |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T2.1 | Open the app at http://localhost:3000. In devtools console, write a fake `IN_PROGRESS` gallery item to `freepik_studio.gallery.v1`, then reload. | A gallery card appears with the amber `generating` pill, a refresh icon, AND a square **Stop** icon. The Stop icon was NOT present before this PR change.                                            |
| T2.2 | Hover over the Stop icon.                                                                                                                   | Tooltip reads "Stop generation". Icon is amber-ish (Tailwind `text-amber-300/80`) — visually distinguishable from the red trash icon.                                                                |
| T2.3 | Click the Stop icon.                                                                                                                        | Within ~1 second the card transitions: amber `generating` pill → red `failed` pill, the inline error text shows `Stopped by user`, and the Stop + refresh icons disappear (replaced by trash only).   |
| T2.4 | Reload the page.                                                                                                                            | The card is still present and still shows status `failed` + error `Stopped by user` (proves the change was persisted to `localStorage`, not just in-memory).                                          |
| T2.5 | Inspect the source of `web/app/page.tsx` to confirm the `MAX_DURATION` constant and `Polling timed out after 12 minutes` string are gone.   | `grep -n "MAX_DURATION\|Polling timed out" web/app/page.tsx` returns no matches.                                                                                                                      |

### Why these steps would fail if the change were broken

- **T2.1**: if the Stop button were not wired, the card would only show refresh + trash and the user would have no way to abort, contradicting "rely only on the API key" intent.
- **T2.3**: if `onStop` were not implemented or not passed through Gallery, clicking the icon would do nothing visible — the card would stay amber.
- **T2.5**: catches a partial revert where the button was added but the timeout was not actually removed.

## T3: Local file upload for Image→Video and Motion Control (this round's diff)

> The user asked: "pada bagian image to video dan motion control bisa
> menambahka file dari lokal file" — they want to be able to attach a local
> file instead of typing a URL. The new `FileUrlInput` component adds an
> "Upload" button next to every URL field in those two modes; selected files
> are read in-browser as base64 data URLs and sent in the existing
> `image_url` / `video_url` payload field. Caps: 10 MB for images, 15 MB for
> videos. The motion-control reference-video field shows a yellow advisory
> when a data URL is selected, because Freepik's docs require a publicly
> reachable URL for `video_url`.

End-to-end Freepik calls remain blocked by the user's free-trial 429, so we
test the **client-side upload UX** which is everything the diff actually
changes, plus the adversarial size-cap path.

| #    | Action                                                                                                                                                                            | Pass criterion (concrete)                                                                                                                                                                                                                                                                                       |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T3.1 | Open the app, sidebar → **Image to Video**.                                                                                                                                       | The "Start frame image *" and "End frame image (optional)" fields each render a URL textbox **plus an "Upload" button** to its right. Before this PR the row was just a textbox.                                                                                                                                |
| T3.2 | Click **Upload** next to "Start frame image".                                                                                                                                     | A native file picker opens, filtered to `image/png,image/jpeg,image/jpg,image/webp` (no other file types selectable).                                                                                                                                                                                          |
| T3.3 | Pick a small valid PNG (`/tmp/upload-test/test-image.png`, 75 bytes — pre-staged off-camera).                                                                                     | The textbox text disappears and is replaced with placeholder "Local file uploaded — clear to type a URL". Below the row, a chip appears with a `FileImage` icon, the filename `test-image.png`, and the size `75 B`. An `X` clear button is visible on the right of the chip.                                  |
| T3.4 | In the page state (read via devtools console: `JSON.parse(localStorage.getItem('freepik_studio.gallery.v1') || '[]')` is fine — we want the *form value*, so just observe), click the X clear button on the chip. | The chip and placeholder disappear. The textbox becomes editable again and is empty.                                                                                                                                                                                                                            |
| T3.5 | Sidebar → **Motion Control**.                                                                                                                                                     | The "Character image *" field has an Upload button. The "Reference motion video *" field also has an Upload button. The motion-control character-image label was previously "Character image URL" — now it's "Character image" (URL is implicit, not the only option).                                          |
| T3.6 | Click Upload next to "Reference motion video", pick a small mp4 (a 60 KB sample staged off-camera at `/tmp/upload-test/sample.mp4`).                                              | Chip with `FileVideo` icon and the filename appears. Directly below the chip a **yellow `AlertTriangle` advisory** appears with text including the words "Freepik" and "URL publik" — this is the `warnBase64` advisory that only renders when the value is a data URL on the motion-control reference-video field. |
| T3.7 | **Adversarial size-cap test.** Click Upload next to "Character image" in motion-control and pick a >10 MB image (`/tmp/upload-test/oversized.png`, ~12 MB, staged off-camera).    | The file is **rejected**: chip does NOT appear, textbox stays empty, and a red `AlertTriangle` row appears with text starting with `File terlalu besar (`, including the actual size in MB and the cap "10.0 MB". Compare to T3.3 where a 75 B image *was* accepted — this proves the validator is real, not noop. |
| T3.8 | Inspect `web/components/FileUrlInput.tsx` to confirm the chip element is gated on both `isDataUrl` AND `meta`.                                                                    | `grep -n "isDataUrl && meta" web/components/FileUrlInput.tsx` returns at least one match (the chip's conditional render).                                                                                                                                                                                       |

### Why these steps would fail if the change were broken

- **T3.1 / T3.5**: if FileUrlInput weren't wired into PromptPanel for these modes, the row would be just a textbox (no Upload button) — visually unmistakable.
- **T3.3 vs T3.7**: a no-op size validator (e.g., `if (false) setError(...)`) would let the 12 MB file through and a chip would appear. We deliberately test BOTH a passing case (T3.3) and a failing case (T3.7) so a broken validator is caught — if T3.7 also produced a chip, that's a real regression.
- **T3.6**: if the `warnBase64` advisory were dropped (e.g., conditional inverted, or the prop not passed for motion-control), the yellow warning wouldn't appear and the user wouldn't know Freepik may reject the upload. We're explicit about the yellow color and the exact words in the assertion so a silent class-name typo would also fail.
- **T3.4**: if the X clear button didn't reset state, the textbox would still be locked with the placeholder, masking the bug.

## Regression sweep (visual only, no submit)

To prove the other three modes at least *render* correctly with the right
controls (the user requested 4 modes total):

| #    | Action                                       | Pass criterion                                                                                                |
| ---- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| R2.1 | Click **Text to Video** in the sidebar.      | Veo 3.1 + Kling 3 Pro · T2V cards visible. Right pane shows duration / aspect ratio / "Generate native audio". |
| R2.2 | Click **Image to Video** in the sidebar.     | Kling 3 Pro · I2V, Kling 2.6 Pro · I2V, Seedance Pro 720p, Seedance Pro 1080p visible. Form shows "Start frame image URL *". |
| R2.3 | Click **Motion Control** in the sidebar.     | Kling 2.6 Pro/Std and Kling 3 Omni Pro cards visible. Form shows both "Character image URL" and "Reference motion video URL" fields.  |

These three are clearly labeled "Regression" so a reviewer skipping them is fine.

## Out of scope

- I will **not** burn user credits running real Veo 3.1 / Kling 3 Pro video
  generations or motion-control transfers — those each consume significant
  Freepik credits and require separate publicly-reachable image/video URLs.
  Nano Banana Pro is the right canary because all four modes share the same
  proxy, key-rotation, gallery, and polling code paths.
- I will not test the page-reload polling resume — recording would have a long
  idle gap. The mechanism is exercised by the same `pollItem` loop that T1.2
  drives.
