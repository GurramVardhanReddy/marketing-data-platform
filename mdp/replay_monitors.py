"""Re-run the monitors over every loaded day, in order, from scratch."""

import json

import duckdb

from mdp import flows, monitors
from mdp.contract import RAW_COLUMNS


def main() -> None:
    con = duckdb.connect(str(flows.WAREHOUSE))
    con.execute("DROP SCHEMA IF EXISTS monitor CASCADE")
    rows = con.execute("SELECT DISTINCT day FROM raw.impressions ORDER BY day").fetchall()
    days = [d for (d,) in rows]
    con.close()
    alerts = []
    for day in days:
        alerts += monitors.run_monitors(flows.WAREHOUSE, day, list(RAW_COLUMNS))
    print(json.dumps({"days": len(days), "alerts": [a.__dict__ for a in alerts]}, indent=1))


if __name__ == "__main__":
    main()
