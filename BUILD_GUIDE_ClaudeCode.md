# 🛠️ BUILD GUIDE — Phát triển MediaCrawler × DigiAds Kit bằng Claude Code

Tài liệu này hướng dẫn **từng bước, cực chi tiết** để:

1. Dựng thư mục dự án ở máy local (gộp MediaCrawler gốc + DigiAds Kit).
2. Đặt đúng từng file vào đúng chỗ.
3. Dùng **chuỗi prompt Claude Code** để code nốt các phần còn lại (Tier 1 → Tier 2 → chất lượng).
4. Đẩy toàn bộ (tài liệu + code) lên **https://github.com/digiads68/MediaCrawler** thành bản v2.

> Đọc kèm `CLAUDE.md` (ranh giới & kiến trúc) — Claude Code sẽ tự đọc file này khi làm việc.

---

## PHẦN A — Chuẩn bị thư mục local

### A.1. Yêu cầu máy

- Python **3.11+**, `git`, `uv` (hoặc `pip`), **Node.js 18+** (cho WebUI, tùy chọn).
- **Claude Code** đã cài (`npm i -g @anthropic-ai/claude-code` hoặc bản desktop).
- Tài khoản: Anthropic API key, Supabase project, (tùy chọn) Redis.

### A.2. Lấy source gốc về

```bash
# Thư mục làm việc
mkdir -p ~/projects && cd ~/projects

# Clone repo của anh (đang là bản fork có API + WebUI)
git clone https://github.com/digiads68/MediaCrawler.git
cd MediaCrawler

# Tạo nhánh phát triển v2 (không code thẳng lên main)
git checkout -b feat/digiads-kit-v2
```

### A.3. Giải nén DigiAds Kit vào đúng chỗ

Giải nén `DigiAds_MediaCrawler_Kit.zip`. Bên trong là thư mục `DigiAds_MediaCrawler_Kit/`.
**Copy toàn bộ nội dung** của nó vào **thư mục `kit/` ở gốc repo**, đồng thời đưa `CLAUDE.md`
và `.env.example` ra **gốc repo**. Sơ đồ đích:

```
MediaCrawler/                         ← gốc repo
├── CLAUDE.md                         ← ĐƯA RA GỐC (từ kit)
├── .env.example                     ← ĐƯA RA GỐC (từ kit)
├── BUILD_GUIDE_ClaudeCode.md        ← file này, để ở gốc hoặc docs/
├── main.py  api/  webui/  ...        ← giữ nguyên của fork
└── kit/                              ← TẠO MỚI, chứa toàn bộ kit
    ├── README.md
    ├── analyzer/mediacrawler_analyzer.py
    ├── prompts/angle_to_video_prompts.py
    ├── mcp/mcp_mediacrawler.py
    ├── n8n/ (3 file .json)
    ├── templates/ (5 file .xlsx)
    └── config/brand_map.json
```

### A.4. Bảng đặt file (nguồn → đích)

| File trong gói kit | Đặt vào (trong repo) | Vai trò |
|---|---|---|
| `CLAUDE.md` | **`/CLAUDE.md`** (gốc) | Ngữ cảnh + ranh giới cho Claude Code |
| `.env.example` | **`/.env.example`** (gốc) | Mẫu biến môi trường |
| `BUILD_GUIDE_ClaudeCode.md` | `/` hoặc `/docs/` | Tài liệu này |
| `HANDBOOK_11_case_studies.html` | `/docs/` | Sổ tay 11 case (đọc bằng trình duyệt) |
| `README.md` | `/kit/README.md` | Giới thiệu kit |
| `analyzer/mediacrawler_analyzer.py` | `/kit/analyzer/` | Phân tích 11 case |
| `prompts/angle_to_video_prompts.py` | `/kit/prompts/` | Nối Angle → AI video |
| `mcp/mcp_mediacrawler.py` | `/kit/mcp/` | MCP server |
| `n8n/*.json` (3) | `/kit/n8n/` | Workflow tự động |
| `templates/*.xlsx` (5) | `/kit/templates/` | Mẫu output báo cáo |
| `config/brand_map.json` | `/kit/config/` | Rổ brand cho CS11 |

