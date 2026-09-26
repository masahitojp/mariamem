#!/usr/bin/env python3
"""Summarize the external CI candidate and guard result in GitHub Actions."""
import argparse
import json
import runpy
import os
from pathlib import Path

from common import ROOT, digest
from native_target import DARWIN, target_metadata



def publication_rows(root):
    record_path = root / 'build/release/ci-publication.json'
    smoke_path = root / 'build/release/ci-public-smoke.json'
    record = json.loads(record_path.read_text()) if record_path.exists() else {}
    smoke = json.loads(smoke_path.read_text()) if smoke_path.exists() else {}
    rows = ['## Release publication', '',
            f"- Operation: `{os.environ.get('OPERATION')}`",
            f"- Exact source/tag commit: `{os.environ.get('SOURCE_SHA')}`",
            f"- Tag: `{record.get('git_tag', 'unavailable')}`",
            f"- Publication: **{record.get('status', 'NOT RUN')}**",
            f"- Public consumer smoke: **{smoke.get('result', 'NOT RUN')}**"]
    if record.get('release_url'):
        rows.append('- Release: ' + record['release_url'])
    for name, sha in record.get('assets', {}).items():
        rows.append(f'- `{name}` SHA256 `{sha}`')
    failed = [name for name, key in [('restore', 'RESTORE_RESULT'),
              ('publication', 'PUBLISH_RESULT'), ('public smoke', 'SMOKE_RESULT')]
              if os.environ.get(key) == 'failure']
    rows.append('- Failed stage: ' + (failed[0] if failed else 'none'))
    for item in (record, smoke):
        if item.get('failure') or item.get('error'):
            rows.append('- Failure: ' + str(item.get('failure') or item['error']))
            rows.append('- Detail stage: ' + str(item.get('stage', 'unknown')))
    if failed:
        rows.append('- Published tags/assets are never moved, deleted, or replaced on failure. Investigate before starting a corrective release.')
    return rows + ['']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--publication', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.publication:
        text = '\n'.join(publication_rows(root))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
                out.write(text)
        print(text)
        return
    version = runpy.run_path(str(root / 'python/mariamem/_version.py'))
    build = root / "build"
    source = build / "release" / f"mariamem-{version['PYTHON_VERSION']}-source-candidate.tar.gz"
    platform = os.environ.get("RELEASE_PLATFORM", DARWIN)
    native = build / "release/native-candidate" / (target_metadata(platform)["bundle_name"] + ".tar.gz")
    wheel_record = root / "tests/evidence/alpha-wheel.json"
    wheel = root / json.loads(wheel_record.read_text())["wheel"] if wheel_record.exists() else None
    acceptance = build / "release/ci-native-acceptance.json"
    ready = build / "release/ci-ready.json"
    rows = ["## Release candidate verification", "",
            f"- Mode: `{os.environ.get('CI_MODE', 'full')}`",
            f"- Source commit: `{os.environ.get('SOURCE_SHA', 'unavailable')}`",
            f"- Derived tag / Python version: `{version['GIT_TAG']}` / `{version['PYTHON_VERSION']}`"]
    for label, path in (("Native candidate", native), ("Wheel", wheel),
                        ("Corresponding source", source)):
        if path is not None and path.is_file():
            rows.append(f"- {label}: `{path.name}` SHA256 `{digest(path)}`")
        else:
            rows.append(f"- {label}: unavailable")
    reuse_path = build / 'release/ci-reuse.json'
    if reuse_path.exists():
        reuse = json.loads(reuse_path.read_text())
        for key in ('candidate_artifact', 'evidence_artifact'):
            if key in reuse:
                rows.append(f"- {key}: `{json.dumps(reuse[key], sort_keys=True)}`")
        rows.append(f"- Handoff SHA256: `{reuse['handoff_sha256']}`")
    elif os.environ.get('CI_MODE') != 'full':
        rows.append(f"- Requested candidate/evidence runs: `{os.environ.get('CANDIDATE_RUN')}` / "
                    f"`{os.environ.get('EVIDENCE_RUN') or os.environ.get('CANDIDATE_RUN')}`")
    stages = [('restore', 'RESTORE_RESULT'), ('native acceptance', 'NATIVE_RESULT'),
              ('wheel acceptance', 'WHEEL_RESULT'), ('guard', 'GUARD_RESULT')]
    failed = [name for name, key in stages if os.environ.get(key) == 'failure']
    rows.append('- Failed stage: ' + (failed[0] if failed else 'none'))
    restore_log = build / 'release/ci-restore.log'
    if failed and failed[0] == 'restore' and restore_log.exists():
        reason = next((line for line in restore_log.read_text().splitlines()
                       if 'CI reuse FAILED' in line), None)
        if reason:
            rows.append('- Restore reason: ' + reason)
    guard_log = build / 'release/ci-guard.log'
    if failed and guard_log.exists():
        lines = guard_log.read_text().splitlines()
        reason = next((lines[i + 1] for i, line in enumerate(lines[:-1])
                       if 'Release candidate: NOT READY' in line), None)
        if reason:
            rows.append('- Guard reason: ' + reason)
    result = json.loads(acceptance.read_text()).get("result") if acceptance.exists() else "NOT RUN"
    rows.extend([f"- Clean {platform} acceptance: **{result}**",
                 f"- Installed-wheel acceptance step: **{os.environ.get('WHEEL_RESULT', 'NOT RUN')}** (reused in guard-only mode)",
                 f"- Release guard: **{'READY' if ready.exists() and os.environ.get('GUARD_RESULT') == 'success' else 'NOT READY'}**",
                 "- Verification stage does not publish tags, releases, or packages.", ""])
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as out:
            out.write("\n".join(rows))
    print("\n".join(rows))


if __name__ == "__main__":
    main()
