"""Headline numbers from the warehouse, written to results/pipeline_summary.json."""

import json

import duckdb

from mdp import flows


def run() -> dict:
    con = duckdb.connect(str(flows.WAREHOUSE), read_only=True)
    q = lambda sql: con.execute(sql).fetchone()  # noqa: E731
    out = {
        "raw_rows": q("select count(*) from raw.impressions")[0],
        "days_loaded": q("select count(distinct day) from raw.impressions")[0],
        "fct_impressions": q("select count(*) from marts.fct_impressions")[0],
        "fct_conversions": q("select count(*) from marts.fct_conversions")[0],
        "fct_campaign_daily": q("select count(*) from marts.fct_campaign_daily")[0],
        "dim_campaign": q("select count(*) from marts.dim_campaign")[0],
        "credited_conversions": q("select sum(is_attributed) from marts.fct_conversions")[0],
        "conversions_spanning_campaigns_or_users": q(
            "select count(*) from marts.fct_conversions "
            "where spans_multiple_campaigns or spans_multiple_users")[0],
        "snapshot_versions": q("select count(*) from snapshots.snap_campaign_tier")[0],
        "campaigns_that_changed_tier": q(
            "select count(*) from (select campaign_id from snapshots.snap_campaign_tier "
            "group by 1 having count(*) > 1)")[0],
        "share_of_spend_on_campaigns_with_no_credited_conversion": round(q(
            "select coalesce(sum(cost) filter (where attributed_conversions = 0), 0) / sum(cost) "
            "from marts.dim_campaign")[0], 4),
        "campaigns_with_no_credited_conversion": q(
            "select count(*) from marts.dim_campaign where attributed_conversions = 0")[0],
        "monitor_alerts_on_clean_data": q("select count(*) from monitor.alerts")[0],
    }
    top = con.execute(
        "select sum(cost) filter (where r <= 10) / sum(cost) from "
        "(select cost, row_number() over (order by cost desc) r from marts.dim_campaign)"
    ).fetchone()[0]
    out["share_of_spend_in_top_10_campaigns"] = round(top, 4)
    con.close()
    (flows.ROOT / "results").mkdir(exist_ok=True)
    (flows.ROOT / "results" / "pipeline_summary.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
