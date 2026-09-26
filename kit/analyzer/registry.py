# -*- coding: utf-8 -*-
"""
Danh mục dashboard — MỘT nguồn sự thật cho toàn hệ.

Trước file này, danh sách lệnh bị nhân bản ở 5 nơi (`kit/queue/tasks.py`,
`kit/mcp/mcp_mediacrawler.py`, `api/routers/kit.py`, `webui/src/lib/api.ts`,
`kit/analyzer/capabilities.py`) nên thêm 1 lệnh phải sửa 6 chỗ và rất dễ lệch.
Nay các nơi đó đọc từ đây; hai chỗ không thể đọc trực tiếp (Literal của pydantic
và type của TypeScript) có test chặn lệch.

Bảng này cũng là catalog để AI agent biết "dashboard nào cần dữ liệu gì" ở Pha 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DataNeeds:
    """Điều kiện dữ liệu để dashboard chạy có nghĩa."""

    # "posts" = file bài đăng, "comments" = file bình luận
    kind: str = "posts"
    # Chỉ chạy được với các nền tảng này (rỗng = mọi nền tảng)
    platforms: tuple[str, ...] = ()
    # Số từ khoá tối thiểu trong 1 file (so sánh ngách cần >= 2)
    min_keywords: int = 0
    # Số tuần dữ liệu tối thiểu (mùa vụ / SOV cần >= 2)
    min_weeks: int = 0
    # Cần chỉ số tương tác cấp bài đăng
    needs_engagement: bool = True
    # Cần trục thời gian (created_at)
    needs_time: bool = False
    # Cần ảnh cover
    needs_cover: bool = False
    # Cần nhiều file (so sánh chéo nền tảng)
    multi_file: bool = False
    # `save_option` bắt buộc khi cào để có dữ liệu này
    save_option: str = ""
    # Ghi chú hiển thị cho người dùng / AI
    note: str = ""


@dataclass(frozen=True)
class Dashboard:
    """1 dashboard = 1 lệnh analyzer + 1 báo cáo HTML."""

    command: str
    name: str            # tên hiển thị (tiếng Việt)
    role: str            # vai trò dùng nó
    purpose: str         # mô tả ngắn, 1 dòng
    case: str            # mã case study
    xlsx: tuple[str, ...] = ()
    needs: DataNeeds = field(default_factory=DataNeeds)


# Thứ tự trong tuple = thứ tự hiển thị trên WebUI
DASHBOARDS: tuple[Dashboard, ...] = (
    # --- có từ trước ---
    Dashboard("trend", "Trend Radar", "marketing",
              "Top bài theo điểm trend, format thắng thế, nhạc đang lên",
              "CS1+CS10",
              ("CS1_trend_top_posts.xlsx", "CS1_trend_formats.xlsx")),
    Dashboard("koc", "Creator Audit", "marketing",
              "Soi sâu kênh: nhịp đăng, quỹ đạo, tỷ lệ hit, trụ nội dung; nhiều kênh thì chấm điểm KOC",
              "CS3+CS9",
              ("CS3_koc_scorecard.xlsx", "CS9_rising_creators.xlsx"),
              DataNeeds(needs_time=True,
                        note="Cần >=5 video/creator — dùng Creator Mode.")),
    Dashboard("sov", "Share of Voice", "marketing",
              "Thị phần tiếng nói theo brand, theo tuần",
              "CS11", ("CS11_sov_weekly.xlsx",),
              DataNeeds(needs_time=True, min_weeks=2,
                        note="Cần thêm brand_map.json (rổ brand theo dõi).")),
    Dashboard("opportunity", "Opportunity Map", "marketing",
              "Bản đồ ngách 4 vùng cơ hội theo từ khoá",
              "CS4+CS6", ("CS6_opportunity_map.xlsx",),
              DataNeeds(min_keywords=2)),
    Dashboard("seasonal", "Seasonal Radar", "marketing",
              "Đợt sóng mùa vụ theo tuần",
              "CS7", ("CS7_seasonal_radar.xlsx",),
              DataNeeds(needs_time=True, min_weeks=2, needs_engagement=False)),
    Dashboard("price", "Price & Promo Intel", "sales",
              "Giá và mồi khuyến mãi trích từ nội dung",
              "CS8", ("CS8_price_intel.xlsx",),
              DataNeeds(needs_engagement=False)),
    Dashboard("angle", "Angle Library", "kịch bản",
              "Xuất angle nạp pipeline AI video",
              "CS5", ("angle_library.jsonl",)),

    # --- 5 dashboard mới của Pha 2 ---
    Dashboard("hook", "Hook Lab", "người viết kịch bản",
              "Mổ xẻ câu mở đầu: kiểu hook nào ăn, dài bao nhiêu thì tốt",
              "CS12",
              ("CS12_hook_lab_types.xlsx", "CS12_hook_lab_top.xlsx"),
              DataNeeds(note="Hook ở đây là câu mở của caption — dữ liệu không "
                             "có transcript nên không phải 3 giây đầu video.")),
    Dashboard("playbook", "Format Playbook", "đạo diễn",
              "Từng format: hiệu quả, độ ổn định, ghép với hook nào thì thắng",
              "CS14",
              ("CS14_format_playbook.xlsx", "CS14_format_unclassified.xlsx")),
    Dashboard("sound", "Structure & Hashtag Kit", "editor",
              "Nhạc dùng lại, kết cấu bài (dạng bài, số ảnh) và hashtag: tag ăn, cặp tag đi cùng",
              "CS10+CS13",
              ("CS10_sound_watchlist.xlsx", "CS13_edit_kit.xlsx"),
              DataNeeds(note="Chỉ Douyin xuất link nhạc, và không có tên nhạc. "
                             "Nền tảng khác chỉ chạy được phần kết cấu.")),
    Dashboard("moodboard", "Cover Moodboard", "đạo diễn",
              "Tường ảnh cover của bài top, xếp theo hiệu suất",
              "CS15", ("CS15_cover_moodboard.xlsx",),
              DataNeeds(needs_cover=True,
                        note="Chỉ trưng bày ảnh — phần mềm không phân tích nội "
                             "dung ảnh (không có thị giác máy tính).")),
    Dashboard("crossplatform", "Cross-platform Benchmark", "marketing",
              "So sánh cùng một ngách trên nhiều nền tảng",
              "CS16",
              ("CS16_crossplatform_summary.xlsx", "CS16_crossplatform_posts.xlsx"),
              DataNeeds(multi_file=True,
                        note="Cần chọn thêm file của nền tảng khác — tối thiểu "
                             "2 nền tảng.")),

    # --- nâng cấp ---
    Dashboard("insight", "Voice of Customer Map", "kịch bản / sales",
              "Nhóm nỗi đau, phản đối, câu hỏi và từ vựng khách hay dùng",
              "CS2", ("CS2_insight_bank.xlsx", "CS2_comment_bank.xlsx"),
              DataNeeds(kind="comments", needs_engagement=False,
                        save_option="jsonl",
                        note="Cần file BÌNH LUẬN. File Excel gộp bình luận vào "
                             "sheet phụ mà analyzer không đọc tới, nên phải cào "
                             "với save_option=jsonl.")),
)

BY_COMMAND: dict[str, Dashboard] = {d.command: d for d in DASHBOARDS}
COMMANDS: tuple[str, ...] = tuple(d.command for d in DASHBOARDS)


def get(command: str) -> Dashboard:
    """Tra 1 dashboard theo lệnh; không có -> ValueError kèm gợi ý."""
    try:
        return BY_COMMAND[command]
    except KeyError:
        raise ValueError(
            f"Lệnh không hợp lệ: {command}. Hợp lệ: {', '.join(COMMANDS)}"
        ) from None


def catalog() -> list[dict]:
    """Danh mục dạng JSON cho REST/MCP (Pha 3 dùng làm catalog cho AI)."""
    out = []
    for d in DASHBOARDS:
        n = d.needs
        out.append({
            "command": d.command, "name": d.name, "role": d.role,
            "purpose": d.purpose, "case": d.case, "xlsx": list(d.xlsx),
            "needs": {
                "kind": n.kind,
                "platforms": list(n.platforms),
                "min_keywords": n.min_keywords,
                "min_weeks": n.min_weeks,
                "needs_engagement": n.needs_engagement,
                "needs_time": n.needs_time,
                "needs_cover": n.needs_cover,
                "multi_file": n.multi_file,
                "save_option": n.save_option,
                "note": n.note,
            },
        })
    return out
