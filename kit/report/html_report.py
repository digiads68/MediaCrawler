# -*- coding: utf-8 -*-
"""
Sinh báo cáo HTML tự chứa từ kết quả analyzer (kèm biểu đồ SVG, link video).

- 3 template giàu: trend / koc / sov.
- 1 template generic phủ các lệnh còn lại (insight/opportunity/seasonal/price/angle).
- HTML tự chứa (CSS inline), theme sáng/tối, in được, mở offline.
- Bảng màu category lấy từ dataviz skill (đã kiểm định CVD sáng+tối).
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd

from kit.analyzer.insights import GOALS as GOAL_LABELS
from kit.enrich.schema import cover_of_row
from kit.media_urls import is_direct_media
from kit.report import charts

# Suy từ vị trí file này, KHÔNG phải CWD — nếu dùng Path("reports") thì chạy
# uvicorn từ thư mục khác sẽ ghi báo cáo ra chỗ api/routers/kit.py không đọc tới.
REPORT_DIR = Path(__file__).resolve().parents[2] / "reports"

# Nhan url -> hien "▶ Xem"; cot chua tu khoa nay coi la link
_URL_HINT = ("url", "link")

# Endpoint proxy ep trinh duyet TAI file thay vi phat inline (xem kit/media_urls.py).
# Duong dan tuong doi -> chay dung ca khi mo qua localhost va qua IP Tailscale;
# khi mo file HTML offline thi link "tai" khong hoat dong, nhung link xem/phat
# truc tiep ben canh van con.
_DOWNLOAD_ENDPOINT = "/kit/media/download"


def _download_href(url: str, filename: str = "") -> str:
    """Link tải qua proxy (ép attachment, gắn Referer đúng nền tảng)."""
    href = f"{_DOWNLOAD_ENDPOINT}?url={quote(str(url), safe='')}"
    if filename:
        href += f"&name={quote(filename, safe='')}"
    return href

# Tên hiển thị cột (tiếng Việt gọn) cho bảng
_COL_LABELS = {
    "title": "Tiêu đề", "format": "Format", "source_keyword": "Từ khoá",
    "nguon_keyword": "Từ khoá", "liked_count": "Like", "collected_count": "Save",
    "share_count": "Share", "comment_count": "Bình luận", "trend_score": "Điểm trend",
    "aweme_url": "Video", "note_url": "Bài", "video_url": "Video",
    "creator": "Creator", "nickname": "Tên", "so_video": "Số video",
    "eng_tb": "Eng TB", "do_deu": "Độ đều", "velocity": "Velocity",
    "nhip_dang_ngay": "Nhịp đăng (ngày)", "diem_tong": "Điểm", "verdict": "Kết luận",
    "rising": "Đang lên", "so_bai": "Số bài", "save_tb": "Save TB",
    "eng_total": "Engagement", "eng_tong": "Engagement", "quadrant": "Vùng cơ hội",
    "week": "Tuần", "brand": "Brand", "eng": "Engagement", "sov_pct": "SOV %",
    "content": "Bình luận", "like_count": "Like", "sub_comment_count": "Trả lời",
    "text": "Trích đoạn", "gia_phat_hien": "Giá phát hiện", "moi_km": "Mồi khuyến mãi",
    "hook": "Hook", "pain_or_desire": "Nỗi đau/mong muốn", "sound_ref": "Nhạc",
    "music_download_url": "Nhạc",
    # --- cột của dashboard Pha 2 ---
    "platform": "Nền tảng", "platform_label": "Nền tảng",
    "hook_text": "Câu mở đầu", "hook_type": "Kiểu hook", "hook_len": "Độ dài hook",
    "eng_median": "Eng median", "eng_p90": "Eng p90", "lift": "Lift",
    "lift_chip": "Lift", "do_on_dinh": "Độ ổn định", "so_creator": "Số creator",
    "phan_tram": "% bài", "save_rate_median": "Save/Like", "share_rate_median": "Share/Like",
    "music_id": "Mã nhạc", "so_anh": "Số ảnh", "so_hashtag": "Số hashtag",
    "media_kind": "Dạng nội dung", "kich_thuoc": "Nhóm", "pct_rank": "Hạng %",
    "m_like": "Like", "m_comment": "Bình luận", "m_share": "Share",
    "m_save": "Save", "m_view": "View", "eng_common": "Eng so sánh được",
    "cum_noi_dau": "Cụm nỗi đau", "phan_doi": "Phản đối", "tan_suat": "Tần suất",
    "quote": "Trích dẫn", "hook_goi_y": "Hook đề xuất", "uu_tien": "Ưu tiên",
    "cach_xu_ly": "Cách xử lý trong script", "bang_chung": "Bằng chứng cần có",
    "tu_khoa": "Từ/cụm khách dùng", "ngu_canh": "Ngữ cảnh", "dung_o_dau": "Dùng ở đâu",
    "cau_hoi": "Câu hỏi của khách", "title_text": "Tiêu đề",
    "cover_url_c": "Ảnh cover", "so_bai_moi_creator": "Bài/creator",
}

# Cột văn bản dài -> cắt hiển thị (giữ nguyên tooltip đầy đủ)
_TEXT_TRUNC = {"title", "text", "content", "hook", "desc", "hook_text",
               "title_text", "quote", "ngu_canh", "hook_goi_y", "cau_hoi",
               "cach_xu_ly", "bang_chung"}
_TRUNC_LEN = 90

# Cột số (căn phải, tabular)
_NUM_COLS = {"liked_count", "collected_count", "share_count", "comment_count",
             "trend_score", "so_video", "eng_tb", "do_deu", "velocity", "diem_tong",
             "so_bai", "save_tb", "eng_total", "eng_tong", "eng", "sov_pct",
             "like_count", "sub_comment_count", "nhip_dang_ngay",
             # cột số của dashboard Pha 2
             "eng_median", "eng_p90", "lift", "do_on_dinh", "so_creator",
             "phan_tram", "save_rate_median", "share_rate_median", "hook_len",
             "so_anh", "so_hashtag", "pct_rank", "eng_common", "tan_suat",
             "uu_tien", "m_like", "m_comment", "m_share", "m_save", "m_view",
             "so_bai_moi_creator"}


def _esc(v: object) -> str:
    return html.escape(str(v), quote=True)


def _is_url(col: str) -> bool:
    c = col.lower()
    return any(h in c for h in _URL_HINT)


def _fmt_cell(col: str, v: Any) -> str:
    """Định dạng 1 ô: link video, số gọn, hay text thường."""
    if pd.isna(v) or v == "":
        return '<span class="muted">—</span>'
    if _is_url(col):
        url = str(v)
        is_music = "music" in col.lower()
        # File media truc tiep (mp4/mp3/anh tren CDN) -> them nut tai qua proxy,
        # vi bam link CDN chi phat inline chu khong tai ve duoc.
        if is_direct_media(url):
            play = "▶ Nghe" if is_music else "▶ Xem"
            return (f'<a href="{_esc(url)}" target="_blank" rel="noopener">{play}</a>'
                    f'<span class="dl-sep">·</span>'
                    f'<a href="{_esc(_download_href(url))}" class="dl-link">⬇ Tải</a>')
        label = "▶ Nghe" if is_music else "▶ Xem"
        return f'<a href="{_esc(url)}" target="_blank" rel="noopener">{label}</a>'
    if col in _TEXT_TRUNC:
        s = str(v)
        if len(s) > _TRUNC_LEN:
            return f'<span title="{_esc(s)}">{_esc(s[:_TRUNC_LEN])}…</span>'
        return _esc(s)
    if col == "verdict":
        cls = {"ký ngay": "chip-good", "theo dõi": "chip-warn",
               "bỏ qua": "chip-muted"}.get(str(v), "chip-muted")
        return f'<span class="chip {cls}">{_esc(v)}</span>'
    if col == "rising":
        return ('<span class="chip chip-good">▲ có</span>' if bool(v)
                else '<span class="muted">—</span>')
    if col in _NUM_COLS:
        try:
            fv = float(v)
            txt = f"{fv:,.0f}" if fv == int(fv) else f"{fv:,.1f}"
            return f'<span class="num">{txt}</span>'
        except (ValueError, TypeError):
            return _esc(v)
    return _esc(v)


def _table(df: pd.DataFrame, *, max_rows: int | None = None, drop: tuple[str, ...] = (),
           page_size: int = 25) -> str:
    """
    Render DataFrame -> bảng HTML (link video, chip verdict, số căn phải).

    Luôn hiện ĐỦ mọi dòng (trước đây cắt 15–60 dòng rồi bảo mở Excel). Bảng dài
    hơn `page_size` có phân trang phía trình duyệt. `max_rows` giữ để tương thích
    với nơi gọi cũ: nay chỉ còn nghĩa là số dòng mỗi trang.
    """
    if df is None or df.empty:
        return '<p class="muted">Không có dữ liệu.</p>'
    size = int(max_rows or page_size)
    cols = [c for c in df.columns if c not in drop and not c.endswith("_norm")
            and c not in ("eng_ma4",)]
    head = "".join(
        f'<th class="{"num" if c in _NUM_COLS else ""}">{_esc(_COL_LABELS.get(c, c))}</th>'
        for c in cols)
    body = []
    for _, r in df.iterrows():
        tds = "".join(
            f'<td class="{"num" if c in _NUM_COLS else ""}">{_fmt_cell(c, r[c])}</td>'
            for c in cols)
        body.append(f"<tr>{tds}</tr>")
    pager = ('<div class="pager-bar"><span class="pager-info"></span><span class="pager">'
             '<button type="button" data-prev>‹ Trước</button><span class="pager-pages"></span>'
             '<button type="button" data-next>Sau ›</button>'
             '<select class="mg-sort" data-size aria-label="Số dòng mỗi trang">'
             + "".join(f'<option value="{n}"{" selected" if n == size else ""}>{n} dòng</option>'
                       for n in sorted({size, 25, 50, 100}))
             + '<option value="0">Tất cả</option></select></span></div>'
             if len(df) > size else "")
    return (f'<div class="dtable" data-dtable data-size="{size}"><div class="tbl-wrap">'
            f'<table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>{pager}</div>')


def _pick_url_col(df: pd.DataFrame) -> str | None:
    for c in ("aweme_url", "note_url", "video_url"):
        if c in df.columns:
            return c
    return None


# Cot co the chua link trang xem (theo nen tang) va link file media truc tiep.
# Phan loai theo GIA TRI chu khong chi theo ten cot, vi `video_url` la trang xem
# voi Bilibili nhung lai la MP4 tren CDN voi Xiaohongshu/rednote.
_PAGE_URL_COLS = ("aweme_url", "note_url", "video_url")
_MEDIA_URL_COLS = ("video_download_url", "download_url", "video_url")


def _row_page_url(r: pd.Series) -> str:
    """Link mo trang xem bai goc (uu tien trang, khong phai file)."""
    for c in _PAGE_URL_COLS:
        v = r.get(c)
        if v and not pd.isna(v) and not is_direct_media(str(v)):
            return str(v)
    # Khong co trang xem -> dung link file (con hon khong co gi)
    for c in _PAGE_URL_COLS:
        v = r.get(c)
        if v and not pd.isna(v):
            return str(v)
    return ""


def _row_media_url(r: pd.Series) -> str:
    """Link file video tai truc tiep duoc (neu co)."""
    for c in _MEDIA_URL_COLS:
        v = r.get(c)
        if v and not pd.isna(v) and is_direct_media(str(v)):
            return str(v)
    return ""


def _pct(v: object) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except (ValueError, TypeError):
        return "—"


def _media_grid(df: pd.DataFrame, *, grid_id: str = "mg", max_cards: int | None = None,
                include_cover_dl: bool = False, grid_class: str = "",
                page_size: int = 24) -> str:
    """
    Lưới thẻ video cho nghiên cứu trend / lấy ý tưởng (clone).

    Mỗi thẻ: ảnh cover (fallback nếu vỡ/thiếu), rank + điểm trend, hook đầy đủ
    (thu gọn/mở rộng), 4 chỉ số + save-rate/share-rate, tên tác giả + ngày,
    nút "Copy hook", "Xem video", "Tải". Toolbar: tìm kiếm, sắp xếp, lọc format /
    từ khoá / mục tiêu / tuổi bài, phân trang (JS thuần, chạy được offline).

    Args:
        max_cards: None = hiện MỌI bài (mặc định — báo cáo phải đủ dữ liệu đã cào);
            chỉ đặt số khi cố ý lấy mẫu (vd 8 bài ví dụ mỗi format).
        page_size: số thẻ mỗi trang lúc mở; người xem đổi được (24/48/96/Tất cả).
    """
    if df is None or df.empty:
        return '<p class="muted">Không có dữ liệu.</p>'
    d = (df if max_cards is None else df.head(max_cards)).reset_index(drop=True)
    formats = sorted({str(f) for f in d.get("format", pd.Series(dtype=str)).dropna().unique()})
    keywords = sorted({str(k) for k in d.get("source_keyword", pd.Series(dtype=str)).dropna()
                       if str(k).strip() and str(k).lower() != "nan"})
    goals = [g for g in ("luu", "ban_luan", "lan_truyen", "can_bang")
             if "goal" in d.columns and (d["goal"] == g).any()]
    has_age = ("age_days" in d.columns
               and pd.to_numeric(d["age_days"], errors="coerce").notna().any())
    has_created = "created_at" in d.columns and d["created_at"].notna().any()

    chips = [f'<button class="fchip active" type="button" data-fmt="__all__">Tất cả '
             f'({len(d)})</button>']
    for fmt in formats:
        n = int((d["format"] == fmt).sum())
        chips.append(f'<button class="fchip" type="button" data-fmt="{_esc(fmt)}">'
                     f'{_esc(fmt)} ({n})</button>')

    cards = []
    for i, r in d.iterrows():
        # Ưu tiên `hook_text` (câu mở đã tách) nếu có: đó chính là thứ người viết
        # kịch bản muốn copy, không phải cả caption dài kèm hashtag.
        title = str(r.get("hook_text") or r.get("title") or r.get("title_text") or "")
        fmt = str(r.get("format", "") or "khác")
        kw = str(r.get("source_keyword", "") or "")
        if kw.lower() == "nan":
            kw = ""
        like = float(r.get("liked_count", 0) or 0)
        save = float(r.get("collected_count", 0) or 0)
        share = float(r.get("share_count", 0) or 0)
        comment = float(r.get("comment_count", 0) or 0)
        score = float(r.get("trend_score", 0) or 0)
        goal = str(r.get("goal", "") or "")
        goal_label = GOAL_LABELS.get(goal, "")
        age = pd.to_numeric(r.get("age_days"), errors="coerce")
        age_s = "" if pd.isna(age) else f"{int(age)}"
        url = _row_page_url(r)
        media_url = _row_media_url(r)
        # cover_of_row thay vì r["cover_url"]: XHS KHÔNG có cột cover_url (cover
        # nằm ở ảnh đầu trong image_list) nên báo cáo XHS trước đây không hiện
        # ảnh nào. Bilibili/Kuaishou lại đặt tên video_cover_url.
        cover = cover_of_row(r)
        nickname = str(r.get("nickname", "") or "")
        created = r.get("created_at")
        created_s = "" if pd.isna(created) else str(created)[:10]
        created_ts = "" if pd.isna(created) else str(int(pd.Timestamp(created).timestamp()))
        music = str(r.get("music_download_url", "") or "")

        thumb = (
            f'<a class="mcard-thumb" href="{_esc(url)}" target="_blank" rel="noopener">'
            # referrerpolicy="no-referrer" là BẮT BUỘC: trình duyệt mặc định gửi
            # Referer của trang báo cáo (vd http://127.0.0.1:8080/...), và CDN ảnh
            # Bilibili chặn Referer lạ -> 403. Đã đo: không Referer = 200,
            # Referer localhost = 403, Referer bilibili.com = 200. Bỏ Referer là
            # cách duy nhất chạy đúng cho mọi nền tảng.
            f'<img src="{_esc(cover)}" loading="lazy" alt="" '
            f'referrerpolicy="no-referrer" '
            f'onerror="this.closest(\'.mcard-thumb\').classList.add(\'mcard-thumb--broken\')">'
            f'<span class="mcard-play">▶</span>'
            f'<span class="mcard-rank">#{i + 1}</span>'
            f'<span class="mcard-score">{score:.0f}</span></a>'
            if url else
            f'<div class="mcard-thumb mcard-thumb--broken">'
            f'<span class="mcard-rank">#{i + 1}</span>'
            f'<span class="mcard-score">{score:.0f}</span></div>'
        )

        meta_bits = [b for b in [_esc(nickname), _esc(created_s)] if b]
        if age_s:
            meta_bits.append(f"{age_s} ngày tuổi")
        if music:
            meta_bits.append(f'<a href="{_esc(music)}" target="_blank" '
                             f'rel="noopener">🎵 nhạc</a>')
        meta = " · ".join(meta_bits)

        actions = (f'<a class="mcard-open" href="{_esc(url)}" target="_blank" '
                   f'rel="noopener">▶ Xem</a>' if url else "")
        if media_url:
            # Ten file goi y: rank + hook rut gon, de tai nhieu video khong bi trung
            fname = f"{i + 1:02d}_{title[:40]}" if title else f"video_{i + 1:02d}"
            actions += (f'<a class="mcard-dl" href="{_esc(_download_href(media_url, fname))}" '
                        f'title="Tải video về máy">⬇ Tải</a>')
        elif include_cover_dl and cover:
            # Moodboard: tai chinh ANH cover — link CDN co moc thoi gian nen se
            # het han, muon dung lau phai luu ban cung.
            fname = f"{i + 1:02d}_{title[:40]}" if title else f"cover_{i + 1:02d}"
            actions += (f'<a class="mcard-dl" href="{_esc(_download_href(cover, fname))}" '
                        f'title="Tải ảnh cover về máy">⬇ Tải ảnh</a>')
        kw_tag = f'<span class="tag tag-kw">{_esc(kw)}</span>' if kw else ""
        goal_tag = (f'<span class="tag tag-goal g-{_esc(goal)}">{_esc(goal_label)}</span>'
                    if goal_label else "")
        meta_div = f'<div class="mcard-meta">{meta}</div>' if meta else ""

        cards.append(
            f'<article class="mcard" data-format="{_esc(fmt)}" data-kw="{_esc(kw)}" '
            f'data-goal="{_esc(goal)}" data-age="{age_s}" data-created="{created_ts}" '
            f'data-hook-lc="{_esc(title.lower())}" data-trend="{score}" '
            f'data-like="{like}" data-save="{save}" data-share="{share}" '
            f'data-comment="{comment}">'
            f'{thumb}'
            f'<div class="mcard-body">'
            f'<div class="mcard-tags"><span class="tag">{_esc(fmt)}</span>{goal_tag}{kw_tag}</div>'
            f'<p class="mcard-hook">{_esc(title)}</p>'
            f'<button class="mcard-more" type="button">Xem đầy đủ ▾</button>'
            f'<div class="mcard-stats">'
            f'<span class="st-like" title="Like">👍 {charts._fmt(like)}</span>'
            f'<span class="st-save" title="Save">💾 {charts._fmt(save)}</span>'
            f'<span class="st-share" title="Share">↗ {charts._fmt(share)}</span>'
            f'<span class="st-comment" title="Bình luận">💬 {charts._fmt(comment)}</span></div>'
            f'<div class="mcard-rates">'
            f'<span>Save/Like: <b>{_pct(r.get("save_rate"))}</b></span>'
            f'<span>Share/Like: <b>{_pct(r.get("share_rate"))}</b></span></div>'
            f'{meta_div}'
            f'<div class="mcard-actions">'
            f'<button class="btn-copy" type="button" data-copy="{_esc(title)}">'
            f'📋 Copy hook</button>{actions}</div>'
            f'</div></article>'
        )

    selects = []
    if len(keywords) > 1:
        opts = "".join(f'<option value="{_esc(k)}">{_esc(k)}</option>' for k in keywords)
        selects.append(f'<select id="{grid_id}-kw" class="mg-sort" aria-label="Lọc theo từ khoá">'
                       f'<option value="">Mọi từ khoá</option>{opts}</select>')
    if goals:
        opts = "".join(f'<option value="{g}">{GOAL_LABELS[g]}</option>' for g in goals)
        selects.append(f'<select id="{grid_id}-goal" class="mg-sort" '
                       f'aria-label="Lọc theo mục tiêu nội dung">'
                       f'<option value="">Mọi mục tiêu</option>{opts}</select>')
    if has_age:
        selects.append(
            f'<select id="{grid_id}-age" class="mg-sort" aria-label="Lọc theo tuổi bài">'
            f'<option value="">Mọi tuổi bài</option><option value="0-30">&lt; 30 ngày</option>'
            f'<option value="30-90">30–90 ngày</option><option value="90-180">90–180 ngày</option>'
            f'<option value="180-1000000">&gt; 180 ngày</option></select>')
    new_opt = '<option value="created">Mới đăng nhất</option>' if has_created else ""
    sizes = ("".join(f'<option value="{n}"{" selected" if n == page_size else ""}>'
                     f'{n} / trang</option>' for n in (24, 48, 96))
             + '<option value="0">Tất cả</option>')

    return f"""
