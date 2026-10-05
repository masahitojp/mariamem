#!/usr/bin/env python3
"""Verify canonical generated source, pinned inputs and guest identity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    source = ROOT/'internal/generatedgo'
    record = json.loads((source/'provenance.json').read_text())
    pins = ROOT/'release/generated-go-inputs.json'
    require(record['input_manifest_sha256'] == digest(pins), 'input manifest changed')
    # Ordinary handwritten integration files are versioned Go source, outside
    # the unchanged transpilation inventory.
    handwritten = {'runtime_instance.go', 'memory_backing_unix.go', 'memory_backing_other.go', 'memory_lifetime.go', 'code/base/runtime_cleanup.go', 'code/base/memory_mapping.go', 'code/base/memory_mapping_test.go', 'memory_backing_test.go'}
    inventory = {str(p.relative_to(source)):digest(p) for p in source.rglob('*')
                 if p.is_file() and p.name != 'provenance.json' and str(p.relative_to(source)) not in handwritten}
    require(inventory == record['files_sha256'], 'generated source inventory changed; regenerate')
    require(record['guest_sha256'] == json.loads(pins.read_text())['guest_sha256'], 'guest identity changed')
    print('PASS: generated source inventory, pinned inputs and guest identity')


if __name__ == '__main__':
    main()
