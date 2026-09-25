# -*- coding: utf-8 -*-
"""
Chuẩn hoá dữ liệu thô MediaCrawler (dùng chung cho analyzer + storage).

Nguồn sự thật duy nhất cho: COUNT_COLS, FORMAT_RULES, các hàm normalize.
Analyzer import lại từ đây — không lặp logic.
"""

from __future__ import annotations

import re

import pandas as pd

# Các cột đếm mà MediaCrawler có thể xuất dạng Text ("1,234", "5678"...)
#
# Phải liệt kê CẢ tên riêng của từng nền tảng, không chỉ tên "chuẩn" của xhs/dy.
# Trước đây thiếu nhóm bilibili/weibo/zhihu nên đã đo được trên dữ liệu thật:
# bài Bilibili có like 472K + favorite 744K + comment 320K + share 91K mà
# `eng_total` chỉ ra 472K, `save_rate`/`share_rate` = 0.
COUNT_COLS: list[str] = [
    # xhs / douyin (tên "chuẩn")
    "liked_count", "comment_count", "share_count", "collected_count",
    # cột của bình luận
    "like_count", "sub_comment_count", "comment_like_count",
    # bilibili
    "video_play_count", "video_favorite_count", "video_share_count",
    "video_comment", "video_coin_count", "video_danmaku", "disliked_count",
    # weibo
    "comments_count", "shared_count",
    # kuaishou (viewd_count: sai chính tả có sẵn trong store, giữ đúng như vậy)
    "viewd_count",
    # zhihu / tieba
    "voteup_count", "total_replay_num",
    # cột canonical do kit/enrich/schema.py sinh
    "m_like", "m_comment", "m_share", "m_save", "m_view",
]

# Bảng nhận diện FORMAT từ tiêu đề/mô tả (khớp chuỗi con, text đã lower()).
#
# Đã đo trên dữ liệu thật trước khi mở rộng: tỉ lệ bài rơi vào "khác" là
# xhs 85% / douyin 75% / bilibili 56% -> phân loại gần như vô dụng. Nguyên nhân
# kép: (1) quá ít từ khoá, (2) khớp theo thứ tự chèn dict nên một từ khoá yếu
# chiếm luôn nhãn. Nay dùng SCORING (xem `tag_format`) + mở rộng từ khoá.
#
# GIỮ NGUYÊN 7 chuỗi nhãn cũ (kể cả "review/測評" viết phồn thể) — nhãn là dữ
# liệu người dùng thấy và có test ghim.
FORMAT_RULES: dict[str, list[str]] = {
    "before-after": ["前后", "对比", "变化", "7天", "30天", "复盘",
                     "trước sau", "thay đổi", "sau 1 tuần", "sau 1 tháng"],
    "review/測評":  ["测评", "评测", "真实", "亲测", "实测", "体验", "值不值",
                     "优缺点", "review", "đánh giá", "có nên", "trải nghiệm"],
    "list/top":     ["清单", "合集", "top", "盘点", "必买", "list", "排行",
                     "大全", "汇总", "推荐", "tổng hợp", "danh sách"],
    "tutorial":     ["教程", "教你", "步骤", "how", "保姆级", "零基础", "手把手",
                     "全流程", "如何", "上手", "攻略", "指南", "从入门",
                     "hướng dẫn", "cách", "các bước"],
    "unboxing":     ["开箱", "到货", "unboxing", "đập hộp"],
    "storytime":    ["故事", "经历", "翻车", "踩雷", "storytime", "亲身经历",
                     "自述", "采访", "探访", "访谈", "坚持",
                     "hành trình", "câu chuyện"],
    "pov/skit":     ["pov", "当你", "剧情", "假如", "如果你", "一人分饰"],
    # --- 6 nhóm mới, rút từ title thật trong data/ ---
    "case/战绩":     ["收入", "战绩", "到账", "入账", "进账", "赚到", "月入",
                     "时薪", "日结", "变现", "月赚",
                     "thu nhập", "doanh thu", "chốt đơn"],
    "warning/劝退":  ["别再", "千万别", "割韭菜", "不可行", "浪费时间", "浪费生命",
                     "死了这条心", "骂醒", "避坑", "智商税", "幸存者偏差",
                     "cảnh báo", "đừng", "tránh"],
    "resource/干货": ["干货", "资料", "源码", "开源", "github", "神器", "宝藏",
                     "模板", "素材", "安装包", "附渠道", "思路", "方案", "项目",
                     "tài liệu", "công cụ", "giải pháp"],
    "recruit/招募":  ["加入我们", "速来", "内推", "我们在找", "招聘", "组队",
                     "tuyển", "tìm người"],
    "qna/问答":      ["有什么", "怎么办", "在哪", "请问", "可以吗"],
    "series/合辑":   ["全套", "系列", "合辑"],
}

