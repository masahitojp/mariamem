// Controlled scheduling only. The compiled pool/task bodies come from pinned upstream.
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
using Clock = std::chrono::steady_clock;
struct Event { std::string kind; double ms; };
std::mutex event_mutex;
std::vector<Event> events;
Clock::time_point origin;
void probe_event(const char *kind) {
  std::lock_guard<std::mutex> lock(event_mutex);
  if (events.size() >= 128) std::abort();
  events.push_back({kind, std::chrono::duration<double,std::milli>(Clock::now()-origin).count()});
}
#include "instrumented.cc"
struct Control {
  std::mutex mutex;
  std::condition_variable cv;
  bool init_entered=false, release_init=false, first_started=false, release_first=false;
  bool second_done=false, third_done=false, reported=false;
  std::atomic<int> entries{0}, exits{0};
  tpool::thread_pool_generic *pool=nullptr;
} control;
void demand(bool condition, const char *message) {
  if (!condition) {std::cerr << "FAIL: " << message << std::endl; std::_Exit(2);}
}
template<typename Predicate> void await(Predicate p, const char *message) {
  std::unique_lock<std::mutex> lock(control.mutex);
  demand(control.cv.wait_for(lock,std::chrono::seconds(2),p),message);
}
void init() {
  if (++control.entries != 1) return;
  std::unique_lock<std::mutex> lock(control.mutex);
  control.init_entered=true;control.cv.notify_all();
  demand(control.cv.wait_for(lock,std::chrono::seconds(2),[]{return control.release_init;}),"first init release");
}
void destroyed() {++control.exits;}
void first(void*) {
  if (control.reported) tpool::tpool_wait_begin();
  {
    std::unique_lock<std::mutex> lock(control.mutex);
    control.first_started=true;control.cv.notify_all();
    demand(control.cv.wait_for(lock,std::chrono::seconds(2),[]{return control.release_first;}),"first task release");
  }
  if (control.reported) tpool::tpool_wait_end();
}
void second(void*) {std::lock_guard<std::mutex> lock(control.mutex);control.second_done=true;control.cv.notify_all();}
void third(void*) {std::lock_guard<std::mutex> lock(control.mutex);control.third_done=true;control.cv.notify_all();}
struct State {size_t queue,active,standby; unsigned waiting,long_tasks; unsigned long long dequeued;};
State state(tpool::thread_pool_generic &p) {
  std::lock_guard<std::mutex> lock(p.m_mtx);
  return {p.m_task_queue.size(),p.m_active_threads.size(),p.m_standby_threads.size(),p.m_waiting_task_count,p.m_long_tasks_count,p.m_tasks_dequeued};
}
size_t event_count(const char *kind) {
 std::lock_guard<std::mutex> lock(event_mutex);size_t n=0;for(auto&e:events) if(e.kind==kind)++n;return n;
}
void release_init() {std::lock_guard<std::mutex> lock(control.mutex);control.release_init=true;control.cv.notify_all();}
void release_first() {std::lock_guard<std::mutex> lock(control.mutex);control.release_first=true;control.cv.notify_all();}
int main(int argc,char**argv) {
 demand(argc==3,"arguments");std::string arm=argv[1];int concurrency=std::stoi(argv[2]);
 demand(concurrency==1||concurrency==16,"concurrency");
 bool fixed=arm=="fixed_pool", late=arm=="late_submit_unreported";
 control.reported=arm=="pending_reported";
 bool hold=arm=="pending_unreported_maintenance"||arm=="pending_unreported_release"||arm=="pending_unreported_submit";
 demand(fixed||late||hold||control.reported,"arm");
 origin=Clock::now();State pending{},before{};double hold_ms=0;size_t pending_count=0;
 {
  tpool::thread_pool_generic pool(fixed?2:1,fixed?2:32);control.pool=&pool;
  pool.set_concurrency(concurrency);pool.set_thread_callbacks(init,destroyed);
  // Prime the actual coarse task timestamp, as the initial maintenance tick does.
  // Later ticks are controlled explicitly, not automatically scheduled by the timer stub.
  pool.maintenance();
  tpool::waitable_task a(first,nullptr),b(second,nullptr),c(third,nullptr);
  pool.submit_task(&a);await([]{return control.init_entered;},"first worker init");
  if (!late) pool.submit_task(&b);
  pending=state(pool);pending_count=event_count("pending_refusal");
  if (!late&&!fixed) demand(pending.queue==2&&pending.active==1&&pending_count==1,"queued pair with pending refusal");
  if (fixed) {release_init();await([]{return control.second_done;},"fixed pool bypasses pending");demand(pending_count==0,"fixed pool no pending refusal");}
  release_init();await([]{return control.first_started;},"first task entered");
  if (late) pool.submit_task(&b);
  if (hold) {
   auto start=Clock::now();
   {std::unique_lock<std::mutex> lock(control.mutex);demand(!control.cv.wait_for(lock,std::chrono::milliseconds(50),[]{return control.second_done;}),"unexpected progress before trigger");}
   hold_ms=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
   demand(std::chrono::duration<double,std::milli>(Clock::now()-origin).count()<250,"invalid control: excessive host scheduling delay");
   before=state(pool);
   demand(before.queue==1&&before.active==1&&before.waiting==0&&before.long_tasks==0&&before.dequeued==1,"queued work after pending clear");
   demand(event_count("pending_clear")==1,"pending clear observed");
   probe_event("explicit_trigger");
   if(arm=="pending_unreported_maintenance") pool.maintenance();
   else if(arm=="pending_unreported_release") release_first();
   else pool.submit_task(&c);
  } else before=state(pool);
  await([]{return control.second_done;},"second task progress");
  release_first();a.wait();b.wait();
  if(arm=="pending_unreported_submit") {await([]{return control.third_done;},"third task progress");c.wait();}
  auto done=state(pool);demand(done.queue==0&&done.waiting==0,"drained queue and wait accounting");
  demand(a.get_ref_count()==0&&b.get_ref_count()==0&&c.get_ref_count()==0,"all task references released");
 }
 demand(control.entries==control.exits,"destructor joined all workers");
 if(hold) {
  auto n=control.entries.load();demand(n==(arm=="pending_unreported_release"?1:2),"rescue worker count");
 }
 std::cout<<"{\"arm\":\""<<arm<<"\",\"concurrency_requested\":"<<concurrency<<",\"result\":\"PASS\",\"pending_refusals\":"<<pending_count<<",\"synthetic_hold_ms\":"<<hold_ms<<",\"before_trigger\":{\"queued\":"<<before.queue<<",\"active\":"<<before.active<<",\"waiting\":"<<before.waiting<<",\"long\":"<<before.long_tasks<<",\"dequeued\":"<<before.dequeued<<"},\"workers_created\":"<<control.entries<<",\"workers_joined\":"<<control.exits<<",\"task_refs_after\":0,\"queue_after\":0,\"events\":[";
 bool first_event=true;for(auto&e:events){if(!first_event)std::cout<<",";first_event=false;std::cout<<"{\"kind\":\""<<e.kind<<"\",\"ms\":"<<e.ms<<"}";}std::cout<<"]}\n";
}
