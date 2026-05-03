# T3 Test Report — Local file upload for Image→Video and Motion Control

PR: https://github.com/birumerahv1/motion-bg-studio/pull/3
Recording: https://app.devin.ai/attachments/145a7c9a-0263-4d26-b82e-dee73314f838/rec-71360b6b-2585-4f24-88f6-cff171e3091e-edited.mp4
Session: https://app.devin.ai/sessions/daa26397d04b430b8a6f42260ee287ae

## TL;DR

All client-side assertions on the new `FileUrlInput` component passed.
End-to-end Freepik happy-path is **still untested** because the supplied API
key is on a free trial returning HTTP 429.

| ID    | Result | What was checked                                                                                                                                |
| ----- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| T3.1  | passed | Image→Video Start + End frame fields render Upload button next to URL input                                                                     |
| T3.2  | passed | File picker filter is `image/png,image/jpeg,image/jpg,image/webp` (verified by accept attribute and picker behaviour)                            |
| T3.3  | passed | 75-byte PNG → chip "test-image.png · 75 B" shown; textbox locked with "Local file uploaded — clear to type a URL" placeholder                   |
| T3.4  | passed | X clear button removes chip and unlocks textbox                                                                                                  |
| T3.5  | passed | Motion Control: Character image AND Reference motion video each render Upload buttons                                                            |
| T3.6  | passed | Reference-video upload: chip + yellow advisory "Freepik mungkin menolak file lokal di sini (endpoint butuh URL publik). Jika gagal..."           |
| T3.7  | passed | 12.6 MB image rejected: red error "File terlalu besar (12.0 MB). Maksimum 10.0 MB untuk gambar." — chip does **not** appear                    |
| T3.8  | passed | `grep "isDataUrl && meta" web/components/FileUrlInput.tsx` returns 1 match (chip element correctly gated on both conditions)                    |
| Reg.  | passed | Earlier "Test card – verifying Stop button" gallery item is still visible after a dev-server restart, confirming the hydration fix still works  |

The contrast between T3.3 (75 B accepted) and T3.7 (12.6 MB rejected) is the
critical evidence that the size validator is real and not a no-op.

## Untested / blocked

- **Freepik happy-path** (e.g. uploading a real start frame and seeing
  `COMPLETED`). The user's API key returns `429 free trial usage limit
  reached`. To unblock this we need a paid Freepik key, ideally two keys to
  also exercise auto-failover end-to-end.
- **Backend acceptance of base64 video** for motion-control `video_url`.
  Because of the same 429, we couldn't observe whether Freepik's Kling 2.6 /
  Kling 3 Omni Pro endpoints accept a `data:video/mp4;base64,...` URL. The
  yellow advisory in T3.6 explicitly warns about this — if it fails in
  production, the user can paste a public URL instead.

## Evidence

### T3.1 — Upload buttons present on Image→Video

![Image-to-Video panel showing both Start frame and End frame fields with Upload buttons](https://app.devin.ai/attachments/3398555d-68df-46a3-b76d-a96737fd013b/01-i2v-upload-buttons.png)

### T3.3 — 75-byte PNG accepted; chip renders

![Image-to-Video Start frame showing test-image.png · 75 B chip and locked textbox](https://app.devin.ai/attachments/b185fc20-a1bd-4622-af0a-b4bd81062626/02-i2v-chip-after-upload.png)

### T3.6 — Motion Control reference-video upload triggers yellow advisory

![Motion Control panel with sample.mp4 chip and yellow advisory below it](https://app.devin.ai/attachments/39bfc9a4-1c3e-4876-b64a-837e206f84c1/03-mc-video-chip-yellow-advisory.png)

### T3.7 — 12.6 MB image rejected with red size-cap error

![Motion Control character-image field with red error "File terlalu besar (12.0 MB). Maksimum 10.0 MB untuk gambar."](https://app.devin.ai/attachments/e740b92d-e981-4a0e-ab5b-caaa4ccd38ce/04-mc-oversize-image-rejected.png)

## Notes on the diff itself

- The component is `web/components/FileUrlInput.tsx`. The chip is gated with
  `{isDataUrl && meta && (...)}` so a stray non–data-URL value (e.g. a
  user-typed `https://...`) cannot accidentally render the chip.
- `web/components/PromptPanel.tsx` was wired to use this component for
  `startImageUrl`, `endImageUrl`, and `referenceVideoUrl`. The
  `warnBase64={true}` prop is passed only to the motion-control reference
  video field, which is why T3.6 triggers the advisory and T3.3 does not.
- A separate payload-name bug was fixed in `web/lib/freepik.ts` —
  motion-control endpoints now send `image_url` / `video_url` (matching
  Freepik OpenAPI) instead of `start_image_url` / `reference_video_url`
  which were rejected by the API. This change is **not directly testable
  without a working API key**, but lint + build + CI pass with it.