# Luật dạng regex (bổ sung cho FORMAT_RULES, cùng tham gia tính điểm).
#
# CẨN THẬN với "list/top": chỉ nhận CHỮ SỐ ASCII + lượng từ ĐỒ VẬT.
# TUYỆT ĐỐI không nhận 步 (bước) — "教你三步护肤教程" phải ra `tutorial`,
# và không nhận số Trung (三/两/几) vì "三步" là các bước, không phải danh sách.
FORMAT_REGEX: dict[str, list[str]] = {
    "list/top":     [r"\d+\s*(个|种|款|条|招|平台|软件|方法|网站|工具|集)"],
    "before-after": [r"\d+\s*(天|周|月|年)后", r"第\s*\d+\s*天"],
    # "赚300" / "挣5k" — số tiền không kèm đơn vị vẫn là kể kết quả
    "case/战绩":     [r"[+＋]?\d[\d.,]*\s*(w|万|k|元|块|美金)", r"\$\s*\d",
                     r"(赚|挣|到手|收入|营收)\s*\d"],
    "qna/问答":      [r"[？?]\s*$", r"[？?]{2,}"],
    "series/合辑":   [r"【?全\s*\d+\s*集】?", r"第\s*\d+\s*期"],
    # "3步搞定" — số + 步 là CÁC BƯỚC (tutorial), cố ý KHÔNG cho `list/top` nhận
    "tutorial":     [r"how\s*to", r"\d+\s*步"],
}

# Hoà điểm thì lấy nhãn đứng trước trong danh sách này (cụ thể -> chung chung).
# `tutorial` PHẢI trên `list/top` (xem cảnh báo ở FORMAT_REGEX).
_FORMAT_PRIORITY: tuple[str, ...] = (
    "before-after", "unboxing", "tutorial", "review/測評", "case/战绩",
    "warning/劝退", "storytime", "pov/skit", "resource/干货", "recruit/招募",
    "series/合辑", "list/top", "qna/问答",
)

OTHER_FORMAT = "khác"


def normalize_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Ép cột count Text -> số; parse create_time (epoch s/ms) -> created_at + week ISO."""
    df = df.copy()
    for c in COUNT_COLS:
        if c in df.columns:
            df[c] = (df[c].astype(str)
                     .str.replace(r"[^\d.]", "", regex=True)
                     .replace("", "0").astype(float))
    # Tên cột thời gian đăng khác nhau theo nền tảng: dy/bili/ks/wb dùng
    # `create_time`, còn xhs dùng `time` — nhận cả hai để KOC/Seasonal/SOV
    # (vốn cần trục thời gian) chạy được với mọi nền tảng.
    time_col = next((c for c in ("create_time", "time") if c in df.columns), None)
    if time_col:
        raw = df[time_col]
        if pd.api.types.is_datetime64_any_dtype(raw):
            # Đã là datetime (vd DataFrame đọc bằng read_json mặc định) -> dùng luôn
            created = pd.to_datetime(raw, errors="coerce")
            if getattr(created.dt, "tz", None) is not None:
                created = created.dt.tz_convert(None)
            df["created_at"] = created
        else:
            ts = pd.to_numeric(raw, errors="coerce")
            # MediaCrawler lưu epoch giây hoặc mili-giây tuỳ nền tảng
            ts = ts.where(ts < 1e12, ts / 1000)
            df["created_at"] = pd.to_datetime(ts, unit="s", errors="coerce")
        df["week"] = df["created_at"].dt.strftime("%G-W%V")
    return df


def text_series(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Luôn trả về Series chuỗi cho cột `col` (rỗng nếu file không có cột đó).

    `df.get(col, "")` trả về str khi thiếu cột, khiến `.fillna()`/`.str` phía sau
    nổ AttributeError — gặp với file bình luận (không có title/desc).
    """
    if col in df.columns:
        return df[col].fillna("").astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype="object")


