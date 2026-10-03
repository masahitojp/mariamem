"""Mandatory focused consumer evidence fails closed; no public downloads in unit tests."""
import json
from pathlib import Path
import sys
import zipfile

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_consumer_smoke as smoke
from consumer_module import prepare_proxy, source_identity
from common import digest

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40
TAG = 'v0.3.0'
VERSION = '0.3.0'
NATIVE = 'b' * 64
WHEEL = 'c' * 64


def accepted(target='darwin-arm64'):
    lock = digest(ROOT / 'release/inputs.lock.json')
    prefix = f'https://github.com/masahitojp/mariamem/releases/download/{TAG}/'
    native = smoke.target_metadata(target)['bundle_name'] + '.tar.gz'
    go = {'result': 'PASS', 'stage': 'complete', 'module_version': TAG, 'native_version': VERSION,
          'cache_initially_empty': True, 'native_overrides': False,
          'steps': {s: 'PASS' for s in smoke.STEPS[:-1]},
          'receipt': {'tag': TAG, 'target': target, 'archive_sha256': NATIVE, 'inputs_lock_sha256': lock},
          'requests': [prefix + native, prefix + 'SHA256SUMS',
                       'https://api.github.com/repos/masahitojp/mariamem/releases/tags/' + TAG]}
    python = {'result': 'PASS', 'version': VERSION, 'wheel_sha256': WHEEL,
              'consumer_outside_repository': True, 'native_overrides': False, 'matched_rowcount': 1}
    environment = ({'system':'Darwin', 'architecture':'arm64', 'product_version':'15.7.9'} if target == smoke.DARWIN
                   else {'system':'Linux', 'architecture':'x86_64', 'distribution':'ubuntu', 'version_id':'24.04'})
    return {'schema_version':1, 'mode':'candidate', 'result':'PASS', 'source_sha':SHA,
            'git_tag':TAG, 'python_version':VERSION, 'target':target, 'native_sha256':NATIVE, 'wheel_sha256':WHEEL,
            'go_source_sha256':source_identity(ROOT), 'harness_sha256':{p:digest(ROOT / p) for p in smoke.HARNESS},
            'steps':{s:'PASS' for s in smoke.STEPS}, 'go':go, 'python':python, 'environment':environment}


@pytest.mark.parametrize('target', (smoke.DARWIN, smoke.UBUNTU))
def test_exact_required_consumer_evidence(target):
    smoke.verify_smoke(accepted(target), ROOT, SHA, TAG, VERSION, target, NATIVE, WHEEL)


@pytest.mark.parametrize('path,value', [
    (('result',), 'FAIL'), (('mode',), 'published'), (('source_sha',), 'd'*40),
    (('native_sha256',), 'd'*64), (('wheel_sha256',), 'd'*64), (('go_source_sha256',), 'd'*64),
    (('harness_sha256',), {}), (('go','cache_initially_empty'), False), (('go','native_overrides'), True),
    (('go','module_version'), 'v0.2.0'), (('go','receipt','archive_sha256'), 'd'*64),
    (('go','receipt','inputs_lock_sha256'), 'd'*64), (('go','requests'), []),
    (('python','matched_rowcount'), 0), (('python','native_overrides'), True),
    (('environment','product_version'), '27.0'),
])
def test_wrong_identity_or_semantics_never_ready(path, value):
    record = accepted()
    part = record
    for key in path[:-1]:
        part = part[key]
    part[path[-1]] = value
    with pytest.raises(ValueError):
        smoke.verify_smoke(record, ROOT, SHA, TAG, VERSION, smoke.DARWIN, NATIVE, WHEEL)


@pytest.mark.parametrize('step', smoke.STEPS)
@pytest.mark.parametrize('status', ('FAIL', 'SKIPPED', None))
def test_every_required_step_must_pass(step, status):
    record = accepted()
    if status is None:
        del record['steps'][step]
    else:
        record['steps'][step] = status
    with pytest.raises(ValueError, match='missing/skipped/failed'):
        smoke.verify_smoke(record, ROOT, SHA, TAG, VERSION, smoke.DARWIN, NATIVE, WHEEL)


@pytest.mark.parametrize('step', smoke.STEPS[:-1])
def test_nested_go_failure_cannot_be_masked_by_top_level_pass(step):
    record = accepted()
    record['go']['steps'][step] = 'FAIL'
    with pytest.raises(ValueError, match='Go smoke steps'):
        smoke.verify_smoke(record, ROOT, SHA, TAG, VERSION, smoke.DARWIN, NATIVE, WHEEL)


def test_candidate_distribution_does_not_repackage_archive(tmp_path):
    archive = tmp_path / 'mariamem-native-darwin-arm64.tar.gz'
    archive.write_bytes(b'exact frozen archive bytes')
    work = tmp_path / 'external'; work.mkdir()
    destination = smoke.candidate_distribution(archive, work, TAG, digest(archive))
    assert (destination / archive.name).read_bytes() == archive.read_bytes()
    assert (destination / 'SHA256SUMS').read_text() == f'{digest(archive)}  {archive.name}\n'
    assert json.loads((destination / 'release.json').read_text())['tag_name'] == TAG
    with pytest.raises(ValueError, match='bytes changed'):
        other = tmp_path / 'wrong'; other.mkdir()
        smoke.candidate_distribution(archive, other, TAG, 'd'*64)


def test_proxy_contains_exact_candidate_go_sources(tmp_path):
    proxy = prepare_proxy(ROOT, tmp_path, TAG)
    archive = proxy / smoke.MODULE / '@v' / f'{TAG}.zip'
    with zipfile.ZipFile(archive) as contents:
        prefix = f'{smoke.MODULE}@{TAG}/'
        for name in ('mariamem.go', 'native_version.go', 'internal/artifacts/download.go', 'release/inputs.lock.json'):
            assert contents.read(prefix + name) == (ROOT / name).read_bytes()
    assert json.loads((archive.parent / f'{TAG}.info').read_text())['Version'] == TAG


def test_guard_requires_consumer_file_before_ready(tmp_path):
    with pytest.raises(ValueError, match='required candidate consumer smoke missing'):
        smoke.require_candidate_smoke(tmp_path, SHA, TAG, VERSION, smoke.DARWIN, NATIVE, WHEEL)
    path = tmp_path / 'build/release/ci-consumer-smoke.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'result': 'FAIL'}))
    with pytest.raises(ValueError, match='missing/failed'):
        smoke.require_candidate_smoke(tmp_path, SHA, TAG, VERSION, smoke.DARWIN, NATIVE, WHEEL)
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    assert 'python candidate-source/scripts/generated_release_acceptance.py --root candidate-source' in workflow
    assert 'python candidate-source/scripts/ci_release_public_smoke.py --root candidate-source' in workflow
    assert 'test "$CONSUMER_RESULT" = success' in workflow
    assert 'candidate-source/build/release/ci-consumer-smoke.json' in workflow


def test_go_smoke_never_supplies_native_override_and_checks_empty_cache():
    source = (ROOT / smoke.HARNESS[2]).read_text()
    assert 'mariamem.Start(ctx, mariamem.Options{})' in source
    assert 'Options{NativeDir:' not in source
    assert 'smoke requires a new empty cache' in source
    assert 'orm.AutoMigrate(&User{})' in source
    assert source.count('orm.AutoMigrate(&User{})') == 2
