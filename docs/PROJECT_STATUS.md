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
| `kit/webhook` | ✅ | ✅ `test_webhook.py` | Cờ `--notify` | Chưa test với `NOTIFY_WEBHOOK_URL` thật (n8n) |
| `kit/queue` (arq) | ✅ | ✅ `test_tasks.py` | CLI enqueue + worker | **Chưa chạy thật với Redis** — chỉ test bằng mock |
| `api/routers/kit.py` | ✅ | ✅ `test_api_kit.py` | Mount trong `api/main.py` | Đã xác nhận hiện đúng trong OpenAPI `/docs` |
| `start.bat` / `start_browser_cdp.bat` | ✅ | Chạy thật, không phải pytest | — | Đã chạy thật từ đầu-đến-cuối trên máy dev (§5.4) |
| `kit/mcp/mcp_mediacrawler.py` | Từ zip gốc | ❌ chưa test | Chưa | **Chưa ai đụng trong các session vừa qua** — coi như chưa kiểm chứng |
| `kit/n8n/*.json` (3 workflow) | Từ zip gốc | — | Chưa import n8n thật | Đã đọc hiểu nội dung khi viết docs, lịch mặc định tuần/tháng, xem §6 |
| `kit/templates/*.xlsx` (5 mẫu) | Từ zip gốc, có công thức sống thật | — | **Chưa auto-fill** | Xem §5.5 — điền tay, không có script nối |
| Base crawler (`media_platform/`, `api/routers/crawler.py`…) | Không sửa | Test gốc của repo | — | 6 test trong `test/` (không phải `tests/`) fail vì cần Redis/proxy thật — **có sẵn từ trước fork, không phải do kit** |

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

### 5.8. Không có chế độ "hot list" chính thức của nền tảng

Đã xác minh trong code (`api/schemas/crawler.py: CrawlerTypeEnum` chỉ có `SEARCH/DETAIL/
CREATOR`) — crawler **không** có chế độ đọc thẳng bảng trending/hot search chính thức của
Douyin/Weibo... Mọi "biết cái gì đang hot" phải suy ra từ crawl theo **từ khoá tự chọn** rồi
chạy `analyzer trend`. Đừng hứa hẹn với người dùng tính năng "lấy hot list" — chưa có.

## 6. Việc CHƯA làm — gợi ý lộ trình tiếp theo

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

## 8. Checklist trước khi bắt đầu code tiếp

- [ ] Đã đọc `CLAUDE.md` (ranh giới) và mục 4-5 ở trên (quyết định + gotcha)?
- [ ] `git status` sạch hoặc hiểu rõ đang có gì chưa commit?
- [ ] `pytest tests -q` xanh, `ruff check .` sạch?
- [ ] Việc định làm có đúng đặt trong `kit/` không (trừ khi bắt buộc chạm base)?
- [ ] Nếu thêm module mới: đã có kế hoạch viết test synthetic (không gọi mạng thật)?
- [ ] Nếu thêm biến môi trường mới: đã cập nhật `.env.example`?
- [ ] Nếu đổi hành vi crawl: có vi phạm "không tăng tải" (CLAUDE.md §2.2) không?
