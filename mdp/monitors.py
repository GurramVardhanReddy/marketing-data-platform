"""Data observability: freshness, volume, schema and distribution monitors.

The checks a tool like Monte Carlo runs, written out so each rule is visible:
after every daily load, per-day metrics are recorded in monitor.daily_metrics and
compared with the trailing days; anything out of bounds becomes a row in
monitor.alerts and, when SLACK_WEBHOOK_URL is set, a Slack message.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from mdp.contract import RAW_COLUMNS

# A day's row count is anomalous when it is outside [median / VOLUME_RATIO, median * VOLUME_RATIO]
VOLUME_RATIO = 2.0
# A rate (click rate, conversion rate) is anomalous beyond this many robust z-scores
RATE_Z = 4.0
# ...and also moves at least this much relative to the trailing median (day-to-day noise is ~5-9%)
RATE_MIN_REL_CHANGE = 0.10
TRAILING_DAYS = 7
MAX_HOURS_SINCE_LOAD = 26


@dataclass
class Alert:
    day: int
    check: str
    severity: str
    detail: str


def _ensure_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS monitor")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor.daily_metrics (
            day INTEGER PRIMARY KEY, n_rows BIGINT, click_rate DOUBLE,
            conversion_rate DOUBLE, attributed_rate DOUBLE, total_cost DOUBLE,
            null_cells BIGINT, n_campaigns BIGINT, measured_at TIMESTAMP)
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor.alerts (
            day INTEGER, check_name VARCHAR, severity VARCHAR, detail VARCHAR,
            raised_at TIMESTAMP)
        """
    )


def record_day(con: duckdb.DuckDBPyConnection, day: int) -> None:
    null_expr = " + ".join(f"count(*) - count({c})" for c in RAW_COLUMNS)
    con.execute("DELETE FROM monitor.daily_metrics WHERE day = ?", [day])
    con.execute(
        f"""
        INSERT INTO monitor.daily_metrics
        SELECT ?, count(*), avg(click), avg(conversion), avg(attribution),
               sum(cost), {null_expr}, count(DISTINCT campaign), ?
        FROM raw.impressions WHERE day = ?
        """,
        [day, datetime.now(UTC).replace(tzinfo=None), day],
    )


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _robust_z(x: float, history: list[float]) -> float:
    med = _median(history)
    mad = _median([abs(h - med) for h in history]) * 1.4826
    if mad == 0:
        return 0.0 if x == med else math.inf
    return (x - med) / mad


def check_day(con: duckdb.DuckDBPyConnection, day: int, drop_columns: list[str]) -> list[Alert]:
    alerts: list[Alert] = []

    missing = [c for c in RAW_COLUMNS if c not in drop_columns]
    extra = [c for c in drop_columns if c not in RAW_COLUMNS and c != "day"]
    if missing or extra:
        alerts.append(Alert(day, "schema", "high", f"missing={missing} extra={extra}"))

    row = con.execute(
        "SELECT n_rows, click_rate, conversion_rate, null_cells FROM monitor.daily_metrics "
        "WHERE day = ?",
        [day],
    ).fetchone()
    if row is None:
        return alerts + [Alert(day, "volume", "high", "no rows loaded")]
    n_rows, click_rate, conv_rate, null_cells = row
    if null_cells:
        alerts.append(Alert(day, "nulls", "medium", f"{null_cells} null cells"))

    hist = con.execute(
        "SELECT n_rows, click_rate, conversion_rate FROM monitor.daily_metrics "
        "WHERE day < ? ORDER BY day DESC LIMIT ?",
        [day, TRAILING_DAYS],
    ).fetchall()
    if len(hist) >= 3:
        med_rows = _median([h[0] for h in hist])
        if not (med_rows / VOLUME_RATIO <= n_rows <= med_rows * VOLUME_RATIO):
            alerts.append(
                Alert(day, "volume", "high", f"{n_rows} rows vs trailing median {med_rows:.0f}")
            )
        for name, value, idx in (("click_rate", click_rate, 1), ("conversion_rate", conv_rate, 2)):
            past = [h[idx] for h in hist]
            z = _robust_z(value, past)
            rel = abs(value / _median(past) - 1) if _median(past) else math.inf
            if abs(z) > RATE_Z and rel >= RATE_MIN_REL_CHANGE:
                alerts.append(
                    Alert(day, name, "medium", f"{value:.5f} (robust z {z:.1f}, {rel:+.0%})")
                )
    return alerts


def check_freshness(con: duckdb.DuckDBPyConnection, now: datetime | None = None) -> Alert | None:
    (last,) = con.execute("SELECT max(_loaded_at) FROM raw.impressions").fetchone()
    now = now or datetime.now(UTC).replace(tzinfo=None)
    if last is None or (now - last).total_seconds() / 3600 > MAX_HOURS_SINCE_LOAD:
        return Alert(-1, "freshness", "high", f"last load {last}")
    return None


def notify(alerts: list[Alert]) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url or not alerts or not url.startswith("https://hooks.slack.com/"):
        return
    text = "\n".join(f"[{a.severity}] day {a.day} {a.check}: {a.detail}" for a in alerts)
    body = json.dumps({"text": f"Data monitor alerts\n{text}"}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})  # noqa: S310
    urllib.request.urlopen(req, timeout=10)  # noqa: S310 - https Slack webhook only (checked above)


def run_monitors(warehouse: Path, day: int, drop_columns: list[str]) -> list[Alert]:
    con = duckdb.connect(str(warehouse))
    try:
        _ensure_tables(con)
        record_day(con, day)
        alerts = check_day(con, day, drop_columns)
        fresh = check_freshness(con)
        if fresh:
            alerts.append(fresh)
        now = datetime.now(UTC).replace(tzinfo=None)
        for a in alerts:
            con.execute(
                "INSERT INTO monitor.alerts VALUES (?, ?, ?, ?, ?)",
                [a.day, a.check, a.severity, a.detail, now],
            )
    finally:
        con.close()
    notify(alerts)
    return alerts