<div class="mg" id="{grid_id}">
<div class="grid-toolbar">
  <input type="search" id="{grid_id}-search" placeholder="Tìm trong hook…" class="mg-search">
  <select id="{grid_id}-sort" class="mg-sort" aria-label="Sắp xếp">
    <option value="trend">Sắp theo: Điểm trend</option>
    <option value="like">Like</option>
    <option value="save">Save</option>
    <option value="share">Share</option>
    <option value="comment">Bình luận</option>
    {new_opt}
  </select>
  {"".join(selects)}
  <select id="{grid_id}-size" class="mg-sort" aria-label="Số thẻ mỗi trang">{sizes}</select>
</div>
<div class="chip-row" id="{grid_id}-chips">{"".join(chips)}</div>
<div class="mcard-grid {grid_class}" id="{grid_id}-grid">{"".join(cards)}</div>
<div class="pager-bar"><span class="pager-info" id="{grid_id}-info"></span>
  <span class="pager"><button type="button" id="{grid_id}-prev">‹ Trước</button>
  <span id="{grid_id}-pages" class="pager-pages"></span>
  <button type="button" id="{grid_id}-next">Sau ›</button></span></div>
</div>
<script>DAMG("{grid_id}");</script>"""


def _tiles(items: list[tuple[str, str, str]]) -> str:
    """KPI tiles: [(nhãn, giá trị, ghi chú)]."""
    cells = []
    for label, value, note in items:
        cells.append(
            f'<div class="tile"><div class="t-label">{_esc(label)}</div>'
            f'<div class="t-value">{_esc(value)}</div>'
            f'<div class="t-note">{_esc(note)}</div></div>')
    return f'<div class="tiles">{"".join(cells)}</div>'


def _section(title: str, inner: str) -> str:
    return f'<section class="panel"><h2>{_esc(title)}</h2>{inner}</section>'


# ---------------------------------------------------------------------------
# Từng loại báo cáo
# ---------------------------------------------------------------------------

def _keyword_metric_line(df: pd.DataFrame) -> str:
    """Line/hbar chỉ số theo từng keyword (Like/Save/Share/Bình luận)."""
    if df is None or "source_keyword" not in df.columns:
        return ""
    metrics = [("Like", "liked_count"), ("Save", "collected_count"),
               ("Share", "share_count"), ("Bình luận", "comment_count")]
    metrics = [(n, c) for n, c in metrics if c in df.columns]
    if not metrics:
        return ""
    g = df.groupby("source_keyword")[[c for _, c in metrics]].sum()
    kws = [str(k)[:14] for k in g.index.tolist()]
    if len(kws) >= 2:
        series = [{"name": n, "points": g[c].tolist()} for n, c in metrics]
        return charts.line(series, kws, title="Chỉ số theo từ khoá")
    # 1 keyword: hbar tổng từng chỉ số
    rows = [(n, float(g[c].iloc[0])) for n, c in metrics]
    return charts.hbar(rows, title="Chỉ số của từ khoá", color_idx=1)


def _lift_chip(v: object) -> str:
    """Chip hiển thị lift (×1.8 ▲ / ×0.5 ▼) — dùng lại class chip sẵn có."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return '<span class="muted">—</span>'
    cls = "chip-good" if f >= 1.3 else ("chip-warn" if f >= 0.8 else "chip-muted")
    arrow = " ▲" if f >= 1.3 else (" ▼" if f < 0.8 else "")
    return f'<span class="chip {cls}">×{f:.2f}{arrow}</span>'


