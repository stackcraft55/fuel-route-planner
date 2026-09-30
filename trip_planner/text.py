import re

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
STATE_BY_NAME = {name.lower(): code for code, name in US_STATES.items()}

_ABBREVIATIONS = [
    (re.compile(r"\bst\.?(?=\s)"), "saint"),
    (re.compile(r"\bste\.?(?=\s)"), "sainte"),
    (re.compile(r"\bft\.?(?=\s)"), "fort"),
    (re.compile(r"\bmt\.?(?=\s)"), "mount"),
]
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def city_key(name):
    # "St. Louis", "Saint Louis", "ST LOUIS" -> "saintlouis"
    value = name.lower().strip()
    for pattern, replacement in _ABBREVIATIONS:
        value = pattern.sub(replacement, value)
    return _NON_ALNUM.sub("", value)


def parse_state(value):
    value = value.strip().rstrip(".")
    if value.upper() in US_STATES:
        return value.upper()
    return STATE_BY_NAME.get(value.lower())
