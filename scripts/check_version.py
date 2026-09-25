#!/usr/bin/env python3
"""Cheap release-version consistency check; does not build or inspect old artifacts."""

import configparser
from pathlib import Path
import sys

from release_version import ROOT, PYTHON_VERSION, GIT_TAG, require_tag


def check():
    config = configparser.ConfigParser()
    config.read(ROOT / "python/setup.cfg")
    if config.has_option("metadata", "version"):
        raise ValueError("python/setup.cfg must not define a second version")
    sys.path.insert(0, str(ROOT / "python"))
    import mariamem
    if mariamem.__version__ != PYTHON_VERSION:
        raise ValueError("Python package version differs from canonical release version")
    require_tag(GIT_TAG)
    print(f"Release version: Python {PYTHON_VERSION}; Git/Go {GIT_TAG}")


if __name__ == "__main__":
    check()
