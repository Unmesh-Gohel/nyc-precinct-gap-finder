from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from pgf import briefs, config, outcomes
from pgf.client import OpenDataClient, to_frame
from pgf.cli import build
from pgf.metrics import precinct_scores, prepare, type_gaps
from pgf.synthetic import GROWING, SLOW, UNRESOLVED, generate

START = datetime(2026, 10, 1)


@pytest.fixture(scope="module")
def scored():
    df = to_frame(generate(START, days=30))
    prepared = prepare(df, START)
    cells = type_gaps(prepared)
    return prepared, cells, precinct_scores(cells)


# --- outcomes ---------------------------------------------------------------

@pytest.mark.parametrize("text,label", [
    ("The Police Department responded to the complaint and took action to fix the condition.", outcomes.ACTION_TAKEN),
    ("The Police Department responded but observed no evidence of the violation at the time.", outcomes.NO_EVIDENCE),
    ("The Police Department responded and upon arrival those responsible for the condition were gone.", outcomes.GONE_ON_ARRIVAL),
    ("The Police Department issued a summons in response to the complaint.", outcomes.ACTION_TAKEN),
    (None, outcomes.OTHER),
    ("", outcomes.OTHER),
])
def test_classify(text, label):
    assert outcomes.classify(text) == label


# --- client -----------------------------------------------------------------

def test_to_frame_parses_precinct_and_drops_unspecified():
    rows = [
        {"unique_key": "1", "created_date": "2026-10-01T10:00:00.000", "closed_date": "2026-10-01T12:00:00.000",
         "complaint_type": "Illegal Parking", "police_precinct": "Precinct 72", "status": "Closed", "resolution_description": "x"},
        {"unique_key": "2", "created_date": "2026-10-01T10:00:00.000", "closed_date": None,
         "complaint_type": "Illegal Parking", "police_precinct": "Unspecified", "status": "Open", "resolution_description": None},
    ]
    df = to_frame(rows)
    assert list(df["precinct"]) == [72]


def test_client_pages_until_short_page(monkeypatch):
    monkeypatch.setattr(config, "PAGE_SIZE", 2)
    row = {"unique_key": "1", "created_date": "2026-10-01T10:00:00.000", "closed_date": None,
           "complaint_type": "Drinking", "police_precinct": "Precinct 1", "status": "Open", "resolution_description": None}
    pages = [[row, row], [row, row], [row]]
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [MagicMock(status_code=200, json=MagicMock(return_value=p)) for p in pages]
    df = OpenDataClient(session=session).fetch_nypd_requests(START, START + timedelta(days=1))
    assert len(df) == 5
    assert session.get.call_count == 3
    assert session.get.call_args_list[1].kwargs["params"]["$offset"] == 2


def test_client_retries_on_429(monkeypatch):
    monkeypatch.setattr("pgf.client.time.sleep", lambda s: None)
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [MagicMock(status_code=429), MagicMock(status_code=200, json=MagicMock(return_value=[]))]
    OpenDataClient(session=session).fetch_nypd_requests(START, START + timedelta(days=1))
    assert session.get.call_count == 2


# --- metrics ----------------------------------------------------------------

def test_open_and_negative_durations_have_no_time():
    df = pd.DataFrame({
        "unique_key": ["1", "2", "3"],
        "created_date": pd.to_datetime(["2026-10-02 10:00"] * 3),
        "closed_date": pd.to_datetime(["2026-10-02 12:00", None, "2026-10-02 09:00"]),
        "complaint_type": ["Drinking"] * 3, "police_precinct": ["Precinct 1"] * 3,
        "status": ["Closed"] * 3, "resolution_description": [None] * 3, "precinct": [1] * 3,
    })
    out = prepare(df, START)
    assert out["hours_to_close"].tolist()[0] == 2.0
    assert out["hours_to_close"].isna().tolist()[1:] == [True, True]


def test_all_precincts_scored(scored):
    _, _, scores = scored
    assert len(scores) == len(config.PRECINCTS)
    assert scores["rank"].tolist() == list(range(1, len(scores) + 1))


def test_finds_planted_gaps(scored):
    _, _, scores = scored
    s = scores.set_index("precinct")
    assert s["time_gap"].idxmax() == SLOW
    assert s["outcome_gap_pp"].idxmax() == UNRESOLVED
    assert s["demand_gap_pp"].idxmax() == GROWING
    assert set(scores.head(5)["precinct"]) >= {SLOW, UNRESOLVED, GROWING}


def test_small_cells_are_skipped(scored):
    _, cells, _ = scored
    assert (cells["n"] >= config.MIN_SAMPLE).all()


# --- briefs -----------------------------------------------------------------

FACTS = {"precinct": 75, "rank_of_77_by_gap_score": 1, "complaints_in_window": 812,
         "time_gap_ratio_vs_city": 2.61, "outcome_gap_points_vs_city": -1.4, "demand_growth_gap_points_vs_city": 3.2,
         "top_drivers": {}}


def test_grounded_brief_passes():
    assert briefs.numbers_are_grounded("Precinct 75 ranks 1 of 77. Closing takes 2.61x the city time.", FACTS)


def test_made_up_number_is_rejected():
    assert not briefs.numbers_are_grounded("Precinct 75 is 40% slower than last year.", FACTS)


def test_no_api_key_falls_back_to_template(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text, source = briefs.llm_brief(FACTS)
    assert source == "template" and "Precinct 75" in text


def test_hallucinated_llm_output_falls_back(monkeypatch):
    fake = MagicMock()
    fake.json.return_value = {"content": [{"type": "text", "text": "Precinct 75 has 9,999 open cases."}]}
    fake.raise_for_status.return_value = None
    monkeypatch.setattr(briefs.requests, "post", lambda *a, **k: fake)
    text, source = briefs.llm_brief(FACTS, api_key="test")
    assert source == "template" and "9,999" not in text


# --- end to end -------------------------------------------------------------

def test_build_writes_outputs(tmp_path):
    df = to_frame(generate(START, days=30))
    result = build(df, START, START + timedelta(days=30), tmp_path, top=5, use_llm=False, sample=True)
    for f in ("dashboard.html", "precinct_scores.csv", "type_gaps.csv", "briefs.json"):
        assert (tmp_path / f).exists()
    html = (tmp_path / "dashboard.html").read_text()
    assert "Sample data" in html and "&#34;" not in html.split("const rows =")[1][:50]
    assert result["precincts"] == len(config.PRECINCTS)
