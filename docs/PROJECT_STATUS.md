# Trạng thái dự án & lộ trình — dành cho AI coding tiếp nối

> Viết cho **AI coding assistant** (Claude Code, Cursor, Copilot, Codex, Gemini CLI…) mở lại
> dự án ở một session/tool khác. Mục tiêu: đọc xong file này, biết ngay đã làm gì, vì sao
> làm vậy, còn thiếu gì, và các "hố" đã rơi vào để không mất công dò lại. Đọc
> [AGENTS.md](../AGENTS.md) trước nếu chưa đọc.

## 1. Mục tiêu dự án

**Chủ dự án** (agency DigiAds, thị trường Việt Nam — TikTok Shop/livestream) fork
[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) (NanmiCoder — crawler dữ liệu
**công khai** từ 7 nền tảng Trung Quốc: Xiaohongshu, Douyin, Kuaishou, Bilibili, Weibo,
Tieba, Zhihu) và bổ sung thư mục `kit/` để biến nó thành **cỗ máy nghiên cứu sáng tạo**:
biến dữ liệu thô crawl được thành 11 case study có số liệu (trend radar, voice-of-customer,
thẩm định KOC, săn ngách sản phẩm, angle library nạp AI video, seasonal, price intel,
rising KOC, sound watchlist, share-of-voice), tự động hoá báo cáo qua n8n/webhook, và nối
sang pipeline sinh kịch bản video AI (Anthropic Claude) cho team Content.

**Không phải mục tiêu:** không xây tính năng thương mại hoá dữ liệu, không mở rộng thành
crawler quy mô lớn (Tier 3 — multi-account/proxy — đang khoá chờ rà soát pháp lý), không
thay thế MediaCrawler gốc (chỉ mở rộng qua `kit/`).

Ranh giới pháp lý/đạo đức đầy đủ: **[CLAUDE.md](../CLAUDE.md)** — coi là bất biến.

## 2. Dòng thời gian đã làm (theo commit thật, nhánh `main`)

Toàn bộ việc dưới đây làm trong 1 chuỗi phiên Claude Code (tháng 7/2026), theo đúng thứ tự
`BUILD_GUIDE_ClaudeCode.md` đề ra (Tier 1 → Tier 2 → chất lượng → docs → packaging), merge
qua 2 PR:

**PR #1 — `feat/digiads-kit-v2` (khung DigiAds Kit v2, Tier 1+2+chất lượng):**
| Commit | Nội dung |
|---|---|
| `0ce7787` | Tích hợp khung kit gốc: analyzer 11 case, prompts, mcp, n8n, templates, config |
| `0442dcf` | `docs/ARCHITECTURE.md` |
| `1005d74` | Schema Supabase — 6 bảng + 4 view + RLS |
| `a41a54b` | `kit/enrich` — normalize/velocity/translate, analyzer refactor dùng chung |
| `61a4660` | `kit/storage/supabase_writer.py` — upsert idempotent, cờ `--to supabase`/`--dry-run` |
| `c1cc173` | `kit/pipeline/angle_to_brief.py` — chuỗi 6 stage, provider claude/mock |
| `1154c4b` | `kit/webhook/emit.py` — retry, cờ `--notify` |
| `74c2573` | `kit/queue` — arq worker tuần tự (`max_jobs=1`), CLI enqueue |
| `60f157b` | `kit/storage/checkpoint.py` — crawl tăng dần (SQLite/Supabase fallback) |
| `0efd136` | `api/routers/kit.py` — `/kit/analyze`, `/kit/reports/{name}`, `/kit/angle-brief` |
| `53aa771` | Test suite đầy đủ (fixture synthetic) + `ruff.toml` + CI GitHub Actions |
| `2396886` | README v2, CHANGELOG, `docs/DEPLOY.md` |
| `3099817` | **fix quan trọng**: pin `starlette==0.37.2`, gộp cài dependencies 1 lệnh (xem §5.2) |
| `cb45b46` | Squash-merge PR #1 vào `main`, tag `v2.0.0` |

**PR #2 — `feat/local-launcher-tailscale` (đóng gói chạy local + truy cập từ xa):**
| Commit | Nội dung |
|---|---|
| `2e33bce` | `start.bat`/`start_browser_cdp.bat` — launcher Windows tự cài đặt, bind `0.0.0.0` cho Tailscale |
| `4026391` | Squash-merge PR #2 vào `main` |

**Sau đó (chưa qua PR — commit tiếp trên `main`):**
- `docs/HUONG_DAN_SU_DUNG.md` — tài liệu nghiệp vụ theo bộ phận (marketing/content/sales/CSKH)
  + 2 dashboard mockup minh hoạ (`docs/dashboard-mockups/`).
