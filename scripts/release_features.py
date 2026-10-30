#!/usr/bin/env python3
"""Record or restore all-six-feature success for an exact READY artifact set."""
import argparse
import json
import os
import re
from pathlib import Path
import stat
import tempfile
import zipfile

from ci_release_reuse import GitHub
from generated_release import CONTRACT, PLATFORMS, expected_names, read, require, write

FEATURES = ('feature-live', 'feature-dump', 'feature-django', 'feature-routing',
            'feature-preparation', 'feature-sql')
CONTRACT_VERSION = 'release-features-v1'


def gate(needs):
    require(needs.get('resolve', {}).get('result') == 'success', 'release resolution failed')
    outputs = needs['resolve'].get('outputs', {})
    reused = outputs.get('features_reused')
    require(reused in ('true', 'false'), 'missing feature reuse decision')
    if reused == 'true':
        require(outputs.get('mode') == 'guard-only', 'feature reuse requires exact READY reuse')
        require(str(outputs.get('feature_run', '')).isdigit() and int(outputs['feature_run']) > 0,
                'missing original feature run')
    expected = 'skipped' if reused == 'true' else 'success'
    for job in ('runtime', 'units', *FEATURES):
        require(needs.get(job, {}).get('result') == expected, job + ' did not finish as selected')
    require(needs.get('verification', {}).get('result') == 'success', 'artifact verification failed')
    return reused == 'true'


def validate(record, commit, run, ready):
    require(ready.get('contract') == CONTRACT and ready.get('result') == 'READY' and
            ready.get('source_commit') == commit and set(ready.get('platforms', {})) == set(PLATFORMS),
            'feature proof requires exact both-platform READY')
    require(isinstance(ready.get('assets'), dict) and
            set(ready['assets']) == expected_names(ready['python_version']) and
            all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                for value in ready['assets'].values()), 'incomplete READY asset hashes')
    require(isinstance(record, dict) and record.get('contract') == CONTRACT_VERSION,
            'feature receipt contract differs')
    require(record.get('source_commit') == commit and type(record.get('feature_run')) is int
            and record['feature_run'] == run and run > 0, 'feature receipt source/run differs')
    require(record.get('assets') == ready['assets'], 'feature receipt artifact hashes differ')
    require(record.get('results') == {job: 'success' for job in ('units', *FEATURES)},
            'feature receipt incomplete or unsuccessful')
    return record


def restore(api, commit, run, ready):
    # Always fetch the original success artifact. Reuse never extends its expiry.
    with tempfile.TemporaryDirectory(prefix='mariamem-feature-proof-') as temporary:
        archive = Path(temporary) / 'features.zip'
        api.artifact(run, 'release-features-' + commit, commit, archive)
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            require(len(entries) == 1 and entries[0].filename == 'features.json',
                    'unexpected feature receipt members')
            item = entries[0]
            require(stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG) and
                    item.file_size <= 4 * 1024 * 1024, 'special/oversized feature receipt')
            record = json.loads(zipped.read(item))
        return validate(record, commit, run, ready)


def record(root, commit, run, candidate_run, evidence_run, needs, api=None):
    reused = gate(needs)
    ready = read(root / 'build/release/ci-ready.json')
    if reused:
        feature_run = int(needs['resolve']['outputs']['feature_run'])
        proof = restore(api, commit, feature_run, ready)
    else:
        feature_run = run
        proof = validate({'contract': CONTRACT_VERSION, 'source_commit': commit,
                          'feature_run': run, 'assets': ready['assets'],
                          'results': {job: needs[job]['result'] for job in ('units', *FEATURES)}},
                         commit, run, ready)
        write(root / 'build/release/features.json', proof)
    require(all(type(value) is int and value > 0 for value in (candidate_run, evidence_run)),
            'invalid qualification references')
    reference = {'version': 2, 'source_commit': commit, 'candidate_run': candidate_run,
                 'evidence_run': evidence_run, 'feature_run': feature_run}
    write(root / 'build/release/qualification.json', reference)
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('gate', 'record'))
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    needs = json.loads(os.environ['NEEDS_JSON'])
    if args.operation == 'gate':
        gate(needs)
    else:
        api = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ.get('GITHUB_TOKEN'))
        record(args.root, os.environ['SOURCE_SHA'], int(os.environ['GITHUB_RUN_ID']),
               int(os.environ['CANDIDATE_RUN']), int(os.environ['EVIDENCE_RUN']), needs, api)


if __name__ == '__main__':
    main()
