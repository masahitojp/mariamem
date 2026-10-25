"""Bind unchanged canonical dump bytes and producer inputs to an exact candidate."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

from linux_acquisition import ROOT, require, source_identity

HERE = Path(__file__).resolve().parent
ORIGIN = '6d81a2f99d0b5bd09bb5ab48dbf1ae23ca27e149'
PARKED = '03cad716fd3a0a44558ef0133566b85f6ec8b1ba'
DUMP_SHA256 = '081ef0273c3625cb1d2a143415b90e9845bc2132312853a047eed09c8807e87c'
ORIGIN_MANIFEST_SHA256 = '2850011163620f3a9e6c8dd0b343e54835c6d8b475706b0671302121de8a0b10'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_host_delta(root):
    """Only the separately approved, hash-pinned host correction may differ."""
    approval = json.loads((root/'tests/dump_import_acceptance/approved-host-delta.json').read_text())
    require(approval['baseline_source_commit'] == ORIGIN, 'host delta baseline changed')
    changed = subprocess.check_output(['git', 'diff', '--name-only', ORIGIN, 'HEAD', '--',
        'cmd', 'internal', 'python/mariamem', 'python/setup.cfg', 'guest', 'go.mod', 'go.sum', 'release'], cwd=root, text=True)
    # Include local edits during development as well as exact committed candidates.
    local = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD', '--',
        'cmd', 'internal', 'python/mariamem', 'python/setup.cfg', 'guest', 'go.mod', 'go.sum', 'release'], cwd=root, text=True)
    paths = set(changed.splitlines()) | set(local.splitlines())
    paths.update(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--',
        'cmd', 'internal', 'python/mariamem', 'python/setup.cfg', 'guest', 'go.mod', 'go.sum', 'release'], cwd=root, text=True).splitlines())
    require(paths == set(approval['files']) | {'python/mariamem/dump.py', 'python/mariamem/__init__.py', 'python/setup.cfg'}, 'unapproved runtime/build input delta')
    for name, pin in approval['files'].items():
        require(name in {'internal/guest/guest.go', 'internal/guest/status_test.go',
                         'internal/mysqlwire/status_decode_test.go'}, 'unapproved host delta path')
        original = subprocess.run(['git', 'show', ORIGIN+':'+name], cwd=root, capture_output=True)
        require((digest(original.stdout) if original.returncode == 0 else None) == pin['before_sha256'],
                'host delta original hash mismatch: '+name)
        committed = subprocess.run(['git', 'show', 'HEAD:'+name], cwd=root, capture_output=True)
        if name in changed.splitlines():
            require(committed.returncode == 0 and digest(committed.stdout) == pin['after_sha256'],
                    'host delta committed hash mismatch: '+name)
        require(digest((root/name).read_bytes()) == pin['after_sha256'], 'host delta hash mismatch: '+name)
    return approval


def validate_inputs(root=ROOT, here=HERE):
    raw = (here/'input/application.sql').read_bytes()
    manifest_raw = (here/'input/input-manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    require(digest(raw) == manifest['dump_sha256'] == DUMP_SHA256, 'canonical dump changed')
    require(manifest['source_commit'] == ORIGIN and manifest['result'] == 'PASS', 'origin identity changed')
    require(digest(manifest_raw) == ORIGIN_MANIFEST_SHA256, 'original manifest bytes changed')
    inputs = {}
    for name, expected in manifest['migration_owner'].items():
        actual = digest((root/name).read_bytes())
        require(actual == expected, 'migration/seed input changed: '+name)
        inputs[name] = actual
    producer = 'tests/dump_import_acceptance/producer.py'
    original_producer = subprocess.check_output(['git', 'show', ORIGIN+':tests/dump_import_spike/producer.py'], cwd=root)
    require((root/producer).read_bytes() == original_producer, 'producer input changed')
    inputs[producer] = digest(original_producer)
    tree = ast.parse(original_producer)
    literals = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id in ['EXTENSION', 'VALUES', 'OPTIONS']}
    for key, name in [('extension_sql', 'EXTENSION'), ('extension_values_decimal_strings_binary_hex', 'VALUES'),
                      ('producer_options', 'OPTIONS')]:
        require(manifest[key] == literals[name], 'manifest/producer mismatch: '+key)
    approval = validate_host_delta(root)
    return dict(canonical_dump_sha256=DUMP_SHA256, origin_manifest_sha256=digest(manifest_raw),
                verified_inputs=inputs, origin_source_commit=ORIGIN, preserved_artifact_source_commit=PARKED,
                approved_host_delta=approval, verified_product_sources={name: digest((root/name).read_bytes()) for name in ['python/mariamem/dump.py', 'python/mariamem/__init__.py', 'python/setup.cfg']})


def producer_receipt(directory, expected_source):
    directory = Path(directory)
    manifest_raw = (directory/'input-manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    origin = json.loads((HERE/'input/input-manifest.json').read_text())
    raw = (directory/'application.sql').read_bytes()
    require(manifest['source_commit'] == expected_source and manifest['result'] == 'PASS',
            'candidate producer execution/source mismatch')
    require(digest(raw) == manifest['dump_sha256'] == DUMP_SHA256 and raw == (HERE/'input/application.sql').read_bytes(),
            'candidate producer did not reproduce exact canonical dump bytes')
    for key in ['migration_owner', 'base_users', 'base_addresses', 'revision', 'extension_sql',
                'extension_values_decimal_strings_binary_hex', 'producer_options', 'server',
                'sql_mode', 'timezone', 'charset', 'collation', 'definer', 'sql_security', 'excluded']:
        require(manifest[key] == origin[key], 'candidate producer inputs differ: '+key)
    return dict(result='PASS', source_commit=expected_source, manifest_sha256=digest(manifest_raw),
                dump_sha256=digest(raw), reproduced_exact_canonical_bytes=True)


def bind(expected_source, producer_output=None):
    source = source_identity(expected_source)
    result = dict(schema=1, result='INPUTS_VERIFIED', source_commit=source['source_commit'],
                  **validate_inputs(), dump_regenerated=False,
                  provenance='Original producer PASS remains bound to origin_source_commit; fresh candidate production is recorded separately.')
    if producer_output is not None:
        result['candidate_producer'] = producer_receipt(producer_output, expected_source)
        result.update(result='BOUND', dump_regenerated=True)
    return result


def check_binding(path, expected_source):
    saved = json.loads(Path(path).read_text())
    require(saved == bind(expected_source, Path(path).parent/'candidate-producer'), 'candidate/input binding mismatch')
    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--producer-output', type=Path, required=True)
    args = parser.parse_args()
    report = bind(args.expected_source_commit, args.producer_output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists(), 'refuse stale binding')
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'result': report['result'], 'source_commit': report['source_commit'],
                      'canonical_dump_sha256': report['canonical_dump_sha256']}))


if __name__ == '__main__':
    main()
