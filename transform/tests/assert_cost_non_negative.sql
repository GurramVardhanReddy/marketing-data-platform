select impression_id, cost from {{ ref('fct_impressions') }} where cost < 0
