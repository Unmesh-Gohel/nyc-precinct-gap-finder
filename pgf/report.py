"""Write the dashboard (one self-contained HTML file) and CSV outputs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config

TEMPLATES = Path(__file__).parent / "templates"


def _clean(v):
    if isinstance(v, float) and v != v:
        return None
    return v


def render(scores: pd.DataFrame, prepared: pd.DataFrame, briefs: list[dict], window_label: str,
           out_dir: Path, sample: bool) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cur = prepared[prepared["window"] == "current"]
    cols = ["rank", "precinct", "gap_score", "time_gap", "outcome_gap_pp", "demand_gap_pp",
            "time_z", "outcome_z", "demand_z", "complaints"]
    rows = [{k: _clean(v) for k, v in r.items()} for r in scores[cols].to_dict("records")]

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    html = env.get_template("dashboard.html.j2").render(
        rows_json=json.dumps(rows),
        precincts=rows,
        briefs=briefs,
        total=int(len(cur)),
        city_median=round(float(cur["hours_to_close"].median()), 1),
        city_unresolved=round(float(cur["unresolved"].mean()) * 100, 1),
        window_label=window_label,
        built=datetime.now().strftime("%b %d, %Y %H:%M"),
        sample=sample,
        min_sample=config.MIN_SAMPLE,
    )
    path = out_dir / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    return path
