"""Bind counter probes to the checked map and actual generated Go definitions."""
from pathlib import Path
import gzip
import json
import re
import sys

source,harness,table,out=map(lambda s:Path(s).resolve(),sys.argv[1:])
out.mkdir(exist_ok=True)
base=source/'internal/generatedgo/code/base/base.go'
names={int(i):n for i,n in (s.split(':',1) for s in gzip.decompress(table.read_bytes()).decode().splitlines())}
replace={}; selected={}; hits={}
def put(original,text):
    dest=out/(str(original.relative_to(source) if original.is_relative_to(source) else original.name).replace('/','_'))
    dest.write_text(text); replace[str(original)]=str(dest)
def change(s,before,after):
    if s.count(before)!=1: raise ValueError(before)
    return s.replace(before,after)
def select(label,match,code):
    entries=[(i,n) for i,n in names.items() if re.search(match,n)]
    if len(entries)!=1: raise ValueError((label,entries))
    i,n=entries[0]
    selected[i]=code; hits[label]=dict(index=i,symbol=n)
select('target',r'emb_stmt_execute','defer base.ProbeSQL(m)()')
select('trigger',r'process_triggers','defer base.ProbeTrigger(m)()')
select('dlmalloc',r'^dlmalloc$','base.ProbeAdd(m,"dlmalloc",1); base.ProbeAdd(m,"dlmalloc_requested_bytes",int64(uint32(l0)))')
select('dlfree',r'^dlfree$','base.ProbeAdd(m,"dlfree",1)')
# The public allocation wrappers and the dlmalloc implementation are separate layers.
# Successful request sizes exclude allocator headers and internal rounding.
success={}
for name,size,ok in [('dlmalloc','int64(uint32(l0))','result!=0'),('__wrap_malloc','int64(uint32(l0))','result!=0'),
                     ('__wrap_calloc','int64(uint32(l0))*int64(uint32(l1))','result!=0'),
                     ('__wrap_realloc','int64(uint32(l1))','result!=0'),('__wrap_posix_memalign','int64(uint32(l2))','result==0')]:
    if name!='dlmalloc':
        select(name,'^'+name+'$','base.ProbeAdd(m,"'+name+'",1)')
    i=hits[name]['index']
    selected[i]+='; defer func(){if '+ok+' {base.ProbeAdd(m,"'+name+'_success_bytes",'+size+')}}()'
    success[i]=name
select('__wrap_free',r'^__wrap_free$','base.ProbeAdd(m,"__wrap_free",1)')
for key,pattern in [('JOIN.optimize',r'^_ZN4JOIN8optimizeEv$'),
                    ('Prepared_statement.reprepare',r'^_ZN18Prepared_statement9reprepareEv$'),
                    ('sp.validate',r'^_ZN13sp_lex_keeper26validate_lex_and_exec_core'),
                    ('handler.ha_index_read_map',r'^_ZN7handler17ha_index_read_map'),
                    ('ha_innobase.index_read',r'^_ZN11ha_innobase10index_read'),
                    ('row_search_mvcc',r'^_Z15row_search_mvcc')]:
    select(key,pattern,'base.ProbeAdd(m,"'+key+'",1)')
text=base.read_text()
module=re.search(r'^type Module struct \{.*?^\}',text,re.M|re.S)[0]
text=change(text,module,module[:-1]+'\tProbeRecord *ProbeRequest\n}')
helpers=[]
for match in list(re.finditer(r'^func (Atomic\w+)\(m \*Module[^\n]*\{',text,re.M)):
    key=match[1]
    if key in ('AtomicWait','AtomicEA'): continue
    helpers.append(key)
    text=change(text,match[0],match[0]+'\n ProbeAdd(m,"helper.'+key+'",1)')
text=change(text,'*child = *m','*child = *m\n child.ProbeRecord=nil')
for method,code in [('AtomicEA','ProbeAdd(m,"AtomicEA",1)'),('MemoryEA','ProbeAdd(m,"MemoryEA",1)'),
                    ('MemoryGrow','ProbeAdd(m,"memory.grow",1); ProbeAdd(m,"memory.grow_requested_pages",int64(uint32(n)))')]:
    anchor=re.search(r'^func '+method+r'\(m \*Module,.*?\{',text,re.M)[0]
    text=change(text,anchor,anchor+'\n '+code)
anchor='func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {'
text=change(text,anchor,anchor.replace(') int32 {',') (result int32) {')+'\n start:=ProbeNow(); var parkBegin,parkEnd int64; defer func(){ProbeWaitEnd(m,start,parkBegin,parkEnd,result)}()')
wait=re.search(r'^func AtomicWait\(.*?^\}',text,re.M|re.S)[0]
parks=wait.replace('select {','parkBegin=ProbeNow()\n select {')
parks,n=re.subn(r'(case <-[^\n]+:)',r'\1\n parkEnd=ProbeNow()',parks)
assert n==5 and parks.count('parkBegin=ProbeNow()')==2
text=change(text,wait,parks)
put(base,text)
observer=Path(__file__).with_name('observer.go.txt').read_text()
wasis=[]
for ns,body in re.findall(r'type (Wasi_snapshot_preview1|Wasix_32v1)Imports interface \{([^}]+)\}',text):
    for method,args,ret in re.findall(r'\s+(\w+)\(([^)]*)\)( int32)?\n?',body):
        key=ns+'.'+method
        wrapper='Probe'+ns+method
        argv=','.join(arg.strip().split()[0] for arg in args.split(','))
        observer+=f'\nfunc {wrapper}({args}){ret} {{ defer ProbeWASI(m,"{key}")(); '
        observer+=('return ' if ret else '')+f'm.{key}({argv}) }}\n'
        wasis.append((key,wrapper))
