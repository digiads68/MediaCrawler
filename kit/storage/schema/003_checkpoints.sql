-- ============================================================================
-- DigiAds Kit · 003_checkpoints.sql — checkpoint crawl tăng dần (Tier 2)
-- Chạy SAU 001_core.sql. Lưu post đã thấy theo (platform, keyword) để lần
-- chạy sau chỉ xử lý post mới (dedup) — giảm chi phí, KHÔNG tăng tải crawler.
-- ============================================================================

create table if not exists crawl_checkpoints (
    id       uuid primary key default gen_random_uuid(),
    platform text not null,
    keyword  text not null,
    post_id  text not null,
    added_ts timestamptz not null default now(),
    unique (platform, keyword, post_id)
);

create index if not exists idx_checkpoints_scope
    on crawl_checkpoints (platform, keyword);

alter table crawl_checkpoints enable row level security;
