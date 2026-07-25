# DigiAds · MediaCrawler Kit

Bộ công cụ nội bộ biến MediaCrawler thành cỗ máy nghiên cứu sáng tạo, phục vụ 11 case study.

> ⚠️ Chỉ dùng cho **nghiên cứu nội bộ dữ liệu công khai**. Tuân thủ ToS nền tảng và
> Nghị định 13/2023. Giữ concurrency = 1, nghỉ giữa request. Tier 3 (multi-account/proxy)
> cần rà soát pháp lý trước.

## Cấu trúc

```
kit/
├── HANDBOOK_11_case_studies.html   # Sổ tay: mở file này trước
├── analyzer/
│   └── mediacrawler_analyzer.py    # 1 file phân tích cho cả 11 case
├── dashboard/                      # 4 loại dashboard HTML chuyên sâu + nút n8n
│   ├── adapters.py                 #   schema riêng từng nền tảng -> hợp nhất
│   ├── metrics.py                  #   nạp/gộp/chuẩn hoá + chỉ số chung
│   ├── analysis.py                 #   phân tích sâu (benchmark, outlier, VoC...)
│   ├── theme.py components.py      #   khung trang + khối UI dùng chung
│   └── profiles/                   #   search · creator · video · overview
├── prompts/
│   └── angle_to_video_prompts.py   # Nối Angle Library → pipeline AI video
├── mcp/
│   └── mcp_mediacrawler.py         # MCP server cho AI agent gọi crawler
├── n8n/
│   ├── WF_MC1_trend_brief_weekly.json     # CS1+CS10+CS5 tự động (tuần)
│   ├── WF_MC2_sov_monitor_monthly.json    # CS11 tự động (tháng)
│   ├── WF_MC3_rising_koc_alert.json        # CS9 tự động (2 tuần)
│   └── WF_MC4_content_action.json          # Webhook nút hành động dashboard
├── config/
│   └── brand_map.json              # rổ brand cho CS11 (sửa tại đây)
└── templates/
    ├── TREND_BRIEF_sample.xlsx     # CS1 + CS10
    ├── INSIGHT_BANK_sample.xlsx    # CS2
    ├── KOC_SCORECARD_sample.xlsx   # CS3 + CS9
    ├── OPPORTUNITY_MAP_sample.xlsx # CS4 + CS6 + CS8
    └── SOV_DASHBOARD_sample.xlsx   # CS11
```

## Cài đặt (1 lần)

```bash
# 0. MediaCrawler đã cài (uv sync) và bật CDP Chrome (127.0.0.1:9222)
# 1. Chạy REST API của MediaCrawler
uvicorn api.main:app --port 8080
# 2. Phụ thuộc cho kit
pip install pandas openpyxl httpx "mcp[cli]"
# 3. Đặt kit cạnh MediaCrawler (n8n executeCommand trỏ /opt/digiads/kit)
```

## Dùng nhanh theo case

| Case | Crawl | Analyzer | Output |
|---|---|---|---|
| CS1 Trend + CS10 Sound | `--type search` (dy/xhs) | `trend` | TREND_BRIEF |
| CS2 Voice of Customer | `--type detail` + comment | `insight` | INSIGHT_BANK |
| CS3 KOC vetting | `--type creator` | `koc` | KOC_SCORECARD |
| CS4/CS6 Product/Saturation | `--type search` (xhs) | `opportunity` | OPPORTUNITY_MAP |
| CS5 Angle Library | `--type search` → jsonl | `angle` | angle_library.jsonl |
| CS7 Seasonal | `--type search` + time | `seasonal` | CS7_seasonal_radar |
| CS8 Price Intel | `--type search` + comment | `price` | OPPORTUNITY_MAP (Price sheet) |
| CS9 Rising KOC | `--type search` | `koc` | CS9_rising_creators |
| CS11 SOV | `--type search` (lặp rổ) | `sov brand_map.json` | SOV_DASHBOARD |

> Muốn xem trực quan + bấm hành động (tải/voice→text/phân tích) thay vì file Excel
> → dùng **dashboard chuyên sâu** ở mục dưới.

