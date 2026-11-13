from pathlib import Path

import pytest

from mdp.ingest import split_into_daily_drops

SAMPLE = Path(__file__).parent / "data" / "criteo_sample.tsv.gz"


@pytest.fixture(scope="session")
def landing(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("landing")
    split_into_daily_drops(SAMPLE, d)
    return d
