from pathlib import Path
import hashlib,json,os,subprocess,sys,time
w=Path(__file__).resolve().parents[1];s=w/'worktree';t=w/'temp';e=w/'evidence'
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit
from build_generated_guest import download
from experiment_disk import DiskGuard,run_guarded
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,sha)
assert sha == '1057adf8fb430f5540f9d4f420f6b3f6f2012aa9'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True).strip()
env=dict(os.environ);go=Path(subprocess.check_output(['go','env','GOROOT'],env=dict(os.environ,GOTOOLCHAIN='go1.26.10'),text=True).strip())/'bin'
env.update(PATH=str(go)+os.pathsep+env['PATH'],GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMAXPROCS='4',GOMEMLIMIT='3GiB',CGO_ENABLED='0')
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
identity={'source_commit':sha,'go':subprocess.check_output(['go','version'],env=env,text=True).strip(),'steps':[]}
assert identity['go']=='go version go1.26.10 darwin/arm64'
(e/'verification.json').write_text(json.dumps(identity,indent=2)+'\n')
guard=DiskGuard(w,12,8)
def run(name,args,timeout=1200):
 start=time.monotonic()
 with (e/(name+'.txt')).open('w') as out:rc=run_guarded([str(x) for x in args],guard,cwd=s,env=env,output=out,timeout=timeout)
 identity['steps'].append({'name':name,'exit_code':rc,'seconds':time.monotonic()-start});(e/'verification.json').write_text(json.dumps(identity,indent=2)+'\n');print(name,rc,flush=True);assert rc==0,name
converter=download(json.loads((s/'release/generated-go-toolchain.json').read_text())['archives']['converter'],t/'downloads')
py=t/'venv/bin/python';spike=s/'benchmarks/spikes/generated-go-integration';guest=t/'guest/mariamem.wasm';guestsha=hashlib.sha256(guest.read_bytes()).hexdigest()
run('translate',[py,spike/'translate_guest.py','--guest',guest,'--guest-sha256',guestsha,'--converter-archive',converter,'--output',t/'translation'])
run('memory32',[py,s/'benchmarks/spikes/memory-candidate/check_fixture.py','--converter',t/'translation/wasm2go','--output',t/'memory32'])
run('candidate',[py,spike/'setup_candidate.py','--source-only','--source-module',t/'translation/module','--guest',guest,'--input-manifest',s/'release/generated-go-translation.json','--output',t/'candidate'])
run('install',[py,s/'scripts/generate_runtime.py','--source-module',t/'candidate/module','--output',t/'generatedgo'])
def inventory(p):return {x.relative_to(p).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in p.rglob('*') if x.is_file()}
a=inventory(t/'generatedgo');b=inventory(s/'internal/generatedgo');assert a==b,sorted(k for k in a.keys()|b.keys() if a.get(k)!=b.get(k))
(e/'regeneration.json').write_text(json.dumps({'result':'PASS','source_commit':sha,'guest_sha256':guestsha,'files':a},indent=2)+'\n');print('independent regeneration PASS',flush=True)
run('crc-units',['go','test','-p','1','-count=1','-v','-run','TestCRC32C','./internal/generatedgo/code/p4'])
run('lifecycle',['go','test','-p','1','-count=1','-v','-tags=integration','-timeout=5m','-run','TestDefaultNoBundleAndForkIsolation|TestDefaultRepeatedConcurrentLifecycle|TestInProcessConnectionLifecycle|TestInProcessCapacityAndClose','./tests/godefault'])
print('PASS local focused verification',flush=True)
