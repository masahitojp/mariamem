"""Normal notices are explicit; legacy attribution and guest sources survive."""
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1] / 'scripts'))
from layout import GENERATED
import json
from pathlib import Path
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from distribution_licenses import inventory, paths, source_inputs


def test_distribution_partition_and_source_inputs():
    value = inventory(ROOT)
    normal = {p.name for p in paths(ROOT)}
    legacy = {p.name for p in paths(ROOT,legacy=True)}
    assert not any(n.startswith('Wasmer-') for n in normal)
    assert set(value['legacy_notices']) <= legacy
    assert {'LLVM-compiler-rt-LICENSE.txt','LLVM-libcxx-LICENSE.txt',
            'LLVM-libcxxabi-LICENSE.txt','LLVM-libunwind-LICENSE.txt',
            'WASIX-dlmalloc-NOTICE.txt','wasm2go-MIT.txt','wolfSSL-LICENSING.txt'} <= normal
    lock=json.loads((ROOT/'release/inputs.lock.json').read_text())
    selected={e['name'] for e in source_inputs(ROOT,lock)}
    original={e['name'] for e in lock['inputs'] if e.get('kind')!='runtime-binary'}
    assert original-selected == {'wasmer-source'}
    assert {'wasix-libc','llvm-project','wasi-headers','wasix-headers',
            'wolfssl','lite4mariadb','libmariadb','pcre2','libfmt'} <= selected


def test_unclassified_changed_and_missing_notices_fail(tmp_path):
    shutil.copytree(ROOT/'licenses',tmp_path/'licenses')
    (tmp_path/'release').mkdir()
    for name in ('distribution-licenses.json','generated-license-evidence.json'):
        shutil.copyfile(ROOT/'release'/name,tmp_path/'release'/name)
    extra=tmp_path/'licenses/unclassified.txt';extra.write_text('new')
    with pytest.raises(ValueError,match='unclassified'):inventory(tmp_path)
    extra.unlink()
    original=tmp_path/'licenses/wasm2go-MIT.txt';content=original.read_bytes()
    original.write_text('changed')
    with pytest.raises(ValueError,match='bytes differ'):inventory(tmp_path)
    original.write_bytes(content);original.unlink()
    with pytest.raises(ValueError,match='missing'):inventory(tmp_path)


def test_evidence_bound_to_adopted_guest_and_generated_source():
    from common import digest
    inventory(ROOT)
    evidence=json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    pins=json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    build=json.loads((ROOT/'release/generated-go-build.json').read_text())
    assert evidence['guest_sha256']==pins['guest_sha256']==build['guest_sha256']
    assert evidence['linked_sha256']==build['linked_guest_sha256']
    from distribution_licenses import verify_generated_attribution
    verify_generated_attribution(ROOT, evidence)
    assert evidence['audit_source_commit']==evidence['host_check']['source_commit']
    assert evidence['symbol_map_entries'] > 0
    assert evidence['historical_evidence']['source_commit']=='e0be06f3a20c72cbb5a9be27971280c80a3ec357'
    assert set(evidence['retained_symbols']) == {'MariaDB','lite4mariadb','WASIX libc',
        'wolfSSL','zlib','PCRE2','fmt','libc++','libc++abi','libunwind','compiler-rt','dlmalloc'}
    for row in evidence['retained_symbols'].values():
        assert row['generated_definitions'] and row['host_named_definitions']
        assert any(x['host_symbol_retained'] for x in row['examples'])
        for example in row['examples']:
            assert ('func '+example['generated_function']+'(') in (ROOT/example['generated_file']).read_text()


