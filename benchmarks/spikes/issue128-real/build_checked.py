#!/usr/bin/env python3
"""Fresh target producer: unchanged canonical development builder, exact pins."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

repo = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo / 'scripts'))
from common import digest
from git_identity import inspect_ref, require_commit


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


started = time.monotonic()
identity = inspect_ref(repo, 'HEAD')
require_commit(repo, identity.source_commit)
assert identity.object_type == 'commit'
pin = json.loads((repo / 'guest/input.json').read_text())
assert pin['source_commit'] == '620a4b5624222048fece7fe1789978ae0675cae2'
assert pin['tag_object_sha'] == '308a50778fb4916ddde0d2923feea3d11dcc92c8'
fresh = {'work_empty': not any(Path('/work').iterdir()),
         'sdk_absent': not Path('/root/.wasixcc').exists(),
         'source_absent': not (repo / 'build/source').exists(),
         'unpack_absent': not (repo / 'build/unpack').exists()}
assert all(fresh.values()), fresh
write(Path('/output/preflight.json'), {'source_commit': identity.source_commit,
      'target_source_commit': pin['source_commit'], 'tag_object_sha': pin['tag_object_sha'],
      'fresh_conditions': fresh, 'builder_sha256': digest(repo / 'scripts/build_generated_guest.py')})
spec = importlib.util.spec_from_file_location('builder', repo / 'scripts/build_generated_guest.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
original = builder.observed_run


def observed(*args, **kwargs):
    result = original(*args, **kwargs)
    if kwargs.get('phase') == 'guest:prepare:0':
        source = repo / 'build/source'
        record = json.loads((repo / 'build/prepared-source.json').read_text())
        for name, expected in record['modified_files'].items():
            assert digest(source / name) == expected, name
        files = {str(p.relative_to(source)): digest(p) for p in sorted(source.rglob('*'))
                 if p.is_file() and not p.is_symlink()}
        write(Path('/output/prepared-tree.json'), files)
        write(Path('/output/prepared-proof.json'), {
            'target_source_commit': pin['source_commit'],
            'source_files': len(files), 'files_sha256': digest(Path('/output/prepared-tree.json')),
            'modified_files': record['modified_files'],
            'prepared_record_sha256': digest(repo / 'build/prepared-source.json'),
            'shared_overlay': record['source_overlay'],
            'semantic_expectations': 'Original prepared function-body, allocator, UCA numeric and routine metadata checks unchanged; runtime still pending'})
    return result


builder.observed_run = observed
sys.argv = [str(repo / 'scripts/build_generated_guest.py'), '--development-output', '/output/artifact']
try:
    builder.main()
except BaseException as error:
    write(Path('/output/producer-result.json'), {'fresh_canonical_builder_success': False,
          'source_commit': identity.source_commit, 'target_source_commit': pin['source_commit'],
          'wall_seconds': time.monotonic() - started,
          'exception': type(error).__name__, 'error': str(error)})
    raise
else:
    path = Path('/output/artifact/guest.json')
    record = json.loads(path.read_text())
    record.update(fresh_canonical_builder_success=True, fresh_target_producer_success=True,
                  build_method='one fresh canonical development invocation; no incremental continuation',
                  target_source_commit=pin['source_commit'], target_tag_object_sha=pin['tag_object_sha'])
    write(path, record)
    write(Path('/output/producer-result.json'), {'fresh_canonical_builder_success': True,
          'source_commit': identity.source_commit, 'target_source_commit': pin['source_commit'],
          'guest_sha256': record['guest_sha256'], 'wall_seconds': time.monotonic() - started})
