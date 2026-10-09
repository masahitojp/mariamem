"""Current public-asset trust boundary, without the retired native import island."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from published_assets import verify_downloads


@pytest.fixture
def assets(tmp_path):
    (tmp_path / 'wheel.whl').write_bytes(b'accepted wheel')
    digest = hashlib.sha256(b'accepted wheel').hexdigest()
    sums = f'{digest}  wheel.whl\n'
    (tmp_path / 'SHA256SUMS').write_text(sums)
    return tmp_path, {'wheel.whl': digest, 'SHA256SUMS': hashlib.sha256(sums.encode()).hexdigest()}


def test_exact_published_bytes(assets):
    root, record = assets
    assert verify_downloads(root, record) == record


@pytest.mark.parametrize('change', ['extra', 'missing', 'corrupted', 'wrong-manifest', 'duplicate-manifest'])
def test_changed_or_ambiguous_public_bytes_fail_closed(assets, change):
    root, record = assets
    if change == 'extra':
        (root / 'unexpected').write_bytes(b'x')
    elif change == 'missing':
        (root / 'wheel.whl').unlink()
    elif change == 'corrupted':
        (root / 'wheel.whl').write_bytes(b'changed')
    else:
        sums = root / 'SHA256SUMS'
        sums.write_text('0' * 64 + '  wheel.whl\n' if change == 'wrong-manifest' else sums.read_text() * 2)
        record['SHA256SUMS'] = hashlib.sha256(sums.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        verify_downloads(root, record)


def test_current_smoke_uses_live_shared_helper():
    path = Path(__file__).resolve().parents[1] / 'scripts/release_generated_ci.py'
    assert 'from published_assets import verify_downloads' in path.read_text()
    assert 'from ci_release_public_smoke import' not in path.read_text()


@pytest.fixture
def publication():
    from generated_release import CONTRACT, PLATFORMS, expected_names
    commit='a'*40; metadata={'GIT_TAG':'v0.4.5','PYTHON_VERSION':'0.4.5'}
    assets={name:'b'*64 for name in expected_names('0.4.5')|{'SHA256SUMS'}}
    platforms={}
    for platform in PLATFORMS:
        from generated_release import wheel_name
        platforms[platform]={'version':3,'contract':CONTRACT,'result':'READY',
            'source_commit':commit,'platform':platform, 'git_tag':'v0.4.5','python_version':'0.4.5',
            'acceptance_sha256':'c'*64, 'wheel_record':{'wheel':'build/dist/'+wheel_name('0.4.5',platform),
                                                     'source_commit':commit,'sha256':'b'*64}}
    record={'version':3,'contract':CONTRACT,'status':'PUBLISHED','source_commit':commit,
            'repository':'masahitojp/mariamem', **{'git_tag':metadata['GIT_TAG'],'python_version':metadata['PYTHON_VERSION']},
            'assets':assets,'platforms':platforms}
    import copy
    provenance={'contract':CONTRACT,'source_commit':commit,'platforms':copy.deepcopy(platforms),
        'assets':{n:h for n,h in assets.items() if n!='SHA256SUMS' and not n.endswith('-provenance.json')}}
    return record,provenance,commit,metadata


def test_narrow_smoke_requires_same_accepted_platform_artifacts(publication):
    from published_assets import verify_publication
    record,provenance,commit,metadata=publication
    assert verify_publication(record,provenance,commit,metadata,'masahitojp/mariamem')==record


@pytest.mark.parametrize('change', ['repository','tag','version','source','old-contract','assets',
                                  'platform','missing-platform','not-ready','acceptance','wheel'])
def test_unknown_or_mismatched_public_identity_cannot_narrow_smoke(publication,change):
    from published_assets import verify_publication
    record,provenance,commit,metadata=publication
    if change=='repository': record['repository']='another/repository'
    if change=='tag': record['git_tag']='v0.4.4'
    if change=='version': record['python_version']='0.4.4'
    if change=='source': provenance['source_commit']='d'*40
    if change=='old-contract': record['contract']='legacy'
    if change=='assets': provenance['assets'][next(iter(provenance['assets']))]='e'*64
    if change=='platform': provenance['platforms'][next(iter(record['platforms']))]['source_commit']='f'*40
    if change=='missing-platform': record['platforms'].pop(next(iter(record['platforms'])))
    if change in ('not-ready','acceptance','wheel'):
        platform=next(iter(record['platforms'])); ready=record['platforms'][platform]
        if change=='not-ready': ready['result']='NOT READY'
        if change=='acceptance': ready['acceptance_sha256']=''
        if change=='wheel': ready['wheel_record']['sha256']='e'*64
        import copy
        provenance['platforms']=copy.deepcopy(record['platforms'])
    with pytest.raises(ValueError): verify_publication(record,provenance,commit,metadata,'masahitojp/mariamem')