Lệnh gợi ý (chạy ở gốc repo, sau khi giải nén cạnh đó):

```bash
UNZIP=~/Downloads/DigiAds_MediaCrawler_Kit      # sửa cho đúng nơi anh giải nén
mkdir -p kit docs
cp -r "$UNZIP"/{analyzer,prompts,mcp,n8n,templates,config} kit/
cp "$UNZIP/README.md" kit/README.md
cp "$UNZIP/CLAUDE.md" ./CLAUDE.md
cp "$UNZIP/.env.example" ./.env.example
cp "$UNZIP/BUILD_GUIDE_ClaudeCode.md" ./BUILD_GUIDE_ClaudeCode.md
cp "$UNZIP/HANDBOOK_11_case_studies.html" docs/
```

### A.5. Cài đặt & chạy thử base

```bash
# Phụ thuộc gốc của MediaCrawler
uv sync            # hoặc: pip install -r requirements.txt

# Phụ thuộc thêm cho kit
pip install pandas openpyxl httpx "mcp[cli]" anthropic supabase arq python-dotenv

# Biến môi trường
cp .env.example .env     # rồi mở .env điền key thật

# Bật API crawler (terminal riêng)
uvicorn api.main:app --port 8080
```

Chạy thử analyzer với 1 file dữ liệu bất kỳ đã cào để chắc chắn kit hoạt động:

```bash
python3 kit/analyzer/mediacrawler_analyzer.py trend data/douyin/<file>.xlsx
```

### A.6. `.gitignore` — thêm các dòng sau (nếu chưa có)

```gitignore
.env
data/
kit/**/reports/
__pycache__/
*.pyc
.venv/
node_modules/
```

---

## PHẦN B — Phát triển bằng Claude Code

### B.1. Cách làm việc

1. Mở Claude Code **tại gốc repo**: `cd ~/projects/MediaCrawler && claude`.
2. Claude Code tự đọc `CLAUDE.md`. Nếu muốn chắc, gõ: *"Đọc CLAUDE.md và tóm tắt ranh giới dự án."*
3. **Dán từng PROMPT bên dưới theo thứ tự.** Mỗi prompt là một task khép kín, có tiêu chí
   nghiệm thu. Xong một prompt, review diff, commit, rồi mới sang prompt tiếp theo.
4. Nguyên tắc vàng: **một prompt = một module = một commit.** Không nhồi nhiều việc.

> Mỗi prompt đều nên bắt đầu bằng câu: *"Tuân thủ CLAUDE.md. "* — đã có sẵn trong các prompt dưới.

---

### 🟢 TIER 1 — Kho dữ liệu + Enrichment + Webhook (làm trước, ROI cao nhất)

#### PROMPT 0 — Khởi tạo & định hướng

```text
Tuân thủ CLAUDE.md. Đây là bản v2 của MediaCrawler đã tích hợp thư mục kit/ của DigiAds.
Nhiệm vụ khởi động:
1. Đọc CLAUDE.md, kit/README.md, kit/analyzer/mediacrawler_analyzer.py và
   kit/prompts/angle_to_video_prompts.py. Tóm tắt cho tôi: kiến trúc hiện tại, các hàm
   analyzer đang có, và schema Angle/Video Brief.
2. Kiểm tra .env.example đã đủ biến chưa (ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY,
   NOTIFY_WEBHOOK_URL, REDIS_URL, MEDIACRAWLER_API). Bổ sung nếu thiếu.
3. Tạo file docs/ARCHITECTURE.md mô tả luồng dữ liệu:
   crawl → enrich → storage(Supabase) → analyzer → pipeline(AI video) → n8n.
4. KHÔNG sửa base crawler. Chỉ đọc và tài liệu hoá. Liệt kê rủi ro/giả định nếu có.
```

