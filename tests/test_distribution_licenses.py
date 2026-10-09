"""Normal notices are explicit; legacy attribution and guest sources survive."""
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


def test_evidence_bound_to_unchanged_guest_and_generated_source():
    from common import digest
    value=inventory(ROOT)
    evidence=json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    pins=json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    assert evidence['guest_sha256']==pins['guest_sha256']
    assert evidence['generated_provenance_sha256']==digest(ROOT/'internal/generatedgo/provenance.json')
    continuity=evidence['snapshot_attribution_source_check']
    provenance=json.loads((ROOT/'internal/generatedgo/provenance.json').read_text())
    assert set(continuity['changed_files']) == {'main.go'}
    assert continuity['generated_provenance_sha256'] == evidence['generated_provenance_sha256']
    assert continuity['changed_files']['main.go']['after'] == provenance['files_sha256']['main.go']
    import hashlib
    unchanged={name:sha for name,sha in provenance['files_sha256'].items() if name!='main.go'}
    assert continuity['unchanged_generated_inventory_sha256'] == hashlib.sha256(
        json.dumps(unchanged,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for row in evidence['retained_symbols'].values():
        assert row['generated_definitions'] and any(x['host_symbol_retained'] for x in row['examples'])
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
