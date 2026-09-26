#!/usr/bin/env python3
"""Summarize the external CI candidate and guard result in GitHub Actions."""
import json
import os
from pathlib import Path

from common import ROOT, digest
from release_version import GIT_TAG, PYTHON_VERSION, SOURCE_CANDIDATE


def main():
    build = ROOT / "build"
    source = build / "release" / SOURCE_CANDIDATE
    native = build / "release/native-candidate/mariamem-native-darwin-arm64.tar.gz"
    wheel_record = ROOT / "tests/evidence/alpha-wheel.json"
    wheel = ROOT / json.loads(wheel_record.read_text())["wheel"] if wheel_record.exists() else None
    acceptance = build / "release/ci-native-acceptance.json"
    ready = build / "release/ci-ready.json"
    rows = ["## Release candidate verification", "",
            f"- Source commit: `{os.environ.get('SOURCE_SHA', 'unavailable')}`",
            f"- Derived tag / Python version: `{GIT_TAG}` / `{PYTHON_VERSION}`"]
    for label, path in (("Native candidate", native), ("Wheel", wheel),
                        ("Corresponding source", source)):
        if path is not None and path.is_file():
            rows.append(f"- {label}: `{path.name}` SHA256 `{digest(path)}`")
        else:
            rows.append(f"- {label}: unavailable")
    result = json.loads(acceptance.read_text()).get("result") if acceptance.exists() else "NOT RUN"
    rows.extend([f"- Clean macOS acceptance: **{result}**",
                 f"- Installed-wheel acceptance step: **{os.environ.get('WHEEL_RESULT', 'NOT RUN')}**",
                 f"- Release guard: **{'READY' if ready.exists() and os.environ.get('GUARD_RESULT') == 'success' else 'NOT READY'}**",
                 "- No tag, release, or package was published.", ""])
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as out:
            out.write("\n".join(rows))
    print("\n".join(rows))


if __name__ == "__main__":
    main()
