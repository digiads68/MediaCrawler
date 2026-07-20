# ARCHITECTURE — MediaCrawler × DigiAds Kit (v2)

> Tài liệu mô tả luồng dữ liệu end-to-end của bản v2. Đọc kèm `CLAUDE.md` (ranh giới)
> và `docs/HANDBOOK_11_case_studies.html` (nghiệp vụ 11 case).

## 1. Sơ đồ tổng quát

```
┌──────────────┐   REST API    ┌──────────────┐
│  WebUI React │ ────────────▶ │  api/ (Fast  │        MediaCrawler base
│  (webui/)    │               │  API :8080)  │──┐     (Playwright/CDP,
└──────────────┘               └──────────────┘  │      concurrency = 1)
                                                 ▼
                                        ┌────────────────┐
                                        │ media_platform/ │  crawl 7 nền tảng
                                        │ store/ → data/  │  → xlsx / jsonl / csv
                                        └────────┬───────┘
                                                 │
        ╔════════════════════════════ kit/ (DigiAds) ═══════════════════════════╗
        ║                                        ▼                              ║
        ║  kit/enrich/        chuẩn hoá count/thời gian, engagement, format,    ║
        ║  (normalize,        velocity WoW, dịch ZH→VI (Claude, batch)          ║
        ║   velocity,                            │                              ║
        ║   translate)                           ▼                              ║
        ║  kit/storage/       Supabase (schema SQL + supabase_writer upsert     ║
        ║  (schema/,          idempotent) — kho dữ liệu cho dashboard,          ║
        ║   supabase_writer,  checkpoint crawl tăng dần (Tier 2)                ║
        ║   checkpoint)                          │                              ║
        ║                                        ▼                              ║
        ║  kit/analyzer/      11 case: trend/insight/koc/opportunity/seasonal/  ║
        ║                     price/sov/angle → Excel reports/ + jsonl          ║
        ║                                        │                              ║
        ║                                        ▼                              ║
        ║  kit/pipeline/      angle_library.jsonl → chuỗi 6 prompt              ║
        ║  (+ kit/prompts/)   (normalize→concept→script→variation→compliance→   ║
        ║                     scorecard) → Video Brief JSON (AutoVid/FACTORY)   ║
        ║                                        │                              ║
        ║                                        ▼                              ║
        ║  kit/webhook/       emit event (trend_brief, rising_koc, sov_updated) ║
        ║                     → NOTIFY_WEBHOOK_URL (n8n)                        ║
        ║                                        │                              ║
        ║  kit/queue/ (Tier2) arq worker: crawl→enrich→store→analyze→notify     ║
        ║                     tuần tự, concurrency=1 ở tầng crawl               ║
        ╚═══════════════════════════════════════│═══════════════════════════════╝
                                                 ▼
                                        ┌────────────────┐
                                        │  n8n workflows  │  WF_MC1 tuần /
                                        │  (kit/n8n/)     │  WF_MC2 tháng /
                                        └────────────────┘  WF_MC3 2 tuần
```

Luồng chuẩn: **crawl → enrich → storage (Supabase) → analyzer → pipeline (AI video) → n8n**.

## 2. Thành phần hiện có (base + kit khởi điểm)

| Thành phần | Vị trí | Trạng thái |
|---|---|---|
| Crawler 7 nền tảng | `media_platform/`, `main.py` | Base — không sửa |
| REST API + WebSocket | `api/` (`uvicorn api.main:app --port 8080`) | Base fork — chỉ thêm router kit |
| WebUI React | `webui/` | Base fork |
| Analyzer 11 case | `kit/analyzer/mediacrawler_analyzer.py` | Có sẵn trong kit |
| Prompt chain AI video | `kit/prompts/angle_to_video_prompts.py` | Có sẵn trong kit |
| MCP server | `kit/mcp/mcp_mediacrawler.py` | Có sẵn trong kit |
| n8n workflows | `kit/n8n/*.json` (3 file) | Có sẵn trong kit |
| Templates Excel | `kit/templates/*.xlsx` (5 file) | Có sẵn trong kit |

## 3. Các hàm analyzer (map case study)