#### PROMPT 1 — Schema Supabase (SQL migrations)

```text
Tuân thủ CLAUDE.md. Tạo lớp lưu trữ Supabase cho kit.
Tạo thư mục kit/storage/schema/ với các file SQL migration (đặt tên 001_, 002_...):

001_core.sql — các bảng:
  - crawl_runs(id, platform, crawler_type, keywords, started_at, finished_at, note_count, status)
  - trend_posts(id, run_id fk, platform, source_keyword, title, format, liked, comment,
      share, collect, created_at, url, trend_score, added_ts)  — dùng cho CS1/CS4/CS6/CS7
  - koc_scores(id, run_id fk, creator_hash, nickname_masked, so_video, eng_tb, do_deu,
      velocity, diem_tong, verdict, rising, updated_at)  — CS3/CS9
  - angle_library(id, angle_id unique, platform, source_keyword, hook, format,
      pain_or_desire, cta_observed, sound_ref, like, comment, share, collect, lang,
      status, created_at)  — CS5
  - sov_weekly(id, week, brand, so_bai, eng, sov_pct, updated_at, unique(week,brand))  — CS11
  - price_intel(id, run_id fk, competitor, price_text, promo_text, source_keyword, eng, created_at) — CS8

002_views.sql — view phục vụ dashboard:
  - v_trend_top: top post 30 ngày theo trend_score
  - v_sov_trend: %SOV theo tuần, kèm biến động WoW (LAG)
  - v_rising_koc: koc rising=true, sắp theo diem_tong
  - v_niche_quadrant: gom source_keyword -> volume vs save TB (median split) trả nhãn quadrant

Yêu cầu:
- Khoá chính uuid default gen_random_uuid(); index cho các cột lọc (week, brand, source_keyword, added_ts).
- Ghi chú RLS: mặc định bật RLS, cấp quyền qua service_role key (dùng ở backend). Thêm comment
  nhắc không expose service_role ra client.
- Thêm kit/storage/README.md hướng dẫn chạy migration (Supabase SQL editor hoặc supabase cli).
Nghiệm thu: SQL chạy không lỗi trên Postgres 15; nêu rõ thứ tự chạy file.
```

#### PROMPT 2 — Lớp enrichment

```text
Tuân thủ CLAUDE.md. Tạo lớp enrichment tại kit/enrich/ để "làm giàu" dữ liệu thô trước khi
phân tích/lưu. Các module:

kit/enrich/normalize.py
  - normalize_counts(df): ép các cột count từ Text -> số (đã có logic mẫu trong analyzer,
    tách ra dùng chung), parse create_time -> created_at + cột week (ISO).
  - add_engagement(df): eng_total, save_rate, share_rate.
  - tag_format(df): gắn nhãn format theo từ điển FORMAT_RULES (import từ analyzer, đừng lặp code).

kit/enrich/velocity.py
  - weekly_velocity(df, key): tính đà tăng WoW cho post/creator (nửa sau / nửa đầu).

kit/enrich/translate.py
  - translate_zh_vi(texts: list[str]) -> list[str]: dịch tiêu đề/hook ZH->VI.
    Mặc định dùng Claude (claude-sonnet-4-6) gọi qua anthropic client, gom batch để tiết kiệm.
    Có tham số provider="claude"|"none"; "none" trả nguyên văn (để chạy offline/test).
    KHÔNG gọi mạng trong test — cho phép inject client giả.

Refactor: analyzer.normalize() gọi lại kit/enrich/normalize.py để không trùng logic.
Thêm tests/test_enrich.py với dữ liệu synthetic (không gọi mạng).
Nghiệm thu: pytest -q pass; analyzer vẫn chạy như cũ (regression).
```

#### PROMPT 3 — Supabase writer + cờ `--to supabase`

