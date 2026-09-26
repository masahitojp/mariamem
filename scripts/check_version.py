#!/usr/bin/env python3
"""Cheap release-version consistency check; does not build or inspect old artifacts."""

import configparser
import re
import runpy
from pathlib import Path
import sys

from release_version import ROOT, PYTHON_VERSION, GIT_TAG, require_tag


# Only release-sensitive usage docs are checked. Historical release notes,
# provenance/evidence, benchmark records, and project history are not version inputs.
DOCS = ("README.md", "docs/go.md", "docs/python.md", "docs/releasing.md")
TAG = r"v\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?"
PYTHON = r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?"


def check_release_docs(root=ROOT):
    root = Path(root)
    version = runpy.run_path(str(root / "python/mariamem/_version.py"))
    expected = {"tag": version["GIT_TAG"], "python": version["PYTHON_VERSION"]}
    rules = (
        ("go get", re.compile(r"go get github\.com/masahitojp/mariamem@([^\s`]+)"), "tag"),
        ("gh release download", re.compile(r"gh release download (v[^\s`]+)"), "tag"),
        ("wheel filename", re.compile(r"mariamem-([0-9][^\s`'\"/]+?)-py3-none-[\w.]+\.whl"), "python"),
    )
    for name in DOCS:
        text = (root / name).read_text()
        # Restrict prose to the introduction for guides/release instructions;
        # their later sections contain pinned dependencies and historical findings.
        intro = text if name == "README.md" else text.split("\n## ", 1)[0]
        literals = [("current tag text", re.findall(r"(?<![\w.])(" + TAG + r")(?![\w.-])", intro), "tag"),
                    ("current Python text", (re.findall(r"`(" + PYTHON + r")`", intro)
                     + re.findall(r"(?<![\w.])(\d+\.\d+\.\d+(?:a|b|rc)\d+)(?![\w.-])", intro)), "python")]
        matches = [(label, [value for value in pattern.findall(text)
                                  if value not in {"<published-tag>", "<version-or-commit>", "<version>"}], kind)
                              for label, pattern, kind in rules] + literals
        for label, values, kind in matches:
            for actual in values:
                if actual != expected[kind]:
                    raise ValueError(f"{name}: {label} uses {actual}, expected {expected[kind]} "
                                     "from python/mariamem/_version.py")
        counts = {label: len(values) for label, values, kind in matches}
        required = {
            "README.md": ("current tag text", "current Python text", "go get", "gh release download", "wheel filename"),
            "docs/go.md": ("current tag text", "go get", "gh release download"),
            "docs/python.md": ("current Python text",),
            "docs/releasing.md": ("current tag text", "current Python text"),
        }[name]
        for label in required:
            if not counts[label]:
                raise ValueError(f"{name}: missing release-facing {label}")
    return expected


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
    check_release_docs()
    print(f"Release version: Python {PYTHON_VERSION}; Git/Go {GIT_TAG}")


if __name__ == "__main__":
    check()
