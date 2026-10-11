import os, sys, json, hashlib
from pathlib import Path
WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK/'worktree/scripts'))
from build_feedback import run
from dev_guest import inventory
old=WORK/'temp/dev-native/product'; new=WORK/'temp/dev-version-product'
a,b=inventory(old),inventory(new)
assert set(a)==set(b)
assert [n for n in a if a[n]!=b[n]]==['internal/mysqlwire/wire.go']
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOCACHE=str(WORK/'temp/gocache'),GOMODCACHE=str(WORK/'temp/modcache'),GOPATH=str(WORK/'temp/gopath'),GOTMPDIR=str(WORK/'temp/go-tmp'),TMPDIR=str(WORK/'temp/tmp'),GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2',MARIAMEM_PHASE_TRACE=str(WORK/'evidence/overlay-phases.jsonl'))
env.pop('MARIAMEM_DEV_WORKSPACE',None)
host=WORK/'temp/mariamem-stable-version-host'
run(['go','build','-p','1','-trimpath','-buildvcs=false','-o',str(host),'./cmd/mariamem-host'],cwd=new,env=env,check=True,phase='overlay:host-build')
assert inventory(new)==b
info=run([str(host),'--snapshot-info'],env=env,check=True,capture_output=True,text=True,phase='overlay:binary-identity')
expected=json.loads((WORK/'temp/dev-guest/guest.json').read_text())['guest_sha256']
assert json.loads(info.stdout)['wasm_sha256']==expected
env.update(PYTHONPATH=str(new/'python'),MARIAMEM_TEST_HOST=str(host),MARIAMEM_TEST_DEFAULT='1',MARIAMEM_DEV_EXPECTED_VERSION='12.3.3',MARIAMEM_DEV_EXPECTED_HANDSHAKE_VERSION='12.3.3',MARIAMEM_DEV_SQL_VERSION_EVIDENCE=str(WORK/'evidence/sql-version-overlay-host.json'))
run([sys.executable,'-m','pytest',str(WORK/'worktree/tests/test_dev_guest_smoke.py'),str(WORK/'worktree/tests/test_python_wire.py'),str(WORK/'worktree/tests/test_owned_snapshot.py'),'-q','-ra'],cwd=new,env=env,check=True,phase='overlay:guest-wire-ownership')
r=json.loads((WORK/'evidence/handshake-overlay-input.json').read_text());r.update(result='UNQUALIFIED',smoke='PASS',binary_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),binary_bytes=host.stat().st_size,go_buildinfo=run(['go','version','-m',str(host)],env=env,check=True,capture_output=True,text=True).stdout,changed_files=['internal/mysqlwire/wire.go'],source_inventory_sha256=hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest())
(WORK/'evidence/handshake-overlay-result.json').write_text(json.dumps(r,indent=2)+'\n')
