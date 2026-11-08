"""Compare two independent canonical-source bootstrap builds; never qualify them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from common import ROOT
from dev_guest import verify_guest, source_identity
from lexer_prepared import verify_record

EXPECTED_GUEST = '14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1'
EXPECTED_LINKED = '69dbde341c47149463d57b9f6cd4d2683506e7936dc756a4793f5425b788a722'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--first', type=Path, required=True)
    p.add_argument('--second', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.first.resolve() == a.second.resolve():
        raise ValueError('two distinct build directories required')
    identity = source_identity(ROOT)
    if identity['commit'] != os.environ['GITHUB_SHA']:
        raise ValueError('not exact CI source')
    records = []
    for path in [a.first, a.second]:
        record = verify_guest(ROOT, path)
        if record['source_commit'] != identity['commit']:
            raise ValueError('build source commit differs')
        prepared = record['prepared_source']
        if prepared.get('experimental_patch') or 'experimental.patch' in prepared['overlays']:
            raise ValueError('experimental source remains')
        verify_record(ROOT, prepared['lexer_prepared'])
        if record['guest_sha256'] != EXPECTED_GUEST:
            raise ValueError('canonical migration changed accepted guest bytes; inspect before rebinding')
        if hashlib.sha256((path / 'linked.wasm').read_bytes()).hexdigest() != EXPECTED_LINKED:
            raise ValueError('linked guest changed')
        records.append(record)
    for key in ['source_identity', 'prepared_source', 'repetitions', 'guest_sha256', 'guest_bytes', 'toolchain']:
        if records[0][key] != records[1][key]:
            raise ValueError('independent builds differ: ' + key)
    result = {'result': 'PASS_TWO_CANONICAL_SOURCE_BUILDS', 'source_commit': identity['commit'],
              'guest_sha256': EXPECTED_GUEST, 'linked_sha256': EXPECTED_LINKED,
              'independent_builds': 2, 'build_record_sha256': [hashlib.sha256((x / 'guest.json').read_bytes()).hexdigest() for x in [a.first,a.second]],
              'same_bytes_as_experiment_origin': 'b1a265cc30a8603ced743c8aeb59c752751ff9d6',
              'canonical_runtime_installation': 'PENDING', 'qualification': 'NOT_RUN', 'release': 'NOT_APPROVED'}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['result'])


if __name__ == '__main__':
    main()