Ví dụ:
```bash
python3 analyzer/mediacrawler_analyzer.py trend  data/douyin/search_护肤.xlsx
python3 analyzer/mediacrawler_analyzer.py koc    data/douyin/creator_x.xlsx
python3 analyzer/mediacrawler_analyzer.py sov    data/douyin/search_x.xlsx config/brand_map.json
```

## Dashboard chuyên sâu (4 loại, theo mode cào)

MediaCrawler có 3 mode cào, mỗi mode cho dữ liệu có "hình" khác nhau — nên có
**4 loại dashboard chuyên sâu** thay vì một bản tổng quan chung. Tất cả là HTML
**tự chứa**, mở offline, không cần server.

| Loại | Mode cào | Chuyên sâu về |
|---|---|---|
| **`search`** · Trend Radar | `--type search` | Săn trend & lên ý tưởng content |
| **`creator`** · Channel Audit | `--type creator` | Soi kênh đối thủ |
| **`video`** · Video Teardown | `--type detail` (+`--get_comment`) | Mổ xẻ video & tiếng nói khán giả |
| **`overview`** | trộn nhiều mode | Bức tranh chéo nền tảng để họp |

**`search` — Trend Radar** (5 tab)
- *Ngách & Chuẩn*: benchmark P25→P90 (biết bao nhiêu mới là "bài tốt") + mốc riêng từng nền tảng.
- *Video đáng clone*: sắp theo **mức vượt trội so với trung vị nền tảng**, nhãn 🚀 Bứt phá.
- *Format × Từ khoá*: ma trận hiệu quả + **khe trống** (cầu cao, cung thấp).
- *Hook Lab*: công thức hook nào **thực sự** hiệu quả (eng trung vị + tỷ lệ thắng), không chỉ đếm.
- *Thời điểm & Cơ hội*: heatmap giờ×thứ + bản đồ ngách vàng.

**`creator` — Channel Audit** (4 tab)
- *So sánh kênh*: nhịp đăng, đà tăng (velocity), độ đều, số bài bứt phá.
- *Soi từng kênh* (có bộ chọn kênh): timeline từng bài, **bài bứt phá so với chính kênh**
  → công thức trúng; format & hook kênh thắng bằng gì; bài tốt nhất vs kém nhất.
- *Thư viện bài* (lọc theo kênh) · *Nhịp đăng* (giờ đối thủ hay đăng).

**`video` — Video Teardown** (4 tab)
- *Mổ xẻ video*: giải phẫu Like/Save/Share/Comment theo **tỷ lệ so với P50** trên thang chung.
- *Voice of Customer*: từ khoá khán giả nhắc nhiều, bình luận top (gộp câu lặp, hiện `lặp N×`).
- *Ý tưởng từ bình luận*: câu hỏi khán giả → chủ đề có cầu sẵn; tín hiệu nỗi đau/mong muốn → angle.
- *Thư viện*.

Mọi lưới video đều có preview + modal xem nhanh + **nút nối n8n**
(📥 Tải · 🎙️ Voice→Text · 🧠 Phân tích ND · 🪝 Phân tích Hook), chọn nhiều để gửi loạt.

```bash
# Chuyên theo mode
python3 -m kit.dashboard search  data/douyin/search_x.xlsx data/xhs/search_x.xlsx
python3 -m kit.dashboard creator data/douyin/creator_x.xlsx
python3 -m kit.dashboard video   data/douyin/detail_x.xlsx      # cần sheet Comments

# Không chỉ định loại -> tự chọn theo mode cào trong dữ liệu
python3 -m kit.dashboard data/douyin/search_x.xlsx

# Sinh TẤT CẢ loại phù hợp + trang điều hướng dashboard_index.html
python3 -m kit.dashboard all data/douyin/*.xlsx data/xhs/*.xlsx \
    --n8n https://n8n.cua-ban.vn/webhook/mc-action
```

```python
from kit.dashboard import build_all, build_dashboard
build_dashboard(["data/douyin/search_x.xlsx"], profile="search")
build_all(["data/douyin/search_x.xlsx", "data/douyin/creator_x.xlsx"])
```

REST: `POST /kit/dashboard` với `{"files": [...], "profile": "search"}`
(`profile`: `auto` | `all` | `search` | `creator` | `video` | `overview`).

