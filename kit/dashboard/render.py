# -*- coding: utf-8 -*-
"""
Render dashboard HTML tự chứa, tương tác (không thư viện/CDN).

- Tab điều hướng: Tổng quan · Trend · Đối thủ · Hook Lab · Cơ hội.
- Biểu đồ SVG dùng lại kit.report.charts; scatter cơ hội vẽ tại chỗ.
- Lưới thẻ video: cover preview + modal xem nhanh + nút nối n8n
  (Tải · Voice→Text · Phân tích ND · Phân tích Hook), chọn nhiều + gửi loạt.
- Cấu hình webhook n8n lưu ở localStorage (đổi ngay trên UI, không cần build lại).
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any

import pandas as pd

from kit.report import charts

# Hành động nối n8n (nhãn hiển thị + mã action gửi kèm payload).
N8N_ACTIONS: list[tuple[str, str, str]] = [
    ("download", "📥 Tải", "Tải video/ảnh gốc về kho"),
    ("transcribe", "🎙️ Voice→Text", "Bóc lời thoại (speech-to-text)"),
    ("analyze", "🧠 Phân tích ND", "Tóm tắt & phân tích nội dung bằng AI"),
    ("hook", "🪝 Phân tích Hook", "Mổ xẻ hook/mở đầu 3 giây"),
]


def _esc(v: object) -> str:
    return html.escape(str(v), quote=True)


def _human(v: float) -> str:
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:.0f}"


def _pct(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# Các khối
# ---------------------------------------------------------------------------

def _tiles(kpis: list[dict[str, str]]) -> str:
    cells = []
    for k in kpis:
        cells.append(
            f'<div class="tile"><div class="t-label">{_esc(k["label"])}</div>'
            f'<div class="t-value">{_esc(k["value"])}</div>'
            f'<div class="t-note">{_esc(k["note"])}</div></div>')
    return f'<div class="tiles">{"".join(cells)}</div>'


def _panel(title: str, inner: str, *, sub: str = "") -> str:
    subhtml = f'<div class="panel-sub">{_esc(sub)}</div>' if sub else ""
    return (f'<section class="panel"><h2>{_esc(title)}</h2>{subhtml}{inner}</section>')


def _overview(sec: dict[str, Any]) -> str:
    tl = sec["timeline"]
    timeline = charts.line(tl["series"], tl["x_labels"],
                           title="Số bài đăng theo tuần (12 tuần gần nhất)") \
        if tl["series"] else '<div class="chart-empty">Chưa đủ dữ liệu thời gian</div>'
    donut_plat = charts.donut(sec["platform_mix"], title="Nền tảng", unit=" bài")
    hbar_kw = charts.hbar(sec["keyword_mix"], title="Từ khoá thu thập", color_idx=4)
    donut_fmt = charts.donut(sec["format_mix"], title="Format nội dung", unit=" bài")
    top = (
        f'<div class="chart-grid-3">'
        f'<div class="chart-donut">{donut_plat}</div>'
        f'<div class="chart-donut">{donut_fmt}</div>'
        f'<div class="chart-hbar">{hbar_kw}</div>'
        f'</div>')
    return (_tiles(sec["kpis"])
            + _panel("Cơ cấu dữ liệu", top)
            + _panel("Nhịp đăng theo thời gian", timeline,
                     sub="Đối chiếu cường độ xuất bản giữa các nền tảng."))


def _media_grid(df: pd.DataFrame, *, max_cards: int = 48) -> str:
    """Lưới thẻ video có nút nối n8n + chọn nhiều."""
    if df is None or df.empty:
        return '<p class="muted">Không có dữ liệu.</p>'
    from kit.dashboard.adapters import PLATFORM_LABELS

    d = df.head(max_cards).reset_index(drop=True)
    formats = sorted({str(f) for f in d.get("format", pd.Series(dtype=str)).dropna().unique()})
    chips = [f'<button class="fchip active" type="button" data-fmt="__all__">'
             f'Tất cả ({len(d)})</button>']
    for fmt in formats:
        n = int((d["format"] == fmt).sum())
        chips.append(f'<button class="fchip" type="button" data-fmt="{_esc(fmt)}">'
                     f'{_esc(fmt)} ({n})</button>')

    cards = []
    for i, r in d.iterrows():
        title = str(r.get("title", "") or "")
        fmt = str(r.get("format", "") or "khác")
        plat = str(r.get("platform", "") or "")
        plat_lb = PLATFORM_LABELS.get(plat, plat)
        kw = str(r.get("source_keyword", "") or "")
        like = float(r.get("liked_count", 0) or 0)
        save = float(r.get("collected_count", 0) or 0)
        share = float(r.get("share_count", 0) or 0)
        comment = float(r.get("comment_count", 0) or 0)
        play = float(r.get("play_count", 0) or 0)
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

        # payload JSON cho n8n (gắn vào data-attr, JS đọc lại khi bấm).
        payload = {
            "platform": plat, "item_id": item_id, "title": title,
            "content_url": url, "download_url": dl, "cover_url": cover,
            "music_url": music, "media_type": media_type,
            "source_keyword": kw, "nickname": nickname,
            "trend_score": score,
        }
        pj = _esc(json.dumps(payload, ensure_ascii=False))

        thumb_inner = (
            f'<img src="{_esc(cover)}" loading="lazy" alt="" '
            f'onerror="this.closest(\'.mcard-thumb\').classList.add(\'mcard-thumb--broken\')">'
            f'<span class="mcard-play">▶</span>' if cover else
            '<span class="mcard-play">🎬</span>')
        thumb = (
            f'<div class="mcard-thumb" data-preview=\'{pj}\'>'
            f'{thumb_inner}'
            f'<span class="mcard-rank">#{i + 1}</span>'
            f'<span class="mcard-score" title="Điểm trend">{score:.0f}</span>'
            f'<label class="mcard-check"><input type="checkbox" class="mc-sel"></label>'
            f'</div>')

        stats = [f'<span title="Like">👍 {charts._fmt(like)}</span>',
                 f'<span title="Save/Favorite">💾 {charts._fmt(save)}</span>',
                 f'<span title="Share">↗ {charts._fmt(share)}</span>',
                 f'<span title="Bình luận">💬 {charts._fmt(comment)}</span>']
        if play > 0:
            stats.insert(0, f'<span title="Lượt xem">▶ {charts._fmt(play)}</span>')

        meta_bits = [b for b in [_esc(nickname), _esc(created_s)] if b]
        if music:
            meta_bits.append(f'<a href="{_esc(music)}" target="_blank" rel="noopener">🎵 nhạc</a>')
        meta = " · ".join(meta_bits)

        act_btns = "".join(
            f'<button class="n8n-btn" type="button" data-action="{a}" '
            f'title="{_esc(desc)}">{_esc(lbl)}</button>'
            for a, lbl, desc in N8N_ACTIONS)

        open_btn = (f'<a class="mcard-open" href="{_esc(url)}" target="_blank" '
                    f'rel="noopener">Mở ↗</a>' if url else "")
        kw_tag = f'<span class="tag tag-kw">{_esc(kw)}</span>' if kw else ""

        cards.append(
            f'<article class="mcard" data-payload=\'{pj}\' '
            f'data-format="{_esc(fmt)}" data-platform="{_esc(plat)}" '
            f'data-kw="{_esc(kw)}" data-hook-lc="{_esc(title.lower())}" '
            f'data-trend="{score}" data-like="{like}" data-save="{save}" '
            f'data-share="{share}" data-comment="{comment}" data-play="{play}">'
            f'{thumb}'
            f'<div class="mcard-body">'
            f'<div class="mcard-tags"><span class="tag tag-plat">{_esc(plat_lb)}</span>'
            f'<span class="tag">{_esc(fmt)}</span>{kw_tag}</div>'
            f'<p class="mcard-hook">{_esc(title)}</p>'
            f'<div class="mcard-stats">{"".join(stats)}</div>'
            f'<div class="mcard-rates">'
            f'<span>Save/Like <b>{_pct(r.get("save_rate"))}</b></span>'
            f'<span>Share/Like <b>{_pct(r.get("share_rate"))}</b></span></div>'
            f'<div class="mcard-meta">{meta}</div>'
            f'<div class="mcard-n8n">{act_btns}</div>'
            f'<div class="mcard-actions">'
            f'<button class="btn-copy" type="button" data-copy="{_esc(title)}">📋 Hook</button>'
            f'{open_btn}</div>'
            f'</div></article>')

    more = (f'<p class="muted tbl-more">Đang hiện {len(d)}/{len(df)} bài top — '
            f'mở file Excel để xem đầy đủ.</p>' if len(df) > max_cards else "")

    return f"""
