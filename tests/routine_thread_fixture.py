"""Package actual canonical J1 functions; retain the historical failure assertions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import os
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import runtime_thread_lifetime as binding

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def normalized(text):return re.sub(r'\s+','',text)
def data_file(path):
    match=re.search(r'var wasm2goData_data_bin = \[\]byte\("((?:\\x[0-9a-f]{2})+)"\)',path.read_text())
    assert match,'canonical data literal missing'
    return bytes.fromhex(match[1].replace('\\x',''))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--run',action='store_true')
    a=parser.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    runtime=ROOT/'internal/generatedgo';provenance=json.loads((runtime/'provenance.json').read_text())
    layout=json.loads((ROOT/'tests/fixtures/routine-thread-layout.json').read_text())
    assert provenance['guest_sha256']==layout['guest_sha256']==binding.GUEST_SHA256
    baseline=json.loads((ROOT/'tests/fixtures/routine-j1-baseline.json').read_text())
    mapping={int(k):int(v) for k,v in layout['function_map'].items()}
    entries={row['old_function']:row for row in layout['functions']}
    closure={70,82,83,88,89,97,131,135,150,151,152,153,158,217,221}
    module=out/'module';module.mkdir();(module/'go.mod').write_text('module github.com/masahitojp/mariamem\n\ngo 1.26.0\n')
    copied={}
    for relative in ('internal/generatedgo/code/base','internal/prepared','internal/timing'):
        target=module/relative;target.mkdir(parents=True)
        for source in (ROOT/relative).iterdir():
            if source.suffix in ('.go','.s') and not source.name.endswith('_test.go'):
                shutil.copy2(source,target/source.name);copied[str(source.relative_to(ROOT))]=sha(source)
    definitions=[];identities={};literal=re.compile(r'(?<![A-Za-z_0-9])\d+\b')
    for old in sorted(closure):
        info=entries[old];relative='code/'+info['file'];source=runtime/relative
        assert sha(source)==provenance['files_sha256'][relative]
        body=binding.function(source.read_text(),'Fn'+str(mapping[old]))
        raw=body
        if old==153:
            hook='\tif base.DeferThreadAllocationFree(m, l0) {\n\t\treturn\n\t}\n'
            assert raw.count(hook)==1;raw=raw.replace(hook,'',1)
        assert hashlib.sha256(normalized(raw).encode()).hexdigest()==info['normalized_sha256']
        expected=re.sub(r'\bFn(\d+)\b',lambda m:'Fn'+str(mapping.get(int(m[1]),int(m[1]))),baseline['functions'][str(old)]['body'])
        assert literal.sub('#',normalized(expected))==literal.sub('#',normalized(raw))
        changes=sorted(set((int(i),int(j)) for i,j in zip(literal.findall(normalized(expected)),literal.findall(normalized(raw))) if i!=j))
        assert changes==[tuple(pair) for pair in info['integer_changes']]
        assert not re.search(r'\bm\.T\d+\[',body)
        direct={int(x) for x in re.findall(r'\bFn(\d+)\(',body)}-{mapping[old]}
        assert direct <= {mapping[n] for n in closure}
        definitions.append(body);identities[str(old)]={'function':mapping[old],'raw_normalized_sha256':info['normalized_sha256'],'installed_body_sha256':hashlib.sha256(body.encode()).hexdigest(),'source_sha256':sha(source)}
    probe=module/'probe';probe.mkdir()
    imports='package probe\nimport("unsafe";"github.com/masahitojp/mariamem/internal/generatedgo/code/base"'+(';"sync/atomic"' if any('atomic.' in body for body in definitions) else '')+')\n'
    (probe/'functions.go').write_text(imports+'\n'.join(definitions))
    extract=runpy.run_path(str(ROOT/'benchmarks/spikes/v050-semantic-audit/package.py'))['host_method']
    source=(runtime/'main.go').read_text();methods=[extract(source,n) for n in ('Futex_wait','futexWake','Futex_wake','Futex_wake_all')]
    anchor='base.AtomicNotify(m, addr, 0, count)';assert methods[1].count(anchor)==1
    methods[1]=methods[1].replace(anchor,anchor+'\n if h.hook!=nil {h.hook(m,out)}')
    interface=(runtime/'code/base/base.go').read_text().split('type Wasix_32v1Imports interface {',1)[1].split('\n}',1)[0];unused=[]
    for line in interface.splitlines():
        if line.strip() and not line.strip().startswith(('Futex_wait(','Futex_wake(','Futex_wake_all(')):
            unused.append('func(h *host) '+line.strip().replace('*Module','*base.Module')+'{panic("unexpected import in bounded join fixture")}')
    (probe/'host.go').write_text('package probe\nimport("encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")\ntype host struct{*base.WasiStubs;hook func(*base.Module,int32)}\n'+'\n'.join(methods+unused))
    data=data_file(runtime/'code/generated.go');assert hashlib.sha256(data).hexdigest()==layout['data_sha256']
    (probe/'data.bin').write_bytes(data)
    init=binding.function((runtime/'code/p7/p7_pure.go').read_text(),'Fn67')
    segments=layout['data_segments'];first=segments[0]['end'];second=segments[1]['end'];third=segments[2]['end']
    for text in (f'base.MemoryInit(m, 0, int32(8388608), v7, int32({first}))',f'base.MemoryInit(m, 1, int32({segments[1]["offset"]}), v7, int32(642620))',f'v14 = int32({segments[2]["offset"]})',f'base.MemoryInit(m, 2, v14, v7, int32({third-second}))'):
        assert text in init,text
    template=ROOT/'benchmarks/spikes/v050-join-lifetime/probe_test.go.txt';test=template.read_text()
    replacements={
        'copy(memory[8388608:], data[:6207334])':f'copy(memory[8388608:], data[:{first}])',
        'copy(memory[14595968:], data[6207334:6849954])':f'copy(memory[{segments[1]["offset"]}:], data[{first}:{second}])',
        'copy(memory[15238592:], data[6849954:])':f'copy(memory[{segments[2]["offset"]}:], data[{second}:])',
        'put(15243132, 123)':f'put({15243132+layout["global_address_delta"]}, 123)',
        'put(15244240, 0)':f'put({15244240+layout["global_address_delta"]}, 0)',
        'put(15244244, tc.waiters)':f'put({15244244+layout["global_address_delta"]}, tc.waiters)',
        'Fn217(':'Fn215(', 'Fn221(':'Fn219(',
    }
    for before,after in replacements.items():
        assert test.count(before)==1,before;test=test.replace(before,after)
    (probe/'probe_test.go').write_text(test)
    (out/'identities.json').write_text(json.dumps({'guest_sha256':layout['guest_sha256'],'provenance_sha256':sha(runtime/'provenance.json'),'functions':identities,'copied_source_sha256':copied,'historical_oracle_sha256':sha(template),'rebased_oracle_sha256':sha(probe/'probe_test.go'),'only_oracle_changes':replacements,'observer':'same post-notify pause; assertions unchanged','data_sha256':layout['data_sha256']},indent=2)+'\n')
    if a.run:
        results=[]
        for backing in ('heap','mmap'):
            for protected,race in (('0',False),('1',False),('1',True)):
                name=backing+'-'+protected+('-race' if race else '')
                command=['go','test','-v','-count=1',*(['-race'] if race else []),'./probe']
                result=subprocess.run(command,cwd=module,env=dict(os.environ,JOIN_BACKING=backing,JOIN_PROTECTED=protected),capture_output=True,text=True,timeout=180)
                text=result.stdout+result.stderr;(out/(name+'.txt')).write_text(text)
                if protected=='0':
                    passed=(result.returncode==1 and 'replacement byte changed from 165 to 1 after join/free/reuse' in text and '--- FAIL: TestJoinAllocationLastAccess/early-free' in text and all('--- PASS: TestJoinAllocationLastAccess/'+control in text for control in ('completed-before-free','no-post-unlock-wake')))
                else:
                    passed=result.returncode==0 and all('--- PASS: TestJoinAllocationLastAccess/'+control in text for control in ('early-free','completed-before-free','no-post-unlock-wake','detached-self-free'))
                results.append(dict(name=name,exit_code=result.returncode,expected_failure=protected=='0',passed=passed))
                (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
                if not passed:raise RuntimeError('J1 oracle failed: '+name)
    print(module)

if __name__=='__main__':main()