- File này + `AGENTS.md` (đang thêm).

**Phiên 25/09/2026** (chi tiết đầy đủ: [`HANDOFF.md`](../HANDOFF.md)):
| Commit | Nội dung |
|---|---|
| `6c032b8` | Đồng bộ upstream NanmiCoder `e6e863a` → `380b426`; merge có cha thứ 2 `upstream/main` (lần sau chỉ cần `git merge upstream/main`) |
| `d898424` | Các thay đổi local trước phiên: `kit/enrich/schema.py`, `analyzer/registry.py`, `capabilities.py`, `media_urls.py`, `crawler_manager` báo `exit_code` |
| `a523d35` | Cổng MCP HTTP 8765 → 8790 (tránh exllm bridge của vidauto) |
| `5fd4d26` | Phân trang tìm kiếm Douyin, chặn từ khoá rỗng, `tools/page_nav.py`, `start.bat` chống chạy trùng, **report đợt 1** (`kit/analyzer/insights.py`, Trend Radar 3 tầng, đủ dữ liệu, ô nhận xét), sửa lỗi JSON mất ngày + bình luận mất 90% |

**Chưa qua tay session này (từ zip gốc, chưa kiểm chứng):** `kit/mcp/mcp_mediacrawler.py`,
`kit/n8n/*.json` (nội dung workflow đã review khi viết docs, nhưng chưa import/test thật
trong n8n), 5 file `kit/templates/*.xlsx`.

## 3. Trạng thái hiện tại — theo module

| Module | Code | Test | Tích hợp | Lưu ý |
|---|---|---|---|---|
| `kit/analyzer` | ✅ | ✅ (11 nhánh, `test_analyzer.py`) | CLI + `/kit/analyze` | Refactor dùng `kit/enrich` chung |
| `kit/enrich` | ✅ | ✅ `test_enrich.py` | Dùng bởi analyzer | `translate_zh_vi` cần `ANTHROPIC_API_KEY` khi provider=claude |
| `kit/storage` (schema/writer/checkpoint) | ✅ | ✅ `test_storage.py`, `test_checkpoint.py` | Cờ `--to supabase` | Schema **chưa deploy** lên Supabase thật nào — chỉ có SQL sẵn |
| `kit/pipeline` | ✅ | ✅ `test_pipeline.py` | CLI + `/kit/angle-brief` | provider=claude chưa chạy thật với API key thật trong session này |
| `kit/analyzer/insights.py` | ✅ (09/2026) | ✅ `test_insights.py` | Gọi từ `trend_radar` | Kết luận/bằng chứng Trend Radar; luật + ngưỡng ở đầu file |
| `kit/report` | ✅ (làm lại 09/2026) | ✅ `test_report.py`, `test_report_full_data.py` | Gọi từ `_run_analyzer`, phục vụ qua `/kit/reports/{name}` | **Mới**: sinh báo cáo HTML tự chứa (donut/hbar/line SVG server-side, link video, palette dataviz đã validate). Đã chạy thật trên data douyin + verify UI end-to-end |
| `kit/webhook` | ✅ | ✅ `test_webhook.py` | Cờ `--notify` | Chưa test với `NOTIFY_WEBHOOK_URL` thật (n8n) |
| `kit/queue` (arq) | ✅ | ✅ `test_tasks.py` | CLI enqueue + worker | **Chưa chạy thật với Redis** — chỉ test bằng mock |
| `api/routers/kit.py` | ✅ | ✅ `test_api_kit.py` | Mount trong `api/main.py` | Đã xác nhận hiện đúng trong OpenAPI `/docs` |
| `start.bat` / `start_browser_cdp.bat` | ✅ | Chạy thật, không phải pytest | — | Đã chạy thật từ đầu-đến-cuối trên máy dev (§5.4) |
| `kit/mcp/mcp_mediacrawler.py` | ✅ (đã mở rộng) | Smoke test thủ công (import + gọi thật qua REST) | stdio (local) + streamable-http (Tailscale) | **Đã kiểm chứng + nâng cấp**: thêm tool `analyze`/`list_reports`/`read_report`, nạp `.env`, chọn transport qua env. Kèm `setup_mcp.bat` (sinh `.mcp.json` portable), `start_mcp.bat` (HTTP cho Tailscale), `kit/mcp/README.md`. Xem §5.10 |
| `kit/n8n/*.json` (3 workflow) | Từ zip gốc | — | Chưa import n8n thật | Đã đọc hiểu nội dung khi viết docs, lịch mặc định tuần/tháng, xem §6 |
| `kit/templates/*.xlsx` (5 mẫu) | Từ zip gốc, có công thức sống thật | — | **Chưa auto-fill** | Xem §5.5 — điền tay, không có script nối |
| Base crawler (`media_platform/`, `api/routers/crawler.py`…) | **Có sửa (09/2026)**: đồng bộ upstream, phân trang Douyin, `goto_resilient`, chặn từ khoá rỗng — xem HANDOFF.md §1–2 | Test gốc của repo | — | 6 test trong `test/` (không phải `tests/`) fail vì cần Redis/proxy thật — **có sẵn từ trước fork, không phải do kit** |

