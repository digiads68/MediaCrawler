# DEPLOY — MediaCrawler × DigiAds Kit trên server

> Hướng dẫn deploy bản v2 lên server Linux (vd Azure VM `172.188.242.245`, Ubuntu 22.04+).
> Nguyên tắc: API + worker chạy bằng **systemd**, secrets trong `/opt/MediaCrawler/.env`
> (chmod 600), crawl giữ concurrency = 1.

## 1. Chuẩn bị máy

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv git redis-server
sudo systemctl enable --now redis-server

# Thư mục chuẩn (khớp đường dẫn trong kit/n8n/*.json)
sudo mkdir -p /opt && cd /opt
sudo git clone https://github.com/digiads68/MediaCrawler.git
cd MediaCrawler
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt anthropic supabase arq "mcp[cli]"
.venv/bin/playwright install chromium   # nếu crawl trực tiếp trên server
```

## 2. Biến môi trường

```bash
cp .env.example .env && nano .env      # điền key thật
chmod 600 .env                          # chỉ owner đọc được
```

Bắt buộc: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (service_role —
không bao giờ đưa ra client), `NOTIFY_WEBHOOK_URL`, `REDIS_URL`,
`MEDIACRAWLER_API=http://127.0.0.1:8080`.

## 3. Schema Supabase (1 lần)

Chạy lần lượt trong Supabase SQL Editor: `kit/storage/schema/001_core.sql` →
`002_views.sql` → `003_checkpoints.sql` (chi tiết: `kit/storage/README.md`).

## 4. systemd — REST API

`/etc/systemd/system/mediacrawler-api.service`:

```ini
[Unit]
Description=MediaCrawler REST API (DigiAds v2)
After=network.target

[Service]
Type=simple
User=digiads
WorkingDirectory=/opt/MediaCrawler
EnvironmentFile=/opt/MediaCrawler/.env
ExecStart=/opt/MediaCrawler/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8080
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> API bind `127.0.0.1` — chỉ truy cập nội bộ/n8n trên cùng máy. Nếu cần WebUI từ xa,
> đặt sau reverse proxy (nginx + basic auth), KHÔNG mở 8080 ra internet.

## 5. systemd — arq worker (Tier 2)

`/etc/systemd/system/mediacrawler-worker.service`:

```ini
[Unit]
Description=DigiAds Kit arq worker (job tuần tự)
After=network.target redis-server.service mediacrawler-api.service

[Service]
Type=simple
User=digiads
WorkingDirectory=/opt/MediaCrawler
EnvironmentFile=/opt/MediaCrawler/.env
ExecStart=/opt/MediaCrawler/.venv/bin/arq kit.queue.worker.WorkerSettings
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Kích hoạt:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mediacrawler-api mediacrawler-worker
systemctl status mediacrawler-api mediacrawler-worker
journalctl -u mediacrawler-worker -f     # xem log tiếng Việt của job
```

## 6. Lịch tự động — n8n hoặc cron

**n8n (khuyến nghị):** import 3 workflow trong `kit/n8n/` — WF_MC1 (trend brief tuần),
WF_MC2 (SOV tháng), WF_MC3 (rising KOC 2 tuần). Sửa node `executeCommand` cho khớp
đường dẫn `/opt/MediaCrawler`; đặt env `ANTHROPIC_API_KEY`, `NOTIFY_WEBHOOK_URL`,
`SUPABASE_URL`, `SUPABASE_KEY` trong n8n.

**cron (thay thế):** ví dụ đẩy job trend mỗi thứ Hai 06:00:

```cron
0 6 * * 1 cd /opt/MediaCrawler && .venv/bin/python kit/queue/enqueue.py dy search "护肤,精华" --analyze trend --to supabase --notify >> /var/log/digiads-kit.log 2>&1
```

## 7. Cập nhật phiên bản

```bash
cd /opt/MediaCrawler && sudo git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart mediacrawler-api mediacrawler-worker
```

## 8. Checklist an toàn

- [ ] `.env` chmod 600, không nằm trong git (`git check-ignore .env` phải trả về `.env`).
- [ ] Port 8080 không mở ra internet (ufw/NSG chỉ cho SSH + reverse proxy).
- [ ] Supabase RLS bật (mặc định trong schema); service_role key chỉ ở backend.
- [ ] Worker max_jobs = 1 — không sửa để "chạy nhanh hơn" (ranh giới CLAUDE.md).
- [ ] Dữ liệu cào (`data/`) không đẩy lên GitHub (đã trong .gitignore).
