# -*- coding: utf-8 -*-
"""
DigiAds · Angle → Video Prompt Library
======================================
Nối "Angle Library" (dữ liệu đã cào & chuẩn hoá từ MediaCrawler) vào pipeline
AI video hiện có (FACTORY OS / AutoVid) để sinh clip 15–20s bán hàng TikTok Shop.

Ý tưởng: MediaCrawler cho anh NGUYÊN LIỆU thật (hook, format, nỗi đau, nhạc trending).
Module này là BỘ NÃO biến nguyên liệu đó thành BRIEF VIDEO chuẩn JSON mà
pipeline tiêu thụ được — qua một chuỗi 6 prompt có thể gọi độc lập hoặc nối chuỗi.

Cách dùng nhanh
---------------
    from angle_to_video_prompts import build_script_prompt, VIDEO_BRIEF_SCHEMA
    msgs = build_script_prompt(concept, product_brief, duration=18)
    # -> đưa msgs["system"], msgs["user"] vào Anthropic Messages API
    # -> model trả JSON theo VIDEO_BRIEF_SCHEMA -> nạp thẳng vào AutoVid

Nguyên tắc: chỉ dùng angle như CẢM HỨNG/khung. Không sao chép câu chữ, nhạc bản
quyền, hình ảnh gốc. Mọi output phải bản địa hoá tiếng Việt cho thị trường VN.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json

MODEL_DEFAULT = "claude-sonnet-4-6"

# ----------------------------------------------------------------------------
# 1. SCHEMAS  (đầu vào Angle Library  +  đầu ra Video Brief cho pipeline)
# ----------------------------------------------------------------------------

@dataclass
class Angle:
    """Một bản ghi đã chuẩn hoá từ MediaCrawler (CS5 - Angle Library)."""
    angle_id: str
    platform: str                 # dy | xhs | ...
    source_keyword: str
    hook: str                     # 3s đầu / tiêu đề gây chú ý
    format: str                   # vd: before-after, POV, unboxing, list, review
    pain_or_desire: str           # nỗi đau / mong muốn cốt lõi
    cta_observed: str = ""        # CTA quan sát được
    sound_ref: str = ""           # nhạc/nền trending (từ music_download_url)
    metrics: dict = field(default_factory=dict)  # {like, comment, share, collect}
    lang: str = "zh"

    def brief(self) -> str:
        m = self.metrics or {}
        return (f"[{self.angle_id}] format={self.format} | hook=\"{self.hook}\" | "
                f"pain/desire={self.pain_or_desire} | cta=\"{self.cta_observed}\" | "
                f"sound={self.sound_ref or '-'} | "
                f"metrics(like/cmt/share/save)="
                f"{m.get('like','?')}/{m.get('comment','?')}/{m.get('share','?')}/{m.get('collect','?')}")


# Schema JSON mà pipeline AutoVid/FACTORY OS tiêu thụ. Model PHẢI trả đúng khuôn này.
VIDEO_BRIEF_SCHEMA = {
    "concept_id": "string",
    "product_focus": "string",
    "angle_type": "pain | desire | proof | curiosity | comparison | trend",
    "hook_line": "câu mở 3 giây đầu (on-screen + thoại)",
    "duration_sec": "int 15-20",
    "aspect_ratio": "9:16",
    "language": "vi-VN",
    "scenes": [
        {
            "t_start": "float giây",
            "t_end": "float giây",
            "visual": "mô tả cảnh/động tác/khung hình cho AI video",
            "onscreen_text": "chữ nổi trên màn",
            "voiceover": "lời đọc tiếng Việt, khẩu ngữ, ngắn"
        }
    ],
    "cta": "câu kêu gọi hành động gắn TikTok Shop",
    "sound_ref": "gợi ý nhạc/nền (dùng thư viện hợp lệ, không bê nhạc bản quyền)",
    "hashtags": ["#..."],
    "source_angle_ids": ["truy vết về Angle Library"],
    "compliance_flags": ["cảnh báo nếu có: y tế/khẳng định quá đà/bản quyền..."]
}

# ----------------------------------------------------------------------------
# 2. VAI TRÒ HỆ THỐNG  (system preamble dùng chung)
# ----------------------------------------------------------------------------

SYSTEM_STRATEGIST = (
    "Bạn là Content Strategist của DigiAds — agency media & bán hàng tại Việt Nam, "
    "chuyên sản xuất video ngắn 15–20s cho TikTok Shop. Bạn giỏi biến insight thô "
    "thành kịch bản bán được hàng, bám 3 giây hook, khẩu ngữ Việt tự nhiên, và luôn "
    "gắn CTA về gian hàng. Bạn KHÔNG sao chép câu chữ/nhạc bản quyền — chỉ lấy angle "
    "làm khung rồi sáng tạo mới, bản địa hoá cho người Việt. Khi được yêu cầu trả JSON, "
    "bạn chỉ trả JSON hợp lệ, không thêm lời dẫn hay dấu ```."
)


def _msgs(user: str, system: str = SYSTEM_STRATEGIST) -> dict:
    return {"system": system, "user": user, "model": MODEL_DEFAULT}


# ----------------------------------------------------------------------------
# 3. CHUỖI 6 PROMPT  (mỗi hàm trả {system, user, model} -> Messages API)
# ----------------------------------------------------------------------------

def build_normalize_prompt(raw_record: dict) -> dict:
    """[Stage 0] Chuẩn hoá 1 record thô từ MediaCrawler -> đối tượng Angle (JSON)."""
    user = f"""Đây là 1 bản ghi thô cào từ nền tảng (đã ẩn danh người dùng):
{json.dumps(raw_record, ensure_ascii=False, indent=2)}