**Chạy để tự kiểm tra:** `pytest tests -q` (không phải `pytest -q` — thư mục `test/` là
legacy của repo gốc, cần hạ tầng riêng, CI cũng chỉ chạy `tests/`).

## 4. Quyết định kỹ thuật quan trọng & lý do

Đọc mục này **trước khi** đổi lại các quyết định dưới — mỗi cái đều có lý do cụ thể từ
việc chạy thật, không phải chọn tuỳ ý.

- **`kit/analyzer` KHÔNG tự viết lại COUNT_COLS/FORMAT_RULES/normalize** — import từ
  `kit/enrich/normalize.py`. Lý do: tránh 2 nguồn sự thật (ban đầu bị trùng lặp, đã refactor).
- **`SupabaseWriter`/`CheckpointStore` nhận `client` qua constructor** (không tự tạo bên
  trong hàm) — để test không cần Supabase thật, dùng mock client.
- **Webhook (`kit/webhook/emit.py`) nuốt lỗi mạng, không raise** — vì nó chạy trong pipeline
  tự động (arq/n8n), lỗi thông báo phụ không được làm hỏng job chính (crawl/phân tích).
- **arq worker `max_jobs=1`, `max_tries=1`** cố định — đúng ranh giới "không tăng tải
  crawler"; đừng tăng để "chạy nhanh hơn" dù có yêu cầu.
- **`api/routers/kit.py` chặn path traversal** (`_resolve_in_project`) — endpoint nhận
  đường dẫn file từ request, phải ép nằm trong `PROJECT_ROOT`.
- **CI cài dependencies trong 1 lệnh `pip install` duy nhất** (không tách `requirements.txt`
  và gói kit thành 2 lệnh) — xem lý do kỹ thuật ở §5.2, đừng tách lại.
- **`start.bat`/`start_browser_cdp.bat` dùng `goto`/label, tránh `if (...) else (...)`
  lồng nhiều tầng** — xem lý do ở §5.3.
- **WebUI dùng đường dẫn tương đối (`/api`, `window.location.host`)** — không hardcode
  `localhost` — nhờ vậy truy cập qua Tailscale IP hoạt động không cần sửa code frontend.

## 5. Vấn đề môi trường đã gặp & cách đã xử lý

Đây là phần **tốn công nhất** để dò ra trong các session trước — đọc kỹ để không lặp lại.

### 5.1. `uv run` tự tải Python riêng + sync mirror Tsinghua → lỗi TLS

`pyproject.toml` khai `requires-python >=3.11` và 1 mirror PyPI Trung Quốc
(`pypi.tuna.tsinghua.edu.cn`). Trên máy dev, `uv run python main.py ...` (lệnh mà
`api/services/crawler_manager.py` dùng để khởi động crawl thật) mặc định cố **tải riêng 1
bản Python 3.11** và **sync lại toàn bộ dependency từ mirror đó** — cả hai đều timeout vì
lỗi chứng chỉ TLS trên máy dev (môi trường có chặn/can thiệp TLS tới nhiều host ngoài).

**Đã xử lý:** đặt 2 biến môi trường trước khi gọi `uv run`:
```
UV_PYTHON_DOWNLOADS=never   # bắt dùng Python đã có sẵn, không tự tải
UV_NO_SYNC=1                 # dùng .venv đã có sẵn as-is, không sync lại dependency
```
`start.bat` đã set 2 biến này trước khi chạy `uvicorn` — subprocess con (`uv run`) kế thừa
qua `env={**os.environ, ...}` trong `crawler_manager.py`. **Nếu port sang máy/CI khác vẫn
gặp lỗi tương tự, set lại 2 biến này trước, đừng nghi ngờ code Python.**

### 5.2. `pip install` 2 lệnh riêng → pip âm thầm nâng `starlette` vỡ tương thích `fastapi`

