"""Rebase the unchanged J1 failure oracle onto this exact experimental guest.

Only fixture image/absolute addresses change. Function bodies come from the
bound generated product. Never write generated product sources.
"""
import argparse,hashlib,json,re,runpy,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import runtime_thread_lifetime as binding


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def body(p,n):return binding.function(p.read_text(),n)
def normalized(text):return re.sub(r'\s+','',text)
def data_file(path):
    m=re.search(r'var wasm2goData_data_bin = \[\]byte\("((?:\\x[0-9a-f]{2})+)"\)',path.read_text())
    assert m,'embedded data literal missing'
    return bytes.fromhex(m[1].replace('\\x',''))


def main():
    p=argparse.ArgumentParser();p.add_argument('--product',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    product=a.product.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    runtime=product/'internal/generatedgo';prov=json.loads((runtime/'provenance.json').read_text())
    assert prov['guest_sha256']==binding.PREPARED_SPIKE_GUEST
    graph=json.loads((ROOT/'docs/reviews/v050-access-paths-evidence/direct-call-graph.json').read_text())
    seen=set();todo=[217,221,152]
    while todo:
        n=todo.pop()
        if n in seen:continue
        seen.add(n);todo.extend(graph[str(n)]['direct_callees'])
    assert seen=={70,82,83,88,89,97,131,135,150,151,152,153,158,217,221}
    assert all(not graph[str(n)]['indirect_calls'] for n in seen)
    module=out/'module';module.mkdir();(module/'go.mod').write_text('module github.com/masahitojp/mariamem\n\ngo 1.26.0\n')
    copied={}
    for relative in ['internal/generatedgo/code/base','internal/prepared','internal/timing']:
        target=module/relative;target.mkdir(parents=True)
        for f in (product/relative).iterdir():
            if f.suffix in ['.go','.s'] and not f.name.endswith('_test.go'):
                shutil.copyfile(f,target/f.name);copied[str(f.relative_to(product))]=sha(f)
    probe=module/'probe';probe.mkdir();defs=[];identities={}
    literal=re.compile(r'(?<![A-Za-z_0-9])\d+\b')
    for n in sorted(seen):
        info=graph[str(n)];rel=info['file'].removeprefix('internal/generatedgo/')
        source=runtime/rel;assert sha(source)==prov['files_sha256'][rel]
        old=body(ROOT/info['file'],'Fn'+str(n));new=body(source,'Fn'+str(n))
        # Default canonical and candidate both retain the completion handoff.
        x,y=normalized(old),normalized(new)
        assert literal.sub('#',x)==literal.sub('#',y),f'function structure changed: {n}'
        changes=sorted(set((int(i),int(j)) for i,j in zip(literal.findall(x),literal.findall(y)) if i!=j))
        for i,j in changes:
            assert (15239105<=i<=15301648 and j-i==46528) or (i,j)==(8687180,8687786),(n,i,j)
        assert not re.search(r'\bm\.T\d+\[',new),'unexpected indirect call'
        identities[str(n)]=dict(source_sha256=sha(source),body_sha256=hashlib.sha256(new.encode()).hexdigest(),integer_literal_relocations=changes,non_literal_structure_equal=True)
        defs.append(new)
    headers='package probe\nimport("unsafe";"github.com/masahitojp/mariamem/internal/generatedgo/code/base"'+(';"sync/atomic"' if any('atomic.' in d for d in defs) else '')+')\n'
    (probe/'functions.go').write_text(headers+'\n'.join(defs))
    host_method=runpy.run_path(str(ROOT/'benchmarks/spikes/v050-semantic-audit/package.py'))['host_method']
    original=(runtime/'main.go').read_text();methods=[host_method(original,n) for n in ['Futex_wait','futexWake','Futex_wake','Futex_wake_all']]
    anchor='base.AtomicNotify(m, addr, 0, count)';assert methods[1].count(anchor)==1
    methods[1]=methods[1].replace(anchor,anchor+'\n if h.hook!=nil {h.hook(m,out)}')
    interface=(runtime/'code/base/base.go').read_text().split('type Wasix_32v1Imports interface {',1)[1].split('\n}',1)[0];unused=[]
    for line in interface.splitlines():
        if line.strip() and not line.strip().startswith(('Futex_wait(','Futex_wake(','Futex_wake_all(')):
            unused.append('func(h *host) '+line.strip().replace('*Module','*base.Module')+'{panic("unexpected import in bounded join fixture")}')
    (probe/'host.go').write_text('package probe\nimport("encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")\ntype host struct{*base.WasiStubs;hook func(*base.Module,int32)}\n'+'\n'.join(methods+unused))
    data=data_file(runtime/'code/generated.go');old_data=data_file(ROOT/'internal/generatedgo/code/generated.go')
    def cstring(b,addr):
        pos=addr-8388608;return b[pos:b.index(b'\0',pos)]
    assert cstring(data,8687786)==cstring(old_data,8687180)
    (probe/'data.bin').write_bytes(data)
    generated=(runtime/'code/generated.go').read_text()
    assert 'wasm2goData_data_bin[0:6208038], wasm2goData_data_bin[6208038:6850658], wasm2goData_data_bin[6850658:6896979]' in generated
    init=body(runtime/'code/p7/p7_pure.go','Fn67')
    for fragment in ['base.MemoryInit(m, 0, int32(8388608), v7, int32(6208038))','base.MemoryInit(m, 1, int32(14596672), v7, int32(642620))','v14 = int32(15239296)','base.MemoryInit(m, 2, v14, v7, int32(46321))']:
        assert fragment in init,fragment
    template=ROOT/'benchmarks/spikes/v050-join-lifetime/probe_test.go.txt';test=template.read_text()
    replacements={
        'copy(memory[8388608:], data[:6207334])':'copy(memory[8388608:], data[:6208038])',
        'copy(memory[14595968:], data[6207334:6849954])':'copy(memory[14596672:], data[6208038:6850658])',
        'copy(memory[15238592:], data[6849954:])':'copy(memory[15239296:], data[6850658:])',
        'put(15243132, 123)':'put(15289660, 123)',
        'put(15244240, 0)':'put(15290768, 0)',
        'put(15244244, tc.waiters)':'put(15290772, tc.waiters)',
    }
    for old,new in replacements.items():assert test.count(old)==1;test=test.replace(old,new)
    (probe/'probe_test.go').write_text(test)
    (out/'identities.json').write_text(json.dumps(dict(guest_sha256=prov['guest_sha256'],provenance_sha256=sha(runtime/'provenance.json'),functions=identities,copied_source_sha256=copied,canonical_oracle_sha256=sha(template),rebased_oracle_sha256=sha(probe/'probe_test.go'),only_oracle_changes=replacements,observer='same single wake pause; canonical assertions unchanged',data_sha256=sha(probe/'data.bin')),indent=2)+'\n')
    print(module)
if __name__=='__main__':main()