Trích thành 1 Angle theo đúng khoá sau, trả JSON thuần:
{{"angle_id","platform","source_keyword","hook","format","pain_or_desire",
"cta_observed","sound_ref","metrics":{{"like","comment","share","collect"}},"lang"}}

- "hook": rút gọn 3s đầu/tiêu đề gây chú ý (giữ ý, không cần dịch).
- "format": phân loại ngắn gọn (before-after / POV / unboxing / list / review / demo / storytime...).
- "pain_or_desire": nỗi đau hoặc mong muốn cốt lõi mà nội dung chạm tới.
- Nếu thiếu trường nào để "" hoặc {{}}."""
    return _msgs(user)


def build_concept_prompt(angles: list[Angle], product_brief: str, n: int = 3) -> dict:
    """[Stage 1] Từ các angle top + sản phẩm -> N concept video bản địa hoá VN."""
    ang = "\n".join(a.brief() for a in angles)
    user = f"""SẢN PHẨM CẦN BÁN:
{product_brief}

ANGLE THAM CHIẾU (đã lọc top hiệu suất từ Angle Library):
{ang}

Nhiệm vụ: đề xuất {n} concept video 15–20s cho TikTok Shop VN, mỗi concept LẤY CẢM HỨNG
từ angle (không sao chép), bản địa hoá cho người Việt. Trả JSON là mảng, mỗi phần tử:
{{"concept_id","angle_type","big_idea","hook_line",
"why_it_sells","source_angle_ids":[...]}}

- angle_type ∈ pain|desire|proof|curiosity|comparison|trend.
- hook_line: câu mở 3s, khẩu ngữ, dừng-lướt được.
- why_it_sells: 1 câu vì sao chuyển đổi tốt cho sản phẩm này."""
    return _msgs(user)


def build_script_prompt(concept: dict, product_brief: str, duration: int = 18) -> dict:
    """[Stage 2] Concept -> kịch bản shot-by-shot 15–20s theo VIDEO_BRIEF_SCHEMA."""
    user = f"""CONCEPT ĐÃ CHỌN:
{json.dumps(concept, ensure_ascii=False, indent=2)}

SẢN PHẨM:
{product_brief}

Viết kịch bản video {duration}s (dọc 9:16, tiếng Việt) theo ĐÚNG schema JSON sau, trả JSON thuần:
{json.dumps(VIDEO_BRIEF_SCHEMA, ensure_ascii=False, indent=2)}

Ràng buộc bắt buộc:
- 0–3s: hook_line phải khựng người xem lại (câu hỏi/số liệu/before-after/nghịch lý).
- Chia 3–5 scene, mỗi scene có visual đủ cụ thể để AI video dựng được.
- voiceover: khẩu ngữ Việt, mỗi câu ≤ 12 chữ, đọc lọt trong thời lượng scene.
- onscreen_text: ngắn, nổi bật lợi ích/con số.
- cta: gắn hành động vào giỏ TikTok Shop ("giỏ vàng", "nhấn giỏ", "link dưới video").
- compliance_flags: liệt kê nếu có khẳng định quá đà (đặc biệt mỹ phẩm/thực phẩm/sức khoẻ)."""
    return _msgs(user)


def build_variation_prompt(video_brief: dict, n: int = 4) -> dict:
    """[Stage 3] 1 kịch bản -> N biến thể hook+CTA để A/B test (giữ nguyên phần thân)."""
    user = f"""KỊCH BẢN GỐC (JSON):
{json.dumps(video_brief, ensure_ascii=False, indent=2)}