def add_engagement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Thêm eng_total, save_rate, share_rate (tỷ lệ trên like, tránh chia 0).

    Ưu tiên cột canonical `m_*` (do `kit/enrich/schema.py` sinh) vì chỉ đường đó
    mới gom đúng chỉ số của bilibili/weibo/zhihu — 3 nền tảng đặt tên cột khác.
    Không có `m_*` thì chạy y nguyên logic cũ trên `liked_count`/... (đường này
    vẫn cần cho DataFrame dựng trực tiếp trong bộ nhớ, không qua `load()`).
    """
    df = df.copy()
    canonical = "m_like" in df.columns

    def col(name: str) -> object:
        """Series của cột, hoặc 0 nếu nền tảng không có chỉ số đó."""
        return df[name] if name in df.columns else 0

    if canonical:
        like, comment = col("m_like"), col("m_comment")
        share, save = col("m_share"), col("m_save")
    else:
        like, comment = col("liked_count"), col("comment_count")
        share, save = col("share_count"), col("collected_count")

    # Cột thiếu coi như 0 KHI TỔNG (nền tảng đó không đo được chỉ số ấy)
    df["eng_total"] = (_num(like) + _num(comment) + _num(share) + _num(save))

    if hasattr(like, "replace"):
        denom = like.replace(0, pd.NA)
        df["save_rate"] = _num(save) / denom
        df["share_rate"] = _num(share) / denom
    else:
        df["save_rate"] = 0
        df["share_rate"] = 0
    return df


def _num(v: object) -> object:
    """Ép Series về số (NaN -> 0) để cộng tổng; scalar thì trả nguyên."""
    if isinstance(v, pd.Series):
        return pd.to_numeric(v, errors="coerce").fillna(0)
    return v


def _format_text(df: pd.DataFrame) -> pd.Series:
    """Văn bản dùng để dò format: title + desc (fallback content cho weibo)."""
    title = text_series(df, "title")
    if not title.str.strip().any():
        title = text_series(df, "title_text")
    desc = text_series(df, "desc")
    if not desc.str.strip().any():
        desc = text_series(df, "content")
    return (title + " " + desc).str.lower()


# Compile 1 lần, dùng lại cho mọi dòng
_FORMAT_RE: dict[str, list[re.Pattern[str]]] = {
    fmt: [re.compile(p) for p in pats] for fmt, pats in FORMAT_REGEX.items()
}
_PRIORITY_INDEX = {fmt: i for i, fmt in enumerate(_FORMAT_PRIORITY)}


def tag_one_format(text: str) -> str:
    """
    Nhãn format của 1 đoạn văn bản (đã lower).

    Cách chấm: điểm = số luật KHÁC NHAU khớp được (chuỗi con + regex). Nhãn cao
    điểm nhất thắng; hoà thì theo `_FORMAT_PRIORITY`. Dùng scoring thay vì
    "khớp đầu tiên thắng" vì với ~13 nhóm luật thì thứ tự chèn dict quyết định
    kết quả một cách tuỳ tiện — một từ khoá yếu sẽ chiếm nhãn của luật mạnh hơn.
    """
    if not text or not text.strip():
        return OTHER_FORMAT
    scores: dict[str, int] = {}
    for fmt, kws in FORMAT_RULES.items():
        n = sum(1 for k in kws if k in text)
        if n:
            scores[fmt] = scores.get(fmt, 0) + n
    for fmt, pats in _FORMAT_RE.items():
        n = sum(1 for p in pats if p.search(text))
        if n:
            scores[fmt] = scores.get(fmt, 0) + n
    if not scores:
        return OTHER_FORMAT
    best = max(scores.items(),
               key=lambda kv: (kv[1], -_PRIORITY_INDEX.get(kv[0], 999)))
    return best[0]


def tag_format(df: pd.DataFrame) -> pd.DataFrame:
    """Gắn nhãn format nội dung theo FORMAT_RULES + FORMAT_REGEX (title + desc)."""
    df = df.copy()
    df["format"] = _format_text(df).map(tag_one_format)
    return df


_HASHTAG_TAIL_RE = re.compile(r"(\s*#[^\s#]+)+\s*$")
_BRACKET_RE = re.compile(r"^[【\[]([^】\]]{1,20})[】\]]")


def hook_text_of(text: object, *, max_len: int = 60) -> str:
    """
    Câu mở đầu (hook) rút từ tiêu đề/caption.

    Cách làm: bỏ chùm hashtag ở CUỐI (Douyin dán hashtag vào đuôi caption — đã
    kiểm: `title == desc` 100% với Douyin), giữ lại `【…】` ở đầu vì với Bilibili
    đó chính là hook mệnh lệnh (`【建议收藏】`), rồi cắt tại dấu câu đầu tiên.

    Lưu ý trung thực: đây là câu mở của VĂN BẢN, không phải 3 giây đầu video —
    dữ liệu không có transcript và không có thời lượng.
    """
    if text is None or pd.isna(text):
        return ""
    s = str(text).strip()
    if not s:
        return ""
    s = _HASHTAG_TAIL_RE.sub("", s).strip()
    prefix = ""
    m = _BRACKET_RE.match(s)
    if m:
        prefix = m.group(0)
        s = s[len(prefix):].strip()
    from kit.enrich.lexicon import HOOK_BREAK_CHARS
    cut = len(s)
    for ch in HOOK_BREAK_CHARS:
        i = s.find(ch)
        if i > 0:
            cut = min(cut, i)
    hook = (prefix + s[:cut]).strip()
    return hook[:max_len]


def tag_one_hook_type(hook: str) -> str:
    """
    Kiểu hook của 1 câu mở (đã lower).

    Đơn nhãn, xét THEO THỨ TỰ trong `HOOK_TYPE_RULES` (khớp trước thắng) —
    khác `tag_one_format` dùng chấm điểm. Lý do: một hook thường mang nhiều dấu
    hiệu cùng lúc ("35岁程序员，副业月入3000" vừa là danh tính vừa là số liệu) và
    người viết kịch bản cần biết dấu hiệu MẠNH nhất về mặt bán hàng, nên thứ tự
    ưu tiên do người đặt là đúng hơn là để số lượng từ khoá quyết định.
    """
    from kit.enrich.lexicon import HOOK_TYPE_RULES, OTHER_HOOK
    if not hook or not hook.strip():
        return OTHER_HOOK
    for name, keywords, patterns in HOOK_TYPE_RULES:
        if any(k in hook for k in keywords):
            return name
        if any(re.search(p, hook) for p in patterns):
            return name
    return OTHER_HOOK


def _clean_title(text: object, *, max_len: int = 80) -> str:
    """Tiêu đề đã bỏ chùm hashtag ở cuối, cắt gọn — dùng để CHẤM hook_type."""
    if text is None or pd.isna(text):
        return ""
    return _HASHTAG_TAIL_RE.sub("", str(text).strip()).strip()[:max_len]


def tag_hook(df: pd.DataFrame) -> pd.DataFrame:
    """
    Thêm `hook_text`, `hook_type`, `hook_len` (dùng cho Hook Lab + Playbook).

    `hook_text` là câu mở để HIỂN THỊ (cắt tại dấu câu đầu), nhưng `hook_type`
    được chấm trên tiêu đề ĐẦY ĐỦ (đã bỏ hashtag đuôi): tín hiệu quyết định
    thường nằm sau dấu phẩy — vd "程序员接私活，一小时赚300" là kể kết quả, còn
    "99%程序员做副业，都是浪费时间" là phủ định. Nếu chấm trên câu đã cắt thì cả
    hai đều bị gán nhầm thành "danh tính/tuổi".
    """
    df = df.copy()
    src = next((c for c in ("title", "title_text", "content", "desc")
                if c in df.columns and text_series(df, c).str.strip().any()), None)
    if src is None:
        df["hook_text"] = ""
        df["hook_type"] = "khác"
        df["hook_len"] = 0
        return df
    df["hook_text"] = df[src].map(hook_text_of)
    df["hook_type"] = df[src].map(_clean_title).str.lower().map(tag_one_hook_type)
    df["hook_len"] = df["hook_text"].str.len()
    return df


def tag_format_stats(df: pd.DataFrame, *, top_other: int = 15) -> dict:
    """
    Chất lượng phân loại format — để báo cáo tự chấm điểm chính nó.

    Trả `other_pct` (tỉ lệ bài không nhận ra format) và các title "khác" có
    engagement cao nhất, làm backlog mở rộng luật. Nhờ đó Format Playbook nói
    thật "nhận diện được bao nhiêu %" thay vì nhồi mọi bài vào một rổ.
    """
    if df is None or df.empty or "format" not in df.columns:
        return {"other_pct": 1.0, "n_formats": 0, "per_format": {},
                "top_other_titles": []}
    vc = df["format"].value_counts()
    other = int(vc.get(OTHER_FORMAT, 0))
    sub = df[df["format"] == OTHER_FORMAT]
    if "eng_total" in sub.columns:
        sub = sub.sort_values("eng_total", ascending=False)
    title_col = next((c for c in ("title", "title_text", "content")
                      if c in sub.columns), None)
    titles = ([str(t)[:80] for t in sub[title_col].head(top_other)]
              if title_col else [])
    return {
        "other_pct": other / len(df),
        "n_formats": int(vc.drop(OTHER_FORMAT, errors="ignore").size),
        "per_format": {str(k): int(v) for k, v in vc.items()},
        "top_other_titles": titles,
    }


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Chuỗi chuẩn hoá đầy đủ: counts/thời gian -> engagement -> format."""
    return tag_format(add_engagement(normalize_counts(df)))
