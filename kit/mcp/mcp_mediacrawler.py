# -*- coding: utf-8 -*-
"""
MCP server cho MediaCrawler (bản fork có REST API).

Mục đích: bọc một lớp MCP mỏng lên REST API sẵn có của MediaCrawler
(http://127.0.0.1:8080) để AI agent (Claude / Paperclip) tự gọi được:
  "quét trend Douyin ngành X" -> nhận dữ liệu (đã ẩn danh) -> tự viết brief.

⚠ NGUYÊN TẮC (đọc kỹ):
  - Chỉ dùng cho NGHIÊN CỨU NỘI BỘ dữ liệu công khai. Không tái xuất bản.
  - Giữ concurrency = 1, tôn trọng nghỉ giữa request. Không quét quy mô lớn.
  - Tuân thủ ToS nền tảng + Nghị định 13/2023 (dữ liệu cá nhân).

Chạy độc lập (local, stdio — cho Claude Code/Desktop cùng máy):
    python kit/mcp/mcp_mediacrawler.py
Chạy remote qua Tailscale (HTTP — cho máy khác kết nối vào):
    MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8765 python kit/mcp/mcp_mediacrawler.py
Cần: pip install "mcp[cli]" httpx python-dotenv
Yêu cầu: API MediaCrawler đang chạy  ->  uvicorn api.main:app --port 8080
Tài liệu kết nối chi tiết: kit/mcp/README.md
"""

import asyncio
import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# Nạp .env ở gốc dự án (portable: suy từ __file__, copy thư mục đi đâu cũng chạy).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

# ---- Cấu hình ----------------------------------------------------------------
API_BASE = os.environ.get("MEDIACRAWLER_API", "http://127.0.0.1:8080")
POLL_INTERVAL_SEC = 5          # nhịp hỏi trạng thái
POLL_TIMEOUT_SEC = 20 * 60     # trần thời gian chờ 1 lần crawl
DEFAULT_MAX_NOTES = 50         # trần mặc định an toàn, tránh quét nặng

# Transport: 'stdio' (mặc định, local) | 'streamable-http' | 'sse' (remote/Tailscale)
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8765"))

# Lệnh analyzer hợp lệ (khớp router /kit/analyze)
ANALYZE_COMMANDS = ("trend", "insight", "koc", "opportunity",
                    "seasonal", "price", "sov", "angle")

mcp = FastMCP("mediacrawler", host=MCP_HOST, port=MCP_PORT)

# Bảng mã nền tảng cho agent dễ đọc
PLATFORMS = {
    "douyin": "dy", "dy": "dy",
    "xiaohongshu": "xhs", "xhs": "xhs", "red": "xhs",
    "kuaishou": "ks", "ks": "ks",
    "bilibili": "bili", "bili": "bili",
    "weibo": "wb", "wb": "wb",
    "tieba": "tieba", "zhihu": "zhihu",
}


def _norm_platform(p: str) -> str:
    key = p.strip().lower()
    if key not in PLATFORMS:
        raise ValueError(f"Nền tảng không hỗ trợ: {p}. Chọn: {sorted(set(PLATFORMS.values()))}")
    return PLATFORMS[key]


async def _start(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API_BASE}/api/crawler/start", json=payload)
        r.raise_for_status()
        return r.json()


async def _status() -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/api/crawler/status")
        r.raise_for_status()
        return r.json()


async def _wait_until_done() -> dict:
    """Chờ crawl chạy xong (status quay về idle) hoặc lỗi."""
    waited = 0
    while waited < POLL_TIMEOUT_SEC:
        st = await _status()
        if st.get("status") in ("idle", "error"):
            return st
        await asyncio.sleep(POLL_INTERVAL_SEC)
        waited += POLL_INTERVAL_SEC
    return {"status": "timeout", "error_message": "Vượt trần thời gian chờ."}


async def _newest_file(platform: str) -> dict | None:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/api/data/files", params={"platform": platform})
        r.raise_for_status()
        files = r.json().get("files", [])
    if not files:
        return None
    return sorted(files, key=lambda f: f.get("modified_at", ""), reverse=True)[0]


async def _read_file(path: str, limit: int = 50) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API_BASE}/api/data/files/{path}",
                        params={"preview": True, "limit": limit})
        r.raise_for_status()
        return r.json()