MIN_SAMPLE_FOR_WINNER = 3


def _pick_winner(stats: pd.DataFrame, key: str, *,
                 min_posts: int = MIN_SAMPLE_FOR_WINNER
                 ) -> tuple[str, str, str]:
    """
    Chọn nhóm "thắng" nhưng CÓ ĐỦ MẪU, trả (tên, lift, ghi chú).

    Vì sao cần ngưỡng mẫu: engagement lệch rất mạnh, một nhóm chỉ 1-2 bài mà
    trúng bài viral sẽ cho lift hàng trăm lần (đo thật: nhóm 2 bài ra ×195 vì có
    1 video 18M view). Đưa con số đó lên tile là nói sai — người đọc sẽ tưởng đó
    là công thức nhân bản được. Nên ưu tiên nhóm đủ mẫu; nếu không nhóm nào đủ
    thì vẫn hiện nhưng ghi rõ mẫu quá nhỏ.
    """
    if stats is None or stats.empty or key not in stats.columns:
        return "—", "—", ""
    real = stats[stats[key].astype(str) != "khác"]
    if real.empty:
        return "—", "—", ""
    enough = real[real["so_bai"] >= min_posts] if "so_bai" in real.columns else real
    pool, warn = (enough, "") if len(enough) else (
        real, f"mẫu nhỏ (<{min_posts} bài) — đọc như định tính")
    row = pool.sort_values("eng_median", ascending=False).iloc[0]
    n = int(row["so_bai"]) if "so_bai" in row else 0
    note = f"n={n} bài" + (f" · {warn}" if warn else "")
    return str(row[key]), f'×{float(row.get("lift", 0)):.2f}', note


def _limits_panel(items: list[str]) -> str:
    """
    Panel "Giới hạn dữ liệu" — đặt TRƯỚC mọi tile/chart của dashboard yếu.

    Mục đích: nói thẳng phần mềm KHÔNG biết gì, để người đọc không suy diễn quá
    những gì dữ liệu đỡ được (vd Moodboard không phân tích nội dung ảnh, Hook Lab
    đọc caption chứ không phải 3 giây đầu video).
    """
    if not items:
        return ""
    lis = "".join(f"<li>{i}</li>" for i in items)   # đã escape ở nơi gọi
    return _section("Giới hạn dữ liệu — đọc trước khi kết luận",
                    f'<ul class="limits">{lis}</ul>')


def _report_playbook(result: dict, df: pd.DataFrame | None) -> tuple[str, list, str]:
    """CS14 — Format Playbook (đạo diễn: nên sản xuất format nào)."""
    NAME = "Format Playbook"
    XLSX = ["CS14_format_playbook.xlsx", "CS14_format_unclassified.xlsx"]
    stats = result.get("stats", pd.DataFrame())
    if stats is None or stats.empty:
        return (f'<p class="muted">Không có dữ liệu cho {_esc(NAME)}.</p>', XLSX, NAME)

    fstats = result.get("format_stats", {})
    other_pct = float(fstats.get("other_pct", 0))
    recognised = 1 - other_pct
    real = stats[stats["format"] != "khác"]

    # Format "rủi ro": engagement cao nhưng thất thường -> khó nhân bản
    risky = "—"
    if len(real) > 1:
        cand = real[real["eng_median"] >= real["eng_median"].median()]
        if len(cand):
            risky = str(cand.sort_values("do_on_dinh").iloc[0]["format"])

    win, win_lift, win_note = _pick_winner(stats, "format")
    tiles = _tiles([
        ("Format nhận diện được", f"{recognised * 100:.0f}%",
         "phần còn lại nằm ở nhóm “khác”"),
        ("Format thắng", win, win_note or "engagement median cao nhất"),
        ("Lift so với trung vị", win_lift, "×1.0 = ngang mặt bằng"),
        ("Format rủi ro", risky, "ăn cao nhưng thất thường"),
    ])

    donut = charts.donut([(str(r["format"]), float(r["so_bai"]))
                          for _, r in stats.iterrows()],
                         title="Cơ cấu format (số bài)", unit="bài")
    bar = charts.hbar([(str(r["format"]), float(r["eng_median"]))
                       for _, r in real.iterrows()],
                      title="Engagement median theo format", color_idx=2)

    body = [tiles]
    if other_pct > 0.40:
        body.append(_limits_panel([
            f"<b>{other_pct * 100:.0f}% bài chưa nhận ra format</b> — bảng dưới chỉ "
            f"nói về phần đã nhận ra, đừng coi là toàn bộ mẫu.",
            "Xem bảng “Chưa nhận ra format” ở cuối để bổ sung từ khoá.",
        ]))
    body.append(_section("Cơ cấu & hiệu suất",
                         f'<div class="chart-grid-2">{donut}{bar}</div>'))

    rows, cols, grid = result.get("crosstab", ([], [], []))
    if rows and cols:
        body.append(_section(
            "Format × kiểu hook — ghép cái gì với cái gì thì ăn",
            charts.heatmap(rows, cols, grid,
                           title="Engagement median (— = chưa có bài nào)",
                           color_idx=1)))

    # Bảng chỉ số: thêm cột lift dạng chip cho dễ đọc
    tbl = stats.copy()
    if "lift" in tbl.columns:
        tbl["lift_chip"] = tbl["lift"]
    body.append(_section("Bảng chỉ số từng format", _table(tbl, max_rows=30)))

    ex = result.get("examples", pd.DataFrame())
    if ex is not None and len(ex):
        cards = []
        for i, (fmt, sub) in enumerate(ex.groupby("format", sort=False)):
            cards.append(f'<h3 class="sub-h">{_esc(fmt)}</h3>'
                         + _media_grid(sub, grid_id=f"pb{i}", max_cards=8))
        body.append(_section("Bài mẫu của 3 format mạnh nhất", "".join(cards)))

    unc = result.get("unclassified", pd.DataFrame())
    if unc is not None and len(unc):
        body.append(_section(
            f"Chưa nhận ra format ({len(unc)} bài, xếp theo engagement)",
            '<p class="muted">Đây là backlog để mở rộng bộ luật nhận diện — '
            'không phải bài kém.</p>' + _table(unc, max_rows=20)))
    return "".join(body), XLSX, NAME


def _report_hook(result: dict, df: pd.DataFrame | None) -> tuple[str, list, str]:
    """CS12 — Hook Lab (người viết kịch bản: viết câu mở đầu)."""
    NAME = "Hook Lab"
    XLSX = ["CS12_hook_lab_types.xlsx", "CS12_hook_lab_top.xlsx"]
    types = result.get("types", pd.DataFrame())
    if types is None or types.empty:
        return (f'<p class="muted">Không có dữ liệu cho {_esc(NAME)}.</p>', XLSX, NAME)

    lengths = result.get("lengths", pd.DataFrame())
    top = result.get("top_posts", pd.DataFrame())
    real = types[types["hook_type"] != "khác"]

    win, win_lift, win_note = _pick_winner(types, "hook_type")
    best_len, _, len_note = _pick_winner(lengths, "nhom_do_dai")
    tiles = _tiles([
        ("Kiểu hook nhận ra", str(len(real)), "nhóm có bài thật"),
        ("Kiểu hook thắng", win, win_note or "engagement median cao nhất"),
        ("Lift so với trung vị", win_lift, "×1.0 = ngang mặt bằng"),
        ("Độ dài hook tốt nhất", best_len, len_note or "theo engagement median"),
    ])

    body = [tiles, _limits_panel([
        "<b>“Hook” ở đây là câu mở của tiêu đề/caption</b>, KHÔNG phải 3 giây đầu "
        "video — dữ liệu cào không có transcript và không có thời lượng video.",
        "Kiểu hook được gán bằng bộ luật từ khoá (không dùng AI), nên bài diễn đạt "
        "lạ có thể rơi vào nhóm “khác”.",
    ])]

    donut = charts.donut([(str(r["hook_type"]), float(r["so_bai"]))
                          for _, r in types.iterrows()],
                         title="Cơ cấu kiểu hook (số bài)", unit="bài")
    bar = charts.hbar([(str(r["hook_type"]), float(r["eng_median"]))
                       for _, r in real.iterrows()],
                      title="Engagement median theo kiểu hook", color_idx=3)
    body.append(_section("Kiểu hook nào ăn",
                         f'<div class="chart-grid-2">{donut}{bar}</div>'))

    if len(lengths):
        body.append(_section(
            "Độ dài hook",
            charts.hbar([(str(r["nhom_do_dai"]), float(r["eng_median"]))
                         for _, r in lengths.iterrows()],
                        title="Engagement median theo độ dài", color_idx=5)))

    body.append(_section("Bảng chỉ số từng kiểu hook", _table(types, max_rows=20)))

    if top is not None and len(top):
        body.append(_section(
            "Hook mẫu — bấm 📋 để copy vào kịch bản",
            '<p class="muted">Ô tìm kiếm lọc theo nội dung hook; nút Copy hook lấy '
            'nguyên văn câu mở.</p>' + _media_grid(top, grid_id="hook")))
    return "".join(body), XLSX, NAME


