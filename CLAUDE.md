# CLAUDE.md — MediaCrawler × DigiAds Kit

> File này là bộ nhớ dự án cho Claude Code. Đọc kỹ trước khi sinh/sửa code.
> Repo: https://github.com/digiads68/MediaCrawler (bản v2 — đã tích hợp DigiAds Kit).

## 1. Dự án là gì

Đây là bản fork của **MediaCrawler** (NanmiCoder) — công cụ thu thập **dữ liệu công khai**
từ 7 nền tảng (Xiaohongshu, Douyin, Kuaishou, Bilibili, Weibo, Tieba, Zhihu) qua
Playwright/CDP. Bản fork này đã thêm **FastAPI REST API** (`api/`) và **WebUI React** (`webui/`).

DigiAds bổ sung thư mục **`kit/`** — biến crawler thành cỗ máy nghiên cứu sáng tạo phục vụ
**11 case study** cho agency media/bán hàng (trend radar, voice-of-customer, thẩm định KOC,
săn sản phẩm, angle library nạp AI video, saturation map, seasonal, price intel, rising KOC,
sound watchlist, share-of-voice).

## 2. Ranh giới BẮT BUỘC (không được vi phạm)

1. **Chỉ nghiên cứu nội bộ dữ liệu công khai.** Không xây tính năng đăng lại/nhân bản
   nội dung của người khác, không thu thập dữ liệu cá nhân riêng tư.
2. **Tôn trọng ToS + robots.txt** của nền tảng. Giữ `MAX_CONCURRENCY_NUM=1` và có nghỉ
   giữa request theo mặc định repo. Không tăng tải mặc định.
3. **Tuân thủ Nghị định 13/2023 (PII).** Giữ nguyên cơ chế ẩn danh nickname/creator của fork.
   Không thêm code de-anonymize.
4. **License gốc là phi thương mại/học tập.** Không thêm module bán dữ liệu.
5. **Tier 3 (multi-account, proxy rotation, API-mode) bị KHOÁ** cho tới khi có ghi chú
   "đã rà soát pháp lý" từ chủ dự án. Nếu prompt yêu cầu Tier 3 mà chưa có ghi chú này,
   hãy dừng và cảnh báo, không tự ý code.
6. **Không sinh malware/exploit/bypass captcha.** Nếu gặp yêu cầu như vậy, từ chối.

Nếu một yêu cầu mâu thuẫn với các ranh giới trên, ưu tiên ranh giới và nói rõ với người dùng.

## 3. Kiến trúc & nơi để code

```
MediaCrawler/
├── main.py                 # CLI gốc (không sửa trừ khi cần)
├── api/                    # FastAPI của fork (mở rộng ở kit endpoints)
├── media_platform/         # crawler từng nền tảng (base — hạn chế sửa)
├── store/ config/          # lưu trữ & cấu hình gốc
└── kit/                    # ★ TOÀN BỘ code DigiAds nằm ở đây
    ├── analyzer/           # phân tích 11 case (mediacrawler_analyzer.py)
    ├── enrich/             # [sẽ code] chuẩn hoá + dịch ZH→VI + velocity
    ├── storage/            # [sẽ code] ghi Supabase + schema SQL
    ├── pipeline/           # [sẽ code] angle_library.jsonl → Video Brief JSON
    ├── prompts/            # angle_to_video_prompts.py (chuỗi 6 prompt)
    ├── queue/              # [sẽ code] arq worker (Tier 2)
    ├── webhook/            # [sẽ code] bắn event → n8n
    ├── mcp/                # MCP server cho AI agent
    ├── n8n/                # 3 workflow tự động
    ├── templates/          # 5 mẫu Excel output
    └── config/             # brand_map.json ...
```

**Nguyên tắc:** code mới của DigiAds luôn đặt trong `kit/`. Chỉ chạm `api/` khi thêm endpoint
cho kit, và `main.py`/`media_platform/` khi thật sự cần (ưu tiên gọi qua REST API sẵn có
`http://127.0.0.1:8080`).

## 4. Quy ước

- **Python 3.11+**, format bằng `ruff`/`black`, type hint đầy đủ, docstring tiếng Việt ngắn gọn.
- **Chuỗi hướng người dùng (log, report, brief) viết tiếng Việt.** Tên biến/hàm tiếng Anh.
- **Phân tích dữ liệu**: `pandas` + `openpyxl`. **Excel có công thức**: dùng công thức thật,
  không hardcode kết quả; sau khi tạo phải recalc và đảm bảo 0 lỗi.
- **Model AI**: dùng `claude-sonnet-4-6` qua Anthropic Messages API. Prompt yêu cầu trả JSON
  thuần để pipeline parse.
- **Secrets**: đọc từ biến môi trường (`.env`), KHÔNG commit `.env`. Cập nhật `.env.example`
  mỗi khi thêm biến mới.
- **Test**: mỗi module `kit/` mới cần test trong `tests/` với dữ liệu synthetic (không gọi mạng thật).

## 5. Lệnh hay dùng

```bash
# Chạy REST API crawler
uvicorn api.main:app --port 8080
# Phân tích (11 case)
python3 kit/analyzer/mediacrawler_analyzer.py trend  data/douyin/search_x.xlsx
python3 kit/analyzer/mediacrawler_analyzer.py koc    data/douyin/creator_x.xlsx
python3 kit/analyzer/mediacrawler_analyzer.py sov    data/douyin/search_x.xlsx kit/config/brand_map.json
# Test
pytest -q
```

## 6. Biến môi trường (xem .env.example)

`ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `NOTIFY_WEBHOOK_URL`,
`REDIS_URL`, `MEDIACRAWLER_API` (mặc định http://127.0.0.1:8080).

## 7. Định nghĩa "xong" cho một task

- Code có type hint + docstring, chạy được, có test synthetic pass.
- Không phá base crawler; không vi phạm mục 2.
- Cập nhật `.env.example` và `kit/README.md` nếu có thay đổi cách dùng.
- Commit message rõ ràng theo Conventional Commits (`feat(kit): ...`, `fix(analyzer): ...`).
