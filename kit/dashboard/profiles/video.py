# -*- coding: utf-8 -*-
"""
Dashboard **DETAIL / VIDEO MODE** — "Video Teardown + Voice of Customer".

Câu hỏi nó trả lời:
  1. Từng video mạnh/yếu ở đâu so với mặt bằng? (giải phẫu like/save/share/comment)
  2. Khán giả nói gì? Hỏi gì? (mỏ ý tưởng content từ bình luận)
  3. Nỗi đau / mong muốn nào lặp lại? → angle cho content mới.
  4. Gửi video sang n8n để bóc lời thoại và phân tích sâu.

Sheet `Comments` chỉ có khi crawl bật `--get_comment`. Không có comment thì
dashboard vẫn chạy, chỉ hiện hướng dẫn bật thêm.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from kit.dashboard import analysis as A
from kit.dashboard import components as C
from kit.dashboard.adapters import PLATFORM_LABELS
from kit.dashboard.theme import esc, page
from kit.report import charts

TABS = [("teardown", "🔬 Mổ xẻ video"), ("voc", "🗣 Voice of Customer"),
        ("ideas", "💡 Ý tưởng từ bình luận"), ("grid", "🎬 Thư viện")]

# Số video dựng khối mổ xẻ chi tiết.
MAX_TEARDOWN = 12


def build(bundle: dict[str, Any], *, meta: dict | None = None) -> str:
    """Dựng dashboard Video Teardown."""
    # So trong từng nền tảng cho công bằng (thang tương tác lệch xa nhau).
    df = A.add_outlier_ratio(bundle["content"], by="platform")
    cm = bundle.get("comments")
    bm = A.benchmark(df)
    voc = A.comment_mining(cm) if cm is not None else A.comment_mining(pd.DataFrame())

    panes = {
        "teardown": _pane_teardown(df, bm, cm),
        "voc": _pane_voc(voc, cm),
        "ideas": _pane_ideas(voc),
        "grid": _pane_grid(df),
    }
    return page(title="Video Teardown — Mổ xẻ video & tiếng nói khán giả",
                eyebrow="DigiAds Kit · DETAIL MODE",
                subtitle=f"{len(df)} video · "
                         f"{voc['n']} bình luận đã phân tích",
                tabs=TABS, panes=panes, meta=meta)


def _cmt(c: dict, *, show_replies: bool = True) -> str:
    """Một ô bình luận; nếu câu đó lặp lại nhiều lần thì nêu rõ (tín hiệu nhu cầu)."""
    bits = [f'<span>👍 {C.human(c["like"])}</span>']
    if show_replies:
        bits.append(f'<span>💬 {C.human(c["replies"])} trả lời</span>')
    rep = int(c.get("repeat", 1) or 1)
    if rep > 1:
        bits.append(f'<span class="chip chip-warn">lặp {rep}×</span>')
    return (f'<div class="cmt"><p class="cmt-text">{esc(c["text"])}</p>'
            f'<div class="cmt-meta">{"".join(bits)}</div></div>')


# ---------------------------------------------------------------------------

def _pane_teardown(df: pd.DataFrame, bm: dict, cm: pd.DataFrame | None) -> str:
    n_cmt = 0 if cm is None or cm.empty else len(cm)
    cmt_per = n_cmt / len(df) if len(df) else 0
    kpis = [
        {"label": "Video phân tích", "value": f"{len(df)}",
         "note": f'{df["platform"].nunique()} nền tảng'},
        {"label": "Bình luận đã cào", "value": f"{n_cmt:,}",
         "note": f"TB {cmt_per:.0f}/video"},
        {"label": "Eng trung vị", "value": C.human(df["eng_total"].median()),
         "note": "mốc so sánh"},
        {"label": "Video vượt trội", "value": f'{int(df["breakout"].sum())}',
         "note": "≥2× trung vị"},
    ]

    blocks = []
    top = df.sort_values("eng_total", ascending=False).head(MAX_TEARDOWN)
    for i, (_, r) in enumerate(top.iterrows(), start=1):
        blocks.append(_teardown_card(i, r, bm, cm))

    if not blocks:
        return C.tiles(kpis) + C.panel(
            "Mổ xẻ video", '<p class="muted">Không có video nào.</p>')

    note = C.callout(
        "Mỗi video được so với <b>mốc trung vị (P50)</b> của tệp dữ liệu: thanh "
        "càng dài càng mạnh, vạch dọc là mốc tham chiếu. Bấm nút n8n để tải, "
        "bóc lời thoại (voice→text) rồi cho AI phân tích nội dung/hook.")
    return C.tiles(kpis) + C.panel("Mổ xẻ từng video", note + "".join(blocks),
                                   sub="Xếp theo tương tác giảm dần.")


def _teardown_card(i: int, r: pd.Series, bm: dict,
                   cm: pd.DataFrame | None) -> str:
    """Một khối mổ xẻ 1 video: giải phẫu tương tác + bình luận top của nó."""
    anatomy = A.engagement_anatomy(r, bm)
    bullets = C.bullets(anatomy) if anatomy else ""
    title = str(r.get("title", "") or "(không tiêu đề)")
    url = str(r.get("content_url", "") or "")
    plat = PLATFORM_LABELS.get(r.get("platform"), str(r.get("platform", "")))
    created = r.get("created_at")
    date_s = "" if pd.isna(created) else f"{created:%d/%m/%Y}"
    ratio = r.get("out_ratio")
    ratio_chip = ""
    if ratio is not None and not pd.isna(ratio):
        cls = "chip-good" if float(ratio) >= 2 else "chip-muted"
        ratio_chip = (f'<span class="chip {cls}">{float(ratio):.1f}× trung vị</span>')

    # Bình luận nổi bật của chính video này
    cmt_html = ""
    if cm is not None and not cm.empty and "item_id" in cm.columns:
        sub = cm[cm["item_id"].astype(str) == str(r.get("item_id", ""))]
        if not sub.empty:
            mined = A.comment_mining(sub, top=4)
            items = "".join(_cmt(c) for c in mined["top"])
            cmt_html = (f'<h3>Bình luận nổi bật ({mined["n"]})</h3>{items}')

    thumb = ""
    cover = str(r.get("cover_url", "") or "")
    if cover:
        payload_ok = True  # ảnh có thể hỏng -> ẩn nhẹ nhàng
        thumb = (f'<img src="{esc(cover)}" alt="" loading="lazy" '
                 f'style="width:120px;border-radius:6px;object-fit:cover" '
                 f'onerror="this.style.display=\'none\'">' if payload_ok else "")

    link = (f'<a href="{esc(url)}" target="_blank" rel="noopener">Mở bài gốc ↗</a>'
            if url else "")
    stats = (f'👍 {C.human(r.get("liked_count"))} · 💾 {C.human(r.get("collected_count"))}'
             f' · ↗ {C.human(r.get("share_count"))} · 💬 {C.human(r.get("comment_count"))}')
    if float(r.get("play_count", 0) or 0) > 0:
        stats = f'▶ {C.human(r.get("play_count"))} · ' + stats

    return (f'<div class="panel" style="margin-top:14px;background:var(--surface-2)">'
            f'<div style="display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap">'
            f'{thumb}'
            f'<div style="flex:1;min-width:220px">'
            f'<div class="muted small">#{i} · {esc(plat)} · {esc(date_s)} '
            f'{ratio_chip}</div>'
            f'<p style="margin:5px 0;font-size:13px;color:var(--ink)">{esc(title)}</p>'
            f'<div class="muted small">{stats}</div>'
            f'<div style="margin-top:4px">{link}</div>'
            f'</div></div>'
            f'<div style="margin-top:12px">{bullets}</div>'
            f'{cmt_html}</div>')


def _pane_voc(voc: dict, cm: pd.DataFrame | None) -> str:
    if not voc["n"]:
        return C.panel(
            "Voice of Customer",
            C.callout(
                "Tệp dữ liệu chưa có bình luận. Cào lại với cờ bật comment để mở "
                "phần này:<br><code>python main.py --platform dy --type detail "
                "--get_comment yes --get_sub_comment yes</code><br>"
                "Hoặc qua REST: <code>POST /api/crawler/start</code> với "
                "<code>\"enable_comments\": true</code>.", warn=True),
            sub="Đây là phần giá trị nhất của mode detail — tiếng nói thật của "
                "khán giả.")

    kpis = [
        {"label": "Bình luận", "value": f'{voc["n"]:,}',
         "note": f'{voc.get("n_unique", 0):,} nội dung khác biệt'},
        {"label": "Có trả lời", "value": C.pct(voc["reply_rate"], 0),
         "note": "bình luận có reply"},
        {"label": "Câu hỏi", "value": f'{len(voc["questions"])}',
         "note": "→ ý tưởng content"},
        {"label": "Tín hiệu nỗi đau", "value": f'{len(voc["pain"])}',
         "note": "→ angle bán hàng"},
    ]
    kw = charts.hbar(voc["keywords"], title="Từ khoá khán giả nhắc nhiều",
                     color_idx=3) if voc["keywords"] else ""
    top_list = "".join(_cmt(c) for c in voc["top"])

    return (C.tiles(kpis)
            + C.panel("Khán giả nhắc gì nhiều nhất", kw,
                      sub="Từ khoá lặp lại trong bình luận — dùng làm từ khoá "
                          "SEO/hashtag và chủ đề cho content mới.")
            + C.panel("Bình luận nhiều tương tác nhất",
                      f'<div class="cmt-list">{top_list}</div>',
                      sub="Bình luận top thường phản ánh đúng điều khán giả quan "
                          "tâm nhất — nguyên liệu tốt cho hook."))


def _pane_ideas(voc: dict) -> str:
    if not voc["n"]:
        return C.panel("Ý tưởng từ bình luận",
                       '<p class="muted">Cần dữ liệu bình luận — xem tab Voice of '
                       'Customer để biết cách bật.</p>')
    def block(items: list[dict], empty: str) -> str:
        if not items:
            return f'<p class="muted">{esc(empty)}</p>'
        return "".join(_cmt(c, show_replies=False) for c in items)

    ins = [
        ("Cách dùng", "Mỗi <b>câu hỏi</b> của khán giả là 1 video trả lời — dạng "
         "content dễ lên nhất vì cầu đã có sẵn."),
        ("Angle", "Câu chứa <b>nỗi đau</b> dùng làm hook mở đầu; câu chứa "
         "<b>mong muốn</b> dùng làm lời hứa (promise) ở giữa video."),
    ]
    return (C.panel("Việc nên làm ngay", C.insights(ins))
            + C.panel(f'Khán giả đang hỏi gì ({len(voc["questions"])})',
                      f'<div class="cmt-list">{block(voc["questions"], "Không thấy câu hỏi.")}</div>',
                      sub="Mỗi câu hỏi = 1 chủ đề video có cầu sẵn.")
            + C.panel("Tín hiệu nỗi đau",
                      block(voc["pain"], "Không thấy tín hiệu rõ."),
                      sub="Nguyên liệu cho hook 'cảnh báo / tránh sai lầm'.")
            + C.panel("Tín hiệu mong muốn",
                      block(voc["desire"], "Không thấy tín hiệu rõ."),
                      sub="Nguyên liệu cho lời hứa & CTA."))


def _pane_grid(df: pd.DataFrame) -> str:
    return C.panel("Thư viện video",
                   C.media_grid(df.sort_values("eng_total", ascending=False),
                                grid_id="video-grid", filter_field="platform",
                                badge_col="breakout", max_cards=60),
                   sub="Bấm ảnh để xem nhanh; dùng nút n8n để tải/bóc lời/phân tích.")
