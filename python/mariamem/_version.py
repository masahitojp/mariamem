"""Canonical mariamem release version and ecosystem-specific spellings."""

MAJOR = 0
MINOR = 1
PATCH = 0
STAGE = "alpha"
SERIAL = 4

_PEP440_STAGE = {"alpha": "a", "beta": "b", "rc": "rc"}
if STAGE not in _PEP440_STAGE or any(
    not isinstance(value, int) or value < 0 for value in (MAJOR, MINOR, PATCH)
) or not isinstance(SERIAL, int) or SERIAL < 1:
    raise ValueError("invalid mariamem release version")

BASE_VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
PYTHON_VERSION = f"{BASE_VERSION}{_PEP440_STAGE[STAGE]}{SERIAL}"
GIT_TAG = f"v{BASE_VERSION}-{STAGE}.{SERIAL}"
