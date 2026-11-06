#!/usr/bin/env python3
"""Read-only proof that packaged data equals the named experimental C header.

Requires that exact commit object locally. Never fetches or rebuilds a guest.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from check import ROOT, validate, read_json, need


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root/'scripts'))
    from git_identity import require_commit
    manifest = read_json(args.bundle/'input.json')
    identity = require_commit(args.root, manifest['prototype_source_commit'])
    patch = subprocess.check_output(['git', 'show', identity.source_commit+':guest/experimental.patch'],
                                    cwd=args.root, text=True)
    lines = patch.splitlines()
    marker = '+++ b/strings/mariamem_uca_prepared.h'
    need(lines.count(marker) == 1, 'missing/ambiguous prototype header')
    start = lines.index(marker) + 1
    need(lines[start].startswith('@@ '), 'unexpected prototype patch framing')
    tail = lines[start+1:]
    need(tail and all(line.startswith('+') for line in tail), 'unexpected prototype header hunk')
    original = ''.join(line[1:]+'\n' for line in tail).encode()
    packaged, _ = validate(args.bundle, args.root)
    need(packaged == original, 'packaged numeric input differs from prototype')
    print(json.dumps({'result': 'PROTOTYPE_BYTES_MATCH', 'source_commit': identity.source_commit,
                      'header_sha256': hashlib.sha256(original).hexdigest(),
                      'header_bytes': len(original), 'new_guest_execution': False}, indent=2))


if __name__ == '__main__':
    main()