```text
Tuân thủ CLAUDE.md. Tạo kit/storage/supabase_writer.py:
  - class SupabaseWriter đọc SUPABASE_URL/SUPABASE_KEY từ env (dùng thư viện supabase).
  - Các hàm upsert: upsert_trend_posts(df, run_id), upsert_koc(df, run_id),
    upsert_angles(records), upsert_sov(df), upsert_price(df, run_id), start_run()/finish_run().
  - Dùng upsert theo khoá tự nhiên (angle_id; (week,brand)) để idempotent, chạy lại không nhân đôi.
  - Batch insert theo lô ~500 dòng; bọc try/except, log tiếng Việt.

Tích hợp CLI analyzer: thêm cờ tùy chọn `--to supabase` cho các lệnh trend/koc/angle/sov/price.
Khi có cờ này: sau khi tính xong, ghi thẳng vào Supabase (ngoài việc xuất Excel).
Khi không có cờ: giữ nguyên hành vi cũ (chỉ Excel/JSONL).

Thêm chế độ dry-run (--dry-run) in ra số dòng sẽ ghi mà không gọi mạng, để test.
tests/test_storage.py: test build payload + dry-run (mock client).
Nghiệm thu: `... trend file.xlsx --to supabase --dry-run` in đúng số dòng; pytest pass.
```

#### PROMPT 4 — Pipeline Angle → Video Brief (nối AI video)

```text
Tuân thủ CLAUDE.md. Tạo kit/pipeline/angle_to_brief.py — biến angle_library.jsonl thành
Video Brief JSON dùng chuỗi prompt trong kit/prompts/angle_to_video_prompts.py.

Yêu cầu:
  - Hàm run(angle_jsonl, product_brief, limit=10, provider="claude"|"mock").
  - Với mỗi angle: normalize (nếu thiếu pain/desire) -> concept -> script -> (tùy chọn)
    variation, compliance, scorecard. Gọi Anthropic Messages API (claude-sonnet-4-6),
    parse JSON trả về, validate theo VIDEO_BRIEF_SCHEMA. Bản ghi lỗi -> log & bỏ qua, không crash.
  - provider="mock": không gọi mạng, trả brief mẫu hợp lệ (để test & demo offline).
  - Xuất kit/pipeline/out/briefs.jsonl (mỗi dòng 1 Video Brief) + tóm tắt scorecard.
  - CLI: python3 kit/pipeline/angle_to_brief.py <angle.jsonl> --product "..." [--provider mock]

tests/test_pipeline.py chạy provider=mock trên 2 angle mẫu, assert brief đúng schema.
Nghiệm thu: chạy mock ra briefs.jsonl hợp lệ; pytest pass.
```

#### PROMPT 5 — Webhook emitter → n8n

```text
Tuân thủ CLAUDE.md. Tạo kit/webhook/emit.py:
  - emit(event: str, payload: dict): POST tới NOTIFY_WEBHOOK_URL (httpx), timeout ngắn,
    retry 2 lần, nuốt lỗi mạng (chỉ log) để không làm hỏng job chính.
  - Hàm tiện ích: notify_trend_brief(text), notify_rising_koc(list), notify_sov_updated().
Tích hợp: sau khi analyzer/pipeline hoàn tất (khi chạy có cờ --notify), gọi emit tương ứng.
tests/test_webhook.py: mock httpx, assert payload đúng, assert lỗi mạng không raise.
Nghiệm thu: pytest pass; thử --notify với URL test (requestbin) thấy nhận payload.
```

---

### 🟡 TIER 2 — Hàng đợi job + Crawl tăng dần (khi cần chạy nhiều ngách)

#### PROMPT 6 — Hàng đợi arq

