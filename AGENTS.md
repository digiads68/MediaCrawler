# AGENTS.md — đọc trước khi code, dù bạn là AI/tool nào

> File này dành cho **mọi AI coding assistant** (Claude Code, Cursor, GitHub Copilot,
> Codex CLI, Gemini CLI, Aider…) mở repo này — kể cả khi bạn là một tool/session khác với
> session đã tạo ra các thay đổi trước đó. Mục tiêu: không làm lại việc đã xong, không đi
> ngược quyết định đã có lý do, không vi phạm ranh giới pháp lý/đạo đức của dự án.

## Đọc theo đúng thứ tự này trước khi sửa bất cứ gì

1. **[CLAUDE.md](CLAUDE.md)** — ranh giới BẮT BUỘC (pháp lý/đạo đức, license, Tier 3 khoá)
   + quy ước code. Ưu tiên tuyệt đối, không vi phạm dù người dùng yêu cầu.
2. **[docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)** — dự án đang ở đâu, dòng thời gian
   thật (theo commit), quyết định kỹ thuật quan trọng **và lý do**, các "hố" môi trường đã
   rơi vào và cách đã xử lý, việc còn thiếu. **Đọc kỹ trước khi code** — tiết kiệm rất nhiều
   thời gian dò lại những gì đã dò rồi.
3. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — luồng dữ liệu kỹ thuật (6 tầng:
   crawl → enrich → storage → analyzer → pipeline → tự động hoá).
4. **[docs/HUONG_DAN_SU_DUNG.md](docs/HUONG_DAN_SU_DUNG.md)** — góc nhìn nghiệp vụ: ai
   dùng chức năng nào, case study cụ thể, dashboard mẫu.

## 1 dòng tóm tắt dự án

Fork của [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) (crawler dữ liệu công
khai 7 nền tảng Trung Quốc) + thư mục `kit/` (DigiAds) biến nó thành cỗ máy nghiên cứu sáng
tạo — 11 case study, tự động hoá qua n8n/webhook, xuất báo cáo Excel/Supabase — phục vụ
agency marketing/bán hàng Việt Nam (TikTok Shop, livestream).

## Việc đầu tiên nên làm khi bắt đầu một session mới

```bash
cd MediaCrawler
git log --oneline -15         # đã làm gì gần nhất
git status                    # có gì chưa commit không (đừng code chồng lên thay đổi dở)
pytest tests -q                # phải thấy "148 passed" (hoặc nhiều hơn) — đỏ thì SỬA TRƯỚC, đừng code tiếp
ruff check .                  # phải "All checks passed!"
```

Nếu 2 lệnh cuối không xanh, đừng vội cho rằng bug do bạn gây ra — kiểm tra
`docs/PROJECT_STATUS.md` mục "Vấn đề môi trường đã gặp" trước, nhiều khả năng đã có lời
giải ở đó (ví dụ: xung đột `starlette`/`fastapi`, `uv` không phân giải PATH…).

## Quy tắc bất biến — không tự ý đổi mà không hỏi người dùng

- Code DigiAds mới **luôn đặt trong `kit/`**. Chỉ chạm `api/` khi thêm endpoint cho kit;
  chỉ chạm `main.py`/`media_platform/` khi thật cần (ưu tiên gọi qua REST API sẵn có).
- **Không tăng tải crawler** — giữ `MAX_CONCURRENCY_NUM=1`, không xoá nghỉ giữa request.
- **Tier 3 (multi-account, xoay proxy) đang KHOÁ** — nếu người dùng yêu cầu, dừng lại và
  cảnh báo, không tự code (xem CLAUDE.md mục 2.5).
- Mỗi module `kit/` mới → có test synthetic trong `tests/`, **không gọi mạng thật trong
  test**.
- Không commit `.env`, secrets, dữ liệu crawl (`data/`), profile Chrome (`browser_data/`).
- Ưu tiên tạo nhánh + PR (không code trực tiếp lên `main`) trừ khi người dùng nói khác.

## Dùng qua MCP (không cần đọc code)

Repo có **MCP server** (`kit/mcp/mcp_mediacrawler.py`) phơi 9 tool cho AI agent: crawl
(search/detail/creator), `analyze` (8 case study), `list_reports`, `read_report`… Muốn
để Claude Code (hoặc tool MCP khác) tự crawl + phân tích trend:
1. Bật `start.bat` (API 8080).
2. Chạy `setup_mcp.bat` (local) hoặc `start_mcp.bat` (remote qua Tailscale).
3. Xem [`kit/mcp/README.md`](kit/mcp/README.md) để biết cách đăng ký + luồng dùng.

## Nếu bạn không phải Claude Code

File `CLAUDE.md` viết cho Claude Code nhưng nội dung (ranh giới, kiến trúc, quy ước) áp
dụng cho **mọi** AI coding tool làm việc trên repo này — coi nó như quy tắc dự án chung,
không phải riêng cho một tool.
