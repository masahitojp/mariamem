"""Normal notices are explicit; legacy attribution and guest sources survive."""
import json
from pathlib import Path
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from distribution_licenses import inventory, paths, source_inputs, verify_generated_attribution


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
    assert verify_generated_attribution(ROOT, evidence) in ('exact', 'os-glue-continuity')
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


@pytest.mark.parametrize('change', ['adapter', 'body', 'unlisted', 'provenance'])
def test_os_glue_continuity_rejects_unreviewed_changes(tmp_path, change):
    import hashlib
    evidence = json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    original = json.loads((ROOT/'internal/generatedgo/provenance.json').read_text())
    names = evidence['os_glue_source_continuity']['previous_file_sha256']
    generated = tmp_path/'internal/generatedgo'
    for name in names:
        target = generated/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/'internal/generatedgo'/name, target)
    # Small synthetic unrelated engine file avoids copying the large SQL corpus.
    (generated/'engine.go').write_text('package engine\n')
    original['files_sha256'] = {name: original['files_sha256'][name] for name in names}
    original['files_sha256']['engine.go'] = hashlib.sha256((generated/'engine.go').read_bytes()).hexdigest()
    historical = json.loads(json.dumps(original))
    historical['files_sha256'].update(names)
    evidence['generated_provenance_sha256'] = hashlib.sha256((json.dumps(historical,indent=2)+'\n').encode()).hexdigest()
    provenance = generated/'provenance.json'
    provenance.write_text(json.dumps(original,indent=2)+'\n')
    assert verify_generated_attribution(tmp_path,evidence) == 'os-glue-continuity'
    if change in ('adapter', 'body'):
        target = generated/'main.go'
        text = target.read_text()
        text = text.replace('entropyfs.Open(', 'os.Open(', 1) if change=='adapter' else text+'\n// unexpected body change\n'
        target.write_text(text)
        original['files_sha256']['main.go'] = hashlib.sha256(target.read_bytes()).hexdigest()
    elif change=='unlisted':
        target = generated/'engine.go'
        target.write_text('package changed\n')
        original['files_sha256']['engine.go'] = hashlib.sha256(target.read_bytes()).hexdigest()
    else:
        original['guest_sha256'] = '0'*64
    provenance.write_text(json.dumps(original,indent=2)+'\n')
    with pytest.raises(ValueError):
        verify_generated_attribution(tmp_path,evidence)
