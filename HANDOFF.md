# HANDOFF — ghi chú bàn giao cho AI/dev tiếp theo

> Đọc sau [`AGENTS.md`](AGENTS.md) và [`CLAUDE.md`](CLAUDE.md). File này ghi **chi tiết phiên
> làm việc gần nhất**: đã sửa gì, vì sao, nằm ở đâu, kiểm lại thế nào, và việc tiếp theo đã
> được chủ dự án duyệt. Tổng quan dài hạn vẫn ở [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

**Phiên:** 25/09/2026 · Claude Code (desktop) · máy Windows 11 của chủ dự án.
**Trạng thái khi kết thúc:** `pytest tests -q` → **538 passed, 8 skipped** · `ruff check .` sạch.

---

## 0. Đọc nhanh trong 1 phút

| Việc | Trạng thái | Chỗ xem |
|---|---|---|
| Đồng bộ upstream NanmiCoder đến `380b426` (19/09/2026) | ✅ xong | §1 |
| Sửa độ chính xác tìm kiếm Douyin (phân trang, từ khoá rỗng) | ✅ xong, đã crawl thật kiểm chứng | §2 |
| Sửa lỗi `Page.goto: Timeout 30000ms` | ✅ xong, đã crawl thật | §2.3 |
| Launcher `.bat` + xung đột cổng với app khác trên máy | ✅ xong | §3 |
| **Report đợt 1** (Trend Radar mới, hiện đủ dữ liệu, ô nhận xét, giao diện mới) | ✅ xong | §4 |
| 3 lỗi dữ liệu có từ trước (JSON mất ngày, bình luận mất 90%, điểm trend) | ✅ xong | §5 |
| **Report đợt 2 + 3** (Creator Audit, Conversation Pulse, Hashtag, Momentum) | ⏳ đã duyệt thiết kế, CHƯA code | §6 |
| Nhận xét report bằng LLM tự động | ⏳ tính năng sau, đã chừa chỗ | §4.4 |

Bản thiết kế report đã được chủ dự án duyệt (có form mẫu chạy bằng dữ liệu thật):
**https://claude.ai/artifact/FCeDhaHNekQtHpif5pkmR8** (riêng tư của chủ dự án — nếu không mở
được, toàn bộ quyết định đã chép lại ở §4 và §6 dưới đây).

---

## 1. Đồng bộ upstream

- Repo fork từng bị **squash thành 1 commit** nên không có merge-base với upstream. Đã dò bằng
  cách so cây thư mục: fork dựa trên upstream **`e6e863a` (25/07/2026)**.
