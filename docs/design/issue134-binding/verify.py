"""Recheck the exact 13.2 worker body comparison against preserved 13.0.2 evidence.

Read-only source evidence: this does not install or accept a runtime binding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from runtime_thread_lifetime import function

REFERENCE = 'f4507b514aabac2eb834170668c69f37067b6732'
PREFIX = 'benchmarks/spikes/issue138-paired-capture/evidence/native/runtime/reviewed-binding/'


def original(name):
    return subprocess.check_output(['git', 'show', REFERENCE+':'+PREFIX+name], cwd=ROOT, text=True)


def normalized(text):
    return re.sub(r'\s+', '', text)


def compare(before, after):
    numbers = r'(?<![A-Za-z0-9_])\d+\b'
    left, right = re.findall(numbers, before), re.findall(numbers, after)
    if len(left) != len(right):
        raise ValueError('different number of numeric literals')
    mapping = {}
    for x, y in zip(left, right):
        if x in mapping and mapping[x] != y:
            raise ValueError('inconsistent relocation')
        mapping[x] = y
    changed = {x:y for x,y in mapping.items() if x != y}
    if any(int(x) < 15000000 or int(y)-int(x) != 67648 for x,y in changed.items()):
        raise ValueError('unreviewed constant/ABI/relocation change')
    relocated = re.sub(numbers, lambda m: mapping[m[0]], before)
    if normalized(relocated) != normalized(after):
        raise ValueError('complete worker body changed beyond recorded relocation')
    return changed


def verify(generated, guest_record):
    old = json.loads(original('identity.json'))
    if guest_record['source_commit'] != 'ecddf5afb248673eee2055d5b842e617ea799964':
        raise ValueError('wrong producer')
    if guest_record['guest_sha256'] != '607cab7baa164aad064aad4d4e8622249a58204cf828650fab5bd9c8d436b3b4':
        raise ValueError('wrong guest')
    result = {}
    for name, item in old['functions'].items():
        fn = item['function']
        before = original(fn+'.txt')
        if hashlib.sha256(normalized(before).encode()).hexdigest() != item['normalized_sha256']:
            raise ValueError('historical body identity mismatch')
        after = function((generated/name.removeprefix('code/')).read_text(), fn)
        result[name] = {'role': item['role'], 'function': fn,
            'normalized_sha256': hashlib.sha256(normalized(after).encode()).hexdigest(),
            'reference_body_sha256': hashlib.sha256(before.encode()).hexdigest(),
            'candidate_body_sha256': hashlib.sha256(after.encode()).hexdigest(),
            'changed_static_addresses': compare(before, after),
            'complete_body_equal_after_recorded_relocation': True}
    tls = set(re.findall(r'm.G2 = int32\((\d+)\)', (generated/'generated.go').read_text()))
    if tls != {'489'}:
        raise ValueError('TLS initializer changed')
    tables = []
    for path in generated.glob('p*/*.go'):
        tables += re.findall(r'm.T0\[94\] = (Fn\d+)\n', path.read_text())
    if tables != ['Fn131'] or normalized(function((generated/'p8/p8_pure.go').read_text(), 'Fn131')) != 'funcFn131(m*base.Module,l0int32){return}':
        raise ValueError('thread entry no-op table target changed')
    return {'reference_source_commit': REFERENCE, 'reference_guest_sha256': old['guest_sha256'],
            'functions': result, 'TLS_init_bytes': 489, 'noop_table_index': 94,
            'ABI_offsets': old['ABI_offsets'],
            'scope': 'Full three-body relocation comparison only; not installed binding or runtime acceptance'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--handoff', type=Path)
    p.add_argument('--self-test', action='store_true')
    a=p.parse_args()
    if a.self_test:
        record = json.loads((Path(__file__).parent/'comparison.json').read_text())
        for item in record['functions'].values():
            body = (Path(__file__).parent/(item['function']+'.txt')).read_text()
            if hashlib.sha256(body.encode()).hexdigest() != item['candidate_body_sha256']:
                raise ValueError('saved candidate body differs')
            before = original(item['function']+'.txt')
            compare(before, body)
            constant = 'int32(1)' if 'int32(1)' in body else 'int32(0)'
            for damaged in (body.replace(constant, 'int32(2)', 1),
                            body.replace('return', 'panic("changed"); return', 1)):
                try:
                    compare(before, damaged)
                except ValueError:
                    continue
                raise ValueError('worker mutation was accepted')
        print('PASS: three complete comparisons and six rejected mutations')
        return
    if a.handoff is None:
        p.error('--handoff or --self-test is required')
    from dev_guest import verify_guest, verify_translation
    guest = verify_guest(ROOT, a.handoff/'guest', engine='13.2.0', profile='native-text')
    verify_translation(ROOT, a.handoff/'review/translation', guest['guest_sha256'])
    print(json.dumps(verify(a.handoff/'review/translation/module/generated', guest), indent=2))


if __name__ == '__main__':
    main()
