-- Each campaign's spend tier given the data loaded so far. The snapshot records how tiers change day by day.
with spend as (
    select
        campaign_id,
        sum(cost)        as cost_to_date,
        count(*)         as impressions_to_date,
        max(day_index)   as as_of_day_index
    from {{ ref('stg_impressions') }}
    group by campaign_id
)

select
    campaign_id,
    cost_to_date,
    impressions_to_date,
    as_of_day_index,
    case ntile(3) over (order by cost_to_date desc)
        when 1 then 'high_spend'
        when 2 then 'mid_spend'
        else 'low_spend'
    end as spend_tier
from spend
