"""Replace the preliminary explicit rollback with observation of upstream cleanup."""
from pathlib import Path
import re,difflib,subprocess
r=Path('worktree');p=r/'guest/experimental.patch';text=p.read_text();name='sql/sql_class.cc';mark='--- a/'+name+'\n';a=text.index(mark);b=text.find('\n--- ',a+len(mark));b=len(text) if b<0 else b
patch=Path('temp/sql-class-reverse.patch');patch.write_text(text[a:b].rstrip()+'\n');original=Path('temp/sql_class-built.cc').resolve();base=Path('temp/sql_class-canonical.cc').resolve()
subprocess.run(['patch','--batch','--reverse','--fuzz=0','--output',str(base),str(original),'-i',str(patch.resolve())],check=True)
after=original.read_text();anchor='    trans_rollback(this);';assert after.count(anchor)==1
after=after.replace(anchor,'''  {
    bool rollback_error= trans_rollback(this);
#ifdef MARIAMEM_NATIVE_WIRE
    if (mariamem_native_wire)
    {
      extern void mariamem_spike_rollback_result(THD*, bool);
      mariamem_spike_rollback_result(this, rollback_error);
    }
#endif
  }''')
a=text.index(mark);b=text.find('\n--- ',a+len(mark));b=len(text) if b<0 else b;text=text[:a]+''.join(difflib.unified_diff(base.read_text().splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name)).rstrip('\n')+text[b:]
p=r/'benchmarks/spikes/issue65-native-control/session.inc';s=p.read_text().replace('#include "transaction.h"\n','');start=s.index('  int rollback_error=trans_rollback(thd);');end=s.index('  io->event(io->ctx,UNREGISTER_THD,',start);s=s[:start]+s[end:];pos=s.index('extern "C" int mariamem_spike_control_session');s=s[:pos]+'''// Observe upstream THD::cleanup's rollback in its original ordering.
void mariamem_spike_rollback_result(THD *thd,bool failed){
 auto *transport=spike_v(thd->net.vio);
 if(transport)transport->io->event(transport->ctx,CLEANUP_RESULT,thd,unsigned(failed));
}
'''+s[pos:];p.write_text(s)
p=r/'benchmarks/spikes/issue65-wasix-link/control.cc';c=p.read_text().replace('uint64_t started=0,joined=0,stale=0','uint64_t rollbackReports=0,started=0,joined=0,stale=0');c=c.replace('if(kind==CLEANUP_RESULT){std::lock_guard<std::mutex> l(gate);','if(kind==CLEANUP_RESULT){std::lock_guard<std::mutex> l(gate);++rollbackReports;');c=c.replace('if(poisoned||cleanupFailed||injectFailure==2){','if(rollbackReports!=started)cleanupFailed=true;\n  if(poisoned||cleanupFailed||injectFailure==2){');c=c.replace('"{\\"fenced\\":','"{\\"rollback_reports\\":"+std::to_string(rollbackReports)+",\\"fenced\\":');p.write_text(c)
for name,new in [('libmysqld/mariamem_wire_probe.inc',s),('wasm/issue65_control.cc',c)]:
 mark='--- /dev/null\n+++ b/'+name+'\n';a=text.index(mark);b=text.find('\n--- ',a+len(mark));b=len(text) if b<0 else b;text=text[:a]+''.join(difflib.unified_diff([],new.splitlines(True),fromfile='/dev/null',tofile='b/'+name)).rstrip('\n')+text[b:]
(r/'guest/experimental.patch').write_text(text.rstrip()+'\n')
print('Retained upstream cleanup order; actual rollback result observed once per native session')
