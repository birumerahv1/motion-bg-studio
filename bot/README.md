# Freepik AI Studio — Telegram Bot

Bot Telegram berbasis Freepik AI dengan **subscription / billing built-in**:

- 🖼 **Text → Image**: Nano Banana Pro, Seedream 4.5
- 🎬 **Text → Video**: Veo 3.1, Kling 3 Pro
- 🎞 **Image → Video**: Kling 3 Pro, Kling 2.6 Pro, Seedance Pro 720p/1080p
- 💃 **Motion Control**: Kling 2.6 Pro/Std, Kling 3 Omni Pro

## Mode operasi

Bot mendukung dua mode (di-toggle via env `ALLOW_BYO_KEYS`):

| Mode | Bagaimana cara kerjanya |
|---|---|
| **SaaS / Operator** (default) | Anda kasih key Freepik via `OPERATOR_FREEPIK_KEYS` (atau `/opaddkey` di Telegram). User tidak butuh key sendiri — mereka beli paket via `/buy` (manual QRIS / transfer, admin approve). |
| **BYO** (`ALLOW_BYO_KEYS=1`) | User tetap bisa `/addkey FPSX...` dan pakai key sendiri (gratis bagi mereka, tidak menguras quota Anda). Subscription tetap berfungsi untuk yang ingin pakai key Anda. |

## Plan default (edit di `bot/billing.py`)

| Plan | Harga | Durasi | Akses |
|---|---|---|---|
| **Bulanan** | Rp 49.999 | 30 hari | Unlimited semua model |
| **Lifetime** | Rp 499.999 | selamanya (sekali bayar) | Unlimited semua model |

Tidak ada quota / credits — pakai sepuasnya selama langganan aktif. Edit `bot/billing.py` untuk ganti harga atau menambah paket.

## Quick start

```bash
cd bot
pip install -r requirements.txt
cp .env.example .env
# isi BOT_TOKEN, OPERATOR_FREEPIK_KEYS, ADMIN_USER_IDS
python -m bot
```

Lalu chat private bot, ketik `/start`. Sebagai admin, jalankan setup awal:

```
/setqris       (reply ke foto QRIS Anda)
/setbank       BCA 1234567 a.n. Nama Anda
                Mandiri 1110002 a.n. Nama Anda
/setsupport    @kontak_admin
/opaddkey      FPSXabc123… (kalau belum diisi via env)
```

Sekarang user yang `/buy` akan menerima QRIS + info bank otomatis.

## Docker

```bash
docker build -t freepik-studio-bot -f bot/Dockerfile .
docker run --rm -it \
  -e BOT_TOKEN=123:abc \
  -e OPERATOR_FREEPIK_KEYS=FPSXkey1,FPSXkey2 \
  -e ADMIN_USER_IDS=123456789 \
  -v $(pwd)/bot-data:/app/data \
  freepik-studio-bot
```

## Deploy

Lihat [DEPLOY.md](DEPLOY.md) untuk panduan lengkap deploy ke Railway, Fly.io, atau VPS biasa.

## Privasi & keamanan

- API key Freepik (operator + BYO) disimpan di SQLite lokal bot. Tidak dikirim ke pihak ketiga selain Freepik sendiri.
- `/addkey` dan `/opaddkey` hanya bekerja di chat private 1:1. Pesan asli yang berisi key langsung dihapus oleh bot setelah disimpan.
- Bot tidak pernah me-log isi API key — yang di-log hanya fingerprint pendek (`<hash>:<4 char terakhir>`).

## Perintah

### User
| Command | Fungsi |
|---|---|
| `/start`, `/menu`, `/help` | Buka mode picker |
| `/plans` | Daftar paket & harga |
| `/buy` | Beli paket — bot kirim QRIS + info bank + kode referensi |
| `/paid <ref>` | Sertakan caption ini di screenshot bukti transfer |
| `/me` | Status langganan & sisa quota |
| `/history` | 10 generasi terakhir |
| `/stop` | Batalkan generasi yang sedang berjalan |
| `/cancel` | Keluar dari flow conversation |
| `/skip` | Skip step optional (negative prompt, end frame, **prompt motion control**) |
| `/seturl <url>` | Set reference video pakai URL publik |

### Admin (otomatis dari `ADMIN_USER_IDS` atau via `/setadmin`)
| Command | Fungsi |
|---|---|
| `/admin` | Dashboard admin |
| `/payments [pending\|approved\|rejected\|all]` | List payment |
| `/approve <id>` | Approve payment → aktifkan subscription |
| `/reject <id> [alasan]` | Reject payment dengan alasan |
| `/opaddkey FPSX… [label]` | Tambah operator Freepik key (pesan dihapus) |
| `/oplistkeys` | List semua operator key |
| `/opdelkey <id>` `/opdisable <id>` `/openable <id>` | Manage operator key |
| `/setqris` (reply ke foto QRIS) | Set image QRIS pembayaran |
| `/setbank <multi-line>` | Set info rekening |
| `/setsupport @username` | Set kontak support |
| `/setadmin <user_id> [note]` | Tambah admin baru runtime |
| `/unsetadmin <user_id>` `/listadmins` | Manage admin |
| `/setplan <user_id> <plan_id> [days]` | Override subscription manual |
| `/broadcast <pesan>` | Kirim pesan ke semua user tercatat |
| `/stats` | Ringkasan statistik bot |

### BYO mode (kalau `ALLOW_BYO_KEYS=1`)
| Command | Fungsi |
|---|---|
| `/addkey <FPSX…> [label]` | Tambah API key milik user sendiri |
| `/listkeys` `/delkey <id>` `/clearkeys` | Manage key user |

## Alur pembelian (manual QRIS / transfer)

1. User: `/buy` → pilih paket dengan tombol.
2. Bot kirim **kode referensi unik** (mis. `FP-12345-6789`), info QRIS, dan info rekening yang admin sudah `/setqris` + `/setbank`.
3. User transfer / scan QRIS sebesar harga paket, sertakan kode referensi di catatan transfer.
4. User screenshot bukti, kirim ke bot dengan caption `/paid FP-12345-6789` (boleh juga reply ke screenshot lama).
5. Bot kirim notifikasi ke semua admin dengan tombol **✅ Approve** / **❌ Reject**.
6. Admin tap Approve → subscription user otomatis aktif (+ 30 hari, quota direset). User dapat notifikasi balik.

## Sync dengan web app

`bot/freepik_models.py` adalah port langsung dari `web/lib/models.ts`. Kalau ada model baru ditambahkan di web app, update file ini juga. `bot/freepik_client.py` mirror logic dari `web/lib/freepik.ts`.
