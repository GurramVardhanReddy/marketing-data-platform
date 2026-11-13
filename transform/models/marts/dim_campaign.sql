with imp as (
    select
        campaign_id,
        min(day_index)     as first_day_index,
        max(day_index)     as last_day_index,
        count(*)           as impressions,
        sum(is_click)      as clicks,
        sum(cost)          as cost
    from {{ ref('stg_impressions') }}
    group by campaign_id
),

conv as (
    select
        campaign_id,
        count(*)                       as conversions,
        sum(is_attributed)             as attributed_conversions,
        avg(cost_per_order)            as avg_cost_per_order
    from {{ ref('int_conversion_journeys') }}
    group by campaign_id
)

select
    imp.campaign_id,
    imp.first_day_index,
    imp.last_day_index,
    imp.impressions,
    imp.clicks,
    imp.cost,
    coalesce(conv.conversions, 0)             as conversions,
    coalesce(conv.attributed_conversions, 0)  as attributed_conversions,
    imp.cost / nullif(conv.attributed_conversions, 0) as cost_per_attributed_conversion,
    conv.avg_cost_per_order
from imp
left join conv using (campaign_id)
