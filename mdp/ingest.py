"""Ingest: turn the raw Criteo file into daily drops, then load drops into the warehouse.

The public dataset is one 30-day file. To behave like a real marketing feed, it is
split into one Parquet file per day ("drops"). Drops land in a local folder or,
when MDP_S3_BUCKET is set, in S3 under raw/impressions/day=NN/, where an S3 event
triggers Snowpipe (see infra/). Locally, drops are loaded into DuckDB one day at a
time, idempotently.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from mdp.contract import RAW_COLUMNS, SECONDS_PER_DAY


def split_into_daily_drops(raw_file: Path, landing_dir: Path) -> list[Path]:
    """Write one Parquet drop per day of impressions. Returns the drop paths."""
    landing_dir.mkdir(parents=True, exist_ok=True)
    columns = ", ".join(f"'{c}': '{t}'" for c, t in RAW_COLUMNS.items())
    con = duckdb.connect()
    con.execute(
        f"""
        CREATE TEMP VIEW raw AS
        SELECT *, CAST(timestamp // {SECONDS_PER_DAY} AS INTEGER) AS day
        FROM read_csv('{raw_file.as_posix()}', delim='\t', header=true,
                      columns={{{columns}}})
        """
    )
    con.execute(
        f"""
        COPY raw TO '{landing_dir.as_posix()}'
        (FORMAT PARQUET, PARTITION_BY (day), OVERWRITE_OR_IGNORE, FILENAME_PATTERN 'drop')
        """
    )
    return sorted(landing_dir.glob("day=*/*.parquet"))


def list_days(landing_dir: Path) -> list[int]:
    return sorted(int(p.name.split("=")[1]) for p in landing_dir.glob("day=*"))


def upload_drop_to_s3(drop: Path, day: int, bucket: str) -> str:
    """Upload one drop to S3; the bucket notification starts Snowpipe."""
    import boto3

    key = f"raw/impressions/day={day:02d}/{drop.name}"
    boto3.client("s3").upload_file(str(drop), bucket, key)
    return f"s3://{bucket}/{key}"


def load_day(warehouse: Path, landing_dir: Path, day: int) -> int:
    """Load one day's drop into raw.impressions. Re-running a day replaces it."""
    files = sorted((landing_dir / f"day={day}").glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no drop for day {day} in {landing_dir}")
    file_list = ", ".join(f"'{f.as_posix()}'" for f in files)
    cols = ", ".join(RAW_COLUMNS)
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    con = duckdb.connect(str(warehouse))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS raw.impressions AS
            SELECT {cols}, 0 AS day, ''::VARCHAR AS _source_file,
                   0::BIGINT AS _file_row_number, TIMESTAMP '1970-01-01' AS _loaded_at
            FROM read_parquet([{file_list}]) LIMIT 0
            """
        )
        con.execute("BEGIN")
        con.execute("DELETE FROM raw.impressions WHERE day = ?", [day])
        # Snowpipe's COPY records METADATA$FILENAME and METADATA$FILE_ROW_NUMBER the same way
        con.execute(
            f"""
            INSERT INTO raw.impressions
            SELECT {cols}, {day} AS day, filename AS _source_file,
                   file_row_number AS _file_row_number, ? AS _loaded_at
            FROM read_parquet([{file_list}], filename=true, file_row_number=true)
            """,
            [loaded_at],
        )
        con.execute("COMMIT")
        (n,) = con.execute("SELECT count(*) FROM raw.impressions WHERE day = ?", [day]).fetchone()
        return int(n)
    finally:
        con.close()


def s3_bucket() -> str | None:
    return os.environ.get("MDP_S3_BUCKET") or None
