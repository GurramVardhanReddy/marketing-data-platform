{{ config(severity='warn') }}
-- A conversion should belong to one campaign and one user. The public feed has a small number
-- that do not; this test keeps them visible on every run.
select conversion_id from {{ ref('fct_conversions') }}
where spans_multiple_campaigns or spans_multiple_users
