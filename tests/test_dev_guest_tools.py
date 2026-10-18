"""Dev-only identity and failure gates; no compiler/guest download required."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import dev_guest as dev
import regenerate_release_guest as regeneration
from common import digest
from generated_release import verify_build


@pytest.fixture
def guest(tmp_path, monkeypatch):
    root = tmp_path/'repo'
    (root/'release').mkdir(parents=True)
    (root/'guest').mkdir()
    (root/'guest/source.patch').write_text('patch')
    (root/'release/inputs.lock.json').write_text('{}')
    tools = {'archives':{'converter':{'sha256':'a'*64}}}
    dev.write(root/'release/generated-go-toolchain.json',tools)
    directory = tmp_path/'dev'
    directory.mkdir()
    (directory/'mariamem.wasm').write_bytes(b'wasm')
    (directory/'linked.wasm').write_bytes(b'linked')
    identity = {'commit':'a'*40,'files_sha256':{'source':'b'*64}}
    monkeypatch.setattr(dev,'source_identity',lambda _:copy.deepcopy(identity))
    record = {'contract':dev.CONTRACT,'result':'UNQUALIFIED','source_identity':copy.deepcopy(identity),
              'toolchain':{'pins_sha256':digest(root/'release/generated-go-toolchain.json'),
                           'archives_sha256':{'converter':'a'*64}},
              'prepared_source':{'inputs_lock_sha256':digest(root/'release/inputs.lock.json'),
                                 'overlays':{'source.patch':digest(root/'guest/source.patch')}},
              'guest_sha256':digest(directory/'mariamem.wasm'),'guest_bytes':4,
              'repetitions':[{'guest_sha256':digest(directory/'mariamem.wasm'),
                              'linked_sha256':digest(directory/'linked.wasm')}]}
    dev.write(directory/'guest.json',record)
    return root,directory,record


def test_bound_guest(guest):
    root,directory,record=guest
    assert dev.verify_guest(root,directory)==record


@pytest.mark.parametrize('damage',['source','wasm','tool','missing','contract','linked','patch'])
def test_guest_rejects_wrong_identity_and_provenance(guest,damage):
    root,directory,record=guest
    if damage=='source':record['source_identity']['commit']='c'*40
    if damage=='wasm':(directory/'mariamem.wasm').write_bytes(b'bad!')
    if damage=='tool':record['toolchain']['pins_sha256']='c'*64
    if damage=='contract':record['contract']='generated-go-v1'
    if damage=='linked':(directory/'linked.wasm').write_bytes(b'bad')
    if damage=='patch':(root/'guest/source.patch').write_text('other')
    dev.write(directory/'guest.json',record)
    if damage=='missing':(directory/'guest.json').unlink()
    with pytest.raises((ValueError,FileNotFoundError)):
        dev.verify_guest(root,directory)


@pytest.mark.parametrize('relative',['build/generated-release','internal/generatedgo','python/mariamem/_native','release'])
def test_canonical_and_release_outputs_rejected(tmp_path,relative):
    with pytest.raises(ValueError,match='outside'):
        dev.external_output(tmp_path,tmp_path/relative)


def test_existing_and_symlink_outputs_rejected(tmp_path):
    root=tmp_path/'source';root.mkdir()
    old=tmp_path/'old';old.mkdir()
    with pytest.raises(ValueError,match='fresh'):dev.external_output(root,old)
    (tmp_path/'alias').symlink_to(old, target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):dev.external_output(root,tmp_path/'alias'/'new')


def test_stale_generated_candidate_cannot_be_installed(tmp_path):
    module=tmp_path/'module';(module/'generated').mkdir(parents=True)
    (module/'generated/data.bin').write_bytes(b'data')
    (module/'generated/a.go').write_text('original')
    record={'contract':dev.CONTRACT,'result':'UNQUALIFIED','source_inventory':dev.inventory(module),
            'data_sha256':digest(module/'generated/data.bin'), 'guest_record_sha256':'a'*64,
            'translation_record_sha256':'b'*64, 'guest_sha256':'c'*64}
    assert dev.install_inputs(record,module)==record
    (module/'generated/a.go').write_text('old guest')
    with pytest.raises(ValueError,match='candidate source'):dev.install_inputs(record,module)


def test_translation_binds_guest_converter_patches_and_complete_inventory(tmp_path):
    root=tmp_path/'source';(root/'release').mkdir(parents=True)
    patches=root/'benchmarks/spikes/wasm2go';patches.mkdir(parents=True)
    (patches/'p.patch').write_bytes(b'patch')
    dev.write(root/'release/generated-go-toolchain.json',{'archives':{'converter':{'sha256':'a'*64}}})
    dev.write(root/'release/generated-go-translation.json',{'patches_sha256':{'p.patch':'ignored'},'converter_commit':'c'*40})
    out=tmp_path/'out';(out/'module/generated').mkdir(parents=True)
    (out/'guest.wasm').write_bytes(b'guest');(out/'wasm2go').write_bytes(b'converter')
    (out/'module/generated/generated.go').write_text('guest-code')
    record={'guest_sha256':digest(out/'guest.wasm'),'converter_commit':'c'*40,'converter_archive_sha256':'a'*64,
            'patched_converter_sha256':digest(out/'wasm2go'),
            'patches_sha256':{'p.patch':digest(patches/'p.patch')},
            'files_sha256':dev.inventory(out/'module/generated')}
    dev.write(out/'input-manifest.json',record)
    assert dev.verify_translation(root,out,record['guest_sha256'])==record
    (out/'module/generated/stale.go').write_text('stale')
    with pytest.raises(ValueError,match='stale/mixed'):dev.verify_translation(root,out,record['guest_sha256'])


def test_partial_generation_never_emits_success_or_canonical_output(guest,tmp_path,monkeypatch):
    root,directory,record=guest
    import build_feedback,build_generated_guest
    monkeypatch.setattr(build_generated_guest,'download',lambda *_:tmp_path/'converter.tar')
    monkeypatch.setattr(build_feedback,'go_environment',lambda e:e)
    def fail(*args,**kwargs):raise subprocess.CalledProcessError(23,args[0])
    monkeypatch.setattr(build_feedback,'run',fail)
    out=tmp_path/'partial'
    with pytest.raises(subprocess.CalledProcessError):dev.regenerate_development(root,directory,out)
    assert json.loads((out/'failure.json').read_text())['result']=='FAILED'
    assert not (out/'development.json').exists()
    assert not (root/'internal/generatedgo').exists()


def test_existing_release_guard_rejects_dev_receipts(guest):
    root,directory,record=guest
    # Reach the existing contract check, rather than relying on a missing file.
    for name in ['generated-go-inputs.json','generated-go-build.json']:
        dev.write(root/'release'/name,{})
    dev.write(directory/'regeneration.json',{'contract':dev.CONTRACT})
    with pytest.raises(ValueError,match='wrong build contract'):
        verify_build(root,'a'*40,directory)


def test_dev_and_release_entrypoints_parse():
    for script in ['scripts/build_generated_guest.py','scripts/regenerate_release_guest.py','scripts/generate_runtime.py']:
        result=subprocess.run([sys.executable,str(ROOT/script),'--help'],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert '--development' in result.stdout


def test_missing_installation_provenance_rejected(tmp_path):
    module=tmp_path/'module';module.mkdir()
    with pytest.raises((ValueError,KeyError)):
        dev.install_inputs({'contract':dev.CONTRACT,'result':'UNQUALIFIED'},module)


def test_external_release_namespace_rejected(tmp_path):
    with pytest.raises(ValueError,match='namespace'):
        dev.external_output(tmp_path/'source',tmp_path/'other-checkout/build/generated-release')


def test_historical_guest_origin_allows_only_bound_host_stage_changes(tmp_path):
    root=tmp_path/'repo';(root/'scripts').mkdir(parents=True)
    (root/'guest').mkdir()
    (root/'scripts/dev_guest.py').write_text('old host stage')
    (root/'scripts/runtime_thread_lifetime.py').write_text('old exact binding')
    (root/'guest/source.patch').write_text('guest patch')
    (root/'internal/mysqlwire').mkdir(parents=True)
    (root/'internal/mysqlwire/wire.go').write_text('old authored host')
    (root/'internal/mysqlwire/multi_spike_test.go').write_text('old host test')
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root,text=True)
    git('init','-q');git('config','user.name','fixture');git('config','user.email','fixture@example.invalid')
    git('add','.');git('commit','-qm','guest origin')
    origin=dev.source_identity(root)
    (root/'scripts/dev_guest.py').write_text('fixed host stage')
    (root/'scripts/runtime_thread_lifetime.py').write_text('reviewed exact binding')
    (root/'internal/mysqlwire/wire.go').write_text('fixed authored host')
    (root/'internal/mysqlwire/multi_spike_test.go').write_text('fixed host test')
    git('add','.');git('commit','-qm','host fix')
    dev.verify_source_origin(root,origin)
    wrong=copy.deepcopy(origin);wrong['files_sha256']['scripts/dev_guest.py']='f'*64
    with pytest.raises(ValueError,match='historical source hash'):
        dev.verify_source_origin(root,wrong)
    wrong=copy.deepcopy(origin);wrong['files_sha256']['internal/mysqlwire/wire.go']='f'*64
    with pytest.raises(ValueError,match='historical source hash'):
        dev.verify_source_origin(root,wrong)
    (root/'internal/mysqlwire/unclassified.go').write_text('unclassified input')
    git('add','.');git('commit','-qm','unclassified addition')
    with pytest.raises(ValueError,match='fresh guest build'):
        dev.verify_source_origin(root,origin)
    (root/'internal/mysqlwire/unclassified.go').unlink()
    git('add','.');git('commit','-qm','remove unclassified addition')
    (root/'guest/source.patch').write_text('different guest')
    git('add','.');git('commit','-qm','guest change')
    with pytest.raises(ValueError,match='fresh guest build'):
        dev.verify_source_origin(root,origin)
