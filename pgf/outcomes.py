"""Sort NYPD's free-text 311 resolution notes into a few outcome buckets.

Rules are plain keyword checks so anyone can read and audit them.
Order matters: the first matching rule wins.
"""

ACTION_TAKEN = "action_taken"
NO_EVIDENCE = "no_evidence"
GONE_ON_ARRIVAL = "gone_on_arrival"
NOT_NECESSARY = "not_necessary"
DUPLICATE = "duplicate"
OTHER = "other"

RULES = [
    ("duplicate", DUPLICATE),
    ("upon arrival those responsible", GONE_ON_ARRIVAL),
    ("were gone", GONE_ON_ARRIVAL),
    ("observed no evidence", NO_EVIDENCE),
    ("no evidence of the violation", NO_EVIDENCE),
    ("condition was not observed", NO_EVIDENCE),
    ("police action was not necessary", NOT_NECESSARY),
    ("action was not necessary", NOT_NECESSARY),
    ("took action to fix", ACTION_TAKEN),
    ("issued a summons", ACTION_TAKEN),
    ("made an arrest", ACTION_TAKEN),
    ("report was prepared", ACTION_TAKEN),
    ("vehicle was towed", ACTION_TAKEN),
]

# Outcomes where the complaint closed without the condition being fixed.
UNRESOLVED = {NO_EVIDENCE, GONE_ON_ARRIVAL}


def classify(text) -> str:
    if not isinstance(text, str) or not text.strip():
        return OTHER
    t = text.lower()
    for needle, label in RULES:
        if needle in t:
            return label
    return OTHER