- Commit `6c032b8` áp toàn bộ diff `e6e863a..380b426` và **có cha thứ hai là `upstream/main`**.
  Từ nay đồng bộ chỉ cần:
  ```bash
  git fetch upstream
  git merge upstream/main
  ```
  (remote `upstream` = https://github.com/NanmiCoder/MediaCrawler.git, thêm lại nếu máy mới chưa có.)
- Upstream mang về: bộ tải media viết lại (`media_downloader/`, `media_platform/*/media.py`,
  cờ `--get_media`), fix dy (`x-tt-argus`, `uifid/verifyFp`), ks (link `/f/<token>`), bili
  (đăng nhập, bình luận ghim), xhs, weibo; `xhshow>=0.2.0`.
- Cách giải xung đột (giữ nguyên khi đồng bộ lần sau):
  - `README.md` giữ bản DigiAds; `README_en/es.md` lấy upstream; bỏ `docs/static/images`.
  - `xhs/playwright_sign.py`, `store/xhs/__init__.py`: lấy upstream (trùng bản vá local).
  - `bilibili/core.py`: lấy luồng tải DASH của upstream **nhưng giữ** cột `download_url` của
    fork (`attach_video_download_url`). Hàm này **phải** gọi `fnval=bili_media.MP4_FNVAL`,
    vì mặc định mới của upstream là DASH (không có `durl`) → cột sẽ rỗng.
- `tests/test_media_extractors.py::test_xhs_video_note_yields_cover_and_video` đã được cố định
  `XHS_INTERNATIONAL=False` vì fork bật `True` trong `config/base_config.py` (IP Việt Nam bị
  chuyển sang rednote.com).

## 2. Crawler

### 2.1. Tìm kiếm Douyin trả sai / thiếu bài
Người dùng thấy kết quả khác trang web và thiếu bài. Nguyên nhân có 2 lớp:

1. **Từ khoá rỗng → âm thầm dùng từ khoá mặc định.** Ô KEYWORDS WebUI chỉ nhận khi nhấn Enter;
   bấm Start luôn thì `keywords=""`, server không truyền `--keywords`, crawler cào
   `config.KEYWORDS` (`编程副业,编程兼职`). File người dùng gửi 100% dòng có
   `source_keyword` = từ khoá mặc định.
   - Sửa: `api/routers/crawler.py` trả **400** khi search không có từ khoá (áp cho cả MCP);
     WebUI `KeywordInput` tự nhận chữ đang gõ khi blur/dấu phẩy, `handleStart` đọc
     `useCrawlerStore.getState()` và chặn khi rỗng.
2. **Phân trang sai** (`media_platform/douyin/core.py::search`, `client.py::search_info_by_keyword`):
   điều kiện vòng lặp chỉ chạy **1 trang** khi `CRAWLER_MAX_NOTES_COUNT=15`; xin `count=15` nhưng
   offset bước 10 → **các trang chồng 5 bài** (nguồn dòng trùng 20–29% ghi ở PROJECT_STATUS §5.11).
   - Đã đo request thật của trang `douyin.com/search/%23aigc`: `search_source=normal_search`,
     `list_type=single`, `count=10`, offset theo `cursor` trả về, `search_id` lấy từ
     `extra.logid` trang đầu, dừng khi `has_more=0`. Code nay làm đúng như vậy, bỏ trùng theo
     `aweme_id`, dừng khi đủ số bài.
   - Kiểm chứng thật `#aigc`: lấy **30/30 bài, 0 trùng**; trùng 19/30 với trang web (10 bài đầu
     8/10). Phần lệch là do **Douyin cá nhân hoá** kết quả mỗi phiên — không đuổi cho khớp 100%.
3. WebUI thêm ô **MAX_POSTS / KEYWORD** (`max_notes_count`, mặc định 15, tối đa 500) — trước đó
   API đã hỗ trợ nhưng WebUI không có ô nhập.

Test: `tests/test_douyin_search_pagination.py`.

### 2.2. `download_url` Bilibili
Xem §1 (phải xin `MP4_FNVAL`).

### 2.3. `Page.goto: Timeout 30000ms exceeded`
Crawler mở trang chủ bằng `goto()` mặc định = chờ `load` (tải xong mọi video/ảnh) → trang
Douyin hay quá 30 s, crawler thoát code 1. Crawler chỉ cần cookie + localStorage (chữ ký
`a_bogus` tính bằng `libs/douyin.js` cục bộ). **`tools/page_nav.py::goto_resilient`**: chờ
`domcontentloaded` (45 s), thử lại 3 lần, chờ thêm `load` tối đa 15 s rồi bỏ qua. Đã áp cho
dy/xhs/bili/wb/ks. Test: `tests/test_page_nav.py`. Crawl thật: trang chưa `load` sau 15 s vẫn lấy
đủ 10/10 bài.

Ghi chú: log `Direct existing-browser CDP connection failed: ws://localhost:9222/devtools/browser`
là **vô hại** — đó là nhánh cho tính năng debug mới của Chrome 136+, code tự chuyển sang dò
`/json/version`.

## 3. Launcher & cổng

### 3.1. `start.bat`
- Build lại WebUI khi mã nguồn `webui/` mới hơn `api/webui/index.html` (trước chỉ build lần đầu →
  giao diện mới không bao giờ hiện).
- Kiểm tra `ffmpeg` (tuỳ chọn, chỉ cảnh báo): bộ tải media mới dùng để ghép DASH Bilibili.
- **Phát hiện chạy trùng:** cổng 8080 đã có MediaCrawler → báo "ĐÃ CHẠY", mở WebUI, thoát;
  app khác giữ 8080 → in tên + PID. Trước đây chạy `start.bat` lần 2 → uvicorn lỗi
  `WinError 10048` rồi tắt, người dùng tưởng "crash".
- Mọi `.bat` phải giữ **CRLF** (xem §7).

### 3.2. Bản đồ cổng trên máy chủ dự án (đo 25/09/2026)
| Cổng | App | Ghi chú |
|---|---|---|
| 8080 | MediaCrawler API + WebUI | |
| **8790** | **MediaCrawler MCP (HTTP, `start_mcp.bat`)** | Đổi từ 8765 — xem dưới |
| 9222 | Chrome CDP của MediaCrawler (`start_browser_cdp.bat`) | `CDP_CONNECT_EXISTING=True`: crawler **không tự mở Chrome** |
| 9223 | Flowboard (WS extension) | trước đây Flowboard dùng 9222 |
| 8765, 8766, 8767… | vidauto — exllm bridge / relay | **lý do đổi cổng MCP** |
| 8000, 8001 | vidauto API / MCP | |
| 8300 | wovoice | |
| 3100 | node (remotion) | |

MCP HTTP đổi mặc định 8765 → **8790** (`start_mcp.bat`, `kit/mcp/mcp_mediacrawler.py`, docs).
Máy khác đăng ký lại: `claude mcp add --transport http mediacrawler http://<tailscale-ip>:8790/mcp`.
Tường lửa cho 8790 **chủ dự án tự mở** (AI không được đổi cài đặt bảo mật hệ thống).

## 4. Report đợt 1 (đã xong)

### 4.1. Yêu cầu của chủ dự án (bất biến — đừng làm ngược)
1. **Lưới thẻ "Dữ liệu đầy đủ" của Trend Radar giữ như cũ**: preview cover + ▶, nút ▶ Xem,
   ⬇ Tải (qua `/kit/media/download`), 📋 Copy hook, "Xem đầy đủ", Save/Like, Share/Like, link
   nhạc. Được **thêm**, không được **bớt**.
2. **Hiện đủ dữ liệu đã cào**, có chuyển trang. Bộ lọc **chi tiết ít nhất như cũ**.
3. Mẫu report mới **gộp vào report hiện có**, không tách report rời.
4. Có **ô nhận xét tổng quan** ở mọi report; sau này sẽ cho LLM (ChatGPT/Claude) phân tích.
5. Phần còn lại được tự do thiết kế lại cho đúng tinh thần data analytics, màu phân biệt rõ.

### 4.2. Đã làm
- **`kit/analyzer/insights.py`** (mới) — mọi luật/ngưỡng ở đầu file:
  - `percentile_trend_score`: điểm 0–100 = thứ hạng % (lưu 0.4 · chia sẻ 0.3 · bình luận 0.2 ·
    like 0.1; chỉ số nền tảng không có thì bỏ và chia lại trọng số). Công thức cũ chia max.
  - `content_goal`: Lưu / Bàn luận / Lan truyền / Cân bằng — tỷ lệ trên like ≥ 1,5 lần trung vị
    **của chính bộ dữ liệu** (mức tuyệt đối khác xa giữa nền tảng: XHS 0,74 vs Douyin 0,16).
  - `crawl_age_days`, `age_profile` (Evergreen / Nghiêng evergreen / Flash / Hỗn hợp).
  - `hashtag_stats` (≥2 bài, bỏ tag hệ thống + tag rác kiểu `】`), `concentration` (top 3, HHI;
    bỏ qua khi < 3 creator).
  - `trend_summary` → dict JSON được + `_verdict` (câu kết luận + ≤3 việc nên làm).
    Tag chỉ được **khuyến nghị** khi ≥ 3 bài (2 bài + 1 viral từng ra "gấp 20 lần" giả).
    `mode="channel"` (không có từ khoá nguồn, < 3 creator) → bỏ nhận định tuổi bài / tập trung.
- **`trend_radar(df, top=None)`** trả **mọi bài** + `summary`. `hook_lab`, `sound_edit_kit`,
  `cover_moodboard`, `comment_bank`, danh sách "chưa nhận ra format" cũng bỏ giới hạn
  (`_take(df, None)`).
- **`kit/report/html_report.py`**:
  - `_media_grid(max_cards=None, page_size=24)`: đủ thẻ; lọc format (chip) + tìm hook + **từ
    khoá, mục tiêu, tuổi bài**; sắp trend/like/save/share/bình luận + **mới đăng**; phân trang
    24/48/96/Tất cả. JS dùng chung `DAMG(id)` trong `_JS` (ES5, chạy offline).
  - `_table`: hiện mọi dòng, phân trang phía trình duyệt (`max_rows` nay = số dòng/trang).
  - `_report_trend`: 3 tầng **Kết luận** (verdict + 3 việc) → KPI có chip → **Bằng chứng**
    (mục tiêu nội dung, tuổi bài, hashtag, format, từ khoá) → **Dữ liệu đầy đủ** (lưới thẻ).
  - `_CSS` mới: token màu cố định theo chỉ số (`--m-save` xanh ngọc, `--m-comment` tím,
    `--m-share` cam, `--m-like` xám xanh), trạng thái `--good/--warn/--bad`, font Be Vietnam Pro
    (Google Fonts, offline tự rơi về font hệ thống). **Giữ nguyên tên class cũ** để 12 report
    khác không vỡ.

### 4.3. Kiểm chứng đã chạy
Sinh bằng `kit.queue.tasks._run_analyzer` (cùng đường WebUI/MCP gọi) trên file kênh 246 video
và `#aigc` 30 bài; kiểm DOM trong trình duyệt: 246 thẻ, 24/trang, "Tất cả" = 246, lọc mục tiêu
/ tuổi / tìm / chip / sắp đều đúng, mỗi thẻ còn đủ nút. 8 report khác sinh lại không lỗi.
Test: `tests/test_insights.py`, `tests/test_report_full_data.py`.

### 4.4. Hợp đồng cho tính năng LLM (tính năng sau)
Mọi report có `section#commentary` chứa:
- `<script type="application/json" id="report-summary">` — payload từ `_llm_payload()`:
  `{report, command, platform, keyword, source_file, summary?, top_posts? (≤15), rows?, columns?}`.
  `summary` của Trend Radar = output `trend_summary()`.
- `div#llm-commentary[data-status="empty"][hidden]` — **chỗ để điền nhận xét AI**: bỏ
  `hidden`, đặt `data-status="done"`, chèn HTML đã escape.
- `textarea#analyst-note` — ghi chú tay, lưu `localStorage["digiads-note:" + pathname]`.
- `button#copy-llm[data-prompt]` — prompt `LLM_PROMPT` + JSON để dán vào ChatGPT thủ công.

Gợi ý triển khai: endpoint `POST /kit/reports/{name}/commentary` đọc `#report-summary`, gọi
`claude-sonnet-4-6` (CLAUDE.md §4) yêu cầu trả JSON, ghi kết quả vào file `*.commentary.json`
bên cạnh report; JS trong `_JS` fetch file đó nếu có. **Không** gửi dữ liệu thô, chỉ summary.

## 5. Lỗi dữ liệu có từ trước đã sửa (ảnh hưởng nhiều report)

1. **Mọi file JSON mất trục thời gian** — `pd.read_json` tự đổi `create_time` sang datetime,
   `normalize()` coi là epoch → `NaT`. KOC / Seasonal / SoV / tuổi bài trên file JSON đều sai.
   Sửa: `_read_raw` dùng `convert_dates=False`; `normalize_counts` nhận cả cột datetime.
2. **File bình luận mất ~90%** — `dedupe_posts` bỏ trùng theo `post_id` (= id bài) nên chỉ còn
   1 bình luận/bài (3.588 → 362). Sửa: có `comment_id` thì bỏ trùng theo `comment_id`.
   Voice of Customer: 273 → **2.330** bình luận dùng được.
3. **Điểm trend bị 1 bài viral ép về ~0** — đổi sang thứ hạng % (§4.2).

## 6. Việc tiếp theo (đã duyệt thiết kế, CHƯA code)

Làm theo đúng khung đợt 1 (3 tầng, token màu, `_media_grid`/`_table` đủ dữ liệu, ô nhận xét).

### Đợt 2
1. **Creator Audit** — làm lại `koc` (`_report_koc`, `koc_scorecard`). Hai chế độ:
   - **1 kênh** (creator mode 1 creator): nhịp đăng (khoảng cách trung vị), số video + like
     trung vị theo quý (**loại video < 30 ngày tuổi** khi so, quý cuối gạch chéo "non tuổi"),
     phân bố hiệu suất theo bội số trung vị kênh (<0,5 · 0,5–1 · 1–2 · 2–10 · ≥10), tỷ lệ hit
     (≥2 lần), phần like của 10% video top, **trụ nội dung** = hashtag ≥6 video với mức so trung
     vị kênh + tỷ lệ hit + khuyến nghị Làm thêm/Giữ/Giảm (bỏ tag nền tảng và tag có ở >80% video),
     lịch đăng theo giờ/thứ **của chính kênh**, mục tiêu nội dung, lưới thẻ đủ video.
   - **Nhiều kênh**: bảng điểm KOC như hiện nay + drilldown từng kênh.
   - Số liệu mẫu đã đo (file 246 video, kênh phim tài liệu động vật): trung vị like 25.026
     (video ≥30 ngày), hit 26%, 10% video top = 59% like, Q2/2026 đăng 42 video (gấp ~2,5 lần)
     nhưng like trung vị không tăng, #虎鲸 ×2,45 (hit 71%), #非洲 ×0,44, 93% video đăng lúc 8:00.
2. **Conversation Pulse** — thêm vào `insight` (Voice of Customer): bình luận/bài, **độ phủ**
   (số đã cào ÷ `comment_count` của bài; mẫu hiện ~3%), thời gian từ lúc đăng đến bình luận
   (trung vị 2,2 giờ), tỷ lệ câu hỏi (`?`/吗/怎么/为什么: 19%), bình luận có ảnh (8%), tỷ lệ bình
   luận gốc có trả lời (65% — nhưng chưa cào phần trả lời). **Phải hiện độ phủ ở đầu trang.**
   Cần ghép file contents cùng phiên để có `create_time` bài và `comment_count` thật.
3. **Structure & Hashtag Kit** — đổi tên `sound` (Sound & Edit Kit) và gộp Hashtag
   Constellation: bảng tag + mức so cả bộ + **cặp tag hay đi cùng**.
4. **Opportunity Map** + cột mức tập trung (HHI, top 3) làm trục "độ khó vào".

### Đợt 3
5. 8 report còn lại (hook, playbook, moodboard, seasonal, price, sov, angle, crossplatform)
   chuyển sang bố cục 3 tầng.
6. **Momentum** trong Trend Radar: tự bật khi chọn 2 file cùng từ khoá; ghép theo id, tăng/ngày,
   tăng %/tuần, nhãn "Nhỏ mà bốc" / "To mà chậm", bài mới lọt / rơi khỏi kết quả. Bilibili đo
   chuẩn nhất (có lượt xem). Mẫu đã đo: 22/07 → 25/07 giữ 17/38 bài.
7. Tính năng LLM cho ô nhận xét (§4.4).
8. Kiểm tra phân trang của các nền tảng khác (mới sửa Douyin — xhs/bili/ks/wb chưa rà).

### Chưa quyết (hỏi chủ dự án)
- Đồng bộ lại `kit/analyzer/registry.py` + `capabilities.py` + WebUI `AnalyzeDialog` khi đổi
  tên / gộp report ở đợt 2.
- Ngưỡng `SAVE_LEVELS` trong `insights.py` là mốc tạm từ ít dữ liệu — chỉnh khi đủ nhiều từ khoá.

## 7. "Hố" gặp trong phiên này

- **CRLF:** repo bật `autocrlf`, file trên đĩa là CRLF. `sed -i` của Git Bash có lúc đổi sang
  LF → `.bat` có thể hỏng `goto`/label. Sửa file bằng Python đọc/ghi nhị phân giữ nguyên CRLF,
  hoặc công cụ Edit.
- **Heredoc bash** chứa nhiều dấu nháy trong code Python dễ vỡ → ghi file tạm rồi chạy.
- **Server 8080 phải khởi động lại** sau khi sửa code `kit/`/`api/` (uvicorn không `--reload`).
  Crawl chạy tiến trình riêng nên luôn dùng code mới.
- **Chụp màn hình khung trình duyệt của app ra ảnh trống** khi cửa sổ bị che/thu nhỏ — kiểm tra
  bằng DOM (`javascript_tool`/`get_page_text`), đừng kết luận là lỗi report.
- **Douyin có captcha/kiểm tra bot** khi lướt nhiều: dừng lại, không vượt (CLAUDE.md §2.6).
- **Bình luận chỉ ~10/bài** theo mặc định → mọi phân tích bình luận là mẫu nhỏ; muốn sâu thì
  tăng `max_comments_count` và bật sub-comments khi crawl.
- `test/` (không phải `tests/`) có 6 test cần Redis thật — fail là bình thường.

## 8. Commit của phiên này (nhánh `main`)

| Commit | Nội dung |
|---|---|
| `6c032b8` | Đồng bộ upstream đến `380b426` (merge, cha thứ 2 = `upstream/main`) + `start.bat` |
| `d898424` | Thay đổi local có từ trước phiên (schema canonical, registry, media_urls, crawler_manager exit_code…) |
| `a523d35` | Đổi cổng MCP 8765 → 8790 |
| `5fd4d26` | Crawler Douyin + goto chịu lỗi + report đợt 1 + sửa lỗi dữ liệu + tài liệu bàn giao |

## 9. Kiểm lại nhanh

```bash
pytest tests -q                       # 538 passed (hoặc hơn)
uvx ruff check .                      # sạch (ruff không cài trong .venv — dùng uvx)
python -c "from kit.queue.tasks import _run_analyzer; print(_run_analyzer('trend', 'data/douyin/json/<file>.json'))"
# mở http://localhost:8080/kit/reports/<tên report>.html
```
