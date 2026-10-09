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
    return {'version': 1, 'repository': 'masahitojp/mariamem', 'workflow': runtime.WORKFLOW,
            'basis_commit': SHA, 'run_id': 7,
            'artifacts': {p: {'id': i + 1, 'zip_sha256': 'b' * 64}
                          for i, p in enumerate(runtime.PLATFORMS)}}


def records(platform):
    mac = platform == runtime.PLATFORMS[0]
    return {
        'inputs.json': {'result': 'PASS', 'candidate_sha': SHA,
            'contract': 'v044-ownedprepared-product-validation', 'python': '3.14.2',
            'machine': 'arm64' if mac else 'x86_64',
            'platform': 'macOS-15.7-arm64' if mac else 'Linux-6.8-x86_64',
            'guest_sha256': 'c' * 64},
        'correctness.json': {'result': 'PASS', 'candidate_sha': SHA,
            'boundaries': ['source/unit', 'handwritten races', 'Go real SQL/lifecycle',
                           'Python import/isolation/lifecycle', 'installed pytest/xdist']},
        'alpha-wheel.json': {'source_commit': SHA, 'manifest': {'platform': platform},
            'source_files_sha256': {'mariamem.go': 'd' * 64}, 'sha256': 'e' * 64,
            'archive_checks_passed': True,
            'host_buildinfo': 'host: go1.26.8\nCGO_ENABLED=0\n-trimpath=true\nGOOS=' +
                ('darwin\nGOARCH=arm64' if mac else 'linux\nGOARCH=amd64') +
                '\nvcs.revision=' + SHA + '\nvcs.modified=false'},
        'alpha.json': {'passed': True, 'installed_files_match_wheel': True,
            'consumer_outside_repository': True, 'native_overrides': False,
            'wheel_sha256': 'e' * 64,
            'runs': [{'name': n} for n in ['serial', 'parallel', 'migration', 'failure-cleanup']]},
        'snapshots.json': {'passed': True, 'checks': list(range(49))},
        'commands.json': [{'name': n, 'exit_code': 0} for n in
            ['validation-tools', 'source-unit-checks', 'runtime-integration',
             'wheel-build', 'installed-pytest', 'comparison']],
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
        self.jobs = [{'name': 'Product contract — ' + p, 'status': 'completed', 'conclusion': 'success'}
                     for p in runtime.PLATFORMS]
        self.artifacts = [{'id': self.pin['artifacts'][platform]['id'],
            'name': f'v044-product-{platform}-{SHA}', 'expired': False,
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
    runtime.fetch_product(api, api.pin, platform, target)
    inventory, receipt = runtime.evidence(target, api.pin, platform)
    assert inventory == {'mariamem.go': 'd' * 64}
    assert receipt['original_wheel_sha256'] == 'e' * 64
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
        runtime.fetch_product(api, api.pin, p, tmp_path / 'proof.zip')
    assert api.downloads == 0


def test_changed_zip_rejected(tmp_path):
    api = API(runtime.PLATFORMS[0])
    api.payload += b'tampered'
    with pytest.raises(ValueError, match='ZIP digest'):
        runtime.fetch_product(api, api.pin, runtime.PLATFORMS[0], tmp_path / 'proof.zip')


@pytest.mark.parametrize('kind', ['result', 'source', 'coverage', 'python', 'platform', 'machine',
    'toolchain', 'cgo', 'vcs', 'installed', 'wheel', 'suite', 'snapshots', 'commands'])
def test_receipt_failures(tmp_path, kind):
    p = runtime.PLATFORMS[0]
    data = records(p)
    if kind == 'result': data['correctness.json']['result'] = 'FAIL'
    if kind == 'source': data['alpha-wheel.json']['source_commit'] = 'f' * 40
    if kind == 'coverage': data['correctness.json']['boundaries'].pop()
    if kind == 'python': data['inputs.json']['python'] = '3.13.0'
    if kind == 'platform': data['alpha-wheel.json']['manifest']['platform'] = runtime.PLATFORMS[1]
    if kind == 'machine': data['inputs.json']['machine'] = 'x86_64'
    if kind == 'toolchain': data['alpha-wheel.json']['host_buildinfo'] = 'go1.27.1'
    if kind == 'cgo': data['alpha-wheel.json']['host_buildinfo'] = data['alpha-wheel.json']['host_buildinfo'].replace('CGO_ENABLED=0', 'CGO_ENABLED=1')
    if kind == 'vcs': data['alpha-wheel.json']['host_buildinfo'] = data['alpha-wheel.json']['host_buildinfo'].replace('vcs.modified=false', 'vcs.modified=true')
    if kind == 'installed': data['alpha.json']['installed_files_match_wheel'] = False
    if kind == 'wheel': data['alpha.json']['wheel_sha256'] = 'f' * 64
    if kind == 'suite': data['alpha.json']['runs'].pop()
    if kind == 'snapshots': data['snapshots.json']['checks'].pop()
    if kind == 'commands': data['commands.json'][0]['exit_code'] = 1
    target = tmp_path / 'proof.zip'
    target.write_bytes(archive(data))
    with pytest.raises(ValueError):
        runtime.evidence(target, intent(), p)


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
    monkeypatch.setattr(runtime, 'fetch_product', lambda *args: None)
    monkeypatch.setattr(runtime, 'evidence', lambda *args: (inventory, {'guest_sha256': 'c' * 64}))
    proof = runtime.validate(root, candidate, api=object())
    assert proof['runtime_basis_commit'] == basis and proof['release_source_commit'] == candidate
    assert runtime.VERSION_FILE in proof['reviewed_changed_paths']
    assert not runtime.development_changed(root, candidate, pin)
    git('tag', '-a', 'annotated', '-m', 'not a commit')
    with pytest.raises(ValueError, match='commit'):
        runtime.validate(root, git('rev-parse', 'annotated'), api=object())
    (root / 'mariamem.go').write_text('changed\n')
    with pytest.raises(ValueError, match='dirty'):
        runtime.validate(root, candidate, api=object())
    git('add', '.')
    git('commit', '-qm', 'genuine runtime change')
    changed = git('rev-parse', 'HEAD')
    assert runtime.development_changed(root, changed, pin)
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
    assert '--development --github-output' in development
    assert "if: needs.scope.outputs.reused != 'true'" in development
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
    monkeypatch.setattr(runtime, 'fetch_product', lambda *args: None)
    monkeypatch.setattr(runtime, 'evidence', lambda *args: (inventory, {'guest_sha256': 'c' * 64}))
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


RECIPE = '''import shutil
for name in ('runtime_instance.go', 'runtime_instance_test.go'):
    shutil.copy2(ROOT/'internal/generatedgo'/name, out/name)
'''
FIXED_RECIPE = RECIPE.replace("('runtime_instance.go',", "('code/base/owned_prepared.go', 'code/base/owned_prepared_test.go', 'runtime_instance.go',")


def test_recipe_repair_is_narrower_than_a_tooling_exemption():
    runtime.verify_handwritten_recipe(RECIPE, FIXED_RECIPE)
    assert not runtime.exempt(runtime.HANDWRITTEN_RECIPE)
    old, new = {runtime.HANDWRITTEN_RECIPE: 'a'*64}, {runtime.HANDWRITTEN_RECIPE: 'b'*64}
    with pytest.raises(ValueError, match='missing generated recipe'):
        runtime.compare_inventory(old, new, VERSION, VERSION)
    assert runtime.compare_inventory(old, new, VERSION, VERSION, RECIPE, FIXED_RECIPE)


@pytest.mark.parametrize('change', [
    "shutil.copy2(ROOT/'other'/name, out/name)",
    "shutil.copy2(ROOT/'internal/generatedgo'/name, out/name)\nbuild_new_guest()",
    "shutil.copy2(ROOT/'internal/generatedgo'/name, out/name)\nGOTOOLCHAIN='other'",
])
def test_recipe_repair_cannot_hide_new_build_logic(change):
    altered = FIXED_RECIPE.replace("shutil.copy2(ROOT/'internal/generatedgo'/name, out/name)", change)
    with pytest.raises(ValueError, match='recipe logic changed'):
        runtime.verify_handwritten_recipe(RECIPE, altered)


@pytest.mark.parametrize('new', [RECIPE,
    FIXED_RECIPE.replace("'code/base/owned_prepared_test.go', ", ''),
    FIXED_RECIPE.replace("'runtime_instance_test.go'", "'different.go'"),
    FIXED_RECIPE.replace("'runtime_instance_test.go'", "'runtime_instance.go'"),
    FIXED_RECIPE + RECIPE,
])
def test_recipe_missing_extra_duplicate_or_ambiguous_glue_rejected(new):
    with pytest.raises(ValueError):
        runtime.verify_handwritten_recipe(RECIPE, new)


def test_real_recipe_carries_only_already_committed_glue():
    import ast
    source = (ROOT/runtime.HANDWRITTEN_RECIPE).read_text()
    original = source.replace("'code/base/owned_prepared.go', 'code/base/owned_prepared_test.go', ", '', 1)
    runtime.verify_handwritten_recipe(original, source)
    assert ast.dump(ast.parse(original)) != ast.dump(ast.parse(source))


def test_repaired_recipe_development_scope_and_release_validation(repository, monkeypatch):
    root, git, _ = repository
    (root/'scripts').mkdir()
    (root/runtime.HANDWRITTEN_RECIPE).write_text(RECIPE)
    git('add', '.')
    git('commit', '-qm', 'original installer')
    basis = git('rev-parse', 'HEAD')
    inventory = {n: digest(subprocess.check_output(['git','show',basis+':'+n],cwd=root))
                 for n in runtime.tree(root,basis)}
    pin = intent()
    pin['basis_commit'] = basis
    (root/runtime.INTENT).write_text(json.dumps(pin))
    (root/runtime.HANDWRITTEN_RECIPE).write_text(FIXED_RECIPE)
    git('add', '.')
    git('commit', '-qm', 'carry tested handwritten files')
    candidate = git('rev-parse', 'HEAD')
    assert not runtime.development_changed(root, candidate, pin)
    monkeypatch.setattr(runtime, 'fetch_product', lambda *a: None)
    monkeypatch.setattr(runtime, 'evidence', lambda *a: (inventory, {'guest_sha256':'c'*64}))
    proof = runtime.validate(root, candidate, api=object())
    assert runtime.HANDWRITTEN_RECIPE in proof['reviewed_changed_paths']
    (root/runtime.HANDWRITTEN_RECIPE).write_text(FIXED_RECIPE+'\nbuild_new_guest()\n')
    git('add', '.')
    git('commit', '-qm', 'different recipe')
    changed = git('rev-parse', 'HEAD')
    assert runtime.development_changed(root, changed, pin)  # ordinary future code checks remain
    with pytest.raises(ValueError, match='recipe logic changed'):
        runtime.validate(root, changed, api=object())


def original_sqlalchemy_fixture():
    current = (ROOT / runtime.SQLALCHEMY_HARNESS).read_text()
    assert current.count('            yield snapshot\n') == 1
    return current.replace('            yield snapshot\n',
                           '            saved = snapshot.path\n            yield snapshot\n'
                           '        assert not saved.exists()\n', 1)


def test_sqlalchemy_fixture_repair_is_exact():
    current = (ROOT / runtime.SQLALCHEMY_HARNESS).read_text()
    original = original_sqlalchemy_fixture()
    runtime.verify_sqlalchemy_fixture(original, current)
    old, new = {runtime.SQLALCHEMY_HARNESS:'a'*64}, {runtime.SQLALCHEMY_HARNESS:'b'*64}
    with pytest.raises(ValueError, match='missing SQLAlchemy harness'):
        runtime.compare_inventory(old, new, VERSION, VERSION)
    assert runtime.compare_inventory(old, new, VERSION, VERSION,
                                     old_harness=original, new_harness=current)
    for altered in (current.replace('            prepare(engine)', '            pass'),
                    current.replace('yield snapshot', 'yield None'),
                    current.replace('template.wait_disconnected()', 'pass'),
                    current.replace('engine.dispose()', 'pass'),
                    current + '\nassert False\n'):
        with pytest.raises(ValueError, match='consumer logic changed'):
            runtime.verify_sqlalchemy_fixture(original, altered)


@pytest.mark.parametrize('finish', ['normal', 'close', 'error'])
def test_actual_consumer_prepared_fixture_needs_no_public_path(finish):
    import ast
    from contextlib import contextmanager
    from types import SimpleNamespace
    source = ast.parse((ROOT / runtime.SQLALCHEMY_HARNESS).read_text())
    fixture = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'prepared')
    fixture.decorator_list = []
    events = []
    snapshot = object()  # intentionally no path, manifest or validation API
    @contextmanager
    def owned_snapshot():
        events.append('snapshot-enter')
        try:
            yield snapshot
        finally:
            events.append('snapshot-close')
    db = SimpleNamespace(diagnostics={}, log_path=Path('/fixture/log'),
                         wait_disconnected=lambda: events.append('disconnected'),
                         snapshot=owned_snapshot)
    @contextmanager
    def start():
        events.append('database-enter')
        try:
            yield db
        finally:
            events.append('database-close')
    namespace = {'mariamem':SimpleNamespace(start=start),
                 'time':SimpleNamespace(monotonic=lambda:1),
                 'engine_for':lambda *_:SimpleNamespace(dispose=lambda:events.append('dispose')),
                 'prepare':lambda _:events.append('prepare'),
                 'reaped':lambda *_:events.append('reaped')}
    exec(compile(ast.Module(body=[fixture], type_ignores=[]), '<actual prepared fixture>', 'exec'), namespace)
    audit = {'mode':'fork', 'templates':[]}
    generator = namespace['prepared'](audit)
    assert next(generator) is snapshot
    assert events == ['database-enter', 'prepare', 'dispose', 'disconnected', 'snapshot-enter', 'reaped']
    if finish == 'normal':
        with pytest.raises(StopIteration):
            next(generator)
    elif finish == 'close':
        generator.close()
    else:
        with pytest.raises(RuntimeError, match='test failure'):
            generator.throw(RuntimeError('test failure'))
    assert events[-2:] == ['snapshot-close', 'database-close']
    assert len(audit['templates']) == 1


def test_consumer_fixture_repair_development_and_release_scope(repository, monkeypatch):
    root, git, _ = repository
    (root / 'tests/consumer').mkdir(parents=True)
    original = original_sqlalchemy_fixture()
    (root / runtime.SQLALCHEMY_HARNESS).write_text(original)
    git('add', '.')
    git('commit', '-qm', 'original consumer')
    basis = git('rev-parse', 'HEAD')
    inventory = {n:digest(subprocess.check_output(['git','show',basis+':'+n],cwd=root))
                 for n in runtime.tree(root,basis)}
    pin = intent()
    pin['basis_commit'] = basis
    (root/runtime.INTENT).write_text(json.dumps(pin))
    current = (ROOT/runtime.SQLALCHEMY_HARNESS).read_text()
    (root/runtime.SQLALCHEMY_HARNESS).write_text(current)
    git('add', '.')
    git('commit', '-qm', 'remove obsolete path probe')
    candidate = git('rev-parse', 'HEAD')
    assert not runtime.development_changed(root, candidate, pin)
    monkeypatch.setattr(runtime, 'fetch_product', lambda *a:None)
    monkeypatch.setattr(runtime, 'evidence', lambda *a:(inventory, {'guest_sha256':'c'*64}))
    assert runtime.SQLALCHEMY_HARNESS in runtime.validate(root, candidate, api=object())['reviewed_changed_paths']
    (root/runtime.SQLALCHEMY_HARNESS).write_text(current.replace('            prepare(engine)', '            pass'))
    git('add', '.')
    git('commit', '-qm', 'different consumer setup')
    changed = git('rev-parse', 'HEAD')
    assert runtime.development_changed(root, changed, pin)
    with pytest.raises(ValueError, match='consumer logic changed'):
        runtime.validate(root, changed, api=object())
