-- Typed, renamed impressions. -1 sentinels in the raw feed become NULLs.
with src as (
    select * from {{ source('raw', 'impressions') }}
)

select
    cast(day as bigint) * 10000000 + _file_row_number            as impression_id,
    cast(day as integer)                                           as day_index,
    timestamp                                                      as impression_ts_s,
    uid                                                            as user_id,
    campaign                                                       as campaign_id,
    cast(click as integer)                                         as is_click,
    cost                                                           as cost,
    case when conversion_id = -1 then null else conversion_id end  as conversion_id,
    case when conversion_timestamp = -1 then null
         else conversion_timestamp end                             as conversion_ts_s,
    cast(conversion as integer)                                    as led_to_conversion,
    cast(attribution as integer)                                   as is_attributed,
    case when click_pos = -1 then null else click_pos end          as click_position,
    case when click_nb = -1 then null else click_nb end            as clicks_before_conversion,
    case when time_since_last_click = -1 then null
         else time_since_last_click end                            as seconds_since_last_click,
    cpo                                                            as cost_per_order,
    cat1, cat2, cat3, cat4, cat5, cat6, cat7, cat8, cat9,
    _loaded_at                                                     as loaded_at
from src