def _report_sound(result: dict, df: pd.DataFrame | None) -> tuple[str, list, str]:
    """CS10+CS13 — Sound & Edit Kit (editor)."""
    NAME = "Sound & Edit Kit"
    XLSX = ["CS10_sound_watchlist.xlsx", "CS13_edit_kit.xlsx"]
    sounds = result.get("sounds", pd.DataFrame())
    kinds = result.get("kinds", pd.DataFrame())
    images = result.get("images", pd.DataFrame())
    hashtags = result.get("hashtags", pd.DataFrame())
    shelf = result.get("shelf", pd.DataFrame())
    has_music = bool(result.get("has_music"))

    # Nhạc chỉ đáng gọi là "trend" khi có creator KHÁC nhau dùng lại
    reused = 0
    if len(sounds) and "so_creator" in sounds.columns:
        reused = int((sounds["so_creator"] >= 2).sum())
    win_kind, _, kind_note = _pick_winner(kinds, "dang_noi_dung")
    best_img, _, img_note = _pick_winner(images, "nhom_so_anh")

    tiles = _tiles([
        ("Nhạc ghi nhận", str(len(sounds)) if has_music else "—",
         "chỉ Douyin xuất link nhạc"),
        ("Nhạc dùng chéo creator", str(reused) if has_music else "—",
         "≥2 creator khác nhau dùng chung"),
        ("Dạng nội dung thắng", win_kind, kind_note or "engagement median"),
        ("Số ảnh tốt nhất", best_img, img_note or "với bài dạng ảnh"),
    ])

    limits = [
        "<b>Phần “kết cấu” không phải phân tích dựng phim</b> — dữ liệu không có "
        "thời lượng, không có cắt cảnh. Chỉ đo được: dạng bài, số ảnh, số hashtag.",
    ]
    if has_music:
        limits.insert(0,
            "<b>Nhạc chỉ có URL mp3, không có tên/tác giả/BPM</b> — nền tảng không "
            "xuất thông tin đó, nên watchlist hiển thị mã file.")
    else:
        limits.insert(0,
            "<b>Nền tảng này không xuất link nhạc</b> (chỉ Douyin có) — báo cáo "
            "chỉ chạy phần kết cấu nội dung.")
    body = [tiles, _limits_panel(limits)]

    if has_music:
        if reused == 0:
            body.append(_section(
                "Sound watchlist",
                '<p class="muted">Trong mẫu này <b>chưa có bản nhạc nào được dùng '
                'bởi từ 2 creator khác nhau</b> — chưa đủ bằng chứng để nói có sound '
                'đang lên. Bảng dưới chỉ liệt kê nhạc đã ghi nhận, không phải xếp '
                'hạng trend.</p>' + _table(sounds, max_rows=20)))
        else:
            body.append(_section(
                f"Sound watchlist — {reused} nhạc được dùng chéo creator",
                _table(sounds, max_rows=20)))

    charts_html = []
    if len(kinds):
        charts_html.append(charts.donut(
            [(str(r["dang_noi_dung"]), float(r["so_bai"])) for _, r in kinds.iterrows()],
            title="Cơ cấu dạng nội dung", unit="bài"))
    if len(kinds) > 1:
        charts_html.append(charts.hbar(
            [(str(r["dang_noi_dung"]), float(r["eng_median"])) for _, r in kinds.iterrows()],
            title="Engagement median theo dạng", color_idx=4))
    if charts_html:
        body.append(_section("Video hay bài ảnh?",
                             f'<div class="chart-grid-2">{"".join(charts_html)}</div>'))

    struct = []
    if len(images):
        struct.append(charts.hbar(
            [(str(r["nhom_so_anh"]), float(r["eng_median"])) for _, r in images.iterrows()],
            title="Engagement median theo số ảnh", color_idx=5))
    if len(hashtags):
        struct.append(charts.hbar(
            [(str(r["nhom_hashtag"]), float(r["eng_median"])) for _, r in hashtags.iterrows()],
            title="Engagement median theo số hashtag", color_idx=6))
    if struct:
        body.append(_section("Kết cấu bài",
                             f'<div class="chart-grid-2">{"".join(struct)}</div>'))

    if shelf is not None and len(shelf):
        body.append(_section(
            "Kệ tư liệu — tải video/nhạc mẫu về dựng",
            _media_grid(shelf, grid_id="sound")))
    return "".join(body), XLSX, NAME


def _report_moodboard(result: dict, df: pd.DataFrame | None) -> tuple[str, list, str]:
    """CS15 — Cover Moodboard (đạo diễn)."""
    NAME = "Cover Moodboard"
    XLSX = ["CS15_cover_moodboard.xlsx"]
    board = result.get("board", pd.DataFrame())
    if board is None or board.empty:
        return ('<p class="muted">Không có ảnh cover nào.</p>', XLSX, NAME)

    coverage = float(result.get("coverage", 0))
    total = int(result.get("total", len(board)))
    formats = result.get("formats", pd.DataFrame())
    win_fmt, _, fmt_note = _pick_winner(formats, "format")

    platforms = (set(board["platform"].dropna().astype(str))
                 if "platform" in board.columns else set())
    tiles = _tiles([
        ("Bài có link cover", str(len(board)), f"trong {total} bài"),
        ("Tỉ lệ có link", f"{coverage * 100:.0f}%",
         "có LINK — chưa chắc còn tải được"),
        ("Format thắng", win_fmt, fmt_note or "engagement median"),
        ("Hạng cao nhất", f'{float(board["pct_rank"].max()):.0f}%'
         if "pct_rank" in board.columns else "—", "hạng phần trăm engagement"),
    ])

    limits = [
        "<b>Phần mềm KHÔNG phân tích nội dung ảnh</b> — không biết cover có mặt "
        "người, chữ to hay màu nóng. Tường ảnh xếp theo hiệu suất; đọc pattern "
        "thị giác là việc của đạo diễn.",
        "<b>Link ảnh có thời hạn</b> (đường dẫn CDN mang mốc thời gian) — ảnh nào "
        "không hiện được sẽ thành ô 🎬. Bấm ⬇ để lưu bản cứng khi ảnh còn tải được.",
        "Nhãn format / kiểu hook suy từ VĂN BẢN của bài, không suy từ ảnh.",
    ]
    if "xhs" in platforms:
        # Đã kiểm bằng thực tế: CDN ảnh của Xiaohongshu/rednote trả 403 cho mọi
        # request ngoài trang (thử cả http/https, có/không Referer, và qua proxy
        # nội bộ). Nói trước để người dùng không tưởng báo cáo bị lỗi.
        limits.insert(0,
            "<b>Ảnh Xiaohongshu/rednote thường KHÔNG hiện được</b>: CDN ảnh của "
            "nền tảng này chặn truy cập từ ngoài (trả 403) kể cả khi đã gắn "
            "Referer đúng. Với XHS, dùng cột link trong file Excel và mở trực "
            "tiếp trên trang gốc; tường ảnh dưới đây sẽ phần lớn là ô trống.")
    body = [tiles, _limits_panel(limits)]

    if len(formats) > 1:
        body.append(_section("Format nào đang thắng (để đọc tường ảnh theo nhóm)",
                             charts.hbar(
                                 [(str(r["format"]), float(r["eng_median"]))
                                  for _, r in formats.iterrows()],
                                 title="Engagement median theo format", color_idx=2)))

    body.append(_section(
        "Tường ảnh cover — xếp theo engagement",
        '<p class="muted">Dùng ô tìm kiếm và chip format để lọc; bấm ảnh để mở bài '
        'gốc, ⬇ để tải ảnh.</p>'
        + _media_grid(board, grid_id="mood",
                      include_cover_dl=True, grid_class="mcard-grid--mood")))
    return "".join(body), XLSX, NAME


