#!/usr/bin/env python3
"""Pinned source/receipt checks for one experimental dictionary-lock patch."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_record(record, pins, source):
    assert record['contract'] == 'development-unqualified-v1'
    assert record['result'] == 'UNQUALIFIED'
    assert record['source_commit'] == record['source_identity']['commit'] == source
    assert len(record['repetitions']) == 1
    assert record['guest_sha256'] == record['repetitions'][0]['guest_sha256']
    prepared = record['prepared_source']
    assert prepared['experimental_patch'] == {'file': 'guest/experimental.patch', 'sha256': pins['patch_sha256']}
    assert prepared['modified_files'][pins['file']] == pins['after_sha256']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--upstream-file', type=Path)
    parser.add_argument('--guest-record', type=Path)
    parser.add_argument('--mutation-controls', action='store_true')
    args = parser.parse_args()
    pins = json.loads((HERE / 'input.json').read_text())
    patch = ROOT / 'guest/experimental.patch'
    assert sha(patch.read_bytes()) == pins['patch_sha256']
    text = patch.read_text()
    assert [s for s in text.splitlines() if s.startswith('+++ ')] == ['+++ b/' + pins['file']]
    assert text.count('+\t\ttpool::tpool_wait_begin();') == text.count('+\t\ttpool::tpool_wait_end();') == 1
    assert '+\tif (!latch.wr_lock_try()) {' in text
    assert '+\t\tlock_wait(SRW_LOCK_CALL);' in text
    if args.upstream_file:
        original = args.upstream_file.read_bytes()
        assert sha(original) == pins['before_sha256']
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / pins['file']
            source.parent.mkdir(parents=True)
            source.write_bytes(original)
            subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=directory, check=True, capture_output=True)
            candidate = source.read_bytes()
            assert sha(candidate) == pins['after_sha256']
            assert candidate.decode().count(pins['candidate_fragment']) == 1
            # Full preimage recovery: only the declared include and eviction change.
            restored = candidate.decode().replace('#include <tpool.h>\n', '').replace(pins['candidate_fragment'], pins['original_fragment'])
            assert restored.encode() == original
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require_commit(ROOT, source)
    if args.guest_record:
        check_record(json.loads(args.guest_record.read_text()), pins, source)
    if args.mutation_controls:
        fixture = {'contract': 'development-unqualified-v1', 'result': 'UNQUALIFIED',
                   'source_commit': source, 'source_identity': {'commit': source},
                   'repetitions': [{'guest_sha256': '0' * 64}], 'guest_sha256': '0' * 64,
                   'prepared_source': {'experimental_patch': {'file': 'guest/experimental.patch', 'sha256': pins['patch_sha256']},
                                       'modified_files': {pins['file']: pins['after_sha256']}}}
        check_record(fixture, pins, source)
        mutations = [lambda r: r.update(result='PASS'),
                     lambda r: r.update(source_commit='0' * 40),
                     lambda r: r['prepared_source']['experimental_patch'].update(file='guest/source.patch'),
                     lambda r: r['prepared_source']['experimental_patch'].update(sha256='0' * 64),
                     lambda r: r['prepared_source']['modified_files'].update({pins['file']: '0' * 64}),
                     lambda r: r['repetitions'].append(r['repetitions'][0])]
        for mutate in mutations:
            bad = copy.deepcopy(fixture)
            mutate(bad)
            try:
                check_record(bad, pins, source)
            except AssertionError:
                continue
            raise AssertionError('corrupt receipt accepted')
        print('PASS: six synthetic invalid receipt controls (not a guest build)')
    print('PASS: experimental patch shape/hash' + ('; exact upstream application and reversal' if args.upstream_file else '') + ('; exact built-source receipt' if args.guest_record else ''))


if __name__ == '__main__':
    main()
