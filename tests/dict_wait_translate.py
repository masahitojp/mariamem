"""One source-only dictionary-wait translation. Never overrides runtime binding guards."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_generated_guest import download
from common import digest
from dev_guest import external_output, inventory, source_identity, verify_guest, verify_translation
from git_identity import require_commit
import runtime_crc32c as crc
import runtime_thread_lifetime as threads


def inspect_bindings(module):
    """Report exact existing anchors only; no normalization beyond their contracts."""
    results = {}
    for path, (name, expected) in threads.FUNCTIONS.items():
        p = module / 'generated' / path.removeprefix('code/')
        try:
            body = threads.function(p.read_text(), name)
            actual = hashlib.sha256(re.sub(r'\s+', '', body).encode()).hexdigest()
            results[name] = {'path': path, 'expected': expected, 'observed': actual,
                             'exact_match': actual == expected}
        except (ValueError, FileNotFoundError) as exc:
            results[name] = {'path': path, 'exact_match': False, 'reason': str(exc)}
    path = module / 'generated' / crc.PATH.removeprefix('code/')
    try:
        body = crc.function(path.read_text())
        results['crc_validator'] = {'path': crc.PATH, 'function': crc.FUNCTION,
                                    'exact_match': True, 'body_sha256': digest_text(body)}
    except (ValueError, FileNotFoundError) as exc:
        results['crc_validator'] = {'path': crc.PATH, 'function': crc.FUNCTION,
                                    'exact_match': False, 'reason': str(exc)}
    data = (module / 'generated/data.bin').read_bytes()
    table = data[crc.TABLE_OFFSET:crc.TABLE_OFFSET + crc.TABLE_SIZE]
    results['crc_table_at_old_offset'] = {'offset': crc.TABLE_OFFSET,
        'expected': crc.TABLE_SHA256, 'observed': hashlib.sha256(table).hexdigest(),
        'exact_match': len(table) == crc.TABLE_SIZE and hashlib.sha256(table).hexdigest() == crc.TABLE_SHA256}
    return results


def digest_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    identity = source_identity(ROOT)
    require_commit(ROOT, identity['commit'])
    guest = args.guest_dir.resolve()
    record = verify_guest(ROOT, guest)
    out = external_output(ROOT, args.output)
    out.mkdir()
    try:
        pin = json.loads((ROOT / 'release/generated-go-toolchain.json').read_text())
        archive = download(pin['archives']['converter'], out / 'downloads')
        translation = out / 'translation'
        adapter = out / 'candidate'
        spike = ROOT / 'benchmarks/spikes/generated-go-integration'
        subprocess.run([sys.executable, str(spike / 'translate_guest.py'),
            '--guest', str(guest / 'mariamem.wasm'), '--guest-sha256', record['guest_sha256'],
            '--converter-archive', str(archive), '--output', str(translation)], check=True)
        raw = verify_translation(ROOT, translation, record['guest_sha256'])
        subprocess.run([sys.executable, str(spike / 'setup_candidate.py'), '--source-only',
            '--source-module', str(translation / 'module'), '--guest', str(guest / 'mariamem.wasm'),
            '--input-manifest', str(translation / 'input-manifest.json'),
            '--output', str(adapter)], check=True)
        bindings = inspect_bindings(adapter / 'module')
        assert verify_guest(ROOT, guest) == record and source_identity(ROOT) == identity
        result = {'result': 'UNQUALIFIED_TRANSLATION_COMPLETE_BINDING_REVIEW_REQUIRED',
            'source_commit': identity['commit'], 'guest_sha256': record['guest_sha256'],
            'linked_sha256': record['repetitions'][0]['linked_sha256'],
            'guest_record_sha256': digest(guest / 'guest.json'),
            'translation_record_sha256': digest(translation / 'input-manifest.json'),
            'raw_translation_guest_sha256': raw['guest_sha256'],
            'runtime_guest_binding_accepted': False, 'canonical_guest_sha256': threads.GUEST_SHA256,
            'binding_anchors': bindings, 'candidate_inventory': inventory(adapter / 'module'),
            'guest_execution': False, 'native_sql': False, 'performance': False,
            'qualification': False, 'next': 'Review complete function/data binding before runtime installation; no guard bypass'}
        (out / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    except BaseException as exc:
        (out / 'failure.json').write_text(json.dumps({'result': 'FAIL', 'source_commit': identity['commit'],
            'guest_sha256': record['guest_sha256'], 'error': type(exc).__name__, 'message': str(exc)}, indent=2)+'\n')
        raise
    print(result['result'])


if __name__ == '__main__':
    main()