def _fmt_vi(v: object, digits: int = 0) -> str:
    """Số kiểu Việt Nam: 8.537 · 0,67. NaN/None -> —."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if f != f:  # NaN
        return "—"
    s = f"{f:,.{digits}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _pill(text: str, tone: str) -> str:
    """Chip trạng thái: tone = good | warn | bad | neutral."""
    return f'<span class="pill pill-{tone}">{_esc(text)}</span>'


def _verdict_block(verdict: str, decisions: list[str]) -> str:
    items = "".join(f'<li><span class="dn">{i}</span><span>{_esc(t)}</span></li>'
                    for i, t in enumerate(decisions, 1))
    lst = f'<ol class="decisions">{items}</ol>' if items else ""
    return (f'<section class="verdict"><div class="eyebrow">Kết luận</div>'
            f'<p class="verdict-text">{_esc(verdict)}</p>{lst}</section>')


def _kpi_tiles(items: list[tuple[str, str, str, str]]) -> str:
    """KPI: [(nhãn, giá trị, ghi chú, chip HTML đã escape)]."""
    cells = "".join(
        f'<div class="tile"><div class="t-label">{_esc(k)}</div>'
        f'<div class="t-value">{_esc(v)}</div>'
        f'<div class="t-note">{chip} {_esc(n)}</div></div>'
        for k, v, n, chip in items)
    return f'<div class="tiles tiles-5">{cells}</div>'


def _goal_stack(goals: dict) -> str:
    """Thanh cơ cấu mục tiêu nội dung (Lưu / Bàn luận / Lan truyền / Cân bằng)."""
    total = sum(v["posts"] for v in goals.values()) or 1
    order = ["luu", "ban_luan", "lan_truyen", "can_bang"]
    segs, legend = [], []
    for g in order:
        v = goals.get(g)
        if not v:
            continue
        w = v["posts"] / total * 100
        segs.append(f'<span class="g-{g}" style="width:{w:.2f}%" '
                    f'title="{_esc(v["label"])}: {v["posts"]} bài">{v["posts"]}</span>')
        legend.append(f'<span><i class="lg-dot g-{g}"></i>{_esc(v["label"])}: '
                      f'<b>{v["posts"]}</b> bài · like trung vị {_fmt_vi(v.get("like_median"))}</span>')
    return (f'<div class="stack" role="img" aria-label="Cơ cấu mục tiêu nội dung">{"".join(segs)}</div>'
            f'<div class="legend">{"".join(legend)}</div>')


def _bar_rows(rows: list[tuple[str, float | None, str]], *, color_class: str = "",
              highlight: str = "") -> str:
    """Thanh ngang đơn giản: [(nhãn, giá trị, text hiển thị)]."""
    vals = [v for _, v, _ in rows if v is not None and v == v]
    top = max(vals) if vals else 1
    out = []
    for label, v, txt in rows:
        w = 0 if v is None or v != v or not top else v / top * 100
        cls = "hb-fill " + ("fill-accent" if label == highlight else color_class)
        out.append(f'<div class="hb-row"><span class="hb-label">{_esc(label)}</span>'
                   f'<span class="hb-track"><span class="{cls}" style="width:{w:.1f}%"></span></span>'
                   f'<span class="hb-val">{_esc(txt)}</span></div>')
    return "".join(out)


def _read(text_html: str) -> str:
    """Dòng 'Đọc thế nào' dưới mỗi biểu đồ (text_html đã escape ở nơi gọi)."""
    return f'<p class="read"><b>Đọc thế nào:</b> {text_html}</p>'


def _report_trend(result: dict, df: pd.DataFrame | None) -> tuple[str, list, str]:
    top = result.get("top_posts", pd.DataFrame())
    fmt = result.get("formats", pd.DataFrame())
    sounds = result.get("sounds", pd.DataFrame())
    s = result.get("summary") or {}
    body: list[str] = []

    # ---- Tầng 1: Kết luận -------------------------------------------------
    if s:
        body.append(_verdict_block(s.get("verdict", ""), s.get("decisions", [])))
        ratios = s.get("ratios") or {}
        lvl = s.get("save_level")
        lo, hi = (s.get("save_level_band") or [None, None])[:2]
        save_chip = _pill(lvl, {"Cao": "good", "Trung bình": "warn", "Thấp": "bad"}[lvl]) if lvl else ""
        age = s.get("age") or {}
        age_chip = _pill(age["label"], "good" if "vergreen" in age.get("label", "") else
                         "warn" if age.get("label") == "Flash" else "neutral") if age.get("label") and s.get("mode") != "channel" else ""
        conc = s.get("concentration") or {}
        conc_chip = _pill(conc["label"], {"Phân tán": "good", "Vừa": "warn", "Tập trung": "bad"}[conc["label"]]) if conc else ""
        tiles = [
            ("Bài", _fmt_vi(s.get("posts")), f'{_fmt_vi(s.get("creators"))} creator', ""),
            ("Like trung vị", _fmt_vi(s.get("like_median")),
             f'10% bài top ≥ {_fmt_vi(s.get("like_p90"))}', ""),
            ("Lưu / like", _fmt_vi(ratios.get("save"), 2) if ratios.get("save") is not None else "—",
             (f"mốc nền tảng {_fmt_vi(lo, 2)}–{_fmt_vi(hi, 2)}" if ratios.get("save") is not None
              else "nền tảng không có lượt lưu"), save_chip),
            ("Tuổi bài", f'{_fmt_vi(age.get("median"))} ngày' if age.get("median") is not None else "—",
             "trung vị lúc cào", age_chip),
            ("Top 3 creator", _fmt_vi((conc.get("top3_share") or 0) * 100) + "%" if conc else "—",
             f'HHI {_fmt_vi(conc.get("hhi"))}' + (" · mẫu < 50 bài" if conc.get("small_sample") else "")
             if conc else "dữ liệu 1 kênh", conc_chip),
        ]
        body.append(_kpi_tiles(tiles))
    body.append("<!--COMMENTARY-->")

    # ---- Tầng 2: Bằng chứng -----------------------------------------------
    body.append('<div class="tier">Bằng chứng</div>')
    ev = []
    if s.get("goals"):
        g = s["goals"]
        low_share = g.get("lan_truyen", {}).get("like_median")
        note = ("Mỗi bài xếp vào nhóm có tỷ lệ (lưu, bình luận hoặc chia sẻ trên mỗi like) "
                "vượt 1,5 lần trung vị của cả bộ; không vượt thì là Cân bằng.")
        if low_share is not None and g.get("can_bang", {}).get("like_median") and \
                low_share < g["can_bang"]["like_median"]:
            note += (" Nhóm Lan truyền có like thấp hơn: bài được gửi đi nhiều hơn được bấm like, "
                     "đo bằng like sẽ bỏ sót.")
        ev.append(f'<section class="panel"><h2>Mục tiêu nội dung của từng bài</h2>'
                  f'{_goal_stack(g)}{_read(_esc(note))}</section>')
    age = s.get("age") or {}
    if age.get("buckets") and any(b["posts"] for b in age["buckets"]):
        bk = age["buckets"]
        biggest = max(bk, key=lambda b: b["posts"])["label"]
        counts = _bar_rows([(b["label"], b["posts"], str(b["posts"])) for b in bk],
                           color_class="fill-like", highlight=biggest)
        likes = _bar_rows([(b["label"], b["like_median"], _fmt_vi(b["like_median"])) for b in bk],
                          color_class="fill-like")
        if s.get("mode") == "channel":
            note = "Dữ liệu một kênh: tuổi bài là độ cũ của kho video, không phải bài trụ trong kết quả tìm kiếm."
        else:
            note = (f"{_fmt_vi((age.get('old_share') or 0) * 100)}% bài đã hơn 90 ngày tuổi, "
                    f"{_fmt_vi((age.get('new_share') or 0) * 100)}% dưới 30 ngày. Nhiều bài cũ vẫn trụ "
                    "trong kết quả là dấu hiệu chủ đề sống lâu. Like là số cộng dồn nên bài cũ có lợi thế.")
        ev.append(f'<section class="panel"><h2>Tuổi bài lúc cào</h2><div class="age-cols">'
                  f'<div><div class="chart-title">Số bài</div>{counts}</div>'
                  f'<div><div class="chart-title">Like trung vị</div>{likes}</div></div>'
                  f'{_read(_esc(note))}</section>')
    if ev:
        body.append(f'<div class="chart-grid-2 ev-grid">{"".join(ev)}</div>')

    tags = s.get("hashtags") or []
    if tags:
        chips = []
        for t in tags:
            lift = t.get("lift")
            cls = "up" if lift and lift >= 1.2 else "down" if lift is not None and lift <= 0.6 else ""
            chips.append(f'<span class="tchip {cls}" title="like trung vị {_fmt_vi(t["like_median"])}">'
                         f'#{_esc(t["tag"])} <b>{t["posts"]}</b> · {_fmt_vi(lift, 1)}×</span>')
        body.append(_section(
            f"Hashtag trong bộ này ({len(tags)} tag có ≥2 bài)",
            f'<div class="tchips">{"".join(chips)}</div>'
            + _read("số đậm là số bài có tag; “×” là like trung vị của tag so với cả bộ. "
                    '<span class="tchip up">xanh</span> ≥ 1,2 lần, <span class="tchip down">đỏ</span> ≤ 0,6 lần. '
                    "Tag dưới 3 bài chỉ đọc như gợi ý, một bài viral đủ làm lệch.")))

    donut = charts.donut(
        [(str(r["format"]), float(r["so_bai"])) for _, r in fmt.iterrows()],
        title="Cơ cấu format (số bài)", unit="bài") if len(fmt) else ""
    bar = charts.hbar(
        [(str(r["format"]), float(r["diem_tb"])) for _, r in fmt.iterrows()],
        title="Điểm trend TB theo format", color_idx=2) if len(fmt) else ""
    if donut or bar:
        body.append(_section("Cơ cấu & hiệu suất format",
                             f'<div class="chart-grid-2">{donut}{bar}</div>'))
    kwline = _keyword_metric_line(df)
    if kwline:
        body.append(_section("Chỉ số theo từ khoá", kwline))

    # ---- Tầng 3: Dữ liệu đầy đủ -------------------------------------------
    body.append('<div class="tier">Dữ liệu đầy đủ</div>')
    body.append(_section(f"Tất cả {len(top)} bài đã cào — xếp theo điểm trend",
                         '<p class="muted">Điểm trend 0–100 là thứ hạng phần trăm (lưu 40% · chia sẻ 30% · '
                         'bình luận 20% · like 10%). Lọc, sắp xếp và chuyển trang ở thanh công cụ.</p>'
                         + _media_grid(top, grid_id="trend")))
    if len(sounds):
        body.append(_section("Sound watchlist — nhạc đang lên", _table(sounds)))
    return "".join(body), ["CS1_trend_top_posts.xlsx", "CS1_trend_formats.xlsx"], "Trend Radar"


def _llm_payload(command: str, title: str, result: Any, meta: dict) -> dict:
    """
    Dữ liệu tóm tắt gắn vào report cho LLM đọc (tính năng sau).

    Giữ gọn: số tổng hợp + tối đa 15 bài nổi bật, không nhúng toàn bộ dữ liệu.
    """
    payload: dict[str, Any] = {"report": title, "command": command,
                               "platform": meta.get("platform", ""),
                               "keyword": meta.get("keyword", ""),
                               "source_file": meta.get("source_file", "")}
    if isinstance(result, dict) and result.get("summary"):
        payload["summary"] = result["summary"]
        top = result.get("top_posts")
        if isinstance(top, pd.DataFrame) and len(top):
            keep = [c for c in ("title", "liked_count", "collected_count", "comment_count",
                                "share_count", "trend_score", "age_days", "goal_label", "format")
                    if c in top.columns]
            payload["top_posts"] = top.head(15)[keep].to_dict("records")
    elif isinstance(result, pd.DataFrame):
        payload["rows"] = int(len(result))
        payload["columns"] = [str(c) for c in result.columns[:30]]
    return payload


LLM_PROMPT = (
    "Bạn là chuyên gia phân tích nội dung mạng xã hội cho một agency. Dưới đây là dữ liệu "
    "tóm tắt (JSON) của báo cáo “{title}”. Hãy viết NHẬN XÉT TỔNG QUAN bằng tiếng Việt, tối đa "
    "220 chữ, gồm: (1) 3 phát hiện chính có dẫn số liệu; (2) 2 điểm cần thận trọng khi đọc số "
    "(cỡ mẫu, cách thu thập); (3) 3 việc nên làm tiếp theo. Không bịa số không có trong dữ liệu."
)


def _commentary_panel(title: str, payload: dict, auto_lines: list[str]) -> str:
    """
    Ô "Nhận xét tổng quan" có ở MỌI báo cáo.

    Hiện tại: tóm tắt tự động (luật) + ô ghi chú của người phân tích (lưu trên
    trình duyệt) + nút copy prompt & dữ liệu để dán vào ChatGPT.
    Tính năng sau: pipeline LLM điền vào khối `#llm-commentary` (đọc dữ liệu từ
    `<script id="report-summary">`), không cần đổi bố cục.
    """
    data = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    prompt = LLM_PROMPT.format(title=title)
    auto = "".join(f"<li>{_esc(t)}</li>" for t in auto_lines if t)
    auto_html = f'<ul class="auto-notes">{auto}</ul>' if auto else ""
    return f"""
<section class="panel commentary" id="commentary">
  <h2>Nhận xét tổng quan</h2>
  {auto_html}
  <div class="llm-slot" id="llm-commentary" data-status="empty" hidden></div>
  <label class="note-label" for="analyst-note">Nhận xét của người phân tích</label>
  <textarea id="analyst-note" rows="4" placeholder="Ghi nhận xét, hoặc dán nhận xét do ChatGPT viết vào đây. Nội dung được lưu trên trình duyệt này."></textarea>
  <div class="note-actions">
    <button type="button" class="btn-copy" id="copy-llm" data-prompt="{_esc(prompt)}">📋 Copy prompt + dữ liệu cho ChatGPT</button>
    <span class="muted note-status" id="note-status"></span>
  </div>
  <p class="muted note-foot">Sắp có: nhận xét AI tự động hiện ở ô phía trên, đọc từ dữ liệu tóm tắt gắn trong báo cáo.</p>
  <script type="application/json" id="report-summary">{data}</script>
