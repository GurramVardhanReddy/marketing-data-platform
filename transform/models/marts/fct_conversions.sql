-- Grain: one conversion, with its path summary and the advertiser's attribution decision.
select
    conversion_id,
    user_id,
    campaign_id,
    conversion_day_index,
    n_impressions,
    n_clicks,
    conversion_ts_s - last_click_ts_s        as seconds_last_click_to_conversion,
    conversion_ts_s - first_impression_ts_s  as seconds_first_touch_to_conversion,
    is_attributed,
    path_cost,
    cost_per_order,
    spans_multiple_campaigns,
    spans_multiple_users,
    has_mixed_attribution
from {{ ref('int_conversion_journeys') }}
