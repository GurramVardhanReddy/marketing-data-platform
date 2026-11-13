"""Data contract for the raw Criteo attribution feed.

One row is one ad impression. Column meanings follow the dataset README
(Criteo AI Lab, "Attribution Modeling Increases Efficiency of Bidding in
Display Advertising", Diemert et al., 2017). Costs are transformed by Criteo,
not real prices.
"""

RAW_COLUMNS: dict[str, str] = {
    "timestamp": "BIGINT",  # seconds since the first impression
    "uid": "BIGINT",
    "campaign": "BIGINT",
    "conversion": "INTEGER",  # 1 if a conversion followed within 30 days
    "conversion_timestamp": "BIGINT",  # -1 if no conversion
    "conversion_id": "BIGINT",  # -1 if no conversion
    "attribution": "INTEGER",  # 1 if the advertiser attributed the conversion to Criteo
    "click": "INTEGER",
    "click_pos": "INTEGER",  # position of the click before the conversion, -1 if none
    "click_nb": "INTEGER",  # number of clicks before the conversion, -1 if none
    "cost": "DOUBLE",
    "cpo": "DOUBLE",
    "time_since_last_click": "BIGINT",  # -1 if no previous click
    **{f"cat{i}": "BIGINT" for i in range(1, 10)},
}

SECONDS_PER_DAY = 86_400