CI ban đầu chạy `pip install -r requirements.txt` rồi `pip install anthropic supabase arq
mcp[cli] ruff` ở **lệnh riêng**. Lệnh sau khiến pip nâng `starlette` lên bản đã bỏ tham số
`on_startup` khỏi `Router.__init__` (Starlette đổi API), vỡ `fastapi==0.110.2` (routers gốc
dùng `APIRouter(..., on_startup=...)`) → `TypeError` khi import `api/routers/__init__.py`.

**Đã xử lý:** pin `starlette==0.37.2` trong `requirements.txt` + gộp cài **1 lệnh pip duy
nhất** (`requirements.txt` + tất cả gói kit) trong `.github/workflows/ci.yml` và mọi hướng
dẫn cài đặt — để pip giải ràng buộc của TẤT CẢ gói cùng lúc. **Đừng tách lại thành 2 lệnh.**

### 5.3. Batch (.bat): `if (...) else (...)` lồng nhiều tầng → `"...was unexpected at this time"`

Viết `start.bat` với `if errorlevel 1 ( ... nested if ... ) else ( ... )` lồng 3 tầng (kèm
dấu `"` trong text hiển thị) khiến `cmd.exe` báo lỗi parser mơ hồ, không chỉ đúng dòng lỗi.
Đã thử bỏ dấu `"` (không phải nguyên nhân chính) rồi mới xác định đúng là **độ lồng sâu của
if/else**.

**Đã xử lý:** viết lại toàn bộ bằng `goto`/label (không có `if (...) else (...)` lồng quá 1
tầng). **Quy tắc cho mọi `.bat` mới trong repo này: dùng `goto`/label cho logic rẽ nhánh
nhiều bước, chỉ dùng `if (...) else (...)` 1 tầng cho việc đơn giản.**

### 5.4. Chrome chặn cổng CDP debug trên profile mặc định (bảo mật, từ Chrome ~v111+)

Crawler dùng CDP mode (`config/base_config.py: CDP_CONNECT_EXISTING = True`) — kết nối vào
1 Chrome đã mở sẵn ở cổng 9222, không tự bật browser. Chrome hiện đại **im lặng không mở
cổng debug** nếu chạy trên profile mặc định của người dùng (`%LOCALAPPDATA%\Google\Chrome\
User Data`), dù cờ `--remote-debugging-port=9222` có truyền đúng — đây là tính năng bảo mật
mới của Chrome, không phải lỗi cấu hình. Ngoài ra: nếu Chrome (bất kỳ profile) đã đang chạy,
lệnh mới với cờ debug port sẽ **bị Chrome cũ nuốt** (chuyển tiếp vào instance cũ, không có
debug port) — phải đóng HẾT Chrome trước khi mở với cờ mới.

**Đã xử lý:** `start_browser_cdp.bat` luôn dùng `--user-data-dir` **riêng biệt**
(`browser_data/cdp_profile/`), không dùng profile mặc định. Nếu vẫn không vào được: đóng
hết `chrome.exe` (Task Manager) trước, chạy lại.

### 5.5. Tự động hoá trình duyệt qua PowerShell bị chặn mạng (nghi EDR/Antivirus)

Khi agent (Claude Code) tự spawn Chrome qua PowerShell (`Start-Process ... chrome.exe
--remote-debugging-port=...`), Chrome đó **mở được nhưng không load được bất kỳ trang
ngoài nào** (kể cả `google.com`) — cùng lỗi xảy ra với `Invoke-WebRequest` gọi từ PowerShell.
Khi **người dùng tự tay** mở đúng lệnh y hệt qua Command Prompt, mọi thứ hoạt động bình
thường. Nghi ngờ hợp lý nhất: phần mềm bảo mật (EDR/Antivirus) trên máy chặn/giữ traffic
mạng của process do tool tự động hoá sinh ra (cờ `--remote-debugging-port` hay bị EDR coi
là dấu hiệu RAT/infostealer), nhưng KHÔNG chặn khi người dùng tự chạy.

**Đã xử lý (không phải sửa code, mà đổi quy trình):** `start_browser_cdp.bat` được thiết kế
để **người dùng tự double-click chạy**, không phải để AI agent tự spawn qua shell tool.
**Quy tắc: không dùng PowerShell/shell tool của agent để tự mở Chrome debug port — luôn để
người dùng tự chạy `start_browser_cdp.bat`.**

### 5.6. Excel `kit/templates/*.xlsx` có công thức sống thật, nhưng chưa auto-fill

