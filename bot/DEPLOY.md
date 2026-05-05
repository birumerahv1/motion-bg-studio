# Deploy Telegram Bot

Tiga opsi deploy, dari termudah ke paling fleksibel.

## Persiapan (sekali saja)

1. Buka Telegram, chat ke [@BotFather](https://t.me/BotFather).
2. Kirim `/newbot` → ikuti petunjuk → catat **bot token** yang diberikan, formatnya `123456789:AAxxx...`.
3. (Opsional) Kirim `/setcommands` ke @BotFather → pilih bot Anda → paste:
   ```
   start - Buka mode picker
   menu - Buka mode picker
   help - Bantuan & daftar perintah
   addkey - Tambah API key Freepik (private chat)
   listkeys - Lihat key tersimpan
   delkey - Hapus key
   clearkeys - Hapus semua key
   history - 10 generasi terakhir
   stop - Batalkan generasi
   cancel - Keluar flow
   skip - Skip step optional
   seturl - Set reference video URL
   ```

---

## Opsi A — VPS / server biasa (paling sederhana)

Cocok kalau Anda sudah punya VPS Linux (Ubuntu, Debian, dll).

```bash
# di server
git clone https://github.com/birumerahv1/motion-bg-studio.git
cd motion-bg-studio/bot

# install Python 3.11+ kalau belum ada
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv

# buat virtualenv & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# konfigurasi
cp .env.example .env
nano .env   # isi BOT_TOKEN

# jalankan langsung untuk test
python -m bot
```

Untuk supaya bot tetap jalan setelah Anda close SSH, pakai `systemd`:

```bash
# /etc/systemd/system/freepik-bot.service
[Unit]
Description=Freepik AI Studio Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/motion-bg-studio
EnvironmentFile=/home/ubuntu/motion-bg-studio/bot/.env
ExecStart=/home/ubuntu/motion-bg-studio/bot/.venv/bin/python -m bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Lalu:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now freepik-bot
sudo journalctl -u freepik-bot -f
```

---

## Opsi B — Docker (atau Docker Compose)

```bash
# build dari root repo
docker build -t freepik-studio-bot -f bot/Dockerfile .

# jalankan, mount data folder supaya DB persisten
docker run -d --name freepik-bot \
  --restart unless-stopped \
  -e BOT_TOKEN="$BOT_TOKEN" \
  -v $PWD/bot-data:/app/data \
  freepik-studio-bot

# logs
docker logs -f freepik-bot
```

Atau pakai compose (`docker-compose.yml` di root repo):

```yaml
version: "3.9"
services:
  freepik-bot:
    build:
      context: .
      dockerfile: bot/Dockerfile
    image: freepik-studio-bot
    restart: unless-stopped
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
    volumes:
      - ./bot-data:/app/data
```

```bash
echo 'BOT_TOKEN=123:abc' > .env
docker compose up -d
```

---

## Opsi C — Fly.io (gratis tier kecil cukup)

```bash
# install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
cd bot

# inisialisasi (bot folder berisi Dockerfile)
fly launch --no-deploy --copy-config --name freepik-studio-bot

# tambahkan persistent volume untuk SQLite
fly volumes create bot_data --size 1 --region sin

# edit fly.toml, tambahkan mount:
#   [mounts]
#     source = "bot_data"
#     destination = "/app/data"

# set secret
fly secrets set BOT_TOKEN=123:abc

# deploy
fly deploy
fly logs
```

---

## Opsi D — Railway / Render (deploy dari GitHub UI)

1. Buka https://railway.app/new (atau https://render.com/)
2. **Deploy from GitHub repo** → pilih `birumerahv1/motion-bg-studio`
3. Set **root directory** ke `bot/` (Railway: di tab Settings → Service Settings).
4. Set **Dockerfile path** ke `bot/Dockerfile` (atau biarkan Railway auto-detect).
5. Set environment variable: `BOT_TOKEN = 123:abc`.
6. (Railway only) tambahkan **Volume**, mount path `/app/data` supaya DB tidak hilang saat redeploy.
7. Deploy.

---

## Verifikasi

Setelah deploy, di Telegram:

1. Buka chat private dengan bot Anda.
2. `/start` → seharusnya muncul welcome + 4 tombol mode.
3. `/addkey FPSX36395ce7...` → bot konfirmasi dan auto-hapus pesan asli.
4. `/listkeys` → seharusnya muncul fingerprint key.
5. `/menu` → pilih mode → pilih model → kirim prompt → tunggu hasil.

Kalau bot tidak respon: cek logs (`journalctl`, `docker logs`, atau `fly logs`).

## Pertimbangan biaya

- VPS kecil (1 vCPU / 1 GB RAM) sudah cukup. Bot pakai long-polling (tidak butuh public IP / port forwarding).
- Bot **tidak menyimpan file gambar/video** dari Freepik — file langsung di-stream ke Telegram. SQLite hanya menyimpan metadata (URL, status, fingerprint key) jadi tetap kecil.
- Cap upload user: 10 MB image, 15 MB video. Bisa diubah via `MAX_IMAGE_BYTES` dan `MAX_VIDEO_BYTES` di env.

## Update bot

```bash
cd motion-bg-studio
git pull
# systemd
sudo systemctl restart freepik-bot
# docker
docker compose up -d --build
# fly.io
cd bot && fly deploy
```

DB SQLite sudah punya `CREATE TABLE IF NOT EXISTS`, jadi schema migration aman.
