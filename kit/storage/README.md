# kit/storage — Kho dữ liệu Supabase

Lớp lưu trữ Tier 1: schema SQL + writer ghi kết quả analyzer vào Supabase để
làm dashboard và theo dõi dài hạn.

> ⚠️ Backend dùng **service_role key** (biến `SUPABASE_KEY` trong `.env`).
> Không bao giờ nhúng key này vào client/WebUI — RLS đã bật trên mọi bảng và
> không có policy cho anon.

## Chạy migration

Chạy **theo thứ tự tên file** (001 → 002):

| Thứ tự | File | Nội dung |
|---|---|---|
| 1 | `schema/001_core.sql` | 6 bảng lõi: `crawl_runs`, `trend_posts`, `koc_scores`, `angle_library`, `sov_weekly`, `price_intel` + index + RLS |
| 2 | `schema/002_views.sql` | 4 view dashboard: `v_trend_top`, `v_sov_trend`, `v_rising_koc`, `v_niche_quadrant` |

### Cách 1 — Supabase SQL Editor (nhanh nhất)

1. Mở https://supabase.com/dashboard → project → **SQL Editor**.
2. Dán nội dung `001_core.sql`, bấm **Run**. Lặp lại với `002_views.sql`.

### Cách 2 — Supabase CLI

```bash
supabase link --project-ref <project-ref>
supabase db execute --file kit/storage/schema/001_core.sql
supabase db execute --file kit/storage/schema/002_views.sql
```

### Cách 3 — psql trực tiếp (Postgres 15+)

```bash
psql "$DATABASE_URL" -f kit/storage/schema/001_core.sql
psql "$DATABASE_URL" -f kit/storage/schema/002_views.sql
```

Migration idempotent (`create table if not exists` / `create or replace view`) —
chạy lại không lỗi.

## Ghi dữ liệu

Dùng `supabase_writer.py` (xem docstring trong file) hoặc cờ `--to supabase`
của analyzer:

```bash
python kit/analyzer/mediacrawler_analyzer.py trend data/douyin/search_x.xlsx --to supabase
```

Upsert theo khoá tự nhiên (`angle_id`; `(week, brand)`; `creator_hash`) nên chạy
lại không nhân đôi dữ liệu.