Đã xác minh bằng `openpyxl`: 5 file mẫu (`TREND_BRIEF_sample.xlsx`,
`KOC_SCORECARD_sample.xlsx`, `OPPORTUNITY_MAP_sample.xlsx`, `SOV_DASHBOARD_sample.xlsx`,
`INSIGHT_BANK_sample.xlsx`) đều có **công thức Excel thật** (`ROUND`, `IFERROR`, `SUMIFS`,
`IF/AND/MEDIAN`...), không hardcode số. Nhưng **không có script nào tự điền dữ liệu thô
(output analyzer) vào các mẫu này** — việc này hiện làm tay (copy-paste). Xem gợi ý ở §6.

### 5.7. Windows Credential Manager giữ token GitHub sai tài khoản

`git push` báo 403 dù user có quyền — do Windows Credential Manager cache token GitHub cũ
gắn với tài khoản KHÁC (không có quyền trên repo đích). Xoá 2 entry liên quan trong
Credential Manager (`cmdkey /delete:...` — cẩn thận target có khoảng trắng cần P/Invoke
`CredDelete` vì `cmdkey` xử lý sai cú pháp) rồi push lại để Git Credential Manager xác thực
lại đúng tài khoản.

### 5.10. MCP server + portability (Claude Code truy cập, copy thư mục là chạy)

- **MCP server** (`kit/mcp/mcp_mediacrawler.py`) bọc REST API thành 9 tool cho AI agent
  (crawl_search/detail/creator, get_status, list_results, read_result, **analyze,
  list_reports, read_report**). MCP chỉ điều phối — **phải bật `start.bat` (API 8080)
  trước**.
- **2 transport**: `stdio` (mặc định, Claude Code cùng máy) và `streamable-http`/`sse`
  (remote qua Tailscale). Chọn bằng env `MCP_TRANSPORT`/`MCP_HOST`/`MCP_PORT`.
- **Kết nối Claude Code**: chạy `setup_mcp.bat` → tự dò đường dẫn tuyệt đối máy hiện tại,
  ghi `.mcp.json` (project-scoped, **gitignore** vì đường dẫn theo máy) + in lệnh
  `claude mcp add`. Remote: `start_mcp.bat` (HTTP 0.0.0.0:8790) rồi máy khác
  `claude mcp add --transport http mediacrawler http://<tailscale-ip>:8790/mcp`.
  Chi tiết: `kit/mcp/README.md`.
- **Lỗi đã gặp**: `print()` tiếng Việt ở nhánh HTTP crash cp1252 trên Windows. Đã
  reconfigure stdout UTF-8 **chỉ trong nhánh HTTP** — TUYỆT ĐỐI không đụng stdout ở mode
  stdio (stdout là kênh JSON-RPC của MCP, ghi vào sẽ hỏng giao thức). Batch: dấu `->` trong
  `echo` bị hiểu là redirect `>` (tạo file rác `phai`) — bỏ `>` khỏi mọi dòng echo.
- **Portability**: mọi đường dẫn suy từ `Path(__file__)` (không hardcode tuyệt đối), API
  + MCP tự nạp `.env` ở gốc (`load_dotenv`) nên cấu hình máy đặt sẵn trong `.env` có tác
  dụng. Copy cả thư mục (kèm `api/webui/` đã build) sang máy khác → `start.bat` tự tạo lại
  `.venv` nếu hỏng (§5.9) → chạy được ở đường dẫn bất kỳ. Bước setup 1 lần cho MCP:
  `setup_mcp.bat`.

### 5.9. `.venv` đồng bộ qua OneDrive từ máy khác → hỏng (đường dẫn Python máy cũ)

Dự án nằm trong thư mục **OneDrive**. Khi tạo `.venv` trên máy A rồi OneDrive đồng bộ
sang máy B, `.venv/pyvenv.cfg` vẫn trỏ `home`/`executable` về đường dẫn Python của **máy
A** (VD `C:\Program Files\Python312` của user `HiepChoc`) — máy B không có đường dẫn đó
nên `.venv\Scripts\python.exe` báo `No Python at '...'` và **mọi lệnh python/pytest/uvicorn
qua venv đều chết**. Đây nhiều khả năng là gốc rễ lỗi "chạy máy khác không truy cập được
localhost:8080": `start.bat` (bản cũ) thấy thư mục `.venv` tồn tại nên bỏ qua bước tạo,
rồi uvicorn chạy bằng python venv hỏng → server không lên.