</section>"""


def _report_koc(result: pd.DataFrame, df: pd.DataFrame | None) -> tuple[str, list, str]:
    s = result
    if s is None or s.empty:
        return ('<p class="muted">Không đủ dữ liệu creator (mỗi creator cần ≥5 video).</p>',
                [], "KOC Scorecard")
    rising = int(s["rising"].sum())
    ky_ngay = int((s["verdict"] == "ký ngay").sum())
    tiles = _tiles([
        ("Creator chấm", str(len(s)), "≥5 video"),
        ("Đang lên", str(rising), "velocity≥1.3 & đều≥0.4"),
        ("Điểm cao nhất", f'{s["diem_tong"].max():.0f}', "thang 0–100"),
        ("Ký ngay", str(ky_ngay), "verdict ký ngay"),
    ])
    verdict_counts = s["verdict"].value_counts()
    donut = charts.donut([(str(k), float(v)) for k, v in verdict_counts.items()],
                         title="Cơ cấu kết luận", unit="creator")
    top10 = s.head(10)
    label_col = "nickname" if s["nickname"].astype(str).str.len().gt(0).any() else "creator"
    bar = charts.hbar([(str(r[label_col])[:16], float(r["diem_tong"]))
                       for _, r in top10.iterrows()],
                      title="Top creator theo điểm", color_idx=1)
    body = [tiles,
            _section("Tổng quan", f'<div class="chart-grid-2">{donut}{bar}</div>'),
            _section("Bảng chấm điểm KOC (creator đang lên = ▲)",
                     _table(s, max_rows=40, drop=("creator",)))]
    return "".join(body), ["CS3_koc_scorecard.xlsx", "CS9_rising_creators.xlsx"], "KOC Scorecard"


def _report_sov(result: pd.DataFrame, df: pd.DataFrame | None) -> tuple[str, list, str]:
    g = result
    if g is None or g.empty:
        return ('<p class="muted">Không có bài nào khớp brand_map.</p>', [], "Share of Voice")
    weeks = sorted(g["week"].unique())
    latest = g[g["week"] == weeks[-1]]
    leader = str(latest.sort_values("sov_pct", ascending=False).iloc[0]["brand"])
    tiles = _tiles([
        ("Brand theo dõi", str(g["brand"].nunique()), "trong rổ"),
        ("Dẫn đầu", leader, f"tuần {weeks[-1]}"),
        ("Tuần dữ liệu", str(len(weeks)), "khoảng theo dõi"),
    ])
    donut = charts.donut([(str(r["brand"]), float(r["sov_pct"]))
                          for _, r in latest.iterrows()],
                         title=f"Share of Voice — tuần {weeks[-1]}", unit="%")
    brands = sorted(g["brand"].unique())
    series = []
    for b in brands:
        pts = [float(g[(g["week"] == w) & (g["brand"] == b)]["sov_pct"].sum()) for w in weeks]
        series.append({"name": str(b), "points": pts})
    line = charts.line(series, [str(w) for w in weeks],
                       title="SOV theo tuần", unit="%") if len(weeks) >= 2 else ""
    charts_html = donut + (line or "")
    body = [tiles,
            _section("Cơ cấu tiếng nói", f'<div class="chart-grid-2">{charts_html}</div>'),
            _section("Chi tiết SOV theo tuần", _table(g, max_rows=60))]
    return "".join(body), ["CS11_sov_weekly.xlsx"], "Share of Voice"


def _report_generic(command: str, result: pd.DataFrame,
                    df: pd.DataFrame | None) -> tuple[str, list, str]:
    """insight / opportunity / seasonal / price / angle."""
    meta = {
        "insight": ("Voice of Customer", "CS2_comment_bank.xlsx"),
        "opportunity": ("Opportunity Map", "CS6_opportunity_map.xlsx"),
        "seasonal": ("Seasonal Radar", "CS7_seasonal_radar.xlsx"),
        "price": ("Price & Promo Intel", "CS8_price_intel.xlsx"),
        "angle": ("Angle Library", "angle_library.jsonl"),
    }
    name, xlsx = meta.get(command, (command, ""))
    if result is None or result.empty:
        return f'<p class="muted">Không có dữ liệu cho {_esc(name)}.</p>', [xlsx], name

    chart = ""
    tiles_items: list[tuple[str, str, str]] = []
    if command == "opportunity":
        vc = result["quadrant"].value_counts()
        tiles_items = [("Từ khoá", str(len(result)), "ngách khảo sát"),
                       ("Biển xanh", str(int(vc.get("🌊 biển xanh — đánh ngay", 0))), "đánh ngay"),
                       ("Bão hoà", str(int(vc.get("🔴 bão hoà — tránh", 0))), "nên tránh")]
        chart = charts.hbar([(str(r["source_keyword"])[:16], float(r["save_tb"]))
                             for _, r in result.head(12).iterrows()],
                            title="Save TB theo từ khoá", color_idx=5)
    elif command == "seasonal":
        weeks = sorted(result["week"].unique())
        tiles_items = [("Tuần dữ liệu", str(len(weeks)), "khoảng theo dõi"),
                       ("Đợt spike", str(int(result["spike"].sum())), "eng > 1.5× TB trượt")]
        kws = sorted(result["source_keyword"].unique())[:6]
        series = []
        for k in kws:
            sub = result[result["source_keyword"] == k]
            pts = [float(sub[sub["week"] == w]["eng_tong"].sum()) for w in weeks]
            series.append({"name": str(k)[:12], "points": pts})
        chart = charts.line(series, [str(w) for w in weeks],
                            title="Engagement theo tuần") if len(weeks) >= 2 else ""
    elif command == "price":
        tiles_items = [("Mẫu có giá/KM", str(len(result)), "trích được")]
        chart = charts.hbar([(str(r["nguon_keyword"])[:16] or "(chung)", float(r["eng_total"]))
                             for _, r in result.head(10).iterrows()],
                            title="Engagement mẫu có giá/KM", color_idx=4)
    elif command == "insight":
        tiles_items = [("Bình luận", str(len(result)), "đã lọc & xếp theo like")]
        col = "like_count" if "like_count" in result.columns else None
        if col:
            top = result.nlargest(8, col)
            chart = charts.hbar([(str(r["content"])[:28], float(r[col]))
                                 for _, r in top.iterrows()],
                                title="Bình luận nổi bật (theo like)", color_idx=3)
    elif command == "angle":
        tiles_items = [("Angle", str(len(result)), "top theo trend")]
        if "format" in result.columns:
            vc = result["format"].value_counts()
            chart = charts.donut([(str(k), float(v)) for k, v in vc.items()],
                                 title="Cơ cấu format của angle", unit="angle")

    body = [_tiles(tiles_items) if tiles_items else ""]
    if chart:
        body.append(_section("Tổng quan", chart))
    body.append(_section(f"Dữ liệu {name}", _table(result, max_rows=60)))
    return "".join(body), [xlsx], name


_RICH = {"trend": _report_trend, "koc": _report_koc, "sov": _report_sov,
         "playbook": _report_playbook, "hook": _report_hook,
         "sound": _report_sound, "moodboard": _report_moodboard}


_SLUG_RE = re.compile(r"[^\w\-]+", re.UNICODE)


def report_slug(*parts: object, max_len: int = 40) -> str:
    """
    Ghép các mảnh (nền tảng, từ khoá...) thành slug an toàn cho tên file.

    Rỗng -> "" để `build_report` giữ nguyên tên file cũ.
    """
    raw = "_".join(str(p).strip() for p in parts if p is not None and str(p).strip())
    slug = _SLUG_RE.sub("_", raw).strip("_")
    return slug[:max_len].strip("_")


def build_report(command: str, result: Any, *, df: pd.DataFrame | None = None,
                 meta: dict | None = None, slug: str = "") -> Path:
    """
    Sinh 1 file HTML báo cáo cho `command`, trả về Path.

    result: dict (trend) hoặc DataFrame (các lệnh khác).
    df: DataFrame chuẩn hoá gốc (để vẽ chỉ số theo keyword cho trend).
    meta: {"keyword", "platform", "source_file"} — hiển thị ở header.
    slug: hậu tố tên file để 2 lần chạy cùng lệnh không ghi đè nhau (vd chạy
        `trend` cho Douyin rồi cho XHS). Để trống -> giữ nguyên tên cũ
        `{command}_report.html` (tương thích ngược với link/doc đã có).
    """
    meta = meta or {}
    if command in _RICH:
        body, _, title = _RICH[command](result, df)
    else:
        body, _, title = _report_generic(command, result, df)

    # Report có khung "Kết luận" riêng (đặt chỗ <!--COMMENTARY-->) thì không lặp lại
    # kết luận trong ô nhận xét; ô này dành cho người phân tích và LLM.
    auto_lines: list[str] = []
    panel = _commentary_panel(title, _llm_payload(command, title, result, meta), auto_lines)
    body = body.replace("<!--COMMENTARY-->", panel, 1) if "<!--COMMENTARY-->" in body \
        else panel + body

    REPORT_DIR.mkdir(exist_ok=True)
    name = f"{command}_{slug}_report.html" if slug else f"{command}_report.html"
    out = REPORT_DIR / name
    out.write_text(_page(title, command, body, meta), encoding="utf-8")
    print(f"[✓] Xuất báo cáo HTML: {out}")
    return out


# ---------------------------------------------------------------------------
# Khung trang (CSS + JS tự chứa, theme sáng/tối)
# ---------------------------------------------------------------------------

def _page(title: str, command: str, body: str, meta: dict) -> str:
    kw = meta.get("keyword", "")
    platform = meta.get("platform", "")
    src = meta.get("source_file", "")
    gen = meta.get("generated") or datetime.now().strftime("%d/%m/%Y %H:%M")
    sub_bits = [b for b in [platform, kw] if b]
    subtitle = " · ".join(sub_bits) if sub_bits else "Báo cáo phân tích"

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — DigiAds</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap">
<style>{_CSS}</style>
<script>{_JS}</script></head>
<body><div class="wrap">
<header class="rpt-head">
  <div>
    <div class="eyebrow">DigiAds Kit · {_esc(command).upper()}</div>
    <h1>{_esc(title)}</h1>
    <div class="sub">{_esc(subtitle)}</div>
  </div>
  <div class="meta">Tạo lúc <b>{_esc(gen)}</b><br>{_esc(src)}</div>
</header>
{body}
<footer>Nguồn: MediaCrawler + DigiAds Kit · dữ liệu công khai, nghiên cứu nội bộ ·
creator ẩn danh theo Nghị định 13/2023</footer>
</div></body></html>"""


