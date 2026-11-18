# NYC Precinct Gap Finder

Finds where each NYPD precinct's 311 service is out of line with the rest of the city, using public NYC Open Data.

It scores all 77 precincts on three gaps, combines them into one ranked dashboard, and writes a short plain-English brief for the precincts at the top.

| Gap | Question it answers | Unit |
|---|---|---|
| **Time to close** | Do complaints here take longer to close than the city norm? | ratio (1.00x = city norm) |
| **Closed without a fix** | Do complaints here close as "no evidence", "no violation on arrival" or "unable to gain entry" more often? | percentage points vs city |
| **Volume growth** | Is complaint volume here growing faster than the city? | percentage points vs city |

Every gap compares a precinct with the city **for the same complaint type**. A precinct with lots of slow complaint types (like abandoned vehicles) does not look "slow" just because of its mix.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pgf demo          # sample data, works offline
pgf run           # live NYC Open Data, last 30 days vs the 30 before
```

Open `out/dashboard.html`. The run also writes `precinct_scores.csv`, `type_gaps.csv` and `briefs.json`.

Options: `--days 60` changes the window, `--top 10` sets how many briefs, `--no-llm` skips the LLM.

Optional environment variables (see `.env.example`):

- `SOCRATA_APP_TOKEN`: a free NYC Open Data app token, for higher rate limits.
- `ANTHROPIC_API_KEY`: turns on LLM-written briefs. Without it, briefs use a plain template.

## How it works

```
NYC Open Data (311 API)
   └─ client.py     pages through NYPD-routed complaints, retries on rate limits
        └─ metrics.py   hours to close, outcome bucket, window; gaps per precinct x complaint type
             └─ metrics.py   roll up to precinct, z-score each gap, average into one score
                  ├─ briefs.py    LLM brief from numbers only, every number checked
                  └─ report.py    one self-contained HTML dashboard + CSVs
```

- **Fair comparisons.** A precinct/type pair needs at least 30 complaints to count. Complaint types need 200 citywide.
- **Open complaints** and bad timestamps (closed before created) are left out of the time measure.
- **Outcomes** come from simple keyword rules in `outcomes.py` that anyone can read and audit. The rules were checked against every distinct NYPD resolution note in live data (Oct 17 to Nov 15, 2026). If more than 10% of closed complaints match no rule, `pgf` prints a warning, because NYPD has probably changed its wording.
- **Slow pages are normal.** Deep pages of this dataset can take 20 to 60 seconds each. The client waits up to 3 minutes per page and retries timeouts.
- The window ends 2 days ago, so most recent complaints have had time to close.

## LLM guardrails

The LLM never sees raw complaints, only aggregate numbers. The prompt forbids guessing causes, naming people or suggesting enforcement. Then every number in the LLM's answer is checked against the facts it was given. If any number does not match, the brief is thrown away and the template brief is used instead. The dashboard labels which kind of brief you are reading.

## Impact and use

- **Data:** public, aggregate NYC 311 data only. No names. Addresses and coordinates are never downloaded.
- **Purpose:** to show where service patterns differ from the city norm, so people know where to look first.
- **Not for:** explaining causes, judging staff, predicting crime, or deciding enforcement. A gap can come from staffing, geography, call volume or how complaints get filed. Treat a gap as a question, not a finding.

## Tests

```bash
pytest -q
```

29 tests cover the API client (paging, retries, timeouts), every current NYPD outcome wording, outcome rules, the gap math, the brief guardrails (a made-up number gets rejected) and an end-to-end build. The sample data plants three known problem precincts, and the tests check the scoring finds all three. GitHub Actions runs the tests on Python 3.11 to 3.13 and builds the sample dashboard on every push.

## Roadmap

- [ ] Run on live data and publish the first real dashboard
- [ ] FastAPI service: `GET /precincts`, `GET /precincts/{id}`
- [ ] Per-resident demand using census population by precinct
- [ ] Trend view: each precinct's gaps month by month
- [ ] Deploy on AWS (Lambda + S3 + CloudFront) with a nightly refresh
