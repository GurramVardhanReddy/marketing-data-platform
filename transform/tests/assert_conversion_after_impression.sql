-- A conversion can only follow the impressions on its path.
select conversion_id
from {{ ref('fct_conversions') }}
where seconds_first_touch_to_conversion < 0
