-- ============================================================================
-- DigiAds Kit · 002_views.sql — view phục vụ dashboard
-- Chạy SAU 001_core.sql (cần các bảng lõi).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- v_trend_top — top post 30 ngày gần nhất theo trend_score (CS1)
-- ----------------------------------------------------------------------------
create or replace view v_trend_top as
select
    p.id,
    p.platform,
    p.source_keyword,
    p.title,
    p.format,
    p.liked,
    p.comment,
    p.share,
    p.collect,
    p.trend_score,
    p.url,
    p.created_at,
    p.added_ts
from trend_posts p
where p.added_ts >= now() - interval '30 days'
order by p.trend_score desc;

-- ----------------------------------------------------------------------------
-- v_sov_trend — %SOV theo tuần + biến động WoW (CS11)
-- ----------------------------------------------------------------------------
create or replace view v_sov_trend as
select
    s.week,
    s.brand,
    s.so_bai,
    s.eng,
    s.sov_pct,
    s.sov_pct - lag(s.sov_pct) over (partition by s.brand order by s.week)
        as sov_wow_delta,
    s.updated_at
from sov_weekly s
order by s.week, s.sov_pct desc;

-- ----------------------------------------------------------------------------
-- v_rising_koc — creator đang lên, sắp theo điểm tổng (CS9)
-- ----------------------------------------------------------------------------
create or replace view v_rising_koc as
select
    k.creator_hash,
    k.nickname_masked,
    k.so_video,
    k.eng_tb,
    k.do_deu,
    k.velocity,
    k.diem_tong,
    k.verdict,
    k.updated_at
from koc_scores k
where k.rising
order by k.diem_tong desc;

-- ----------------------------------------------------------------------------
-- v_niche_quadrant — gom source_keyword: volume vs save TB, chia 4 quadrant
-- theo median-split (CS4/CS6). Nhãn khớp analyzer.opportunity_map().
-- ----------------------------------------------------------------------------
create or replace view v_niche_quadrant as
with agg as (
    select
        source_keyword,
        count(*)              as so_bai,
        avg(collect)::numeric as save_tb,
        avg(liked + comment + share + collect)::numeric as eng_tb
    from trend_posts
    group by source_keyword
),
med as (
    select
        percentile_cont(0.5) within group (order by so_bai)  as vol_med,
        percentile_cont(0.5) within group (order by save_tb) as save_med
    from agg
)
select
    a.source_keyword,
    a.so_bai,
    round(a.save_tb, 1) as save_tb,
    round(a.eng_tb, 1)  as eng_tb,
    case
        when a.so_bai <= m.vol_med and a.save_tb >  m.save_med then '🌊 biển xanh — đánh ngay'
        when a.so_bai >  m.vol_med and a.save_tb >  m.save_med then '⚔ cạnh tranh — cần angle khác biệt'
        when a.so_bai <= m.vol_med                              then '🏜 sa mạc — chưa có cầu'
        else '🔴 bão hoà — tránh'
    end as quadrant
from agg a
cross join med m
order by quadrant, save_tb desc;