atomic_ops=[]
for op in ('Load','Store'):
    for bits in ('32','64'):
        name=op+'Uint'+bits; typ='uint'+bits
        args='p *'+typ+(', v '+typ if op=='Store' else '')
        ret=' '+typ if op=='Load' else ''
        operation='return atomic.'+name+'(p)' if op=='Load' else 'atomic.'+name+'(p,v)'
        observer+=f'\nfunc Probe{name}(m *Module,{args}){ret} {{ ProbeAdd(m,"inline.{name}",1); {operation} }}\n'
        atomic_ops.append(name)
put(base.with_name('probe_233.go'),observer)
parser,=[i for i,n in names.items() if n.startswith('_Z9parse_sqlP3THD')]
validate=hits['sp.validate']['index']
seen=set(); dispatch=0; wasi_sites={}; parser_sites=[]
for path in sorted(base.parents[1].glob('p*/*.go')):
    if path.name.endswith('_test.go') or path.name=='alias.go': continue
    old=s=path.read_text()
    for m in list(re.finditer(r'^func Fn(\d+)\(m \*base\.Module[^\n]*\{',s,re.M)):
        i=int(m[1])
        if i not in selected: continue
        head=m[0]
        if i in success:
            assert head.endswith(') int32 {')
            head=head[:-len('int32 {')]+'(result int32) {'
        s=change(s,m[0],head+'\n '+selected[i]); seen.add(i)
    body=re.search(r'^func Fn'+str(validate)+r'\([^\n]+\{.*?^}',s,re.M|re.S)
    if body:
        # MariaDB sql/sp_instr.cc lines 575 and 1097-1099 in the pinned source.
        # The inlined parse_expr path invokes parse_sql once per actual reparse.
        call,=[line for line in body[0].splitlines() if 'Fn'+str(parser)+'(m,' in line]
        parser_sites.append(dict(caller=validate,callee=parser,statement=call.strip()))
        s=change(s,body[0],change(body[0],call,'\tbase.ProbeAdd(m,"sp.reparse_at_parse_sql",1)\n'+call))
    for key,wrapper in wasis:
        call='m.'+key+'(m'
        if call in s:
            wasi_sites[key]=wasi_sites.get(key,0)+s.count(call); s=s.replace(call,'base.'+wrapper+'(m')
    for op in atomic_ops:
        s=s.replace('atomic.'+op+'(','base.Probe'+op+'(m, ')
    if '"sync/atomic"' in s and 'atomic.' not in s:
        s=s.replace('"sync/atomic"','')
    pattern=r'(?m)^(\s*[^\n]*m\.T0\[[^\n]+\]\.\(func\([^\n]+)$'
    # Every dynamic dispatch is a standalone expression/assignment in generated source.
    s,n=re.subn(pattern,lambda m:'\tbase.ProbeAdd(m,"call_indirect",1)\n'+m[1],s); dispatch+=n
    assert n==s.count('].(func('),(path,n,s.count('].(func('))
    if s!=old: put(path,s)
assert seen==set(selected) and dispatch>0 and wasi_sites and len(parser_sites)==1
# Internal instrumentation bridge is overlay-only. The CPU build uses the untouched checkout.
put(source/'probe_233.go','''package mariamem
import "github.com/masahitojp/mariamem/internal/generatedgo/code/base"
func ProbeClient(db,i int){base.ProbeClient(db,i)}
func ProbeReply(){base.ProbeReply()}
func ProbeSave(path string){base.ProbeSave(path)}
''')
main=(harness/'main.go').read_text()
main=change(main,'start := time.Now()','ordinal := 0\n start := time.Now()')
main=change(main,'_, err = st.Exec','maria.ProbeClient(n,ordinal); ordinal++\n _, err = st.Exec')
main=change(main,'it.UnitPriceCents)\n\t\t\tmust(err)','it.UnitPriceCents)\n maria.ProbeReply()\n\t\t\tmust(err)')
main=change(main,'flag.Parse()','flag.Parse(); defer maria.ProbeSave(os.Getenv("COUNTER_OUTPUT"))')
put(harness/'main.go',main)
(out/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2))
(out/'bindings.json').write_text(json.dumps(dict(functions=hits,indirect_sites=dispatch,wasi_sites=wasi_sites,sp_reparse_sites=parser_sites,atomic_helpers=helpers,atomic_inline=atomic_ops),indent=2)+'\n')
