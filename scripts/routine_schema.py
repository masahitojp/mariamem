"""Generate the one pinned proc DDL and independently reviewed metadata contract.

This deliberately supports only the adopted proc definition, not arbitrary SQL.
Source drift fails preparation; it is not a runtime schema-upgrade mechanism.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'wasm/routine_schema_sql.inc'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parts(text, separator=','):
    result, start, depth, quote, i = [], 0, 0, None, 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == '\\':
                i += 2
                continue
            if c == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth < 0:
                raise ValueError('unbalanced proc definition')
        elif c == separator and depth == 0:
            result.append(text[start:i].strip())
            start = i + 1
        i += 1
    if quote or depth:
        raise ValueError('unbalanced proc definition')
    result.append(text[start:].strip())
    return result


def column_type(text):
    quote, depth, end = False, 0, 0
    for end, c in enumerate(text):
        if c == "'":
            quote = not quote
        elif not quote:
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c.isspace() and depth == 0:
                break
    else:
        end = len(text)
    value, attrs = text[:end], text[end:]
    quote, normalized = False, []
    for c in value:
        if c == "'":
            quote = not quote
        if quote or not c.isspace():
            normalized.append(c if quote else c.lower())
    value = ''.join(normalized)
    if not re.fullmatch(r'(?:char\(\d+\)|varchar\(\d+\)|blob|longblob|timestamp|text|(?:enum|set)\(.+\))', value):
        raise ValueError('unreviewed proc column type: ' + value)
    return value, attrs


def definition(ddl):
    prefix = 'CREATE TABLE IF NOT EXISTS proc ('
    if not ddl.startswith(prefix):
        raise ValueError('proc DDL anchor changed')
    # The adopted table has only this one top-level closing-parenthesis suffix.
    body, tail = ddl[len(prefix):].rsplit(')', 1)
    engine = re.search(r'\bengine=(\w+)', tail, re.I)
    collation = re.search(r'\bCOLLATE (\w+)', tail, re.I)
    if not engine or not collation:
        raise ValueError('proc engine/collation not found')
    columns, key = [], None
    for item in parts(body):
        if item.startswith('PRIMARY KEY '):
            match = re.fullmatch(r'PRIMARY KEY \((\w+(?:,\w+)*)\)', item)
            if not match:
                raise ValueError('unreviewed proc primary key')
            key = match[1].split(',')
            continue
        name, type_and_attrs = item.split(None, 1)
        if not re.fullmatch(r'[a-z_][a-z_0-9]*', name):
            raise ValueError('unreviewed proc column name')
        kind, attrs = column_type(type_and_attrs)
        collate = re.search(r'\bcollate (\w+)', attrs, re.I)
        charset = ((collate[1] if collate else collation[1])
                   if kind.startswith(('char(', 'varchar(', 'enum(', 'set(')) or kind == 'text' else None)
        nullable = 'NO' if re.search(r'\bNOT\s+NULL\b', attrs, re.I) else 'YES'
        columns.append([name, kind, charset, nullable])
    if len(columns) != 22 or key != ['db', 'name', 'type']:
        raise ValueError('unreviewed proc layout')
    return dict(columns=columns, primary_key=key, engine=engine[1])


def prepare(source, *, root=ROOT):
    source, root = Path(source), Path(root)
    pin = json.loads((root/'guest/routine_schema.json').read_text())
    lock = json.loads((root/'release/inputs.lock.json').read_text())
    upstream = next(p for p in lock['inputs'] if p['name'] == 'mariadb')
    if (pin['version'] != 1 or pin['source_commit'] != upstream['revision']
            or pin['server_version'] != upstream['version']
            or pin['source_file'] != 'scripts/mariadb_system_tables.sql'):
        raise ValueError('routine source identity mismatch')
    version = dict(re.findall(r'^MYSQL_VERSION_(MAJOR|MINOR|PATCH)=(\d+)$',
                              (source/'VERSION').read_text(), re.M))
    if '.'.join(version[k] for k in ['MAJOR', 'MINOR', 'PATCH']) != pin['server_version']:
        raise ValueError('routine source version mismatch')
    raw = (source/pin['source_file']).read_bytes()
    if sha(raw) != pin['source_file_sha256']:
        raise ValueError('routine SQL source hash mismatch')
    matches = [line for line in raw.decode().splitlines()
               if line.startswith('CREATE TABLE IF NOT EXISTS proc (')]
    if len(matches) != 1 or sha(matches[0].encode()) != pin['ddl_sha256']:
        raise ValueError('routine DDL identity/anchor mismatch')
    ddl = matches[0]
    spec = definition(ddl)
    if any(spec[k] != pin[k] for k in ['columns', 'primary_key', 'engine']):
        raise ValueError('proc DDL differs from reviewed native metadata')
    copyright = raw.decode().split('SET NAMES', 1)[0]
    if '*/' in copyright:
        raise ValueError('unexpected license header delimiter')
    lines = ['/* Generated from ' + pin['source_file'] + ' @ ' + pin['source_commit'],
             copyright, '*/', '#define ROUTINE_SCHEMA_DDL_SHA256 ' + json.dumps(pin['ddl_sha256']),
             'static const char routine_schema_ddl[] = ' + json.dumps(ddl) + ';',
             'static const char *const routine_schema_columns[][4] = {']
    for row in spec['columns']:
        lines.append('  {' + ', '.join('NULL' if v is None else json.dumps(v) for v in row) + '},')
    lines += ['};', 'static const char *const routine_schema_key[] = {' +
              ', '.join(json.dumps(v) for v in spec['primary_key']) + '};',
              'static const char routine_schema_engine[] = ' + json.dumps(spec['engine']) + ';', '']
    text = '\n'.join(lines)
    target = source/HEADER
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('routine generated header already exists')
    target.write_text(text)
    return {'source_commit':pin['source_commit'], 'source_file_sha256':sha(raw),
            'ddl_sha256':pin['ddl_sha256'],
            'metadata_sha256':sha(json.dumps(spec,sort_keys=True,separators=(',', ':')).encode()),
            'header':HEADER, 'header_sha256':sha(text.encode())}
