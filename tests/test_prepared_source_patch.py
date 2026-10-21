"""Exact patch boundaries and source-function proofs, not actual guest parity."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepared_source_patch as patch


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def tree(tmp_path):
    root, source = tmp_path / 'root', tmp_path / 'source'
    (root / 'guest').mkdir(parents=True)
    (root / 'tests/fixtures').mkdir(parents=True)
    files, delta = [], ''
    for name in ['sql/sql_prepare.cc', 'libmysqld/libmysql.c']:
        p = source / name
        p.parent.mkdir(parents=True)
        p.write_bytes(b'old\n')
        delta += '--- a/'+name+'\n+++ b/'+name+'\n@@ -1 +1 @@\n-old\n+new\n'
        files.append(dict(file=name, before_sha256=sha(b'old\n'), after_sha256=sha(b'new\n')))
    (root / 'guest/input.json').write_text(json.dumps(dict(source_commit='fixed',patches=[{
        'file':'guest/patches/common-portability.patch',
        'after_sha256':{'libmysqld/libmysql.c':sha(b'old\n')}}])))
    (root / 'guest/experimental.patch').write_text(delta)
    (root / 'guest/prepared_source_patch.json').write_text(json.dumps(dict(
        source_commit='fixed', patch_sha256=sha(delta.encode()), files=files)))
    (root / 'tests/fixtures/prepared-p2-source-functions.json').write_text(json.dumps(dict(
        file='libmysqld/libmysql.c', before={}, after={})))
    p = root / 'guest/prepared_source_patch.json'
    pin = json.loads(p.read_text())
    pin['component_fixture_sha256'] = sha((root / 'tests/fixtures/prepared-p2-source-functions.json').read_bytes())
    p.write_text(json.dumps(pin))
    return root, source


def test_exact_apply_and_double_application(tree):
    root, source = tree
    patch.apply(source, root)
    assert (source / 'libmysqld/libmysql.c').read_bytes() == b'new\n'
    with pytest.raises(ValueError, match='preimage'):
        patch.apply(source, root)


def test_check_all_preimages_before_any_mutation(tree):
    root, source = tree
    (source / 'libmysqld/libmysql.c').write_bytes(b'unrelated\nold\n')
    with pytest.raises(ValueError, match='preimage'):
        patch.apply(source, root)
    assert (source / 'sql/sql_prepare.cc').read_bytes() == b'old\n'


@pytest.mark.parametrize('field', ['source_commit', 'patch_sha256', 'component_fixture_sha256', 'before_sha256', 'after_sha256', 'file'])
def test_mutated_pins_rejected(tree, field):
    root, source = tree
    p = root / 'guest/prepared_source_patch.json'
    pin = json.loads(p.read_text())
    if field in ['source_commit', 'patch_sha256', 'component_fixture_sha256']:
        pin[field] = 'changed'
    else:
        pin['files'][1][field] = 'changed'
    p.write_text(json.dumps(pin))
    with pytest.raises(ValueError):
        patch.apply(source, root)


def test_command_failure_not_hidden(tree, monkeypatch):
    root, source = tree
    def fail(command, **kwargs):
        assert '--forward' in command and '--fuzz=0' in command and kwargs['check']
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(patch.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        patch.apply(source, root)


def test_repository_binding_and_time_repair_preserved():
    pin = patch.inputs(ROOT)
    old = json.loads((ROOT / 'guest/prepared_time_patch.json').read_text())
    assert pin['files'][0] == {k: old[k] for k in ['file', 'before_sha256', 'after_sha256']}


def test_repository_binding_is_after_portability():
    source=json.loads((ROOT/'guest/input.json').read_text())
    expected=source['patches'][0]['after_sha256']['libmysqld/libmysql.c']
    assert patch.inputs(ROOT)['files'][1]['before_sha256']==expected


def test_wrong_preparation_phase_rejected_before_mutation(tree):
    root,source=tree;p=root/'guest/input.json';data=json.loads(p.read_text())
    data['patches'][0]['after_sha256']['libmysqld/libmysql.c']='wrong-phase'
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='inputs changed'):
        patch.apply(source,root)
    assert (source/'sql/sql_prepare.cc').read_bytes()==b'old\n'


@pytest.mark.parametrize('version,wasi,expected', [
    ('before', True, (0, False)),
    ('after', True, (7, True)),
    ('after', False, (0, False)),
])
@pytest.mark.parametrize('sanitize', [False, True])
def test_real_source_functions(tmp_path, version, wasi, expected, sanitize):
    cc = shutil.which('clang') or shutil.which('cc')
    if not cc:
        if os.environ.get('MARIAMEM_REQUIRE_PREPARED_C') == '1':
            pytest.fail('C compiler required')
        pytest.skip('C compiler unavailable')
    fixture = json.loads((ROOT / 'tests/fixtures/prepared-p2-source-functions.json').read_text())
    (tmp_path / 'functions.inc').write_text('\n\n'.join(fixture[version].values())+'\n')
    binary = tmp_path / 'source-proof'
    command = [cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-DEMBEDDED_LIBRARY']
    if wasi:
        command += ['-D__wasi__']
    if sanitize:
        command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    subprocess.run(command + ['-I', str(tmp_path), str(ROOT / 'tests/fixtures/prepared_p2_source_harness.c'),
                              '-o', str(binary)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    record = json.loads(result.stdout)
    print(json.dumps(dict(version=version,wasi=wasi,sanitizers=sanitize,result=record)))
    assert (record['accepted_types'], record['metadata_refreshed']) == expected
