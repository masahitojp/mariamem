// Native experiment transport/control owner. DATA never interprets MySQL bytes.
#include <mysql.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <cerrno>
#include <unistd.h>
#include "../libmysqld/mariamem_control_abi.h"
#include "routine_bootstrap.inc"
using Clock=std::chrono::steady_clock;
using Bytes=std::vector<unsigned char>;
constexpr size_t INPUT_LIMIT=1048581, OUTPUT_LIMIT=65536, CHUNK=4096;
enum Kind { OPEN=1,DATA=2,ACK=3,PEER_EOF=4,QUIESCE=5,STOP=6,STATS=7,HOLD=8,INSPECT=9,EXPIRE=10,
 READY=100,OPENED=101,REPLY=102,OUTPUT=103,RETIRED=104,POISON=105,CREDIT=106,STATE=107,STATS_REPLY=108,QUIESCED=109,REJECTED=110,DONE=111 };
enum Phase { HANDSHAKE,IDLE,RECEIVING,EXECUTING,FLUSHING,RETIRING,DEAD };
static const char *phase_name(Phase p){static const char *names[]={"handshake","idle","receiving","executing","flushing","retiring","dead"};return names[p];}
static void need(bool b,const char *what){if(!b){fprintf(stderr,"FAIL:%s\n",what);std::exit(2);}}
static void le(Bytes &b,uint64_t n,int size){for(int i=0;i<size;++i){b.push_back(n&255);n>>=8;}}
static uint64_t at(const unsigned char *p,int n){uint64_t r=0;for(int i=0;i<n;++i)r|=uint64_t(p[i])<<(8*i);return r;}
struct Frame {unsigned char kind;uint32_t request=0,slot=0;uint64_t epoch=0,generation=0,value=0;Bytes data;};
static Bytes bytes(const std::string &s){return Bytes(s.begin(),s.end());}
static bool exact(int fd,unsigned char *p,size_t n){while(n){ssize_t z=read(fd,p,n);if(z<0&&errno==EINTR)continue;if(z<=0)return false;p+=z;n-=z;}return true;}
static bool receive(Frame &f){unsigned char h[4];if(!exact(0,h,4))return false;size_t n=at(h,4);need(n>=33&&n<=33+65536,"internal frame length");Bytes b(n);need(exact(0,b.data(),n),"internal frame EOF");f.kind=b[0];f.request=at(b.data()+1,4);f.slot=at(b.data()+5,4);f.epoch=at(b.data()+9,8);f.generation=at(b.data()+17,8);f.value=at(b.data()+25,8);f.data.assign(b.begin()+33,b.end());return true;}
static void send_frame(const Frame &f){Bytes b;le(b,33+f.data.size(),4);b.push_back(f.kind);le(b,f.request,4);le(b,f.slot,4);le(b,f.epoch,8);le(b,f.generation,8);le(b,f.value,8);b.insert(b.end(),f.data.begin(),f.data.end());size_t p=0;while(p<b.size()){ssize_t n=write(1,b.data()+p,b.size()-p);if(n<0&&errno==EINTR)continue;if(n<=0)std::_Exit(80);p+=n;}}
struct Manager;
struct Session {
 Manager *owner;uint32_t slot;uint64_t generation;
 std::mutex io,handle;std::condition_variable changed;
 std::deque<unsigned char> input,output;
 uint64_t received=0,consumed=0,produced=0,sent=0,acked=0;
 size_t inputPeak=0,outputPeak=0;bool closed=false,armed=false,hold=false,creditPending=false,opened=false;
 int error=0;void *thd=nullptr;
 Phase phase=HANDSHAKE;unsigned status=2;uint64_t command=0,executions=0;int limitMs=5000;
 Clock::time_point deadline=Clock::time_point::max();
 bool statePending=true,workerDone=false,joining=false;int result=-1;unsigned netError=0;
 std::thread worker;
 Session(Manager *m,uint32_t s,uint64_t g,int ms):owner(m),slot(s),generation(g),limitMs(ms){deadline=Clock::now()+std::chrono::milliseconds(ms);}
 void closeIO(int err){std::lock_guard<std::mutex> l(io);closed=true;error=err;input.clear();output.clear();changed.notify_all();}
};
struct Manager {
 std::mutex gate,outMu,killMu;std::condition_variable progress,outReady,killReady;
 std::array<std::shared_ptr<Session>,16> slots{};std::array<uint64_t,16> generations{};
 std::deque<Frame> controls;size_t controlBytes=0;std::unique_ptr<Frame> urgent;
 std::deque<std::shared_ptr<Session>> killQueue;
 std::atomic<bool> controlOverflow{false};bool fenced=false,closing=false,poisoned=false,timerStop=false,reaperStop=false,killerStop=false,writerStop=false;
 std::string cause;uint64_t epoch=(uint64_t(getpid())<<32)|0x3b;
 uint64_t started=0,joined=0,stale=0,denied=0,controlPeak=0;size_t retiredInputPeak=0,retiredOutputPeak=0;
 std::thread writer,timer,reaper,killer;
 Frame frame(int kind,uint32_t request=0,const std::shared_ptr<Session>& s={},uint64_t value=0,std::string text=""){Frame f;f.kind=kind;f.request=request;f.epoch=epoch;f.value=value;f.data=bytes(text);if(s){f.slot=s->slot;f.generation=s->generation;}return f;}
 void emit(Frame f){std::lock_guard<std::mutex> l(outMu);size_t n=33+f.data.size();if(f.kind==POISON){urgent=std::make_unique<Frame>(std::move(f));}else if(controlBytes+n>65536){controlOverflow=true;}else{controlBytes+=n;controlPeak=std::max<uint64_t>(controlPeak,controlBytes);controls.push_back(std::move(f));}outReady.notify_all();}
 void state(const std::shared_ptr<Session>& s){s->statePending=true;outReady.notify_all();progress.notify_all();}
 void scheduleKill(const std::shared_ptr<Session>& s){std::lock_guard<std::mutex> l(killMu);killQueue.push_back(s);killReady.notify_all();}
 // gate held; queue closing never waits for external I/O or THD engine locks.
 void cancelLocked(int err){for(auto &s:slots)if(s){s->closeIO(err);scheduleKill(s);}progress.notify_all();outReady.notify_all();}
 void poisonLocked(const std::string &why){if(poisoned||closing)return;poisoned=true;fenced=true;cause=why;emit(frame(POISON,0,{},0,why));cancelLocked(why.find("deadline")!=std::string::npos?ETIMEDOUT:ECONNRESET);}
 std::shared_ptr<Session> match(const Frame &f){if(f.epoch!=epoch||f.slot>=16||!slots[f.slot]||slots[f.slot]->generation!=f.generation){++stale;emit(frame(REJECTED,f.request,{},5,"stale"));return {};}return slots[f.slot];}
 void start(){
  writer=std::thread([this]{writeLoop();});
  killer=std::thread([this]{need(!mysql_thread_init(),"killer thread init");for(;;){std::shared_ptr<Session>s;{std::unique_lock<std::mutex> l(killMu);killReady.wait(l,[&]{return killerStop||!killQueue.empty();});if(killQueue.empty()&&killerStop)break;s=killQueue.front();killQueue.pop_front();}std::lock_guard<std::mutex> pin(s->handle);if(s->thd)mariamem_spike_kill(s->thd);}mysql_thread_end();});
  timer=std::thread([this]{std::unique_lock<std::mutex> l(gate);while(!timerStop){progress.wait_for(l,std::chrono::milliseconds(5));if(controlOverflow.exchange(false))poisonLocked("control_queue_overflow");if(poisoned||closing)continue;auto now=Clock::now();for(auto &s:slots)if(s&&s->deadline<=now){if(s->command==0){s->phase=RETIRING;s->deadline=Clock::time_point::max();s->closeIO(ETIMEDOUT);scheduleKill(s);state(s);}else{poisonLocked("deadline");break;}}}});
  reaper=std::thread([this]{reapLoop();});
  emit(frame(READY,0,{},OUTPUT_LIMIT,"{\"max_sessions\":16,\"pending_input_limit\":1048581,\"output_limit\":65536}"));
 }
 bool admit(Session *raw){std::lock_guard<std::mutex> l(gate);auto s=slots[raw->slot];if(!s||s.get()!=raw||fenced||poisoned||closing){++denied;raw->closeIO(ECANCELED);return false;}need(s->phase==IDLE,"admit only idle");s->phase=RECEIVING;++s->command;s->deadline=Clock::now()+std::chrono::milliseconds(s->limitMs);state(s);return true;}
 int finish(Session *raw,unsigned status,bool retire){
  std::shared_ptr<Session>s;
  {std::lock_guard<std::mutex> l(gate);s=slots[raw->slot];if(!s||s.get()!=raw||poisoned||closing)return 1;s->phase=FLUSHING;state(s);}
  uint64_t target;{std::unique_lock<std::mutex> l(s->io);target=s->produced;s->changed.wait(l,[&]{return s->closed||s->acked>=target;});if(s->closed)return 1;}
  {std::lock_guard<std::mutex> l(gate);if(poisoned||closing)return 1;s->status=status;s->phase=retire?RETIRING:IDLE;s->deadline=Clock::time_point::max();state(s);}return 0;
 }
 int event(Session *raw,int kind,void *thd,unsigned status){
  if(kind==REGISTER_THD){{std::lock_guard<std::mutex> pin(raw->handle);raw->thd=thd;}std::lock_guard<std::mutex> l(gate);return poisoned||closing;}
  if(kind==UNREGISTER_THD){{std::lock_guard<std::mutex> pin(raw->handle);raw->thd=nullptr;}std::lock_guard<std::mutex> l(gate);raw->netError=status;raw->phase=RETIRING;raw->deadline=Clock::time_point::max();state(slots[raw->slot]);return 0;}
  if(kind==AUTH_COMPLETE)return finish(raw,status,false);
  if(kind==COMMAND_COMPLETE||kind==CONNECTION_COMPLETE)return finish(raw,status,kind==CONNECTION_COMPLETE);
  if(kind==ARM_COMMAND){{std::lock_guard<std::mutex> l(gate);if(fenced||poisoned||closing)return 1;}{std::lock_guard<std::mutex> l(raw->io);raw->armed=true;}return 0;}
  if(kind==EXECUTE_START){std::lock_guard<std::mutex> l(gate);raw->phase=EXECUTING;++raw->executions;state(slots[raw->slot]);return poisoned||closing;}
  return 0;
 }
 static int eventCb(void *p,int e,void *thd,unsigned st){auto *s=(Session*)p;return s->owner->event(s,e,thd,st);}
 static size_t readCb(void *p,unsigned char *to,size_t n){
  auto *s=(Session*)p;std::unique_lock<std::mutex> l(s->io);s->changed.wait(l,[&]{return s->closed||!s->input.empty();});if(s->closed)return size_t(-1);
  if(s->armed){s->armed=false;if(s->hold){l.unlock();{std::lock_guard<std::mutex> g(s->owner->gate);s->owner->emit(s->owner->frame(REPLY,0,s->owner->slots[s->slot],s->command,"admit_wait"));}l.lock();s->changed.wait(l,[&]{return s->closed||!s->hold;});if(s->closed)return size_t(-1);}l.unlock();if(!s->owner->admit(s))return size_t(-1);l.lock();if(s->closed)return size_t(-1);}
  n=std::min({n,s->input.size(),CHUNK});for(size_t i=0;i<n;++i){to[i]=s->input.front();s->input.pop_front();}s->consumed+=n;s->creditPending=true;l.unlock();s->owner->outReady.notify_all();return n;
 }
 static size_t writeCb(void *p,const unsigned char *from,size_t n){auto *s=(Session*)p;std::unique_lock<std::mutex> l(s->io);s->changed.wait(l,[&]{return s->closed||s->produced-s->acked<OUTPUT_LIMIT;});if(s->closed)return size_t(-1);n=std::min({n,size_t(OUTPUT_LIMIT-(s->produced-s->acked)),CHUNK});s->output.insert(s->output.end(),from,from+n);s->produced+=n;s->outputPeak=std::max<size_t>(s->outputPeak,s->produced-s->acked);l.unlock();s->owner->outReady.notify_all();return n;}
 static int errorCb(void *p){auto *s=(Session*)p;std::lock_guard<std::mutex> l(s->io);return s->error?s->error:EIO;}
 static void closeCb(void *p){((Session*)p)->closeIO(ECANCELED);}
 static int waitCb(void *p,int kind,int ms){auto *s=(Session*)p;std::unique_lock<std::mutex> l(s->io);auto ready=[&]{return s->closed||(kind==0?!s->input.empty():s->produced-s->acked<OUTPUT_LIMIT);};if(ms<0)s->changed.wait(l,ready);else if(!s->changed.wait_for(l,std::chrono::milliseconds(ms),ready)){s->error=ETIMEDOUT;return 0;}return s->closed?-1:1;}
 void open(const Frame &f){std::lock_guard<std::mutex> l(gate);if(f.epoch!=epoch){++stale;emit(frame(REJECTED,f.request,{},5,"stale"));return;}if(fenced||poisoned||closing){emit(frame(REJECTED,f.request,{},4,"closing"));return;}unsigned slot=16;for(unsigned i=0;i<16;++i)if(!slots[i]){slot=i;break;}if(slot==16){emit(frame(REJECTED,f.request,{},3,"capacity"));return;}need(generations[slot]!=UINT64_MAX,"generation exhaustion");int ms=int(f.value);need(ms>=100&&ms<=10000,"deadline configuration");auto s=std::make_shared<Session>(this,slot,++generations[slot],ms);slots[slot]=s;++started;emit(frame(OPENED,f.request,s));s->worker=std::thread([this,s]{need(!mysql_thread_init(),"session thread init");SpikeIO io{s.get(),readCb,writeCb,errorCb,waitCb,closeCb,eventCb};int result=mariamem_spike_control_session(&io);mysql_thread_end();{std::lock_guard<std::mutex> l(gate);s->result=result;s->workerDone=true;progress.notify_all();}});}
 void input(const Frame &f){std::lock_guard<std::mutex> l(gate);auto s=match(f);if(!s)return;if(poisoned||closing)return;std::lock_guard<std::mutex> q(s->io);if(s->closed)return;if(f.value!=s->received){poisonLockedAfterIO(s,q);return;}if(f.data.size()>INPUT_LIMIT-s->input.size()){controlOverflow=false; /* no payload appended */
    // Release the queue lock before cancelling all sessions.
    pendingPoison="pending_input_overflow";return;
   }s->input.insert(s->input.end(),f.data.begin(),f.data.end());s->received+=f.data.size();s->inputPeak=std::max(s->inputPeak,s->input.size());s->changed.notify_all();}
 // Input framing errors are escalated immediately by the reader after releasing I/O locks.
 std::string pendingPoison;
 void poisonLockedAfterIO(const std::shared_ptr<Session>&,const std::lock_guard<std::mutex>&){pendingPoison="input_offset";}
 void acknowledge(const Frame &f){std::lock_guard<std::mutex> l(gate);auto s=match(f);if(!s)return;{std::lock_guard<std::mutex> q(s->io);if(f.value<s->acked||f.value>s->sent){pendingPoison="output_offset";return;}s->acked=f.value;s->changed.notify_all();}outReady.notify_all();}
 void peerEOF(const Frame &f){std::lock_guard<std::mutex> l(gate);auto s=match(f);if(!s)return;bool pending;{std::lock_guard<std::mutex> q(s->io);pending=!s->input.empty();}if(s->phase==RETIRING)return;if(!fenced&&!closing&&!poisoned&&s->command!=0&&(s->phase!=IDLE||pending)){poisonLocked("unexpected_peer_eof");}else{s->phase=RETIRING;s->deadline=Clock::time_point::max();s->closeIO(ECANCELED);scheduleKill(s);state(s);}}
 void quiesce(const Frame &f){std::lock_guard<std::mutex> l(gate);if(f.epoch!=epoch){++stale;emit(frame(REJECTED,f.request,{},5,"stale"));return;}if(fenced||poisoned||closing){emit(frame(REJECTED,f.request,{},4,"closing"));return;}for(auto &s:slots)if(s&&s->phase!=IDLE){emit(frame(REJECTED,f.request,{},1,"busy"));return;}if(!f.value)for(auto &s:slots)if(s&&(s->status&1)){emit(frame(REJECTED,f.request,{},2,"transaction_active"));return;}fenced=true;emit(frame(QUIESCED,f.request,{},1,"fenced"));}
 std::string stats(){std::lock_guard<std::mutex> l(gate);std::string s="{\"fenced\":"+std::string(fenced?"true":"false")+",\"poisoned\":"+(poisoned?"true":"false")+",\"cause\":\""+cause+"\",\"started\":"+std::to_string(started)+",\"joined\":"+std::to_string(joined)+",\"stale\":"+std::to_string(stale)+",\"denied\":"+std::to_string(denied)+",\"retired_input_peak\":"+std::to_string(retiredInputPeak)+",\"retired_output_peak\":"+std::to_string(retiredOutputPeak)+",\"sessions\":[";bool comma=false;for(auto &p:slots)if(p){std::lock_guard<std::mutex> q(p->io);if(comma)s+=",";comma=true;s+="{\"slot\":"+std::to_string(p->slot)+",\"generation\":"+std::to_string(p->generation)+",\"phase\":\""+phase_name(p->phase)+"\",\"command\":"+std::to_string(p->command)+",\"status\":"+std::to_string(p->status)+",\"input\":"+std::to_string(p->input.size())+",\"outstanding\":"+std::to_string(p->produced-p->acked)+",\"input_peak\":"+std::to_string(p->inputPeak)+",\"output_peak\":"+std::to_string(p->outputPeak)+"}";}return s+"]}";}
 void dispatch(const Frame &f){
  if(f.kind==OPEN){open(f);return;}if(f.kind==DATA){input(f);}
  else if(f.kind==ACK){acknowledge(f);}
  else if(f.kind==PEER_EOF){peerEOF(f);}
  else if(f.kind==QUIESCE){quiesce(f);}
  else if(f.kind==STATS){emit(frame(STATS_REPLY,f.request,{},0,stats()));}
  else if(f.kind==HOLD){std::lock_guard<std::mutex> l(gate);auto s=match(f);if(s){std::lock_guard<std::mutex> q(s->io);s->hold=f.value;s->changed.notify_all();emit(frame(REPLY,f.request,s,0,"hold_set"));}}
  else if(f.kind==EXPIRE){std::lock_guard<std::mutex> l(gate);auto s=match(f);if(s){if(s->command!=f.value||s->phase==IDLE||s->phase==RETIRING){++stale;emit(frame(REJECTED,f.request,s,5,"stale_timer"));}else poisonLocked("deadline_injected");}}
  {std::lock_guard<std::mutex> l(gate);if(!pendingPoison.empty()){auto why=pendingPoison;pendingPoison.clear();poisonLocked(why);}}
 }
 void reapLoop(){for(;;){std::shared_ptr<Session>s;{std::unique_lock<std::mutex> l(gate);progress.wait_for(l,std::chrono::milliseconds(5),[&]{if(reaperStop)return true;for(auto &p:slots)if(p&&p->workerDone&&!p->joining)return true;return false;});for(auto &p:slots)if(p&&p->workerDone&&!p->joining){s=p;p->joining=true;break;}if(!s&&reaperStop)return;}if(!s)continue;s->worker.join();{std::lock_guard<std::mutex> l(gate);std::lock_guard<std::mutex> q(s->io);retiredInputPeak=std::max(retiredInputPeak,s->inputPeak);retiredOutputPeak=std::max(retiredOutputPeak,s->outputPeak);s->phase=DEAD;slots[s->slot].reset();++joined;emit(frame(RETIRED,0,s,s->result,"{\"net_error\":"+std::to_string(s->netError)+",\"executions\":"+std::to_string(s->executions)+",\"input_peak\":"+std::to_string(s->inputPeak)+",\"output_peak\":"+std::to_string(s->outputPeak)+"}"));progress.notify_all();}}}
 bool pickData(Frame &f,size_t &cursor){std::vector<std::shared_ptr<Session>> v;{std::lock_guard<std::mutex> l(gate);for(auto &s:slots)if(s)v.push_back(s);}for(size_t n=0;n<v.size();++n){auto s=v[(cursor+n)%v.size()];std::lock_guard<std::mutex> q(s->io);if(!s->opened||s->output.empty())continue;size_t k=std::min(CHUNK,s->output.size());f=frame(OUTPUT,0,s,s->sent);for(size_t i=0;i<k;++i){f.data.push_back(s->output.front());s->output.pop_front();}s->sent+=k;cursor=(cursor+n+1)%v.size();return true;}return false;}
 bool pickControl(Frame &f){ {std::lock_guard<std::mutex> l(outMu);if(urgent){f=std::move(*urgent);urgent.reset();return true;}if(!controls.empty()){f=std::move(controls.front());controls.pop_front();controlBytes-=33+f.data.size();return true;}}
  std::lock_guard<std::mutex> l(gate);for(auto &s:slots)if(s){if(s->statePending){s->statePending=false;f=frame(STATE,0,s,s->command,phase_name(s->phase));return true;}std::lock_guard<std::mutex> q(s->io);if(s->creditPending){s->creditPending=false;f=frame(CREDIT,0,s,s->consumed);return true;}}return false;
 }
 void writeLoop(){size_t cursor=0;unsigned quota=0;for(;;){Frame f;bool have=false;if(quota>=8){have=pickData(f,cursor);if(have)quota=0;}if(!have&&pickControl(f)){have=true;++quota;}if(!have&&pickData(f,cursor)){have=true;quota=0;}if(have){send_frame(f);if(f.kind==OPENED){std::lock_guard<std::mutex> g(gate);auto s=slots[f.slot];if(s&&s->generation==f.generation){std::lock_guard<std::mutex> q(s->io);s->opened=true;}}continue;}{std::unique_lock<std::mutex> l(outMu);if(writerStop&&controls.empty()&&!urgent)break;outReady.wait_for(l,std::chrono::milliseconds(2));}}}
 void shutdown(){ {std::lock_guard<std::mutex> l(gate);closing=true;fenced=true;cancelLocked(ECANCELED);}
  {std::unique_lock<std::mutex> l(gate);progress.wait(l,[&]{for(auto &s:slots)if(s)return false;return true;});timerStop=true;reaperStop=true;progress.notify_all();}
  timer.join();reaper.join();{std::lock_guard<std::mutex> l(killMu);killerStop=true;killReady.notify_all();}killer.join();
 }
 void stopWriter(){ {std::lock_guard<std::mutex> l(outMu);writerStop=true;outReady.notify_all();}writer.join();}
};
static MYSQL *connect(){MYSQL *m=mysql_init(nullptr);need(m!=nullptr,"mysql_init");mysql_options(m,MYSQL_OPT_USE_EMBEDDED_CONNECTION,nullptr);if(!mysql_real_connect(m,nullptr,"root","",nullptr,0,nullptr,0)){fprintf(stderr,"FAIL:connect %u %s\n",mysql_errno(m),mysql_error(m));std::exit(1);}return m;}
static void query(MYSQL *m,const char *s){if(mysql_query(m,s)){fprintf(stderr,"FAIL:SQL %s %u %s\n",s,mysql_errno(m),mysql_error(m));std::exit(1);}}
static void embedded_prepared(MYSQL *m){
 auto before=mariamem_spike_decode_count();MYSQL_STMT *st=mysql_stmt_init(m);const char *sql="SELECT ?, ?";
 need(!mysql_stmt_prepare(st,sql,strlen(sql)),"embedded prepare");long long n=42,got=0;char s[3]={'a',0,'b'},out[8]={};unsigned long len=3,outlen=0;MYSQL_BIND in[2]={},result[2]={};
 in[0].buffer_type=MYSQL_TYPE_LONGLONG;in[0].buffer=&n;in[1].buffer_type=MYSQL_TYPE_STRING;in[1].buffer=s;in[1].buffer_length=3;in[1].length=&len;
 need(!mysql_stmt_bind_param(st,in),"embedded bind input");need(!mysql_stmt_execute(st),"embedded execute");
 result[0].buffer_type=MYSQL_TYPE_LONGLONG;result[0].buffer=&got;result[1].buffer_type=MYSQL_TYPE_STRING;result[1].buffer=out;result[1].buffer_length=sizeof(out);result[1].length=&outlen;
 need(!mysql_stmt_bind_result(st,result),"embedded bind result");need(!mysql_stmt_store_result(st),"embedded store");need(!mysql_stmt_fetch(st),"embedded fetch");need(got==42&&outlen==3&&!memcmp(s,out,3),"embedded typed result");need(mysql_stmt_fetch(st)==MYSQL_NO_DATA,"embedded one row");need(!mysql_stmt_close(st),"embedded stmt close");need(before==mariamem_spike_decode_count(),"embedded did not use native decode");
 fprintf(stderr,"PASS:embedded_MYSQL_BIND\n");
}

