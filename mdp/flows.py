"""Prefect orchestration: one run per daily drop.

daily_pipeline(day): load the drop -> run monitors -> dbt build (models + tests)
-> dbt snapshot (campaign tier history). backfill() replays every day in order,
which is also how the snapshot builds its history.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pyarrow.parquet as pq
from prefect import flow, get_run_logger, task

from mdp import ingest, monitors

ROOT = Path(__file__).resolve().parent.parent
LANDING = Path(os.environ.get("MDP_LANDING", ROOT / "data" / "landing"))
WAREHOUSE = Path(os.environ.get("MDP_WAREHOUSE", ROOT / "warehouse.duckdb"))
DBT_DIR = ROOT / "transform"


@task(retries=2, retry_delay_seconds=30)
def land(day: int) -> list[str]:
    """Upload the drop to S3 when a bucket is configured; return the drop's columns."""
    files = sorted((LANDING / f"day={day}").glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no drop for day {day}")
    bucket = ingest.s3_bucket()
    if bucket:
        for f in files:
            ingest.upload_drop_to_s3(f, day, bucket)
    return pq.read_schema(files[0]).names


@task(retries=2, retry_delay_seconds=30)
def load(day: int) -> int:
    return ingest.load_day(WAREHOUSE, LANDING, day)


@task
def monitor(day: int, columns: list[str]) -> int:
    alerts = monitors.run_monitors(WAREHOUSE, day, columns)
    log = get_run_logger()
    for a in alerts:
        log.warning("monitor alert day=%s %s [%s]: %s", a.day, a.check, a.severity, a.detail)
    return len(alerts)


def _dbt(*args: str) -> None:
    env = {**os.environ, "MDP_WAREHOUSE": str(WAREHOUSE), "DBT_PROFILES_DIR": str(DBT_DIR)}
    subprocess.run(["dbt", *args, "--project-dir", str(DBT_DIR)], check=True, env=env)


@task(retries=1, retry_delay_seconds=60)
def dbt_build(full_refresh: bool = False) -> None:
    extra = ["--full-refresh"] if full_refresh else []
    _dbt("build", "--exclude", "resource_type:snapshot", *extra)


@task
def dbt_snapshot() -> None:
    _dbt("snapshot")


@flow(name="daily-marketing-pipeline")
def daily_pipeline(day: int, build: bool = True) -> dict:
    columns = land(day)
    rows = load(day)
    n_alerts = monitor(day, columns)
    if build:
        dbt_build()
        dbt_snapshot()
    return {"day": day, "rows": rows, "alerts": n_alerts}


@flow(name="backfill")
def backfill() -> list[dict]:
    """Replay all drops in order, exactly as the daily schedule would have run them.

    Incremental models pick up one new day per run, and the snapshot runs after
    each day, so campaign tier changes are recorded with the day they happened.
    """
    return [daily_pipeline(day) for day in ingest.list_days(LANDING)]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        print(backfill())
    else:
        print(daily_pipeline(int(sys.argv[1])))
