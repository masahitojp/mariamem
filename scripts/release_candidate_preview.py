#!/usr/bin/env python3
"""Aggregate current-run qualification without producing publication credentials."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

from ci_release_reuse import GitHub, safe_name
from common import digest
from generated_release import CONTRACT as LEGACY_CONTRACT, checkout, source_inventory, version, wheel_name
from native_target import DARWIN, LINUX_ARM, LINUX_X86, UBUNTU, WINDOWS_ARM, WINDOWS_X86, platform_fields, target_metadata
from release_features import FEATURES

CONTRACT = 'release-candidate-preview-v1'
TARGETS = (UBUNTU, DARWIN, WINDOWS_X86, WINDOWS_ARM, LINUX_X86, LINUX_ARM)
REQUIRED_JOBS = {'resolve', 'units', 'runtime', 'guest', 'core_ubuntu', 'candidate_ubuntu',
                 'verification_ubuntu', *FEATURES, 'preview-macos', 'preview-windows', 'preview-linux'}
SCENARIOS = ('installed_wheel', 'orm_round_trip', 'parallel_fork_isolation', 'failure_cleanup')
LIBCS = ('manylinux_2_28', 'musllinux_1_2')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_jobs(needs, commit):
    require(set(needs) == REQUIRED_JOBS, 'preview dependency set differs')
    for job in sorted(REQUIRED_JOBS):
        require(needs[job].get('result') == 'success', job + ' did not pass')
    outputs = needs['resolve']['outputs']
    require((outputs.get('mode'), outputs.get('runtime_reused'), outputs.get('features_reused'),
             outputs.get('source_sha')) == ('full', 'false', 'false', commit), 'preview requires fresh qualification')


class Bundle:
    def __init__(self, archive):
        self.archive = archive
        members = archive.infolist()
        names = {safe_name(item.filename) for item in members}
        require(len(names) == len(members), 'duplicate artifact member')
        for item in members:
            require(stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR),
                    'special artifact member')
        self.names = names

    def member(self, name, max_size):
        require(name in self.names, 'missing artifact member: ' + name)
        item = self.archive.getinfo(name)
        require(not item.is_dir() and 0 < item.file_size <= max_size, 'invalid artifact member size: ' + name)
        return item

    def json(self, name):
        return json.loads(self.archive.read(self.member(name, 8 * 1024 * 1024)))

    def file_sha(self, name, max_size=128 * 1024 * 1024):
        expected = self.member(name, max_size)
        with self.archive.open(expected) as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()


@contextmanager
def artifact(api, run, commit, name):
    with tempfile.TemporaryDirectory(prefix='mariamem-preview-') as temporary:
        path = Path(temporary) / 'artifact.zip'
        reference = api.artifact(run, name, commit, path)
        with zipfile.ZipFile(path) as archive:
            yield Bundle(archive), reference


def verify_build(build, target, commit, package, guest, inventory, name, sha):
    meta = target_metadata(target)
    manifest = build['manifest']
    host = meta.get('host_name', 'mariamem-host')
    require(build.get('source_commit') == commit and build.get('source_files_sha256') == inventory
            and build.get('archive_checks_passed') is True, target + ': build source differs')
    info = build.get('host_buildinfo', '').splitlines()
    stamps = {line.strip() for line in info[1:]}
    require(info and info[0].endswith(': go1.26.11')
            and {f'build\tvcs.revision={commit}', 'build\tvcs.modified=false', 'build\tCGO_ENABLED=0',
                 f'build\tGOOS={meta["goos"]}', f'build\tGOARCH={meta["goarch"]}'} <= stamps,
            target + ': host source stamp differs')
    require(Path(build['wheel'].replace('\\', '/')).name == name and build.get('sha256') == sha,
            target + ': wheel build digest differs')
    require(all(manifest.get(key) == value for key, value in platform_fields(meta).items())
            and (manifest.get('package_version'), manifest.get('guest_sha256'),
                 manifest.get('runtime_kind'), manifest.get('public_release_ready'))
            == (package, guest, 'generated-go', False), target + ': manifest differs')
    native_hashes = manifest.get('sha256', {})
    require(set(native_hashes) == {host} and re.fullmatch('[0-9a-f]{64}', native_hashes[host]),
            target + ': malformed native host digest')
    return native_hashes[host]


def verify_native(report, target, commit, package, guest, name, sha, host_sha):
    require((report.get('contract'), report.get('status'), report.get('target'), report.get('source_commit'),
             report.get('version'), report.get('guest_sha256'), report.get('wheel'), report.get('wheel_sha256'),
             report.get('host_sha256')) == ('native-candidate-v1', 'PASS', target, commit, package, guest, name, sha, host_sha),
            target + ': native receipt identity differs')
    require(report.get('scenarios') == dict.fromkeys(SCENARIOS, 'PASS'), target + ': scenario missing or unsuccessful')
    require(report.get('common_cases') == {'tests': 3, 'failures': 0, 'errors': 0, 'skipped': 0},
            target + ': installed case counts differ')
    if target in (WINDOWS_X86, WINDOWS_ARM):
        require(report.get('cases') == {'tests': 18, 'failures': 0, 'errors': 0, 'skipped': 0},
                target + ': Windows boundary case counts differ')
    require(report.get('go_consumer', {}).get('result') == 'PASS'
            and report.get('sqlalchemy', {}).get('result') == 'PASS'
            and report['sqlalchemy'].get('wheel_sha256') == sha, target + ': ORM receipt differs')


def verify_linux(record, target, family, commit, name, sha):
    require((record.get('result'), record.get('target'), record.get('family'), record.get('source_commit'),
             record.get('wheel'), record.get('sha256')) == ('PASS', target, family, commit, name, sha),
            target + ': invalid acceptance for ' + family)
    require(record.get('environment', {}).get('machine') == target_metadata(target)['architecture']
            and record.get('image_digests'), target + ': container identity missing')


def collect(api, run, commit, package, guest, inventory):
    records = {}
    for target in TARGETS:
        name = wheel_name(package, target)
        if target == UBUNTU:
            wheel_artifact = 'release-runtime-ubuntu-24.04-' + commit
            proof_artifact = 'release-evidence-' + target + '-' + commit
            with artifact(api, run, commit, wheel_artifact) as (bundle, wheel_ref):
                build = bundle.json('tests/evidence/alpha-wheel.json')
                sha = bundle.file_sha('build/dist/' + name)
                verify_build(build, target, commit, package, guest, inventory, name, sha)
            with artifact(api, run, commit, proof_artifact) as (bundle, proof_ref):
                proof = bundle.json('build/release/ci-ready.json')
                require((proof.get('version'), proof.get('contract'), proof.get('result'), proof.get('source_commit'),
                         proof.get('platform'), proof.get('guest_sha256'), proof.get('python_version'))
                        == (3, LEGACY_CONTRACT, 'READY', commit, target, guest, package)
                        and proof.get('assets', {}).get(name) == sha and proof.get('wheel_record') == build
                        and 'runtime_validation' not in proof, 'Ubuntu platform qualification differs')
                for key in ('build_evidence_sha256', 'regeneration_sha256', 'acceptance_sha256'):
                    require(re.fullmatch('[0-9a-f]{64}', proof.get(key, '')), 'Ubuntu evidence hash missing: ' + key)
                require(proof['acceptance_sha256'] ==
                        bundle.file_sha('build/release/generated-acceptance.json', 8 * 1024 * 1024),
                        'Ubuntu acceptance digest differs')
            refs = [wheel_ref, proof_ref]
        elif target in (LINUX_X86, LINUX_ARM):
            with artifact(api, run, commit, 'linux-wheel-' + target + '-' + commit) as (bundle, ref):
                sha = bundle.file_sha('dist/' + name)
                verify_build(bundle.json('linux-receipts/wheel.json'), target, commit, package, guest, inventory, name, sha)
                for family in LIBCS:
                    verify_linux(bundle.json(f'linux-receipts/{family}.json'), target, family, commit, name, sha)
            refs = [ref]
        else:
            if target == DARWIN:
                with artifact(api, run, commit, 'macos-boundary-' + commit) as (bundle, ref):
                    sha = bundle.file_sha('build/dist/' + name)
                    build = bundle.json('tests/evidence/alpha-wheel.json')
                    report = bundle.json('build/macos-boundary/acceptance.json')
                refs = [ref]
            else:
                suffix = target_metadata(target)['goarch'] + '-' + commit
                with artifact(api, run, commit, 'windows-wheel-' + suffix) as (bundle, wheel_ref):
                    sha = bundle.file_sha(name)
                with artifact(api, run, commit, 'windows-boundary-' + suffix) as (bundle, proof_ref):
                    build = bundle.json('tests/evidence/alpha-wheel.json')
                    report = bundle.json('build/windows-boundary/acceptance.json')
                refs = [wheel_ref, proof_ref]
            host_sha = verify_build(build, target, commit, package, guest, inventory, name, sha)
            verify_native(report, target, commit, package, guest, name, sha, host_sha)
        records[target] = {'wheel': name, 'wheel_sha256': sha, 'artifact_refs': refs}
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    commit = os.environ['SOURCE_SHA']
    run, attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
    record = {'contract': CONTRACT, 'result': 'NOT READY', 'source_commit': commit,
              'workflow_commit': os.environ['WORKFLOW_SHA'], 'run_id': run, 'run_attempt': attempt}
    try:
        checkout(args.root, commit)
        check_jobs(json.loads(os.environ['NEEDS_JSON']), commit)
        api = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN'])
        package = version(args.root)['PYTHON_VERSION']
        path = args.root / 'release/generated-go-inputs.json'
        guest = json.loads(path.read_text())['guest_sha256']
        record['guest_sha256'] = guest
        record['inputs_sha256'] = digest(path)
        record['targets'] = collect(api, run, commit, package, guest, source_inventory(args.root))
        record['result'] = 'READY'
    except Exception as error:
        record['reason'] = str(error)
        raise
    finally:
        args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        print('Native preview: ' + record['result'])


if __name__ == '__main__':
    main()
