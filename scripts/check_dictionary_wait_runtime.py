"""Exact guest/body/data boundary for the dictionary contention regression."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def body(text, name):
    matches = list(re.finditer(r'^func '+name+r'\(', text, re.M))
    if len(matches) != 1:
        raise ValueError('missing/duplicate dictionary fixture function: '+name)
    tail = text[matches[0].start():]
    end = re.search(r'\nfunc ', tail)
    return tail[:end.start()] if end else tail


def validate_body(text, expected):
    observed = hashlib.sha256(re.sub(r'\s+', '', text).encode()).hexdigest()
    if observed != expected:
        raise ValueError('dictionary fixture body changed')


def validate(root=ROOT):
    root = Path(root)
    pins = json.loads((root/'tests/fixtures/dictionary-wait-layout.json').read_text())
    guest = json.loads((root/'release/generated-go-inputs.json').read_text())
    if (guest['guest_sha256'] != pins['guest_sha256'] or
            guest['data_sha256'] != pins['data_sha256']):
        raise ValueError('dictionary fixture guest/data changed')
    files = {}
    for name, entry in pins['functions'].items():
        if entry['file'] not in files:
            files[entry['file']] = (root/entry['file']).read_text()
        validate_body(body(files[entry['file']], name), entry['normalized_sha256'])
    return pins


if __name__ == '__main__':
    validate()
    print('PASS: exact dictionary guest/body/data regression binding')
