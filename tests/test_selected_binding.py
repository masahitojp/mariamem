"""Registered exact bodies, selected handoff and installer refusal controls."""
import copy
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import selected_binding as binding
import install_selected_guest as installer
from common import digest


@pytest.fixture
def generated(tmp_path):
    tmp_path = tmp_path/'raw'
    tmp_path.mkdir()
    record, sha = binding.registered(ROOT, '13.2.0/native-text')
    for name, item in record['functions'].items():
        target = tmp_path/name.removeprefix('code/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT/'docs/design/issue134-binding'/(item['function']+'.txt')).read_text()+'\n')
    with (tmp_path/'p8/p8_pure.go').open('a') as out:
        out.write('func Fn131(m *base.Module, l0 int32) {\n return\n}\n')
    (tmp_path/'p8/p8.go').write_text('m.T0[94] = Fn131\n')
    (tmp_path/'generated.go').write_text('m.G2 = int32(489)\n')
    return record, tmp_path


def test_registered_binding_and_complete_bodies(generated):
    record, root = generated
    binding.validate_bodies(record, root)
    for name, item in record['functions'].items():
        source = (root/name.removeprefix('code/')).read_text()
        after = binding.apply(record, name, source)
        assert ('DeferThreadAllocationFree' in after) == (item['role'] == 'free')
    assert 'p3.Fn151' in binding.wrapper(record)


@pytest.mark.parametrize('role', ['free', 'yield', 'entry'])
@pytest.mark.parametrize('damage', ['constant', 'control', 'duplicate'])
def test_body_mutations_rejected(generated, role, damage):
    record, root = generated
    name, item = next((p,v) for p,v in record['functions'].items() if v['role'] == role)
    path = root/name.removeprefix('code/')
    source = path.read_text()
    if damage == 'constant':
        anchor = 'int32(1)' if 'int32(1)' in source else 'int32(0)'
        source = source.replace(anchor, 'int32(123)', 1)
    elif damage == 'control': source = source.replace('return', 'panic("bad"); return', 1)
    else: source += '\nfunc '+item['function']+'(m *base.Module, l0 int32) {return}\n'
    path.write_text(source)
    with pytest.raises(ValueError): binding.validate_bodies(record, root)


@pytest.mark.parametrize('file,old,new', [('generated.go','489','505'),
    ('p8/p8.go','Fn131','Fn129'),('p8/p8_pure.go',' return',' panic("bad"); return')])
def test_tls_and_noop_mutations_rejected(generated, file, old, new):
    record, root = generated
    path = root/file;path.write_text(path.read_text().replace(old,new))
    with pytest.raises(ValueError): binding.validate_bodies(record, root)


def test_wrong_registration_and_abi_rejected(tmp_path):
    shutil.copytree(ROOT/'guest/bindings',tmp_path/'guest/bindings')
    with pytest.raises(ValueError, match='not registered'): binding.registered(tmp_path,'13.0.2/native-text')
    path=tmp_path/'guest/bindings/13.2.0-native-text.json'
    data=json.loads(path.read_text());data['ABI_offsets']['pthread.map_base']=48
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='identity'): binding.registered(tmp_path,'13.2.0/native-text')
    registry=tmp_path/'guest/bindings/registry.json'
    data=json.loads(registry.read_text());data['13.2.0/native-text']['sha256']=digest(path)
    registry.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='ABI'): binding.registered(tmp_path,'13.2.0/native-text')


@pytest.fixture
def inputs(monkeypatch, generated):
    record, module = generated
    selected={'selection':record['selection'],'resolved_sha256':'a'*64}
    identity={'commit':'b'*40,'files_sha256':{}}
    monkeypatch.setattr(installer,'source_identity',lambda _: identity)
    monkeypatch.setattr(installer,'verify_handoff',lambda *a,**k:(selected,record,'c'*64))
    source=module.parent/'source'
    source.mkdir()
    shutil.copytree(module,source/'generated')
    (source/'generated/data.bin').write_bytes(b'data')
    receipt=dict(contract=binding.CONTRACT,result='UNQUALIFIED',release_eligible=False,
        installer_source_identity=identity,producer_directory='/producer',handoff_directory='/handoff',
        engine='13.2.0',profile='native-text',selection=selected['selection'],resolved_sha256='a'*64,
        binding_sha256='c'*64,guest_sha256=record['guest_sha256'],
        producer_source_commit=record['producer_source_commit'],
        source_inventory=installer.inventory(source),data_sha256=digest(source/'generated/data.bin'))
    return receipt,source


def test_selected_installation_positive(inputs):
    record,module=inputs
    assert installer.verify_installation(record,module,ROOT)[0] == record


@pytest.mark.parametrize('field', ['contract','result','release_eligible','installer_source_identity',
    'selection','resolved_sha256','binding_sha256','guest_sha256','producer_source_commit',
    'source_inventory','data_sha256'])
def test_selected_installation_tuple_refusals(inputs,field):
    record,module=inputs
    bad=copy.deepcopy(record);bad[field]='wrong'
    with pytest.raises(ValueError):installer.verify_installation(bad,module,ROOT)


def test_canonical_binding_remains_separate():
    import runtime_thread_lifetime as canonical
    record,_=binding.registered(ROOT,'13.2.0/native-text')
    assert canonical.GUEST_SHA256 != record['guest_sha256']
    with pytest.raises(ValueError):canonical.validate_inputs(record['guest_sha256'],{})
