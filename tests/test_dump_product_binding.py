"""Canonical bytes cannot be rebound after changing dump, manifest or inputs."""
import json
from pathlib import Path
import shutil
import sys
import subprocess
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent/'dump_import_acceptance'))
import bind_input
import linux_acquisition


def test_existing_canonical_input_matches_current_producer_and_migrations():
    result = bind_input.validate_inputs()
    assert result['canonical_dump_sha256'] == bind_input.DUMP_SHA256
    assert result['origin_source_commit'] == bind_input.ORIGIN
    assert len(result['verified_inputs']) == 9


@pytest.mark.parametrize('target', ['application.sql', 'input-manifest.json'])
def test_changed_artifact_bytes_are_rejected(target, tmp_path):
    here = tmp_path/'fixture'
    shutil.copytree(bind_input.HERE/'input', here/'input')
    file = here/'input'/target
    file.write_bytes(file.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='changed'):
        bind_input.validate_inputs(here=here)


@pytest.mark.parametrize('name', ['tests/preparation_migration_acceptance/application.py',
                                 'tests/preparation_migration_acceptance/conftest.py',
                                 'tests/dump_import_acceptance/producer.py'])
def test_changed_source_input_is_rejected(name):
    original = Path.read_bytes
    target = bind_input.ROOT/name
    def changed(path):
        return b'changed input' if path == target else original(path)
    with patch.object(Path, 'read_bytes', changed), pytest.raises(ValueError, match='input changed'):
        bind_input.validate_inputs()


def test_old_origin_pass_is_not_relabelled_as_candidate_generation():
    with patch.object(bind_input, 'current_source', return_value={'source_commit': '1'*40, 'source_tree_sha': '2'*40}):
        result = bind_input.bind('1'*40)
    assert result['source_commit'] == '1'*40
    assert result['origin_source_commit'] == bind_input.ORIGIN
    assert result['result'] == 'INPUTS_VERIFIED' and result['dump_regenerated'] is False
    assert 'candidate_producer' not in result


def test_fresh_producer_receipt_requires_exact_candidate_and_bytes(tmp_path):
    origin = json.loads((bind_input.HERE/'input/input-manifest.json').read_text())
    candidate = '1'*40
    origin['source_commit'] = candidate
    (tmp_path/'input-manifest.json').write_text(json.dumps(origin))
    shutil.copy2(bind_input.HERE/'input/application.sql', tmp_path/'application.sql')
    receipt = bind_input.producer_receipt(tmp_path, candidate)
    assert receipt['source_commit'] == candidate and receipt['reproduced_exact_canonical_bytes'] is True
    with pytest.raises(ValueError, match='execution/source mismatch'):
        bind_input.producer_receipt(tmp_path, '2'*40)
    (tmp_path/'application.sql').write_bytes(b'changed dump')
    with pytest.raises(ValueError, match='exact canonical dump bytes'):
        bind_input.producer_receipt(tmp_path, candidate)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Binding test')
    git('config', 'user.email', 'binding@example.test')
    (tmp_path/'source').write_text('baseline')
    git('add', '.')
    git('commit', '-qm', 'baseline')
    monkeypatch.setattr(bind_input, 'ROOT', tmp_path)
    monkeypatch.setattr(linux_acquisition, 'ROOT', tmp_path)
    return tmp_path, git


def test_current_source_accepts_new_committed_runtime_without_experiment_history(repository):
    root, git = repository
    first = git('rev-parse', 'HEAD')
    old = bind_input.current_source(first)
    (root/'internal').mkdir()
    (root/'internal/new.go').write_text('package internal\n')
    git('add', '.')
    git('commit', '-qm', 'ordinary future runtime change')
    second = git('rev-parse', 'HEAD')
    current = bind_input.current_source(second)
    assert current['source_commit'] == second != first
    assert current['source_tree_sha'] != old['source_tree_sha']
    with pytest.raises(ValueError): bind_input.current_source(first)


@pytest.mark.parametrize('kind', ['tracked', 'untracked', 'tag', 'abbreviated'])
def test_current_source_rejects_dirty_or_noncommit_identity(repository, kind):
    root, git = repository
    source = git('rev-parse', 'HEAD')
    if kind == 'tracked': (root/'source').write_text('dirty')
    if kind == 'untracked': (root/'extra').write_text('dirty')
    if kind == 'tag':
        git('tag', '-am', 'tag object', 'v-test')
        source = git('rev-parse', 'v-test')
    if kind == 'abbreviated': source = source[:7]
    with pytest.raises(ValueError): bind_input.current_source(source)


def test_saved_binding_rejects_source_tree_and_product_hash_mutations(tmp_path):
    current = dict(source_commit='1'*40, source_tree_sha='2'*40,
                   verified_product_sources={'python/mariamem/dump.py': '3'*64})
    path = tmp_path/'binding.json'
    for mutated in [dict(current, source_commit='4'*40), dict(current, source_tree_sha='5'*40),
                    dict(current, verified_product_sources={'python/mariamem/dump.py': '6'*64})]:
        path.write_text(json.dumps(mutated))
        with patch.object(bind_input, 'bind', return_value=current), pytest.raises(ValueError, match='binding mismatch'):
            bind_input.check_binding(path, '1'*40)


def test_binding_rechecks_source_after_reading_inputs():
    first = dict(source_commit='1'*40, source_tree_sha='2'*40)
    second = dict(first, source_tree_sha='3'*40)
    with patch.object(bind_input, 'current_source', side_effect=[first, second]), pytest.raises(ValueError, match='source changed'):
        bind_input.bind('1'*40)
