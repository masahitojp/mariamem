from pathlib import Path
import subprocess,json,hashlib,os,re,shutil,tarfile,time
W=Path(__file__).resolve().parents[1];S=W/'worktree';E=W/'evidence';T=W/'temp';O=T/'overlay';O.mkdir()
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
source='500020e7dc6d702ef059f0e73a4bab738103b774';identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=S));assert identity['source_commit']==source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
proof=json.loads((E/'rebind-proof.json').read_text());assert all(x['verified_helper_body_normalized_equal'] for x in proof['functions'])
mapping={};records=[]
def patch(path,edit):
 p=S/path;s=p.read_text();out=edit(s);assert out!=s;dst=O/path.replace('/','_');dst.write_text(out);subprocess.run(['gofmt','-w',str(dst)],check=True);mapping[str(p)]=str(dst);records.append({'path':path,'original_sha256':sha(p.read_bytes()),'overlay_sha256':sha(dst.read_bytes())})
def replace(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
patch('internal/generatedgo/code/base/base.go',lambda s:replace(s,'type Module struct {','type Module struct {\n UCAStart func(int32) func()\n UCAPhase func(string)'))
patch('internal/generatedgo/runtime_instance.go',lambda s:replace(s,'\t\tdefer releaseMemoryModule(m, release, &err)','\t\tdefer releaseMemoryModule(m, release, &err)\n attachUCAProbe(m, restore!=nil)'))
anchors=[('pages','L13:\n\t;'),('contractions','L122:\n\t;'),('hash_allocate','L361:\n\t;'),('hash_zero','\tbase.MemoryFill(m, v2281, v2286, int32(245760))'),('remaining','L359:\n\t;')]
def inject(s):
 for n in [465,468]:
  m=re.search(r'^func Fn'+str(n)+r'\([^\n]+\{\n',s,re.M);assert m;end=s.index('\n}',m.end())+2;b=s[m.start():end];expected=next(x['current_body_sha256'] for x in proof['functions'] if x['function']==n);assert sha(b.encode())==expected
  original=b
  if n==465:
   add='if m.UCAStart!=nil {defer m.UCAStart(l0)()}\n';b=b.replace('{\n','{\n'+add,1)
  else:
   add='if m.UCAPhase!=nil {m.UCAPhase("setup");defer m.UCAPhase("")}\n';b=b.replace('{\n','{\n'+add,1)
   for phase,anchor in anchors:
    mark='if m.UCAPhase!=nil {m.UCAPhase("'+phase+'")}';assert b.count(anchor)==1
    if anchor.startswith('L'):b=b.replace(anchor,anchor+'\n'+mark,1)
    else:
     b=b.replace(anchor,mark+'\n'+anchor+'\nif m.UCAPhase!=nil {m.UCAPhase("hash_populate")}',1)
   records.append({'function':n,'anchors':anchors,'unit':'elapsed ns, phase intervals; remaining includes booster and following level validation'})
  # Removing only injected observer statements recovers the original instructions.
  recovered=re.sub(r'^if m\.UCA(?:Start|Phase)!=nil \{[^\n]+\}\n','',b,flags=re.M);assert recovered==original
  s=s[:m.start()]+b+s[end:]
 return s
patch('internal/generatedgo/code/p2/p2_pure.go',inject)
p=O/'uca_probe.go';shutil.copy2(E/'probe.go',p);subprocess.run(['gofmt','-w',str(p)],check=True);mapping[str(S/'internal/generatedgo/uca_probe.go')]=str(p)
dump(O/'overlay.json',{'Replace':mapping});dump(E/'overlay-proof.json',{'source':identity,'files':records,'probe_sha256':sha(p.read_bytes()),'original_instruction_recovery':'PASS','limitations':'elapsed diagnostic intervals; logging happens after recorded UCA interval but affects later scheduling; no observer-off performance claim'})
harness='d24087eedd21c6384c231fb119c8e98da7b370aa'
archive=T/'harness.tar'
with archive.open('wb') as f:subprocess.run(['git','archive',harness,'tests/timer_calibration/runner'],cwd=S,stdout=f,check=True)
with tarfile.open(archive) as tf:tf.extractall(T,filter='data')
archive.unlink();H=T/'tests/timer_calibration/runner';mod=H/'go.mod';mod.write_text(mod.read_text().replace('=> ../../..','=> '+str(S)))
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','GIT_','FORK_STAGE','MODELCASE','UCA_'))};env.update(GOTOOLCHAIN='go1.26.10',GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='2',GOWORK='off',GOENV='off')
binary=T/'probe.test'
with (T/'build.log').open('w') as f:r=subprocess.run(['go','test','-mod=readonly','-p','1','-trimpath','-buildvcs=false','-overlay',str(O/'overlay.json'),'-c','-o',str(binary),'./maria/store'],cwd=H,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
if r.returncode:print((T/'build.log').read_text()[-4500:]);raise SystemExit(r.returncode)
dump(E/'binary.json',{'source_commit':source,'harness_commit':harness,'binary_sha256':sha(binary.read_bytes()),'go':'1.26.10','route':'Pipe','parallel':4,'fork_cap':5})
print('diagnostic build PASS',flush=True)
for i in range(2):
 scratch=T/f'scratch-{i}';scratch.mkdir();out=T/f'shop-{i}.json';probe=E/f'uca-{i}.jsonl'
 local=dict(env,GOMAXPROCS='8',GOGC='100',TMPDIR=str(scratch),SHOP_PARALLEL='4',ISSUE88_POOL_MIB='16',FORK_STAGES='0',MODELCASE_TRACE=str(out),UCA_SUBPHASE_PATH=str(probe))
 with (T/f'run-{i}.log').open('w') as f:r=subprocess.run([str(binary),'-test.parallel=4','-test.timeout=140s','-test.count=1'],cwd=H,env=local,stdout=f,stderr=subprocess.STDOUT,timeout=150)
 if r.returncode:print((T/f'run-{i}.log').read_text()[-4500:]);raise SystemExit(r.returncode)
 x=json.loads(out.read_text());assert not list(scratch.iterdir());m=x['meta']
 for k,v in {'active_mappings_after':'0','read_cases':'50','write_cases':'20','test_exit':'0','fork_cap':'5','innodb_read_io_threads':'1','innodb_buffer_pool_size':'16777216'}.items():assert m[k]==v,(k,m)
 rows=[json.loads(l) for l in probe.read_text().splitlines()];assert len(rows)==110
 assert len({v['instance'] for v in rows})==22
 for row in rows:
  for phase in ['pages','contractions','hash_allocate','hash_zero','hash_populate','remaining']:assert row['phases'][phase][0]==3,(phase,row)
  assert sum(v[1] for v in row['phases'].values())<=row['total_ns']
 dump(E/f'run-{i}.json',{'result':'PASS_DIAGNOSTIC','sql_cases':70,'forks':21,'fresh':1,'uca_records':len(rows),'phase_count_oracle':'3 occurrences per selected phase per collation','active_mappings_after':0,'scratch_empty':True,'binary_sha256':sha(binary.read_bytes())})
 print('P4 observation',i,'PASS',flush=True)
