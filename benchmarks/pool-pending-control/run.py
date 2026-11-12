"""Finite native scheduler mechanism control. No guest build or natural SQL sampling."""
import argparse,hashlib,json,os,pathlib,subprocess,time
P=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--upstream',type=pathlib.Path,required=True);p.add_argument('--temp',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
plan=json.loads((P/'plan.json').read_text());a.temp.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
for n,h in plan['upstream_files_sha256'].items():assert sha((a.upstream/n).read_bytes())==h,n
# No product tpool patch applies to this pinned upstream file.
s=(a.upstream/'tpool_generic.cc').read_text();source=s
replacements=[
 ('class thread_pool_generic : public thread_pool\n{','class thread_pool_generic : public thread_pool\n{\npublic: // harness: permit locked inspection and explicit maintenance'),
 ('  m_thread_creation_pending.clear();\n\n  while','  m_thread_creation_pending.clear();\n  probe_event("pending_clear");\n\n  while'),
 ('    if (m_thread_creation_pending.test_and_set())\n      return false;', '    if (m_thread_creation_pending.test_and_set()) { probe_event("pending_refusal"); return false; }'),
 ('    std::thread thread(&thread_pool_generic::worker_main, this, thread_data);','    probe_event("spawn_call");\n    std::thread thread(&thread_pool_generic::worker_main, this, thread_data);'),
 ('  task* task;\n  set_tls_pool(this);','  task* task;\n  probe_event("worker_enter");\n  set_tls_pool(this);'),
 ('    task->execute();','    probe_event("task_begin");\n    task->execute();\n    probe_event("task_end");'),
 ('  m_waiting_task_count++;','  m_waiting_task_count++;\n  probe_event("wait_begin");'),
 ('void thread_pool_generic::maintenance()\n{','void thread_pool_generic::maintenance()\n{\n  probe_event("maintenance");'),
]
for old,new in replacements:
 assert s.count(old)==1,old;s=s.replace(old,new)
# Support headers only. Pool/task/queue/mutex/atomic algorithms stay upstream.
headers={
 'my_global.h':'#pragma once\n#include <cstddef>\n#include <cstdint>\n#include <cassert>\n',
 'my_pthread.h':'#pragma once\n',
 'my_dbug.h':'#pragma once\n#include <cassert>\n#define DBUG_ASSERT(x) assert(x)\n#define DBUG_PUSH_EMPTY ((void)0)\n#define DBUG_POP_EMPTY ((void)0)\n',
 'aligned.h':'#pragma once\n#define CPU_LEVEL1_DCACHE_LINESIZE 64\n',
 'thr_timer.h':'''#pragma once
struct thr_timer_t { void (*probe_callback)(void*) = nullptr; void* probe_arg = nullptr; };
inline void thr_timer_init(thr_timer_t*t,void(*f)(void*),void*a){t->probe_callback=f;t->probe_arg=a;}
inline void thr_timer_end(thr_timer_t*){}
inline void thr_timer_settime(thr_timer_t*,unsigned long long){}
inline void thr_timer_set_period(thr_timer_t*,unsigned long long){}
'''}
for n,v in headers.items():(a.temp/n).write_text(v)
(a.temp/'instrumented.cc').write_text(s)
compiler=subprocess.check_output(['clang++','--version'],text=True)
command=['clang++','-std=c++17','-O2','-pthread','-I'+str(a.temp.resolve()),'-I'+str(a.upstream.resolve()),str(P/'harness.cc'),*[str(a.upstream/n) for n in ('task.cc','task_group.cc','wait_notification.cc')],'-o',str(a.temp/'control')]
t0=time.monotonic();r=subprocess.run(command,capture_output=True,text=True,timeout=60)
(a.temp/'build.log').write_text(r.stdout+r.stderr)
if r.returncode:raise RuntimeError(r.stderr)
build_seconds=time.monotonic()-t0
results=[]
for rep in range(plan['repetitions']):
 for concurrency in plan['concurrency']:
  for arm in plan['controls']:
   r=subprocess.run([str(a.temp/'control'),arm,str(concurrency)],capture_output=True,text=True,timeout=plan['watchdog_seconds'])
   if r.returncode:
    (a.output/'failure.json').write_text(json.dumps({'repetition':rep+1,'arm':arm,'concurrency':concurrency,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2)+'\n');raise RuntimeError(r.stderr)
   d=json.loads(r.stdout);assert d['result']=='PASS';d['repetition']=rep+1;results.append(d)
   print(rep+1,concurrency,arm,'PASS',flush=True)
(a.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
identity=json.loads(subprocess.check_output(['python3',str(P.parents[1]/'scripts/git_identity.py'),'inspect','HEAD'],text=True))
(a.output/'inputs.json').write_text(json.dumps({'source':identity,'plan_sha256':sha((P/'plan.json').read_bytes()),'harness_sha256':sha((P/'harness.cc').read_bytes()),'runner_sha256':sha(pathlib.Path(__file__).read_bytes()),'upstream_source_commit':plan['upstream_source_commit'],'upstream_files_sha256':plan['upstream_files_sha256'],'instrumented_cpp_sha256':sha(s.encode()),'support_headers_sha256':{n:sha(v.encode()) for n,v in headers.items()},'compiler':compiler,'binary_sha256':sha((a.temp/'control').read_bytes()),'build_seconds':build_seconds,'native_builds':1,'guest_builds':0,'heavy_ci':0,'cases':len(results),'limitations':plan['limitations']},indent=2)+'\n')
