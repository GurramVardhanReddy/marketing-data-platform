FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home app
WORKDIR /app
COPY pyproject.toml ./
COPY mdp ./mdp
RUN pip install --no-cache-dir ".[snowflake]"
COPY transform ./transform
COPY scripts ./scripts
COPY tests/data ./tests/data
RUN chown -R app /app
USER app

ENV MDP_LANDING=/app/data/landing \
    MDP_WAREHOUSE=/app/data/warehouse.duckdb \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false
# Default: run the pipeline on the bundled sample. Mount data/ and pass a raw file for the full feed.
CMD ["bash", "-c", "python -m mdp prepare tests/data/criteo_sample.tsv.gz && python -m mdp backfill"]
