"""Execute exact candidate API/method bodies with a scheduler seam; not a guest build."""
import pathlib,sys,subprocess,json,hashlib
src=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=True)
def block(text,anchor):
 a=text.index(anchor);b=text.index('{',a);level=1;i=b+1
 while level:
  if text[i]=='{':level+=1
  elif text[i]=='}':level-=1
  i+=1
 return text[a:i]
generic=(src/'tpool/tpool_generic.cc').read_text();worker=block(generic,'struct worker_data')+';'
begin=block(generic,'bool thread_pool_generic::wait_begin_if_needed()').replace('thread_pool_generic::','test_pool::')
end=block(generic,'void thread_pool_generic::wait_end()').replace('thread_pool_generic::','test_pool::')
history=block((src/'storage/innobase/trx/trx0sys.cc').read_text(),'size_t trx_sys_t::history_size()')
(out/'my_global.h').write_text('#pragma once\n#include <cstdint>\n#include <cstring>\n#include <cstdlib>\n#include <cassert>\n#define CPU_LEVEL1_DCACHE_LINESIZE 64\n')
(out/'my_pthread.h').write_text('#pragma once\n')
cpp=r'''#include <cassert>
#include <array>
#include <stdexcept>
#include <type_traits>
#include <thread>
#include <tpool.h>
namespace tpool {
enum worker_wake_reason {WAKE_REASON_NONE,WAKE_REASON_TASK,WAKE_REASON_SHUTDOWN};
WORKER
static thread_local worker_data *tls_worker_data;
class test_pool : public thread_pool {
public:
 std::mutex m_mtx;int m_waiting_task_count=0;int wake_calls=0;bool throw_wake=false;
 aio *create_native_aio(int,aio_implementation)override{return nullptr;}
 void submit_task(task*)override{}
 timer *create_timer(callback_func,void*)override{return nullptr;}
 void maybe_wake_or_create_thread(){wake_calls++;if(throw_wake)throw std::runtime_error("wake");}
 bool wait_begin_if_needed()override;
 void wait_end()override;
};
BEGIN
END
extern "C" void set_tls_pool(thread_pool*);
}
static int *waiting_count;
static int expected_waiting;
struct latch {
 bool busy=false;int tries=0,slow=0,unlocks=0;
 bool rd_lock_try(){tries++;return !busy;}
 void rd_lock(){slow++;assert(*waiting_count==expected_waiting);}
 void rd_unlock(){unlocks++;}
};
struct rseg {struct latch latch;size_t history_size=7;};
struct trx_sys_t {std::array<rseg,3>rseg_array;bool is_initialised(){return true;}size_t history_size();};
#define ut_ad(x) assert(x)
#define SRW_LOCK_CALL
HISTORY
int main(){
 using namespace tpool;
 static_assert(!std::is_copy_constructible<scoped_wait>::value,"unique wait ownership");
 static_assert(!std::is_move_constructible<scoped_wait>::value,"unique wait ownership");
 test_pool p;worker_data worker;tls_worker_data=&worker;set_tls_pool(&p);
 waiting_count=&p.m_waiting_task_count;
 worker.m_state=worker_data::EXECUTING_TASK;
 {scoped_wait outer;assert(p.m_waiting_task_count==1&&worker.is_waiting());{scoped_wait inner;assert(p.m_waiting_task_count==1);}assert(worker.is_waiting());}
 assert(p.m_waiting_task_count==0&&!worker.is_waiting()&&p.wake_calls==1);
 worker.m_state=worker_data::EXECUTING_TASK|worker_data::WAITING;p.m_waiting_task_count=1;
 {scoped_wait nested;}assert(p.m_waiting_task_count==1&&worker.is_waiting());p.wait_end();
 for(int state:{0,worker_data::EXECUTING_TASK|worker_data::LONG_TASK}){worker.m_state=state;scoped_wait skip;assert(p.m_waiting_task_count==0);}
 worker.m_state=worker_data::EXECUTING_TASK;tls_worker_data=nullptr;{scoped_wait nonworker;}assert(p.m_waiting_task_count==0);tls_worker_data=&worker;
 set_tls_pool(nullptr);{scoped_wait no_pool;}assert(p.m_waiting_task_count==0);set_tls_pool(&p);
 {scoped_wait owner;set_tls_pool(nullptr);}assert(p.m_waiting_task_count==0);set_tls_pool(&p);
 try{scoped_wait exception;throw std::runtime_error("body");}catch(const std::runtime_error&){}assert(p.m_waiting_task_count==0&&!worker.is_waiting());
 p.throw_wake=true;try{scoped_wait failed;assert(false);}catch(const std::runtime_error&){}assert(p.m_waiting_task_count==0&&!worker.is_waiting());p.throw_wake=false;
 {scoped_wait retry;assert(p.m_waiting_task_count==1);}assert(p.m_waiting_task_count==0);
 int before=p.wake_calls;trx_sys_t fast;assert(fast.history_size()==21);assert(p.wake_calls==before);for(auto&r:fast.rseg_array)assert(r.latch.tries==1&&r.latch.slow==0&&r.latch.unlocks==1);
 trx_sys_t slow;slow.rseg_array[1].latch.busy=true;expected_waiting=1;assert(slow.history_size()==21);assert(p.wake_calls==before+1&&p.m_waiting_task_count==0);for(auto&r:slow.rseg_array)assert(r.latch.unlocks==1);
 tls_worker_data=nullptr;expected_waiting=0;trx_sys_t foreground;foreground.rseg_array[0].latch.busy=true;assert(foreground.history_size()==21);assert(p.m_waiting_task_count==0);
 auto f=[&]{worker_data w;w.m_state=worker_data::EXECUTING_TASK;tls_worker_data=&w;set_tls_pool(&p);for(int i=0;i<100;i++){scoped_wait s;}set_tls_pool(nullptr);tls_worker_data=nullptr;};
 std::thread a(f),b(f);a.join();b.join();assert(p.m_waiting_task_count==0);
 return 0;
}
'''.replace('WORKER',worker).replace('BEGIN',begin).replace('END',end).replace('HISTORY',history)
(out/'contract.cc').write_text(cpp)
cmd=['g++','-std=c++17','-pthread','-Wall','-Wextra','-Wno-unused-parameter','-include',str(out/'my_global.h'),'-I'+str(out),'-I'+str(src/'tpool'),str(out/'contract.cc'),str(src/'tpool/wait_notification.cc'),'-o',str(out/'contract')]
q=subprocess.run(cmd,capture_output=True,text=True);(out/'compile.txt').write_text(q.stdout+q.stderr);q.check_returncode();subprocess.run([str(out/'contract')],check=True,timeout=10)
proof={'result':'PASS','scope':'realpatchedheader,wait_notification.cc,and exact generic begin/end + history_size bodies;fake scheduler and minimalplatformheaders;fullguestbuild still required','body_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in [('worker',worker),('begin',begin),('end',end),('history',history)]},'checks':['nonworker/no-pool/inactive/long/alreadywaiting','nestedscopedownership','bodyexceptioncleanup','beginfailure rollback and retry','TLSowner retained','uncontendedfastpath no notification','contendedread notification/unlockloops','two-thread TLS isolation/balance']}
(out/'result.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