def test_upstream_notice_comparison_checks_original_not_just_repository_hash(tmp_path):
    import io
    import tarfile
    from common import digest
    from distribution_licenses import verify_upstream_notices
    (tmp_path/'licenses').mkdir();(tmp_path/'release').mkdir();downloads=tmp_path/'build/downloads';downloads.mkdir(parents=True)
    text=tmp_path/'licenses/original.txt';text.write_text('original')
    evidence=tmp_path/'release/generated-license-evidence.json';evidence.write_text('{}')
    value={'version':1,'contract':'generated-go-v1','components':{'library':'DISTRIBUTED / DERIVED'},
           'distributed_notices':{'original.txt':digest(text)},'legacy_notices':{},
           'legacy_source_inputs':['wasmer-source'],'evidence_sha256':digest(evidence),
           'upstream_notice_files':{'original.txt':{'input':'library','path':'LICENSE'}}}
    def record():
        (tmp_path/'release/distribution-licenses.json').write_text(json.dumps(value))
    record();archive=downloads/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        m=tarfile.TarInfo('library-revision/LICENSE');m.size=8;t.addfile(m,io.BytesIO(b'original'))
    lock={'inputs':[{'name':'library','file':archive.name,'sha256':digest(archive)}]}
    assert verify_upstream_notices(tmp_path,lock)
    text.write_text('modified');value['distributed_notices']['original.txt']=digest(text);record()
    with pytest.raises(ValueError,match='upstream notice bytes differ'):verify_upstream_notices(tmp_path,lock)


def test_image_metadata_cannot_hide_generated_attribution_drift(tmp_path):
    from distribution_licenses import verify_generated_attribution
    from common import digest
    import shutil
    (tmp_path/'release').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'release/attribution-tolerance.json', tmp_path/'release/attribution-tolerance.json')
    policy_path = tmp_path/'release/attribution-tolerance.json'
    policy = json.loads(policy_path.read_text())
    policy['metadata_files'][0]['before'] = None
    policy_path.write_text(json.dumps(policy, indent=2)+'\n')
    target = tmp_path/GENERATED
    (target/'image').mkdir(parents=True)
    for name in ('provenance.json', 'image/layout.json'):
        shutil.copyfile(ROOT/GENERATED/name, target/name)
    evidence = json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    # Exercise the historical metadata-only path independently of whether the
    # current canonical audit already includes image metadata.
    import hashlib
    historical = json.loads((target/'provenance.json').read_text())
    historical['files_sha256'].pop('image/layout.json')
    evidence.pop('audited_image_metadata_sha256', None)
    evidence['generated_provenance_sha256'] = hashlib.sha256(
        (json.dumps(historical, indent=2)+'\n').encode()).hexdigest()
    assert verify_generated_attribution(tmp_path, evidence) == 'unchanged-generated-code; image-metadata-only'
    original = (target/'provenance.json').read_bytes()
    for mutation in ('source', 'extra', 'guest'):
        value = json.loads(original)
        if mutation == 'source': value['files_sha256']['code/alias.go'] = '0'*64
        elif mutation == 'extra': value['files_sha256']['extra.json'] = '0'*64
        else: value['guest_sha256'] = '0'*64
        (target/'provenance.json').write_text(json.dumps(value, indent=2)+'\n')
        with pytest.raises(ValueError, match='beyond image metadata'):
            verify_generated_attribution(tmp_path, evidence)
    (target/'provenance.json').write_bytes(original)
    (target/'image/layout.json').write_text('{}')
    with pytest.raises(ValueError, match='metadata mismatch'):
        verify_generated_attribution(tmp_path, evidence)


def test_replaced_image_binding_reconstructs_exact_audited_provenance(tmp_path):
    from distribution_licenses import verify_generated_attribution
    import shutil
    (tmp_path/'release').mkdir()
    shutil.copyfile(ROOT/'release/attribution-tolerance.json', tmp_path/'release/attribution-tolerance.json')
    target = tmp_path/GENERATED
    shutil.copytree(ROOT/(GENERATED / 'image'), target/'image')
    shutil.copyfile(ROOT/(GENERATED / 'provenance.json'), target/'provenance.json')
    evidence = json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    assert verify_generated_attribution(tmp_path, evidence) == 'unchanged-generated-code; image-metadata-only'
    bad = dict(evidence, audited_image_metadata_sha256='0'*64)
    with pytest.raises(ValueError, match='beyond image metadata'):
        verify_generated_attribution(tmp_path, bad)
    record = json.loads((target/'provenance.json').read_text())
    record['files_sha256']['code/alias.go'] = '0'*64
    (target/'provenance.json').write_text(json.dumps(record, indent=2)+'\n')
    with pytest.raises(ValueError, match='beyond image metadata'):
        verify_generated_attribution(tmp_path, evidence)