**Đã xử lý:** `start.bat` giờ **chạy thử** `.venv\Scripts\python.exe -c "import sys"`;
nếu lỗi (venv hỏng/đồng bộ từ máy khác) thì **xoá và tạo lại venv** tự động, rồi cài lại
dependencies. **Đừng chỉ kiểm tra `if exist .venv` — phải chạy thử interpreter.** Cân nhắc
loại `.venv/` khỏi phạm vi đồng bộ OneDrive (right-click → Free up space / Always keep on
this device không giải quyết; cần loại hẳn khỏi thư mục sync hoặc dùng repo ngoài OneDrive).

### 5.8. Không có chế độ "hot list" chính thức của nền tảng

Đã xác minh trong code (`api/schemas/crawler.py: CrawlerTypeEnum` chỉ có `SEARCH/DETAIL/
CREATOR`) — crawler **không** có chế độ đọc thẳng bảng trending/hot search chính thức của
Douyin/Weibo... Mọi "biết cái gì đang hot" phải suy ra từ crawl theo **từ khoá tự chọn** rồi
chạy `analyzer trend`. Đừng hứa hẹn với người dùng tính năng "lấy hot list" — chưa có.

### 5.11. Dữ liệu xuất ra có dòng TRÙNG → mọi báo cáo cũ phồng số 20–29%

Đo trên chính dữ liệu trong `data/`: `xhs_search_20260724` 40 dòng có **8 trùng
`note_id`** (20%), `bilibili_search_20260724` 39 dòng có **10 trùng `video_id`** (26%),
`douyin_search_20260724` 28 dòng có **8 trùng `aweme_id`** (29%).

**Đã xử lý:** `kit/enrich/schema.py: dedupe_posts()` chạy trong `analyzer.load()`, bỏ trùng
theo `(platform, post_id)` và in `[!] Bỏ N dòng trùng`.

⚠️ **Hệ quả cần biết:** mọi báo cáo sinh TRƯỚC fix này có số cao hơn thực tế. Chạy lại
analyzer trên cùng file sẽ ra số nhỏ hơn — đó là số đúng, không phải mất dữ liệu.
Đặc biệt **sound watchlist (CS10) trước đây là ảo**: 8 "nhạc trending" của file Douyin chỉ
là cùng một bài bị đếm 2 lần; sau dedupe còn 20 bài / 20 nhạc, **không nhạc nào dùng lại**.

### 5.12. Mã nền tảng KHÁC tên thư mục dữ liệu → MCP không thấy file vừa cào

`api/routers/data.py` lọc `?platform=` bằng so khớp chuỗi con của đường dẫn, nhưng thư mục
là tên đầy đủ: `dy`→`data/douyin/`, `ks`→`data/kuaishou/`, `wb`→`data/weibo/`, và Bilibili
ghi **hai** thư mục (`data/bilibili/` cho Excel, `data/bili/` cho JSON). Đo thật trước fix:
`?platform=dy` → **0 file** trong khi `?platform=douyin` → 3 file. Vì MCP luôn gửi mã ngắn,
`crawl_search` trên Douyin/Kuaishou/Weibo **luôn** báo *"chưa thấy file kết quả"* dù cào xong.

**Đã xử lý:** bảng `PLATFORM_DIRS` + `dirs_for()` trong `kit/enrich/schema.py` là nguồn sự
thật duy nhất; `api/routers/data.py` và `kit/queue/tasks.py` khớp theo **tên thư mục**.

### 5.13. Crawl thất bại vẫn báo `idle` → phía gọi dùng dữ liệu của lần trước

`crawler_manager` trước đây set `status="idle"` bất kể exit code và `get_status()` hardcode
`error_message=None`. Hệ quả: MCP/job coi crawl chết là xong rồi đi lấy **file cũ**.

**Đã xử lý:** lưu `exit_code`; exit ≠ 0 → `status="error"` + `error_message` kèm 3 dòng log
lỗi cuối; `CrawlerStatusResponse` lộ thêm `exit_code`.

### 5.14. `.jsonl` vô hình với API dữ liệu — mà đó là `save_option` mặc định

`api/routers/data.py` thiếu `.jsonl` trong `supported_extensions` và không có nhánh preview,
trong khi `CrawlerStartRequest.save_option` và MCP `crawl_detail` **mặc định là `jsonl`**
→ luồng detail gần như luôn "không thấy file". **Đã xử lý:** thêm đuôi + nhánh preview đọc
từng dòng JSON.

### 5.15. `trend_radar` crash trên Bilibili/Weibo + `eng_total` hụt

Hai lỗi cùng gốc là tên cột chỉ số khác nhau giữa các nền tảng:
- `trend_radar` agg cứng vào `collected_count` → **KeyError, crash hoàn toàn** trên Bilibili
  và Weibo (2 nền tảng không có cột đó).
