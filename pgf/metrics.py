"""The three gaps, and one score that combines them.

Every gap compares a precinct with the citywide norm FOR THE SAME COMPLAINT
TYPE. That matters: noise complaints and blocked driveways behave very
differently, so a precinct with lots of one type should not look "slow" or
"fast" just because of its mix.

  time gap     median hours to close, precinct vs city            (ratio, 1.0 = same)
  outcome gap  share closed without a fix, precinct vs city       (percentage points)
  demand gap   volume growth vs the prior window, precinct vs city (percentage points)

Positive numbers always mean "worse than the city".
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from . import config
from .outcomes import UNRESOLVED, classify


def prepare(df: pd.DataFrame, window_start: datetime) -> pd.DataFrame:
    """Add derived columns: hours to close, outcome bucket, which window."""
    df = df.copy()
    hours = (df["closed_date"] - df["created_date"]).dt.total_seconds() / 3600
    # Open complaints and bad timestamps (closed before created) get no time.
    df["hours_to_close"] = hours.where(hours >= 0)
    df["outcome"] = df["resolution_description"].map(classify)
    df["unresolved"] = df["outcome"].isin(UNRESOLVED)
    df["window"] = np.where(df["created_date"] >= pd.Timestamp(window_start), "current", "prior")
    return df


def type_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """One row per precinct x complaint type, current window only."""
    cur = df[df["window"] == "current"]
    prior = df[df["window"] == "prior"]

    city_counts = cur.groupby("complaint_type").size()
    keep = city_counts[city_counts >= config.MIN_CITYWIDE].index
    cur = cur[cur["complaint_type"].isin(keep)]
    prior = prior[prior["complaint_type"].isin(keep)]

    city = cur.groupby("complaint_type").agg(
        city_median_hours=("hours_to_close", "median"),
        city_unresolved=("unresolved", "mean"),
        city_n=("unique_key", "size"),
    )
    city["city_prior_n"] = prior.groupby("complaint_type").size()
    city["city_growth"] = city["city_n"] / city["city_prior_n"] - 1

    cell = cur.groupby(["precinct", "complaint_type"]).agg(
        n=("unique_key", "size"),
        median_hours=("hours_to_close", "median"),
        unresolved=("unresolved", "mean"),
    )
    cell["prior_n"] = prior.groupby(["precinct", "complaint_type"]).size()
    cell = cell.reset_index().merge(city.reset_index(), on="complaint_type", how="left")

    cell = cell[cell["n"] >= config.MIN_SAMPLE].copy()
    cell["time_gap"] = cell["median_hours"] / cell["city_median_hours"]
    cell["outcome_gap_pp"] = (cell["unresolved"] - cell["city_unresolved"]) * 100
    growth = cell["n"] / cell["prior_n"] - 1
    # Growth only counts when the prior window had a real sample too.
    growth = growth.where(cell["prior_n"] >= config.MIN_SAMPLE)
    cell["demand_gap_pp"] = (growth - cell["city_growth"]) * 100
    cell["growth"] = growth
    return cell.replace([np.inf, -np.inf], np.nan)


def _weighted(group: pd.DataFrame, col: str) -> float:
    g = group.dropna(subset=[col])
    if g.empty:
        return float("nan")
    return float(np.average(g[col], weights=g["n"]))


def precinct_scores(cells: pd.DataFrame) -> pd.DataFrame:
    """Roll type-level gaps up to one row per precinct, then score and rank."""
    rows = []
    for precinct, g in cells.groupby("precinct"):
        rows.append({
            "precinct": int(precinct),
            "complaints": int(g["n"].sum()),
            "types_compared": int(len(g)),
            # Ratios are averaged on a log scale so 2x slower and 2x faster cancel out.
            "time_gap": float(np.exp(_weighted(g.assign(lt=np.log(g["time_gap"])), "lt"))),
            "outcome_gap_pp": _weighted(g, "outcome_gap_pp"),
            "demand_gap_pp": _weighted(g, "demand_gap_pp"),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out

    def z(s: pd.Series) -> pd.Series:
        sd = s.std(ddof=0)
        return (s - s.mean()) / sd if sd and not np.isnan(sd) else s * 0

    out["time_z"] = z(np.log(out["time_gap"]))
    out["outcome_z"] = z(out["outcome_gap_pp"])
    out["demand_z"] = z(out["demand_gap_pp"])
    # Missing parts count as "at the norm" (0) rather than dropping the precinct.
    out["gap_score"] = out[["time_z", "outcome_z", "demand_z"]].fillna(0).mean(axis=1)
    out = out.sort_values("gap_score", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out


def top_drivers(cells: pd.DataFrame, precinct: int, k: int = 3) -> dict[str, list[dict]]:
    """For one precinct, the complaint types that drive each gap the most."""
    g = cells[cells["precinct"] == precinct]

    def pick(col: str, fmt) -> list[dict]:
        rows = g.dropna(subset=[col]).sort_values(col, ascending=False).head(k)
        return [fmt(r) for _, r in rows.iterrows()]

    return {
        "time": pick("time_gap", lambda r: {
            "type": r["complaint_type"], "n": int(r["n"]),
            "median_hours": round(float(r["median_hours"]), 1),
            "city_median_hours": round(float(r["city_median_hours"]), 1),
            "ratio": round(float(r["time_gap"]), 2)}),
        "outcome": pick("outcome_gap_pp", lambda r: {
            "type": r["complaint_type"], "n": int(r["n"]),
            "unresolved_pct": round(float(r["unresolved"]) * 100, 1),
            "city_unresolved_pct": round(float(r["city_unresolved"]) * 100, 1),
            "gap_pp": round(float(r["outcome_gap_pp"]), 1)}),
        "demand": pick("demand_gap_pp", lambda r: {
            "type": r["complaint_type"], "n": int(r["n"]), "prior_n": int(r["prior_n"]),
            "growth_pct": round(float(r["growth"]) * 100, 1),
            "city_growth_pct": round(float(r["city_growth"]) * 100, 1),
            "gap_pp": round(float(r["demand_gap_pp"]), 1)}),
    }
