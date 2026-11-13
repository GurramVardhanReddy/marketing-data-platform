-- Day index 0 is the first day of the feed. The dataset gives relative time only, so no calendar dates are invented.
with days as (
    select distinct day_index from {{ ref('stg_impressions') }}
    union
    select distinct conversion_day_index from {{ ref('int_conversion_journeys') }}
)

select
    day_index,
    cast(floor(day_index / 7) as integer)  as week_index,
    mod(day_index, 7)                      as day_of_week_index,
    day_index <= (select max(day_index) from {{ ref('stg_impressions') }}) as in_impression_window
from days
