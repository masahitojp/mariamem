"""Fail-closed canonical portability input and application boundaries."""
import copy
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import ROOT, LOCK
from guest_input import descriptor, apply_series, safe_relative


def test_registered_input_and_order():
    value = descriptor(ROOT, LOCK)
    assert value['version'] == '12.3.3'
    assert [p['file'] for p in value['patches']] == [
        'guest/patches/common-portability.patch', 'guest/patches/12.3.3-redo.patch']
    assert sum(len(p['after_sha256']) for p in value['patches']) == 18


@pytest.mark.parametrize('field', ['revision', 'sha256'])
def test_wrong_source_identity_rejected(field):
    lock = copy.deepcopy(LOCK)
    next(e for e in lock['inputs'] if e['name'] == 'mariadb')[field] = '0' * 64
    with pytest.raises(ValueError, match='mismatch'):
        descriptor(ROOT, lock)


def test_changed_patch_rejected(tmp_path):
    value = json.loads((ROOT / 'guest/input.json').read_text())
    (tmp_path / 'guest').mkdir()
    (tmp_path / 'guest/input.json').write_text(json.dumps(value))
    for patch in value['patches']:
        path = tmp_path / patch['file']; path.parent.mkdir(exist_ok=True)
        path.write_bytes((ROOT / patch['file']).read_bytes() + b'\n')
    with pytest.raises(ValueError, match='patch identity'):
        descriptor(tmp_path, LOCK)


def test_modified_preimage_stops_before_application(tmp_path):
    patch = {'file': 'unused.patch', 'before_sha256': {'input.c': '0' * 64}, 'after_sha256': {}}
    (tmp_path / 'input.c').write_text('changed')
    with pytest.raises(ValueError, match='preimage differs'):
        apply_series(ROOT, tmp_path, {'patches': [patch]})


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a/../../escape'])
def test_paths_cannot_escape(name):
    with pytest.raises(ValueError, match='unsafe'):
        safe_relative(name)


def test_failed_application_is_not_ignored(tmp_path):
    import hashlib
    import subprocess
    content = b'original\n'
    (tmp_path / 'input.c').write_bytes(content)
    # Correct declared preimage, but a hunk that cannot apply.
    (tmp_path / 'bad.patch').write_text('--- a/input.c\n+++ b/input.c\n@@ -1 +1 @@\n-other\n+new\n')
    patch = {'file': 'bad.patch', 'before_sha256': {'input.c': hashlib.sha256(content).hexdigest()},
             'after_sha256': {'input.c': '0' * 64}}
    with pytest.raises(subprocess.CalledProcessError):
        apply_series(tmp_path, tmp_path, {'patches': [patch]})


def test_wrong_postimage_is_not_ignored(tmp_path):
    import hashlib
    content = b'original\n'
    (tmp_path / 'input.c').write_bytes(content)
    (tmp_path / 'apply.patch').write_text('--- a/input.c\n+++ b/input.c\n@@ -1 +1 @@\n-original\n+new\n')
    patch = {'file': 'apply.patch', 'before_sha256': {'input.c': hashlib.sha256(content).hexdigest()},
             'after_sha256': {'input.c': '0' * 64}}
    with pytest.raises(ValueError, match='postimage differs'):
        apply_series(tmp_path, tmp_path, {'patches': [patch]})
