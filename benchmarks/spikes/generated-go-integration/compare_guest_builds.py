#!/usr/bin/env python3
"""Compare independent legacy-EH work directories without historical pin gates."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uleb(data, pos):
    value = shift = 0
    while True:
        b = data[pos]
        pos += 1
        value |= (b & 127) << shift
        if b < 128:
            return value, pos
        shift += 7


def sections(path):
    data = path.read_bytes()
    assert data[:8] == b'\0asm\x01\0\0\0'
    result = []
    pos = 8
    while pos < len(data):
        kind = data[pos]
        size, start = uleb(data, pos + 1)
        payload = data[start:start + size]
        entry = {'id': kind, 'size': size, 'sha256': hashlib.sha256(payload).hexdigest()}
        if kind == 0:
            n, at = uleb(payload, 0)
            entry['name'] = payload[at:at + n].decode()
        if kind == 10:
            n, at = uleb(payload, 0)
            bodies = []
            for _ in range(n):
                length, at = uleb(payload, at)
                bodies.append(hashlib.sha256(payload[at:at + length]).hexdigest())
                at += length
            entry['function_bodies'] = bodies
        result.append(entry)
        pos = start + size
    return result


def inventory(work):
    build = work / 'source/build-legacy-no-postopt'
    result = {'objects': {}, 'archives': {}, 'configuration': {}, 'artifacts': {}}
    for suffix, key in [('*.o', 'objects'), ('*.a', 'archives')]:
        for p in sorted(build.rglob(suffix)):
            result[key][str(p.relative_to(build))] = digest(p)
    for name in ['link.txt', 'flags.make', 'CMakeCache.txt']:
        result['configuration'][name] = digest(work / 'artifact' / name)
    for name in ['mariamem-legacy-eh.wasm', 'mariamem-legacy-eh-O2-compatible.wasm']:
        p = work / 'artifact' / name
        result['artifacts'][name] = {'sha256': digest(p), 'size': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns, 'sections': sections(p)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    a, b = inventory(args.left), inventory(args.right)
    diff = {}
    for key in ['objects', 'archives', 'configuration']:
        diff[key] = {p: {'left': a[key].get(p), 'right': b[key].get(p)} for p in sorted(a[key].keys() | b[key].keys()) if a[key].get(p) != b[key].get(p)}
    for name, artifact in a['artifacts'].items():
        other = b['artifacts'][name]
        assert len(artifact['sections']) == len(other['sections'])
        changes = []
        for x, y in zip(artifact['sections'], other['sections']):
            if x['sha256'] != y['sha256']:
                item = {'id': x['id'], 'name': x.get('name'), 'left': x['sha256'], 'right': y['sha256']}
                if x['id'] == 10:
                    assert len(x['function_bodies']) == len(y['function_bodies'])
                    item['changed_defined_functions'] = [i for i, (u, v) in enumerate(zip(x['function_bodies'], y['function_bodies'])) if u != v]
                changes.append(item)
        diff[name] = changes
    args.output.write_text(json.dumps({'left_work': str(args.left), 'right_work': str(args.right), 'left': a, 'right': b, 'differences': diff}, indent=2) + '\n')
    print(json.dumps({'object_changes': len(diff['objects']), 'archive_changes': len(diff['archives']), 'configuration_changes': len(diff['configuration']), 'final_equal': a['artifacts']['mariamem-legacy-eh-O2-compatible.wasm']['sha256'] == b['artifacts']['mariamem-legacy-eh-O2-compatible.wasm']['sha256']}, indent=2))


if __name__ == '__main__':
    main()