```text
Tuân thủ CLAUDE.md. Tạo hàng đợi job bằng arq (tái dùng pattern từ AutoVid) tại kit/queue/:
  - worker.py: cấu hình arq WorkerSettings, đọc REDIS_URL.
  - tasks.py: task crawl_and_analyze(ctx, platform, crawler_type, keywords, options) —
    gọi REST API crawler (http://127.0.0.1:8080), poll status tới khi idle, chạy analyzer,
    (tùy chọn) ghi Supabase + emit webhook. Giữ concurrency=1 ở tầng crawl (tôn trọng ranh giới).
  - enqueue.py: CLI để đẩy job vào hàng đợi.
Không tự tăng tải crawler. Job chạy tuần tự, có timeout & log tiếng Việt.
tests/test_tasks.py: test lắp payload & luồng (mock REST + analyzer).
Nghiệm thu: chạy worker + enqueue 1 job (dùng REST mock) chạy hết luồng; pytest pass.
```

#### PROMPT 7 — Crawl tăng dần / resume

```text
Tuân thủ CLAUDE.md. Thêm cơ chế crawl tăng dần để monitoring định kỳ rẻ hơn (KHÔNG tăng tải):
  - kit/storage/checkpoint.py: lưu/đọc "post id đã thấy" và max(added_ts) theo (platform, keyword)
    trong Supabase (bảng crawl_checkpoints) hoặc SQLite fallback.
  - Trong tasks/analyzer: sau khi cào, lọc bỏ post đã có (dedup theo id), chỉ xử lý post mới,
    rồi cập nhật checkpoint.
Mục tiêu: lần chạy thứ 2 trên cùng keyword xử lý ÍT dòng hơn lần đầu.
tests/test_checkpoint.py với SQLite tạm.
Nghiệm thu: test chứng minh lần 2 skip post cũ; pytest pass.
```

---

### 🔵 CHẤT LƯỢNG — API, Test, CI, Tài liệu, Release

#### PROMPT 8 — Endpoint kit trong FastAPI

```text
Tuân thủ CLAUDE.md. Mở rộng api/ (KHÔNG phá endpoint cũ) thêm router kit tại api/routers/kit.py:
  - POST /kit/analyze  {command, file|run_id, to_supabase?, notify?} -> chạy analyzer tương ứng
  - GET  /kit/reports/{name} -> tải file Excel output
  - POST /kit/angle-brief {angle_jsonl, product, provider} -> chạy pipeline, trả briefs
Đăng ký router trong api/main.py. Có validation (pydantic), xử lý lỗi trả JSON rõ ràng.
tests/test_api_kit.py dùng TestClient (mock lớp nặng).
Nghiệm thu: /docs (OpenAPI) hiện endpoint mới; pytest pass.
```

#### PROMPT 9 — Test suite + CI

```text
Tuân thủ CLAUDE.md. Củng cố chất lượng:
  - tests/conftest.py: fixture sinh DataFrame synthetic giống output MediaCrawler
    (title/desc ZH, count Text, create_time epoch, creator_hash...).
  - tests/test_analyzer.py: test cả 11 nhánh (trend/insight/koc/opportunity/seasonal/price/sov/angle),
    assert cột & logic (vd verdict KOC, quadrant, %SOV).
  - .github/workflows/ci.yml: chạy trên push/PR — cài deps, ruff check, pytest -q.
  - pyproject.toml hoặc ruff.toml: cấu hình ruff/black.
Nghiệm thu: `pytest -q` xanh local; CI file hợp lệ (yaml lint).
```

#### PROMPT 10 — Tài liệu & phát hành v2

```text
Tuân thủ CLAUDE.md. Hoàn thiện tài liệu và chuẩn bị release:
  1. Viết lại README.md ở gốc repo: giới thiệu bản v2 (MediaCrawler + DigiAds Kit),
     sơ đồ kiến trúc, quick start, link docs/HANDBOOK_11_case_studies.html và docs/ARCHITECTURE.md.
     Ghi rõ mục "Chỉ dùng nghiên cứu nội bộ dữ liệu công khai; tuân thủ ToS & Nghị định 13/2023".
  2. Bổ sung mục "Credits": fork từ NanmiCoder/MediaCrawler, giữ license gốc.
  3. Tạo CHANGELOG.md: liệt kê phần thêm (kit, enrich, storage, pipeline, queue, api/kit, tests, CI).
  4. Tạo docs/DEPLOY.md: cách deploy trên server (Azure 172.188.242.245): systemd cho API,
     arq worker, biến môi trường, cron/n8n.
  5. Kiểm tra không có secret nào lọt vào repo (grep key). Cập nhật .gitignore.
Nghiệm thu: README render đẹp trên GitHub; không còn TODO trống; không lộ secret.
```

