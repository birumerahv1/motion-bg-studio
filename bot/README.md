# Freepik AI Studio — Telegram Bot

Bot Telegram dengan kemampuan yang sama seperti web app di `web/`:

- 🖼 **Text → Image**: Nano Banana Pro, Seedream 4.5
- 🎬 **Text → Video**: Veo 3.1, Kling 3 Pro
- 🎞 **Image → Video**: Kling 3 Pro, Kling 2.6 Pro, Seedance Pro 720p/1080p
- 💃 **Motion Control**: Kling 2.6 Pro/Std, Kling 3 Omni Pro

Fitur:

- Multi API key Freepik per user — kalau salah satu key kena 401/403/429/5xx, bot otomatis pindah ke key berikutnya.
- Upload gambar/video langsung dari Telegram (foto/dokumen). Cap 10 MB image, 15 MB video.
- `/seturl` untuk paste URL publik (kalau Freepik menolak base64 di endpoint motion-control).
- Riwayat 10 generasi terakhir disimpan di SQLite (`/history`).
- `/stop` untuk batalkan generasi yang sedang berjalan.

## Quick start (local)

```bash
cd bot
pip install -r requirements.txt
cp .env.example .env
# edit .env, isi BOT_TOKEN dari @BotFather
python -m bot
```

Lalu di Telegram, buka chat private dengan bot Anda dan ketik `/start`.

## Docker

```bash
# dari root repo
docker build -t freepik-studio-bot -f bot/Dockerfile .
docker run --rm -it \
  -e BOT_TOKEN=123:abc \
  -v $(pwd)/bot-data:/app/data \
  freepik-studio-bot
```

## Deploy

Lihat <a href="DEPLOY.md">DEPLOY.md</a> untuk panduan lengkap deploy ke Railway, Fly.io, atau VPS biasa.

## Privasi & keamanan

- API key Freepik disimpan **per Telegram user** di SQLite lokal bot. Tidak ada key yang dikirim ke layanan pihak ketiga selain Freepik sendiri.
- `/addkey` hanya bekerja di chat private 1:1, dan pesan asli yang berisi API key langsung dihapus oleh bot setelah disimpan.
- Bot tidak pernah me-log isi API key — yang di-log hanya fingerprint pendek (`<hash>:<4 char terakhir>`).

## Perintah

| Command | Fungsi |
|---|---|
| `/start`, `/menu`, `/help` | Buka mode picker |
| `/addkey <FPSX...> [label]` | Tambah API key (private chat only) |
| `/listkeys` | Lihat key tersimpan |
| `/delkey <id>` | Hapus key berdasarkan id |
| `/clearkeys` | Hapus semua key |
| `/history` | 10 generasi terakhir |
| `/stop` | Batalkan generasi yang sedang berjalan |
| `/cancel` | Keluar dari flow yang lagi jalan |
| `/skip` | Skip step optional (negative prompt, end frame) |
| `/seturl <url>` | Set reference video pakai URL publik |

## Sync dengan web app

`bot/freepik_models.py` adalah port langsung dari `web/lib/models.ts`. Kalau ada model baru ditambahkan di web app, update file ini juga. `bot/freepik_client.py` mirror logic dari `web/lib/freepik.ts`.
