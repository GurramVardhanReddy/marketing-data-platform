import duckdb

from mdp import monitors
from mdp.contract import RAW_COLUMNS
from mdp.ingest import list_days, load_day


def test_robust_z_flags_outlier():
    hist = [0.30, 0.31, 0.29, 0.30, 0.32, 0.30]
    assert abs(monitors._robust_z(0.305, hist)) < 1
    assert monitors._robust_z(0.60, hist) > monitors.RATE_Z


def test_schema_drift_is_reported(landing, tmp_path):
    wh = tmp_path / "wh.duckdb"
    load_day(wh, landing, 0)
    cols = [c for c in RAW_COLUMNS if c != "cost"] + ["surprise"]
    alerts = monitors.run_monitors(wh, 0, cols)
    schema = [a for a in alerts if a.check == "schema"]
    assert schema and "cost" in schema[0].detail and "surprise" in schema[0].detail


def test_volume_drop_is_flagged(landing, tmp_path):
    wh = tmp_path / "wh.duckdb"
    for day in list_days(landing)[:6]:
        load_day(wh, landing, day)
        monitors.run_monitors(wh, day, list(RAW_COLUMNS))
    con = duckdb.connect(str(wh))
    # simulate a partial delivery for day 5: keep only 10% of its rows
    con.execute("delete from raw.impressions where day = 5 and _file_row_number % 10 <> 0")
    con.close()
    alerts = monitors.run_monitors(wh, 5, list(RAW_COLUMNS))
    assert any(a.check == "volume" for a in alerts)


def test_clean_day_has_no_alerts(landing, tmp_path):
    wh = tmp_path / "wh.duckdb"
    alerts = []
    for day in list_days(landing)[:6]:
        load_day(wh, landing, day)
        alerts = monitors.run_monitors(wh, day, list(RAW_COLUMNS))
    assert [a for a in alerts if a.check in ("schema", "nulls", "freshness")] == []


def test_small_rate_wobble_is_not_an_alert():
    # A 5% move on a very stable history is statistically unusual but not worth paging anyone
    hist = [0.0490, 0.0491, 0.0489, 0.0490, 0.0492, 0.0490]
    value = 0.0515
    assert abs(monitors._robust_z(value, hist)) > monitors.RATE_Z
    assert abs(value / monitors._median(hist) - 1) < monitors.RATE_MIN_REL_CHANGE