# JS dùng chung: lưới thẻ (lọc/sắp/phân trang), bảng phân trang, ô nhận xét.
# Viết ES5 thuần để mở được bằng mọi trình duyệt, kể cả file offline.
_JS = r"""
function DAMG(id){
  var root=document.getElementById(id); if(!root) return;
  var grid=document.getElementById(id+"-grid"), search=document.getElementById(id+"-search"),
      sortSel=document.getElementById(id+"-sort"), chipRow=document.getElementById(id+"-chips"),
      kwSel=document.getElementById(id+"-kw"), goalSel=document.getElementById(id+"-goal"),
      ageSel=document.getElementById(id+"-age"), sizeSel=document.getElementById(id+"-size"),
      info=document.getElementById(id+"-info"), pagesEl=document.getElementById(id+"-pages"),
      prev=document.getElementById(id+"-prev"), next=document.getElementById(id+"-next");
  var cards=Array.prototype.slice.call(grid.children), total=cards.length;
  var activeFmt="__all__", page=0;
  function num(c,k){return parseFloat(c.getAttribute("data-"+k)||0)||0;}
  function matches(c){
    var q=(search.value||"").toLowerCase();
    if(activeFmt!=="__all__"&&c.getAttribute("data-format")!==activeFmt) return false;
    if(q&&(c.getAttribute("data-hook-lc")||"").indexOf(q)===-1) return false;
    if(kwSel&&kwSel.value&&c.getAttribute("data-kw")!==kwSel.value) return false;
    if(goalSel&&goalSel.value&&c.getAttribute("data-goal")!==goalSel.value) return false;
    if(ageSel&&ageSel.value){var a=c.getAttribute("data-age"); if(a==="") return false;
      var r=ageSel.value.split("-"), v=parseFloat(a); if(v<+r[0]||v>=+r[1]) return false;}
    return true;
  }
  function sortCards(){var k=sortSel.value;
    cards.sort(function(a,b){return num(b,k)-num(a,k);});
    cards.forEach(function(c){grid.appendChild(c);});}
  function render(){
    var size=parseInt(sizeSel.value,10)||0, list=cards.filter(matches), n=list.length;
    var pages=size?Math.max(1,Math.ceil(n/size)):1; if(page>pages-1) page=pages-1;
    var from=size?page*size:0, to=size?from+size:n;
    cards.forEach(function(c){c.style.display="none";});
    list.slice(from,to).forEach(function(c){c.style.display="";});
    info.textContent=n?("Hiển thị "+(from+1)+"–"+Math.min(to,n)+" / "+n+" bài"+(n<total?" khớp lọc (tổng "+total+")":"")):"Không có bài khớp bộ lọc.";
    prev.disabled=!size||page===0; next.disabled=!size||page>=pages-1;
    pagesEl.innerHTML=""; if(size&&pages>1){var s=Math.max(0,page-3),e=Math.min(pages,s+7);
      for(var i=s;i<e;i++){var b=document.createElement("button");b.type="button";b.textContent=i+1;
        if(i===page) b.setAttribute("aria-current","page"); (function(p){b.onclick=function(){page=p;render();top();};})(i); pagesEl.appendChild(b);}}
  }
  function top(){var y=root.getBoundingClientRect().top+window.pageYOffset-12; if(window.pageYOffset>y) window.scrollTo(0,y);}
  chipRow.addEventListener("click",function(e){var chip=e.target.closest(".fchip"); if(!chip) return;
    Array.prototype.forEach.call(chipRow.children,function(c){c.classList.remove("active");});
    chip.classList.add("active"); activeFmt=chip.getAttribute("data-fmt"); page=0; render();});
  [search].forEach(function(el){el.addEventListener("input",function(){page=0;render();});});
  [kwSel,goalSel,ageSel,sizeSel].forEach(function(el){if(el) el.addEventListener("change",function(){page=0;render();});});
  sortSel.addEventListener("change",function(){sortCards();page=0;render();});
  prev.addEventListener("click",function(){page--;render();top();});
  next.addEventListener("click",function(){page++;render();top();});
  grid.addEventListener("click",function(e){
    var copyBtn=e.target.closest(".btn-copy");
    if(copyBtn){var text=copyBtn.getAttribute("data-copy")||"";
      if(navigator.clipboard){navigator.clipboard.writeText(text).then(function(){var old=copyBtn.textContent;
        copyBtn.textContent="✓ Đã copy"; setTimeout(function(){copyBtn.textContent=old;},1500);});}
      return;}
    var moreBtn=e.target.closest(".mcard-more");
    if(moreBtn){var hookEl=moreBtn.previousElementSibling; hookEl.classList.toggle("mcard-hook--expanded");
      moreBtn.textContent=hookEl.classList.contains("mcard-hook--expanded")?"Thu gọn ▴":"Xem đầy đủ ▾";}
  });
  render();
}
document.addEventListener("DOMContentLoaded",function(){
  // Bảng: phân trang cho bảng dài
  Array.prototype.forEach.call(document.querySelectorAll("[data-dtable]"),function(box){
    var rows=Array.prototype.slice.call(box.querySelectorAll("tbody tr")), bar=box.querySelector(".pager-bar");
    if(!bar) return;
    var sel=bar.querySelector("[data-size]"), info=bar.querySelector(".pager-info"), pg=bar.querySelector(".pager-pages"),
        prev=bar.querySelector("[data-prev]"), next=bar.querySelector("[data-next]"), page=0;
    function render(){var size=parseInt(sel.value,10)||0, n=rows.length, pages=size?Math.ceil(n/size):1;
      if(page>pages-1) page=pages-1; var from=size?page*size:0, to=size?from+size:n;
      rows.forEach(function(r,i){r.style.display=(i>=from&&i<to)?"":"none";});
      info.textContent="Dòng "+(from+1)+"–"+Math.min(to,n)+" / "+n;
      prev.disabled=!size||page===0; next.disabled=!size||page>=pages-1;
      pg.textContent=size?("Trang "+(page+1)+"/"+pages):"";}
    sel.addEventListener("change",function(){page=0;render();});
    prev.addEventListener("click",function(){page--;render();}); next.addEventListener("click",function(){page++;render();});
    render();
  });
  // Ô nhận xét: lưu trên trình duyệt + copy prompt cho ChatGPT
  var note=document.getElementById("analyst-note"), status=document.getElementById("note-status");
  if(note){var key="digiads-note:"+location.pathname;
    try{note.value=localStorage.getItem(key)||"";}catch(e){}
    var t; note.addEventListener("input",function(){clearTimeout(t); t=setTimeout(function(){
      try{localStorage.setItem(key,note.value); status.textContent="Đã lưu trên trình duyệt này";}
      catch(e){status.textContent="Trình duyệt không cho lưu — hãy copy nhận xét ra ngoài";}},400);});}
  var btn=document.getElementById("copy-llm");
  if(btn){btn.addEventListener("click",function(){
    var data=(document.getElementById("report-summary")||{}).textContent||"{}";
    var text=(btn.getAttribute("data-prompt")||"")+"\n\nDỮ LIỆU:\n"+data;
    function done(){status.textContent="Đã copy — dán vào ChatGPT, rồi dán nhận xét trả về vào ô trên";}
    if(navigator.clipboard){navigator.clipboard.writeText(text).then(done,function(){status.textContent="Không copy được — trình duyệt chặn clipboard";});}
  });}
});
"""