**Nối n8n:** bấm *⚙ Kết nối n8n* trên dashboard, dán URL webhook (lưu ở trình duyệt),
rồi import workflow **`n8n/WF_MC4_content_action.json`** — nó định tuyến theo `action`
(tải / bóc lời / phân tích ND / phân tích hook). Nhớ đặt credential Anthropic + endpoint
speech-to-text trong n8n, và bật CORS cho webhook nếu mở dashboard từ `file://`.

**Lưu ý số liệu:** bài trùng (cùng video cào ở nhiều từ khoá) được gộp theo
`(nền tảng, item_id)`; điểm trend và mức vượt trội chuẩn hoá **trong từng nền tảng**
vì thang tương tác giữa các nền tảng lệch rất xa; độ đều dùng thang tứ phân vị nên
một bài viral lẻ không làm sai lệch.

## Nối vào pipeline AI video (CS5)

```python
from prompts.angle_to_video_prompts import build_script_prompt, VIDEO_BRIEF_SCHEMA
# angle_library.jsonl -> concept -> build_script_prompt() -> Messages API
# -> Video Brief JSON (theo VIDEO_BRIEF_SCHEMA) -> AutoVid / FACTORY OS
```

## Tự động hoá (n8n)

Import 4 file trong `n8n/` (WF_MC1..MC3 tự động theo lịch; **WF_MC4** là webhook cho
nút hành động trên dashboard). Biến môi trường cần đặt trong n8n:
`ANTHROPIC_API_KEY`, `NOTIFY_WEBHOOK_URL`, `SUPABASE_URL`, `SUPABASE_KEY`.
Sửa đường dẫn `executeCommand` cho khớp máy chủ (mặc định `/opt/digiads/kit` và
`/opt/MediaCrawler/data`).

## Các module v2 (Tier 1 + Tier 2 — đã có)

| Module | Dùng khi | Lệnh/API |
|---|---|---|
| `enrich/` | Chuẩn hoá dữ liệu thô, velocity WoW, dịch ZH→VI | `from kit.enrich import normalize, weekly_velocity, translate_zh_vi` |
| `dashboard/` | 4 loại dashboard chuyên sâu theo mode cào | `python -m kit.dashboard [search\|creator\|video\|overview\|all] <file...>` |
| `storage/schema/` | Tạo kho Supabase (1 lần) | chạy `001` → `002` → `003` (xem `storage/README.md`) |
| `storage/supabase_writer.py` | Ghi kết quả analyzer lên Supabase | thêm cờ `--to supabase` (thử trước: `--dry-run`) |
| `storage/checkpoint.py` | Crawl tăng dần — lần 2 chỉ xử lý post mới | option `incremental` trong job queue |
| `pipeline/angle_to_brief.py` | Angle → Video Brief JSON cho AI video | `python kit/pipeline/angle_to_brief.py <angle.jsonl> --product "..." [--provider mock]` |
| `webhook/emit.py` | Bắn event sang n8n sau khi phân tích | thêm cờ `--notify` |
| `queue/` | Chạy nhiều ngách theo hàng đợi (cần Redis) | `arq kit.queue.worker.WorkerSettings` + `python kit/queue/enqueue.py dy search "kw" --analyze trend` |
| REST `/kit/*` | Gọi kit qua HTTP | `POST /kit/analyze`, `POST /kit/dashboard`, `GET /kit/reports/{name}`, `POST /kit/angle-brief` |

Ví dụ chuỗi đầy đủ Tier 1:

```bash
python kit/analyzer/mediacrawler_analyzer.py angle data/douyin/search_x.xlsx --to supabase
python kit/pipeline/angle_to_brief.py reports/angle_library.jsonl \
    --product "Serum kiềm dầu 199k, TikTok Shop" --notify
```

## Lộ trình nâng cấp

Tier 1 (đã có): ghi Supabase + enrichment + webhook n8n.
Tier 2 (đã có): hàng đợi arq + crawl tăng dần checkpoint.
Tier 3 (KHOÁ — cẩn trọng pháp lý): multi-account + proxy rotation, chỉ mở khi có
ghi chú "đã rà soát pháp lý" trong CLAUDE.md.
