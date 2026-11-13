-- The advertiser only credits clicked paths; an attributed conversion with no click is a feed error.
select conversion_id from {{ ref('fct_conversions') }} where is_attributed = 1 and n_clicks = 0
