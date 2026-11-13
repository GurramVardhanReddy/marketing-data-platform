-- Grain: campaign x day. Spend and engagement by impression day, conversions by conversion day.
with spend as (
    select campaign_id, day_index,
           count(*) as impressions, sum(is_click) as clicks, sum(cost) as cost
    from {{ ref('fct_impressions') }}
    group by campaign_id, day_index
),

conv as (
    select campaign_id, conversion_day_index as day_index,
           count(*) as conversions, sum(is_attributed) as attributed_conversions
    from {{ ref('fct_conversions') }}
    group by campaign_id, conversion_day_index
)

select
    coalesce(spend.campaign_id, conv.campaign_id)     as campaign_id,
    coalesce(spend.day_index, conv.day_index)         as day_index,
    coalesce(spend.impressions, 0)                    as impressions,
    coalesce(spend.clicks, 0)                         as clicks,
    coalesce(spend.cost, 0)                           as cost,
    coalesce(conv.conversions, 0)                     as conversions,
    coalesce(conv.attributed_conversions, 0)          as attributed_conversions
from spend
full outer join conv
    on spend.campaign_id = conv.campaign_id and spend.day_index = conv.day_index
