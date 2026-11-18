"""Realistic SAMPLE data in the exact shape the 311 API returns.

Used for tests and for the demo dashboard when you are offline. Three
precincts get planted gaps so tests can check the scoring finds them:
  75  -> slow to close       (time gap)
  40  -> many closed with no fix (outcome gap)
  110 -> fast-growing volume (demand gap)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from .config import PRECINCTS

TYPES = {  # complaint type: (share of volume, typical hours to close)
    "Illegal Parking": (0.32, 3.0),
    "Noise - Residential": (0.25, 2.0),
    "Blocked Driveway": (0.14, 3.5),
    "Noise - Street/Sidewalk": (0.09, 2.0),
    "Noise - Commercial": (0.06, 2.5),
    "Noise - Vehicle": (0.05, 2.0),
    "Abandoned Vehicle": (0.04, 40.0),
    "Non-Emergency Police Matter": (0.03, 5.0),
    "Drinking": (0.02, 2.0),
}

_NYPD = "The New York City Police Department responded to the complaint and "
RESOLUTIONS = {  # current NYPD wording, as seen in live data on 2026-11-18
    "action": _NYPD + "their investigation determined that a violation of law occurred. Police issued a summons in response to the complaint.",
    "no_evidence": _NYPD + "with the information available observed no evidence of a criminal violation at that time.",
    "gone": _NYPD + "observed no criminal violation upon their arrival.",
    "not_necessary": _NYPD + "their investigation determined that police action was not necessary.",
    "duplicate": "The Police Department responded to the complaint and found this was a duplicate of an earlier complaint.",
}

SLOW, UNRESOLVED, GROWING = 75, 40, 110


def generate(window_start: datetime, days: int = 30, per_day: int = 1200, seed: int = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    types = list(TYPES)
    shares = np.array([TYPES[t][0] for t in types])
    shares = shares / shares.sum()
    weights = rng.uniform(0.5, 1.5, len(PRECINCTS))
    rows = []
    key = 60_000_000
    start = window_start - timedelta(days=days)
    for d in range(days * 2):
        current = d >= days
        day = start + timedelta(days=d)
        w = weights.copy()
        if current:
            w[PRECINCTS.index(GROWING)] *= 1.8
        w = w / w.sum()
        n = rng.poisson(per_day)
        precs = rng.choice(PRECINCTS, size=n, p=w)
        tps = rng.choice(types, size=n, p=shares)
        for p, t in zip(precs, tps):
            created = day + timedelta(seconds=int(rng.integers(0, 86400)))
            base = TYPES[t][1] * (2.6 if p == SLOW else rng.uniform(0.85, 1.15))
            hours = float(rng.lognormal(np.log(base), 0.6))
            p_unres = 0.62 if p == UNRESOLVED else 0.35
            r = rng.random()
            if r < p_unres:
                res = "no_evidence" if rng.random() < 0.6 else "gone"
            elif r < p_unres + 0.08:
                res = "not_necessary"
            elif r < p_unres + 0.10:
                res = "duplicate"
            else:
                res = "action"
            still_open = rng.random() < 0.01
            key += 1
            rows.append({
                "unique_key": str(key),
                "created_date": created.strftime("%Y-%m-%dT%H:%M:%S.000"),
                "closed_date": None if still_open else (created + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000"),
                "complaint_type": t,
                "police_precinct": f"Precinct {p}",
                "status": "In Progress" if still_open else "Closed",
                "resolution_description": None if still_open else RESOLUTIONS[res],
            })
    # A few rows with no precinct, as in the real data.
    rows.append({**rows[0], "unique_key": "1", "police_precinct": "Unspecified"})
    return rows