- `COUNT_COLS` thiếu tên cột Bilibili/Weibo/Zhihu → 1 bài Bilibili có like 472K + favorite
  744K + comment 320K + share 91K mà `eng_total` chỉ ra **472K**, `save_rate`/`share_rate` = 0.

**Đã xử lý:** `kit/enrich/schema.py` map cột về canonical `m_like/m_comment/m_share/m_save/
m_view` (chỉ THÊM cột, không đổi cột gốc); `add_engagement` ưu tiên `m_*` và **có fallback**
về logic cũ; `save_tb` suy cột theo nền tảng. Sau fix `eng_total` = **1.628.745**.
Cột thiếu để **NaN, không điền 0** — Kuaishou không có comment/share, điền 0 sẽ dìm nó khi
so sánh chéo nền tảng.

### 5.16. Báo cáo XHS không hiện ảnh nào

`_media_grid` chỉ đọc `cover_url`, nhưng XHS **không có** cột đó (cover là ảnh đầu trong
`image_list`), Bilibili/Kuaishou lại dùng `video_cover_url`. **Đã xử lý:** dùng
`schema.cover_of_row()`. Đã kiểm: báo cáo XHS từ 0 → 20 ảnh. Ảnh cover load được **không
cần Referer** (đo: `200 image/jpeg`) nên hotlink trực tiếp, không cần proxy.

### 5.17. `FORMAT_RULES` quá yếu → phân loại format gần như vô dụng

Đo trước khi sửa, tỉ lệ bài rơi vào "khác": **xhs 85% · douyin 75% · bilibili 56%**. Nguyên
nhân kép: quá ít từ khoá, và khớp theo thứ tự chèn dict nên một từ khoá yếu chiếm luôn nhãn.

**Đã xử lý:** đổi sang **chấm điểm** (số luật khớp được, hoà thì theo `_FORMAT_PRIORITY`) +
mở rộng từ khoá tiếng Trung/Việt + thêm 6 nhóm (`case/战绩`, `warning/劝退`, `resource/干货`,
`recruit/招募`, `qna/问答`, `series/合辑`). Sau sửa: **xhs 9.4% · douyin 20% · bilibili 3.4%**.
`tests/test_format_rules.py` ghim ngưỡng ≤40% thành ràng buộc CI và ghim nhãn cũ khỏi hồi quy.
⚠️ `list/top` **cố ý không nhận `步`** (bước) và chỉ nhận chữ số ASCII — nếu không,
`"教你三步护肤教程"` sẽ ra `list/top` thay vì `tutorial`.

### 5.18. Tên báo cáo cố định → chạy 2 nền tảng là ghi đè nhau

`build_report` luôn ghi `reports/{command}_report.html`, nên chạy `trend` cho Douyin rồi cho
XHS là **mất báo cáo đầu**. **Đã xử lý:** thêm tham số `slug` (mặc định rỗng → giữ nguyên tên
cũ cho tương thích); `_run_analyzer` sinh slug từ nền tảng + từ khoá. Ngoài ra `reports/` giờ
suy từ `Path(__file__)` chứ không phải CWD — trước đây chạy uvicorn từ thư mục khác thì báo
cáo ghi ra chỗ `api/routers/kit.py` không đọc tới.

### 5.19. Phiên 25/09/2026 — tóm tắt các "hố" (chi tiết ở HANDOFF.md §2–§7)

- **Tìm kiếm Douyin:** từ khoá rỗng từng âm thầm rơi về `config.KEYWORDS`; phân trang chỉ 1
  trang và chồng 5 bài/trang. Đã sửa, đã đo tham số thật của trang web.
- **`Page.goto` timeout** trang chủ: chờ `load` là không cần; dùng `tools/page_nav.py`.
- **Mọi file JSON mất trục thời gian** (`read_json` tự parse `create_time`) → KOC/Seasonal/SoV sai.
- **File bình luận mất ~90%** vì bỏ trùng theo id bài → nay theo `comment_id`.
- **Điểm trend chia max** → 1 bài viral ép cả bộ về ~0 → nay thứ hạng %.
- **Cổng:** máy chủ dự án có vidauto (8000/8001/8765+), wovoice (8300), Flowboard (9223),
  remotion (3100). MCP HTTP của repo dùng **8790**.
- **CRLF:** `sed -i` có thể đổi `.bat` sang LF → giữ CRLF khi sửa.

## 6. Việc CHƯA làm — gợi ý lộ trình tiếp theo

