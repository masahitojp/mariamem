"""Exact canonical dictionary-wait source/input guard; not runtime acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = '07188f71ed2fed76083a9eb39313e74cb7b8acca00d2c6fb738f459873a98a9a'
DELTA_SHA = '8609bef5c2bfb96e14d407bec08ba36c95cd8e7c190dbacd1959773f63f68744'
DELTA_START = b'--- a/storage/innobase/dict/dict0dict.cc\n'
FILE = 'storage/innobase/dict/dict0dict.cc'
PREPARED_SHA = 'a301ec1c4a2853c37d1b5fba14224da8b66a6909adb4ac83ee2c3563caf77df5'
GUEST = '5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20'
PORT_PATCH_SHA = '0826197caa46c8d1e389e9883e752749b99eb84a56b0afee48b7ba6dd2465288'
PORT_DELTA_SHA = '71a24ef21b35afa8eb65b4450b2a7c16ca7584aa79ab24b910bd4a7668b2218b'
PORT_PREPARED_SHA = '68abba5af765e4eac441a72883fc010641501a3215ff74431a771a2b0c6bf4cc'
LINKED = '7f34f46793406df2e7fbfec293ffbba3bb1491d07a714439d963dc1c49d06e12'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def source(root=ROOT):
    root = Path(root)
    require(not (root/'guest/experimental.patch').exists(), 'experimental patch remains')
    patch = (root/'guest/source.patch').read_bytes()
    input_path = root/'guest/input.json'
    if input_path.is_file() and json.loads(input_path.read_text())['version'] == '12.3.4':
        digest = hashlib.sha256(patch).hexdigest()
        require(digest == PORT_PATCH_SHA, 'canonical 12.3.4 patch differs')
        return {'canonical_patch_sha256': digest, 'dictionary_delta_sha256': PORT_DELTA_SHA,
                'prepared_dictionary_sha256': PORT_PREPARED_SHA}
    # Preserve the historical UCA/dictionary sections byte-for-byte while
    # separately pinning the buffer-pool-only candidate suffix.
    boundary = b'--- a/storage/innobase/buf/buf0buf.cc\n'
    require(patch.count(boundary) == 1, 'missing or duplicate buffer-zero boundary')
    prefix, suffix = patch.split(boundary)
    require(hashlib.sha256(boundary + suffix).hexdigest() == '47f74fd234252c657b119a3f34a30a9c001552cd59b9f2080da39cfcd9cc2354',
            'buffer-zero candidate delta changed')
    complete_patch = patch
    patch = prefix
    require(patch.count(DELTA_START) == 1, 'missing or duplicate dictionary boundary')
    offset = patch.index(DELTA_START)
    require(hashlib.sha256(patch[:offset]).hexdigest() == BASE_SHA, 'canonical base changed')
    require(hashlib.sha256(patch[offset:]).hexdigest() == DELTA_SHA, 'dictionary delta changed')
    digest = hashlib.sha256(complete_patch).hexdigest()
    profile = json.loads((root/'guest/versions/12.3.3/legacy-full.json').read_text())
    require(profile['files']['guest/source.patch']['sha256'] == digest, 'selected source pin differs')
    return {'canonical_patch_sha256': digest, 'dictionary_delta_sha256': DELTA_SHA}


def prepared(directory, expected=PREPARED_SHA):
    require(hashlib.sha256((Path(directory)/FILE).read_bytes()).hexdigest() == expected,
            'actual prepared dictionary source differs')


def validate_record(record, commit):
    require(record['source_commit'] == record['source_identity']['commit'] == commit,
            'source identity differs')
    require(record['contract'] == 'development-unqualified-v1' and record['result'] == 'UNQUALIFIED',
            'bootstrap must remain UNQUALIFIED')
    require(record['guest_sha256'] == GUEST and record['repetitions'] == [
        {'guest_sha256': GUEST, 'linked_sha256': LINKED}], 'reviewed guest/linked bytes differ')
    prep = record['prepared_source']
    require(not prep.get('experimental_patch') and 'experimental.patch' not in prep['overlays'],
            'experimental build provenance remains')
    require(prep['modified_files'].get(FILE) == PREPARED_SHA, 'built dictionary source differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-source', type=Path)
    parser.add_argument('--guest-dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = dict(source(), result='PASS_SOURCE_ONLY')
    if args.prepared_source:
        expected = result.get('prepared_dictionary_sha256', PREPARED_SHA)
        prepared(args.prepared_source, expected)
        result['prepared_dictionary_sha256'] = expected
    if args.guest_dir:
        from dev_guest import verify_guest
        record = verify_guest(ROOT, args.guest_dir)
        validate_record(record, os.environ['GITHUB_SHA'])
        result.update(result='PASS_CANONICAL_SOURCE_SAME_GUEST_UNQUALIFIED',
                      source_commit=record['source_commit'], guest_sha256=GUEST,
                      linked_sha256=LINKED, runtime_acceptance=False)
    text = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
