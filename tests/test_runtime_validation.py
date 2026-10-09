"""Authenticate runtime reuse without building or executing MariaDB."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import runtime_validation as runtime

SHA = 'a' * 40
VERSION = 'MAJOR=0\nMINOR=4\nPATCH=3\nSTAGE=""\nSERIAL=0\nGIT_TAG=f"v{MAJOR}.{MINOR}.{PATCH}"\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def intent():
    return {'version': 2, 'repository': 'masahitojp/mariamem', 'workflow': runtime.WORKFLOW,
            'basis_commit': SHA, 'run_id': 7,
            'artifacts': {p: {'id': i + 1, 'zip_sha256': 'b' * 64}
                          for i, p in enumerate(runtime.PLATFORMS)}}


def records(platform):
    mac = platform == runtime.PLATFORMS[0]
    inventory = {n: 'd'*64 for n in ('mariamem.go', 'scripts/verify.py',
                 'scripts/validate_product_candidate.py', runtime.WORKFLOW)}
    return {
        'inputs.json': {'version':1, 'result':'PASS', 'candidate_sha':SHA,
            'contract':runtime.CONTRACT, 'python':'3.14.2', 'native_platform':platform,
            'environment': {'system':'Darwin' if mac else 'Linux',
                'architecture':'arm64' if mac else 'x86_64',
                'product_version':'15.7', 'distribution':'ubuntu', 'version_id':'24.04'},
            'go_version':'go version go1.26.8 ' + ('darwin/arm64' if mac else 'linux/amd64'),
            'guest_sha256':'c'*64, 'git_tree_sha256':'f'*64,
            'source_inventory_sha256':digest(json.dumps(inventory).encode()),
            'harness_sha256':{n:h for n,h in inventory.items() if n!='mariamem.go'}},
        'correctness.json': {'version':1, 'contract':runtime.CONTRACT, 'result':'PASS',
            'candidate_sha':SHA, 'boundaries':sorted(runtime.BOUNDARIES)},
        'source-inventory.json':inventory,
        'commands.json':[{'name':n, 'exit_code':0, 'argv':['python','scripts/verify.py',c]}
                         for n,c in [('source-unit-checks','check'),('runtime-integration','integration')]],
    }


def archive(data, extras=None, checksum_change=None):
    files = {n: json.dumps(v).encode() for n, v in data.items()}
    hashes = {n: digest(v) for n, v in files.items()}
    if checksum_change:
        checksum_change(hashes)
    files['SHA256SUMS.json'] = json.dumps(hashes).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zipped:
        for n, v in files.items():
            zipped.writestr(n, v)
        for n, v in extras or []:
            zipped.writestr(n, v)
    return output.getvalue()


class API:
    def __init__(self, platform):
        self.pin = intent()
        self.payload = archive(records(platform))
        self.pin['artifacts'][platform]['zip_sha256'] = digest(self.payload)
        self.run = {'path': runtime.WORKFLOW, 'repository': {'full_name': self.pin['repository']},
                    'status': 'completed', 'conclusion': 'success', 'head_sha': SHA}
        self.jobs = [{'name': 'Runtime qualification — ' + p, 'status': 'completed', 'conclusion': 'success'}
                     for p in runtime.PLATFORMS]
        self.artifacts = [{'id': self.pin['artifacts'][platform]['id'],
            'name': f'runtime-{platform}-{SHA}', 'expired': False,
            'digest': 'sha256:' + digest(self.payload), 'size_in_bytes': len(self.payload)}]
        self.downloads = 0

    def json(self, path):
        if '/jobs?' in path:
            return {'jobs': self.jobs}
        if '/artifacts?' in path:
            return {'artifacts': self.artifacts}
        return self.run

    def request(self, path):
        self.downloads += 1
        return io.BytesIO(self.payload)


@pytest.mark.parametrize('platform', runtime.PLATFORMS)
def test_authenticated_native_archive(tmp_path, platform):
    api = API(platform)
    target = tmp_path / 'proof.zip'
    runtime.fetch_qualification(api, api.pin, platform, target)
    inventory, receipt = runtime.evidence(target, api.pin, platform)
    assert inventory == records(platform)['source-inventory.json']
    assert receipt['contract'] == runtime.CONTRACT
    assert receipt['zip_sha256'] == digest(api.payload)


@pytest.mark.parametrize('kind', ['workflow', 'repository', 'source', 'failed', 'missing-job',
    'failed-job', 'artifact-name', 'artifact-id', 'expired', 'digest', 'oversize', 'duplicate'])
def test_origin_failures_stop_before_download(tmp_path, kind):
    p = runtime.PLATFORMS[0]
    api = API(p)
    if kind == 'workflow': api.run['path'] = '.github/workflows/other.yml'
    if kind == 'repository': api.run['repository']['full_name'] = 'other/project'
    if kind == 'source': api.run['head_sha'] = 'f' * 40
    if kind == 'failed': api.run['conclusion'] = 'failure'
    if kind == 'missing-job': api.jobs.pop()
    if kind == 'failed-job': api.jobs[1]['conclusion'] = 'failure'
    if kind == 'artifact-name': api.artifacts[0]['name'] = 'other'
    if kind == 'artifact-id': api.artifacts[0]['id'] = 999
    if kind == 'expired': api.artifacts[0]['expired'] = True
    if kind == 'digest': api.artifacts[0]['digest'] = 'sha256:' + '0' * 64
    if kind == 'oversize': api.artifacts[0]['size_in_bytes'] = 9 * 1024 * 1024
    if kind == 'duplicate': api.artifacts *= 2
    with pytest.raises(ValueError):
        runtime.fetch_qualification(api, api.pin, p, tmp_path / 'proof.zip')
    assert api.downloads == 0


def test_changed_zip_rejected(tmp_path):
    api = API(runtime.PLATFORMS[0])
    api.payload += b'tampered'
    with pytest.raises(ValueError, match='ZIP digest'):
        runtime.fetch_qualification(api, api.pin, runtime.PLATFORMS[0], tmp_path / 'proof.zip')


@pytest.mark.parametrize('kind', ['source','failed','contract','version','coverage','platform','python',
    'go','environment','guest','tree','inventory','harness','command','command-args','missing-command'])
def test_receipt_failures(tmp_path, kind):
    p=runtime.PLATFORMS[0]; data=records(p)
    if kind=='source': data['correctness.json']['candidate_sha']='f'*40
    if kind=='failed': data['inputs.json']['result']='FAIL'
    if kind=='contract': data['inputs.json']['contract']='v044-ownedprepared-product-validation'
    if kind=='version': data['inputs.json']['version']=0
    if kind=='coverage': data['correctness.json']['boundaries'].pop()
    if kind=='platform': data['inputs.json']['native_platform']=runtime.PLATFORMS[1]
    if kind=='python': data['inputs.json']['python']='3.13.9'
    if kind=='go': data['inputs.json']['go_version']='go version go1.27.1 darwin/arm64'
    if kind=='environment': data['inputs.json']['environment']['product_version']='27.0'
    if kind=='guest': data['inputs.json']['guest_sha256']='not-a-hash'
    if kind=='tree': data['inputs.json']['git_tree_sha256']='not-a-hash'
    if kind=='inventory': data['source-inventory.json'].pop('mariamem.go')
    if kind=='harness': data['inputs.json']['harness_sha256']={}
    if kind=='command': data['commands.json'][0]['exit_code']=1
    if kind=='command-args': data['commands.json'][1]['argv'].append('--scope=docs')
    if kind=='missing-command': data['commands.json'].pop()
    target=tmp_path/'proof.zip';target.write_bytes(archive(data))
    with pytest.raises((ValueError,KeyError)):
        runtime.evidence(target,intent(),p)


@pytest.mark.parametrize('kind', ['missing-hash', 'wrong-hash', 'traversal', 'duplicate', 'symlink'])
def test_archive_structure_rejected(tmp_path, kind):
    p = runtime.PLATFORMS[0]
    extras = []
    mutate = None
    if kind == 'missing-hash': mutate = lambda h: h.pop('inputs.json')
    if kind == 'wrong-hash': mutate = lambda h: h.update({'inputs.json': '0' * 64})
    if kind == 'traversal': extras = [('../escape', b'bad')]
    if kind == 'duplicate': extras = [('inputs.json', b'{}')]
    if kind == 'symlink':
        info = zipfile.ZipInfo('link')
        info.external_attr = 0o120777 << 16
        extras = [(info, b'target')]
    target = tmp_path / 'proof.zip'
    if kind == 'duplicate':
        with pytest.warns(UserWarning, match='Duplicate name'):
            target.write_bytes(archive(records(p), extras, mutate))
    else:
        target.write_bytes(archive(records(p), extras, mutate))
    with pytest.raises(ValueError):
        runtime.evidence(target, intent(), p)


@pytest.mark.parametrize('path', ['mariamem.go', 'snapshot.go', 'python/mariamem/_api.py',
    'go.mod', 'release/generated-go-inputs.json', 'scripts/build_alpha.py',
    'tests/gointegration/isolation_test.go', 'build/go.mod',
    'benchmarks/results/direct-link-consumer-experience.json', 'unexpected.py'])
def test_unreviewed_source_changes_rejected(path):
    with pytest.raises(ValueError, match='unreviewed'):
        runtime.compare_inventory({path: 'a' * 64}, {path: 'b' * 64}, VERSION, VERSION)
    with pytest.raises(ValueError):
        runtime.compare_inventory({}, {path: 'a' * 64}, VERSION, VERSION)
    with pytest.raises(ValueError):
        runtime.compare_inventory({path: 'a' * 64}, {}, VERSION, VERSION)


def test_only_constant_version_values_may_change():
    old = {runtime.VERSION_FILE: 'a' * 64}
    new = {runtime.VERSION_FILE: 'b' * 64}
    assert runtime.compare_inventory(old, new, VERSION, VERSION.replace('PATCH=3', 'PATCH=4'))
    for bad in [VERSION + '\ndef hidden(): return 1\n', VERSION.replace('PATCH=3', 'PATCH=int("4")'),
                VERSION.replace('PATCH=3', 'PATCH=4\nPATCH=3'), VERSION.replace('PATCH=3\n', '')]:
        with pytest.raises(ValueError):
            runtime.compare_inventory(old, new, VERSION, bad)


@pytest.fixture
def repository(tmp_path):
    def run(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path, text=True).strip()
    run('init', '-q')
    run('config', 'user.name', 'Fixture')
    run('config', 'user.email', 'fixture@example.invalid')
    for name, data in [(runtime.VERSION_FILE, VERSION), ('mariamem.go', 'runtime\n'),
                       ('release/generated-go-inputs.json', '{"guest_sha256":"' + 'c' * 64 + '"}')]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)
    run('add', '.')
    run('commit', '-qm', 'runtime basis')
    return tmp_path, run, run('rev-parse', 'HEAD')


def test_real_git_equivalence_and_source_authentication(repository, monkeypatch):
    root, git, basis = repository
    pin = intent()
    pin['basis_commit'] = basis
    destination = root / runtime.INTENT
    destination.write_text(json.dumps(pin))
    (root / 'docs').mkdir()
    (root / 'docs/review.md').write_text('Reviewed metadata only\n')
    (root / runtime.VERSION_FILE).write_text(VERSION.replace('PATCH=3', 'PATCH=4'))
    git('add', '.')
    git('commit', '-qm', 'integration and metadata')
    candidate = git('rev-parse', 'HEAD')
    inventory = {n: digest(subprocess.check_output(['git', 'show', basis + ':' + n], cwd=root))
                 for n in runtime.tree(root, basis)}
    monkeypatch.setattr(runtime, 'fetch_qualification', lambda *args: None)
    monkeypatch.setattr(runtime, 'evidence', lambda *args: (inventory, {'guest_sha256': 'c' * 64, 'git_tree_sha256':runtime.digest_bytes(json.dumps(runtime.tree(root,basis),sort_keys=True,separators=(',',':')).encode())}))
    proof = runtime.validate(root, candidate, api=object())
    assert proof['runtime_basis_commit'] == basis and proof['release_source_commit'] == candidate
    assert runtime.VERSION_FILE in proof['reviewed_changed_paths']
    git('tag', '-a', 'annotated', '-m', 'not a commit')
    with pytest.raises(ValueError, match='commit'):
        runtime.validate(root, git('rev-parse', 'annotated'), api=object())
    (root / 'mariamem.go').write_text('changed\n')
    with pytest.raises(ValueError, match='dirty'):
        runtime.validate(root, candidate, api=object())
    git('add', '.')
    git('commit', '-qm', 'genuine runtime change')
    changed = git('rev-parse', 'HEAD')
    with pytest.raises(ValueError, match='unreviewed tree change'):
        runtime.validate(root, changed, api=object())


def test_frozen_proof_cannot_be_a_verified_flag(tmp_path, monkeypatch):
    (tmp_path / 'release').mkdir()
    (tmp_path / runtime.INTENT).write_text(json.dumps(intent()))
    expected = {'runtime_basis_commit': SHA, 'release_source_commit': 'f' * 40,
                'run_id': 7, 'platforms': {'native': {'zip_sha256': 'b' * 64}}}
    monkeypatch.setattr(runtime, 'validate', lambda *args: expected)
    with pytest.raises(FileNotFoundError):
        runtime.verify_frozen(tmp_path, 'f' * 40)
    path = tmp_path / runtime.PROOF
    path.parent.mkdir(parents=True)
    path.write_text('{"verified":true}')
    with pytest.raises(ValueError, match='frozen'):
        runtime.verify_frozen(tmp_path, 'f' * 40)
    path.write_text(json.dumps(expected))
    assert runtime.verify_frozen(tmp_path, 'f' * 40) == expected


def test_workflow_requires_proof_before_expensive_work():
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    assert workflow.index('scripts/runtime_validation.py --candidate-sha') < workflow.index('scripts/build_alpha.py')
    assert "needs.resolve.outputs.runtime_reused }}' = true" in workflow
    assert 'scripts/release_preparation_checks.py' in workflow
    assert 'python scripts/verify.py integration' in workflow
    development = (ROOT / '.github/workflows/check.yml').read_text()
    assert 'scripts/runtime_validation.py' not in development
    assert 'scripts/development_scope.py' in development
    assert "if: needs.scope.outputs.integration == 'true'" in development
    assert 'scripts/verify.py integration' in development


@pytest.mark.parametrize('kind', ['mode', 'rename', 'dependency', 'version-logic', 'inventory', 'missing-inventory'])
def test_git_change_and_basis_inventory_fail_closed(repository, monkeypatch, kind):
    root, git, basis = repository
    pin = intent()
    pin['basis_commit'] = basis
    inventory = {n: digest(subprocess.check_output(['git', 'show', basis + ':' + n], cwd=root))
                 for n in runtime.tree(root, basis)}
    (root / runtime.INTENT).write_text(json.dumps(pin))
    if kind == 'mode':
        (root / 'mariamem.go').chmod(0o755)
        git('update-index', '--chmod=+x', 'mariamem.go')
    if kind == 'rename': git('mv', 'mariamem.go', 'snapshot.go')
    if kind == 'dependency': (root / 'go.mod').write_text('changed dependency\n')
    if kind == 'version-logic': (root / runtime.VERSION_FILE).write_text(VERSION + 'GIT_TAG="wrong"\n')
    if kind == 'inventory': inventory['mariamem.go'] = '0' * 64
    if kind == 'missing-inventory': inventory.pop('mariamem.go')
    git('add', '.')
    git('commit', '-qm', 'candidate')
    monkeypatch.setattr(runtime, 'fetch_qualification', lambda *args: None)
    monkeypatch.setattr(runtime, 'evidence', lambda *args: (inventory, {'guest_sha256': 'c' * 64, 'git_tree_sha256':runtime.digest_bytes(json.dumps(runtime.tree(root,basis),sort_keys=True,separators=(',',':')).encode())}))
    with pytest.raises(ValueError):
        runtime.validate(root, git('rev-parse', 'HEAD'), api=object())


def test_guard_cannot_return_ready_without_valid_runtime_proof(tmp_path, monkeypatch):
    import check_version
    import generated_release as release
    monkeypatch.setattr(check_version, 'check_release_docs', lambda *a: None)
    monkeypatch.setattr(release, 'checkout', lambda *a: None)
    monkeypatch.setattr(release, 'verify_build', lambda *a: {})
    monkeypatch.setattr(release, 'verify_source', lambda *a: {})
    monkeypatch.setattr(release, 'verify_wheel', lambda *a: (tmp_path / 'final.whl', {'sha256': 'e' * 64}))
    monkeypatch.setattr(release, 'verify_acceptance', lambda *a: 'd' * 64)
    def fail(*args): raise ValueError('frozen runtime proof differs')
    monkeypatch.setattr(runtime, 'verify_frozen', fail)
    with pytest.raises(ValueError, match='frozen runtime proof'):
        release.guard(tmp_path, SHA, runtime.PLATFORMS[0])


# The qualification runner's fail-closed / partial initialization owner.
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import validate_product_candidate as runner


def load_runner():
    return runner


class QualificationRunnerTest(unittest.TestCase):
    def test_failed_runner_never_writes_pass_and_preserves_tracked_boundary(self):
        module=load_runner()
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            source=base/'source';source.mkdir()
            (source/'build').mkdir();(source/'build/go.mod').write_text('module disposable-build\n')
            (source/'release').mkdir()
            (source/'release/generated-go-inputs.json').write_text(json.dumps(dict(guest_sha256='c'*64)))
            workspace=base/'work'
            def output(command,**kwargs):
                if command[:2]==['go','version']: return 'go version go1.26.8 darwin/arm64\n'
                return SHA+'\n' if command[1:3]==['rev-parse','HEAD'] else ''
            inventory={name:'c'*64 for name in (module.WORKFLOW, 'scripts/verify.py', 'scripts/validate_product_candidate.py')}
            with patch.object(module.sys,'version','3.14.8'),\
                 patch.object(module,'environment',return_value=dict(system='Darwin',architecture='arm64',product_version='15.7')),\
                 patch.dict(module.os.environ,{'PYTEST_ADDOPTS':'-k never','GOFLAGS':'-tags=skip','MARIAMEM_TEST_HOST':'wrong'}),\
                 patch.object(module,'require_commit'),\
                 patch.object(module,'source_inventory',return_value=inventory),\
                 patch.object(module,'tree',return_value={}),\
                 patch.object(module.subprocess,'check_output',side_effect=output),\
                 patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=1)) as execute:
                with self.assertRaisesRegex(RuntimeError,'source-unit-checks failed'):
                    module.qualify(source,SHA,workspace,'darwin-arm64')
            execution=execute.call_args.kwargs['env']
            self.assertNotIn('PYTEST_ADDOPTS',execution)
            self.assertNotIn('MARIAMEM_TEST_HOST',execution)
            self.assertEqual(execution['GOFLAGS'],'')
            self.assertEqual(execution['CGO_ENABLED'],'1')
            report=json.loads((workspace/'evidence/inputs.json').read_text())
            self.assertEqual(report['result'],'FAIL')
            self.assertEqual(json.loads((workspace/'evidence/correctness.json').read_text())['result'],'NOT READY')
            self.assertFalse((workspace/'scratch').exists())
            self.assertTrue((source/'build/go.mod').exists())

    def test_bad_candidate_identity_stops_before_scratch_or_build(self):
        module=load_runner()
        with tempfile.TemporaryDirectory() as temporary:
            workspace=Path(temporary)/'work'
            with patch.object(module,'require_commit',side_effect=ValueError('wrong candidate identity')),\
                 patch.object(module.subprocess,'run') as execute:
                with self.assertRaisesRegex(ValueError,'wrong candidate identity'):
                    module.qualify(Path(temporary),SHA,workspace,'darwin-arm64')
                execute.assert_not_called()
            self.assertFalse(workspace.exists())


@pytest.mark.parametrize('version', [1, True, 0, '2'])
def test_historical_or_ambiguous_intent_is_not_new_qualification(tmp_path,version):
    data=intent(); data['version']=version
    path=tmp_path/runtime.INTENT; path.parent.mkdir(parents=True); path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='intent version'): runtime.read_intent(tmp_path)


def test_runtime_reuse_does_not_exempt_recipes_consumers_or_executable_docs():
    for name in ('scripts/generated_guest_recipe.py','scripts/generated_release_acceptance.py',
                 'tests/consumer/run_sqlalchemy.py',runtime.WORKFLOW,'docs/hidden_runtime.py'):
        with pytest.raises(ValueError,match='unreviewed source change'):
            runtime.compare_inventory({name:'a'*64},{name:'b'*64},VERSION,VERSION)


def test_existing_workflow_owns_only_versioned_native_runtime_qualification():
    workflow=(ROOT/runtime.WORKFLOW).read_text()
    for value in ('Runtime qualification (v1)','Runtime qualification —',
                  'runner: macos-15','runner: ubuntu-24.04',
                  'platform: darwin-arm64','platform: ubuntu24.04-x86_64',
                  'runtime-${{ matrix.platform }}-', 'retention-days: 90'):
        assert value in workflow
    assert workflow.index('Freeze candidate identity') < workflow.index('actions/setup-go')
    assert 'test "$CANDIDATE" = "$GITHUB_SHA"' in workflow
    for historical in ('run_compare.py','build_alpha.py','--phase','--baseline','performance-correctness'):
        assert historical not in workflow
    assert 'scripts/validate_product_candidate.py --candidate-sha' in workflow
