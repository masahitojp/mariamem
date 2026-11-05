from pathlib import Path
import difflib,re
repo=Path('worktree');p=repo/'benchmarks/spikes/issue65-wasix-link/control.cc';s=p.read_text()
s=s.replace('bool closed=false,armed=', 'bool inputEOF=false,closed=false,armed=').replace('unsigned status=2;', 'unsigned nativeCommand=0,status=2;')
s=s.replace('s->phase=RECEIVING;++s->command;', 's->phase=RECEIVING;s->nativeCommand=0;++s->command;')
old='s->phase=FLUSHING;state(s);}'
new='''bool inputEOF;{std::lock_guard<std::mutex> q(s->io);inputEOF=s->inputEOF;}
   if(retire&&inputEOF&&s->phase==RECEIVING&&s->nativeCommand!=COM_QUIT){poisonLocked("unexpected_peer_eof");return 1;}
   if(retire&&inputEOF){s->phase=RETIRING;s->deadline=Clock::time_point::max();state(s);return 0;}
   s->phase=FLUSHING;state(s);}''';assert old in s;s=s.replace(old,new,1)
old='if(kind==EXECUTE_START){std::lock_guard<std::mutex> l(gate);raw->phase=EXECUTING;++raw->executions;state(slots[raw->slot]);return poisoned||closing;}'
new='''if(kind==EXECUTE_START){std::lock_guard<std::mutex> l(gate);auto s=slots[raw->slot];bool inputEOF;{std::lock_guard<std::mutex> q(raw->io);inputEOF=raw->inputEOF;}raw->nativeCommand=status;if(inputEOF&&status!=COM_QUIT){poisonLocked("unexpected_peer_eof");return 1;}raw->phase=EXECUTING;++raw->executions;state(s);return poisoned||closing;}''';assert old in s;s=s.replace(old,new)
s=s.replace('return s->closed||!s->input.empty();});if(s->closed)return size_t(-1);', 'return s->closed||s->inputEOF||!s->input.empty();});if(s->closed)return size_t(-1);if(s->input.empty()&&s->inputEOF)return 0;',1)
s=s.replace('(kind==0?!s->input.empty():', '(kind==0?(s->inputEOF||!s->input.empty()):')
a=s.index(' void peerEOF(');b=s.index('\n void quiesce',a)
s=s[:a]+''' void peerEOF(const Frame &f){std::lock_guard<std::mutex> l(gate);auto s=match(f);if(!s||s->phase==RETIRING)return;
  {std::lock_guard<std::mutex> q(s->io);s->inputEOF=true;s->changed.notify_all();}
  if(f.value){if(s->command&&s->phase!=IDLE){poisonLocked("peer_output_error");return;}s->phase=RETIRING;s->deadline=Clock::time_point::max();s->closeIO(ECANCELED);scheduleKill(s);state(s);return;}
  if(!fenced&&!closing&&!poisoned&&s->phase==EXECUTING&&s->nativeCommand!=COM_QUIT)poisonLocked("unexpected_peer_eof");
 }
'''.rstrip()+s[b:];p.write_text(s)
p=repo/'benchmarks/spikes/issue65-native-control/session.inc';entry=p.read_text().replace('void mariamem_spike_dispatch_start(THD *thd) {','bool mariamem_spike_dispatch_start(THD *thd, enum enum_server_command command) {').replace('if(!thd->mariamem_native_wire)return;','if(!thd->mariamem_native_wire)return false;').replace('s->io->event(s->ctx,EXECUTE_START,thd,thd->server_status);','return s->io->event(s->ctx,EXECUTE_START,thd,unsigned(command)) != 0;');p.write_text(entry)
p=repo/'guest/experimental.patch';text=p.read_text()
for name,new in [('libmysqld/mariamem_wire_probe.inc',entry),('wasm/issue65_control.cc',s)]:
 mark='--- /dev/null\n+++ b/'+name+'\n';a=text.index(mark);b=text.find('\n--- ',a+len(mark));b=len(text) if b<0 else b
 delta=''.join(difflib.unified_diff([],new.splitlines(True),fromfile='/dev/null',tofile='b/'+name)).rstrip('\n');text=text[:a]+delta+text[b:]
text=text.replace('+    extern void mariamem_spike_dispatch_start(THD*);','+    extern bool mariamem_spike_dispatch_start(THD*, enum enum_server_command);').replace('+    mariamem_spike_dispatch_start(thd);','+    if (mariamem_spike_dispatch_start(thd,command)) return DISPATCH_COMMAND_CLOSE_CONNECTION;')
# Recompute exact hunk metadata after additions; no source-context matching is weakened.
lines=text.splitlines(True);out=[];delta=0;i=0
while i<len(lines):
 line=lines[i]
 if line.startswith('--- '):delta=0
 if line.startswith('@@ '):
  match=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)',line);assert match
  j=i+1
  while j<len(lines) and not lines[j].startswith(('@@ ','--- ')):j+=1
  body=lines[i+1:j];old_count=sum(x[:1] in (' ','-') for x in body);new_count=sum(x[:1] in (' ','+') for x in body);assert old_count==int(match[2] or 1)
  old_start=int(match[1]);new_start=1 if old_start==0 else old_start+delta
  out.append(f'@@ -{old_start},{old_count} +{new_start},{new_count} @@'+match[5]+'\n');out.extend(body);delta+=new_count-old_count;i=j;continue
 out.append(line);i+=1
p.write_text(''.join(out).rstrip()+'\n')