> **Ưu tiên hiện tại (đã được chủ dự án duyệt thiết kế):** report đợt 2 + 3 — Creator Audit,
> Conversation Pulse, Structure & Hashtag Kit, Opportunity Map + mức tập trung, Momentum, LLM
> cho ô nhận xét. Đặc tả + số liệu mẫu đã đo: **[`HANDOFF.md`](../HANDOFF.md) §6**.

Sắp theo độ ưu tiên (dựa trên giá trị/công sức), không phải thứ tự bắt buộc:

1. **Script tự động điền `kit/templates/*.xlsx`** từ output thô của analyzer — hiện làm
   tay (§5.6). Giá trị cao nếu team dùng lặp lại hàng tuần.
2. **Đổi lịch n8n từ tuần/tháng sang ngày** cho ai cần theo dõi trend hàng ngày — chỉ sửa
   node `Schedule Trigger`, không cần sửa code (đã ghi rõ trong
   `docs/HUONG_DAN_SU_DUNG.md` Phần 6). Cân nhắc thêm bộ từ khoá cố định trước khi đổi.
3. **Test `kit/queue` với Redis thật** (hiện chỉ test bằng mock arq) và `kit/webhook` với
   `NOTIFY_WEBHOOK_URL` thật (n8n) — để chắc luồng end-to-end không chỉ đúng ở unit test.
4. **Import + chạy thật 3 workflow n8n** (`kit/n8n/*.json`) trên 1 instance n8n thật, sửa
   `executeCommand` cho khớp đường dẫn server thật.
5. **Kiểm chứng lại `kit/mcp/mcp_mediacrawler.py`** — chưa ai chạy/test module này trong
   các session gần đây, không rõ còn tương thích với `api/` hiện tại hay không.
6. **Deploy schema Supabase lên 1 project thật** và nối `--to supabase` end-to-end (hiện
   chỉ test bằng mock client) — cần trước khi dashboard sống (Phần 4.3 trong
   `docs/HUONG_DAN_SU_DUNG.md`) có ý nghĩa thực tế.
7. **(Tier 3 — cần rà soát pháp lý trước, KHÔNG tự làm)** multi-account/proxy rotation nếu
   sau này cần crawl quy mô lớn hơn.

## 7. Bản đồ tài liệu

| File | Dành cho | Nội dung |
|---|---|---|
| [`AGENTS.md`](../AGENTS.md) | AI coding assistant | Entry point — đọc cái gì trước |
| [`CLAUDE.md`](../CLAUDE.md) | AI coding assistant | Ranh giới bắt buộc + quy ước code |
| `docs/PROJECT_STATUS.md` (file này) | AI coding assistant | Tiến trình, quyết định, gotcha, TODO |
| `docs/ARCHITECTURE.md` | Dev | Luồng dữ liệu kỹ thuật 6 tầng |
| `docs/HUONG_DAN_SU_DUNG.md` | Người dùng cuối (marketing/content/sales/CSKH) | Case study, webhook, dashboard |
| `docs/DEPLOY.md` | Người vận hành | Deploy Windows+Tailscale hoặc Linux systemd |
| `kit/storage/README.md` | Dev | Chạy migration Supabase |
| `kit/README.md` | Người dùng cuối | Quick reference lệnh CLI |
| `BUILD_GUIDE_ClaudeCode.md` | AI coding assistant (lịch sử) | Chuỗi 11 prompt gốc đã dùng để build — đã xong hết, giữ lại để tham khảo cách chia nhỏ task |
| `CHANGELOG.md` | Mọi người | Lịch sử thay đổi theo version |
| [`HANDOFF.md`](../HANDOFF.md) | AI coding assistant | Ghi chú bàn giao phiên gần nhất: đã sửa gì, vì sao, việc tiếp theo đã duyệt |

## 8. Checklist trước khi bắt đầu code tiếp

- [ ] Đã đọc `CLAUDE.md` (ranh giới) và mục 4-5 ở trên (quyết định + gotcha)?
- [ ] `git status` sạch hoặc hiểu rõ đang có gì chưa commit?
- [ ] `pytest tests -q` xanh, `ruff check .` sạch?
- [ ] Việc định làm có đúng đặt trong `kit/` không (trừ khi bắt buộc chạm base)?
- [ ] Nếu thêm module mới: đã có kế hoạch viết test synthetic (không gọi mạng thật)?
- [ ] Nếu thêm biến môi trường mới: đã cập nhật `.env.example`?
- [ ] Nếu đổi hành vi crawl: có vi phạm "không tăng tải" (CLAUDE.md §2.2) không?
