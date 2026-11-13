-- One row per conversion: the path of impressions that led to it.
with touches as (
    select * from {{ ref('stg_impressions') }}
    where conversion_id is not null
)

select
    conversion_id,
    min(user_id)                                             as user_id,
    min(campaign_id)                                         as campaign_id,
    count(distinct campaign_id) > 1                          as spans_multiple_campaigns,
    count(distinct user_id) > 1                              as spans_multiple_users,
    count(*)                                                 as n_impressions,
    sum(is_click)                                            as n_clicks,
    min(impression_ts_s)                                     as first_impression_ts_s,
    max(impression_ts_s)                                     as last_impression_ts_s,
    max(case when is_click = 1 then impression_ts_s end)     as last_click_ts_s,
    max(conversion_ts_s)                                     as conversion_ts_s,
    cast(floor(max(conversion_ts_s) / 86400) as integer)     as conversion_day_index,
    max(is_attributed)                                       as is_attributed,
    count(distinct is_attributed) > 1                        as has_mixed_attribution,
    sum(cost)                                                as path_cost,
    max(cost_per_order)                                      as cost_per_order
from touches
group by conversion_id
