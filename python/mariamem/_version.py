"""Canonical mariamem release version and ecosystem-specific spellings."""

MAJOR = 0
MINOR = 1
PATCH = 0
STAGE = ""
SERIAL = 0

_PEP440_STAGE = {"alpha": "a", "beta": "b", "rc": "rc"}
if STAGE not in ("", *_PEP440_STAGE) or any(
    not isinstance(value, int) or value < 0 for value in (MAJOR, MINOR, PATCH)
) or not isinstance(SERIAL, int) or (SERIAL != 0 if STAGE == "" else SERIAL < 1):
    raise ValueError("invalid mariamem release version")

BASE_VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
PYTHON_VERSION = f"{BASE_VERSION}{_PEP440_STAGE[STAGE]}{SERIAL}" if STAGE else BASE_VERSION
GIT_TAG = f"v{BASE_VERSION}-{STAGE}.{SERIAL}" if STAGE else f"v{BASE_VERSION}"