<div class="grid-toolbar">
  <input type="search" id="mg-search" placeholder="Tìm trong hook…" class="mg-search">
  <select id="mg-sort" class="mg-sort">
    <option value="trend">Sắp theo: Điểm trend</option>
    <option value="play">Lượt xem</option>
    <option value="like">Like</option>
    <option value="save">Save</option>
    <option value="share">Share</option>
    <option value="comment">Bình luận</option>
  </select>
  <div class="chip-row" id="mg-chips">{"".join(chips)}</div>
</div>
<div class="bulk-bar" id="bulk-bar">
  <label class="bulk-all"><input type="checkbox" id="mg-selall"> Chọn tất cả</label>
  <span class="bulk-count" id="bulk-count">0 đã chọn</span>
  <span class="bulk-spacer"></span>
  <span class="bulk-label">Gửi loạt sang n8n:</span>
  {"".join(f'<button class="n8n-btn bulk-act" data-action="{a}">{_esc(lbl)}</button>' for a, lbl, _ in N8N_ACTIONS)}
</div>
<div class="mcard-grid" id="mg-grid">{"".join(cards)}</div>
{more}
"""


def _creators(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '<p class="muted">Chưa đủ dữ liệu creator (cần ≥2 bài/creator).</p>'
    # Biểu đồ top creator theo tổng tương tác.
    bar_rows = [(str(r["nickname"]), float(r["eng_tong"]))
                for _, r in df.head(10).iterrows()]
    bar = charts.hbar(bar_rows, title="Top creator theo tổng tương tác", color_idx=6)

    head = ("<tr><th>Creator</th><th>Nền tảng</th><th class='num'>Video</th>"
            "<th class='num'>Eng TB</th><th class='num'>Eng tổng</th>"
            "<th class='num'>Điểm trend</th><th class='num'>Độ đều</th>"
            "<th class='num'>Velocity</th><th>Nhịp độ</th></tr>")
    rows = []
    for _, r in df.iterrows():
        vel = float(r.get("velocity", 1) or 1)
        vchip = ("chip-good" if vel >= 1.3 else
                 "chip-warn" if vel >= 1.0 else "chip-muted")
        vlabel = ("đang tăng" if vel >= 1.3 else
                  "ổn định" if vel >= 1.0 else "chững lại")
        deu = float(r.get("do_deu", 0) or 0)
        dbar = (f'<span class="minibar"><span style="width:{deu * 100:.0f}%"></span></span>')
        rows.append(
            f"<tr><td>{_esc(r['nickname'])}</td><td>{_esc(r['platform'])}</td>"
            f"<td class='num'>{int(r['so_video'])}</td>"
            f"<td class='num'>{_human(r['eng_tb'])}</td>"
            f"<td class='num'>{_human(r['eng_tong'])}</td>"
            f"<td class='num'>{float(r['trend_tb']):.0f}</td>"
            f"<td class='num'>{dbar}</td>"
            f"<td class='num'>{vel:.2f}×</td>"
            f"<td><span class='chip {vchip}'>{vlabel}</span></td></tr>")
    table = (f'<div class="tbl-wrap"><table><thead>{head}</thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    return _panel("Bảng xếp hạng creator / đối thủ", bar + table,
                  sub="Độ đều = mức nhất quán tương tác giữa các bài. "
                      "Velocity = đà tăng nửa sau so với nửa đầu kỳ.")


def _hooks(hooks: dict[str, Any]) -> str:
    tags = charts.hbar(hooks["top_tags"], title="Hashtag / thẻ xuất hiện nhiều",
                       color_idx=3) if hooks["top_tags"] else \
        '<div class="chart-empty">Không thấy hashtag</div>'
    pats = charts.hbar(hooks["patterns"], title="Công thức hook phổ biến",
                       color_idx=1, unit=" bài") if hooks["patterns"] else \
        '<div class="chart-empty">Chưa nhận diện được công thức</div>'
    charts_row = (f'<div class="chart-grid-2"><div class="chart-hbar">{pats}</div>'
                  f'<div class="chart-hbar">{tags}</div></div>')
    ex_cards = []
    for name, ex in hooks["examples"].items():
        ex_cards.append(
            f'<div class="hook-ex"><div class="hook-ex-name">{_esc(name)}</div>'
            f'<div class="hook-ex-title">“{_esc(ex["title"])}”</div>'
            f'<div class="hook-ex-meta">{_esc(ex["platform"])} · điểm '
            f'{ex["score"]:.0f}</div></div>')
    examples = (f'<div class="hook-ex-grid">{"".join(ex_cards)}</div>'
                if ex_cards else "")
    return _panel("Hook Lab — mổ xẻ tiêu đề & hashtag",
                  charts_row + examples,
                  sub="Nhặt hashtag đang chạy và công thức mở đầu để tái sử dụng "
                      "cho content mới. Nhấn 🪝 trên thẻ video để AI mổ hook sâu.")


def _opportunity(items: list[dict[str, Any]]) -> str:
    if not items:
        return _panel("Bản đồ cơ hội ngách", '<p class="muted">Không đủ dữ liệu.</p>')
    scatter = _scatter(items)
    verdict_cls = {"ngách vàng": "chip-good", "đông nhưng hot": "chip-warn",
                   "thử nghiệm": "chip-muted", "bão hoà": "chip-muted"}
    head = ("<tr><th>Từ khoá</th><th class='num'>Số bài</th>"
            "<th class='num'>Eng TB</th><th class='num'>Save TB</th>"
            "<th>Đánh giá</th></tr>")
    rows = []
    for it in items:
        cls = verdict_cls.get(it["verdict"], "chip-muted")
        rows.append(
            f"<tr><td>{_esc(it['keyword'])}</td>"
            f"<td class='num'>{it['volume']}</td>"
            f"<td class='num'>{_human(it['eng'])}</td>"
            f"<td class='num'>{_human(it['save'])}</td>"
            f"<td><span class='chip {cls}'>{_esc(it['verdict'])}</span></td></tr>")
    table = (f'<div class="tbl-wrap"><table><thead>{head}</thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    return _panel("Bản đồ cơ hội ngách", scatter + table,
                  sub="Trục ngang = độ bão hoà (số bài); trục dọc = sức hút "
                      "(tương tác TB). Góc trên-trái = ngách vàng: ít người làm, hút tương tác.")


def _scatter(items: list[dict[str, Any]], *, w: int = 560, h: int = 300) -> str:
    """Scatter cơ hội: X=volume, Y=eng_tb, màu theo verdict, nhãn keyword."""
    pad_l, pad_r, pad_t, pad_b = 46, 80, 16, 34
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    # +18% headroom để điểm ở max không dính mép, nhãn keyword còn chỗ hiển thị.
    vmax = (max((it["volume"] for it in items), default=1) or 1) * 1.18
    emax = (max((it["eng"] for it in items), default=1) or 1) * 1.18
    vmed = sorted(it["volume"] for it in items)[len(items) // 2]
    emed = sorted(it["eng"] for it in items)[len(items) // 2]

    def px(v: float) -> float:
        return pad_l + (v / vmax) * plot_w

    def py(v: float) -> float:
        return pad_t + plot_h - (v / emax) * plot_h

    color = {"ngách vàng": "var(--good)", "đông nhưng hot": "var(--c-4)",
             "thử nghiệm": "var(--c-1)", "bão hoà": "var(--muted)"}
    grid = []
    for k in range(5):
        gy = pad_t + plot_h * k / 4
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
                    f'y2="{gy:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        grid.append(f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" '
                    f'class="ax">{charts._fmt(emax * (4 - k) / 4)}</text>')
    # đường trung vị chia 4 góc phần tư
    mx, my = px(vmed), py(emed)
    grid.append(f'<line x1="{mx:.1f}" y1="{pad_t}" x2="{mx:.1f}" y2="{pad_t + plot_h}" '
                f'stroke="var(--accent)" stroke-dasharray="4 4" stroke-width="1" opacity=".6"/>')
    grid.append(f'<line x1="{pad_l}" y1="{my:.1f}" x2="{pad_l + plot_w}" y2="{my:.1f}" '
                f'stroke="var(--accent)" stroke-dasharray="4 4" stroke-width="1" opacity=".6"/>')
    dots = []
    for i, it in enumerate(items):
        cx, cy = px(it["volume"]), py(it["eng"])
        c = color.get(it["verdict"], "var(--muted)")
        # So le nhãn trên/dưới để 2 điểm gần nhau không đè chữ.
        dy = -9 if i % 2 == 0 else 15
        ly = min(max(cy + dy, pad_t + 8), pad_t + plot_h - 4)
        dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{c}" '
                    f'opacity=".85"><title>{_esc(it["keyword"])}: {it["volume"]} bài · '
                    f'{_human(it["eng"])} eng TB · {_esc(it["verdict"])}</title></circle>')
        dots.append(f'<text x="{cx + 9:.1f}" y="{ly:.1f}" class="ax" '
                    f'fill="var(--ink-2)">{_esc(it["keyword"][:10])}</text>')
    xlbl = (f'<text x="{pad_l + plot_w / 2:.0f}" y="{h - 4}" text-anchor="middle" '
            f'class="ax">Số bài (độ bão hoà) →</text>')
    return (f'<div class="chart-line"><svg viewBox="0 0 {w} {h}" width="100%" '
            f'role="img" aria-label="ban do co hoi">'
            f'{"".join(grid)}{"".join(dots)}{xlbl}</svg></div>')


# ---------------------------------------------------------------------------
# Trang
# ---------------------------------------------------------------------------

def render_dashboard(sec: dict[str, Any], *, meta: dict | None = None) -> str:
    """Ghép toàn bộ dashboard thành 1 chuỗi HTML tự chứa."""
    meta = meta or {}
    gen = meta.get("generated") or datetime.now().strftime("%d/%m/%Y %H:%M")
    sources = meta.get("sources", [])
    default_webhook = meta.get("n8n_webhook", "")

    tab_overview = _overview(sec)
    tab_trend = _media_grid(sec["trend"])
    tab_creators = _creators(sec["creators"])
    tab_hooks = _hooks(sec["hooks"])
    tab_opp = _opportunity(sec["opportunity"])

    src_html = " · ".join(_esc(s) for s in sources) if sources else "—"
    cfg = json.dumps({"webhook": default_webhook,
                      "actions": [a for a, _, _ in N8N_ACTIONS]},
                     ensure_ascii=False)

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard nghiên cứu nội dung — DigiAds</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<header class="rpt-head">
  <div>
    <div class="eyebrow">DigiAds Kit · Social Content Radar</div>
    <h1>Dashboard nghiên cứu trend &amp; đối thủ</h1>
    <div class="sub">Đa nền tảng · dữ liệu công khai · nghiên cứu nội bộ</div>
  </div>
  <div class="head-right">
    <div class="meta">Tạo lúc <b>{_esc(gen)}</b><br>{src_html}</div>
    <div class="head-tools">
      <button class="tool-btn" id="btn-n8n">⚙ Kết nối n8n</button>
      <button class="tool-btn" id="btn-theme" title="Sáng/Tối">◐</button>
    </div>
  </div>
</header>

<nav class="tabs" id="tabs">
  <button class="tab active" data-tab="overview">📊 Tổng quan</button>
  <button class="tab" data-tab="trend">🔥 Trend &amp; Video</button>
  <button class="tab" data-tab="creators">🎯 Đối thủ</button>
  <button class="tab" data-tab="hooks">🪝 Hook Lab</button>
  <button class="tab" data-tab="opp">🧭 Cơ hội</button>
</nav>

<div class="tab-pane active" data-pane="overview">{tab_overview}</div>
<div class="tab-pane" data-pane="trend">{tab_trend}</div>
<div class="tab-pane" data-pane="creators">{tab_creators}</div>
<div class="tab-pane" data-pane="hooks">{tab_hooks}</div>
<div class="tab-pane" data-pane="opp">{tab_opp}</div>

<footer>Nguồn: MediaCrawler + DigiAds Kit · dữ liệu công khai, nghiên cứu nội bộ ·
creator ẩn danh theo Nghị định 13/2023. Hành động n8n chỉ chạy khi bạn tự cấu hình webhook.</footer>
</div>

<!-- Modal preview -->
<div class="modal" id="preview-modal"><div class="modal-box">
  <button class="modal-close" id="modal-close">✕</button>
  <div class="modal-media" id="modal-media"></div>
  <div class="modal-info" id="modal-info"></div>
  <div class="modal-acts" id="modal-acts"></div>
</div></div>

<!-- Modal cấu hình n8n -->
<div class="modal" id="n8n-modal"><div class="modal-box modal-box--sm">
  <button class="modal-close" id="n8n-close">✕</button>
  <h3>Kết nối n8n</h3>
  <p class="muted">Dán URL webhook n8n của bạn. Mỗi nút hành động sẽ POST JSON
  (action + thông tin video) tới webhook này. URL lưu tại trình duyệt.</p>
  <input type="url" id="n8n-url" class="n8n-input"
    placeholder="https://n8n.cua-ban.vn/webhook/mc-action">
  <label class="n8n-check"><input type="checkbox" id="n8n-newtab">
    Mở tab xác nhận sau khi gửi</label>
  <div class="n8n-actions-cfg">
    <button class="tool-btn" id="n8n-save">Lưu</button>
    <button class="tool-btn" id="n8n-test">Gửi thử (ping)</button>
  </div>
  <p class="muted small">Workflow mẫu: <code>kit/n8n/WF_MC4_content_action.json</code></p>
</div></div>

<div class="toast" id="toast"></div>

<script>window.__MC_CFG__ = {cfg};</script>
<script>{_JS}</script>
</body></html>"""


