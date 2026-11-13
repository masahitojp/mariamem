from pathlib import Path
import hashlib,json,re,collections
E=Path(__file__).resolve().parent;W=E.parent/'worktree';D=W/'benchmarks/forkcost/caller-map-20261113';D.mkdir(parents=True,exist_ok=True)
P=W/'internal/generatedgo/provenance.json';prov=json.loads(P.read_text());assert prov['guest_sha256']=='5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20'
inputs={};snippets=[]
for p,line in [(0,675426),(7,47043),(4,253349),(5,1033883),(1,45102)]:
 rel=f'code/p{p}/p{p}_pure.go';f=W/'internal/generatedgo'/rel;assert hashlib.sha256(f.read_bytes()).hexdigest()==prov['files_sha256'][rel]
 lines=f.read_text().splitlines();inputs[rel]=prov['files_sha256'][rel]
 snippets+=['### '+rel+':'+str(line),'```go',*lines[line-15:line+6],'```','']
assert 'base.MemoryFill(m, v2934, int32(0), v2933)' in (W/'internal/generatedgo/code/p0/p0_pure.go').read_text().splitlines()[675425]
assert 'base.MemoryFill(m, v76, int32(0), v27)' in (W/'internal/generatedgo/code/p7/p7_pure.go').read_text().splitlines()[47042]
(D/'generated-snippets.md').write_text('\n'.join(snippets));(D/'source-identity.json').write_bytes((E/'source-identity.json').read_bytes())
(D/'generated-hashes.json').write_text(json.dumps(inputs,indent=2)+'\n')
for n in ['sites.py','sites.json','fetch.py','strings.py','source-files.json']:(D/n).write_bytes((E/n).read_bytes())
(D/'buffer-alignment.patch.txt').write_bytes((W/'guest/patches/12.3.3-buffer-alignment.patch').read_bytes())
for n in ['strings-18569.json','strings-961.json','strings-5424.json','strings-4800.json']:(D/n).write_bytes((E/n).read_bytes())
summary={}
for p,d in json.loads((E/'sites.json').read_text()).items():
 c=collections.Counter()
 for r in d['memclr_sites']:
  st=r['stack']
  if 'p0.Fn18569 ' in st and ':675426:' in st:k='buffer_pool_allocation'
  elif 'p7.Fn981 ' in st and 'p4.Fn4245 ' in st:k='keycache_management_allocation'
  elif 'p7.Fn981 ' in st:k='other_my_malloc_callers'
  elif 'p5.Fn18284 ' in st:k='other_innodb_fill'
  elif 'p1.Fn961 ' in st:k='charset_initialization'
  else:k='other_memclr_paths'
  c[k]+=r['cpu_ns']
 summary[p]={'total_cpu_ns':d['total_cpu_ns'],'sites_cpu_ns':dict(c)}
(D/'classified.json').write_text(json.dumps(summary,indent=2)+'\n');(E/'classified.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
