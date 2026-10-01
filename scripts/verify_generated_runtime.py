#!/usr/bin/env python3
"""Verify committed generated source and supported built-in executable identities."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re

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
    inventory = {str(p.relative_to(source)):digest(p) for p in source.rglob('*')
                 if p.is_file() and p.name != 'provenance.json'}
    require(inventory == record['files_sha256'], 'generated source inventory changed; regenerate')
    require(record['guest_sha256'] == json.loads(pins.read_text())['guest_sha256'], 'guest identity changed')
    images = ROOT/'internal/builtinruntime'
    metadata = json.loads((images/'provenance.json').read_text())
    require(metadata['guest_sha256'] == record['guest_sha256'], 'image guest identity changed')
    require(metadata['generated_provenance_sha256'] == digest(source/'provenance.json'), 'image generated-source binding changed')
    require(metadata['entry_sha256'] == digest(ROOT/'cmd/mariamem-guest/main.go'), 'image entry binding changed')
    require(set(metadata['images']) == {'darwin-arm64','linux-amd64'}, 'platform image inventory changed')
    for target, image in metadata['images'].items():
        path = images/('image_'+target.replace('-','_')+'.go')
        require(digest(path) == image['source_sha256'], target+' image source changed')
        data, identity = re.search(r'return "([A-Za-z0-9+/=]+)", "([0-9a-f]+)"', path.read_text()).groups()
        compressed = base64.b64decode(data, validate=True)
        require(len(compressed) == image['compressed_bytes'], target+' compressed size changed')
        binary = gzip.decompress(compressed)
        require(len(binary) == image['binary_bytes'], target+' executable size changed')
        require(hashlib.sha256(binary).hexdigest() == identity == image['sha256'], target+' executable checksum changed')
    print('PASS: generated source inventory, guest identity and both platform images')


if __name__ == '__main__':
    main()
