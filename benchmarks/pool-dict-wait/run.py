import os,pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2]; w=root.parent;tmp=w/'temp'; ev=w/'evidence'
tmp.mkdir(exist_ok=True);ev.mkdir(exist_ok=True)
identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=root))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root).strip()
(ev/'execution-input.json').write_text(json.dumps({'source':identity,'baseline':'8df45792a927e440972266ee799d6f7223713e14','guest_sha256':'332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22','go':'go1.26.10','case_budget':27,'build_attempt':'dictionary slow path prototype'},indent=2)+'\n')
env=os.environ.copy();env.update(GOTOOLCHAIN='go1.26.10',GOCACHE=str(tmp/'gocache'),PENDING_RESULTS=str(ev/'cases.json'))
subprocess.run(['python3','benchmarks/pool-dict-wait/make_overlay.py'],cwd=root,env=env,check=True)
cmd=['go','test','-overlay',str(tmp/'overlay/overlay.json'),'-tags=integration','-c','-o',str(tmp/'control.test'),'./internal/generatedgo']
start=time.monotonic()
with (ev/'build.txt').open('w') as log:
 result=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
print('build exit',result.returncode,'elapsed',round(time.monotonic()-start,1),flush=True)
if result.returncode: raise SystemExit(result.returncode)
with (ev/'test.txt').open('w') as log:
 result=subprocess.run([str(tmp/'control.test'),'-test.run=^TestDictWaitGuest$','-test.v','-test.timeout=120s'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=130)
print('test exit',result.returncode,flush=True)
print((ev/'test.txt').read_text()[-10000:],flush=True)
raise SystemExit(result.returncode)
