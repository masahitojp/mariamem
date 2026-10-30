"""Exercise authenticated transport through the final guard, without remote writes.

Use tiny synthetic build/wheel/acceptance inputs in place of MariaDB artifacts.
ZIP/TAR transport, source comparison, aggregate guard, staging, and publisher
control flow are real. Existing generated-release tests own leaf artifact oracles.
"""
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import ci_release_publish as publisher
import generated_release as release
import release_generated_ci as transport
from ci_release_reuse import GitHub, WORKFLOW
from common import digest

SHA = 'a'*40
REPO = 'masahitojp/mariamem'


def archive_zip(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, value in files.items(): archive.writestr(name, value)
    return stream.getvalue()


def archive_tar(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name, value in files.items():
            item = tarfile.TarInfo(name); item.size = len(value)
            archive.addfile(item, io.BytesIO(value))
    return stream.getvalue()


@pytest.fixture
def handoff(tmp_path, monkeypatch):
    root = tmp_path/'source'; root.mkdir()
    for name, content in {
        'python/mariamem/_version.py': 'PYTHON_VERSION="0.4.0"\nGIT_TAG="v0.4.0"\nSTAGE=""\nSERIAL=0\n',
        'release/NOTES-v0.4.0.md': '# v0.4.0\n',
        'release/generated-go-inputs.json': '{}',
        'release/generated-go-toolchain.json': '{}',
        'internal/generatedgo/provenance.json': '{}',
    }.items():
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
    records = {}; guard_calls = []; commands = []; payloads = {}; corrupt_digest = set(); expired = set()
    monkeypatch.setattr(release, 'notices', lambda *a, **k: {})
    import check_version
    import runtime_validation
    monkeypatch.setattr(check_version, 'check_release_docs', lambda root: None)
    monkeypatch.setattr(runtime_validation, 'verify_frozen', lambda *a: None)
    # Tiny leaf fixtures retain corruption checks. The aggregate and publisher
    # cannot pass by merely trusting the downloaded READY document.
    def build(project, commit):
        value = release.read(project/'build/generated-release/guest.json')
        release.require(value == {'guest': {'guest_sha256': 'b'*64}}, 'guest fixture differs')
        return value
    def source(project, commit):
        name = release.source_name('0.4.0')
        release.require((project/'build/release'/name).read_bytes() == b'corresponding source', 'source fixture differs')
        return {'file': name, 'sha256': digest(project/'build/release'/name)}
    def wheel(project, platform, commit=None):
        value = release.read(project/'tests/evidence/alpha-wheel.json')
        path = project/value['wheel']
        release.require(value == records[platform] and digest(path) == value['sha256'], 'wheel fixture differs')
        return path, value
    def acceptance(project, commit, platform, wheel_sha):
        value = release.read(project/'build/release/generated-acceptance.json')
        release.require(value == {'source_commit': commit, 'wheel_sha256': wheel_sha, 'result': 'PASS'},
                        'acceptance fixture differs')
        return digest(project/'build/release/generated-acceptance.json')
    monkeypatch.setattr(release, 'verify_build', build)
    monkeypatch.setattr(release, 'verify_source', source)
    monkeypatch.setattr(release, 'verify_wheel', wheel)
    monkeypatch.setattr(release, 'verify_acceptance', acceptance)
    actual_guard = release.guard
    def guard(project, commit, platform):
        guard_calls.append(platform)
        return actual_guard(project, commit, platform)
    monkeypatch.setattr(release, 'guard', guard)
    for platform in release.PLATFORMS:
        project = root/'build/platforms'/platform
        for path in transport.public_files(root):
            target = project/path.relative_to(root); target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        name = 'build/dist/'+release.wheel_name('0.4.0', platform)
        content = ('wheel '+platform).encode()
        records[platform] = {'wheel': name, 'sha256': hashlib.sha256(content).hexdigest()}
        inputs = {name: content,
                  'tests/evidence/alpha-wheel.json': json.dumps(records[platform]).encode(),
                  'build/generated-release/guest.json': json.dumps({'guest': {'guest_sha256': 'b'*64}}).encode(),
                  'build/generated-release/regeneration.json': b'{}',
                  'build/release/'+release.source_name('0.4.0'): b'corresponding source'}
        evidence = {'build/release/generated-acceptance.json': json.dumps({
            'source_commit': SHA, 'wheel_sha256': records[platform]['sha256'], 'result': 'PASS'}).encode(),
                    'tests/evidence/alpha.json': b'{}'}
        for path, data in {**inputs, **evidence}.items():
            target = project/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        tar = archive_tar(inputs)
        payloads[(10, 'release-candidate-'+platform+'-'+SHA)] = archive_zip({
            'candidate-handoff.tar': tar, 'candidate-handoff.sha256': hashlib.sha256(tar).hexdigest()})
        payloads[(20, 'release-evidence-'+platform+'-'+SHA)] = archive_zip(evidence)
    ready = release.check_aggregate(root, SHA)
    payloads[(20, 'release-ready-'+SHA)] = archive_zip({
        'ci-ready.json': json.dumps(ready),
        'SHA256SUMS': ''.join(f'{sha}  {name}\n' for name, sha in ready['assets'].items()),
        'qualification.json': json.dumps({'version': 2, 'source_commit': SHA,
                                         'candidate_run': 10, 'evidence_run': 20, 'feature_run': 20})})
    shutil.rmtree(root/'build')
    guard_calls.clear()
    keys = list(payloads); fetched = []
    class FixtureGitHub(GitHub):
        def __init__(self, repository, token): assert repository == REPO
        def json(self, path):
            if '/artifacts?' in path:
                run = int(path.split('/runs/')[1].split('/')[0])
                return {'artifacts': [{'id': i, 'name': key[1], 'expired': key in expired,
                        'digest': 'sha256:'+('0'*64 if key in corrupt_digest else hashlib.sha256(payloads[key]).hexdigest())}
                        for i, key in enumerate(keys, 1) if key[0] == run and key in payloads]}
            return {'path': WORKFLOW}
        def request(self, path):
            key = keys[int(path.split('/artifacts/')[1].split('/')[0])-1]
            fetched.append(key)
            return io.BytesIO(payloads[key])
    monkeypatch.setattr(publisher, 'GitHub', FixtureGitHub)
    def command(args, cwd):
        commands.append(args)
        if args[:2] == ['git', 'rev-parse']: return SHA
        if args[:2] == ['git', 'ls-files']: return 'release/NOTES-v0.4.0.md'
        if args[:3] == ['gh', 'api', f'repos/{REPO}/commits/{SHA}']: return json.dumps({'sha': SHA})
        return ''
    monkeypatch.setattr(publisher, 'command', command)
    monkeypatch.setattr(publisher, 'release_exists', lambda *a: False)
    return root, ready, payloads, guard_calls, commands, fetched, corrupt_digest, expired


def mutations(commands):
    return [c for c in commands if c[:2] in (['git', 'tag'], ['git', 'push'], ['gh', 'release'])
            and (c[:2] != ['git', 'tag'] or '-a' in c)]


def test_authenticated_publication_runs_one_final_guard_per_platform(handoff):
    root, ready, _, guards, commands, fetched, *_ = handoff
    result = publisher.publish(root, SHA, REPO, dry_run=True, candidate_run=10, evidence_run=20)
    assert result['status'] == 'DRY_RUN'
    assert guards == list(release.PLATFORMS)
    assert len(fetched) == 5 and len(set(fetched)) == 5  # READY + two handoffs + two evidence ZIPs.
    assert not mutations(commands)
    for name, sha in ready['assets'].items(): assert digest(root/'build/release/publish'/name) == sha


@pytest.mark.parametrize('failure', ['digest', 'expired', 'missing', 'wrong-ready-source', 'wrong-reference',
                                     'ready-assets', 'wheel', 'source', 'acceptance', 'guest', 'traversal'])
def test_bad_handoff_stops_before_any_publication_mutation(handoff, failure):
    root, ready, payloads, guards, commands, _, corrupt, expired = handoff
    key = (20, 'release-ready-'+SHA)
    if failure == 'digest': corrupt.add(key)
    elif failure == 'expired': expired.add(key)
    elif failure == 'missing': del payloads[key]
    elif failure in ('wrong-ready-source', 'wrong-reference', 'ready-assets'):
        with zipfile.ZipFile(io.BytesIO(payloads[key])) as zipped:
            files = {name: zipped.read(name) for name in zipped.namelist()}
        name = 'qualification.json' if failure == 'wrong-reference' else 'ci-ready.json'
        data = json.loads(files[name])
        if failure == 'ready-assets':
            data['assets'][next(iter(data['assets']))] = 'f'*64
            files['SHA256SUMS'] = ''.join(f'{sha}  {name}\n' for name, sha in data['assets'].items())
        else:
            data['source_commit' if failure == 'wrong-ready-source' else 'candidate_run'] = 'b'*40 if failure == 'wrong-ready-source' else 99
        files[name] = json.dumps(data); payloads[key] = archive_zip(files)
    elif failure == 'acceptance':
        key = (20, 'release-evidence-'+release.DARWIN+'-'+SHA)
        payloads[key] = archive_zip({'build/release/generated-acceptance.json': b'{"result":"FAIL"}'})
    else:
        key = (10, 'release-candidate-'+release.DARWIN+'-'+SHA)
        with zipfile.ZipFile(io.BytesIO(payloads[key])) as zipped:
            tar = zipped.read('candidate-handoff.tar')
        with tarfile.open(fileobj=io.BytesIO(tar), mode='r:') as archive:
            files = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
        name = {'wheel': 'build/dist/'+release.wheel_name('0.4.0', release.DARWIN),
                'source': 'build/release/'+release.source_name('0.4.0'),
                'guest': 'build/generated-release/guest.json', 'traversal': '../escape'}[failure]
        files[name] = b'{}'
        tar = archive_tar(files)
        payloads[key] = archive_zip({'candidate-handoff.tar': tar,
                                    'candidate-handoff.sha256': hashlib.sha256(tar).hexdigest()})
    with pytest.raises((ValueError, KeyError)):
        publisher.publish(root, SHA, REPO, candidate_run=10, evidence_run=20)
    assert not mutations(commands)
    assert release.read(root/'build/release/ci-publication.json')['status'] == 'FAILED'
    assert not (root/'build/release/ci-ready.json').exists()


def test_remote_restore_cannot_be_combined_with_external_ready_override(handoff):
    root, _, _, _, commands, *_ = handoff
    with pytest.raises(ValueError, match='cannot override'):
        publisher.publish(root, SHA, REPO, ready_path=root/'other.json', candidate_run=10, evidence_run=20)
    assert not mutations(commands)


@pytest.mark.parametrize('candidate_run,evidence_run', [(10,None), (None,20), (True,20), (10,0)])
def test_incomplete_or_invalid_run_references_do_not_restore_or_publish(handoff, candidate_run, evidence_run):
    root, _, _, guards, commands, fetched, *_ = handoff
    with pytest.raises(ValueError, match='exact candidate and evidence'):
        publisher.publish(root, SHA, REPO, candidate_run=candidate_run, evidence_run=evidence_run)
    assert not guards and not fetched and not mutations(commands)


def test_changed_staged_bytes_stop_before_remote_mutations(handoff, monkeypatch):
    root, _, _, _, commands, *_ = handoff
    stage = publisher.stage
    def corrupt(project, checked):
        stage(project, checked)
        (project/'build/release/publish'/next(iter(checked['assets']))).write_bytes(b'changed after guard')
    monkeypatch.setattr(publisher, 'stage', corrupt)
    with pytest.raises(ValueError, match='artifact hash differs'):
        publisher.publish(root, SHA, REPO, candidate_run=10, evidence_run=20)
    assert not mutations(commands)
