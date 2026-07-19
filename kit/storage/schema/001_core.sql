-- ============================================================================
-- DigiAds Kit · 001_core.sql — bảng lõi cho kho dữ liệu nghiên cứu
-- Chạy trên Postgres 15+ / Supabase. Chạy TRƯỚC 002_views.sql.
--
-- LƯU Ý BẢO MẬT:
--   * RLS bật mặc định trên MỌI bảng. Backend ghi/đọc qua service_role key
--     (bypass RLS). TUYỆT ĐỐI không expose service_role key ra client/WebUI.
--   * Dữ liệu creator đã ẩn danh (creator_hash, nickname_masked) — không lưu PII thô.
-- ============================================================================

create extension if not exists pgcrypto;  -- gen_random_uuid()

-- ----------------------------------------------------------------------------
-- crawl_runs — nhật ký mỗi lần crawl (mọi bảng dữ liệu trỏ về run_id)
-- ----------------------------------------------------------------------------
create table if not exists crawl_runs (
    id            uuid primary key default gen_random_uuid(),
    platform      text not null,                 -- dy | xhs | ks | bili | wb | tieba | zhihu
    crawler_type  text not null,                 -- search | detail | creator
    keywords      text,                          -- từ khoá, phân tách bằng dấu phẩy
    started_at    timestamptz not null default now(),
    finished_at   timestamptz,
    note_count    integer not null default 0,
    status        text not null default 'running'  -- running | done | failed
);

comment on table crawl_runs is 'Nhật ký crawl — chỉ nghiên cứu nội bộ dữ liệu công khai';

-- ----------------------------------------------------------------------------
-- trend_posts — bài viết đã enrich (CS1 trend / CS4+CS6 opportunity / CS7 seasonal)
-- ----------------------------------------------------------------------------
create table if not exists trend_posts (
    id             uuid primary key default gen_random_uuid(),
    run_id         uuid references crawl_runs(id) on delete set null,
    platform       text not null,
    source_keyword text not null,
    title          text,
    format         text,                          -- before-after | review | list/top | ...
    liked          bigint not null default 0,
    comment        bigint not null default 0,
    share          bigint not null default 0,
    collect        bigint not null default 0,
    created_at     timestamptz,                   -- thời điểm đăng bài (từ create_time)
    url            text,
    trend_score    numeric(8,2) not null default 0,
    added_ts       timestamptz not null default now()
);

create index if not exists idx_trend_posts_keyword  on trend_posts (source_keyword);
create index if not exists idx_trend_posts_added_ts on trend_posts (added_ts);
create index if not exists idx_trend_posts_score    on trend_posts (trend_score desc);

-- ----------------------------------------------------------------------------
-- koc_scores — scorecard KOC (CS3) + cờ rising (CS9)
-- ----------------------------------------------------------------------------
create table if not exists koc_scores (
    id              uuid primary key default gen_random_uuid(),
    run_id          uuid references crawl_runs(id) on delete set null,
    creator_hash    text not null,                -- định danh ẩn danh (KHÔNG de-anonymize)
    nickname_masked text,
    so_video        integer not null default 0,
    eng_tb          numeric(12,1) not null default 0,
    do_deu          numeric(6,3)  not null default 0,   -- 1/(1+CV)
    velocity        numeric(8,2)  not null default 1,   -- ER nửa sau / nửa đầu
    diem_tong       numeric(6,1)  not null default 0,
    verdict         text,                          -- bỏ qua | theo dõi | ký ngay
    rising          boolean not null default false,
    updated_at      timestamptz not null default now(),
    unique (creator_hash)
);

create index if not exists idx_koc_scores_rising on koc_scores (rising) where rising;
create index if not exists idx_koc_scores_diem   on koc_scores (diem_tong desc);

-- ----------------------------------------------------------------------------
-- angle_library — kho angle nạp pipeline AI video (CS5)
-- ----------------------------------------------------------------------------
create table if not exists angle_library (
    id             uuid primary key default gen_random_uuid(),
    angle_id       text not null unique,          -- khoá tự nhiên để upsert idempotent
    platform       text not null,
    source_keyword text,
    hook           text,
    format         text,
    pain_or_desire text,
    cta_observed   text,
    sound_ref      text,
    "like"         bigint not null default 0,
    comment        bigint not null default 0,
    share          bigint not null default 0,
    collect        bigint not null default 0,
    lang           text not null default 'zh',
    status         text not null default 'new',   -- new | briefed | produced | killed
    created_at     timestamptz not null default now()
);

create index if not exists idx_angle_library_keyword on angle_library (source_keyword);
create index if not exists idx_angle_library_status  on angle_library (status);

-- ----------------------------------------------------------------------------
-- sov_weekly — share of voice theo tuần (CS11)
-- ----------------------------------------------------------------------------
create table if not exists sov_weekly (
    id         uuid primary key default gen_random_uuid(),
    week       text not null,                     -- ISO: 2026-W29
    brand      text not null,
    so_bai     integer not null default 0,
    eng        bigint  not null default 0,
    sov_pct    numeric(5,1) not null default 0,
    updated_at timestamptz not null default now(),
    unique (week, brand)                          -- khoá tự nhiên để upsert idempotent
);

create index if not exists idx_sov_weekly_week  on sov_weekly (week);
create index if not exists idx_sov_weekly_brand on sov_weekly (brand);

-- ----------------------------------------------------------------------------
-- price_intel — tình báo giá & khuyến mãi (CS8)
-- ----------------------------------------------------------------------------
create table if not exists price_intel (
    id             uuid primary key default gen_random_uuid(),
    run_id         uuid references crawl_runs(id) on delete set null,
    competitor     text,
    price_text     text,
    promo_text     text,
    source_keyword text,
    eng            bigint not null default 0,
    created_at     timestamptz not null default now()
);

create index if not exists idx_price_intel_keyword on price_intel (source_keyword);

-- ============================================================================
-- RLS — bật trên mọi bảng. KHÔNG tạo policy cho anon: chỉ backend (service_role,
-- bypass RLS) được đọc/ghi. Nếu sau này cần dashboard đọc trực tiếp, tạo policy
-- SELECT riêng cho role authenticated — không bao giờ dùng service_role ở client.
-- ============================================================================
alter table crawl_runs    enable row level security;
alter table trend_posts   enable row level security;
alter table koc_scores    enable row level security;
alter table angle_library enable row level security;
alter table sov_weekly    enable row level security;
alter table price_intel   enable row level security;
