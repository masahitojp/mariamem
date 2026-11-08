import os,pathlib,subprocess,json,hashlib,platform,time,re,sys
w=pathlib.Path(sys.argv[1]).resolve();s=w/'worktree';t=w/'temp';e=w/'evidence';b=s/'benchmarks/issue88modelcase';env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_'))};env.update(CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),ISSUE88_POOL_MIB='16',ISSUE88_SAMPLE_PHASES='1',ISSUE68_CAPTURE='1')
def run(args,cwd=s,timeout=600):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
 if r.returncode:(e/'failure.txt').write_text(repr(args)+'\n'+r.stdout+r.stderr);r.check_returncode()
 return r
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout);assert not run(['git','status','--porcelain']).stdout;assert not run(['git','diff','a3b2b645','--','internal','guest','release','go.mod','go.sum']).stdout
inputs={'source':identity,'plan':json.loads((s/'benchmarks/issue68prepare/plan.json').read_text()),'host':{'platform':platform.platform(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()}};(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
run(['python3','benchmarks/issue88poolab/overlay.py',str(s),str(t/'overlay')]);inputs['overlay']=json.loads((t/'overlay/hashes.json').read_text());print('BUILD bounded capture',flush=True);start=time.monotonic();r=run(['go','test','-c','-trimpath','-mod=readonly','-overlay',str(t/'overlay/overlay.json'),'-o',str(t/'probe'),'./maria/store'],cwd=b,timeout=650);(e/'build.txt').write_text(r.stdout+r.stderr)
inputs.update(binary_sha256=hashlib.sha256((t/'probe').read_bytes()).hexdigest(),build_info=run(['go','version','-m',str(t/'probe')]).stdout.replace(str(w),'<WORKSPACE>'),build_seconds=time.monotonic()-start);(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
def matching_blocks(profile,dbid):
 blocks=[]
 for block in profile.split('\n\n'):
  lines=block.splitlines();labels=next((json.loads(line[len('# labels: '):]) for line in lines if line.startswith('# labels: ')),{})
  if labels.get('db_id')==dbid:blocks.append(block)
 return blocks
obs=[]
for i,arm in enumerate([16,16,8,8,16]):
 control=i==0;name='positive-control' if control else f'natural-{i-1}-pool{arm}';capdir=e/name;capdir.mkdir();env.update(ISSUE88_POOL_MIB=str(arm),ISSUE68_CONTROL='1' if control else '0',ISSUE68_CAPTURE_DIR=str(capdir),MODELCASE_TRACE=str(e/(name+'-trace.json')),SAMPLE_PHASES_OUT=str(e/(name+'-sql.json')))
 print(name,flush=True);r=run([str(t/'probe'),'-test.parallel=8','-test.timeout=120s','-test.count=1'],cwd=b,timeout=130);(e/(name+'.txt')).write_text(r.stdout+r.stderr);trace=json.loads((e/(name+'-trace.json')).read_text());loaders=json.loads((e/(name+'-sql.json')).read_text());assert trace['meta']['read_cases']=='50' and trace['meta']['write_cases']=='20' and trace['meta']['active_mappings_after']=='0';assert len(loaders)==21
 caps=[]
 for path in capdir.glob('capture-*.json'):
  m=json.loads(path.read_text());text=(capdir/m['profile_file']).read_text();assert len(text.encode())==m['bytes'];blocks=matching_blocks(text,m['db_id']);inside=m['call_enter_us']<=m['snapshot_begin_us']<=m['snapshot_end_us']<=m['call_return_us'];guest=[v for v in blocks if re.search(r'/internal/generatedgo/code/p\d+\.Fn\d+',v)]
  m.update(snapshot_inside_caller=inside,matching_db_blocks=len(blocks),matching_guest_blocks=len(guest),profile_sha256=hashlib.sha256(text.encode()).hexdigest(),usable=inside and not m['truncated'] and bool(guest) and not m.get('error'));m['matching_blocks']=blocks;caps.append(m)
 assert len(caps)<=1
 if control:assert len(caps)==1 and caps[0]['usable'] and caps[0]['phase']=='positive_control'
 obs.append({'name':name,'control':control,'pool_mib':arm,'trace':trace,'loaders':loaders,'captures':caps});(e/'observations.json').write_text(json.dumps(obs,separators=(',',':'))+'\n');print('PASS usable capture',sum(c['usable'] for c in caps),flush=True)
print('FINITE CONTROL +4 NATURAL SUITES COMPLETE',flush=True)
