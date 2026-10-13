"""Generate actual Wasm wait/spawn helpers and run owned boundary oracles."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/runtime_correctness'))
from narrow_fixture import u,vec,sec,typ

def fixture():
 types=[typ([0x7f,0x7f,0x7e],[0x7f]),typ([0x7f],[0x7f]),typ([0x7f,0x7f],[]),typ([],[]),typ([0x7f,0x7e,0x7e],[0x7f]),typ([0x7f,0x7f],[0x7f]),typ([0x7f,0x7f,0x7f],[0x7f])]
 imp=vec([u(4)+b'wasi'+u(12)+b'thread-spawn'+b'\0'+u(1)])
 code=b'\0\x20\0\x20\x01\x20\x02\xfe\x01\x02\0\x0b'
 bodies=[u(len(code))+code,b'\x02\0\x0b']
 wait64=b'\0\x20\0\x20\x01\x20\x02\xfe\x02\x03\0\x0b';notify=b'\0\x20\0\x20\x01\xfe\0\x02\0\x0b'
 bodies.extend([u(len(wait64))+wait64,u(len(notify))+notify])
 spawn=b'\0\x20\0\x10\0\x0b';load=b'\0\x20\0\xfe\x10\x02\0\x0b';bodies.extend([u(len(spawn))+spawn,u(len(load))+load])
 cmp=b'\0\x20\0\x20\x01\x20\x02\xfe\x48\x02\0\x0b';bodies.append(u(len(cmp))+cmp)
 pad=b'\0'+b'\x01'*(1<<20)+b'\x0b';bodies.append(u(len(pad))+pad)
 exports=vec([u(4)+b'Wait'+b'\0'+u(1),u(5)+b'Spawn'+b'\0'+u(5),u(17)+b'wasi_thread_start'+b'\0'+u(2),u(6)+b'Wait64'+b'\0'+u(3),u(6)+b'Notify'+b'\0'+u(4),u(4)+b'Load'+b'\0'+u(6),u(3)+b'Cmp'+b'\0'+u(7),u(6)+b'memory'+b'\x02\0'])
 return b'\0asm\x01\0\0\0'+sec(1,vec(types))+sec(2,imp)+sec(3,vec([u(0),u(2),u(4),u(5),u(1),u(1),u(6),u(3)]))+sec(5,b'\x01\x03\x01\x02')+sec(7,exports)+sec(10,vec(bodies))

def main():
 p=argparse.ArgumentParser();p.add_argument('--scope',choices=['wait','thread','all'],default='all');p.add_argument('--converter',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);wasm=out/'fixture.wasm';wasm.write_bytes(fixture())
 module=out/'module';module.mkdir();(module/'go.mod').write_text('module example.com/waitfixture\n\ngo 1.26.0\n')
 env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='')
 subprocess.run([str(a.converter.resolve()),'-pure','-keep-dead-funcs','-i',str(wasm),'-out-dir',str(module/'fixture'),'-pkg','fixture','-import','example.com/waitfixture/fixture'],check=True,env=env)
 base=module/'fixture/base'
 for name in ('wait_timeout_test.go','thread_identity_test.go'):
  src=ROOT/'scripts/runtime_correctness'/(name+'.txt')
  if src.exists() and (a.scope=='all' or (name.startswith('wait_') and a.scope=='wait') or (name.startswith('thread_') and a.scope=='thread')):shutil.copyfile(src,base/name)
 if a.scope in ('wait','all'):
  (base/'generated_wait64_test.go').write_text('package base\nimport "testing"\nfunc TestGeneratedWait64PositiveRange(t *testing.T) { checkWaitTimeoutPositiveRange(t, map[string]func(*Module,uint64,int64)int32{"wait64":func(m *Module,ea uint64,timeout int64)int32{return AtomicWait64At(m,ea,0,timeout)}}) }\n')
 for name,target in [('timeout_test.go.txt','audit_timeout_test.go'),('thread_boundary_test.go.txt','audit_thread_boundary_test.go')]:
  if a.scope=='all' or (name.startswith('timeout') and a.scope=='wait') or (name.startswith('thread_') and a.scope=='thread'):shutil.copyfile(ROOT/'benchmarks/spikes/v050-semantic-audit'/name,base/target)
 (base/'audit_support_test.go').write_text('package base\nfunc AuditParked(m *Module,ea uint64) int {m.Threads.parkMu.Lock();defer m.Threads.parkMu.Unlock();return len(m.Threads.parked[ea])}\n')
 checks=[]
 for race in [False,True]:
  cmd=['go','test',*(['-race'] if race else []),'-count=1','-timeout=30s','-v','./fixture/base']
  r=subprocess.run(cmd,cwd=module,env=env,capture_output=True,text=True,timeout=120);log=r.stdout+r.stderr;name='race' if race else 'normal';(out/(name+'.txt')).write_text(log)
  checks.append({'command':cmd,'exit_code':r.returncode,'race_reports':log.count('WARNING: DATA RACE'),'log_sha256':hashlib.sha256(log.encode()).hexdigest()})
 result={'wasm_sha256':hashlib.sha256(wasm.read_bytes()).hexdigest(),'converter_sha256':hashlib.sha256(a.converter.read_bytes()).hexdigest(),'raw_base_sha256':hashlib.sha256((base/'base.go').read_bytes()).hexdigest(),'checks':checks}
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(checks));assert all(x['exit_code']==0 for x in checks)
if __name__=='__main__':main()
