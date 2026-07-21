# Tài liệu hướng dẫn sử dụng — DigiAds · MediaCrawler Kit

> Dành cho: Marketing/Nghiên cứu thị trường, Content/Sáng tạo, Sales (TikTok Shop/Livestream),
> CSKH/Voice of Customer, và người quản lý agency. **Không cần biết code** — phần nào cần kỹ
> thuật sẽ ghi rõ để nhờ dev hỗ trợ. Đọc kèm [README.md](../README.md) (cài đặt) và
> [HANDBOOK_11_case_studies.html](HANDBOOK_11_case_studies.html) (chi tiết nghiệp vụ gốc).

## Mục lục

1. [6 tầng chức năng — đọc trước khi dùng](#phần-1--6-tầng-chức-năng-của-tool)
2. [Giải nghĩa 11 case study](#phần-2--giải-nghĩa-11-case-study)
3. [Webhook — dùng khi nào, hiệu quả gì](#phần-3--webhook)
4. [Các dạng báo cáo & dashboard](#phần-4--các-dạng-báo-cáo--dashboard)
5. [Case study theo bộ phận](#phần-5--case-study-theo-bộ-phận)
6. [Quy trình cho team Content sáng tạo theo trend](#phần-6--quy-trình-cho-team-content-sáng-tạo-theo-trend)
7. [Checklist & giới hạn cần nhớ](#phần-7--checklist--giới-hạn-cần-nhớ)

---

## PHẦN 1 — 6 tầng chức năng của tool

Dữ liệu chảy qua tool theo đúng 6 bước sau. Hiểu tầng nào làm gì giúp biết **nên gọi ai,
lúc nào, và kỳ vọng đầu ra là gì** — tránh nhầm "tool crawl được cái gì" với "tool phân
tích ra cái gì".

```
1. THU THẬP (Crawler)      →  2. CHUẨN HOÁ (Enrich)      →  3. PHÂN TÍCH (Analyzer, 11 case)
   lấy bài/comment/creator      làm sạch số liệu, dịch          biến dữ liệu thô thành
   công khai theo TỪ KHOÁ       ZH→VI, gắn nhãn format           chỉ số/insight/xếp hạng
        │                                                              │
        │                                                              ▼
        │                                              4. LƯU TRỮ (Supabase) — kho dữ liệu,
        │                                                 nền cho dashboard sống
        │                                                              │
        ▼                                                              ▼
6. TỰ ĐỘNG HOÁ (Webhook + Queue + n8n) ◄──────────────  5. SÁNG TẠO (Pipeline Angle→Video Brief)
   chạy định kỳ, báo tự động qua chat                     biến insight thành kịch bản video 15-20s
```

### 1.1. Tầng Thu thập — Crawler

**Là gì:** thu thập bài viết / comment / thông tin creator **công khai** từ 7 nền tảng
(Douyin, Xiaohongshu, Kuaishou, Bilibili, Weibo, Tieba, Zhihu).

**Điều quan trọng nhất cần biết:** tool thu thập theo **từ khoá bạn tự chọn** (`search`),
hoặc theo **ID bài/creator cụ thể** (`detail`/`creator`) — **không có** chế độ đọc thẳng
bảng "Hot Search"/"热榜" chính thức của nền tảng. Nghĩa là chất lượng "biết cái gì đang
hot" phụ thuộc vào việc bạn chọn đúng bộ từ khoá đại diện cho ngành/khách hàng của mình.

**Dùng như nào:** mở WebUI (`http://localhost:8080`) → chọn nền tảng, loại crawl, nhập
từ khoá → bấm **Initiate Scan**. Lần đầu crawl thật cần mở sẵn `start_browser_cdp.bat`
để đăng nhập/quét QR (đọc [README.md](../README.md)).

**Ai dùng tầng này:** người phụ trách nghiên cứu (chọn từ khoá đúng ngách/đối thủ/khách
hàng mục tiêu) — quyết định chất lượng của MỌI tầng phía sau.

### 1.2. Tầng Chuẩn hoá — Enrich (`kit/enrich`)

**Là gì:** làm sạch dữ liệu thô chạy **ngầm**, không ai bấm nút riêng cho tầng này —
nhưng cần biết nó tồn tại để hiểu vì sao số liệu "tự nhiên đúng":

- Đổi số dạng chữ Trung ("1.2万") → số thật.
- Tính giờ đăng bài, engagement tổng, tỷ lệ save/share.
- Gắn nhãn **format nội dung** tự động (before-after, review, unboxing, list, tutorial,
  storytime, POV) dựa trên tiêu đề/mô tả.
- Dịch ZH→VI theo batch (qua Claude) — nhờ bước này, người không biết tiếng Trung vẫn
  đọc được hook/insight khi cần.

### 1.3. Tầng Phân tích — Analyzer (11 case study)

**Là gì:** trái tim của tool — biến dữ liệu thô thành **số liệu & xếp hạng có công thức
rõ ràng** (không phải cảm tính). Chi tiết từng case ở [Phần 2](#phần-2--giải-nghĩa-11-case-study).

**Dùng như nào:**
```bash
python kit/analyzer/mediacrawler_analyzer.py trend  data/douyin/search_x.xlsx
python kit/analyzer/mediacrawler_analyzer.py koc    data/douyin/creator_x.xlsx
python kit/analyzer/mediacrawler_analyzer.py sov    data/douyin/search_x.xlsx kit/config/brand_map.json
```
hoặc qua REST API: `POST /kit/analyze {"command": "trend", "file": "..."}` — thuận tiện
khi muốn tích hợp vào công cụ khác (Zapier, Google Sheets script, n8n).

### 1.4. Tầng Lưu trữ — Supabase

**Là gì:** kho dữ liệu dùng chung, để số liệu **tích luỹ theo thời gian** (không chỉ 1 lần
chạy là mất) và làm **nền cho dashboard sống** (Phần 4.3) thay vì chỉ có file Excel tĩnh.

**Dùng như nào:** thêm cờ `--to supabase` khi chạy analyzer. Có 4 view dựng sẵn:
`v_trend_top` (top bài 30 ngày), `v_sov_trend` (SOV theo tuần + biến động WoW),
`v_rising_koc` (KOC đang lên), `v_niche_quadrant` (bản đồ ngách 4 góc).

**Ai dùng:** người dựng dashboard (BI tool), hoặc account team cần lịch sử dữ liệu để
so sánh tháng này/tháng trước.

### 1.5. Tầng Sáng tạo — Pipeline Angle → Video Brief

**Là gì:** biến insight (angle — hook/format/nỗi đau đã lọc top hiệu suất) thành
**kịch bản video 15-20s** dạng JSON có scene-by-scene, qua chuỗi 6 bước AI (Claude):
normalize → concept → script → variation (A/B) → compliance (rà policy) → scorecard
(chấm điểm hook trước khi tốn chi phí dựng).

**Dùng như nào:**
```bash
python kit/pipeline/angle_to_brief.py reports/angle_library.jsonl \
    --product "Serum kiềm dầu 199k, TikTok Shop" --provider mock   # demo offline, không tốn API
```
Bỏ `--provider mock` (dùng `claude`) khi chạy thật, cần `ANTHROPIC_API_KEY`.

**Ai dùng:** team Content/Sản xuất video — nhận Video Brief JSON, KHÔNG cần tự nghĩ hook
từ đầu, chỉ cần bản địa hoá/tinh chỉnh theo brand.

### 1.6. Tầng Tự động hoá — Webhook + Queue + n8n

**Là gì:** làm mọi tầng trên **chạy định kỳ** và **tự báo cho đúng người** khi có kết quả,
không cần ai ngồi bấm tay mỗi ngày. Xem chi tiết ở [Phần 3](#phần-3--webhook).

---

## PHẦN 2 — Giải nghĩa 11 case study

| Case | Câu hỏi kinh doanh trả lời được | Chỉ số chính | Bộ phận dùng | Lệnh chạy |
|---|---|---|---|---|
| **CS1** Trend Radar | Nội dung/format nào đang được hưởng ứng trong ngách này? | `trend_score = 0.4·save + 0.3·share + 0.2·comment + 0.1·like` (thang 0–100, chuẩn hoá theo max) | Marketing, Content | `trend` |
| **CS10** Sound Watchlist | Nhạc/nền nào đang được dùng lại nhiều, nên bắt trend? | Số video dùng lại ≥2 lần + engagement TB | Content, Editor video | `trend` (đi kèm CS1) |
| **CS2** Voice of Customer | Khách đang phàn nàn/mong muốn gì nhiều nhất? | Comment bank đã lọc rác, dedupe, xếp theo like — sẵn sàng đưa AI phân cụm | CSKH, Content, R&D sản phẩm | `insight` |
| **CS3** KOC Scorecard | Creator này có nên hợp tác/trả tiền không? | `điểm tổng = 0.4·eng_norm + 0.35·độ_đều + 0.25·velocity_norm`; verdict bỏ qua/theo dõi/ký ngay | Sales/BD, Influencer Marketing | `koc` |
| **CS9** Rising KOC | Creator nào đang "lên" sớm, nên ký trước khi đắt? | `velocity ≥ 1.3` và `độ đều ≥ 0.4` (cờ `rising`) trong cùng kết quả `koc` | Sales/BD | `koc` |
| **CS4/CS6** Opportunity Map | Ngách/sản phẩm nào nên đánh, nên tránh? | 4 quadrant theo median-split (số bài vs save TB): 🌊 biển xanh / ⚔ cạnh tranh / 🏜 sa mạc / 🔴 bão hoà | Marketing, Product/Sourcing | `opportunity` |
| **CS5** Angle Library | Có sẵn "nguyên liệu" nào để dựng video mới? | Top X% bài theo trend_score, chuẩn hoá thành hook/format/pain-desire | Content, Production | `angle` |
| **CS7** Seasonal Radar | Ngành này có sóng theo mùa/tuần không, khi nào lên lịch content? | Spike = tuần có engagement > 1.5× trung bình trượt 4 tuần | Marketing, Trưởng phòng lên kế hoạch | `seasonal` |
| **CS8** Price & Promo Intel | Đối thủ đang bán giá bao nhiêu, mồi khuyến mãi gì? | Trích giá/promo bằng regex từ desc/comment, xếp theo engagement | Sales, Pricing | `price` |
| **CS11** Share of Voice | Brand mình đang chiếm bao nhiêu % "tiếng nói" trong ngành so với đối thủ? | `%SOV = engagement brand / tổng engagement ngành` theo tuần | Marketing, Account/Brand Manager | `sov` |
| **(nối tiếp CS5)** Angle → Video Brief | Từ insight ra kịch bản video cụ thể như nào? | Video Brief JSON (hook, scene, CTA, hashtag) + scorecard hook | Content, Production | `kit/pipeline/angle_to_brief.py` |

---

## PHẦN 3 — Webhook

Tool có **2 đường báo tự động**, dùng cho 2 tình huống khác nhau — hiểu đúng để không
nhầm "tại sao không thấy báo":

### 3.1. `--notify` (cờ CLI, chạy qua `kit/webhook/emit.py`)

**Dùng khi:** bạn tự chạy analyzer/pipeline bằng tay hoặc qua hàng đợi arq (`kit/queue`),
muốn có 1 tin báo ngắn ngay khi xong — **không cần** dựng cả quy trình n8n.

**Cách dùng:** thêm `--notify` vào lệnh, ví dụ
`python kit/analyzer/mediacrawler_analyzer.py trend data.xlsx --notify`.

**Cơ chế:** gửi `POST {event, payload, ts}` tới `NOTIFY_WEBHOOK_URL` (đặt trong `.env`).
Thường URL này là 1 **Webhook trigger của n8n** (để n8n định dạng đẹp rồi relay ra
Zalo/Slack), nhưng cũng có thể là webhook của bất kỳ hệ thống nào nhận JSON.

| Sự kiện | Khi nào bắn | Nội dung | Hiệu quả cho |
|---|---|---|---|
| `trend_brief` | Sau lệnh `trend` chạy xong | Số bài top + format thắng thế | Content — biết ngay hôm nay nên làm dạng nào |
| `rising_koc` | Sau lệnh `koc` chạy xong, có creator `rising=true` | Danh sách creator đang lên + điểm | Sales/BD — ký trước khi giá tăng |
| `sov_updated` | Sau lệnh `sov` chạy xong | Báo "SOV tuần đã cập nhật" (rỗng, n8n tự query dashboard) | Account/Brand team — vào dashboard xem ngay |

**Đặc điểm quan trọng:** lỗi mạng khi bắn webhook **không làm hỏng job chính** (retry 2
lần rồi bỏ, chỉ log) — an toàn để chạy tự động không giám sát.

### 3.2. 3 workflow n8n dựng sẵn (`kit/n8n/`) — toàn trình, tự chạy theo lịch

Khác với `--notify` (chỉ bắn 1 tin), 3 workflow này **tự làm hết từ A-Z**: gọi API bật
crawl → chờ xong → chạy analyzer → **AI viết bản tóm tắt bằng lời** (WF_MC1) → gửi
Zalo/Slack — không cần ai ngồi bấm.

| Workflow | Lịch | Việc tự làm | Ai nhận báo | Hiệu quả |
|---|---|---|---|---|
| **WF_MC1** `trend_brief_weekly` | Thứ 2, 7h sáng | Crawl → `trend`+`angle` → **Claude viết Trend Brief** → gửi Zalo/Slack | Content team | Mỗi tuần có sẵn brief bằng lời, không cần đọc Excel thô |
| **WF_MC2** `sov_monitor_monthly` | Mùng 1 mỗi tháng, 6h sáng | Lần lượt crawl từng brand trong rổ → `sov` → ghi Supabase → báo | Account/Brand team | Theo dõi SOV dài hạn, có lịch sử trong dashboard |
| **WF_MC3** `rising_koc_alert` | Thứ 4, 2 tuần/lần, 8h sáng | Crawl ngách MCN quan tâm → `koc` → chỉ báo **nếu có** creator đang lên | Team MCN/Influencer | Không bị spam — im lặng khi chưa có gì đáng chú ý |

**Cài đặt:** import 3 file JSON trong `kit/n8n/` vào n8n, sửa node `executeCommand` cho
khớp đường dẫn máy chủ thật, đặt biến môi trường `ANTHROPIC_API_KEY`, `NOTIFY_WEBHOOK_URL`,
`SUPABASE_URL/KEY` trong n8n.

> **Muốn chạy hàng ngày thay vì tuần/tháng?** Chỉ cần sửa node lịch (`Schedule Trigger`)
> trong n8n — không cần sửa code. Xem gợi ý nhịp ngày ở [Phần 6](#phần-6--quy-trình-cho-team-content-sáng-tạo-theo-trend).

---

## PHẦN 4 — Các dạng báo cáo & dashboard

Có **4 lớp báo cáo**, từ thô tới đẹp — chọn đúng lớp theo nhu cầu, đừng đợi lớp đẹp nhất
cho mọi việc (mất công vô ích cho báo cáo dùng 1 lần).

### 4.0. Phân tích ngay trong WebUI + báo cáo HTML (dễ nhất — KHÔNG cần command line)

Đây là cách nhanh nhất cho người không rành kỹ thuật:

1. Sau khi crawl xong, mở **PAYLOAD_MATRIX** (nút trên WebUI) để xem danh sách file đã cào.
2. Trên mỗi file có nút **"Phân tích"** → bấm vào.
3. Chọn **loại phân tích** (Trend Radar / KOC / SOV / Opportunity / Seasonal / Price /
   Voice of Customer / Angle) → bấm **"Chạy phân tích"** (10–60 giây).
   - Riêng **SOV** cần điền đường dẫn `brand_map.json` (mặc định `kit/config/brand_map.json`).
4. Xong sẽ hiện **danh sách file báo cáo**:
   - **Báo cáo HTML** → bấm *"Mở báo cáo"* → mở tab mới, xem ngay (biểu đồ + bảng + link video).
   - **File Excel** → bấm *"Tải về"* để chỉnh/gửi khách.

**Báo cáo HTML tự chứa** này (mới) gồm — tuỳ loại phân tích:
- **KPI tiles** (số bài, điểm cao nhất, format thắng thế, sound nổi…).
- **Biểu đồ tròn (donut) cơ cấu** — VD cơ cấu format, cơ cấu verdict KOC, share of voice.
- **Biểu đồ đường (line)** — VD chỉ số (like/save/share/bình luận) theo từng từ khoá,
  SOV theo tuần, engagement theo tuần (seasonal).
- **Biểu đồ thanh** — điểm trend TB theo format, top creator theo điểm…
- **Bảng chi tiết kèm link ▶ Xem video** và đầy đủ chỉ số (like/save/share/điểm).

Báo cáo HTML mở offline được (tự chứa CSS + biểu đồ SVG, không cần mạng), in ra PDF đẹp,
tự đổi sáng/tối theo hệ thống — tiện gửi cho khách hoặc lưu hồ sơ chiến dịch.

### 4.1. Excel thô — xuất trực tiếp từ analyzer (nhanh nhất)

Mỗi lệnh analyzer tự xuất vào `reports/`, ví dụ lệnh `trend` ra:
`CS1_trend_top_posts.xlsx`, `CS1_trend_formats.xlsx`, `CS10_sound_watchlist.xlsx`.
**Dùng khi:** cần số liệu ngay để tự lọc/pivot tiếp trong Excel, không cần trình bày đẹp.

### 4.2. Excel mẫu có công thức sống — `kit/templates/*.xlsx` (trình bày sẵn, để báo cáo khách/leader)

Đây là 5 mẫu báo cáo đã **thiết kế sẵn công thức thật** (không phải số hardcode) — copy
dữ liệu thô từ 4.1 vào, công thức tự tính lại:

| Mẫu | Sheet | Công thức đại diện |
|---|---|---|
| `TREND_BRIEF_sample.xlsx` | TREND_BRIEF, SOUND_WATCHLIST | Điểm trend tự tính lại theo Like/Save/Share; velocity nhạc = `IFERROR(tuần_này/tuần_trước, "mới")` |
| `INSIGHT_BANK_sample.xlsx` | PAIN_POINTS, OBJECTIONS, VOCAB | `% tổng` mỗi cụm nỗi đau tự tính theo `SUM` |
| `KOC_SCORECARD_sample.xlsx` | SCORECARD | Điểm tổng + `IF` phân loại "KÝ NGAY / theo dõi / bỏ qua" tự động |
| `OPPORTUNITY_MAP_sample.xlsx` | NICHE_MAP, PRICE_INTEL | Quadrant tự tính bằng `IF/AND/MEDIAN` |
| `SOV_DASHBOARD_sample.xlsx` | DATA, SOV_DASHBOARD | `%SOV` mỗi brand mỗi tuần bằng `SUMIFS`, biến động WoW tự trừ |

> **Lưu ý kỹ thuật:** hiện việc **copy dữ liệu thô (4.1) vào các mẫu này là làm tay** —
> chưa có script tự động nối 2 bước. Nếu team làm báo cáo này lặp lại hàng tuần, nên nhờ
> dev viết thêm 1 script điền tự động (không khó, chỉ chưa có sẵn).

### 4.3. Dashboard sống qua Supabase — cho theo dõi liên tục, nhiều người xem

Khi chạy analyzer với `--to supabase`, dữ liệu vào kho và có 4 view SQL dựng sẵn (đọc
[Phần 1.4](#14-tầng-lưu-trữ--supabase)). Kết nối 1 BI tool (Metabase, Looker Studio,
Retool — đều đọc được Postgres của Supabase) vào các view này để có **dashboard tự cập
nhật mỗi lần chạy job**, nhiều người xem cùng lúc, không cần gửi file qua lại.

**Ví dụ minh hoạ trực quan** (mockup — xem để hình dung, không phải ảnh thật):
- 🔗 *Trend & Content Radar Dashboard* — top bài, format thắng thế, sound watchlist (CS1+CS10+CS5)
- 🔗 *SOV & Rising KOC Dashboard* — % chia sẻ tiếng nói theo tuần + danh sách creator đang lên (CS9+CS11)

*(2 mockup trên được gửi kèm dưới dạng file HTML riêng trong cùng phản hồi này.)*

### 4.4. Ví dụ: case study nào ra báo cáo dạng nào

| Case study | Báo cáo phù hợp nhất | Vì sao |
|---|---|---|
| CS1 Trend Radar | Excel mẫu `TREND_BRIEF` (gửi tuần) **hoặc** dashboard sống nếu theo dõi hàng ngày | Trend biến động nhanh, cần cập nhật liên tục nếu daily |
| CS2 Voice of Customer | Excel mẫu `INSIGHT_BANK` (theo chiến dịch, không cần realtime) | Dùng để brief content 1 lần/chiến dịch, không cần dashboard sống |
| CS3+CS9 KOC/Rising | Excel mẫu `KOC_SCORECARD` + alert webhook (WF_MC3) | Cần quyết định nhanh (ký/không ký) hơn là xem lịch sử |
| CS4/CS6 Opportunity Map | Excel mẫu `OPPORTUNITY_MAP` | Ra quyết định 1 lần khi mở ngách mới, không cần theo dõi liên tục |
| CS7 Seasonal | Excel thô (4.1) + biểu đồ tuần trong Excel/Sheets | Chỉ cần xem 1 lần để lên lịch content theo mùa |
| CS8 Price Intel | Excel mẫu `PRICE_INTEL` (sheet trong OPPORTUNITY_MAP) | Cập nhật khi có chiến dịch giá mới của đối thủ |
| CS11 SOV | Dashboard sống Supabase (theo dõi liên tục) + Excel mẫu `SOV_DASHBOARD` khi báo cáo khách theo tháng | Account team cần cả live view và file gửi khách |

---

## PHẦN 5 — Case study theo bộ phận

### 5.1. Marketing / Nghiên cứu thị trường

**Mục tiêu:** hiểu ngách đang nóng ở đâu, đối thủ đang chiếm bao nhiêu tiếng nói, nên mở
ngách nào tiếp theo.

| Bước | Hành động | Chức năng dùng | Đầu ra |
|---|---|---|---|
| 1 | Crawl 5-10 từ khoá ngành (search mode) | Tầng Thu thập | Dữ liệu thô |
| 2 | Chạy `opportunity` | CS4/CS6 | Bản đồ ngách 4 quadrant |
| 3 | Chạy `sov` với `brand_map.json` của ngành | CS11 | %SOV theo tuần |
| 4 | Chạy `seasonal` nếu ngành có tính mùa vụ | CS7 | Radar spike theo tuần |
| 5 | Đẩy Supabase, dựng dashboard SOV theo dõi hàng tháng | Tầng Lưu trữ | Dashboard sống |

**Webhook dùng:** `sov_updated` (báo account team khi có số mới) hoặc WF_MC2 (tự động
hàng tháng, có lịch sử).

**Ví dụ ngành cụ thể — Skincare:** chạy `opportunity` trên 護肤/精华 → phát hiện ngách
"kiềm dầu buổi trưa" ở góc 🌊 biển xanh (ít bài, save cao) → đề xuất sản phẩm mới nhắm
đúng ngách này trước khi đối thủ vào.

### 5.2. Content ngành dịch vụ (spa, giáo dục, F&B, agency…)

**Mục tiêu:** có nguồn insight thật (không đoán) để brief content sáng tạo đúng nỗi đau
khách hàng, đúng format đang hiệu quả.

| Bước | Hành động | Chức năng dùng | Đầu ra |
|---|---|---|---|
| 1 | Crawl detail + comment các bài đối thủ/ngành đang tốt | Tầng Thu thập | Comment thô |
| 2 | Chạy `insight` | CS2 | Comment bank đã lọc, sẵn sàng phân cụm |
| 3 | Đưa comment bank vào LLM phân cụm (Claude) → điền `INSIGHT_BANK` mẫu | CS2 + Excel mẫu | Cụm nỗi đau + hook đề xuất |
| 4 | Chạy `trend` để biết format nào đang thắng | CS1 | Bảng format |
| 5 | Chạy `angle` rồi `angle_to_brief.py` | CS5 + Pipeline | Video Brief JSON sẵn dùng |

**Webhook dùng:** `trend_brief` hàng tuần (WF_MC1) để content team luôn có nguồn cảm
hứng mới, không phải tự lục tìm.

**Ví dụ ngành cụ thể — Trung tâm tiếng Anh:** phân cụm comment lộ ra nỗi đau
"sợ nói sai trước mặt người khác" xuất hiện nhiều nhất → viết hook theo đúng nỗi đau này
thay vì hook chung "học tiếng Anh hiệu quả".

### 5.3. Sales / Livestream / TikTok Shop / Influencer Marketing

**Mục tiêu:** biết đối thủ đang bán giá bao nhiêu, mồi khuyến mãi gì, và ký đúng creator
trước khi họ đắt.

| Bước | Hành động | Chức năng dùng | Đầu ra |
|---|---|---|---|
| 1 | Crawl search theo từ khoá sản phẩm/đối thủ | Tầng Thu thập | Dữ liệu thô |
| 2 | Chạy `price` | CS8 | Bảng giá/promo đối thủ |
| 3 | Crawl creator mode cho danh sách KOC quan tâm | Tầng Thu thập | Dữ liệu creator |
| 4 | Chạy `koc` | CS3+CS9 | Scorecard + verdict + cờ rising |
| 5 | Nhận alert `rising_koc` (WF_MC3) — ký sớm | Webhook | Quyết định nhanh |

**Webhook dùng:** `rising_koc` — đây là case webhook **quan trọng nhất cho Sales**, vì
lợi thế nằm ở việc ký TRƯỚC người khác, chậm vài ngày có thể mất giá tốt.

**Ví dụ cụ thể:** WF_MC3 báo creator X có `velocity=1.8` (engagement gần gấp đôi so với
nửa đầu chu kỳ) và `độ đều=0.55` → verdict "ký ngay" → Sales liên hệ trong ngày, trước
khi giá booking tăng theo follower mới.

### 5.4. Chăm sóc khách hàng / Voice of Customer

**Mục tiêu:** hiểu khách đang phàn nàn gì, dùng từ ngữ nào, để cả CSKH và Content cùng
dùng chung 1 nguồn sự thật (không phải đoán qua vài ticket lẻ tẻ).

| Bước | Hành động | Chức năng dùng | Đầu ra |
|---|---|---|---|
| 1 | Crawl comment trên bài của mình + đối thủ cùng ngành | Tầng Thu thập | Comment thô |
| 2 | Chạy `insight` | CS2 | Comment bank sạch, xếp theo like |
| 3 | Phân cụm bằng LLM → điền sheet OBJECTIONS + VOCAB | CS2 + Excel mẫu | Bảng phản đối thường gặp + từ khách hay dùng |
| 4 | Chuyển bảng OBJECTIONS cho CSKH làm script trả lời chuẩn | — | Script CSKH nhất quán |
| 5 | Chuyển sheet VOCAB cho Content — dùng đúng từ khách hay dùng trong hook | — | Hook "nói đúng ngôn ngữ khách" |

**Webhook dùng:** không cần tự động hoá liên tục — `insight` thường chạy theo chiến dịch
(1 lần khi ra mắt sản phẩm/xử lý khủng hoảng), nên chạy tay + `--notify` báo 1 lần đủ.

---

## PHẦN 6 — Quy trình cho team Content sáng tạo theo trend

Đây là quy trình đề xuất cụ thể khi mục tiêu là **content team sản xuất liên tục theo
trend**, ghép đúng các chức năng theo nhịp tuần (đổi sang nhịp ngày nếu cần — xem lưu ý
cuối phần).

| Ngày | Hành động | Chức năng | Người chịu trách nhiệm | Đầu ra |
|---|---|---|---|---|
| **Thứ 2** | WF_MC1 tự chạy 7h sáng: crawl từ khoá theo dõi → `trend`+`angle` → Claude viết brief → gửi Zalo/Slack | CS1+CS10+CS5, webhook `trend_brief` | Tự động (n8n) | Trend Brief bằng lời trong nhóm chat |
| **Thứ 3** | Content Lead đọc Trend Brief, mở `angle_library.jsonl`, chọn top 5-10 angle phù hợp brand | CS5 (Angle Library) | Content Lead | Danh sách angle đã chọn |
| **Thứ 3 (chiều)** | Chạy `angle_to_brief.py` với `--product` đúng SP đang cần đẩy | Pipeline Angle→Video Brief | Content Lead / dev hỗ trợ | `briefs.jsonl` — kịch bản 15-20s |
| **Thứ 4** | Review scorecard (`hook_strength`, `verdict: ship/revise/kill`) — chỉ giữ brief `ship` | Pipeline (bước scorecard) | Content Lead | Brief đã lọc, sẵn sản xuất |
| **Thứ 4-5** | Rà `compliance` (đã có sẵn trong brief) trước khi giao dựng — đặc biệt SP mỹ phẩm/thực phẩm/sức khoẻ | Pipeline (bước compliance) | QA/Compliance | Brief an toàn pháp lý |
| **Thứ 5-6** | Giao brief cho Production dựng video (AI video hoặc quay thật) | — (bàn giao ngoài tool) | Production | Video xuất bản |
| **Song song** | Theo dõi `sound_watchlist` (CS10) — ưu tiên nhạc đang lên khi dựng | CS10 | Editor | Video bắt trend nhạc |

**Đổi sang nhịp hàng ngày:** sửa `Schedule Trigger` trong WF_MC1 từ "mỗi tuần" thành
"mỗi ngày" (n8n, không cần sửa code) — nhưng cân nhắc 2 điều trước khi đổi:
1. Cần bộ từ khoá theo dõi **cố định, đủ rộng** để mỗi ngày đều có dữ liệu mới đáng phân
   tích (crawl 1 từ khoá y hệt mỗi ngày ra ít bài mới → dùng cờ crawl tăng dần, xem
   [Phần 1.6](#16-tầng-tự-động-hoá--webhook--queue--n8n) / `kit/storage/checkpoint.py`).
2. Nhịp ngày phù hợp để **phát hiện sớm** (sound mới nổi, creator mới lên) — còn việc
   **ra brief sản xuất** vẫn nên giữ nhịp tuần (Thứ 3-6 ở trên), vì review + compliance +
   sản xuất cần thời gian, làm hàng ngày dễ vội và bỏ sót bước compliance.

---

## PHẦN 7 — Checklist & giới hạn cần nhớ

- **Chỉ dữ liệu công khai, chỉ nghiên cứu nội bộ.** Không đăng lại/nhân bản nội dung
  người khác; creator luôn ẩn danh (`creator_hash`, nickname mask) — tuân thủ Nghị định
  13/2023, không thêm code de-anonymize.
- **Không có "hot list" chính thức của nền tảng** — chất lượng insight phụ thuộc vào bộ
  từ khoá bạn chọn, cần review/cập nhật định kỳ (gợi ý: mỗi tháng rà lại 1 lần).
- **Giữ concurrency = 1**, có nghỉ giữa request — không tăng tải crawler dù có nhu cầu
  chạy nhiều ngách; dùng hàng đợi (`kit/queue`) để xếp lịch tuần tự thay vì chạy song song.
- **Excel mẫu (`kit/templates/`) hiện cần điền tay** — nếu 1 báo cáo dùng lặp lại nhiều
  lần, nên đầu tư viết script tự động điền (nhờ dev), tiết kiệm thời gian dài hạn.
- **Session Chrome (CDP) cần duy trì đăng nhập** — nếu tự động hoá hàng ngày, đảm bảo
  không bị đăng xuất/captcha giữa các lần chạy (rủi ro thực tế của mọi hệ thống tự động
  hoá crawl, cần người theo dõi định kỳ, không "set và quên").
- **Tier 3 (multi-account, xoay proxy) chưa mở** — nếu cần chạy quy mô lớn hơn, cần rà
  soát pháp lý trước, không tự ý tăng cấu hình.
