#!/usr/bin/env python3
"""Verify published bytes and consume the public tag; never modify a release."""

if __name__ == "__main__":
    raise SystemExit("Retired Wasmer reference tool; reproduce with its pinned historical tag. Current generated-Go build/release uses docs/development.md.")

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from common import ROOT, digest
from consumer_module import MODULE
from release_consumer_smoke import run as run_consumers, STEPS, verify_go, verify_python
from native_target import DARWIN, UBUNTU, target_metadata
from ci_release_platforms import expected_names, PLATFORMS


def require(condition, message):
    if not condition:
        raise ValueError(message)


from published_assets import verify_downloads


def verify_consumer(evidence, commit, tag, native_hash, wheel_hash, lock_hash):
    require(evidence.get('result') == 'PASS' and evidence.get('mode') == 'published', 'public consumers failed')
    require(evidence.get('source_sha') == commit and evidence.get('git_tag') == tag,
            'public consumer requested another source/tag')
    resolved = evidence.get('module_resolved', {})
    require(resolved.get('Version') == tag and resolved.get('Origin', {}).get('Hash') == commit,
            'public Go tag resolved another commit/version')
    require(evidence.get('native_sha256') == native_hash and evidence.get('wheel_sha256') == wheel_hash,
            'public consumers used another native archive/wheel')
    require(set(evidence.get('steps', {})) == set(STEPS)
            and all(value == 'PASS' for value in evidence['steps'].values()),
            'public consumer acceptance steps incomplete')
    verify_go(evidence.get('go', {}), tag, evidence['python_version'], evidence['target'], native_hash, lock_hash)
    verify_python(evidence.get('python', {}), evidence['python_version'], wheel_hash)


def smoke(root, repository, publication_path, output, platform=DARWIN):
    root = Path(root).resolve()
    report = {'schema_version': 1, 'result': 'FAIL', 'started_at': datetime.now(timezone.utc).isoformat(),
              'stage': 'publication_identity', 'nothing_modified': True}
    output.parent.mkdir(parents=True, exist_ok=True)
    log = output.with_suffix('.log')
    def execute(argv, public_consumer=False):
        env = dict(os.environ)
        if public_consumer:
            env.pop("GH_TOKEN", None)
            env.pop("GITHUB_TOKEN", None)
        result = subprocess.run(argv, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with log.open('a') as stream:
            stream.write(json.dumps(argv) + '\n' + result.stdout + result.stderr + '\n')
        require(result.returncode == 0, 'command failed; see ' + str(log))
    try:
        publication = json.loads(publication_path.read_text())
        commit, tag, assets = publication['source_commit'], publication['git_tag'], publication['assets']
        require(publication.get('status') == 'PUBLISHED', 'publication did not complete')
        require(publication.get('repository') == repository, 'publication repository differs')
        require(re.fullmatch('[0-9a-f]{40}', commit) is not None, 'publication source SHA invalid')
        require(re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta|rc)\.[0-9]+)?', tag) is not None,
                'publication tag invalid')
        if publication.get('version') == 2:
            require(set(publication.get('platforms', {})) == set(PLATFORMS), 'publication platform set incomplete')
            require(set(assets) == expected_names(publication['python_version']) | {'SHA256SUMS'}, 'publication asset set incomplete')
        else:
            require(len(assets) == 4 and 'SHA256SUMS' in assets
                and 'mariamem-native-darwin-arm64.tar.gz' in assets
                and sum(n.endswith('.whl') for n in assets) == 1
                and sum(n.endswith('-corresponding-source.tar.gz') for n in assets) == 1,
                'publication asset set incomplete')
        require(all(Path(n).name == n and re.fullmatch('[0-9a-f]{64}', h) for n, h in assets.items()),
                'publication asset identity invalid')
        report.update(source_commit=commit, git_tag=tag, repository=repository, assets=assets)
        with tempfile.TemporaryDirectory(prefix='mariamem-public-smoke-') as temporary:
            work = Path(temporary).resolve()
            require(work != root and root not in work.parents, 'public consumer temporary directory is inside checkout')
            downloaded = work / 'published'
            downloaded.mkdir()
            report['stage'] = 'published_download'
            execute(['gh', 'release', 'download', tag, '--repo', repository, '--dir', str(downloaded)])
            report['stage'] = 'published_hashes'
            report['downloaded_hashes'] = verify_downloads(downloaded, assets)
            report['stage'] = 'public_clean_consumers'
            consumer_path = work / 'consumer.json'
            native = target_metadata(platform)['bundle_name'] + '.tar.gz'
            wheels = [name for name in assets if name.endswith('-' + target_metadata(platform)['wheel_platform'] + '.whl')]
            require(len(wheels) == 1, 'published platform wheel missing/ambiguous')
            wheel = wheels[0]
            try:
                run_consumers(root, commit, downloaded / native, downloaded / wheel, consumer_path,
                              mode='published', tag=tag)
            finally:
                if consumer_path.exists():
                    report['consumer'] = json.loads(consumer_path.read_text())
                if consumer_path.with_suffix('.log').exists():
                    output.with_name(output.stem + '-consumer.log').write_text(consumer_path.with_suffix('.log').read_text())
            consumer = report['consumer']
            verify_consumer(consumer, commit, tag, assets[native], assets[wheel], digest(root / 'release/inputs.lock.json'))
            require(consumer.get('target') == platform, 'public consumer platform differs')
            report['platform'] = platform
            report['environment'] = consumer['environment']
        report.update(stage='complete', result='PASS')
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        report['failure'] = str(exc)
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=PLATFORMS, default=DARWIN)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--publication', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    report = smoke(root, args.repository, args.publication or root / 'build/release/ci-publication.json',
                   args.output or root / 'build/release/ci-public-smoke.json', args.platform)
    print(json.dumps(report, indent=2))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
