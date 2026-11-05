from pathlib import Path
import difflib,re
r=Path('worktree');sp=r/'benchmarks/spikes/issue65-wasix-link';c=sp/'control.cc';s=c.read_text();old=s
s=s.replace('EXPIRE=10,','EXPIRE=10,TRY_CAPTURE=11,CAPTURE_STOP=12,INJECT=13,').replace('DONE=111 };','DONE=111,CAPTURE_FENCED=112,CAPTURE_STOP_ACCEPTED=113,CAPTURE_STOPPED=114 };')
s=s.replace('std::string cause;uint64_t epoch=0;','std::string cause;uint64_t epoch=0,captureID=0;bool cleanupFailed=false;unsigned injectFailure=0;')
s=s.replace('"{\\"max_sessions\\":16,','"{\\"lifecycle_profile\\":1,\\"max_sessions\\":16,')
s=s.replace('  if(kind==REGISTER_THD)', '  if(kind==CLEANUP_RESULT){std::lock_guard<std::mutex> l(gate);if(status||injectFailure==1)cleanupFailed=true;return 0;}\n  if(kind==REGISTER_THD)',1)
s=s.replace('auto s=slots[raw->slot];bool inputEOF;', 'auto s=slots[raw->slot];if(fenced||poisoned||closing)return 1;bool inputEOF;',1)
s=s.replace('if(poisoned||closing)return;std::lock_guard<std::mutex> q(s->io);','if(fenced||poisoned||closing)return;std::lock_guard<std::mutex> q(s->io);',1)
s=s.replace('if(!s||s->phase==RETIRING)return;','if(!s||s->phase==RETIRING||(fenced&&captureID))return;',1)
a=s.index(' void quiesce(')
s=s[:a]+''' void tryCapture(const Frame &f){std::lock_guard<std::mutex> l(gate);
  if(f.epoch!=epoch||!f.value||f.generation>1){emit(frame(REJECTED,f.request,{},5,"capture_identity"));return;}
  if(captureID==f.value&&fenced&&!poisoned&&!closing){emit(frame(CAPTURE_FENCED,f.request,{},captureID,"fenced"));return;}
  if(fenced||closing||poisoned){emit(frame(REJECTED,f.request,{},4,"closing"));return;}
  for(auto &s:slots)if(s&&s->phase!=IDLE){emit(frame(REJECTED,f.request,{},1,"busy"));return;}
  if(!f.generation)for(auto &s:slots)if(s&&(s->status&1)){emit(frame(REJECTED,f.request,{},2,"transaction_active"));return;}
  captureID=f.value;fenced=true;emit(frame(CAPTURE_FENCED,f.request,{},captureID,"fenced"));
 }
 bool captureStop(const Frame &f){std::lock_guard<std::mutex> l(gate);
  if(f.epoch!=epoch||!captureID||captureID!=f.value||!fenced||poisoned||closing){emit(frame(REJECTED,f.request,{},5,"capture_stop_identity"));return false;}
  closing=true;emit(frame(CAPTURE_STOP_ACCEPTED,f.request,{},captureID,"expected_owner_stop"));return true;
 }
 bool captureComplete(const Frame &f){std::lock_guard<std::mutex> l(gate);
  if(poisoned||cleanupFailed||injectFailure==2){emit(frame(POISON,0,{},0,poisoned?cause:(cleanupFailed?"cleanup_failed":"engine_shutdown_injected")));return false;}
  need(started==joined,"capture native join");emit(frame(CAPTURE_STOPPED,f.request,{},captureID,statsUnlocked()));return true;
 }
''' +s[a:]
# stats called while gate held at completion; centralize unlocked formatter.
s=s.replace('std::string stats(){std::lock_guard<std::mutex> l(gate);std::string s=', 'std::string stats(){std::lock_guard<std::mutex> l(gate);return statsUnlocked();}\n std::string statsUnlocked(){std::string s=')
s=s.replace('  if(f.kind==OPEN)', '  if(f.kind==TRY_CAPTURE){tryCapture(f);return;}\n  if(f.kind==INJECT){std::lock_guard<std::mutex> l(gate);injectFailure=unsigned(f.value);emit(frame(REPLY,f.request,{},f.value,"failure_injection"));return;}\n  if(f.kind==OPEN)',1)
a=s.index('int main(){');s=s[:a]+'''int main(){
 need(!issue65_bootstrap(),"product fresh/restore bootstrap");
 Manager manager;manager.start();Frame f,stopRequest;bool gotStop=false,capture=false;
 while(receive(f)){
  if(f.kind==STOP){gotStop=true;break;}
  if(f.kind==CAPTURE_STOP){if(manager.captureStop(f)){gotStop=true;capture=true;stopRequest=f;break;}continue;}
  manager.dispatch(f);
 }
 manager.shutdown();issue65_shutdown();
 bool ok=gotStop;
 if(capture)ok=manager.captureComplete(stopRequest);
 manager.emit(manager.frame(DONE,0,{},0,manager.stats()));manager.stopWriter();
 fprintf(stderr,"NATIVE_STOP mode=%s started=%llu joined=%llu cleanup_failed=%u\\n",capture?"capture":"ordinary",(unsigned long long)manager.started,(unsigned long long)manager.joined,unsigned(manager.cleanupFailed));
 return ok?0:21;
}
''';c.write_text(s)
p=r/'benchmarks/spikes/issue65-native-control/session.inc';session=p.read_text().replace('#include "sql_parse.h"','#include "sql_parse.h"\n#include "transaction.h"');session=session.replace('  io->event(io->ctx,UNREGISTER_THD,','  int rollback_error=trans_rollback(thd);\n  if(rollback_error)result=19;\n  io->event(io->ctx,CLEANUP_RESULT,thd,unsigned(rollback_error!=0));\n  io->event(io->ctx,UNREGISTER_THD,',1);p.write_text(session)
p=r/'benchmarks/spikes/issue65-native-control/control_abi.h';abi=p.read_text().replace('UNREGISTER_THD=7','UNREGISTER_THD=7, CLEANUP_RESULT=8');p.write_text(abi)
p=sp/'bootstrap.inc';bootstrap=p.read_text();prior=bootstrap;bootstrap=bootstrap.replace('/* Fresh-only native-wire experiment. Keep the real product bootstrap first. */','/* Experimental fresh/restore native-wire entry; no fixture SQL on shutdown. */').replace('  if (routine_boot_mode(getenv("MARIAMEM_BOOT_MODE"), 0) != 0) return 11;','  int restore=routine_boot_mode(getenv("MARIAMEM_BOOT_MODE"), 0);\n  if (restore < 0) return 11;').replace('routine_bootstrap(g_mysql, 0)','routine_bootstrap(g_mysql, restore)');p.write_text(bootstrap)
p=r/'guest/experimental.patch';text=p.read_text()
for name,new in [('libmysqld/mariamem_control_abi.h',abi),('libmysqld/mariamem_wire_probe.inc',session),('wasm/issue65_control.cc',s)]:
 mark='--- /dev/null\n+++ b/'+name+'\n';a=text.index(mark);b=text.find('\n--- ',a+len(mark));b=len(text) if b<0 else b
 text=text[:a]+''.join(difflib.unified_diff([],new.splitlines(True),fromfile='/dev/null',tofile='b/'+name)).rstrip('\n')+text[b:]
old=''.join('+'+x for x in prior.splitlines(True));new=''.join('+'+x for x in bootstrap.splitlines(True));assert text.count(old)==1;text=text.replace(old,new)
lines=text.splitlines(True);out=[];delta=0;i=0
while i<len(lines):
 line=lines[i]
 if line.startswith('--- '):delta=0
 if line.startswith('@@ '):
  m=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)',line);assert m;j=i+1
  while j<len(lines) and not lines[j].startswith(('@@ ','--- ')):j+=1
  body=lines[i+1:j];oc=sum(x[:1] in (' ','-') for x in body);nc=sum(x[:1] in (' ','+') for x in body);os=int(m[1]);ns=1 if os==0 else os+delta
  out.append(f'@@ -{os},{oc} +{ns},{nc} @@'+m[5]+'\n');out.extend(body);delta+=nc-oc;i=j;continue
 out.append(line);i+=1
p.write_text(''.join(out).rstrip()+'\n');print('Prepared coherent capture guest patch')
