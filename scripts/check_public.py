#!/usr/bin/env python3
"""Check the explicitly selected public source files (not local build outputs)."""
import json
import os
from pathlib import Path
import re
from common import ROOT, digest

TOP_FILES = {".gitignore", ".gitattributes", "README.md", "CONTRIBUTING.md", "LICENSE", "NOTICE",
             "THIRD_PARTY_LICENSES", "go.mod", "go.sum", "mariamem.go", "mariamem_test.go",
             "connection.go", "errors.go", "snapshot.go"}
TOP_DIRS = {"cmd", "internal", "python", "guest", "scripts", "tests", "docs", "licenses", "release", ".github", "benchmarks"}
EXCLUDED = {"__pycache__", ".pytest_cache", "_native"}
# Repository guidance is public on GitHub but is not part of corresponding source.
REPOSITORY_ONLY_FILES = {"AGENTS.md"}


def public_files(root=None):
    root = ROOT if root is None else Path(root)
    found = []
    for directory, dirs, files in os.walk(root):
        base = Path(directory)
        for name in list(dirs):
            path = base / name
            rel = path.relative_to(root)
            ignored = (name in EXCLUDED or name.endswith(".egg-info") or
                       rel.parts in ((".git",), ("build",), (".venv",), ("python", "build"),
                                     ("tests", "runs"), ("tests", "evidence"), ("benchmarks", "results")))
            if ignored:
                dirs.remove(name)
            elif path.is_symlink():
                raise ValueError(f"symlink in publication set: {rel}")
        for name in files:
            path = base / name
            rel = path.relative_to(root)
            if name == ".DS_Store" or path.suffix == ".pyc":
                continue
            if rel.as_posix() in REPOSITORY_ONLY_FILES:
                continue
            if rel.parts[0] not in TOP_DIRS and rel.as_posix() not in TOP_FILES:
                raise ValueError(f"unexpected file outside publication allowlist: {rel}")
            if path.is_symlink():
                raise ValueError(f"symlink in publication set: {rel}")
            if path.suffix in (".pyc", ".wasm", ".wasmu", ".whl", ".zip", ".gz", ".log"):
                raise ValueError(f"generated/binary file in publication set: {rel}")
            found.append(path)
    return sorted(found)


def check(root=None):
    root = ROOT if root is None else Path(root)
    errors = []
    paths = public_files(root)
    for path in paths:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            errors.append(f"non-text file: {rel}")
            continue
        # Generic checks avoid embedding the developer's personal path in this tool.
        patterns = (r"/Users/[^\s/]+/", r"/home/[^\s/]+/", r"(?i)-----BEGIN .*PRIVATE KEY-----",
                    r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")
        if rel != "scripts/check_public.py" and any(re.search(pattern, text) for pattern in patterns):
            errors.append(f"local path or credential-like content: {rel}")
        if rel != "scripts/check_public.py" and re.search(r"(?:investigation|experiments)/", text):
            errors.append(f"reference to non-product workspace: {rel}")
    if errors:
        raise ValueError("\n".join(errors))
    return {"passed": True, "files": {p.relative_to(root).as_posix(): digest(p) for p in paths}}


if __name__ == "__main__":
    result = check()
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/public-source-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Public source check passed: {len(result['files'])} files")