| Lệnh CLI | Hàm | Case | Output |
|---|---|---|---|
| `trend` | `trend_radar()` | CS1 + CS10 | `CS1_trend_top_posts.xlsx`, `CS1_trend_formats.xlsx`, `CS10_sound_watchlist.xlsx` |
| `insight` | `comment_bank()` | CS2 | `CS2_comment_bank.xlsx` |
| `koc` | `koc_scorecard()` | CS3 + CS9 | `CS3_koc_scorecard.xlsx`, `CS9_rising_creators.xlsx` |
| `opportunity` | `opportunity_map()` | CS4 + CS6 | `CS6_opportunity_map.xlsx` |
| `seasonal` | `seasonal_radar()` | CS7 | `CS7_seasonal_radar.xlsx` |
| `price` | `price_intel()` | CS8 | `CS8_price_intel.xlsx` |
| `sov` | `sov()` | CS11 | `CS11_sov_weekly.xlsx` |
| `angle` | `export_angles()` | CS5 | `angle_library.jsonl` |

Công thức lõi:

- `trend_score = (0.4·save + 0.3·share + 0.2·comment + 0.1·like) · 100` (chuẩn hoá max).
- KOC: `diem_tong = 0.40·eng_norm + 0.35·do_deu + 0.25·velocity_norm`;
  `do_deu = 1/(1+CV)`; `rising = velocity ≥ 1.3 và do_deu ≥ 0.4` (CS9).
- Opportunity: median-split `so_bai × save_tb` → 4 quadrant (biển xanh / cạnh tranh / sa mạc / bão hoà).
- SOV: gắn brand theo keyword trong title/desc → `% engagement theo tuần`.

## 4. Schema Angle & Video Brief

**Angle** (1 dòng `angle_library.jsonl`, dataclass `Angle` trong `kit/prompts/`):

```json
{"angle_id": "kw_123", "platform": "dy", "source_keyword": "护肤",
 "hook": "…", "format": "before-after", "pain_or_desire": "…",
 "cta_observed": "…", "sound_ref": "…",
 "metrics": {"like": 0, "comment": 0, "share": 0, "collect": 0}, "lang": "zh"}
```

**Video Brief** (đầu ra chuỗi prompt, `VIDEO_BRIEF_SCHEMA`): `concept_id`, `product_focus`,
`angle_type` (pain|desire|proof|curiosity|comparison|trend), `hook_line`, `duration_sec`
(15–20), `aspect_ratio` 9:16, `language` vi-VN, `scenes[]` (t_start/t_end/visual/
onscreen_text/voiceover), `cta`, `sound_ref`, `hashtags[]`, `source_angle_ids[]`,
`compliance_flags[]`.

Chuỗi 6 prompt (mỗi stage 1 hàm builder, trả `{system, user, model}` cho Messages API,
model mặc định `claude-sonnet-4-6`): `normalize → concept → script → variation →
compliance → scorecard`.

## 5. Biến môi trường

Xem `.env.example`: `ANTHROPIC_API_KEY`, `MEDIACRAWLER_API` (mặc định
`http://127.0.0.1:8080`), `SUPABASE_URL`, `SUPABASE_KEY`, `NOTIFY_WEBHOOK_URL`,
`REDIS_URL`, `TRANSLATE_PROVIDER` (tuỳ chọn).

## 6. Rủi ro & giả định

1. **Cột dữ liệu khác nhau giữa nền tảng** (vd `aweme_url` vs `note_url`,
   `liked_count` dạng text "1.2万"). Analyzer đã phòng thủ bằng `df.get(...)`;
   lớp enrich sẽ là nơi duy nhất chuẩn hoá.
2. **`create_time` khi thiếu** làm `seasonal`/`koc` giảm chất lượng (velocity cần
   thứ tự thời gian). Giả định: luôn bật thu thập thời gian đăng.
3. **Dịch ZH→VI tốn token** — bắt buộc batch và có provider `none` cho offline/test.
4. **Supabase dùng service_role key ở backend** — tuyệt đối không expose ra client;
   RLS bật mặc định trên mọi bảng.
5. **Ẩn danh creator** (`creator_hash`, nickname đã mask) phải giữ nguyên xuyên suốt
   enrich/storage — tuân thủ Nghị định 13/2023; không lưu PII thô.
6. **Tier 3 bị khoá** (multi-account/proxy/API-mode) cho tới khi có ghi chú rà soát
   pháp lý trong `CLAUDE.md`.
7. **Giới hạn tải**: mọi tầng gọi crawler (queue, n8n) giữ tuần tự, concurrency=1,
   không retry dồn dập.
