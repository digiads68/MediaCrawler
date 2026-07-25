# -*- coding: utf-8 -*-
"""
Khối UI dùng chung cho mọi loại dashboard.

Gồm: tiles KPI, panel, callout, danh sách insight, bảng, lưới thẻ video (có nút
n8n), và các biểu đồ bổ sung mà kit.report.charts chưa có — heatmap giờ×thứ,
thanh benchmark (bullet), ma trận format×từ khoá, scatter cơ hội, timeline bài.

Biểu đồ cơ bản (donut/hbar/line) dùng lại `kit.report.charts` — không vẽ lại.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pandas as pd

from kit.dashboard.adapters import PLATFORM_LABELS
from kit.dashboard.theme import N8N_ACTIONS, esc
from kit.report import charts

fmt = charts._fmt  # định dạng số gọn 12.3K/1.2M (một nguồn duy nhất)


def human(v: object) -> str:
    """Số gọn, an toàn với None/NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return fmt(float(v))
    except (TypeError, ValueError):
        return "—"


def pct(v: object, digits: int = 1) -> str:
    """Tỷ lệ 0..1 -> '12.3%'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# Khối bố cục
# ---------------------------------------------------------------------------

def tiles(items: Sequence[dict[str, str]], *, cols: int = 4) -> str:
    """Hàng thẻ KPI. items: [{label, value, note}]."""
    cls = "tiles tiles--5" if cols == 5 else "tiles"
    cells = "".join(
        f'<div class="tile"><div class="t-label">{esc(it["label"])}</div>'
        f'<div class="t-value">{esc(it["value"])}</div>'
        f'<div class="t-note">{esc(it.get("note", ""))}</div></div>'
        for it in items)
    return f'<div class="{cls}">{cells}</div>'


def panel(title: str, inner: str, *, sub: str = "") -> str:
    """Khung panel có tiêu đề + mô tả ngắn."""
    subhtml = f'<div class="panel-sub">{esc(sub)}</div>' if sub else ""
    return f'<section class="panel"><h2>{esc(title)}</h2>{subhtml}{inner}</section>'


def callout(text_html: str, *, warn: bool = False) -> str:
    """Ô nhấn mạnh (cho phép HTML inline đã escape từ trước)."""
    cls = "callout callout--warn" if warn else "callout"
    return f'<div class="{cls}">{text_html}</div>'


def insights(items: Sequence[tuple[str, str]]) -> str:
    """
    Danh sách "điều nên làm" — mỗi dòng (nhãn, nội_dung_html).

    Đây là phần biến số liệu thành hành động cho team content.
    """
    if not items:
        return '<p class="muted">Chưa đủ dữ liệu để rút kết luận.</p>'
    lis = "".join(f'<li><span class="ins-tag">{esc(tag)}</span>{body}</li>'
                  for tag, body in items)
    return f'<ul class="insights">{lis}</ul>'


def table(headers: Sequence[tuple[str, bool]], rows: Sequence[Sequence[str]],
          *, cls: str = "") -> str:
    """
    Bảng đơn giản. headers: [(nhãn, là_số)]; rows: ô đã render sẵn (HTML).
    """
    if not rows:
        return '<p class="muted">Không có dữ liệu.</p>'
    head = "".join(f'<th class="num">{esc(h)}</th>' if num else f'<th>{esc(h)}</th>'
                   for h, num in headers)
    body = []
    for r in rows:
        cells = "".join(
            f'<td class="num">{c}</td>' if headers[i][1] else f'<td>{c}</td>'
            for i, c in enumerate(r))
        body.append(f"<tr>{cells}</tr>")
    klass = f' class="{cls}"' if cls else ""
    return (f'<div class="tbl-wrap"><table{klass}><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


# ---------------------------------------------------------------------------
# Biểu đồ bổ sung
# ---------------------------------------------------------------------------

def heatmap(matrix: Sequence[Sequence[float]], *, row_labels: Sequence[str],
            col_labels: Sequence[str], title: str = "",
            note: str = "", color_idx: int = 1) -> str:
    """
    Heatmap dạng bảng (giờ × thứ). Ô đậm = giá trị cao.

    Dùng opacity trên 1 màu nền -> vẫn đọc được ở cả theme sáng/tối, và có
    số trong ô nên không phụ thuộc riêng vào màu (chuẩn khả dụng CVD).
    """
    flat = [v for row in matrix for v in row]
    vmax = max(flat) if flat else 0
    if vmax <= 0:
        return _empty("Không đủ dữ liệu thời gian")
    head = "".join(f'<th>{esc(c)}</th>' for c in col_labels)
    rows_html = []
    for i, row in enumerate(matrix):
        cells = []
        for j, v in enumerate(row):
            op = 0.08 + 0.92 * (v / vmax) if v else 0.05
            txt = fmt(v) if v else ""
            tip = f"{row_labels[i]} · {col_labels[j]}: {fmt(v)}"
            cells.append(f'<td class="hm-cell" style="background:color-mix(in srgb,'
                         f'var(--c-{color_idx}) {op * 100:.0f}%, var(--surface-2))"'
                         f' title="{esc(tip)}">{txt}</td>')
        rows_html.append(f'<tr><th class="row">{esc(row_labels[i])}</th>'
                         f'{"".join(cells)}</tr>')
    ttl = f'<div class="chart-title">{esc(title)}</div>' if title else ""
    lg = (f'<div class="hm-legend"><span>Thấp</span>'
          f'<span class="hm-sw" style="background:color-mix(in srgb,var(--c-{color_idx}) 10%,var(--surface-2))"></span>'
          f'<span class="hm-sw" style="background:color-mix(in srgb,var(--c-{color_idx}) 50%,var(--surface-2))"></span>'
          f'<span class="hm-sw" style="background:var(--c-{color_idx})"></span>'
          f'<span>Cao</span>{" · " + esc(note) if note else ""}</div>')
    return (f'{ttl}<div class="tbl-wrap"><table class="hm"><thead><tr><th></th>'
            f'{head}</tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>{lg}')


def bullets(rows: Sequence[dict[str, Any]], *, title: str = "") -> str:
    """
    Thanh benchmark: giá trị thực vs mốc tham chiếu (vạch dọc).

    rows: [{label, value, ref, vmax, text}] — value/ref cùng đơn vị.
    """
    if not rows:
        return _empty("Không đủ dữ liệu")
    out = []
    for r in rows:
        vmax = float(r.get("vmax") or 0) or max(float(r["value"]), float(r["ref"]), 1)
        w = min(100.0, float(r["value"]) / vmax * 100)
        mk = min(100.0, float(r["ref"]) / vmax * 100)
        out.append(
            f'<div class="bullet-row">'
            f'<span class="bullet-label">{esc(r["label"])}</span>'
            f'<span class="bullet-track">'
            f'<span class="bullet-fill" style="width:{w:.1f}%"></span>'
            f'<span class="bullet-mark" style="left:{mk:.1f}%" '
            f'title="Mốc tham chiếu"></span></span>'
            f'<span class="bullet-val">{esc(r.get("text", ""))}</span></div>')
    ttl = f'<div class="chart-title">{esc(title)}</div>' if title else ""
    return f'{ttl}{"".join(out)}'


def matrix(cells: dict[tuple[str, str], float], *, rows: Sequence[str],
           cols: Sequence[str], title: str = "", note: str = "",
           counts: dict[tuple[str, str], int] | None = None) -> str:
    """
    Ma trận 2 chiều (vd. format × từ khoá) — giá trị = tương tác TB.

    counts: số bài mỗi ô (hiện dạng chú thích nhỏ, để biết ô có đáng tin không).
    """
    vals = [v for v in cells.values() if v > 0]
    if not vals:
        return _empty("Không đủ dữ liệu")
    vmax = max(vals)
    head = "".join(f'<th class="num">{esc(c)}</th>' for c in cols)
    body = []
    for r in rows:
        tds = []
        for c in cols:
            v = cells.get((r, c), 0.0)
            n = (counts or {}).get((r, c), 0)
            if v <= 0:
                tds.append('<td class="mx-cell muted">—</td>')
                continue
            op = 0.10 + 0.90 * (v / vmax)
            sub = f'<br><span class="small muted">{n} bài</span>' if n else ""
            tds.append(f'<td class="mx-cell" style="background:color-mix(in srgb,'
                       f'var(--c-5) {op * 100:.0f}%, var(--surface-2))">'
                       f'{fmt(v)}{sub}</td>')
        body.append(f'<tr><td class="lbl">{esc(r)}</td>{"".join(tds)}</tr>')
    ttl = f'<div class="chart-title">{esc(title)}</div>' if title else ""
    nt = f'<p class="muted small" style="margin-top:8px">{esc(note)}</p>' if note else ""
    return (f'{ttl}<div class="tbl-wrap"><table class="mx"><thead><tr><th></th>'
            f'{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>{nt}')


def scatter_opportunity(items: Sequence[dict[str, Any]], *, w: int = 560,
                        h: int = 300) -> str:
    """Scatter cơ hội ngách: X = số bài (bão hoà), Y = tương tác TB (sức hút)."""
    if not items:
        return _empty("Không đủ dữ liệu")
    pad_l, pad_r, pad_t, pad_b = 46, 80, 16, 34
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    vmax = (max(it["volume"] for it in items) or 1) * 1.18
    emax = (max(it["eng"] for it in items) or 1) * 1.18
    vmed = sorted(it["volume"] for it in items)[len(items) // 2]
    emed = sorted(it["eng"] for it in items)[len(items) // 2]

    def px(v: float) -> float:
        return pad_l + (v / vmax) * plot_w

    def py(v: float) -> float:
        return pad_t + plot_h - (v / emax) * plot_h

    color = {"ngách vàng": "var(--good)", "đông nhưng hot": "var(--c-4)",
             "thử nghiệm": "var(--c-1)", "bão hoà": "var(--muted)"}
    parts = []
    for k in range(5):
        gy = pad_t + plot_h * k / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
                     f'y2="{gy:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" '
                     f'class="ax">{fmt(emax * (4 - k) / 4)}</text>')
    mx, my = px(vmed), py(emed)
    parts.append(f'<line x1="{mx:.1f}" y1="{pad_t}" x2="{mx:.1f}" '
                 f'y2="{pad_t + plot_h}" stroke="var(--accent)" '
                 f'stroke-dasharray="4 4" stroke-width="1" opacity=".6"/>')
    parts.append(f'<line x1="{pad_l}" y1="{my:.1f}" x2="{pad_l + plot_w}" '
                 f'y2="{my:.1f}" stroke="var(--accent)" stroke-dasharray="4 4" '
                 f'stroke-width="1" opacity=".6"/>')
    for i, it in enumerate(items):
        cx, cy = px(it["volume"]), py(it["eng"])
        c = color.get(it["verdict"], "var(--muted)")
        ly = min(max(cy + (-9 if i % 2 == 0 else 15), pad_t + 8), pad_t + plot_h - 4)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{c}" '
                     f'opacity=".85"><title>{esc(it["keyword"])}: {it["volume"]} bài · '
                     f'{fmt(it["eng"])} eng TB · {esc(it["verdict"])}</title></circle>')
        parts.append(f'<text x="{cx + 9:.1f}" y="{ly:.1f}" class="ax" '
                     f'fill="var(--ink-2)">{esc(str(it["keyword"])[:10])}</text>')
    parts.append(f'<text x="{pad_l + plot_w / 2:.0f}" y="{h - 4}" '
                 f'text-anchor="middle" class="ax">Số bài (độ bão hoà) →</text>')
    return (f'<div class="chart-line"><svg viewBox="0 0 {w} {h}" width="100%" '
            f'role="img" aria-label="ban do co hoi">{"".join(parts)}</svg></div>')


def timeline_posts(points: Sequence[dict[str, Any]], *, title: str = "",
                   baseline: float = 0.0, w: int = 560, h: int = 260) -> str:
    """
    Timeline từng bài của 1 kênh: X = ngày đăng, Y = engagement, size = save.

    baseline: đường trung vị của kênh -> thấy ngay bài nào bứt phá.
    """
    pts = [p for p in points
           if p.get("ts") is not None and not pd.isna(p.get("eng"))]
    if not pts:
        return _empty("Không đủ dữ liệu thời gian")
    pad_l, pad_r, pad_t, pad_b = 50, 16, 14, 30
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    xs = [p["ts"] for p in pts]
    x0, x1 = min(xs), max(xs)
    span = (x1 - x0) or 1
    ymax = (max(p["eng"] for p in pts) or 1) * 1.12

    def px(t: float) -> float:
        return pad_l + (t - x0) / span * plot_w

    def py(v: float) -> float:
        return pad_t + plot_h - (v / ymax) * plot_h

    parts = []
    for k in range(5):
        gy = pad_t + plot_h * k / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
                     f'y2="{gy:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" '
                     f'class="ax">{fmt(ymax * (4 - k) / 4)}</text>')
    if baseline > 0:
        by = py(baseline)
        parts.append(f'<line x1="{pad_l}" y1="{by:.1f}" x2="{pad_l + plot_w}" '
                     f'y2="{by:.1f}" stroke="var(--accent)" stroke-dasharray="5 4" '
                     f'stroke-width="1.5"/>')
        parts.append(f'<text x="{pad_l + plot_w:.0f}" y="{by - 5:.1f}" '
                     f'text-anchor="end" class="ax" fill="var(--accent)">'
                     f'trung vị kênh {fmt(baseline)}</text>')
    for p in pts:
        cx, cy = px(p["ts"]), py(p["eng"])
        breakout = baseline > 0 and p["eng"] >= 2 * baseline
        c = "var(--good)" if breakout else "var(--c-1)"
        r = 4.5 + 3.5 * (p.get("rel_save") or 0)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{c}" '
                     f'opacity=".8"><title>{esc(p.get("date", ""))} · '
                     f'{fmt(p["eng"])} eng · {esc(str(p.get("title", ""))[:70])}</title>'
                     f'</circle>')
    for i, lb in enumerate([p["date"] for p in (pts[0], pts[-1])]):
        x = pad_l if i == 0 else pad_l + plot_w
        anchor = "start" if i == 0 else "end"
        parts.append(f'<text x="{x:.0f}" y="{h - 8}" text-anchor="{anchor}" '
                     f'class="ax">{esc(lb)}</text>')
    ttl = f'<div class="chart-title">{esc(title)}</div>' if title else ""
    return (f'<div class="chart-line">{ttl}<svg viewBox="0 0 {w} {h}" width="100%" '
            f'role="img" aria-label="timeline bai dang">{"".join(parts)}</svg></div>')


def _empty(msg: str) -> str:
    return f'<div class="chart-empty">{esc(msg)}</div>'


# ---------------------------------------------------------------------------
# Lưới thẻ video (nút n8n + chọn nhiều)
# ---------------------------------------------------------------------------

def media_grid(df: pd.DataFrame, *, grid_id: str = "mg", max_cards: int = 48,
               filter_field: str = "format", sort_options: Sequence[tuple[str, str]] | None = None,
               badge_col: str | None = None) -> str:
    """
    Lưới thẻ video: cover + modal preview + 4 nút n8n + chọn nhiều gửi loạt.

    filter_field: cột dùng cho hàng chip lọc ("format" | "nickname" | "platform"
        | "source_keyword").
    badge_col: cột bool/str -> hiện nhãn nhỏ góc dưới ảnh (vd. "breakout").
    """
    if df is None or df.empty:
        return '<p class="muted">Không có dữ liệu.</p>'
    d = df.head(max_cards).reset_index(drop=True)
    sort_options = sort_options or [
        ("trend", "Điểm trend"), ("eng", "Engagement"), ("play", "Lượt xem"),
        ("like", "Like"), ("save", "Save"), ("share", "Share"),
        ("comment", "Bình luận"),
    ]

    # chip lọc theo filter_field
    vals = [v for v in d.get(filter_field, pd.Series(dtype=str)).fillna("").unique()
            if str(v).strip()]
    label_of = (lambda v: PLATFORM_LABELS.get(v, str(v))) if filter_field == "platform" \
        else str
    chips = [f'<button class="fchip active" type="button" data-val="__all__">'
             f'Tất cả ({len(d)})</button>']
    for v in sorted(vals, key=lambda x: -int((d[filter_field] == x).sum()))[:12]:
        n = int((d[filter_field] == v).sum())
        chips.append(f'<button class="fchip" type="button" data-val="{esc(v)}">'
                     f'{esc(label_of(v))} ({n})</button>')

    cards = []
    for i, r in d.iterrows():
        cards.append(_card(i, r, badge_col=badge_col, filter_field=filter_field))

    opts = "".join(f'<option value="{esc(k)}">Sắp theo: {esc(lb)}</option>'
                   if i == 0 else f'<option value="{esc(k)}">{esc(lb)}</option>'
                   for i, (k, lb) in enumerate(sort_options))
    bulk = "".join(f'<button class="n8n-btn bulk-act" data-action="{a}">{esc(lbl)}</button>'
                   for a, lbl, _ in N8N_ACTIONS)
    more = (f'<p class="muted tbl-more">Đang hiện {len(d)}/{len(df)} bài — '
            f'mở file Excel để xem đầy đủ.</p>' if len(df) > max_cards else "")

    return f"""
