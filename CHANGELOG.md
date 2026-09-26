# CHANGELOG

## Report đợt 2 — 2026-09-25

- **Creator Audit** (thay KOC Scorecard, lệnh `koc`): 1 kênh → soi sâu nhịp đăng, quỹ đạo theo quý
  (loại video < 30 ngày tuổi), tỷ lệ hit, trụ nội dung (Làm thêm / Giữ / Giảm), lịch đăng, lưới thẻ
  đủ video; nhiều kênh → bảng điểm KOC + chọn kênh để xem sâu. `kit/analyzer/creator_audit.py`.
- **Conversation Pulse** trong Voice of Customer: độ phủ mẫu bình luận (tự ghép file bài cùng
  phiên), thời gian bình luận đến, bài kéo thảo luận, câu hỏi của khách. `kit/analyzer/conversation.py`.
- **Structure & Hashtag Kit** (đổi tên Sound & Edit Kit): bảng hashtag + cặp tag hay đi cùng.
  Fix kệ tư liệu hiện 0 like.
- **Opportunity Map**: thêm trục "độ khó vào" (số creator, top 3 chiếm %, HHI).
- Bỏ nhánh `claude/social-media-analytics-dashboard-mto92x` theo quyết định chủ dự án.

## Report đợt 1 — 2026-09-25

- **Trend Radar làm lại:** khung Kết luận + 3 việc nên làm, KPI có chip trạng thái, bằng
  chứng (mục tiêu nội dung, tuổi bài, hashtag), lưới thẻ đủ mọi bài có phân trang. Giữ
  nguyên preview, ▶ Xem, ⬇ Tải, Copy hook và bộ lọc cũ; thêm lọc từ khoá / mục tiêu / tuổi,
  sắp theo mới đăng. Module mới `kit/analyzer/insights.py`.
- **Bỏ mọi giới hạn dòng:** Trend 20, Hook 40, Sound 30, Moodboard 120, Comment Bank 800,
  bảng HTML 15–60 dòng. Excel đủ dòng.
- **Điểm trend theo thứ hạng %** thay cho chia max (1 bài viral từng ép mọi bài về ~0).
- **Ô Nhận xét tổng quan** ở mọi report, chuẩn bị chỗ cho LLM (xem kit/README.md).
- **Giao diện mới** cho mọi report: màu cố định theo chỉ số, chip trạng thái, font Be Vietnam Pro.
- Fix: mọi file **JSON** mất trục thời gian (`read_json` tự đổi `create_time` → NaT) làm
  sai KOC / Seasonal / SoV / tuổi bài.
- Fix: file **bình luận** bị bỏ trùng theo id bài → mất ~90% bình luận (3.588 → 362).
  Nay theo `comment_id` (VoC: 273 → 2.330 bình luận dùng được).
- Fix: `Page.goto` timeout ở trang chủ (Douyin/XHS/Bilibili/Weibo/Kuaishou) — `tools/page_nav.py`.

## Sửa độ chính xác tìm kiếm Douyin — 2026-09-25

- **Từ khoá rỗng → âm thầm dùng từ khoá mặc định.** Ô KEYWORDS chỉ nhận khi nhấn Enter;
  bấm Initiate Scan khi chưa Enter thì crawler cào `编程副业,编程兼职` của config.
  Nay WebUI tự thêm chữ đang gõ (blur/dấu phẩy), chặn Start khi rỗng; API `/api/crawler/start`
  trả 400 nếu search không có từ khoá (áp cho cả MCP).
- **Phân trang Douyin sai.** Chỉ chạy 1 trang/từ khoá khi MAX=15; `count=15` nhưng offset bước
  10 → trang chồng 5 bài (nguồn dòng trùng 20–29%). Nay theo `cursor`/`has_more` như web
  (đo thật 2026-09: `normal_search`, `list_type=single`, `count=10`), bỏ trùng, dừng đúng số bài.
- WebUI thêm ô **MAX_POSTS / KEYWORD** (mặc định 15, tối đa 500).
- Kiểm chứng `#aigc`: 30/30 bài, 0 trùng; khớp 19/30 với trang web (top 10: 8/10) — phần lệch
  do Douyin cá nhân hoá/xếp lại kết quả mỗi phiên tìm kiếm.

## Đồng bộ upstream — 2026-09-25

Cập nhật base crawler từ [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)
`e6e863a` (2026-07-25) → `380b426` (2026-09-19). Code `kit/` không đổi.

- **Tải media viết lại** (`media_downloader/`, `media_platform/*/media.py`) cho
  xhs/dy/ks/bili/wb; bỏ các `store/*/*_store_media.py` cũ. Cờ CLI mới `--get_media`.
  Bilibili tải DASH chất lượng cao nếu máy có **ffmpeg** (không có thì tự hạ mp4).
- Fix: dy (header `x-tt-argus`, tham số `uifid/verifyFp`), ks (link rút gọn `/f/<token>`,
  video bị gỡ làm crash, giới hạn tần suất), bili (xác định đăng nhập, bình luận ghim),
  xhs (phân loại lỗi, video chỉ tải được ảnh bìa), weibo (lệch múi giờ 8 tiếng).
- `xhshow>=0.2.0` — bỏ monkey-patch ký GET (trùng bản vá local trước đó).
- Giữ các sửa local: `download_url` của Bilibili (nay xin `MP4_FNVAL` vì mặc định
  mới là DASH, không có `durl`), `exit_code`/`error_message` của CrawlerManager,
  `XHS_INTERNATIONAL=True`.
- `start.bat`: build lại WebUI khi mã nguồn `webui/` mới hơn bản build; kiểm tra ffmpeg
  (chỉ cảnh báo, không tự cài).

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