# ===========================================================================
# CSS (mở rộng từ kit.report.html_report — thêm tabs/modal/n8n/scatter)
# ===========================================================================
_CSS = """
:root{color-scheme:light;
 --page:#eceee7;--surface:#f7f8f3;--surface-2:#eef0ea;--ink:#16211f;--ink-2:#4b5850;
 --muted:#7c8880;--rule:#d7dbd1;--grid:#d7dbd1;--accent:#eb6834;--accent-ink:#1a0f08;
 --good:#0ca30c;--warn:#c98500;
 --c-1:#2a78d6;--c-2:#008300;--c-3:#e87ba4;--c-4:#eda100;--c-5:#1baf7a;--c-6:#4a3aa7;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){
 --page:#0d1311;--surface:#121917;--surface-2:#17201d;--ink:#eef1ec;--ink-2:#c3ccc6;
 --muted:#85938c;--rule:#26332f;--grid:#26332f;--accent:#d95926;--accent-ink:#160d02;
 --good:#0ca30c;--warn:#c98500;
 --c-1:#3987e5;--c-2:#008300;--c-3:#d55181;--c-4:#c98500;--c-5:#199e70;--c-6:#9085e9;}}
:root[data-theme=dark]{
 --page:#0d1311;--surface:#121917;--surface-2:#17201d;--ink:#eef1ec;--ink-2:#c3ccc6;
 --muted:#85938c;--rule:#26332f;--grid:#26332f;--accent:#d95926;--accent-ink:#160d02;
 --c-1:#3987e5;--c-2:#008300;--c-3:#d55181;--c-4:#c98500;--c-5:#199e70;--c-6:#9085e9;}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--page);color:var(--ink);
 font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
 font-size:14px;line-height:1.45;padding:24px}
.wrap{max-width:1200px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
.rpt-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;
 border-bottom:2px solid var(--accent);padding-bottom:12px;flex-wrap:wrap}
.eyebrow{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--accent);font-weight:700}
.rpt-head h1{margin:4px 0 0;font-size:26px;font-weight:600;letter-spacing:-.01em;
 font-family:Charter,"Iowan Old Style","Palatino Linotype",Georgia,serif;text-wrap:balance}
.rpt-head .sub{margin-top:5px;color:var(--ink-2);font-size:13px}
.head-right{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.meta{text-align:right;color:var(--muted);font-size:12px}
.meta b{color:var(--ink-2)}
.head-tools{display:flex;gap:8px}
.tool-btn{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
 padding:6px 12px;font-size:12px;color:var(--ink-2);cursor:pointer;font-family:inherit}
.tool-btn:hover{border-color:var(--accent);color:var(--accent)}
.tabs{display:flex;gap:4px;flex-wrap:wrap;position:sticky;top:0;z-index:20;
 background:var(--page);padding:6px 0;border-bottom:1px solid var(--rule)}
.tab{background:none;border:none;border-radius:6px 6px 0 0;padding:9px 16px;font-size:13px;
 color:var(--muted);cursor:pointer;font-family:inherit;font-weight:600;border-bottom:2px solid transparent}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent);background:var(--surface)}
.tab-pane{display:none;flex-direction:column;gap:16px}
.tab-pane.active{display:flex}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:13px 15px}
.t-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.t-value{font-size:22px;font-weight:600;margin-top:3px;font-family:Charter,Georgia,serif;text-wrap:balance}
.t-note{font-size:11.5px;color:var(--ink-2);margin-top:2px}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:16px 18px}
.panel h2{margin:0 0 4px;font-size:15px;font-weight:700}
.panel-sub{font-size:12px;color:var(--muted);margin-bottom:14px}
.chart-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
.chart-grid-3{display:grid;grid-template-columns:1fr 1fr 1.1fr;gap:20px;align-items:start}
.chart-title{font-size:12px;color:var(--ink-2);font-weight:600;margin-bottom:8px}
.chart-empty{display:flex;align-items:center;justify-content:center;color:var(--muted);
 font-size:12px;background:var(--surface-2);border-radius:6px;min-height:120px}
.donut-wrap{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.donut-total{font-size:20px;font-weight:700;fill:var(--ink);font-family:Charter,Georgia,serif}
.donut-unit{font-size:10px;fill:var(--muted)}
.donut-legend{display:flex;flex-direction:column;gap:5px;min-width:110px}
.lg-row{display:flex;align-items:center;gap:7px;font-size:12px}
.lg-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.lg-label{color:var(--ink-2);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lg-val{font-weight:700;font-variant-numeric:tabular-nums}
.hb-row{display:grid;grid-template-columns:120px 1fr 62px;gap:8px;align-items:center;margin:7px 0}
.hb-label{font-size:12px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hb-track{height:13px;background:var(--surface-2);border-radius:3px;overflow:hidden}
.hb-fill{display:block;height:100%;border-radius:3px}
.hb-val{font-size:12px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink)}
.ax{fill:var(--muted);font-size:10px}
.endlbl{font-size:10.5px;font-weight:700}
.tbl-wrap{overflow-x:auto;margin-top:14px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);
 font-weight:600;padding:0 10px 6px 0;border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:7px 10px 7px 0;border-bottom:1px solid var(--rule);color:var(--ink-2);vertical-align:middle}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
a{color:var(--accent);text-decoration:none;font-weight:600}
a:hover{text-decoration:underline}
.muted{color:var(--muted)}
.small{font-size:11px}
.tbl-more{font-size:11.5px;margin:10px 0 0}
.chip{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700}
.chip-good{background:var(--good);color:#fff}
.chip-warn{background:var(--warn);color:#160d02}
.chip-muted{background:var(--surface-2);color:var(--muted);border:1px solid var(--rule)}
.minibar{display:inline-block;width:56px;height:8px;background:var(--surface-2);border-radius:3px;
 overflow:hidden;vertical-align:middle}
.minibar>span{display:block;height:100%;background:var(--c-5)}
footer{border-top:1px solid var(--rule);padding-top:11px;font-size:11px;color:var(--muted)}
/* toolbar + grid */
.grid-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.mg-search{flex:1;min-width:180px;background:var(--surface);border:1px solid var(--rule);
 border-radius:6px;padding:8px 11px;font-size:12.5px;color:var(--ink);font-family:inherit}
.mg-search::placeholder{color:var(--muted)}
.mg-sort{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
 padding:8px 11px;font-size:12.5px;color:var(--ink);font-family:inherit}
.chip-row{display:flex;gap:6px;flex-wrap:wrap}
.fchip{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:5px 12px;
 font-size:11.5px;color:var(--ink-2);cursor:pointer;font-family:inherit;white-space:nowrap}
.fchip.active{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:700}
.bulk-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--surface);
 border:1px solid var(--rule);border-radius:8px;padding:8px 12px;margin-bottom:12px;font-size:12px}
.bulk-all{display:flex;gap:6px;align-items:center;color:var(--ink-2);cursor:pointer}
.bulk-count{color:var(--accent);font-weight:700}
.bulk-spacer{flex:1}
.bulk-label{color:var(--muted)}
.mcard-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.mcard{background:var(--surface);border:1px solid var(--rule);border-radius:10px;overflow:hidden;
 display:flex;flex-direction:column}
.mcard.sel{outline:2px solid var(--accent)}
.mcard-thumb{position:relative;display:block;aspect-ratio:3/4;cursor:pointer;
 background:linear-gradient(135deg,var(--surface-2),var(--rule));overflow:hidden}
.mcard-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.mcard-thumb--broken img{display:none}
.mcard-thumb--broken::before{content:"🎬";position:absolute;inset:0;display:flex;align-items:center;
 justify-content:center;font-size:34px;opacity:.35}
.mcard-play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
 font-size:30px;color:#fff;background:rgba(0,0,0,0);opacity:0;transition:opacity .15s}
.mcard-thumb:hover .mcard-play{opacity:1;background:rgba(0,0,0,.32)}
.mcard-rank{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.65);color:#fff;font-size:10.5px;
 font-weight:700;padding:2px 7px;border-radius:10px}
.mcard-score{position:absolute;top:6px;right:34px;background:var(--accent);color:var(--accent-ink);
 font-size:11px;font-weight:800;padding:2px 8px;border-radius:10px;font-variant-numeric:tabular-nums}
.mcard-check{position:absolute;top:5px;right:6px;background:rgba(0,0,0,.5);border-radius:6px;
 padding:3px 4px;display:flex;cursor:pointer}
.mcard-check input{cursor:pointer;margin:0}
.mcard-body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:7px;flex:1}
.mcard-tags{display:flex;gap:5px;flex-wrap:wrap}
.mcard-tags .tag{font-size:10px;border:1px solid var(--rule);border-radius:3px;padding:1px 6px;
 color:var(--ink-2);text-transform:uppercase;letter-spacing:.02em}
.mcard-tags .tag-kw{color:var(--accent);border-color:var(--accent)}
.mcard-tags .tag-plat{color:var(--c-1);border-color:var(--c-1);font-weight:700}
.mcard-hook{font-size:12.5px;color:var(--ink);margin:0;line-height:1.4;
 display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.mcard-stats{display:flex;gap:9px;flex-wrap:wrap;font-size:11.5px;color:var(--ink-2);
 font-variant-numeric:tabular-nums}
.mcard-rates{display:flex;gap:12px;font-size:11px;color:var(--muted)}
.mcard-rates b{color:var(--ink-2);font-variant-numeric:tabular-nums}
.mcard-meta{font-size:11px;color:var(--muted);display:flex;gap:4px;flex-wrap:wrap}
.mcard-meta a{color:var(--muted);font-weight:400}
.mcard-n8n{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:4px}
.n8n-btn{background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;padding:5px 6px;
 font-size:10.5px;color:var(--ink-2);cursor:pointer;font-family:inherit;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.n8n-btn:hover{border-color:var(--accent);color:var(--accent);background:var(--surface)}
.mcard-actions{display:flex;gap:8px;margin-top:auto;padding-top:4px;align-items:center}
.btn-copy{background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;padding:5px 9px;
 font-size:11px;color:var(--ink-2);cursor:pointer;font-family:inherit}
.btn-copy:hover{border-color:var(--accent);color:var(--accent)}
.mcard-open{margin-left:auto;background:var(--accent);color:var(--accent-ink);border-radius:6px;
 padding:5px 11px;font-size:11px;font-weight:700;text-decoration:none}
.bulk-act{padding:6px 10px;font-size:11.5px}
/* hook lab */
.hook-ex-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:16px}
.hook-ex{background:var(--surface-2);border:1px solid var(--rule);border-radius:8px;padding:11px 13px}
.hook-ex-name{font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.03em}
.hook-ex-title{font-size:12.5px;color:var(--ink);margin:6px 0;line-height:1.4}
.hook-ex-meta{font-size:11px;color:var(--muted)}
/* modal */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;
 justify-content:center;z-index:100;padding:20px}
.modal.open{display:flex}
.modal-box{background:var(--surface);border-radius:12px;max-width:760px;width:100%;max-height:90vh;
 overflow:auto;padding:20px;position:relative}
.modal-box--sm{max-width:440px}
.modal-close{position:absolute;top:12px;right:12px;background:var(--surface-2);border:1px solid var(--rule);
 border-radius:50%;width:30px;height:30px;cursor:pointer;color:var(--ink-2);font-size:14px}
.modal-media{width:100%;border-radius:8px;overflow:hidden;background:#000;margin-bottom:14px}
.modal-media img,.modal-media video{width:100%;display:block;max-height:60vh;object-fit:contain;background:#000}
.modal-info h3{margin:0 0 6px;font-size:16px}
.modal-info p{margin:4px 0;color:var(--ink-2);font-size:13px}
.modal-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.n8n-input{width:100%;background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;
 padding:9px 11px;font-size:13px;color:var(--ink);font-family:inherit;margin:10px 0}
.n8n-check{display:flex;gap:7px;align-items:center;font-size:12px;color:var(--ink-2);margin-bottom:12px}
.n8n-actions-cfg{display:flex;gap:8px;margin-bottom:10px}
code{background:var(--surface-2);padding:1px 5px;border-radius:4px;font-size:11px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);
 background:var(--ink);color:var(--page);padding:11px 20px;border-radius:8px;font-size:13px;
 opacity:0;transition:all .25s;z-index:200;max-width:80vw;text-align:center}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.err{background:#c0392b;color:#fff}
@media(max-width:820px){.tiles{grid-template-columns:repeat(2,1fr)}
 .chart-grid-2,.chart-grid-3{grid-template-columns:1fr}
 .mcard-grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}}
"""