async def _run(payload: dict, platform: str, preview: int) -> dict:
    """Khởi động crawl -> chờ xong -> trả về file mới nhất + preview."""
    try:
        await _start(payload)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return {"ok": False, "error": "Đang có một tiến trình crawl khác chạy. Hãy chờ hoặc gọi stop."}
        return {"ok": False, "error": f"Không khởi động được: {e}"}

    done = await _wait_until_done()
    if done.get("status") == "error":
        return {"ok": False, "error": done.get("error_message", "Crawl lỗi.")}

    newest = await _newest_file(platform)
    if not newest:
        return {"ok": True, "note": "Crawl xong nhưng chưa thấy file kết quả.", "status": done}

    data = await _read_file(newest["path"], limit=preview)
    return {
        "ok": True,
        "file": newest,
        "preview": data,
        "reminder": "Dữ liệu đã ẩn danh nickname. Chỉ dùng để nghiên cứu, không tái xuất bản.",
    }


# ---- TOOLS phơi ra cho agent -------------------------------------------------

@mcp.tool()
async def crawl_search(
    platform: str,
    keywords: str,
    max_notes: int = DEFAULT_MAX_NOTES,
    with_comments: bool = True,
    with_sub_comments: bool = False,
    save_option: str = "excel",
    preview_rows: int = 50,
) -> dict:
    """
    Quét nội dung theo TỪ KHOÁ (chế độ search) — dùng cho radar trend & product research.
    platform: douyin | xiaohongshu | kuaishou | bilibili | weibo | tieba | zhihu
    keywords: các cụm từ, ngăn cách bằng dấu phẩy, ví dụ "护肤教程,穿搭".
    """
    p = _norm_platform(platform)
    payload = {
        "platform": p, "crawler_type": "search", "keywords": keywords,
        "enable_comments": with_comments, "enable_sub_comments": with_sub_comments,
        "save_option": save_option, "max_notes_count": max(1, min(max_notes, 500)),
        "headless": True,
    }
    return await _run(payload, p, preview_rows)


@mcp.tool()
async def crawl_detail(
    platform: str,
    post_ids: str,
    with_comments: bool = True,
    with_sub_comments: bool = True,
    max_comments: int = 500,
    save_option: str = "jsonl",
    preview_rows: int = 50,
) -> dict:
    """
    Bóc sâu 1 hoặc nhiều POST/VIDEO viral theo ID (chế độ detail) — dùng cho voice-of-customer.
    post_ids: danh sách ID, ngăn cách bằng dấu phẩy.
    Lưu jsonl để MediaCrawler tự sinh word cloud từ comment.
    """
    p = _norm_platform(platform)
    payload = {
        "platform": p, "crawler_type": "detail", "specified_ids": post_ids,
        "enable_comments": with_comments, "enable_sub_comments": with_sub_comments,
        "save_option": save_option, "max_comments_count": max(1, min(max_comments, 2000)),
        "headless": True,
    }
    return await _run(payload, p, preview_rows)


@mcp.tool()
async def crawl_creator(
    platform: str,
    creator_ids: str,
    with_comments: bool = False,
    save_option: str = "excel",
    preview_rows: int = 50,
) -> dict:
    """
    Quét trang NHÀ SÁNG TẠO theo ID (chế độ creator) — dùng để thẩm định KOC / soi đối thủ.
    creator_ids: danh sách ID creator, ngăn cách bằng dấu phẩy.
    """
    p = _norm_platform(platform)
    payload = {
        "platform": p, "crawler_type": "creator", "creator_ids": creator_ids,
        "enable_comments": with_comments, "save_option": save_option,
        "headless": True,
    }
    return await _run(payload, p, preview_rows)


@mcp.tool()
async def get_status() -> dict:
    """Kiểm tra trạng thái tiến trình crawl (idle / running / stopping / error)."""
    return await _status()


@mcp.tool()
async def list_results(platform: str | None = None) -> dict:
    """Liệt kê các file dữ liệu đã xuất, lọc theo nền tảng nếu cần."""
    params = {}
    if platform:
        params["platform"] = _norm_platform(platform)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/api/data/files", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def read_result(file_path: str, limit: int = 100) -> dict:
    """Đọc nội dung (preview) một file kết quả đã ẩn danh để agent phân tích."""
    return await _read_file(file_path, limit=limit)


