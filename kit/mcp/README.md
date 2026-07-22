# MCP server — MediaCrawler × DigiAds Kit

Bọc REST API của MediaCrawler thành **MCP server** để AI agent (Claude Code, Claude
Desktop, Cursor…) tự gọi: crawl dữ liệu công khai → phân tích 11 case → đọc báo cáo, phục
vụ nghiên cứu trend / lấy ý tưởng content — **chỉ nghiên cứu nội bộ, dữ liệu đã ẩn danh**.

## 0. Điều kiện tiên quyết

MCP server **gọi lại REST API** ở cổng 8080, nên **luôn phải bật `start.bat` trước**
(server `http://127.0.0.1:8080` đang chạy). MCP chỉ là lớp mỏng điều phối.

## 1. Kết nối LOCAL (Claude Code cùng máy — khuyến nghị)

Cách nhanh nhất — chạy 1 lần:

```bat
setup_mcp.bat
```

Script tự dò đường dẫn tuyệt đối của thư mục + `.venv` trên **máy hiện tại** và ghi
`.mcp.json`. Sau đó **mở Claude Code ngay tại thư mục dự án** → nó tự nhận MCP tên
`mediacrawler` (bấm *approve* khi được hỏi).

Hoặc đăng ký thủ công (chạy ở đâu cũng được), dùng lệnh mà `setup_mcp.bat` in ra:

```bat
claude mcp add mediacrawler -- "<ĐƯỜNG_DẪN>\.venv\Scripts\python.exe" "<ĐƯỜNG_DẪN>\kit\mcp\mcp_mediacrawler.py"
```

> `.mcp.json` chứa đường dẫn tuyệt đối của **máy cụ thể** nên **không commit** (đã cho vào
> `.gitignore`). Copy thư mục sang máy mới → chạy lại `setup_mcp.bat` là xong.

## 2. Kết nối REMOTE qua Tailscale (máy khác gọi vào)

Trên **máy chủ** (máy chạy crawler), sau khi `start.bat` đã bật:

```bat
start_mcp.bat            REM mở MCP HTTP tại 0.0.0.0:8765 (đổi cổng: start_mcp.bat "" 9000)
```

Trên **máy khách** (đã cài Tailscale, cùng tailnet):

```bat
claude mcp add --transport http mediacrawler http://<TAILSCALE_IP>:8765/mcp
```

`<TAILSCALE_IP>` lấy bằng `tailscale ip -4` trên máy chủ (start_mcp.bat cũng tự in ra nếu
phát hiện Tailscale). Chỉ cần mở cổng **8765** cho máy khách; MCP tự gọi API 8080 nội bộ
trên máy chủ nên **không cần** phơi cổng 8080 ra ngoài.

> Windows Firewall: nếu máy khách không kết nối được, trên máy chủ mở cổng (Run as Admin):
> `netsh advfirewall firewall add rule name=MediaCrawlerMCP dir=in action=allow protocol=TCP localport=8765`

## 3. Các tool MCP phơi ra

| Tool | Việc | Tham số chính |
|---|---|---|
| `crawl_search` | Crawl theo **từ khoá** (radar trend, product research) | `platform`, `keywords`, `max_notes` |
| `crawl_detail` | Bóc sâu 1+ **post/video** theo ID (voice-of-customer) | `platform`, `post_ids` |
| `crawl_creator` | Quét trang **creator** theo ID (thẩm định KOC) | `platform`, `creator_ids` |
| `get_status` | Trạng thái tiến trình crawl | — |
| `list_results` | Liệt kê file dữ liệu đã cào | `platform?` |
| `read_result` | Đọc preview 1 file dữ liệu (đã ẩn danh) | `file_path`, `limit` |
| `analyze` | Chạy 1 trong **8 phân tích** → xuất báo cáo | `command`, `file_path`, `brand_map?` |
| `list_reports` | Liệt kê báo cáo đã sinh (Excel + HTML) + URL | — |
| `read_report` | Đọc nội dung 1 báo cáo **.html** (text, bỏ CSS/JS) | `name` |

`platform`: `douyin` \| `xiaohongshu` \| `kuaishou` \| `bilibili` \| `weibo` \| `tieba` \| `zhihu`.
`analyze.command`: `trend` \| `insight` \| `koc` \| `opportunity` \| `seasonal` \| `price` \| `sov` \| `angle`.

## 4. Luồng dùng điển hình (Claude Code tự thực hiện)

**Nghiên cứu trend cho team content:**
1. `crawl_search(platform="douyin", keywords="护肤教程,油皮")` → chờ crawl xong, trả file mới nhất.
2. `list_results(platform="douyin")` → lấy `path` của file (thêm tiền tố `data/`).
3. `analyze(command="trend", file_path="data/douyin/json/search_contents_...json")`
   → trả `report_urls`.
4. `read_report("trend_report.html")` → Claude đọc thẳng: top bài, hook, chỉ số,
   link video để lấy ý tưởng/clone; hoặc mở `report_urls` (.html) trong trình duyệt.

**Thẩm định KOC:** `crawl_creator(...)` → `analyze(command="koc", ...)` → `read_report("koc_report.html")`.

## 5. Ranh giới (bắt buộc)

- Chỉ **nghiên cứu nội bộ dữ liệu công khai**, không tái xuất bản/nhân bản nội dung người khác.
- Giữ tải mặc định (concurrency = 1), có nghỉ giữa request — không quét quy mô lớn.
- Creator luôn **ẩn danh** (`creator_hash`), tuân thủ Nghị định 13/2023.
- Tier 3 (multi-account, xoay proxy) **đang khoá** — xem [CLAUDE.md](../../CLAUDE.md).

## 6. Biến môi trường

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `MEDIACRAWLER_API` | URL REST backend | `http://127.0.0.1:8080` |
| `MCP_TRANSPORT` | `stdio` \| `streamable-http` \| `sse` | `stdio` |
| `MCP_HOST` / `MCP_PORT` | Địa chỉ bind khi chạy HTTP | `127.0.0.1` / `8765` |

Đọc từ `.env` ở gốc dự án (tự nạp). Xem thêm `.env.example`.