extern "C" int issue65_bootstrap(void);
extern "C" void issue65_shutdown(void);
int main(){
 need(!issue65_bootstrap(),"product fresh bootstrap");
 MYSQL *m=connect();query(m,"CREATE TABLE test.effects(n INT) ENGINE=MEMORY");embedded_prepared(m);mysql_close(m);
 Manager manager;manager.start();Frame f;
 while(receive(f)){
  if(f.kind==STOP)break;
  if(f.kind==INSPECT){m=connect();query(m,"SELECT COUNT(*) FROM test.effects");MYSQL_RES *r=mysql_store_result(m);need(r!=nullptr,"oracle result");MYSQL_ROW row=mysql_fetch_row(r);std::string count=row[0];mysql_free_result(r);mysql_close(m);manager.emit(manager.frame(REPLY,f.request,{},std::stoull(count),"effects_count"));}
  else manager.dispatch(f);
 }
 manager.shutdown();m=connect();need(!mysql_select_db(m,"test"),"reopen test");need(!routine_bootstrap(m,1),"routine remains valid");embedded_prepared(m);mysql_close(m);issue65_shutdown();
 manager.emit(manager.frame(DONE,0,{},0,manager.stats()));manager.stopWriter();
 fprintf(stderr,"PASS:engine_shutdown_joined started=%llu joined=%llu\n",(unsigned long long)manager.started,(unsigned long long)manager.joined);
}
