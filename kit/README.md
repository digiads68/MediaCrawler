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
├── prompts/
│   └── angle_to_video_prompts.py   # Nối Angle Library → pipeline AI video
├── mcp/
│   └── mcp_mediacrawler.py         # MCP server cho AI agent gọi crawler
├── n8n/
│   ├── WF_MC1_trend_brief_weekly.json     # CS1+CS10+CS5 tự động (tuần)
│   ├── WF_MC2_sov_monitor_monthly.json    # CS11 tự động (tháng)
│   └── WF_MC3_rising_koc_alert.json        # CS9 tự động (2 tuần)
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

Ví dụ:
```bash
python3 analyzer/mediacrawler_analyzer.py trend  data/douyin/search_护肤.xlsx
python3 analyzer/mediacrawler_analyzer.py koc    data/douyin/creator_x.xlsx
python3 analyzer/mediacrawler_analyzer.py sov    data/douyin/search_x.xlsx config/brand_map.json
```

## Nối vào pipeline AI video (CS5)

```python
from prompts.angle_to_video_prompts import build_script_prompt, VIDEO_BRIEF_SCHEMA
# angle_library.jsonl -> concept -> build_script_prompt() -> Messages API
# -> Video Brief JSON (theo VIDEO_BRIEF_SCHEMA) -> AutoVid / FACTORY OS
```

## Tự động hoá (n8n)

Import 3 file trong `n8n/`. Biến môi trường cần đặt trong n8n:
`ANTHROPIC_API_KEY`, `NOTIFY_WEBHOOK_URL`, `SUPABASE_URL`, `SUPABASE_KEY`.
Sửa đường dẫn `executeCommand` cho khớp máy chủ (mặc định `/opt/digiads/kit` và
`/opt/MediaCrawler/data`).

## Lộ trình nâng cấp

Tier 1 (làm ngay, rủi ro thấp): ghi Supabase + enrichment + webhook n8n.
Tier 2: hàng đợi arq + crawl tăng dần + lịch tự động.
Tier 3 (cẩn trọng pháp lý): multi-account + proxy rotation.
