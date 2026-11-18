"""API client for NYC Open Data (Socrata SODA API).

Wraps paging, retries and the query so the rest of the code never builds
raw HTTP requests.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import pandas as pd
import requests

from . import config


class OpenDataClient:
    def __init__(self, app_token: str | None = None, session: requests.Session | None = None):
        self.session = session or requests.Session()
        token = app_token or os.getenv("SOCRATA_APP_TOKEN")
        if token:
            # A free app token raises Socrata's rate limits. Optional.
            self.session.headers["X-App-Token"] = token

    def _get(self, params: dict) -> list[dict]:
        """GET one page, retrying on rate limits and server errors."""
        delay = 2
        for attempt in range(config.MAX_RETRIES):
            resp = self.session.get(config.DATASET_URL, params=params, timeout=config.REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < config.MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
        return []  # unreachable, keeps type checkers happy

    def fetch_nypd_requests(self, start: datetime, end: datetime) -> pd.DataFrame:
        """All NYPD-routed 311 requests created in [start, end)."""
        where = (
            "agency = 'NYPD' "
            f"AND created_date >= '{start:%Y-%m-%dT%H:%M:%S}' "
            f"AND created_date < '{end:%Y-%m-%dT%H:%M:%S}'"
        )
        rows: list[dict] = []
        offset = 0
        while True:
            page = self._get({
                "$select": ",".join(config.FIELDS),
                "$where": where,
                "$order": "unique_key",       # stable order so paging never skips rows
                "$limit": config.PAGE_SIZE,
                "$offset": offset,
            })
            rows.extend(page)
            if len(page) < config.PAGE_SIZE:
                break
            offset += config.PAGE_SIZE
        return to_frame(rows)


def to_frame(rows: list[dict]) -> pd.DataFrame:
    """Turn raw API rows into a clean, typed DataFrame."""
    df = pd.DataFrame(rows, columns=config.FIELDS)
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
    df["closed_date"] = pd.to_datetime(df["closed_date"], errors="coerce")
    # "Precinct 72" -> 72. "Unspecified" and blanks become NaN and are dropped.
    df["precinct"] = pd.to_numeric(
        df["police_precinct"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    df = df.dropna(subset=["created_date", "precinct", "complaint_type"])
    df["precinct"] = df["precinct"].astype(int)
    df = df[df["precinct"].isin(config.PRECINCTS)]
    return df.reset_index(drop=True)
