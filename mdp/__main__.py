"""CLI: python -m mdp {prepare RAW_FILE | backfill | day N | attribution}"""

import json
import sys
from pathlib import Path

from mdp import flows, ingest


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prepare":
        drops = ingest.split_into_daily_drops(Path(sys.argv[2]), flows.LANDING)
        print(f"{len(drops)} drops in {flows.LANDING}")
    elif cmd == "backfill":
        print(json.dumps(flows.backfill(), indent=1))
    elif cmd == "day":
        print(flows.daily_pipeline(int(sys.argv[2])))
    elif cmd == "attribution":
        from mdp import attribution

        print(json.dumps(attribution.run(flows.WAREHOUSE), indent=2))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
