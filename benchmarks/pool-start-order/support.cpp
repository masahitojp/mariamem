#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <functional>
#include <iostream>
#include <list>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>
#include <algorithm>
using namespace std::chrono;
#define DBUG_ASSERT assert
static const milliseconds LONG_TASK_DURATION(500);
struct task { std::function<void()> fn; void add_ref(){} void execute(){fn();} };
struct worker_data {
 enum {EXECUTING_TASK=1,LONG_TASK=2,WAITING=4}; int m_state=0; worker_data*m_next=nullptr;
 system_clock::time_point m_task_start_time;
 bool is_executing_task(){return m_state&EXECUTING_TASK;} bool is_waiting(){return m_state&WAITING;} bool is_long_task(){return m_state&LONG_TASK;}
};
static thread_local worker_data*tls_worker_data=nullptr;
struct workers {
 std::list<worker_data*>v;
 void links(){worker_data*prev=nullptr;for(auto p:v){if(prev)prev->m_next=p;prev=p;}if(prev)prev->m_next=nullptr;}
 void push_back(worker_data*p){v.push_back(p);links();} void erase(worker_data*p){v.remove(p);links();}
 bool empty(){return v.empty();} size_t size(){return v.size();} worker_data*front(){return v.front();}
};
struct cache {worker_data*get(){return new worker_data;} void put(worker_data*p){delete p;}};
class thread_pool_generic;
void set_tls_pool(thread_pool_generic*){} // Only guest TLS lookup is replaced.
class thread_pool_generic {
public:
 enum class timer_state_t {ON,OFF}; enum {WAKE_REASON_TASK=1};
 cache m_thread_data_cache; workers m_active_threads,m_standby_threads;
 std::queue<task*>m_task_queue; std::mutex m_mtx; std::condition_variable cv;
 unsigned m_concurrency=16; int m_max_threads=64,m_min_threads=1;
 int m_long_tasks_count=0,m_waiting_task_count=0; unsigned long long m_tasks_enqueued=0,m_tasks_dequeued=0,m_last_activity=0;
 unsigned m_wakeups=0; size_t m_last_thread_count=0;
 bool m_in_shutdown=false; std::atomic_flag m_thread_creation_pending=ATOMIC_FLAG_INIT;
 std::atomic<int>pending_blocks{0},max_blocks{0},throttle_blocks{0};
 system_clock::time_point m_timestamp=system_clock::now(),m_last_thread_creation{};
 std::function<void()>m_worker_init_callback=[]{}; std::function<void()>m_worker_destroy_callback=[]{};
 void switch_timer(timer_state_t){} // Timer delivered explicitly by test, never background.
 void check_idle(system_clock::time_point){} // Idle timer shutdown outside scope.
 bool wake(int){assert(false);return false;} // No idle standby worker in this reduction.
 size_t thread_count(){return m_active_threads.size();}
 void maybe_wake_or_create_thread();bool add_thread();void submit_task(task*);
 void worker_main(worker_data*);void maintenance();void set_concurrency(unsigned=0);void wait_begin();void wait_end();
 bool get_task(worker_data*w,task**t){
  std::unique_lock<std::mutex>lk(m_mtx);
  if(w->is_long_task())--m_long_tasks_count;
  assert(!w->is_waiting());w->m_state=0;
  cv.wait(lk,[&]{return m_in_shutdown||!m_task_queue.empty();});
  if(m_task_queue.empty())return false;
  *t=m_task_queue.front();m_task_queue.pop();++m_tasks_dequeued;w->m_state=worker_data::EXECUTING_TASK;w->m_task_start_time=m_timestamp;return true;
 }
 void worker_end(worker_data*w){std::lock_guard<std::mutex>lk(m_mtx);m_active_threads.erase(w);m_thread_data_cache.put(w);cv.notify_all();}
 void stop(){std::unique_lock<std::mutex>lk(m_mtx);m_in_shutdown=true;cv.notify_all();assert(cv.wait_for(lk,seconds(2),[&]{return m_active_threads.empty();}));assert(m_task_queue.empty());}
};
// EXTRACTED_METHODS
int main(int argc,char**argv){
 assert(argc==2);std::string mode=argv[1];bool pending=mode!="after_start";bool announce=mode=="announced_wait";bool rescue=mode=="pending_400"||mode=="pending_40";
 assert(rescue||mode=="after_start"||announce);
 thread_pool_generic pool;std::mutex mu;std::condition_variable ready;
 bool init_enter=false,release_init=false,a_started=false,b_done=false,a_done=false;std::atomic<int>inits{0};
 steady_clock::time_point as,bs,ad;auto origin=steady_clock::now();
 pool.m_worker_init_callback=[&]{if(inits.fetch_add(1)==0){std::unique_lock<std::mutex>l(mu);init_enter=true;ready.notify_all();ready.wait(l,[&]{return release_init;});}};
 task a{[&]{std::unique_lock<std::mutex>l(mu);as=steady_clock::now();a_started=true;ready.notify_all();l.unlock();if(announce)pool.wait_begin();l.lock();assert(ready.wait_for(l,seconds(2),[&]{return b_done;}));l.unlock();if(announce)pool.wait_end();l.lock();ad=steady_clock::now();a_done=true;ready.notify_all();}};
 task b{[&]{std::lock_guard<std::mutex>l(mu);bs=steady_clock::now();b_done=true;ready.notify_all();}};
 pool.submit_task(&a);
 {std::unique_lock<std::mutex>l(mu);assert(ready.wait_for(l,seconds(2),[&]{return init_enter;}));}
 if(pending)pool.submit_task(&b);
 {std::unique_lock<std::mutex>l(mu);release_init=true;ready.notify_all();assert(ready.wait_for(l,seconds(2),[&]{return a_started;}));}
 if(!pending)pool.submit_task(&b);
 size_t queued=0,active=0;int waiting=0;double tick_ms=-1;
 if(rescue){
  std::unique_lock<std::mutex>l(mu);bool early=ready.wait_until(l,as+milliseconds(mode=="pending_400"?400:40),[&]{return b_done;});assert(!early);l.unlock();
  {std::lock_guard<std::mutex>p(pool.m_mtx);queued=pool.m_task_queue.size();active=pool.m_active_threads.size();waiting=pool.m_waiting_task_count;assert(queued==1&&active==1&&waiting==0);}
  tick_ms=duration<double,std::milli>(steady_clock::now()-as).count();pool.maintenance();
 }
 {std::unique_lock<std::mutex>l(mu);assert(ready.wait_for(l,seconds(2),[&]{return a_done&&b_done;}));}
 assert(pool.pending_blocks==(pending?1:0));assert(pool.max_blocks==0&&pool.throttle_blocks==0);pool.stop();
 std::cout<<"{\"mode\":\""<<mode<<"\",\"pending_blocks\":"<<pool.pending_blocks<<",\"max_blocks\":"<<pool.max_blocks<<",\"throttle_blocks\":"<<pool.throttle_blocks<<",\"queue_before_tick\":"<<queued<<",\"active_before_tick\":"<<active<<",\"waiting_before_tick\":"<<waiting<<",\"concurrency\":16,\"tick_ms\":"<<tick_ms<<",\"A_wait_ms\":"<<duration<double,std::milli>(ad-as).count()<<",\"B_start_ms\":"<<duration<double,std::milli>(bs-as).count()<<",\"workers\":"<<inits<<",\"clean\":true}"<<std::endl;
}
