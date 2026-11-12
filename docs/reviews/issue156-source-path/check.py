#!/usr/bin/env python3
"""Read-only source/profile anchor checks. Requires the cited Git objects."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def body(text, name):
    start = text.index('func ' + name + '(')
    end = text.find('\nfunc ', start + 1)
    return text[start:end if end >= 0 else len(text)].rstrip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--upstream', type=pathlib.Path)
    args = parser.parse_args()
    data = json.loads((HERE / 'bindings.json').read_text())
    cache = {}
    current = {}
    for name, item in data['generated_functions'].items():
        for field, ref in [('current', data['product_source_commit']), ('baseline', data['baseline_profile_product_source_commit'])]:
            key = (ref, item['path'])
            if key not in cache:
                cache[key] = subprocess.check_output(['git', 'show', ref + ':' + item['path']], cwd=ROOT, text=True)
            text = body(cache[key], name)
            assert sha(text.encode()) == item[field + '_sha256'], (field, name)
            if field == 'current':
                current[name] = text
    purge_read = purge_dict = 0
    for profile in data['profiles']:
        text = subprocess.check_output(['git', 'show', data['profile_record_source_commit'] + ':' + profile['path']], cwd=ROOT)
        assert sha(text) == profile['sha256'], profile['path']
        chains = [re.findall(r'\bp\d+\.(Fn\d+)\+', b) for b in text.decode().split('\n\n')]
        chains = [c for c in chains if 'Fn16595' in c or ('Fn18164' in c and 'Fn17739' in c)]
        assert chains == [s['chain'] for s in profile['stacks']]
        purge_read += sum('Fn18228' in c and 'Fn17217' in c for c in chains)
        purge_dict += sum('Fn18228' in c and 'Fn17220' in c for c in chains)
        assert len(chains) == 4 and sum('Fn16595' in c for c in chains) == 3
        assert any(all(f in c for f in ['Fn17733', 'Fn17744', 'Fn18236', 'Fn16595']) for c in chains)
        assert any(all(f in c for f in ['Fn17221', 'Fn18228', 'Fn16595']) and ('Fn17217' in c or 'Fn17220' in c) for c in chains)
        assert any(all(f in c for f in ['Fn18276', 'Fn17500', 'Fn17499', 'Fn16595']) for c in chains)
    assert (purge_read, purge_dict) == (3, 1)
    assert 'Fn18276(m, int32(1))' in current['Fn17500']
    assert 'if l0 == int32(0)' in current['Fn18276'] and 'Fn16583(m)' in current['Fn18276']
    assert 'if l1 != 0' in current['Fn16787'] and 'Fn16583(m)' in current['Fn16787']
    assert 'Fn17217(m, l0)' in current['Fn17221']
    assert 'Fn18162(m, v256, v257, l0, v257)' in current['Fn17217']
    assert 'Fn16787(m, v196, l2)' in current['Fn18162']
    assert 'Fn17733(m)' in current['Fn17744'] and 'Fn17733(m)' in current['Fn17739']
    assert 'Fn92(m, v29, v70)' in current['Fn17220'] and 'v29 = int32(18662528)' in current['Fn17220']
    for f in ['Fn17733', 'Fn17744', 'Fn18236', 'Fn17220']:
        assert 'Fn16583(m)' not in current[f] and 'Fn16584(m)' not in current[f]
    # Literal anchors identify the C functions; this is not a recovered symbol map.
    generated = subprocess.check_output(['git', 'show', data['product_source_commit'] + ':internal/generatedgo/code/generated.go'], cwd=ROOT, text=True)
    raw = generated.split('var wasm2goData_data_bin = []byte("', 1)[1].split('")', 1)[0]
    assert re.fullmatch(r'(?:\\x[0-9a-fA-F]{2})*', raw)
    segment = bytes.fromhex(raw.replace('\\x', ''))
    for address, expected in data['literal_anchors'].items():
        addr = int(address)
        offset = addr - 8388608 if addr < 18119910 else addr - 18119936 + 9731302
        actual = segment[offset:].split(b'\0', 1)[0].decode()
        assert actual == expected, address
    if args.upstream:
        for path, digest in data['upstream_files_sha256'].items():
            assert sha((args.upstream / path).read_bytes()) == digest, path
    sums = json.loads((HERE / 'SHA256SUMS.json').read_text())
    for path, digest in sums.items():
        assert sha((HERE / path).read_bytes()) == digest, path
    print('PASS: 4 historical profiles / 19 current+baseline function hashes / call and literal anchors / checksums')
    print('C source bytes checked' if args.upstream else 'C source bytes not present in offline replay; pinned URLs/hashes retained')
    print('No execution, causal attribution, WAITING-state or lock-owner measurement is implied.')

if __name__ == '__main__':
    main()