Tạo {n} biến thể để A/B test. Chỉ thay ĐỔI hook_line và cta (giữ nguyên scenes/product),
mỗi biến thử một cơ chế tâm lý khác nhau (khan hiếm, tò mò, bằng chứng xã hội, so sánh...).
Trả JSON mảng, mỗi phần tử: {{"variant_id","mechanism","hook_line","cta"}}."""
    return _msgs(user)


def build_compliance_prompt(video_brief: dict, brand_rules: str = "") -> dict:
    """[Stage 4] Rà chính sách nền tảng + brand + bản quyền trước khi sản xuất."""
    user = f"""KỊCH BẢN CẦN RÀ (JSON):
{json.dumps(video_brief, ensure_ascii=False, indent=2)}

QUY TẮC THƯƠNG HIỆU / KHÁCH HÀNG (nếu có):
{brand_rules or "(không có, dùng chuẩn an toàn chung)"}

Rà soát và trả JSON:
{{"pass": true/false,
 "issues": [{{"type":"policy|medical_claim|copyright|brand|misleading",
              "where":"trường/scene nào","detail":"...","fix":"cách sửa gợi ý"}}],
 "safe_rewrite": "nếu fail, viết lại phần vi phạm cho an toàn"}}

Lưu ý VN: cẩn trọng khẳng định 'trị dứt điểm', 'cam kết 100%', so sánh hạ bệ đối thủ,
dùng nhạc/nhân vật có bản quyền, và nội dung hướng tới trẻ vị thành niên."""
    return _msgs(user)


def build_scorecard_prompt(video_brief: dict) -> dict:
    """[Stage 5] Chấm điểm sức mạnh hook & khả năng chuyển đổi trước khi tốn chi phí dựng."""
    user = f"""KỊCH BẢN (JSON):
{json.dumps(video_brief, ensure_ascii=False, indent=2)}

Chấm điểm dự đoán (0–10) và trả JSON:
{{"hook_strength":0-10,"clarity":0-10,"desire":0-10,"cta_strength":0-10,
 "scroll_stop_prob":"low|medium|high",
 "top_fix":"1 chỉnh sửa tác động lớn nhất",
 "verdict":"ship | revise | kill"}}

Đánh giá khắt khe như một buyer TikTok Shop khó tính đang lướt feed."""
    return _msgs(user)


# ----------------------------------------------------------------------------
# 4. ĐỊNH NGHĨA CHUỖI PIPELINE  (để agent/arq điều phối)
# ----------------------------------------------------------------------------

PIPELINE = [
    ("normalize", "Record thô MediaCrawler  → Angle chuẩn hoá"),
    ("concept",   "Angle top + sản phẩm      → N concept bản địa hoá"),
    ("script",    "Concept                    → Video Brief 15–20s (JSON)"),
    ("variation", "Video Brief                → N biến thể hook/CTA (A/B)"),
    ("compliance","Video Brief                → Rà policy/brand/bản quyền"),
    ("scorecard", "Video Brief                → Điểm hook & verdict ship/kill"),
]


def run_chain_example():
    """Ví dụ minh hoạ chuỗi — CHƯA gọi model, chỉ dựng prompt để anh cắm client vào."""
    angle = Angle(
        angle_id="dy_0007", platform="dy", source_keyword="护肤教程",
        hook="Da dầu mà vẫn bóng nhờn? 90% là làm sai bước này",
        format="before-after", pain_or_desire="hết bóng nhờn, kiềm dầu cả ngày",
        cta_observed="链接在评论区", sound_ref="trend_bgm_2231",
        metrics={"like": 128000, "comment": 4200, "share": 9800, "collect": 31000},
        lang="vi",
    )
    product_brief = ("Serum kiềm dầu X cho da dầu mụn, giá 199k, bán trên TikTok Shop, "
                     "USP: kiềm dầu 8 tiếng, không gây khô căng.")

    print("=== ANGLE ===\n" + angle.brief() + "\n")
    concept = {
        "concept_id": "c1", "angle_type": "pain",
        "big_idea": "Vạch trần bước skincare sai khiến da càng dầu",
        "hook_line": "Bạn càng rửa mặt, da càng đổ dầu — đây là lý do",
        "why_it_sells": "Đánh trúng nỗi bực hằng ngày, mở đường cho giải pháp sản phẩm.",
        "source_angle_ids": ["dy_0007"],
    }
    for name, prompt in [
        ("SCRIPT", build_script_prompt(concept, product_brief, 18)),
        ("VARIATION", build_variation_prompt({"...": "video_brief_json"})),
        ("SCORECARD", build_scorecard_prompt({"...": "video_brief_json"})),
    ]:
        print(f"=== PROMPT: {name} (user) ===")
        print(prompt["user"][:600] + "…\n")


if __name__ == "__main__":
    run_chain_example()
