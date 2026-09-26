#!/usr/bin/env python3
"""Aggregate existing platform guards; restore/stage exact bytes, never build or accept."""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tarfile

from check_ci_release import check_candidate, require
from check_public import check as check_public, public_files
from common import ROOT, digest
from native_target import DARWIN, UBUNTU, target_metadata

PLATFORMS = (DARWIN, UBUNTU)


def platform_root(root, platform):
    require(platform in PLATFORMS, 'unsupported release platform')
    return root / 'build/platforms' / platform


def materialize_source(root, platform):
    destination = platform_root(root, platform)
    require(not destination.exists(), 'platform checkout already exists')
    for source in public_files(root):
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return destination


def source_name(version, platform):
    return f'mariamem-{version}-{platform}-corresponding-source.tar.gz'


def expected_names(version):
    result = set()
    for platform in PLATFORMS:
        target = target_metadata(platform)
        result.update({target['bundle_name'] + '.tar.gz',
                       f"mariamem-{version}-py3-none-{target['wheel_platform']}.whl",
                       source_name(version, platform)})
    return result


def aggregate_records(records, commit):
    require(set(records) == set(PLATFORMS), 'all supported platforms are required')
    first = records[PLATFORMS[0]]
    assets = {}
    for platform, record in records.items():
        require(record.get('result') == 'READY' and record.get('source_commit') == commit,
                platform + ': platform not READY for exact source')
        for key in ('git_tag', 'python_version'):
            require(record[key] == first[key], 'platform version mismatch: ' + key)
        for key in ('wasm_sha256', 'prepared_source_sha256', 'toolchain_provenance_sha256', 'inputs_lock_sha256'):
            require(record['guest_source_provenance'][key] == first['guest_source_provenance'][key],
                    'common guest identity differs: ' + key)
        target = target_metadata(platform)
        version = record['python_version']
        source = f'mariamem-{version}-corresponding-source.tar.gz'
        require(set(record['assets']) == {target['bundle_name'] + '.tar.gz',
                f"mariamem-{version}-py3-none-{target['wheel_platform']}.whl", source},
                platform + ': platform asset set differs')
        for name, value in record['assets'].items():
            name = source_name(version, platform) if name == source else name
            require(name not in assets, 'duplicate release asset')
            assets[name] = value
    require(set(assets) == expected_names(first['python_version']), 'release asset set incomplete')
    return {'version': 2, 'result': 'READY', 'source_commit': commit,
            'git_tag': first['git_tag'], 'python_version': first['python_version'],
            'assets': assets, 'platforms': records,
            'common_guest_wasm_sha256': first['guest_source_provenance']['wasm_sha256']}


def check_aggregate(root, commit):
    if (root / ".git").exists():
        checkout_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        require(checkout_sha == commit, "aggregate checkout is not exact candidate")
    source_files = check_public(root)['files']
    records = {}
    for platform in PLATFORMS:
        checkout = platform_root(root, platform)
        require(check_public(checkout)['files'] == source_files,
                platform + ': source checkout differs from exact candidate')
        records[platform] = check_candidate(commit, checkout / 'build/release/ci-native-acceptance.json', checkout)
    return aggregate_records(records, commit)


def stage(root, ready):
    output = root / 'build/release'
    staging = output / 'publish'
    staging.mkdir(parents=True, exist_ok=True)
    require(not set(p.name for p in staging.iterdir()) - (set(ready['assets']) | {'SHA256SUMS'}),
            'unexpected staged release asset')
    for platform in PLATFORMS:
        checkout = platform_root(root, platform)
        target = target_metadata(platform)
        native = target['bundle_name'] + '.tar.gz'
        wheel_record = json.loads((checkout / 'tests/evidence/alpha-wheel.json').read_text())
        wheel = checkout / wheel_record['wheel']
        source = json.loads((checkout / 'build/release/source-manifest.json').read_text())
        paths = {native: checkout / 'build/release/native-candidate' / native,
                 wheel.name: wheel,
                 source_name(ready['python_version'], platform): checkout / 'build/release' / source['file']}
        for name, path in paths.items():
            require(digest(path) == ready['assets'][name], 'staging input hash differs')
            shutil.copyfile(path, staging / name)
            require(digest(staging / name) == ready['assets'][name], 'staged bytes differ')
    sums = ''.join(f'{sha}  {name}\n' for name, sha in sorted(ready['assets'].items()))
    (output / 'SHA256SUMS').write_text(sums)
    (staging / 'SHA256SUMS').write_text(sums)
    (output / 'ci-ready.json').write_text(json.dumps(ready, indent=2, sort_keys=True) + '\n')


def handoff(root, platform, output):
    manifest = json.loads((root / 'build/guest-aot/manifest.json').read_text())
    require(manifest['platform'] == platform, 'handoff platform differs')
    source = json.loads((root / 'build/release/source-manifest.json').read_text())
    wheel = json.loads((root / 'tests/evidence/alpha-wheel.json').read_text())
    paths = ['build/guest-wasm', 'build/guest-aot',
             'build/release/native-candidate/' + target_metadata(platform)['bundle_name'] + '.tar.gz',
             'build/release/native-candidate/native-candidate.json',
             'build/release/' + source['file'], 'build/release/source-manifest.json',
             'build/source-candidate-check.json', wheel['wheel'], 'tests/evidence/alpha-wheel.json']
    with tarfile.open(output, 'w') as archive:
        for name in paths:
            archive.add(root / name, arcname=name)
    output.with_suffix('.sha256').write_text(digest(output) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('handoff', 'restore', 'guard'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--candidate-sha')
    parser.add_argument('--candidate-run')
    parser.add_argument('--evidence-run')
    parser.add_argument('--platform', choices=PLATFORMS)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == 'handoff':
            require(args.platform and args.output, 'handoff requires platform/output')
            handoff(root, args.platform, args.output)
        elif args.command == 'restore':
            require(args.candidate_run and args.evidence_run and args.candidate_sha, 'restore requires exact candidate and evidence runs')
            for platform in PLATFORMS:
                checkout = materialize_source(root, platform)
                subprocess.run([sys.executable, str(ROOT / 'scripts/ci_release_reuse.py'),
                                '--mode', 'guard-only', '--platform', platform, '--root', str(checkout),
                                '--candidate-sha', args.candidate_sha, '--candidate-run', args.candidate_run,
                                '--evidence-run', args.evidence_run], check=True)
        else:
            result = check_aggregate(root, args.candidate_sha)
            stage(root, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            print('Aggregate release candidate: READY (all supported platforms)')
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        print('Aggregate release candidate: NOT READY\n- ' + str(exc))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
