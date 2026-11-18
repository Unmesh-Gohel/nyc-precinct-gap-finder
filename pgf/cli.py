"""Command line: `pgf run` (live NYC Open Data) or `pgf demo` (sample data)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from . import briefs as B
from .client import OpenDataClient, to_frame
from .metrics import precinct_scores, prepare, top_drivers, type_gaps
from .report import render
from .synthetic import generate


def build(raw_df, window_start, window_end, out_dir: Path, top: int, use_llm: bool, sample: bool) -> dict:
    prepared = prepare(raw_df, window_start)
    cells = type_gaps(prepared)
    scores = precinct_scores(cells)

    out_dir.mkdir(parents=True, exist_ok=True)
    cells.to_csv(out_dir / "type_gaps.csv", index=False)
    scores.to_csv(out_dir / "precinct_scores.csv", index=False)

    brief_rows = []
    for row in scores.head(top).to_dict("records"):
        drivers = top_drivers(cells, row["precinct"])
        facts = B.facts_for(row, drivers)
        text, source = B.llm_brief(facts) if use_llm else (B.template_brief(facts), "template")
        brief_rows.append({"precinct": row["precinct"], "rank": row["rank"], "text": text,
                           "source": source, "drivers": drivers})
    (out_dir / "briefs.json").write_text(json.dumps(brief_rows, indent=2), encoding="utf-8")

    label = f"{window_start:%b %d, %Y} to {window_end - timedelta(days=1):%b %d, %Y}"
    page = render(scores, prepared, brief_rows, label, out_dir, sample)
    return {"dashboard": str(page), "precincts": len(scores), "complaints": int((prepared["window"] == "current").sum())}


def main(argv=None):
    p = argparse.ArgumentParser(prog="pgf", description="NYC Precinct Gap Finder")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "demo"):
        s = sub.add_parser(name)
        s.add_argument("--days", type=int, default=30, help="window length in days (compared with the window before it)")
        s.add_argument("--out", type=Path, default=Path("out"))
        s.add_argument("--top", type=int, default=10, help="how many precinct briefs to write")
        s.add_argument("--no-llm", action="store_true", help="use template briefs only")
    a = p.parse_args(argv)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # End the window 2 days back so most complaints have had time to close.
    end = today - timedelta(days=2)
    start = end - timedelta(days=a.days)

    if a.cmd == "run":
        print(f"Fetching NYPD 311 complaints {start:%Y-%m-%d} to {end:%Y-%m-%d} (plus the prior {a.days} days)...")
        df = OpenDataClient().fetch_nypd_requests(start - timedelta(days=a.days), end)
        sample = False
    else:
        df = to_frame(generate(start, days=a.days))
        sample = True

    print(f"{len(df):,} complaints loaded.")
    result = build(df, start, end, a.out, a.top, not a.no_llm, sample)
    print(f"Scored {result['precincts']} precincts. Dashboard: {result['dashboard']}")


if __name__ == "__main__":
    main()
