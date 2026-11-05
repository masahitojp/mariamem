#!/usr/bin/env python3
"""Validate/re-express prototype numeric inputs; never install a guest or qualify it."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
RAW_BYTES = 918016
MAX_COMPRESSED_BYTES = 65536


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(), object_pairs_hook=unique)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def render_header(levels):
    parts = ['static const MY_UCA_LEVEL_BOOSTER prepared[3] = {\n']
    def rows(values, width):
        return ',\n'.join('{{' + ','.join(map(str, values[i:i+width])) + '}}'
                         for i in range(0, len(values), width))
    for raw in levels:
        need(len(raw) == RAW_BYTES, 'invalid table size')
        values = struct.unpack('<459008H', raw)
        parts.append('{\n{' + rows(values[:327680], 5) + '},\n{' +
                     rows(values[327680:458752], 2) + '},\n{' +
                     ','.join(map(str, values[458752:])) + '}\n},\n')
    return (''.join(parts) + '};\n').encode()


def validate(bundle, root=ROOT, source=None):
    manifest = read_json(bundle/'input.json')
    keys = {'schema', 'scope', 'prototype_source_commit', 'mariadb_source_commit',
            'source_archive_sha256', 'pristine_files_sha256', 'unicode_input_sha256',
            'raw_bytes_per_level', 'header_sha256', 'tables'}
    need(set(manifest) == keys, 'unknown/missing manifest fields')
    need(type(manifest['schema']) is int and manifest['schema'] == 1, 'unsupported schema')
    need(manifest['scope'] == 'PREPARATION_ONLY_NOT_USED_BY_GUEST', 'unsupported scope')
    need(type(manifest['raw_bytes_per_level']) is int and
         manifest['raw_bytes_per_level'] == RAW_BYTES, 'unsupported table layout')
    guest = read_json(root/'guest/input.json')
    inputs = read_json(root/'release/inputs.lock.json')['inputs']
    archives = [x for x in inputs if x['name'] == guest['source_input']]
    need(len(archives) == 1, 'ambiguous source archive')
    need(manifest['mariadb_source_commit'] == guest['source_commit'] == archives[0]['revision'],
         'unsupported MariaDB source identity')
    need(manifest['source_archive_sha256'] == archives[0]['sha256'], 'source archive mismatch')
    need(set(manifest['pristine_files_sha256']) == {'strings/ctype-uca.c', 'include/m_ctype.h'},
         'unsupported source-file inventory')
    source_check = 'PINS_ONLY_NO_PRISTINE_TREE_SUPPLIED'
    if source is not None:
        for name, expected in manifest['pristine_files_sha256'].items():
            need(digest((source/name).read_bytes()) == expected, 'pristine source mismatch: ' + name)
        need(digest((source/'mysql-test/std_data/unicode/allkeys1400.txt').read_bytes()) ==
             manifest['unicode_input_sha256'], 'Unicode input mismatch')
        source_check = 'PRISTINE_SOURCE_HASHES_PASS'
    tables = manifest['tables']
    need(type(tables) is list and len(tables) == 3, 'expected exactly three levels')
    levels = []
    for level, table in enumerate(tables):
        need(set(table) == {'level', 'file', 'compressed_sha256', 'raw_sha256'},
             'unknown/missing table fields')
        need(type(table['level']) is int and table['level'] == level, 'duplicate/reordered level')
        need(table['file'] == f'level{level}.u16le.json', 'unsafe/unexpected table path')
        path = bundle/table['file']
        need(not path.is_symlink(), 'table symlink rejected')
        need(path.stat().st_size <= (MAX_COMPRESSED_BYTES*4//3 + 128), 'table text too large')
        container = read_json(path)
        need(set(container) == {'format', 'data'} and
             container['format'] == 'gzip-base64-u16le' and type(container['data']) is str,
             'unsupported numeric container')
        try:
            blob = base64.b64decode(container['data'], validate=True)
        except ValueError as exc:
            raise ValueError('invalid numeric base64') from exc
        need(len(blob) <= MAX_COMPRESSED_BYTES, 'compressed table too large')
        need(digest(blob) == table['compressed_sha256'], 'compressed hash mismatch')
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
                raw = stream.read(RAW_BYTES + 1)
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError('invalid gzip framing') from exc
        need(len(raw) == RAW_BYTES, 'expanded table size mismatch')
        need(digest(raw) == table['raw_sha256'], 'numeric table hash mismatch')
        levels.append(raw)
    header = render_header(levels)
    need(digest(header) == manifest['header_sha256'], 'rendered header differs from prototype')
    return header, {'result': 'INPUT_PACKAGE_PASS', 'scope': manifest['scope'],
                    'source_check': source_check, 'header_sha256': digest(header),
                    'header_bytes': len(header), 'numeric_bytes': 3*RAW_BYTES,
                    'guest_build': 'NOT_RUN', 'guest_integration': 'NOT_IMPLEMENTED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--source-dir', type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--emit-header', type=Path)
    actions.add_argument('--check-header', type=Path)
    args = parser.parse_args(argv)
    header, result = validate(args.bundle, args.root, args.source_dir)
    if args.emit_header:
        with args.emit_header.open('xb') as output:
            output.write(header)
    if args.check_header:
        need(args.check_header.read_bytes() == header, 'existing header differs')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
