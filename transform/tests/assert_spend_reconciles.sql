-- Total spend in the campaign-day mart must equal total spend in the impression fact.
select abs(a.cost - b.cost) as diff
from (select sum(cost) as cost from {{ ref('fct_campaign_daily') }}) a,
     (select sum(cost) as cost from {{ ref('fct_impressions') }}) b
where abs(a.cost - b.cost) > 1e-6