<div data-mgrid="{esc(grid_id)}" data-filter-field="{esc(filter_field)}">
  <div class="grid-toolbar">
    <input type="search" class="mg-search" placeholder="Tìm trong hook…">
    <select class="mg-sort">{opts}</select>
    <div class="chip-row">{"".join(chips)}</div>
  </div>
  <div class="bulk-bar">
    <label class="bulk-all"><input type="checkbox" class="mg-selall"> Chọn tất cả</label>
    <span class="bulk-count">0 đã chọn</span>
    <span class="bulk-spacer"></span>
    <span class="bulk-label">Gửi loạt sang n8n:</span>{bulk}
  </div>
  <div class="mcard-grid">{"".join(cards)}</div>
  {more}
</div>"""


def _card(i: int, r: pd.Series, *, badge_col: str | None,
          filter_field: str) -> str:
    """Một thẻ video."""
    title = str(r.get("title", "") or "")
    fmt_v = str(r.get("format", "") or "khác")
    plat = str(r.get("platform", "") or "")
    plat_lb = PLATFORM_LABELS.get(plat, plat)
    kw = str(r.get("source_keyword", "") or "")
    like = float(r.get("liked_count", 0) or 0)
    save = float(r.get("collected_count", 0) or 0)
    share = float(r.get("share_count", 0) or 0)
    comment = float(r.get("comment_count", 0) or 0)
    play = float(r.get("play_count", 0) or 0)
    eng = float(r.get("eng_total", 0) or 0)
    score = float(r.get("trend_score", 0) or 0)
    url = str(r.get("content_url", "") or "")
    dl = str(r.get("download_url", "") or "")
    cover = str(r.get("cover_url", "") or "")
    nickname = str(r.get("nickname", "") or "")
    music = str(r.get("music_url", "") or "")
    media_type = str(r.get("media_type", "video") or "video")
    created = r.get("created_at")
    created_s = "" if pd.isna(created) else str(created)[:10]
    item_id = str(r.get("item_id", "") or "")

    payload = {"platform": plat, "item_id": item_id, "title": title,
               "content_url": url, "download_url": dl, "cover_url": cover,
               "music_url": music, "media_type": media_type,
               "source_keyword": kw, "nickname": nickname,
               "trend_score": score}
    pj = esc(json.dumps(payload, ensure_ascii=False))

    thumb_inner = (
        f'<img src="{esc(cover)}" loading="lazy" alt="" '
        f'onerror="this.closest(\'.mcard-thumb\').classList.add(\'mcard-thumb--broken\')">'
        f'<span class="mcard-play">▶</span>' if cover
        else '<span class="mcard-play">🎬</span>')
    badge = ""
    if badge_col and r.get(badge_col):
        bt = r.get(badge_col)
        btxt = "🚀 Bứt phá" if bt is True else str(bt)
        badge = f'<span class="mcard-badge">{esc(btxt)}</span>'
    thumb = (f'<div class="mcard-thumb" data-preview=\'{pj}\'>{thumb_inner}'
             f'<span class="mcard-rank">#{i + 1}</span>'
             f'<span class="mcard-score" title="Điểm trend">{score:.0f}</span>'
             f'<label class="mcard-check"><input type="checkbox" class="mc-sel"></label>'
             f'{badge}</div>')

    stats = [f'<span title="Like">👍 {fmt(like)}</span>',
             f'<span title="Save/Favorite">💾 {fmt(save)}</span>',
             f'<span title="Share">↗ {fmt(share)}</span>',
             f'<span title="Bình luận">💬 {fmt(comment)}</span>']
    if play > 0:
        stats.insert(0, f'<span title="Lượt xem">▶ {fmt(play)}</span>')

    rates = [f'<span>Save/Like <b>{pct(r.get("save_rate"))}</b></span>',
             f'<span>Share/Like <b>{pct(r.get("share_rate"))}</b></span>']
    if r.get("out_ratio") is not None and not pd.isna(r.get("out_ratio")):
        rates.append(f'<span>So ngách <b>{float(r["out_ratio"]):.1f}×</b></span>')

    meta_bits = [b for b in [esc(nickname), esc(created_s)] if b]
    if music:
        meta_bits.append(f'<a href="{esc(music)}" target="_blank" rel="noopener">🎵 nhạc</a>')

    act_btns = "".join(f'<button class="n8n-btn" type="button" data-action="{a}" '
                       f'title="{esc(desc)}">{esc(lbl)}</button>'
                       for a, lbl, desc in N8N_ACTIONS)
    open_btn = (f'<a class="mcard-open" href="{esc(url)}" target="_blank" '
                f'rel="noopener">Mở ↗</a>' if url else "")
    kw_tag = f'<span class="tag tag-kw">{esc(kw)}</span>' if kw else ""

    return (
        f'<article class="mcard" data-payload=\'{pj}\' '
        f'data-format="{esc(fmt_v)}" data-platform="{esc(plat)}" '
        f'data-nickname="{esc(nickname)}" data-source_keyword="{esc(kw)}" '
        f'data-hook-lc="{esc(title.lower())}" data-trend="{score}" '
        f'data-eng="{eng}" data-like="{like}" data-save="{save}" '
        f'data-share="{share}" data-comment="{comment}" data-play="{play}">'
        f'{thumb}<div class="mcard-body">'
        f'<div class="mcard-tags"><span class="tag tag-plat">{esc(plat_lb)}</span>'
        f'<span class="tag">{esc(fmt_v)}</span>{kw_tag}</div>'
        f'<p class="mcard-hook">{esc(title)}</p>'
        f'<div class="mcard-stats">{"".join(stats)}</div>'
        f'<div class="mcard-rates">{"".join(rates)}</div>'
        f'<div class="mcard-meta">{" · ".join(meta_bits)}</div>'
        f'<div class="mcard-n8n">{act_btns}</div>'
        f'<div class="mcard-actions">'
        f'<button class="btn-copy" type="button" data-copy="{esc(title)}">📋 Hook</button>'
        f'{open_btn}</div></div></article>')
