"""Compile exact Manager::open with engine/thread-launch stubs; inspect identity mutations."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
if hashlib.sha256(a.source.read_bytes()).hexdigest()!='ab9890c071da2df7432e6ce6ff1656711dc09ff1ce6f52e88d2301b01b6aeaf4':raise ValueError('controller source changed')
s=a.source.read_text();start=s.index(' void open(const Frame &f){');end=s.index('\n void input(',start);method=s[start:end]
pre=r'''
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
struct Session {uint32_t slot;uint64_t generation;std::thread worker;int result=0;bool workerDone=false;Session(Manager*,uint32_t s,uint64_t g,int):slot(s),generation(g){};};
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
int main(){Manager m;Frame f;f.request=17;f.epoch=42;f.slot=7;f.generation=19;f.value=1000;m.open(f);assert(m.replies.size()==1);auto reply=m.replies.back();assert(reply.kind==OPENED&&reply.slot==7&&reply.generation==19&&reply.request==17&&reply.epoch==42);assert(m.slots[7]&&m.slots[7]->slot==7&&m.generations[7]==19);m.slots[7]->worker.join();
auto reject=[&](Frame r,int code){auto started=m.started;auto watermark=m.generations;m.open(r);auto result=m.replies.back();assert(result.kind==REJECTED&&result.value==unsigned(code)&&result.slot==r.slot&&result.generation==r.generation&&result.request==r.request&&result.epoch==42);assert(m.started==started&&m.generations==watermark);};
reject(f,8);auto r=f;r.slot=16;reject(r,8);r=f;r.generation=0;reject(r,8);r=f;r.epoch=43;reject(r,5);m.slots[7].reset();reject(f,8);r=f;r.generation=18;reject(r,8);r=f;r.generation=20;m.closing=true;reject(r,4);m.closing=false;m.open(r);assert(m.replies.back().generation==20);m.slots[7]->worker.join();}
'''
mutants={'guest_chooses_own_tuple':('this,f.slot,f.generation,ms','this,0,1,ms'),'accepts_replayed_generation':('f.generation<=generations[f.slot]||',''),'reject_advances_watermark':('++stale;reject(8,"open_identity")','++stale;if(f.slot<16)generations[f.slot]=f.generation;reject(8,"open_identity")')}
rows=[]
for name,change in [('positive',None),*mutants.items()]:
 body=method
 if change:
  old,new=change
  if body.count(old)!=1:raise ValueError('mutation seam changed: '+name)
  body=body.replace(old,new)
 source=a.output/(name+'.cc');source.write_text(pre+body+post);binary=a.output/name
 subprocess.run(['c++','-std=c++17','-pthread',str(source),'-o',str(binary)],check=True)
 result=subprocess.run([str(binary)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (a.output/(name+'.txt')).write_text(result.stdout)
 if (result.returncode==0)!=(change is None):raise ValueError('controller identity mutation not detected: '+name)
 rows.append({'name':name,'exit':result.returncode})
(a.output/'result.json').write_text(json.dumps({'scope':'exact Manager::open with engine stubs; not an engine run','source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'method_sha256':hashlib.sha256(method.encode()).hexdigest(),'cases':rows},indent=2)+'\n');print('PASS exact open method and3 source mutation controls')
