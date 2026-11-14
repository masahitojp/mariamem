"""PyPI identity, idempotent recovery and publication-free verification."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pypi_release as release
from common import digest
from test_release_plan import job_text

SOURCE = 'a' * 40
TOOLING = 'b' * 40
TAG_OBJECT = 'c' * 40
TAG = 'v0.6.2'
VERSION = '0.6.2'
REPO = 'masahitojp/mariamem'
WHEEL = next(iter(release.selected_wheels(VERSION)))


@pytest.fixture
def origin(tmp_path, monkeypatch):
    wheels = {WHEEL, f'mariamem-{VERSION}-py3-none-linux_x86_64.whl'}
    assets = {n: 'd' * 64 for n in {*wheels, f'mariamem-{VERSION}-corresponding-source.tar.gz'}}
    assets[WHEEL] = hashlib.sha256(b'accepted wheel').hexdigest()
    platforms = {}
    for platform, name in [('darwin-arm64', WHEEL), ('ubuntu24.04-x86_64', next(n for n in wheels if 'linux' in n))]:
        platforms[platform] = {'version': 3, 'contract': 'generated-go-v1', 'result': 'READY',
                               'source_commit': SOURCE, 'platform': platform, 'git_tag': TAG,
                               'python_version': VERSION, 'acceptance_sha256': 'e' * 64,
                               'wheel_record': {'wheel': 'build/dist/' + name, 'sha256': assets[name],
                                                'source_commit': SOURCE}}
    provenance = {'contract': 'generated-go-v1', 'source_commit': SOURCE, 'assets': assets, 'platforms': platforms}
    prov_name = f'mariamem-{VERSION}-provenance.json'
    files = {prov_name: json.dumps(provenance).encode(), WHEEL: b'accepted wheel'}
    sums = {**assets, prov_name: hashlib.sha256(files[prov_name]).hexdigest()}
    files['SHA256SUMS'] = ''.join(f'{sha}  {name}\n' for name, sha in sorted(sums.items())).encode()
    gh = {'tag_name': TAG, 'draft': False, 'prerelease': False, 'html_url': 'https://github.com/example',
          'assets': [{'name': name} for name in {*sums, 'SHA256SUMS'}]}
    calls = []
    monkeypatch.setattr(release.time, 'sleep', lambda delay: None)

    def command(args, root):
        args = list(map(str, args)); calls.append(args)
        if args[:2] == ['gh', 'api']:
            return json.dumps(gh)
        if args[:3] == ['gh', 'release', 'download']:
            target = Path(args[args.index('--dir') + 1])
            for i, value in enumerate(args):
                if value == '--pattern':
                    (target / args[i+1]).write_bytes(files[args[i+1]])
        return ''

    monkeypatch.setattr(release, 'run', command)
    monkeypatch.setattr(release, 'require_commit', lambda *a: None)
    monkeypatch.setattr(release, 'inspect_ref', lambda root, ref: SimpleNamespace(
        object_sha=TAG_OBJECT, object_type='tag', source_commit=SOURCE) if ref == 'FETCH_HEAD'
        else SimpleNamespace(source_commit=TOOLING))
    monkeypatch.setattr(release, 'pypi_files', lambda v: {})
    return SimpleNamespace(root=tmp_path, directory=tmp_path/'output', sums=sums, files=files,
                           provenance=provenance, gh=gh, calls=calls)


def prepare(o, operation='verify', publication=None):
    return release.prepare(o.root, o.directory, SOURCE, TAG, operation, REPO, publication)


def test_verify_uses_original_release_without_build_or_upload(origin):
    record = prepare(origin)
    assert record['status'] == 'VERIFIED' and record['operation'] == 'verify'
    assert record['source_commit'] == SOURCE and record['tooling_commit'] == TOOLING
    assert record['tag_object_sha'] == TAG_OBJECT
    assert record['assets'] == {WHEEL: origin.sums[WHEEL]}
    assert record['missing'] == [WHEEL]
    assert (origin.directory/'upload'/WHEEL).read_bytes() == b'accepted wheel'
    assert all(c[:2] in (['git', 'fetch'], ['git', 'status']) or c[:2] == ['gh', 'api']
               or c[:3] == ['gh', 'release', 'download'] for c in origin.calls)
    with pytest.raises(ValueError, match='state'):
        release.verify_uploaded(origin.directory/'ci-pypi-publication.json')


def test_already_uploaded_files_are_never_staged_again(origin, monkeypatch):
    monkeypatch.setattr(release, 'pypi_files', lambda v: {WHEEL: {'sha256': origin.sums[WHEEL], 'yanked': False}})
    record = prepare(origin, 'release')
    assert record['missing'] == [] and not list((origin.directory/'upload').iterdir())
    assert release.verify_uploaded(origin.directory/'ci-pypi-publication.json')['status'] == 'SMOKE_PENDING'


@pytest.mark.parametrize('actual', [{'sha256': '0'*64, 'yanked': False}, {'sha256': None, 'yanked': True}])
def test_conflict_or_yank_stops_without_upload(origin, monkeypatch, actual):
    actual['sha256'] = actual['sha256'] or origin.sums[WHEEL]
    monkeypatch.setattr(release, 'pypi_files', lambda v: {WHEEL: actual})
    with pytest.raises(ValueError):
        prepare(origin, 'release')
    record = json.loads((origin.directory/'ci-pypi-publication.json').read_text())
    assert record['status'] == 'FAILED' and record['stage'] == 'pypi-preflight'
    assert not (origin.directory/'upload').exists()


def test_partial_upload_and_lost_success_response_are_reconciled_by_hash(origin, monkeypatch):
    record = prepare(origin, 'release')
    path = origin.directory/'ci-pypi-publication.json'
    with pytest.raises(ValueError, match='still missing'):
        release.verify_uploaded(path)
    assert json.loads(path.read_text())['status'] == 'FAILED'
    # Retry starts with an authenticated origin, not a rewritten FAILED receipt.
    other = origin.root/'retry'
    monkeypatch.setattr(release, 'pypi_files', lambda v: {WHEEL: {'sha256': record['assets'][WHEEL], 'yanked': False}})
    retry = release.prepare(origin.root, other, SOURCE, TAG, 'release', REPO)
    assert retry['missing'] == []
    assert release.verify_uploaded(other/'ci-pypi-publication.json')['status'] == 'SMOKE_PENDING'
    expected = {'first.whl': 'a'*64, 'second.whl': 'b'*64}
    assert release.missing_files(expected, {'first.whl': {'sha256': 'a'*64, 'yanked': False}}) == ['second.whl']


@pytest.mark.parametrize('tag', ['v0.6.2-alpha.1', 'v0.6.2-beta.1', 'v0.6.2-rc.1', '0.6.2', 'v00.6.2'])
def test_backfill_rejects_nonstable_or_noncanonical_tags(origin, tag):
    with pytest.raises(ValueError, match='stable'):
        release.prepare(origin.root, origin.directory, SOURCE, tag, 'release', REPO)
    assert all(c[:2] == ['git', 'status'] for c in origin.calls)


def test_normal_github_prerelease_skips_pypi(origin):
    receipt = origin.root/'publication.json'
    receipt.write_text(json.dumps({'status': 'PUBLISHED', 'source_commit': SOURCE,
                                  'git_tag': 'v0.7.0-rc.1', 'prerelease': True}))
    assert prepare(origin, 'release', receipt)['status'] == 'SKIPPED'
    assert all(c[:2] == ['git', 'status'] for c in origin.calls)


@pytest.mark.parametrize('failure', ['source', 'ready', 'wheel', 'sum', 'draft', 'download', 'tag'])
def test_origin_rejection_precedes_pypi(origin, monkeypatch, failure):
    if failure in ('source', 'ready', 'wheel'):
        d=origin.provenance
        if failure == 'source': d['source_commit'] = 'f'*40
        if failure == 'ready': d['platforms']['darwin-arm64']['result'] = 'NOT READY'
        if failure == 'wheel': d['platforms']['darwin-arm64']['wheel_record']['sha256'] = 'f'*64
        name=f'mariamem-{VERSION}-provenance.json'
        origin.files[name]=json.dumps(d).encode()
        origin.sums[name]=hashlib.sha256(origin.files[name]).hexdigest()
        origin.files['SHA256SUMS']=''.join(f'{sha}  {n}\n' for n,sha in origin.sums.items()).encode()
    elif failure == 'sum': origin.files['SHA256SUMS'] += origin.files['SHA256SUMS'].splitlines(keepends=True)[0]
    elif failure == 'draft': origin.gh['draft'] = True
    elif failure == 'download': origin.files[WHEEL] = b'corrupted'
    else:
        monkeypatch.setattr(release, 'inspect_ref', lambda r, ref: SimpleNamespace(
            source_commit=SOURCE, object_type='commit', object_sha=SOURCE))
    with pytest.raises(ValueError): prepare(origin, 'release')


def test_normal_publication_and_backfill_share_origin_checks(origin):
    receipt = origin.root/'publication.json'
    record = {'version': 3, 'contract': 'generated-go-v1', 'status': 'PUBLISHED',
              'source_commit': SOURCE, 'git_tag': TAG, 'python_version': VERSION,
              'repository': REPO, 'platforms': origin.provenance['platforms'],
              'assets': {**origin.sums, 'SHA256SUMS': hashlib.sha256(origin.files['SHA256SUMS']).hexdigest()},
              'prerelease': False}
    receipt.write_text(json.dumps(record))
    assert prepare(origin, 'release', receipt)['assets'] == {WHEEL: origin.sums[WHEEL]}


def test_only_404_means_not_uploaded(monkeypatch):
    def fail(code):
        def request(*a, **kw): raise urllib.error.HTTPError('https://pypi.org', code, 'failure', {}, None)
        return request
    monkeypatch.setattr(release.urllib.request, 'urlopen', fail(404))
    assert release.pypi_files(VERSION) == {}
    for code in (401, 403, 429, 500, 503):
        monkeypatch.setattr(release.urllib.request, 'urlopen', fail(code))
        with pytest.raises(urllib.error.HTTPError): release.pypi_files(VERSION)


def test_smoke_reuse_binds_source_artifacts_and_conditions(origin):
    current = prepare(origin, 'release')
    conditions = release.smoke_conditions(ROOT)
    previous = {**current, 'status': 'COMPLETE', 'smoke': {'result': 'PASS', 'conditions': conditions}}
    assert release.reusable(previous, current, conditions)
    for field in ('source_commit', 'assets', 'git_tag', 'tag_object_sha', 'checksums_sha256', 'provenance_sha256'):
        wrong = copy.deepcopy(previous); wrong[field] = 'changed'
        assert not release.reusable(wrong, current, conditions)
    assert not release.reusable(previous, current, {**conditions, 'python': '3.11'})
    assert not release.reusable({**previous, 'status': 'FAILED'}, current, conditions)


def test_smoke_failure_record_is_not_complete(origin, monkeypatch):
    prepare(origin, 'release')
    path = origin.directory/'ci-pypi-publication.json'
    monkeypatch.setattr(release, 'pypi_files', lambda v: {WHEEL: {'sha256': origin.sums[WHEEL], 'yanked': False}})
    release.verify_uploaded(path)
    def failed(*args): raise RuntimeError('smoke could not start')
    monkeypatch.setattr(release, 'find_smoke', failed)
    with pytest.raises(RuntimeError): release.smoke(ROOT, path)
    result=json.loads(path.read_text())
    assert result['status'] == 'FAILED' and result['pypi_status'] == 'HASH_VERIFIED'
    assert result['stage'] == 'pypi-smoke'


def test_pypi_workflow_has_no_verify_upload_or_build_and_keeps_normal_gates():
    workflow=(ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    verify=job_text('pypi_verify'); publish=job_text('pypi_publication'); smoke=job_text('pypi_smoke')
    assert "inputs.operation == 'verify' && inputs.published_tag != ''" in verify
    assert 'id-token: write' not in verify and 'gh-action-pypi-publish' not in verify
    assert "inputs.operation == 'release'" in publish
    assert "inputs.published_tag != '' || needs.publication.result == 'success'" in publish
    assert 'environment: pypi' in publish and 'id-token: write' in publish
    assert 'skip-existing: false' in publish and 'continue-on-error: true' in publish
    assert 'python scripts/pypi_release.py verify-upload' in publish
    assert 'steps.prepare.outputs.enabled' in publish
    assert "inputs.published_tag == ''" in job_text('resolve')
    assert "needs.pypi_publication.result == 'success'" in smoke
    assert 'architecture: arm64' in smoke
    assert 'name: ${{ needs.pypi_publication.outputs.artifact }}' in smoke
    assert 'artifact: pypi-publication-${{ inputs.candidate_ref }}-${{ github.run_attempt }}' in publish
    assert 'name: pypi-smoke-${{ needs.pypi_publication.outputs.source }}-${{ github.run_attempt }}' in smoke
    for text in (verify,publish,smoke):
        assert 'setup-go' not in text and 'build_alpha' not in text and 'build_generated_guest' not in text
    from workflow_model import load, events
    assert events(load(ROOT/'.github/workflows/release-candidate-ready.yml'))['workflow_dispatch']['inputs']['operation']['options'] == ['verify', 'release', 'public-smoke-recovery']


def test_smoke_runs_installed_package_and_requires_real_host_exit(monkeypatch):
    import pypi_smoke
    closed=[]
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,sql): assert sql=='SELECT 1'
        def fetchone(self): return (1,)
    class Connection(Cursor):
        def cursor(self): return Cursor()
    process=SimpleNamespace(poll=lambda: None, returncode=None)
    db=SimpleNamespace(_session=SimpleNamespace(_process=process), closed=False,
                       connection_info=lambda: {}, close=lambda: closed.append(True))
    monkeypatch.setitem(sys.modules,'mariamem',SimpleNamespace(__version__=VERSION,start=lambda: db))
    monkeypatch.setitem(sys.modules,'pymysql',SimpleNamespace(connect=lambda **kwargs: Connection()))
    monkeypatch.setattr(pypi_smoke.platform,'system',lambda: 'Darwin')
    monkeypatch.setattr(pypi_smoke.platform,'machine',lambda: 'arm64')
    with pytest.raises(RuntimeError,match='host exit'): pypi_smoke.check(VERSION)
    assert closed
    def close(): db.closed=True; process.returncode=0
    db.close=close; process.poll=lambda: process.returncode
    assert pypi_smoke.check(VERSION)['host_exit']==0


def test_new_publication_boundary_selects_python_checks_only():
    import development_scope
    paths = ['scripts/pypi_release.py', 'scripts/pypi_smoke.py',
             'release/baselines/v0.6.2.json', 'tests/test_pypi_release.py',
             '.github/workflows/release-candidate-ready.yml']
    result = development_scope.select(paths)
    assert result['check_scope'] == 'python' and not result['integration']


def test_dirty_publication_tooling_cannot_upload(origin, monkeypatch):
    monkeypatch.setattr(release, 'run', lambda *a: ' M scripts/pypi_release.py')
    with pytest.raises(ValueError, match='clean'):
        prepare(origin, 'release')


def test_reused_smoke_does_not_install_or_execute_again(origin, monkeypatch):
    prepare(origin, 'release')
    path = origin.directory/'ci-pypi-publication.json'
    monkeypatch.setattr(release, 'pypi_files', lambda v: {WHEEL: {'sha256': origin.sums[WHEEL], 'yanked': False}})
    release.verify_uploaded(path)
    reused = {'result': 'PASS', 'conditions': release.smoke_conditions(ROOT),
              'reused_from': {'run_id': 123, 'zip_sha256': 'e'*64}}
    monkeypatch.setattr(release, 'find_smoke', lambda *a: reused)
    def unexpected(*a): raise AssertionError('already passed smoke must not rerun')
    monkeypatch.setattr(release, 'run', unexpected)
    result=release.smoke(ROOT,path)
    assert result['status']=='COMPLETE' and result['smoke']==reused


def test_reuse_fetches_authenticated_attempt_receipt_and_skips_failed_one(origin, monkeypatch):
    import zipfile
    current=prepare(origin,'release')
    conditions=release.smoke_conditions(ROOT)
    success={**current,'status':'COMPLETE','smoke':{'result':'PASS','conditions':conditions}}
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    monkeypatch.setenv('GITHUB_RUN_ID','30')
    prefix='pypi-smoke-'+SOURCE+'-'
    calls=[]
    class API:
        def __init__(self,*args): pass
        def json(self,path):
            if '/workflows/' in path:
                return {'workflow_runs':[
                    {'id':30,'head_sha':TOOLING,'status':'in_progress','path':release.WORKFLOW},
                    {'id':20,'head_sha':'f'*40,'status':'completed','path':release.WORKFLOW},
                    {'id':10,'head_sha':TOOLING,'status':'completed','path':release.WORKFLOW}]}
            assert path.startswith('/actions/runs/10/')
            return {'artifacts':[{'id':1,'name':prefix+'1','expired':False},
                                 {'id':2,'name':prefix+'2','expired':False}]}
        def artifact(self,run,name,source,destination):
            calls.append((run,name,source))
            previous=success if name.endswith('-1') else {**success,'status':'FAILED'}
            with zipfile.ZipFile(destination,'w') as archive:
                archive.writestr('ci-pypi-publication.json',json.dumps(previous))
            return {'run_id':run,'zip_sha256':digest(destination)}
    monkeypatch.setattr(release,'GitHub',API)
    found=release.find_smoke(ROOT,current,conditions)
    assert found['result']=='PASS' and found['reused_from']['run_id']==10
    assert calls==[(10,prefix+'2',SOURCE),(10,prefix+'1',SOURCE)]


def test_uploaded_file_becomes_visible_after_initial_missing_response(origin, monkeypatch):
    prepare(origin, 'release')
    replies = iter([{}, {}, {WHEEL: {'sha256': origin.sums[WHEEL], 'yanked': False}}])
    monkeypatch.setattr(release, 'pypi_files', lambda v: next(replies))
    waits = []
    monkeypatch.setattr(release.time, 'sleep', waits.append)
    result = release.verify_uploaded(origin.directory/'ci-pypi-publication.json')
    assert result['status'] == 'SMOKE_PENDING' and result['visibility_checks'] == 3
    assert result['missing'] == [] and waits == [2, 4]


def test_upload_visibility_wait_is_bounded(origin, monkeypatch):
    prepare(origin, 'release')
    reads = []
    def absent(version):
        reads.append(version)
        return {}
    waits = []
    monkeypatch.setattr(release, 'pypi_files', absent)
    monkeypatch.setattr(release.time, 'sleep', waits.append)
    path = origin.directory/'ci-pypi-publication.json'
    with pytest.raises(ValueError, match='still missing'):
        release.verify_uploaded(path)
    assert len(reads) == 6 and waits == [2, 4, 8, 16, 30] and sum(waits) == 60
    assert json.loads(path.read_text())['status'] == 'FAILED'


@pytest.mark.parametrize('failure', ['hash', 'yanked', 'http'])
def test_visibility_retry_never_hides_integrity_or_network_errors(origin, monkeypatch, failure):
    prepare(origin, 'release')
    reads = []
    def response(version):
        reads.append(version)
        if len(reads) == 1:
            return {}
        if failure == 'http':
            raise urllib.error.HTTPError('https://pypi.org', 503, 'unavailable', {}, None)
        return {WHEEL: {'sha256': '0'*64 if failure == 'hash' else origin.sums[WHEEL],
                         'yanked': failure == 'yanked'}}
    waits = []
    monkeypatch.setattr(release, 'pypi_files', response)
    monkeypatch.setattr(release.time, 'sleep', waits.append)
    path = origin.directory/'ci-pypi-publication.json'
    with pytest.raises((ValueError, urllib.error.HTTPError)):
        release.verify_uploaded(path)
    assert len(reads) == 2 and waits == [2]
    assert json.loads(path.read_text())['status'] == 'FAILED'


@pytest.mark.parametrize('host', [None, '/explicit/source-host'])
@pytest.mark.parametrize('failure', [None, 'sql', 'close', 'version', 'platform'])
def test_common_short_smoke_preserves_sql_close_and_host_selection(monkeypatch, host, failure):
    from contextlib import contextmanager
    import pypi_smoke
    starts = []
    closed = []
    process = SimpleNamespace(poll=lambda: 1 if failure == 'close' else 0, returncode=0)
    db = SimpleNamespace(_session=SimpleNamespace(_process=process), closed=False,
                         connection_info=lambda: {'port': 1234})
    def close():
        db.closed = True
        closed.append(True)
    db.close = close
    def start(**kwargs):
        starts.append(kwargs)
        return db
    monkeypatch.setitem(sys.modules, 'mariamem', SimpleNamespace(
        __version__='wrong' if failure == 'version' else VERSION, start=start))
    @contextmanager
    def connect(**kwargs):
        assert kwargs == {'port': 1234, 'connect_timeout': 10, 'read_timeout': 10}
        @contextmanager
        def cursor():
            def execute(sql):
                assert sql == 'SELECT 1'
                if failure == 'sql':
                    raise RuntimeError('SQL failed')
            yield SimpleNamespace(execute=execute, fetchone=lambda: (1,))
        yield SimpleNamespace(cursor=cursor)
    monkeypatch.setitem(sys.modules, 'pymysql', SimpleNamespace(connect=connect))
    monkeypatch.setattr(pypi_smoke.platform, 'system', lambda: 'wrong' if failure == 'platform' else 'Linux')
    monkeypatch.setattr(pypi_smoke.platform, 'machine', lambda: 'x86_64')
    if failure:
        with pytest.raises(RuntimeError):
            pypi_smoke.check(VERSION, 'linux-x86_64', host=host)
    else:
        assert pypi_smoke.check(VERSION, 'linux-x86_64', host=host)['result'] == 'PASS'
    if failure in ('version', 'platform'):
        assert not starts and not closed
    else:
        assert starts == [({'host_binary': host} if host else {})]
        assert closed == [True]


@pytest.mark.parametrize('system,machine,expected', [
    ('Darwin', 'arm64', 'darwin-arm64'),
    ('Linux', 'x86_64', 'linux-x86_64'),
    ('Linux', 'aarch64', 'linux-aarch64'),
    ('Windows', 'AMD64', None),
])
def test_short_smoke_native_platform_is_explicit(monkeypatch, system, machine, expected):
    import pypi_smoke
    monkeypatch.setattr(pypi_smoke.platform, 'system', lambda: system)
    monkeypatch.setattr(pypi_smoke.platform, 'machine', lambda: machine)
    if expected is None:
        with pytest.raises(RuntimeError):
            pypi_smoke.native_platform()
    else:
        assert pypi_smoke.native_platform() == expected
