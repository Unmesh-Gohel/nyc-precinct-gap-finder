"""Settings for the NYC Precinct Gap Finder."""

# NYC Open Data: 311 Service Requests from 2010 to Present
DATASET_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"

# Only the columns we need. Smaller pulls are faster and keep us away from
# fields we have no reason to touch (addresses, coordinates).
FIELDS = [
    "unique_key",
    "created_date",
    "closed_date",
    "complaint_type",
    "police_precinct",
    "status",
    "resolution_description",
]

PAGE_SIZE = 50_000          # Socrata's max rows per request
REQUEST_TIMEOUT = 60        # seconds
MAX_RETRIES = 4

# A precinct/complaint-type cell needs at least this many complaints
# before we compare it with the city. Small samples make noisy "gaps".
MIN_SAMPLE = 30

# Complaint types with fewer than this many complaints citywide are skipped.
MIN_CITYWIDE = 200

# The 77 NYPD precincts.
PRECINCTS = [
    1, 5, 6, 7, 9, 10, 13, 14, 17, 18, 19, 20, 22, 23, 24, 25, 26, 28, 30, 32,
    33, 34, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 52, 60, 61, 62, 63, 66,
    67, 68, 69, 70, 71, 72, 73, 75, 76, 77, 78, 79, 81, 83, 84, 88, 90, 94, 100,
    101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115,
    120, 121, 122, 123,
]

DEFAULT_MODEL = "claude-sonnet-5-5"
