# MediaCrawler × DigiAds Kit (v2)

> Cỗ máy **nghiên cứu sáng tạo** cho agency media/bán hàng: thu thập dữ liệu công khai
> từ 7 nền tảng (Douyin, Xiaohongshu, Kuaishou, Bilibili, Weibo, Tieba, Zhihu) và
> phân tích thành **11 case study** — trend radar, voice-of-customer, thẩm định KOC,
> angle library nạp AI video, share-of-voice...

> ⚠️ **Chỉ dùng nghiên cứu nội bộ dữ liệu công khai.** Tuân thủ ToS/robots.txt của
> nền tảng và **Nghị định 13/2023** về bảo vệ dữ liệu cá nhân (creator luôn ẩn danh,
> không de-anonymize). Giữ concurrency = 1, có nghỉ giữa request. Không dùng thương mại
> — xem [License](#license--credits).

## Kiến trúc

```
crawl (media_platform/, REST api/ :8080)
  → enrich   (kit/enrich/    — chuẩn hoá count/thời gian, engagement, format, dịch ZH→VI)
  → storage  (kit/storage/   — Supabase: 6 bảng + 4 view dashboard, checkpoint tăng dần)
  → analyzer (kit/analyzer/  — 11 case: trend/insight/koc/opportunity/seasonal/price/sov/angle)
  → pipeline (kit/pipeline/  — angle_library.jsonl → Video Brief JSON cho AI video)
  → n8n      (kit/webhook/ + kit/n8n/ — tự động hoá tuần/tháng, alert rising KOC)
```

Chi tiết: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
Sổ tay nghiệp vụ: [docs/HANDBOOK_11_case_studies.html](docs/HANDBOOK_11_case_studies.html) ·
Hướng dẫn build từng bước: [BUILD_GUIDE_ClaudeCode.md](BUILD_GUIDE_ClaudeCode.md)

## Quick start

```bash
git clone https://github.com/digiads68/MediaCrawler.git && cd MediaCrawler

# 1. Cài đặt (Python 3.11+)
pip install -r requirements.txt
pip install anthropic supabase arq "mcp[cli]"
cp .env.example .env        # điền ANTHROPIC_API_KEY, SUPABASE_URL/KEY...

# 2. Tạo schema Supabase (1 lần) — xem kit/storage/README.md
#    chạy kit/storage/schema/001..003 trong SQL Editor

# 3. Bật REST API crawler + WebUI
uvicorn api.main:app --port 8080     # WebUI: http://127.0.0.1:8080

# 4. Phân tích dữ liệu đã cào (11 case)
python kit/analyzer/mediacrawler_analyzer.py trend data/douyin/search_x.xlsx --to supabase --notify
python kit/analyzer/mediacrawler_analyzer.py koc   data/douyin/creator_x.xlsx
python kit/analyzer/mediacrawler_analyzer.py sov   data/douyin/search_x.xlsx kit/config/brand_map.json

# 5. Angle → Video Brief (AI video, cần ANTHROPIC_API_KEY; demo offline dùng --provider mock)
python kit/pipeline/angle_to_brief.py reports/angle_library.jsonl --product "Serum kiềm dầu 199k"

# 6. (Tier 2) Hàng đợi job — cần Redis
arq kit.queue.worker.WorkerSettings                          # terminal 1
python kit/queue/enqueue.py dy search "护肤" --analyze trend  # terminal 2

# Test
pytest tests -q
```

## REST API cho kit

| Endpoint | Chức năng |
|---|---|
| `POST /kit/analyze` | Chạy analyzer trên file dữ liệu (`command`, `file`, `to_supabase`, `notify`) |
| `GET /kit/reports/{name}` | Tải báo cáo Excel/JSONL từ `reports/` |
| `POST /kit/angle-brief` | Chạy pipeline Angle → Video Brief (`provider: claude\|mock`) |

OpenAPI đầy đủ tại `http://127.0.0.1:8080/docs`.

## Cấu trúc thư mục

```
├── main.py  api/  webui/  media_platform/   # MediaCrawler base (fork, giữ nguyên)
├── kit/                                     # ★ DigiAds Kit
│   ├── analyzer/     # 1 file phân tích 11 case
│   ├── enrich/       # normalize / velocity / translate ZH→VI
│   ├── storage/      # schema SQL + SupabaseWriter + checkpoint
│   ├── pipeline/     # angle_to_brief (chuỗi 6 prompt → Video Brief)
│   ├── prompts/      # angle_to_video_prompts (6 stage)
│   ├── queue/        # arq worker (Tier 2, tuần tự)
│   ├── webhook/      # emit event → n8n
│   ├── mcp/          # MCP server cho AI agent
│   ├── n8n/          # 3 workflow (tuần / tháng / 2 tuần)
│   ├── templates/    # 5 mẫu Excel output
│   └── config/       # brand_map.json (rổ brand CS11)
├── docs/             # ARCHITECTURE, DEPLOY, HANDBOOK, README upstream
└── tests/            # test synthetic (không gọi mạng) + CI
```

## Deploy

Xem [docs/DEPLOY.md](docs/DEPLOY.md) — systemd cho API + arq worker, biến môi trường,
lịch n8n/cron trên server.

## License & Credits

- Fork từ [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) —
  cảm ơn tác giả gốc. README upstream: [docs/README_upstream.md](docs/README_upstream.md).
- Giữ nguyên **NON-COMMERCIAL LEARNING LICENSE 1.1** của repo gốc (xem [LICENSE](LICENSE)):
  chỉ dùng học tập/nghiên cứu, **không thương mại**, không gây tải bất thường lên nền tảng.
- Phần `kit/` (DigiAds) tuân theo cùng license và các ranh giới trong [CLAUDE.md](CLAUDE.md).
