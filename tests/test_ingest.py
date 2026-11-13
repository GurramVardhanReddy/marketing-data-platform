import duckdb
import pyarrow.parquet as pq

from mdp.contract import RAW_COLUMNS
from mdp.ingest import list_days, load_day


def test_one_drop_per_day(landing):
    assert list_days(landing) == list(range(31))


def test_drop_matches_contract(landing):
    names = pq.read_schema(next(landing.glob("day=0/*.parquet"))).names
    assert set(RAW_COLUMNS) <= set(names)


def test_load_is_idempotent_and_complete(landing, tmp_path):
    wh = tmp_path / "wh.duckdb"
    first = load_day(wh, landing, 3)
    again = load_day(wh, landing, 3)
    assert first == again > 0
    for day in list_days(landing):
        load_day(wh, landing, day)
    con = duckdb.connect(str(wh))
    total, dup = con.execute(
        "select count(*), count(*) - count(distinct (day, _file_row_number)) from raw.impressions"
    ).fetchone()
    assert total == 3299
    assert dup == 0