@mcp.tool()
async def analyze(
    command: str,
    file_path: str,
    brand_map: str | None = None,
) -> dict:
    """
    Chạy 1 trong 8 phân tích DigiAds trên file dữ liệu đã cào, trả file báo cáo.

    command: trend | insight | koc | opportunity | seasonal | price | sov | angle
      - trend  : radar trend + format thắng thế + sound đang lên (CS1/CS10/CS5)
      - insight: ngân hàng bình luận / voice-of-customer (CS2, cần file comment)
      - koc    : chấm điểm creator + KOC đang lên (CS3/CS9)
      - opportunity: bản đồ ngách 4 vùng cơ hội (CS4/CS6)
      - seasonal   : sóng mùa vụ theo tuần (CS7)
      - price  : giá & mồi khuyến mãi đối thủ (CS8)
      - sov    : share of voice theo brand (CS11, cần brand_map)
      - angle  : xuất angle_library.jsonl nạp pipeline AI video (CS5)
    file_path: đường dẫn file dữ liệu, TƯƠNG ĐỐI gốc repo, ví dụ
      "data/douyin/json/search_contents_2026-07-21.json"
      (lấy từ list_results -> path, nhớ thêm tiền tố "data/").
    brand_map: chỉ dùng cho sov — đường dẫn brand_map.json (mặc định
      "kit/config/brand_map.json").

    Trả về danh sách file báo cáo. Báo cáo HTML mở/đọc được tại
    {API_BASE}/kit/reports/{tên_file} — agent có thể fetch URL đó để đọc phân
    tích trực quan (bảng chỉ số, hook, link video để lấy ý tưởng/clone).
    """
    if command not in ANALYZE_COMMANDS:
        return {"ok": False, "error": f"command phải thuộc {ANALYZE_COMMANDS}"}
    body: dict = {"command": command, "file": file_path}
    if command == "sov":
        body["brand_map"] = brand_map or "kit/config/brand_map.json"
    async with httpx.AsyncClient(timeout=300) as c:
        try:
            r = await c.post(f"{API_BASE}/kit/analyze", json=body)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:  # noqa: BLE001
                detail = e.response.text[:200]
            return {"ok": False, "error": f"Phân tích lỗi ({e.response.status_code}): {detail}"}
    res = r.json()
    reports = res.get("reports", [])
    return {
        "ok": True,
        "command": command,
        "rows": res.get("rows"),
        "reports": reports,
        "report_urls": [f"{API_BASE}/kit/reports/{n}" for n in reports],
        "hint": "Fetch report_urls (.html) để đọc phân tích trực quan; .xlsx để tải số liệu.",
    }


@mcp.tool()
async def list_reports() -> dict:
    """Liệt kê các file báo cáo đã sinh (Excel + HTML), kèm URL mở/tải."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/kit/reports")
        r.raise_for_status()
        data = r.json()
    for item in data.get("reports", []):
        item["full_url"] = f"{API_BASE}{item['url']}"
    return data


@mcp.tool()
async def read_report(name: str) -> dict:
    """
    Đọc nội dung 1 báo cáo HTML (text) để agent phân tích trực tiếp trong hội thoại.

    name: tên file, ví dụ "trend_report.html" (lấy từ analyze/list_reports).
    Trả text đã cắt gọn (bỏ CSS/JS) tối đa ~40k ký tự.
    """
    if not name.lower().endswith(".html"):
        return {"ok": False, "error": "Chỉ đọc được báo cáo .html. Dùng list_reports để lấy tên."}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API_BASE}/kit/reports/{name}")
        r.raise_for_status()
        html = r.text
    # Cắt gọn: bỏ <style>/<script> để agent đọc nội dung, không tốn token vào CSS/JS
    import re
    txt = re.sub(r"<style[\s\S]*?</style>", "", html)
    txt = re.sub(r"<script[\s\S]*?</script>", "", txt)
    return {"ok": True, "name": name, "html": txt[:40000],
            "url": f"{API_BASE}/kit/reports/{name}"}


if __name__ == "__main__":
    # stdio: cắm trực tiếp vào Claude Code/Desktop cùng máy.
    #   -> TUYỆT ĐỐI không ghi gì ra stdout ở mode này: stdout là kênh JSON-RPC.
    # streamable-http / sse: chạy như service, máy khác kết nối qua Tailscale.
    if MCP_TRANSPORT in ("streamable-http", "sse"):
        # Windows console mặc định cp1252 -> ép UTF-8 để in tiếng Việt không lỗi
        # (an toàn vì mode HTTP không dùng stdout làm kênh giao thức).
        import sys
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(f"[MCP] mediacrawler chay {MCP_TRANSPORT} tai {MCP_HOST}:{MCP_PORT} "
              f"(API backend: {API_BASE})", flush=True)
    mcp.run(transport=MCP_TRANSPORT)
