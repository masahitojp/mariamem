"""Guard the accepted UCA private-copy migration; not runtime acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'f43257225e1fd65c58ea8f5d7b220c3a509c203b'
BASE_PATCH = 'e51d1f3119f6f079810bdec6be2c5924d91d23f066811506c6e1bdb5d32429ee'
DELTA_PATCH = 'be6d8077d9df40b8a79ec6d653a0ec41d0178b9b862a103c850ed8c4ac77b376'
DELTA_BYTES = 216045
GUEST = '332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22'
LINKED = '432200d991a53f56dcbb3ddd5e2ef49a8d3099b9702dc48d3c9ddd26bfc43b6c'
PREPARED = {
    'strings/ctype-uca.c': '7f8708a3f5be2f3b05df572b9f6a2f003b3cf72bd5588e20be72f64f0ccf69c8',
    'strings/mariamem_uca_copy_prepared.h': 'e98564588cdff8076e747b0be6780a6e23c981a7769322db52ba26738cc5f5e7',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source(root):
    root = Path(root)
    require(not (root/'guest/experimental.patch').exists(), 'experimental patch remains')
    patch = (root/'guest/source.patch').read_bytes()
    sha = lambda b: hashlib.sha256(b).hexdigest()
    require(sha(patch[:-DELTA_BYTES]) == BASE_PATCH, 'canonical base patch changed')
    require(sha(patch[-DELTA_BYTES:]) == DELTA_PATCH, 'accepted private-copy delta changed')
    profile = json.loads((root/'guest/versions/12.3.3/legacy-full.json').read_text())
    require(profile['files']['guest/source.patch']['sha256'] == sha(patch),
            'selected12.3.3 source pin differs')
    return {'base_patch_sha256': BASE_PATCH, 'accepted_delta_sha256': DELTA_PATCH,
            'canonical_patch_sha256': sha(patch), 'experimental_origin': ORIGIN}


def validate_record(record, commit):
    require(record['source_commit'] == record['source_identity']['commit'] == commit,
            'build source differs')
    require(record['contract'] == 'development-unqualified-v1' and record['result'] == 'UNQUALIFIED',
            'stage1 must remain UNQUALIFIED')
    require(record['guest_sha256'] == GUEST and record['repetitions'] == [
        {'guest_sha256': GUEST, 'linked_sha256': LINKED}], 'accepted guest/linked bytes differ')
    prepared = record['prepared_source']
    require(not prepared.get('experimental_patch') and 'experimental.patch' not in prepared['overlays'],
            'experimental build provenance remains')
    for name, sha in PREPARED.items():
        require(prepared['modified_files'].get(name) == sha, 'prepared UCA source differs: '+name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest-dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = dict(source(ROOT), result='PASS_SOURCE_MIGRATION_ONLY')
    if args.guest_dir:
        from dev_guest import verify_guest
        record = verify_guest(ROOT, args.guest_dir)
        validate_record(record, os.environ['GITHUB_SHA'])
        result.update(result='PASS_CANONICAL_SOURCE_SAME_GUEST_UNQUALIFIED',
                      source_commit=record['source_commit'], guest_sha256=GUEST,
                      linked_sha256=LINKED, independent_builds=1,
                      installation='PENDING', platform_acceptance='PENDING')
    text = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
