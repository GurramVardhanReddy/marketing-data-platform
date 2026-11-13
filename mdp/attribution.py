"""Attribution model on the conversion mart.

Question: which conversions does the advertiser credit to Criteo? The advertiser
weighs Criteo against its other channels, so the label is not something Criteo
controls. A bidder that predicts it can value an impression by the conversions it
will actually be paid for (Diemert et al., 2017).

Compared, out-of-time (train on earlier conversion days, test on later ones):
  1. rule: credit when the last Criteo click is within T seconds of the conversion
     (T chosen on the training days)
  2. logistic regression on path features
  3. gradient boosting on the same features plus the campaign's training-period
     credit rate
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = Path(os.environ.get("MDP_WAREHOUSE", ROOT / "warehouse.duckdb"))
TEST_FROM_DAY = 25  # conversions on day >= 25 are the out-of-time test set
SEED = 7


def count_excluded(warehouse: Path) -> int:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        (n,) = con.execute(
            "select count(*) from marts.fct_conversions "
            "where spans_multiple_campaigns or spans_multiple_users"
        ).fetchone()
        return int(n)
    finally:
        con.close()


def load_conversions(warehouse: Path) -> pd.DataFrame:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        return con.execute(
            """
            select conversion_id, campaign_id, conversion_day_index, n_impressions, n_clicks,
                   seconds_last_click_to_conversion, seconds_first_touch_to_conversion,
                   path_cost, is_attributed
            from marts.fct_conversions
            where not spans_multiple_campaigns and not spans_multiple_users
            """
        ).df()
    finally:
        con.close()


def features(df: pd.DataFrame, campaign_rate: pd.Series, prior: float) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["log_secs_last_click"] = np.log1p(df["seconds_last_click_to_conversion"].clip(lower=0))
    x["log_secs_first_touch"] = np.log1p(df["seconds_first_touch_to_conversion"].clip(lower=0))
    x["log_impressions"] = np.log1p(df["n_impressions"])
    x["log_clicks"] = np.log1p(df["n_clicks"])
    x["log_path_cost"] = np.log1p(df["path_cost"] * 1e4)
    x["campaign_rate"] = df["campaign_id"].map(campaign_rate).fillna(prior)
    return x


def smoothed_campaign_rate(train: pd.DataFrame, k: float = 20.0) -> tuple[pd.Series, float]:
    prior = float(train["is_attributed"].mean())
    g = train.groupby("campaign_id")["is_attributed"].agg(["sum", "count"])
    return (g["sum"] + k * prior) / (g["count"] + k), prior


def best_threshold(secs: pd.Series, y: pd.Series) -> float:
    grid = np.unique(np.quantile(secs, np.linspace(0.02, 0.98, 97)))
    accs = [((secs <= t).astype(int) == y).mean() for t in grid]
    return float(grid[int(np.argmax(accs))])


def evaluate(y: np.ndarray, p: np.ndarray) -> dict:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {
        "auc": round(float(roc_auc_score(y, p)), 4),
        "log_loss": round(float(log_loss(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "accuracy": round(float(((p >= 0.5).astype(int) == y).mean()), 4),
    }


def campaign_error(test: pd.DataFrame, p: np.ndarray, min_conv: int = 50) -> dict:
    """How well predicted credited conversions per campaign match the advertiser's count."""
    t = test.assign(p=p).groupby("campaign_id").agg(actual=("is_attributed", "sum"),
                                                     pred=("p", "sum"), n=("p", "size"))
    t = t[t["n"] >= min_conv]
    ape = (t["pred"] - t["actual"]).abs() / t["actual"].clip(lower=1)
    return {"campaigns": int(len(t)), "median_abs_pct_error": round(float(ape.median()), 4),
            "total_pred": round(float(t["pred"].sum()), 1), "total_actual": int(t["actual"].sum())}


def run(warehouse: Path = WAREHOUSE, out_dir: Path = ROOT / "results") -> dict:
    df = load_conversions(warehouse)
    train = df[df["conversion_day_index"] < TEST_FROM_DAY]
    test = df[df["conversion_day_index"] >= TEST_FROM_DAY]
    rate, prior = smoothed_campaign_rate(train)
    xtr, xte = features(train, rate, prior), features(test, rate, prior)
    ytr, yte = train["is_attributed"].to_numpy(), test["is_attributed"].to_numpy()

    out: dict = {
        "conversions_used": int(len(df)),
        "excluded_multi_campaign_or_user": count_excluded(warehouse),
        "train_conversions": int(len(train)),
        "test_conversions": int(len(test)),
        "test_from_conversion_day": TEST_FROM_DAY,
        "credited_share_train": round(float(ytr.mean()), 4),
        "credited_share_test": round(float(yte.mean()), 4),
    }

    t = best_threshold(train["seconds_last_click_to_conversion"], train["is_attributed"])
    rule_te = (test["seconds_last_click_to_conversion"] <= t).astype(int).to_numpy()
    out["rule"] = {"threshold_seconds": round(t, 1), "threshold_hours": round(t / 3600, 2),
                   "accuracy": round(float((rule_te == yte).mean()), 4),
                   "campaign": campaign_error(test, rule_te.astype(float))}
    # AUC for the rule uses the time itself as a score (shorter gap = more likely credited)
    rule_score = -test["seconds_last_click_to_conversion"]
    out["rule"]["auc"] = round(float(roc_auc_score(yte, rule_score)), 4)

    cols_lr = [c for c in xtr.columns if c != "campaign_rate"]
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    lr.fit(xtr[cols_lr], ytr)
    p_lr = lr.predict_proba(xte[cols_lr])[:, 1]
    out["logistic"] = {**evaluate(yte, p_lr), "campaign": campaign_error(test, p_lr)}

    gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=SEED)
    gb.fit(xtr, ytr)
    p_gb = gb.predict_proba(xte)[:, 1]
    out["gradient_boosting"] = {**evaluate(yte, p_gb), "campaign": campaign_error(test, p_gb)}

    base = np.full_like(p_gb, ytr.mean())
    out["base_rate"] = evaluate(yte, base)

    # paired bootstrap: AUC gain of gradient boosting over the time rule
    rng = np.random.default_rng(SEED)
    score_rule = -test["seconds_last_click_to_conversion"].to_numpy()
    diffs = []
    for _ in range(200):
        i = rng.integers(0, len(yte), len(yte))
        if yte[i].min() == yte[i].max():
            continue
        diffs.append(roc_auc_score(yte[i], p_gb[i]) - roc_auc_score(yte[i], score_rule[i]))
    out["auc_gain_gb_vs_rule"] = {"mean": round(float(np.mean(diffs)), 4),
                                  "ci95": [round(float(np.percentile(diffs, 2.5)), 4),
                                           round(float(np.percentile(diffs, 97.5)), 4)]}

    out_dir.mkdir(exist_ok=True)
    (out_dir / "attribution.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
