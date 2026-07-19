# CHANGELOG

## v2.0.0 — 2026-07-19 · DigiAds Kit

Bản v2 tích hợp **DigiAds Kit** biến MediaCrawler thành cỗ máy nghiên cứu sáng tạo
(11 case study). Toàn bộ code mới nằm trong `kit/` — không phá base crawler.

### Thêm mới

- **kit/analyzer** — 1 file phân tích 11 case (trend, insight, koc, opportunity,
  seasonal, price, sov, angle) + cờ `--to supabase`, `--dry-run`, `--notify`.
- **kit/enrich** — lớp chuẩn hoá dùng chung: `normalize` (count Text → số,
  epoch s/ms → created_at + week ISO, engagement, tag format), `weekly_velocity`
  (đà tăng WoW), `translate_zh_vi` (dịch batch qua Claude, provider `none` offline).
- **kit/storage** — schema Supabase (`001_core.sql`: 6 bảng + RLS; `002_views.sql`:
  4 view dashboard; `003_checkpoints.sql`), `SupabaseWriter` upsert idempotent
  theo khoá tự nhiên, `checkpoint` crawl tăng dần (Supabase/SQLite fallback).
- **kit/pipeline** — `angle_to_brief.py`: angle_library.jsonl → Video Brief JSON
  qua chuỗi 6 prompt (normalize → concept → script → variation → compliance →
  scorecard), provider `claude`/`mock`, validate schema, xuất `out/briefs.jsonl`.
- **kit/queue** (Tier 2) — arq worker **tuần tự** (max_jobs=1, không tăng tải),
  task `crawl_and_analyze` gọi REST crawler → poll → analyzer → Supabase/webhook,
  CLI `enqueue.py`.
- **kit/webhook** — `emit()` bắn event sang n8n (retry 2 lần, nuốt lỗi mạng) +
  `notify_trend_brief` / `notify_rising_koc` / `notify_sov_updated`.
- **api/routers/kit.py** — REST: `POST /kit/analyze`, `GET /kit/reports/{name}`,
  `POST /kit/angle-brief` (pydantic validation, chặn path traversal).
- **tests/** — 60+ test synthetic mới (enrich, storage, pipeline, webhook, queue,
  checkpoint, api, analyzer 11 nhánh) — không gọi mạng thật.
- **CI** — GitHub Actions (`.github/workflows/ci.yml`): ruff + pytest trên push/PR;
  cấu hình `ruff.toml` phạm vi kit.
- **Tài liệu** — `docs/ARCHITECTURE.md`, `docs/DEPLOY.md`,
  `docs/HANDBOOK_11_case_studies.html`, `BUILD_GUIDE_ClaudeCode.md`, README v2.

### Thay đổi

- `kit/analyzer` refactor dùng chung logic chuẩn hoá từ `kit/enrich` (bỏ trùng lặp);
  ép stdout UTF-8 trên Windows.
- README gốc chuyển sang `docs/README_upstream.md` (giữ credit NanmiCoder).
- `.gitignore` thêm output kit (`kit/**/reports/`, `kit/pipeline/out/`).

### Ranh giới (không đổi)

- Chỉ nghiên cứu nội bộ dữ liệu công khai; concurrency = 1; creator ẩn danh
  (Nghị định 13/2023); license phi thương mại của repo gốc.
- Tier 3 (multi-account/proxy) **không có** trong bản này — chờ rà soát pháp lý.
