"""Exact experimental worker binding; canonical installer policy stays unchanged.

Only the rebuilt Issue63 guest is accepted, and all three whole-function hashes
must equal the reviewed ABI before the normal installer's checks run again.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import generate_runtime
import runtime_thread_lifetime as binding

GUEST = '96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f'


def authorize(guest_sha, source):
    if guest_sha != GUEST:
        raise ValueError('not the exact Issue63 development guest')
    checked = {}
    for name, (fn, expected) in binding.FUNCTIONS.items():
        path = source/'generated'/name.removeprefix('code/')
        body = binding.function(path.read_text(), fn)
        actual = hashlib.sha256(re.sub(r'\s+', '', body).encode()).hexdigest()
        if actual != expected:
            raise ValueError('Issue63 worker ABI changed: '+fn)
        checked[fn] = actual
    return checked


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--development-input' not in args:
        raise ValueError('Issue63 binding is development-only')
    pins = json.loads(Path(args[args.index('--development-input')+1]).read_text())
    src = Path(args[args.index('--source-module')+1])
    checks = authorize(pins['guest_sha256'], src)
    print('Issue63 exact guest / unchanged worker bodies:', json.dumps(checks), flush=True)
    # Process-local exact rebinding. validate_inputs and apply retain every
    # inventory, whole-body, yield/Module, driver and runtime-preimage check.
    binding.GUEST_SHA256 = GUEST
    generate_runtime.main()