---

## PHẦN C — Đẩy lên GitHub (v2)

Sau khi các prompt chạy xong và test xanh:

```bash
# 1. Kiểm tra không lộ secret
git status
grep -rIn "sk-ant\|service_role\|SUPABASE_KEY=ey" --exclude-dir=.git . || echo "OK, sạch"

# 2. Commit theo từng phần (nếu chưa commit lẻ trong lúc làm)
git add .
git commit -m "feat(kit): tích hợp DigiAds Kit v2 (analyzer 11 case, enrich, storage, pipeline, queue, api, tests, CI)"

# 3. Đẩy nhánh lên
git push -u origin feat/digiads-kit-v2

# 4. Mở Pull Request trên GitHub: feat/digiads-kit-v2 -> main, review rồi merge.
#    (Hoặc nếu muốn push thẳng main:)
# git checkout main && git merge feat/digiads-kit-v2 && git push origin main

# 5. Gắn tag phát hành
git tag -a v2.0.0 -m "DigiAds Kit v2: research & creative engine"
git push origin v2.0.0
```

> Mẹo: bật branch protection cho `main`, yêu cầu CI xanh trước khi merge.

---

## PHẦN D — Thứ tự khuyến nghị & mốc kiểm tra

| Bước | Prompt | Kết quả kỳ vọng | Commit |
|---|---|---|---|
| 1 | 0 | ARCHITECTURE.md, .env.example đủ biến | `docs: architecture` |
| 2 | 1 | Schema SQL chạy được trên Supabase | `feat(storage): schema` |
| 3 | 2 | Lớp enrich + test pass | `feat(enrich): normalize/velocity/translate` |
| 4 | 3 | Ghi Supabase (dry-run OK) | `feat(storage): supabase writer` |
| 5 | 4 | briefs.jsonl từ mock | `feat(pipeline): angle->brief` |
| 6 | 5 | Webhook bắn được | `feat(webhook): emit` |
| 7 | 6–7 | arq + incremental | `feat(queue): arq + checkpoint` |
| 8 | 8 | Endpoint /kit/* | `feat(api): kit router` |
| 9 | 9 | pytest xanh + CI | `test+ci: coverage` |
| 10 | 10 | README v2 + tag | `docs: v2 release` |

**Chốt Tier 1 = xong bước 6.** Lúc đó anh đã có: dữ liệu vào Supabase, dashboard nền,
pipeline AI video chạy được, và tự động hoá qua n8n. Tier 2 (bước 7) làm khi cần chạy
nhiều ngách. Tier 3 (multi-account/proxy) **không nằm trong guide này** — chỉ mở khi có
rà soát pháp lý, và phải cập nhật CLAUDE.md trước.

---

## PHẦN E — Nhắc nhở an toàn (đọc trước khi public repo)

- Repo **public** → tuyệt đối không commit `.env`, key, cookie đăng nhập, dữ liệu cá nhân đã cào.
- Giữ nguyên tinh thần **fork học tập/nghiên cứu**; ghi rõ license gốc & credit NanmiCoder.
- Dữ liệu cào để trong `data/` đã bị `.gitignore` — đừng đẩy dữ liệu thật lên GitHub.
- Mọi tính năng "scale mạnh" (Tier 3) cần gate pháp lý; Claude Code đã được dặn từ chối nếu
  chưa có ghi chú duyệt trong CLAUDE.md.