# ===========================================================================
# JS (vanilla, tự chứa)
# ===========================================================================
_JS = r"""
(function(){
  var CFG = window.__MC_CFG__ || {webhook:"", actions:[]};
  var LS_URL = "mc_n8n_webhook", LS_TAB = "mc_n8n_newtab", LS_THEME = "mc_theme";

  function $(id){return document.getElementById(id);}
  function webhook(){return localStorage.getItem(LS_URL) || CFG.webhook || "";}
  function newtab(){return localStorage.getItem(LS_TAB) === "1";}

  var toastT;
  function toast(msg, err){
    var t = $("toast"); t.textContent = msg;
    t.className = "toast show" + (err ? " err" : "");
    clearTimeout(toastT);
    toastT = setTimeout(function(){t.className = "toast";}, 2600);
  }

  // ---- theme ----
  var savedTheme = localStorage.getItem(LS_THEME);
  if(savedTheme){document.documentElement.setAttribute("data-theme", savedTheme);}
  $("btn-theme").addEventListener("click", function(){
    var cur = document.documentElement.getAttribute("data-theme");
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(LS_THEME, next);
  });

  // ---- tabs ----
  document.getElementById("tabs").addEventListener("click", function(e){
    var tab = e.target.closest(".tab"); if(!tab) return;
    var name = tab.getAttribute("data-tab");
    document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("active");});
    document.querySelectorAll(".tab-pane").forEach(function(p){p.classList.remove("active");});
    tab.classList.add("active");
    document.querySelector('.tab-pane[data-pane="'+name+'"]').classList.add("active");
    window.scrollTo({top:0, behavior:"smooth"});
  });

  // ---- n8n config modal ----
  function openModal(id){$(id).classList.add("open");}
  function closeModal(id){$(id).classList.remove("open");}
  $("btn-n8n").addEventListener("click", function(){
    $("n8n-url").value = webhook();
    $("n8n-newtab").checked = newtab();
    openModal("n8n-modal");
  });
  $("n8n-close").addEventListener("click", function(){closeModal("n8n-modal");});
  $("n8n-save").addEventListener("click", function(){
    localStorage.setItem(LS_URL, $("n8n-url").value.trim());
    localStorage.setItem(LS_TAB, $("n8n-newtab").checked ? "1" : "0");
    closeModal("n8n-modal");
    toast("Đã lưu webhook n8n");
  });
  $("n8n-test").addEventListener("click", function(){
    localStorage.setItem(LS_URL, $("n8n-url").value.trim());
    send("ping", {note:"ping từ dashboard DigiAds"});
  });

  // ---- gửi payload sang n8n ----
  function send(action, payload){
    var url = webhook();
    if(!url){toast("Chưa cấu hình webhook n8n — bấm ⚙ Kết nối n8n", true);
      openModal("n8n-modal"); return;}
    var body = {action:action, payload:payload, source:"digiads-dashboard",
                ts:new Date().toISOString()};
    toast("Đang gửi: " + action + "…");
    fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
      mode:"cors", body:JSON.stringify(body)})
      .then(function(r){
        if(!r.ok) throw new Error("HTTP " + r.status);
        toast("✓ Đã gửi '" + action + "' sang n8n");
        if(newtab()){window.open(url.replace(/\/webhook\//, "/webhook-test/"), "_blank");}
      })
      .catch(function(err){
        toast("Lỗi gửi n8n: " + err.message + " (kiểm tra URL/CORS)", true);
      });
  }

  // ---- media grid: search / sort / filter / select / n8n ----
  var grid = $("mg-grid");
  if(grid){
    var search = $("mg-search"), sortSel = $("mg-sort"), chipRow = $("mg-chips");
    var activeFmt = "__all__";
    function apply(){
      var q = (search.value||"").toLowerCase();
      Array.prototype.forEach.call(grid.children, function(card){
        var fmt = card.getAttribute("data-format");
        var hook = card.getAttribute("data-hook-lc")||"";
        var show = (activeFmt==="__all__"||fmt===activeFmt) && (!q||hook.indexOf(q)!==-1);
        card.style.display = show ? "" : "none";
      });
    }
    function sortBy(key){
      var cards = Array.prototype.slice.call(grid.children);
      cards.sort(function(a,b){
        return parseFloat(b.getAttribute("data-"+key)||0) - parseFloat(a.getAttribute("data-"+key)||0);
      });
      cards.forEach(function(c){grid.appendChild(c);});
    }
    chipRow.addEventListener("click", function(e){
      var chip = e.target.closest(".fchip"); if(!chip) return;
      Array.prototype.forEach.call(chipRow.children, function(c){c.classList.remove("active");});
      chip.classList.add("active");
      activeFmt = chip.getAttribute("data-fmt"); apply();
    });
    search.addEventListener("input", apply);
    sortSel.addEventListener("change", function(){sortBy(sortSel.value);});

    function updateCount(){
      var n = grid.querySelectorAll(".mc-sel:checked").length;
      $("bulk-count").textContent = n + " đã chọn";
    }
    $("mg-selall").addEventListener("change", function(e){
      grid.querySelectorAll(".mcard").forEach(function(card){
        if(card.style.display==="none") return;
        var cb = card.querySelector(".mc-sel");
        cb.checked = e.target.checked;
        card.classList.toggle("sel", e.target.checked);
      });
      updateCount();
    });

    grid.addEventListener("change", function(e){
      var cb = e.target.closest(".mc-sel"); if(!cb) return;
      cb.closest(".mcard").classList.toggle("sel", cb.checked);
      updateCount();
    });

    grid.addEventListener("click", function(e){
      var copyBtn = e.target.closest(".btn-copy");
      if(copyBtn){
        var text = copyBtn.getAttribute("data-copy")||"";
        if(navigator.clipboard){navigator.clipboard.writeText(text).then(function(){
          var old = copyBtn.textContent; copyBtn.textContent = "✓";
          setTimeout(function(){copyBtn.textContent = old;}, 1400);
        });}
        return;
      }
      var n8nBtn = e.target.closest(".n8n-btn");
      if(n8nBtn){
        var card = n8nBtn.closest(".mcard");
        var payload = JSON.parse(card.getAttribute("data-payload"));
        send(n8nBtn.getAttribute("data-action"), payload);
        return;
      }
      var thumb = e.target.closest(".mcard-thumb");
      if(thumb){openPreview(JSON.parse(thumb.getAttribute("data-preview"))); return;}
    });

    // bulk actions
    document.querySelectorAll(".bulk-act").forEach(function(btn){
      btn.addEventListener("click", function(){
        var sel = grid.querySelectorAll(".mc-sel:checked");
        if(!sel.length){toast("Chưa chọn video nào", true); return;}
        var items = [];
        sel.forEach(function(cb){
          items.push(JSON.parse(cb.closest(".mcard").getAttribute("data-payload")));
        });
        send(btn.getAttribute("data-action"), {batch:true, count:items.length, items:items});
      });
    });
  }

  // ---- preview modal ----
  function openPreview(p){
    var media = $("modal-media"), info = $("modal-info"), acts = $("modal-acts");
    var isVideo = p.media_type === "video";
    // Cover luôn hiển thị; video nhúng chỉ thử với nguồn có thể phát (Douyin/XHS).
    var mediaHtml = "";
    if(isVideo && p.download_url && /douyin|aweme|\.mp4|xhscdn|redcdn/.test(p.download_url)){
      mediaHtml = '<video src="'+p.download_url+'" poster="'+(p.cover_url||"")+
        '" controls playsinline preload="none"></video>';
    } else if(p.cover_url){
      mediaHtml = '<img src="'+p.cover_url+'" alt="">';
    } else {
      mediaHtml = '<div style="padding:60px;text-align:center;color:#888">Không có preview</div>';
    }
    media.innerHTML = mediaHtml;
    info.innerHTML = '<h3>'+escapeHtml(p.title||"(không tiêu đề)")+'</h3>'+
      '<p>'+escapeHtml(p.nickname||"")+' · '+escapeHtml(p.source_keyword||"")+
      ' · điểm trend '+Math.round(p.trend_score||0)+'</p>'+
      (p.content_url ? '<p><a href="'+p.content_url+'" target="_blank" rel="noopener">Mở bài gốc ↗</a></p>' : "");
    var btns = CFG.actions.map(function(a){
      var lbl = {download:"📥 Tải", transcribe:"🎙️ Voice→Text",
                 analyze:"🧠 Phân tích ND", hook:"🪝 Phân tích Hook"}[a] || a;
      return '<button class="n8n-btn" data-pa="'+a+'">'+lbl+'</button>';
    }).join("");
    acts.innerHTML = btns;
    acts.querySelectorAll(".n8n-btn").forEach(function(b){
      b.addEventListener("click", function(){send(b.getAttribute("data-pa"), p);});
    });
    openModal("preview-modal");
  }
  $("modal-close").addEventListener("click", function(){
    closeModal("preview-modal"); $("modal-media").innerHTML = "";
  });
  document.querySelectorAll(".modal").forEach(function(m){
    m.addEventListener("click", function(e){if(e.target===m){m.classList.remove("open");
      if(m.id==="preview-modal") $("modal-media").innerHTML="";}});
  });
  document.addEventListener("keydown", function(e){
    if(e.key==="Escape"){document.querySelectorAll(".modal.open").forEach(function(m){
      m.classList.remove("open");}); $("modal-media").innerHTML="";}
  });

  function escapeHtml(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}
})();
"""
