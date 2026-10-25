"""Canonical bytes cannot be rebound after changing dump, manifest or inputs."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent/'dump_import_spike'))
import bind_input


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
                                 'tests/dump_import_spike/producer.py'])
def test_changed_source_input_is_rejected(name):
    original = Path.read_bytes
    target = bind_input.ROOT/name
    def changed(path):
        return b'changed input' if path == target else original(path)
    with patch.object(Path, 'read_bytes', changed), pytest.raises(ValueError, match='input changed'):
        bind_input.validate_inputs()


def test_old_origin_pass_is_not_relabelled_as_candidate_generation():
    with patch.object(bind_input, 'source_identity', return_value={'source_commit': '1'*40}):
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
