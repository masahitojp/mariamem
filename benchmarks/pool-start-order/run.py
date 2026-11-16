from pathlib import Path
import subprocess,json,hashlib,sys,platform
root=Path(__file__).resolve().parents[2];d=Path(__file__).resolve().parent;w=Path(sys.argv[1]).resolve();e=w/'evidence';t=w/'temp';e.mkdir(exist_ok=True);t.mkdir(exist_ok=True)
id=json.loads(subprocess.check_output([sys.executable,str(root/'scripts/git_identity.py'),'--root',str(root),'inspect','HEAD']));assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
src=(root/'benchmarks/insert-wait-owner/evidence/tpool_generic.cc').read_text()
names=['static int  throttling_interval_ms','void thread_pool_generic::maybe_wake_or_create_thread','bool thread_pool_generic::add_thread','void thread_pool_generic::submit_task','void thread_pool_generic::worker_main','void thread_pool_generic::maintenance()','void thread_pool_generic::set_concurrency','void thread_pool_generic::wait_begin','void thread_pool_generic::wait_end']
bodies=[];records=[]
for name in names:
 start=src.index(name);pos=src.index('{',start);depth=1;i=pos+1
 while depth:
  if src[i]=='{':depth+=1
  if src[i]=='}':depth-=1
  i+=1
 original=src[start:i];instrumented=original
 if name=='bool thread_pool_generic::add_thread':
  pairs=[('if (n_threads >= m_max_threads)\n    return false;','if (n_threads >= m_max_threads) { ++max_blocks; return false; }'),('if (m_thread_creation_pending.test_and_set())\n      return false;','if (m_thread_creation_pending.test_and_set()) { ++pending_blocks; return false; }'),('      return false;\n    }\n  }','      ++throttle_blocks; return false;\n    }\n  }')]
  for a,b in pairs:assert instrumented.count(a)==1,(name,a);instrumented=instrumented.replace(a,b)
 records.append({'method':name,'source_sha256':hashlib.sha256(original.encode()).hexdigest(),'instrumented_sha256':hashlib.sha256(instrumented.encode()).hexdigest(),'counter_hooks_only':original!=instrumented});bodies.append(instrumented)
cpp=(d/'support.cpp').read_text().replace('// EXTRACTED_METHODS','\n\n'.join(bodies));(t/'repro.cpp').write_text(cpp)
meta={'source_identity':id,'upstream_commit':'83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e','upstream_sha256':hashlib.sha256(src.encode()).hexdigest(),'methods':records,'generated_cpp_sha256':hashlib.sha256(cpp.encode()).hexdigest(),'platform':platform.platform(),'compiler':subprocess.check_output(['clang++','--version'],text=True),'command':['clang++','-std=c++17','-O2','-pthread','repro.cpp','-o','repro']};(e/'inputs.json').write_text(json.dumps(meta,indent=2))
with(e/'build.txt').open('w')as f:subprocess.run(['clang++','-std=c++17','-O2','-pthread',str(t/'repro.cpp'),'-o',str(t/'repro')],stdout=f,stderr=f,check=True,timeout=60)
meta['binary_sha256']=hashlib.sha256((t/'repro').read_bytes()).hexdigest();(e/'inputs.json').write_text(json.dumps(meta,indent=2));rows=[]
for rep in range(3):
 for mode in ['pending_400','after_start','announced_wait','pending_40']:
  p=subprocess.run([str(t/'repro'),mode],text=True,capture_output=True,timeout=5);(e/f'{rep}-{mode}.txt').write_text(p.stdout+p.stderr);assert p.returncode==0,(rep,mode,p.stderr);row=json.loads(p.stdout);row['rep']=rep;rows.append(row);print(row,flush=True)
(e/'results.json').write_text(json.dumps(rows,indent=2));assert len(rows)==12;print('ALL_12_CASES_PASS')
