{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='day_index'
) }}

-- Grain: one impression. Incremental by day: only days loaded since the last run are rebuilt.
select
    impression_id,
    day_index,
    impression_ts_s,
    user_id,
    campaign_id,
    conversion_id,
    is_click,
    led_to_conversion,
    is_attributed,
    cost,
    seconds_since_last_click,
    loaded_at
from {{ ref('stg_impressions') }}
{% if is_incremental() %}
where day_index in (
    select distinct day_index from {{ ref('stg_impressions') }}
    where loaded_at > (select max(loaded_at) from {{ this }})
)
{% endif %}
