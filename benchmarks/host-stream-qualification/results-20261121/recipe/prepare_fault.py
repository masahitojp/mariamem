"""Add a diagnostic read pause and a notification on the real writer's full branch."""
import json,sys
from pathlib import Path
w=Path(sys.argv[1]).resolve();t=w/'temp';rec=Path(__file__).resolve().parent
mapping=json.loads((t/'overlay.json').read_text())['Replace']
src=w/'worktree';pipe=src/'internal/guest/experiment_stream.go'
s=Path(mapping[str(pipe)]).read_text()
def replace(old,new):
    global s
    assert s.count(old)==1
    s=s.replace(old,new)
replace('type bytePipe struct {','type bytePipe struct {\n qualPaused bool\n qualFull chan struct{}')
replace('for p.used == 0 && !p.readerClosed','for (p.used == 0 || p.qualPaused) && !p.readerClosed')
replace('if p.used == len(p.buf) {','if p.used == len(p.buf) {\n if p.qualPaused && p.qualFull!=nil {close(p.qualFull);p.qualFull=nil}')
s+='''
// The writer signals only after exhausting capacity with bytes still to write.
// A real Close breaks the reader pause through the original closed-state checks.
func (proc *Process) QualPause(direction string) (<-chan struct{},func()) {
 var p *bytePipe
 if direction=="input" { p=proc.in.(byteWriter).p } else { p=proc.out.(byteReader).p }
 p.mu.Lock()
 ch:=make(chan struct{});p.qualFull=ch;p.qualPaused=true
 p.mu.Unlock()
 return ch,func(){p.mu.Lock();p.qualPaused=false;p.changed.Broadcast();p.mu.Unlock()}
}
func (p *Process) QualStopping() bool {p.mu.Lock();defer p.mu.Unlock();return p.stopping}
'''
diag=t/'fault-stream.go';diag.write_text(s);mapping[str(pipe)]=str(diag)
mapping[str(src/'internal/host/qual_full_test.go')]=str(rec/'fault_test.go.txt')
(t/'fault-overlay.json').write_text(json.dumps({'Replace':mapping}))