_CSS = """
:root{color-scheme:light;
 --page:#f4f5f7;--surface:#ffffff;--surface-2:#eef0f3;--ink:#12151a;--ink-2:#3d4550;
 --muted:#687180;--rule:#dde1e7;--grid:#dde1e7;--accent:#2446c7;--accent-ink:#ffffff;
 --accent-soft:#e3e8fb;
 --good:#17803d;--warn:#a86a00;--bad:#d23a3a;
 --good-bg:#e4f4e9;--warn-bg:#fbf0d9;--bad-bg:#fbe5e3;
 --m-like:#5d6b7e;--m-save:#0d8a7d;--m-comment:#7a4fc4;--m-share:#e2761b;
 --c-1:#2a78d6;--c-2:#008300;--c-3:#e87ba4;--c-4:#eda100;--c-5:#1baf7a;--c-6:#4a3aa7;
 --font:"Be Vietnam Pro","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
 --zh:"Microsoft YaHei","PingFang SC","Noto Sans SC","Be Vietnam Pro",sans-serif;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){color-scheme:dark;
 --page:#0f1216;--surface:#161a20;--surface-2:#1d222a;--ink:#eef1f5;--ink-2:#c1c8d2;
 --muted:#8a94a3;--rule:#2a313b;--grid:#2a313b;--accent:#7d95ff;--accent-ink:#0b1030;
 --accent-soft:#1f2748;
 --good:#4cc26f;--warn:#e0a53a;--bad:#f06a62;--good-bg:#15301f;--warn-bg:#352a12;--bad-bg:#3a1b1b;
 --m-like:#9aa8bb;--m-save:#2cc0ae;--m-comment:#a887ec;--m-share:#f59a4a;
 --c-1:#3987e5;--c-2:#008300;--c-3:#d55181;--c-4:#c98500;--c-5:#199e70;--c-6:#9085e9;}}
:root[data-theme=dark]{color-scheme:dark;
 --page:#0f1216;--surface:#161a20;--surface-2:#1d222a;--ink:#eef1f5;--ink-2:#c1c8d2;
 --muted:#8a94a3;--rule:#2a313b;--grid:#2a313b;--accent:#7d95ff;--accent-ink:#0b1030;
 --accent-soft:#1f2748;
 --good:#4cc26f;--warn:#e0a53a;--bad:#f06a62;--good-bg:#15301f;--warn-bg:#352a12;--bad-bg:#3a1b1b;
 --m-like:#9aa8bb;--m-save:#2cc0ae;--m-comment:#a887ec;--m-share:#f59a4a;
 --c-1:#3987e5;--c-2:#008300;--c-3:#d55181;--c-4:#c98500;--c-5:#199e70;--c-6:#9085e9;}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--page);color:var(--ink);font-family:var(--font);
 font-size:14px;line-height:1.5;padding:28px 16px}
.wrap{max-width:1200px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
.rpt-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap;
 border-bottom:1px solid var(--rule);padding-bottom:14px}
.eyebrow{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:700}
.rpt-head h1{margin:4px 0 0;font-size:28px;font-weight:700;letter-spacing:-.01em;text-wrap:balance}
.rpt-head .sub{margin-top:4px;color:var(--ink-2);font-size:13.5px}
.rpt-head .meta{text-align:right;color:var(--muted);font-size:12px}
.rpt-head .meta b{color:var(--ink-2)}
/* Tầng kết luận */
.verdict{background:var(--accent-soft);border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;gap:10px}
.verdict-text{margin:0;font-size:18px;font-weight:700;line-height:1.35;text-wrap:balance}
.decisions{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}
.decisions li{background:var(--surface);border-radius:9px;padding:9px 12px;display:flex;gap:9px;font-size:13px;color:var(--ink-2)}
.decisions .dn{font-weight:700;color:var(--accent)}
.tier{font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:var(--muted);
 display:flex;align-items:center;gap:10px;margin-top:6px}
.tier::after{content:"";flex:1;height:1px;background:var(--rule)}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.tiles-5{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 14px}
.t-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.t-value{font-size:24px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums;text-wrap:balance}
.t-note{font-size:12px;color:var(--ink-2);margin-top:3px;display:flex;flex-wrap:wrap;gap:5px;align-items:center}
.pill{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:1px 8px;white-space:nowrap}
.pill-good{background:var(--good-bg);color:var(--good)}.pill-warn{background:var(--warn-bg);color:var(--warn)}
.pill-bad{background:var(--bad-bg);color:var(--bad)}.pill-neutral{background:var(--surface-2);color:var(--ink-2)}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:15px 17px;min-width:0}
.panel h2{margin:0 0 12px;font-size:15px;font-weight:700}
.read{margin:12px 0 0;font-size:12.5px;color:var(--ink-2);background:var(--surface-2);border-radius:8px;padding:8px 11px}
.read b{color:var(--ink)}
.ev-grid{align-items:stretch}
.age-cols{display:grid;grid-template-columns:1fr;gap:6px}
/* Cơ cấu mục tiêu nội dung */
.stack{display:flex;height:28px;border-radius:7px;overflow:hidden}
.stack span{display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700;min-width:0}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;font-size:12px;color:var(--ink-2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.g-luu{background:var(--m-save)}.g-ban_luan{background:var(--m-comment)}
.g-lan_truyen{background:var(--m-share)}.g-can_bang{background:var(--m-like)}
.fill-like{background:var(--m-like)}.fill-accent{background:var(--accent)}
/* Hashtag */
.tchips{display:flex;flex-wrap:wrap;gap:6px}
.tchip{font-size:12px;border-radius:999px;padding:3px 10px;border:1px solid var(--rule);background:var(--surface);
 font-family:var(--zh);color:var(--ink-2)}
.tchip b{font-family:var(--font);font-variant-numeric:tabular-nums;color:var(--ink)}
.tchip.up{border-color:var(--good);background:var(--good-bg)}
.tchip.down{border-color:var(--bad);background:var(--bad-bg)}
/* Nhận xét tổng quan */
.commentary{border-left:4px solid var(--accent)}
.auto-notes{margin:0 0 12px;padding-left:18px;color:var(--ink-2);font-size:13px;display:flex;flex-direction:column;gap:4px}
.auto-notes li:first-child{color:var(--ink);font-weight:600}
.llm-slot{background:var(--surface-2);border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:13px}
.note-label{display:block;font-size:12px;font-weight:600;color:var(--ink-2);margin-bottom:5px}
#analyst-note{width:100%;font:inherit;font-size:13px;color:var(--ink);background:var(--surface-2);
 border:1px solid var(--rule);border-radius:8px;padding:9px 11px;resize:vertical}
#analyst-note:focus-visible,.mg-search:focus-visible,.mg-sort:focus-visible,button:focus-visible,a:focus-visible{
 outline:2px solid var(--accent);outline-offset:1px}
.note-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px}
.note-status{font-size:12px}
.note-foot{font-size:11.5px;margin:8px 0 0}
.chart-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.chart-title{font-size:12px;color:var(--ink-2);font-weight:600;margin-bottom:8px}
.chart-empty{display:flex;align-items:center;justify-content:center;color:var(--muted);
 font-size:12px;background:var(--surface-2);border-radius:6px}
.donut-wrap{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.donut-total{font-size:20px;font-weight:700;fill:var(--ink)}
.donut-unit{font-size:10px;fill:var(--muted)}
.donut-legend{display:flex;flex-direction:column;gap:5px;min-width:120px}
.lg-row{display:flex;align-items:center;gap:7px;font-size:12px}
.lg-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;display:inline-block}
.lg-label{color:var(--ink-2);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lg-val{font-weight:700;font-variant-numeric:tabular-nums}
.hb-row{display:grid;grid-template-columns:minmax(80px,120px) 1fr 70px;gap:8px;align-items:center;margin:7px 0}
.hb-label{font-size:12px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hb-track{display:block;height:13px;background:var(--surface-2);border-radius:4px;overflow:hidden}
.hb-fill{display:block;height:100%;border-radius:4px}
.hb-val{font-size:12px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink)}
.chart-line svg,.chart-hbar,.chart-donut{max-width:100%}
.chart-heatmap{overflow-x:auto;max-width:100%}
.hm-lbl{fill:var(--ink-2);font-size:10.5px}
.hm-cell-txt{font-size:9.5px;font-variant-numeric:tabular-nums}
.ax{fill:var(--muted);font-size:10px}
.endlbl{font-size:10.5px;font-weight:700}
svg text{font-family:var(--font)}
/* Bảng */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;background:var(--surface-2);
 color:var(--muted);font-weight:600;padding:7px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:7px 10px;border-bottom:1px solid var(--rule);color:var(--ink-2);vertical-align:top;max-width:360px}
tbody tr:hover td{background:var(--surface-2)}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td .num{font-variant-numeric:tabular-nums}
a{color:var(--accent);text-decoration:none;font-weight:600;white-space:nowrap}
a:hover{text-decoration:underline}
.muted{color:var(--muted)}
.tbl-more{font-size:11.5px;margin:8px 0 0}
.chip{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700}
.chip-good{background:var(--good-bg);color:var(--good)}
.chip-warn{background:var(--warn-bg);color:var(--warn)}
.chip-muted{background:var(--surface-2);color:var(--muted);border:1px solid var(--rule)}
.limits{margin:0;padding-left:20px;color:var(--ink-2);font-size:12.5px}
.limits li{margin:4px 0}
.sub-h{font-size:12.5px;font-weight:700;color:var(--ink-2);margin:14px 0 8px;
 text-transform:uppercase;letter-spacing:.04em}
.sub-h:first-child{margin-top:0}
footer{border-top:1px solid var(--rule);padding-top:11px;font-size:11px;color:var(--muted)}
/* Phân trang (lưới thẻ + bảng) */
.pager-bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;
 margin-top:12px;font-size:12.5px;color:var(--muted)}
.pager{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.pager button{font:inherit;font-size:12.5px;border:1px solid var(--rule);background:var(--surface);
 color:var(--ink-2);border-radius:6px;padding:4px 10px;cursor:pointer}
.pager button[aria-current=page]{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:700}
.pager button:disabled{opacity:.4;cursor:default}
.pager-pages{display:flex;gap:4px}

/* --- Media grid (nghien cuu trend / clone y tuong) --- */
.grid-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.mg-search{flex:1;min-width:180px;background:var(--surface-2);border:1px solid var(--rule);
 border-radius:7px;padding:7px 10px;font-size:12.5px;color:var(--ink);font-family:inherit}
.mg-search::placeholder{color:var(--muted)}
.mg-sort{background:var(--surface-2);border:1px solid var(--rule);border-radius:7px;
 padding:7px 10px;font-size:12.5px;color:var(--ink);font-family:inherit}
.chip-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.fchip{background:var(--surface-2);border:1px solid var(--rule);border-radius:999px;
 padding:5px 12px;font-size:11.5px;color:var(--ink-2);cursor:pointer;font-family:inherit;white-space:nowrap}
.fchip.active{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:700}
.mcard-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.mcard-grid--mood{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.mcard{background:var(--surface);border:1px solid var(--rule);border-radius:10px;overflow:hidden;
 display:flex;flex-direction:column}
.mcard:hover{border-color:var(--accent)}
.mcard-thumb{position:relative;display:block;aspect-ratio:9/12;background:
 linear-gradient(135deg,var(--surface-2),var(--rule));overflow:hidden;text-decoration:none}
.mcard-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.mcard-thumb--broken img{display:none}
.mcard-thumb--broken::before{content:"🎬";position:absolute;inset:0;display:flex;
 align-items:center;justify-content:center;font-size:34px;opacity:.35}
.mcard-play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
 font-size:26px;color:#fff;background:rgba(0,0,0,0);opacity:0;transition:opacity .15s}
.mcard-thumb:hover .mcard-play{opacity:1;background:rgba(0,0,0,.35)}
.mcard-rank{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.65);color:#fff;
 font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:10px}
.mcard-score{position:absolute;top:6px;right:6px;background:var(--accent);color:var(--accent-ink);
 font-size:11px;font-weight:800;padding:2px 8px;border-radius:10px;font-variant-numeric:tabular-nums}
.mcard-body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:7px;flex:1}
.mcard-tags{display:flex;gap:5px;flex-wrap:wrap}
.mcard-tags .tag{font-size:10px;border:1px solid var(--rule);border-radius:4px;padding:1px 6px;
 color:var(--ink-2);text-transform:uppercase;letter-spacing:.02em;background:none}
.mcard-tags .tag-kw{color:var(--accent);border-color:var(--accent)}
.mcard-tags .tag-goal{background:none;font-weight:700}
.tag-goal.g-luu{color:var(--m-save);border-color:var(--m-save)}
.tag-goal.g-ban_luan{color:var(--m-comment);border-color:var(--m-comment)}
.tag-goal.g-lan_truyen{color:var(--m-share);border-color:var(--m-share)}
.tag-goal.g-can_bang{color:var(--m-like);border-color:var(--m-like)}
.mcard-hook{font-size:12.5px;color:var(--ink);margin:0;line-height:1.45;font-family:var(--zh);
 display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.mcard-hook--expanded{-webkit-line-clamp:unset;overflow:visible}
.mcard-more{align-self:flex-start;background:none;border:none;color:var(--accent);
 font-size:11px;font-weight:600;cursor:pointer;padding:0;font-family:inherit}
.mcard-stats{display:flex;gap:9px;flex-wrap:wrap;font-size:11.5px;font-variant-numeric:tabular-nums;font-weight:600}
.st-like{color:var(--m-like)}.st-save{color:var(--m-save)}.st-share{color:var(--m-share)}.st-comment{color:var(--m-comment)}
.mcard-rates{display:flex;gap:12px;font-size:11px;color:var(--muted)}
.mcard-rates b{color:var(--ink-2);font-variant-numeric:tabular-nums}
.mcard-meta{font-size:11px;color:var(--muted);display:flex;gap:4px;flex-wrap:wrap}
.mcard-meta a{color:var(--muted);font-weight:400}
.mcard-actions{display:flex;gap:8px;margin-top:auto;padding-top:4px;flex-wrap:wrap}
.btn-copy{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
 padding:5px 9px;font-size:11px;color:var(--ink-2);cursor:pointer;font-family:inherit}
.btn-copy:hover{border-color:var(--accent);color:var(--accent)}
.mcard-open{background:var(--accent);color:var(--accent-ink);border-radius:6px;
 padding:5px 10px;font-size:11px;font-weight:700;text-decoration:none}
.mcard-dl{background:var(--surface);border:1px solid var(--accent);color:var(--accent);
 border-radius:6px;padding:5px 10px;font-size:11px;font-weight:700;text-decoration:none}
.mcard-dl:hover{background:var(--accent);color:var(--accent-ink);text-decoration:none}
.dl-sep{color:var(--muted);margin:0 5px;font-weight:400}
.dl-link{white-space:nowrap}
@media (prefers-reduced-motion:reduce){.mcard-play{transition:none}}
@media(max-width:800px){.tiles{grid-template-columns:repeat(2,1fr)}
 .chart-grid-2{grid-template-columns:1fr}
 .mcard-grid{grid-template-columns:repeat(auto-fill,minmax(160px,1fr))}}
"""
