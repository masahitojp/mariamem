#!/usr/bin/env python3
"""Aggregate or revalidate preview qualification without producing publication credentials."""

import argparse
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

from ci_release_reuse import GitHub, WORKFLOW, safe_name
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


def check_jobs(needs, commit, *, reuse=False):
    require(set(needs) == REQUIRED_JOBS, 'preview dependency set differs')
    require(needs['resolve'].get('result') == 'success', 'resolve did not pass')
    expected = 'skipped' if reuse else 'success'
    for job in sorted(REQUIRED_JOBS - {'resolve'}):
        require(needs[job].get('result') == expected, job + ' must be ' + expected)
    outputs = needs['resolve']['outputs']
    qualification = ('preview-reuse', 'false', 'true') if reuse else ('full', 'false', 'false')
    require((outputs.get('mode'), outputs.get('runtime_reused'), outputs.get('features_reused'),
             outputs.get('source_sha')) == (*qualification, commit), 'preview qualification plan differs')


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


def successful_attempt(api, run, workflow):
    info = api.json(f'/actions/runs/{run}')
    require(info.get('path', '').split('@', 1)[0] == WORKFLOW
            and (info.get('id'), info.get('head_sha'), info.get('event'),
                 info.get('status'), info.get('conclusion'))
            == (run, workflow, 'workflow_dispatch', 'completed', 'success'),
            'reuse requires a successful exact-workflow Release CI run')
    attempt = info.get('run_attempt')
    require(type(attempt) is int and attempt > 0, 'invalid qualification run attempt')
    return attempt


def revalidate(api, run, commit, workflow, package, guest, inputs, inventory):
    attempt = successful_attempt(api, run, workflow)
    name = f'release-candidate-preview-{commit}-attempt-{attempt}'
    with artifact(api, run, commit, name) as (bundle, reference):
        require(bundle.names == {'preview-qualification.json'}, 'unexpected preview receipt members')
        receipt = bundle.json('preview-qualification.json')
    identity = {'contract': CONTRACT, 'result': 'READY', 'source_commit': commit,
                'workflow_commit': workflow, 'run_id': run, 'run_attempt': attempt,
                'guest_sha256': guest, 'inputs_sha256': inputs}
    require(isinstance(receipt, dict) and set(receipt) == {*identity, 'targets'}
            and all(receipt[key] == value for key, value in identity.items()),
            'preview READY identity differs')
    targets = receipt['targets']
    require(isinstance(targets, dict) and set(targets) == set(TARGETS),
            'preview READY targets differ')
    require(collect(api, run, commit, package, guest, inventory) == targets,
            'preview READY wheel or artifact identity differs')
    require(successful_attempt(api, run, workflow) == attempt,
            'qualification run was restarted during validation')
    return {**reference, 'run_attempt': attempt}


REUSE_ERRORS = (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, http.client.HTTPException)


def select_reuse(api, current_run, commit, workflow, package, guest, inputs, inventory):
    endpoint = f'/actions/workflows/{Path(WORKFLOW).name}/runs'
    try:
        runs = api.json(f'{endpoint}?event=workflow_dispatch&status=success&head_sha={workflow}&per_page=100')
        for item in runs['workflow_runs']:
            run = item['id']
            if run == current_run:
                continue
            try:
                return revalidate(api, run, commit, workflow, package, guest, inputs, inventory)
            except REUSE_ERRORS as error:
                print(f'Cannot reuse preview run {run}: {error}', file=sys.stderr)
    except REUSE_ERRORS as error:
        print(f'Cannot discover preview qualification: {error}', file=sys.stderr)
    return None


def preview_inputs(root, commit):
    checkout(root, commit)
    package = version(root)['PYTHON_VERSION']
    path = root / 'release/generated-go-inputs.json'
    guest = json.loads(path.read_text())['guest_sha256']
    return package, guest, digest(path), source_inventory(root)


def write_selection(reference):
    mode = 'preview-reuse' if reference else 'full'
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'mode={mode}\nruntime_reused=false\nfeatures_reused={str(bool(reference)).lower()}\n')
        if reference:
            output.write('preview_reuse=' + json.dumps(reference, separators=(',', ':')) + '\n')
    if reference:
        print(f"Reusing preview run {reference['run_id']} attempt {reference['run_attempt']}")
    else:
        print('No reusable preview qualification; running all six targets')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--reuse-run', type=int, help='Revalidate one completed exact-source preview run')
    mode.add_argument('--select-reuse', action='store_true', help='Write the automatic plan to GITHUB_OUTPUT')
    args = parser.parse_args()
    if not args.select_reuse and args.output is None:
        parser.error('--output is required when writing a qualification receipt')
    commit = os.environ['SOURCE_SHA']
    workflow = os.environ['WORKFLOW_SHA']
    run, attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
    api = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN'])
    if args.select_reuse:
        inputs = preview_inputs(args.root, commit)
        write_selection(select_reuse(api, run, commit, workflow, *inputs))
        return
    record = {'contract': CONTRACT, 'result': 'NOT READY', 'source_commit': commit,
              'workflow_commit': workflow, 'run_id': run, 'run_attempt': attempt}
    try:
        needs = json.loads(os.environ['NEEDS_JSON']) if args.reuse_run is None else None
        if args.reuse_run is None and needs['resolve']['outputs'].get('mode') == 'preview-reuse':
            check_jobs(needs, commit, reuse=True)
            reference = json.loads(needs['resolve']['outputs']['preview_reuse'])
            original = reference['run_id']
            require(type(original) is int and original > 0 and original != run, 'invalid original qualification run')
            require(successful_attempt(api, original, workflow) == reference['run_attempt'],
                    'qualification run changed after selection')
            record['reused_qualification'] = reference
        else:
            inputs = preview_inputs(args.root, commit)
            package, guest, input_digest, inventory = inputs
            if args.reuse_run is None:
                check_jobs(needs, commit)
                record['guest_sha256'] = guest
                record['inputs_sha256'] = input_digest
                record['targets'] = collect(api, run, commit, package, guest, inventory)
            else:
                require(args.reuse_run > 0 and args.reuse_run != run,
                        'reuse requires a distinct earlier qualification run')
                record['reused_qualification'] = revalidate(api, args.reuse_run, commit, workflow, *inputs)
        record['result'] = 'READY'
    except Exception as error:
        record['reason'] = str(error)
        raise
    finally:
        args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        print('Native preview: ' + record['result'])


if __name__ == '__main__':
    main()
