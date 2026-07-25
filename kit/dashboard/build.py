# -*- coding: utf-8 -*-
"""
Điều phối: file raw → dashboard chuyên sâu theo mode cào.

    build_dashboard(paths, profile="auto")   # 1 dashboard
    build_all(paths)                          # nhiều dashboard + trang index
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from kit.dashboard import profiles as P
from kit.dashboard.metrics import load_bundle
from kit.dashboard.theme import esc

REPORT_DIR = Path("reports")


def _meta(paths: list[str | Path], n8n_webhook: str | None) -> dict:
    """Metadata hiển thị ở header + webhook n8n mặc định."""
    webhook = (n8n_webhook if n8n_webhook is not None
               else os.getenv("N8N_ACTION_WEBHOOK_URL")
               or os.getenv("NOTIFY_WEBHOOK_URL", ""))
    return {"generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "sources": [Path(p).name for p in paths],
            "n8n_webhook": webhook}


def pick_profile(modes: Counter[str]) -> str:
    """
    Chọn loại dashboard từ các mode cào có trong dữ liệu.

    Một mode duy nhất -> dashboard chuyên của mode đó. Trộn nhiều mode ->
    `overview` (bức tranh chéo).
    """
    if not modes:
        return "overview"
    kinds = [k for k, n in modes.items() if n]
    if len(kinds) == 1:
        return P.MODE_TO_PROFILE.get(kinds[0], "overview")
    return "overview"


def build_dashboard(paths: list[str | Path], *, profile: str = "auto",
                    out: str | Path | None = None,
                    n8n_webhook: str | None = None) -> Path:
    """
    Sinh 1 dashboard HTML.

    paths: file .xlsx/.jsonl/.csv do MediaCrawler xuất (trộn nền tảng được).
    profile: "auto" (theo mode cào) | "search" | "creator" | "video" | "overview".
    out: đường dẫn HTML ra (mặc định reports/dashboard_<profile>.html).
    n8n_webhook: URL webhook nhúng sẵn; None -> đọc env N8N_ACTION_WEBHOOK_URL
        rồi NOTIFY_WEBHOOK_URL.
    """
    if not paths:
        raise ValueError("Cần ít nhất 1 file dữ liệu.")
    if profile != "auto" and profile not in P.PROFILES:
        raise ValueError(f"Loại dashboard không hợp lệ: {profile!r}. "
                         f"Chọn: auto, {', '.join(P.PROFILES)}")

    bundle = load_bundle(list(paths))
    chosen = pick_profile(bundle["modes"]) if profile == "auto" else profile
    html = P.render(chosen, bundle, meta=_meta(list(paths), n8n_webhook))

    out_path = Path(out) if out else REPORT_DIR / P.filename_of(chosen)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    df = bundle["content"]
    print(f"[✓] Dashboard [{chosen}]: {out_path}  ({len(df)} bài, "
          f"{df['platform'].nunique()} nền tảng, "
          f"{len(bundle['comments'])} bình luận)")
    return out_path


def build_all(paths: list[str | Path], *, out_dir: str | Path | None = None,
              n8n_webhook: str | None = None,
              wanted: list[str] | None = None) -> dict[str, Path]:
    """
    Sinh nhiều dashboard cùng lúc + 1 trang `dashboard_index.html` để điều hướng.

    Mặc định sinh: dashboard chuyên cho từng mode có trong dữ liệu, cộng
    `overview`. Nếu có bình luận thì thêm `video` (Teardown) dù mode không phải
    detail — vì bình luận là dữ liệu đáng mổ.
    """
    if not paths:
        raise ValueError("Cần ít nhất 1 file dữ liệu.")
    bundle = load_bundle(list(paths))
    meta = _meta(list(paths), n8n_webhook)
    base = Path(out_dir) if out_dir else REPORT_DIR
    base.mkdir(parents=True, exist_ok=True)

    if wanted:
        todo = [w for w in wanted if w in P.PROFILES]
    else:
        todo = [P.MODE_TO_PROFILE[m] for m in bundle["modes"]
                if m in P.MODE_TO_PROFILE]
        if not bundle["comments"].empty and "video" not in todo:
            todo.append("video")
        if "overview" not in todo:
            todo.append("overview")
    # Bỏ trùng, giữ thứ tự
    todo = list(dict.fromkeys(todo))

    made: dict[str, Path] = {}
    for prof in todo:
        p = base / P.filename_of(prof)
        p.write_text(P.render(prof, bundle, meta=meta), encoding="utf-8")
        made[prof] = p
        print(f"[✓] Dashboard [{prof}]: {p}")

    idx = base / "dashboard_index.html"
    idx.write_text(_index_html(made, bundle, meta), encoding="utf-8")
    made["index"] = idx
    print(f"[✓] Trang điều hướng: {idx}")
    return made


_DESC = {
    "search": ("Săn trend & lên ý tưởng content", [
        "Chuẩn của ngách (P25→P90) — biết thế nào là bài tốt",
        "Video vượt trội đáng bản địa hoá + gửi loạt sang n8n",
        "Ma trận Format × Từ khoá + khe trống chưa ai làm",
        "Công thức hook nào thực sự hiệu quả (tỷ lệ thắng)",
        "Giờ vàng nên đăng + bản đồ ngách vàng"]),
    "creator": ("Soi kênh đối thủ", [
        "Nhịp đăng, đà tăng, độ đều của từng kênh",
        "Bài bứt phá so với chính kênh → công thức trúng",
        "Format & hook kênh thắng bằng gì",
        "Bảng so sánh nhiều kênh + giờ đối thủ đăng"]),
    "video": ("Mổ xẻ video & tiếng nói khán giả", [
        "Giải phẫu tương tác từng video so mốc trung vị",
        "Voice of Customer: khán giả nói gì, nhắc từ khoá gì",
        "Câu hỏi của khán giả → ý tưởng content có cầu sẵn",
        "Tín hiệu nỗi đau / mong muốn → angle bán hàng"]),
    "overview": ("Bức tranh chéo nền tảng", [
        "KPI tổng, cơ cấu nền tảng/từ khoá/format",
        "So sánh hiệu quả giữa các nền tảng",
        "Xếp hạng creator + hook/hashtag đang chạy"]),
}


def _index_html(made: dict[str, Path], bundle: dict, meta: dict) -> str:
    """Trang điều hướng giữa các dashboard đã sinh."""
    df = bundle["content"]
    modes = ", ".join(f"{k} ({n} file)" for k, n in bundle["modes"].items())
    cards = []
    for prof, path in made.items():
        if prof == "index":
            continue
        desc, bullets = _DESC.get(prof, ("", []))
        lis = "".join(f"<li>{esc(b)}</li>" for b in bullets)
        cards.append(
            f'<a class="card" href="{esc(path.name)}">'
            f'<div class="card-tag">{esc(prof.upper())}</div>'
            f'<h2>{esc(P.title_of(prof))}</h2>'
            f'<p class="card-desc">{esc(desc)}</p>'
            f'<ul>{lis}</ul>'
            f'<span class="card-go">Mở dashboard →</span></a>')

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard nghiên cứu nội dung — DigiAds</title>
<style>
:root{{color-scheme:light;--page:#eceee7;--surface:#f7f8f3;--surface-2:#eef0ea;
 --ink:#16211f;--ink-2:#4b5850;--muted:#7c8880;--rule:#d7dbd1;--accent:#eb6834;}}
@media (prefers-color-scheme:dark){{:root{{--page:#0d1311;--surface:#121917;
 --surface-2:#17201d;--ink:#eef1ec;--ink-2:#c3ccc6;--muted:#85938c;--rule:#26332f;
 --accent:#d95926;}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--page);color:var(--ink);padding:32px 24px;
 font-family:"Segoe UI",system-ui,-apple-system,Arial,sans-serif;font-size:14px;line-height:1.5}}
.wrap{{max-width:1080px;margin:0 auto}}
.eyebrow{{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
 color:var(--accent);font-weight:700}}
h1{{margin:6px 0 4px;font-size:28px;font-weight:600;
 font-family:Charter,"Iowan Old Style",Georgia,serif}}
.sub{{color:var(--ink-2);font-size:13px;margin-bottom:4px}}
.meta{{color:var(--muted);font-size:12px;border-bottom:2px solid var(--accent);
 padding-bottom:14px;margin-bottom:22px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}}
.card{{display:block;background:var(--surface);border:1px solid var(--rule);
 border-radius:10px;padding:18px 20px;text-decoration:none;color:inherit;
 transition:border-color .15s,transform .15s}}
.card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.card-tag{{font-size:10px;font-weight:800;letter-spacing:.08em;color:var(--accent)}}
.card h2{{margin:6px 0 4px;font-size:16.5px;font-weight:700}}
.card-desc{{margin:0 0 10px;color:var(--ink-2);font-size:12.5px}}
.card ul{{margin:0 0 12px;padding-left:18px;color:var(--muted);font-size:12px}}
.card ul li{{margin:3px 0}}
.card-go{{color:var(--accent);font-weight:700;font-size:12.5px}}
footer{{margin-top:26px;border-top:1px solid var(--rule);padding-top:12px;
 font-size:11px;color:var(--muted)}}
</style></head><body><div class="wrap">
<div class="eyebrow">DigiAds Kit · Social Content Radar</div>
<h1>Dashboard nghiên cứu nội dung</h1>
<div class="sub">Mỗi dashboard chuyên sâu một việc — chọn đúng loại theo mode cào.</div>
<div class="meta">Tạo lúc <b>{esc(meta.get("generated", ""))}</b> ·
{len(df)} bài · {df["platform"].nunique()} nền tảng ·
{len(bundle["comments"])} bình luận · mode: {esc(modes or "—")}<br>
Nguồn: {esc(" · ".join(meta.get("sources", [])))}</div>
<div class="grid">{"".join(cards)}</div>
<footer>Dữ liệu công khai, nghiên cứu nội bộ · creator ẩn danh theo Nghị định 13/2023.</footer>
</div></body></html>"""
