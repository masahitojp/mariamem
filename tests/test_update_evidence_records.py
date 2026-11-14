"""Ledger updates preserve independent audit pins and reject source drift."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import update_evidence_records as updater
from update_evidence_records import planned_updates
from distribution_licenses import attribution_tolerance


def test_current_ledgers_are_fresh():
    updater.main(['--check'], root=ROOT)


@pytest.fixture
def ledger(tmp_path):
    for directory in ('release', 'python', 'licenses', 'internal/generatedgo/image'):
        (tmp_path/directory).mkdir(parents=True)
    policy=json.loads((ROOT/'release/attribution-tolerance.json').read_text())
    policy['metadata_files'][0]['before']=None
    (tmp_path/'release/attribution-tolerance.json').write_text(json.dumps(policy,indent=2)+'\n')
    def write(name, value):
        raw=(json.dumps(value, indent=2)+'\n').encode()
        (tmp_path/name).write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    audit={'guest_sha256':'guest','files_sha256':{}}
    audited=hashlib.sha256((json.dumps(audit,indent=2)+'\n').encode()).hexdigest()
    metadata=write('internal/generatedgo/image/layout.json', {})
    audit['files_sha256']['image/layout.json']=metadata
    write('internal/generatedgo/provenance.json',audit)
    evidence={'guest_sha256':'guest','linked_sha256':'linked','generated_provenance_sha256':audited}
    evidence_hash=write('release/generated-license-evidence.json',evidence)
    write('release/generated-go-inputs.json',{'guest_sha256':'guest'})
    write('release/generated-go-build.json',{'guest_sha256':'guest','linked_guest_sha256':'linked'})
    value={'version':1,'contract':'generated-go-v1','distributed_notices':{},'legacy_notices':{},'components':{},'evidence_sha256':evidence_hash}
    write('release/distribution-licenses.json',value)
    write('python/license-inventory.json',value)
    return tmp_path


def test_metadata_update_is_minimal_and_idempotent(ledger):
    before=(ledger/'release/generated-license-evidence.json').read_bytes()
    updates=planned_updates(ledger)
    assert set(updates)=={'release/generated-license-evidence.json','release/distribution-licenses.json','python/license-inventory.json'}
    assert (ledger/'release/generated-license-evidence.json').read_bytes()==before
    for name,raw in updates.items(): (ledger/name).write_bytes(raw)
    assert planned_updates(ledger)=={}


@pytest.mark.parametrize('mutation',['guest','source','metadata','reason'])
def test_unapproved_changes_rejected_before_writes(ledger,mutation):
    before=(ledger/'release/generated-license-evidence.json').read_bytes()
    if mutation=='metadata':
        (ledger/'internal/generatedgo/image/layout.json').write_text('changed')
    else:
        name={'guest':'release/generated-go-inputs.json','source':'internal/generatedgo/provenance.json','reason':'release/attribution-tolerance.json'}[mutation]
        value=json.loads((ledger/name).read_text())
        if mutation=='guest': value['guest_sha256']='different'
        elif mutation=='source': value['files_sha256']['extra.go']='0'*64
        else: value['metadata_files'][0]['reason']=''
        (ledger/name).write_text(json.dumps(value,indent=2)+'\n')
    with pytest.raises(ValueError): planned_updates(ledger)
    assert (ledger/'release/generated-license-evidence.json').read_bytes()==before


def test_explicit_source_delta_requires_exact_approved_hash(ledger):
    name='internal/generatedgo/provenance.json'
    record=json.loads((ledger/name).read_text())
    raw=b'approved handwritten helper'
    (ledger/'internal/generatedgo/helper.go').write_bytes(raw)
    checksum=hashlib.sha256(raw).hexdigest()
    record['files_sha256']['helper.go']=checksum
    (ledger/name).write_text(json.dumps(record,indent=2)+'\n')
    with pytest.raises(ValueError): planned_updates(ledger)
    policy=json.loads((ledger/'release/attribution-tolerance.json').read_text())
    policy['generated_file_deltas']=[{'path':'helper.go','before':None,'after':checksum,'reason':'Approved source continuity fixture','approval':'test decision'}]
    (ledger/'release/attribution-tolerance.json').write_text(json.dumps(policy,indent=2)+'\n')
    updates=planned_updates(ledger)
    evidence=json.loads(updates[updater.LEDGERS[0]])
    assert evidence['attribution_continuity']['kind']=='reviewed-generated-source-delta'
    assert 'metadata_only_provenance_sha256' not in evidence
    (ledger/'internal/generatedgo/helper.go').write_bytes(b'unapproved')
    with pytest.raises(ValueError): planned_updates(ledger)


def rewrite(path, value):
    path.write_bytes(updater.encoded(value))


def adopt_current_fixture(ledger):
    """Create an independent audited baseline that already includes metadata."""
    provenance=ledger/'internal/generatedgo/provenance.json'
    evidence=ledger/updater.LEDGERS[0]
    value=json.loads(evidence.read_text())
    value['generated_provenance_sha256']=updater.sha(provenance.read_bytes())
    rewrite(evidence,value)
    inventory=json.loads((ledger/updater.LEDGERS[1]).read_text())
    inventory['evidence_sha256']=updater.sha(evidence.read_bytes())
    for name in updater.LEDGERS[1:]: rewrite(ledger/name,inventory)
    policy=json.loads((ledger/'release/attribution-tolerance.json').read_text())
    policy['metadata_files'][0]['before']=json.loads(provenance.read_text())['files_sha256']['image/layout.json']
    rewrite(ledger/'release/attribution-tolerance.json',policy)


@pytest.mark.parametrize('change',['metadata','source','both'])
def test_audited_metadata_preserved_during_reconstruction(ledger,change):
    adopt_current_fixture(ledger)
    provenance=ledger/'internal/generatedgo/provenance.json'
    record=json.loads(provenance.read_text())
    if change in ('metadata','both'):
        metadata=ledger/'internal/generatedgo/image/layout.json'
        metadata.write_text('{  }\n')  # formatting-only metadata change
        record['files_sha256']['image/layout.json']=updater.sha(metadata.read_bytes())
    if change in ('source','both'):
        helper=ledger/'internal/generatedgo/helper.go'
        helper.write_text('reviewed source')
        checksum=updater.sha(helper.read_bytes())
        record['files_sha256']['helper.go']=checksum
        policy=json.loads((ledger/'release/attribution-tolerance.json').read_text())
        policy['generated_file_deltas']=[{'path':'helper.go','before':None,'after':checksum,
                                         'reason':'fixture source continuity','approval':'fixture decision'}]
        rewrite(ledger/'release/attribution-tolerance.json',policy)
    rewrite(provenance,record)
    updates=planned_updates(ledger)
    evidence=json.loads(updates[updater.LEDGERS[0]])
    expected=('unchanged-generated-code; image-metadata-only' if change=='metadata'
              else 'reviewed-generated-source-delta')
    assert evidence['attribution_continuity']['kind']==expected
    updater.apply_updates(ledger,updates)
    assert planned_updates(ledger)=={}


def test_reviewed_rename_reconstructs_original_audit(ledger):
    generated=ledger/'internal/generatedgo'
    (generated/'old.go').write_text('reviewed original')
    before=updater.sha((generated/'old.go').read_bytes())
    record=json.loads((generated/'provenance.json').read_text())
    record['files_sha256']['old.go']=before
    record['files_sha256']=dict(sorted(record['files_sha256'].items()))
    rewrite(generated/'provenance.json',record)
    adopt_current_fixture(ledger)
    (generated/'old.go').unlink()
    (generated/'new.go').write_text('reviewed replacement')
    after=updater.sha((generated/'new.go').read_bytes())
    del record['files_sha256']['old.go']
    record['files_sha256']['new.go']=after
    rewrite(generated/'provenance.json',record)
    policy=json.loads((ledger/'release/attribution-tolerance.json').read_text())
    policy['generated_file_deltas']=[
        {'path':name,'before':old,'after':new,'reason':'reviewed rename','approval':'fixture decision'}
        for name,old,new in [('old.go',before,None),('new.go',None,after)]]
    rewrite(ledger/'release/attribution-tolerance.json',policy)
    assert planned_updates(ledger)
    (generated/'new.go').write_text('unreviewed')
    with pytest.raises(ValueError): planned_updates(ledger)


@pytest.mark.parametrize('boundary', [0,1,2])
@pytest.mark.parametrize('error', [OSError, KeyboardInterrupt])
def test_failed_write_recovers_and_retries(ledger,monkeypatch,boundary,error):
    originals={name:(ledger/name).read_bytes() for name in updater.LEDGERS}
    updates=planned_updates(ledger)
    real_write=updater.atomic_write
    interrupted=False
    def fail_once(path,data):
        nonlocal interrupted
        real_write(path,data)
        if path==ledger/updater.LEDGERS[boundary] and not interrupted:
            interrupted=True
            raise error('injected interruption after replacement')
    monkeypatch.setattr(updater,'atomic_write',fail_once)
    with pytest.raises(error): updater.apply_updates(ledger,updates)
    if error is OSError:
        assert all((ledger/n).read_bytes()==v for n,v in originals.items())
    else:
        with pytest.raises(ValueError,match='unfinished'): planned_updates(ledger)
    # Use the CLI path: recovery is automatic for --update and followed by validation.
    updater.main(['--update'],root=ledger)
    updater.main(['--check'],root=ledger)
    assert all((ledger/n).read_bytes()==updates[n] for n in updates)
    assert not (ledger/updater.JOURNAL).exists()


def test_recovery_preserves_intervening_user_edit(ledger,monkeypatch):
    real_write=updater.atomic_write
    def interrupt(path,data):
        real_write(path,data)
        if path==ledger/updater.LEDGERS[0]: raise KeyboardInterrupt()
    monkeypatch.setattr(updater,'atomic_write',interrupt)
    with pytest.raises(KeyboardInterrupt): updater.apply_updates(ledger,planned_updates(ledger))
    path=ledger/updater.LEDGERS[2]
    path.write_text('user edit')
    snapshot={n:(ledger/n).read_bytes() for n in updater.LEDGERS}
    with pytest.raises(ValueError,match='changed since'): updater.recover_update(ledger)
    assert all((ledger/n).read_bytes()==v for n,v in snapshot.items())


def test_check_is_read_only_and_cli_update_is_idempotent(ledger):
    before={n:(ledger/n).read_bytes() for n in updater.LEDGERS}
    with pytest.raises(SystemExit) as error: updater.main(['--check'],root=ledger)
    assert error.value.code==1
    assert all((ledger/n).read_bytes()==v for n,v in before.items())
    updater.main(['--update'],root=ledger)
    after={n:(ledger/n).read_bytes() for n in updater.LEDGERS}
    updater.main(['--update'],root=ledger)
    assert all((ledger/n).read_bytes()==v for n,v in after.items())
    updater.main(['--check'],root=ledger)
