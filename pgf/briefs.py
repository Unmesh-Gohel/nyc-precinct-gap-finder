"""Plain-English precinct briefs, written by an LLM from computed numbers only.

Guardrails:
  1. The model only sees aggregate numbers, never raw complaints or addresses.
  2. The prompt forbids guessing causes, naming people or suggesting enforcement.
  3. Every number in the model's answer is checked against the facts we sent.
     If any number is not in the facts, the brief is thrown away and a plain
     template brief is used instead. The dashboard marks which one you got.
"""

from __future__ import annotations

import json
import os
import re

import requests

from . import config

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM = (
    "You write short, neutral service briefs for a city operations dashboard. "
    "Use ONLY the numbers in the facts you are given, written exactly as given. "
    "Do not guess causes. Do not mention people, neighborhoods' demographics, or "
    "enforcement actions. Do not rank or blame. Three sentences, plain words."
)


def facts_for(row: dict, drivers: dict) -> dict:
    return {
        "precinct": row["precinct"],
        "complaints_in_window": row["complaints"],
        "rank_of_77_by_gap_score": row["rank"],
        "time_gap_ratio_vs_city": round(row["time_gap"], 2),
        "outcome_gap_points_vs_city": _r(row["outcome_gap_pp"]),
        "demand_growth_gap_points_vs_city": _r(row["demand_gap_pp"]),
        "top_drivers": drivers,
    }


def _r(x):
    return None if x is None or x != x else round(float(x), 1)


def _numbers(obj) -> set[str]:
    """All numbers that appear anywhere in the facts, as normalized strings."""
    found: set[str] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            found |= _numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= _numbers(v)
    elif isinstance(obj, (int, float)) and obj == obj:
        found.add(_norm(str(obj)))
        found.add(_norm(str(abs(obj))))
    return found


def _norm(s: str) -> str:
    s = s.replace(",", "")
    return s[:-2] if s.endswith(".0") else s


def numbers_are_grounded(text: str, facts: dict) -> bool:
    allowed = _numbers(facts) | {"77", "3"}  # "of 77 precincts", "3 sentences"
    for tok in re.findall(r"\d[\d,]*\.?\d*", text):
        if _norm(tok.rstrip(".")) not in allowed:
            return False
    return True


def template_brief(f: dict) -> str:
    parts = [f"Precinct {f['precinct']} ranks {f['rank_of_77_by_gap_score']} of 77 on the combined gap score, "
             f"based on {f['complaints_in_window']} complaints."]
    parts.append(f"Complaints take {f['time_gap_ratio_vs_city']:.2f}x the city's typical time to close, "
                 "comparing like with like by complaint type.")
    og = f["outcome_gap_points_vs_city"]
    if og is not None:
        side = "above" if og >= 0 else "below"
        parts.append(f"The share closed without a fix is {abs(og)} points {side} the city rate.")
    return " ".join(parts)


def llm_brief(f: dict, api_key: str | None = None, model: str | None = None) -> tuple[str, str]:
    """Returns (brief, source) where source is 'llm' or 'template'."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return template_brief(f), "template"
    try:
        resp = requests.post(
            API_URL,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": model or os.getenv("PGF_MODEL", config.DEFAULT_MODEL),
                "max_tokens": 300,
                "system": SYSTEM,
                "messages": [{"role": "user", "content": "Facts:\n" + json.dumps(f, indent=2)}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = "".join(b.get("text", "") for b in resp.json().get("content", [])).strip()
    except requests.RequestException:
        return template_brief(f), "template"
    if text and numbers_are_grounded(text, f):
        return text, "llm"
    return template_brief(f), "template"
