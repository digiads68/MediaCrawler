# DEPLOY — MediaCrawler × DigiAds Kit trên server

> Hai cách deploy: **Windows local + Tailscale** (nhanh, dùng máy cá nhân — xem PHẦN 0)
> hoặc **server Linux systemd** (Azure VM, chạy 24/7 — xem PHẦN 1). Nguyên tắc chung:
> secrets trong `.env` (không commit), crawl giữ concurrency = 1.

## PHẦN 0 — Windows local + Tailscale (khuyến nghị cho máy cá nhân)

Dùng khi anh chạy MediaCrawler ngay trên máy Windows của mình (không cần server đám mây)
và muốn truy cập WebUI từ máy/điện thoại khác qua mạng riêng ảo [Tailscale](https://tailscale.com).

### 0.1. Cài đặt lần đầu

1. Clone repo, cài [Tailscale](https://tailscale.com/download) trên **máy chạy server**
   và trên **máy sẽ truy cập từ xa**, đăng nhập cùng 1 tài khoản Tailscale (cùng tailnet)
   ở cả hai máy.
2. Double-click **`start.bat`** ở gốc repo. Lần đầu chạy sẽ tự động:
   - Tạo `.venv`, cài `requirements.txt` + gói của DigiAds Kit (anthropic, supabase, arq, mcp[cli]).
   - Cài `uv` qua winget nếu máy chưa có (`uv` cần cho nút "Initiate Scan" khởi động crawl thật).
   - Build WebUI (`webui/` → `api/webui/`) nếu có Node.js/npm; bỏ qua nếu chưa cài Node
     (vẫn dùng được REST API, chỉ thiếu giao diện).
   - Tạo `.env` từ `.env.example` (điền `ANTHROPIC_API_KEY`/`SUPABASE_*` sau nếu cần).
   - Khởi động server ở `0.0.0.0:8080` (nghe trên mọi network interface, bao gồm Tailscale).
3. Script sẽ in ra địa chỉ Tailscale của máy này (nếu `tailscale` CLI có trong PATH) —
   ví dụ `http://100.x.y.z:8080`. Từ máy khác trong cùng tailnet, mở đúng địa chỉ đó.

### 0.2. Mở Windows Firewall cho cổng 8080 (chỉ cần 1 lần)

`start.bat` không tự sửa Firewall (thay đổi cấu hình bảo mật hệ thống cần anh tự xác nhận).
Nếu máy khác không vào được, mở **Command Prompt (Run as Administrator)** trên máy chạy
server, chạy:

```cmd
netsh advfirewall firewall add rule name=MediaCrawlerAPI dir=in action=allow protocol=TCP localport=8080
```

Muốn thu hẹp phạm vi cho chắc (chỉ Tailscale, không cả mạng LAN), thêm
`remoteip=100.64.0.0/10` (dải IP nội bộ của Tailscale) vào cuối lệnh trên. Gỡ rule khi
không dùng nữa bằng `netsh advfirewall firewall delete rule name=MediaCrawlerAPI`.

### 0.3. Crawl dữ liệu thật (không chỉ xem WebUI)

Fork này dùng **CDP mode**: crawler kết nối vào 1 Chrome đang chạy sẵn (cổng debug 9222),
không tự bật browser. Trước khi bấm **"Initiate Scan"** trên WebUI:

1. Double-click **`start_browser_cdp.bat`** — mở 1 Chrome **riêng** (profile trắng, tách biệt
   Chrome anh dùng hàng ngày) với cổng debug 9222.
   - Nếu Chrome báo đã chạy / không hiện cửa sổ mới: **đóng hết Chrome hiện tại** (Task
     Manager → End task mọi dòng `chrome.exe`), rồi chạy lại file.
   - Chrome **profile mặc định** tự chặn cổng debug vì lý do an toàn — bắt buộc phải dùng
     `--user-data-dir` riêng như script đã làm, nếu không cổng 9222 sẽ không mở được dù cờ
     `--remote-debugging-port` có truyền đúng.
2. Chọn 1 profile (hoặc "Tiếp tục không có tài khoản") để vào giao diện Chrome chính.
3. Quay lại WebUI, bấm **"Initiate Scan"** — quét QR/đăng nhập ngay trong cửa sổ Chrome đó.
   Session được lưu trong `browser_data/cdp_profile/` (đã `.gitignore`) nên lần sau không
   cần đăng nhập lại.

### 0.4. Giới hạn đã biết

- `start.bat` bind `0.0.0.0` — server nghe trên **mọi** interface, không chỉ Tailscale.
  An toàn vì Windows Firewall (mặc định chặn inbound) là lớp chặn thực sự; chỉ mở rule ở
  bước 0.2 khi cần dùng, và thu hẹp `remoteip` như gợi ý nếu máy có IP LAN/công khai khác.
- Máy phải **luôn mở** (không sleep) trong lúc muốn truy cập từ xa.
- Không dùng cấu hình này cho crawl khối lượng lớn liên tục — giữ đúng ranh giới
  `MAX_CONCURRENCY_NUM=1` trong `CLAUDE.md`.

## PHẦN 1 — Server Linux (systemd, chạy 24/7)

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
