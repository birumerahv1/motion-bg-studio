# Deploy ke Vercel

App ini adalah Next.js 14 standar — **tidak butuh env var apapun** karena
API key Freepik disimpan di localStorage browser pengguna, bukan di server.

---

## Opsi A — Import dari GitHub (paling cepat, otomatis update tiap push)

1. Buka https://vercel.com/new
2. Klik **Add New… → Project**, pilih repo `birumerahv1/motion-bg-studio`.
3. Di halaman konfigurasi:
   - **Framework Preset**: Next.js (terdeteksi otomatis)
   - **Root Directory**: klik **Edit**, pilih `web` ← penting, kalau dibiarkan
     `./` build akan gagal karena di root repo ada project Python.
   - **Build & Output Settings**: biarkan default (`next build`).
   - **Environment Variables**: kosongkan, tidak ada yang perlu diisi.
4. Klik **Deploy**.

Vercel akan kasih URL `https://<nama-project>.vercel.app`. Buka, klik
**API Keys** di sidebar kiri, paste key Freepik Anda → siap dipakai.

Setiap push ke branch `devin/1777798272-freepik-ai-studio` (atau `main`
nanti setelah merge) akan auto-redeploy.

---

## Opsi B — Upload manual via Vercel CLI (kalau tidak mau lewat GitHub)

```bash
unzip freepik-ai-studio-web.zip
cd freepik-ai-studio-web
npm install
npx vercel       # interaktif: login + create project
npx vercel --prod
```

Tidak ada env var yang perlu diset.

---

## Opsi C — Build lokal lalu deploy ke hosting lain

```bash
npm install
npm run build
npm start        # listen di port 3000
```

Atau pakai Docker / Node host kesukaan Anda — yang penting `next start`
bisa jalan.

---

## Catatan keamanan

- API key tidak pernah masuk ke server / log / database. Hanya
  `localStorage` browser pengguna → diteruskan langsung ke
  `api.freepik.com` lewat server proxy (`/api/generate`, `/api/task`,
  `/api/proxy`).
- Tidak ada autentikasi user di app ini. Siapa saja yang punya URL bisa
  pakai. Kalau Anda mau batasi, bisa tambahkan password basic auth lewat
  Vercel Edge Middleware.
- Cap upload: 10 MB image, 15 MB video. Diatur di
  `next.config.js` (`bodySizeLimit: "20mb"`).

---

## Trouble­shooting

- **"Generation failed: Failed to execute 'fetch' on 'Window'..."** —
  hanya terjadi kalau URL halaman berisi credentials seperti
  `https://user:pass@host/`. Vercel deploy tidak punya basic auth jadi
  tidak akan kena. Kalau pakai tunnel/proxy yang sama dengan basic auth,
  fix sudah ada di commit `ae175b1` (strip credentials dari
  `window.location` saat mount).
- **Motion Control reject base64 video** — beberapa endpoint Freepik
  memang require URL publik untuk `video_url`. UI sudah kasih peringatan
  kuning saat data URL dipilih. Solusinya: host video di S3/Cloudinary/dll
  lalu paste URL HTTPS-nya.
- **Free trial 429** — Freepik free trial selalu return
  `429 free trial usage limit reached`. Pakai paid key.
