"""Sort NYPD's free-text 311 resolution notes into a few outcome buckets.

Rules are plain keyword checks so anyone can read and audit them.
Order matters: the first matching rule wins.

The rules cover the wording NYPD uses in late 2026 (checked against live data
on 2026-11-18) plus older wording still found in past records. If NYPD changes
its wording, new text falls into "other": check `pgf` output for a large
"other" share and add a rule here.
"""

ACTION_TAKEN = "action_taken"        # summons, arrest, report, fixed by police
CORRECTED = "corrected"              # condition corrected without summons or arrest
REFERRED = "referred"                # handed to another agency
NO_EVIDENCE = "no_evidence"          # no evidence of a violation found
GONE_ON_ARRIVAL = "gone_on_arrival"  # nothing observed when officers arrived
NO_ACCESS = "no_access"              # officers could not get in
NOT_NECESSARY = "not_necessary"      # police action not necessary
NOT_JURISDICTION = "not_jurisdiction"
DUPLICATE = "duplicate"
OTHER = "other"

RULES = [
    ("duplicate", DUPLICATE),
    ("does not fall under the jurisdiction", NOT_JURISDICTION),
    ("condition was corrected", CORRECTED),
    ("issued a summons", ACTION_TAKEN),
    ("made an arrest", ACTION_TAKEN),
    ("report was prepared", ACTION_TAKEN),
    ("took action to fix", ACTION_TAKEN),
    ("vehicle was towed", ACTION_TAKEN),
    ("has been referred to", REFERRED),
    ("unable to gain entry", NO_ACCESS),
    ("upon their arrival", GONE_ON_ARRIVAL),
    ("upon arrival those responsible", GONE_ON_ARRIVAL),
    ("were gone", GONE_ON_ARRIVAL),
    ("no evidence", NO_EVIDENCE),
    ("observed no encampment", NO_EVIDENCE),
    ("condition was not observed", NO_EVIDENCE),
    ("action was not necessary", NOT_NECESSARY),
]

# Outcomes where the complaint closed without the condition being found or fixed.
UNRESOLVED = {NO_EVIDENCE, GONE_ON_ARRIVAL, NO_ACCESS}


def classify(text) -> str:
    if not isinstance(text, str) or not text.strip():
        return OTHER
    t = text.lower()
    for needle, label in RULES:
        if needle in t:
            return label
    return OTHER
