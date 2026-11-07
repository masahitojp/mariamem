"""Compile actual timeout header and Manager::open with engine stubs;detect mutations."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--header',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
pins=json.loads((Path(__file__).parent/'timeout-source.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if sha(a.source)!=pins['controller_sha256'] or sha(a.header)!=pins['header_sha256']:raise ValueError('timeout source changed')
s=a.source.read_text();start=s.index(' void open(const Frame &f){');end=s.index('\n void input(',start);method=s[start:end];header=a.header.read_text()
pre=r'''
#include "issue65_deadline.h"
#include <array>
#include <cassert>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <cstdint>
struct Manager;
struct Session {uint32_t slot;uint64_t generation;issue65_deadline::Budget deadline;std::thread worker;int result=0;bool workerDone=false;Session(Manager*,uint32_t s,uint64_t g,uint64_t ns):slot(s),generation(g),deadline(ns){};};
struct Frame {int kind=0;uint32_t request=0,slot=0;uint64_t epoch=0,generation=0,value=100;};
struct SpikeIO {void *session;int a,b,c,d,e,f;};
int mysql_thread_init(){return 0;}void mysql_thread_end(){}int mariamem_spike_control_session(SpikeIO*){return 0;}
void need(bool value,const char*){assert(value);}
constexpr int REJECTED=110,OPENED=101;
struct Manager {std::mutex gate;std::condition_variable progress;std::array<std::shared_ptr<Session>,16>slots{};std::array<uint64_t,16>generations{};uint64_t epoch=42,stale=0,started=0;bool fenced=false,poisoned=false,closing=false;
static constexpr int readCb=0,writeCb=0,errorCb=0,waitCb=0,closeCb=0,eventCb=0;
std::vector<Frame> replies;
Frame frame(int kind,uint32_t request,std::shared_ptr<Session>s={},uint64_t value=0,std::string=""){Frame f;f.kind=kind;f.request=request;f.epoch=epoch;f.value=value;if(s){f.slot=s->slot;f.generation=s->generation;}return f;}
void emit(Frame f){replies.push_back(f);}
'''
post=r'''
};
using namespace issue65_deadline;
Clock::time_point point(int64_t ns){return Clock::time_point(Clock::duration(ns));}
int main(){
 for(uint64_t ns:{uint64_t(1),uint64_t(999999),uint64_t(30000000000),uint64_t(30000000001),maximum}){assert(valid(ns));Budget b(ns);assert(b.limit==ns);b.arm(point(100));assert(!b.expired(point(100)));if(ns>1)assert(!b.expired(point(101)));b.disarm();assert(!b.expired(point(INT64_MAX)));b.arm(point(200));assert(b.start==200);}
 assert(!valid(0)&&!valid(maximum+1)&&!valid(UINT64_MAX));
 assert(!elapsed(UINT64_MAX-1,UINT64_MAX-20,100));assert(!elapsed(50,UINT64_MAX-20,100));assert(elapsed(79,UINT64_MAX-20,100));
 Budget wrap(3);wrap.arm(point(INT64_MAX-1));assert(!wrap.expired(point(INT64_MAX)));assert(wrap.expired(point(INT64_MIN+1)));
 Budget ordinary(30000000001);ordinary.arm(point(100));assert(!ordinary.expired(point(30000000100)));assert(ordinary.expired(point(30000000101)));ordinary.arm(point(40000000000));assert(!ordinary.expired(point(40000000001)));
 Manager m;Frame f;f.request=17;f.epoch=42;f.slot=7;f.generation=19;f.value=30000000001;m.open(f);assert(m.replies.size()==1);auto reply=m.replies.back();assert(reply.kind==OPENED&&reply.slot==7&&reply.generation==19&&reply.request==17&&reply.epoch==42);assert(m.slots[7]&&m.slots[7]->slot==7&&m.generations[7]==19&&m.slots[7]->deadline.limit==f.value);m.slots[7]->worker.join();
 auto reject=[&](Frame r,int code){auto started=m.started;auto watermark=m.generations;m.open(r);auto result=m.replies.back();assert(result.kind==REJECTED&&result.value==unsigned(code)&&result.slot==r.slot&&result.generation==r.generation&&result.request==r.request&&result.epoch==42);assert(m.started==started&&m.generations==watermark);};
 reject(f,8);auto r=f;r.slot=16;reject(r,8);r=f;r.generation=0;reject(r,8);r=f;r.epoch=43;reject(r,5);m.slots[7].reset();reject(f,8);r=f;r.generation=18;reject(r,8);
 r=f;r.generation=20;for(uint64_t ns:{uint64_t(0),maximum+1,UINT64_MAX}){r.value=ns;reject(r,9);}r.value=maximum;m.closing=true;reject(r,4);m.closing=false;m.open(r);assert(m.replies.back().generation==20&&m.slots[7]->deadline.limit==maximum);m.slots[7]->worker.join();
}
'''
mutations={
 'legacy_range':('header','return ns!=0 && ns<=maximum;','return ns>=100000000 && ns<=10000000000;'),
 'rounds_milliseconds':('header','limit(ns),start','limit(ns/1000000*1000000),start'),
 'adds_overflowing_deadline':('header','return now-start>=ns;','return now>=start+ns;'),
 'forgets_disarm':('header','armed=false;','armed=true;'),
 'fails_to_rearm':('header','start=ticks(now);armed=true;','(void)now;armed=true;'),
 'narrows_open_timeout':('method','this,f.slot,f.generation,f.value','this,f.slot,f.generation,uint32_t(f.value)'),
 'guest_chooses_own_tuple':('method','this,f.slot,f.generation,f.value','this,0,1,f.value'),
 'accepts_replayed_generation':('method','f.generation<=generations[f.slot]||',''),
 'reject_advances_watermark':('method','++stale;reject(8,"open_identity")','++stale;if(f.slot<16)generations[f.slot]=f.generation;reject(8,"open_identity")'),
}
rows=[]
for name,change in [('positive',None),*mutations.items()]:
 h,body=header,method
 if change:
  target,before,after=change;text=h if target=='header' else body
  if text.count(before)!=1:raise ValueError('mutation anchor changed: '+name)
  text=text.replace(before,after)
  if target=='header':h=text
  else:body=text
 (a.output/'issue65_deadline.h').write_text(h);source=a.output/(name+'.cc');source.write_text(pre+body+post);binary=a.output/name
 subprocess.run(['c++','-std=c++17','-pthread','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(source),'-o',str(binary)],check=True)
 result=subprocess.run([str(binary)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (a.output/(name+'.txt')).write_text(result.stdout)
 if (result.returncode==0)!=(change is None):raise ValueError('timeout mutation not detected: '+name)
 rows.append({'name':name,'exit':result.returncode})
(a.output/'result.json').write_text(json.dumps({'scope':'exact timeout header and OPEN with engine stubs;not a full engine run','controller_sha256':sha(a.source),'header_sha256':sha(a.header),'sanitizer':'undefined with no recovery','cases':rows},indent=2)+'\n');print('PASS timeout arithmetic/open and9 detected source mutations')
