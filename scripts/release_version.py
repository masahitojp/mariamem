"""Read the single packaged version source without importing the runtime API."""

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
_version = runpy.run_path(str(ROOT / "python/mariamem/_version.py"))
PYTHON_VERSION = _version["PYTHON_VERSION"]
GIT_TAG = _version["GIT_TAG"]
SOURCE_ROOT = f"mariamem-{PYTHON_VERSION}"
SOURCE_CANDIDATE = f"{SOURCE_ROOT}-source-candidate.tar.gz"
CORRESPONDING_SOURCE = f"{SOURCE_ROOT}-corresponding-source.tar.gz"


def require_tag(tag):
    if tag != GIT_TAG:
        raise ValueError(f"release tag {tag!r} does not match {GIT_TAG!r}")
