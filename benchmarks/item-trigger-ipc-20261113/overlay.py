from pathlib import Path
import json
r=Path(__file__).resolve().parents[1];src=r/'worktree/internal/guest/linked.go';s=src.read_text();old='execution := generatedgo.StartInstance(childIn, childOut, logs, transfer, restore, timing.Enabled(ctx), func(err error) { failed <- err }, capture)';assert s.count(old)==1
s=s.replace(old,'''var guestIn io.Reader=childIn
 var guestOut io.Writer=childOut
 var hostIn io.WriteCloser=in
 var hostOut io.ReadCloser=out
 var ledger *experimentLedger
 if experimentEnabled{
  label,_:=ctx.Value("mariamem_benchmark_label").(string)
  ledger=newExperimentLedger(label)
  guestIn=&experimentReader{Reader:childIn,s:ledger.stream("guest_read",true)}
  guestOut=&experimentWriter{Writer:childOut,s:ledger.stream("guest_write",false)}
  hostIn=&experimentWriteCloser{WriteCloser:in,s:ledger.stream("host_write",true)}
  hostOut=&experimentReadCloser{ReadCloser:out,s:ledger.stream("host_read",false)}
 }
 execution:=generatedgo.StartInstance(guestIn,guestOut,logs,transfer,restore,timing.Enabled(ctx),func(err error){failed<-err},capture)
 if ledger!=nil{originalDone:=execution;observedDone:=make(chan error,1);go func(){err:=<-originalDone;ledger.mu.Lock();ledger.Joined=true;if err!=nil{ledger.ExitError=err.Error()};ledger.mu.Unlock();observedDone<-err}();execution=observedDone}
''').replace('ConnectWithFailure(ctx, in, out, execution,','ConnectWithFailure(ctx, hostIn, hostOut, execution,')
a=r/'temp/linked_overlay.go';a.write_text(s)
b=r/'temp/experiment_probe.go';b.write_bytes((r/'evidence/probe.go.txt').read_bytes())
c=r/'temp/public_probe.go';c.write_text('''package mariamem
import "github.com/masahitojp/mariamem/internal/guest"
func ExperimentNowNS()int64{return guest.ExperimentNowNS()}
func ExperimentRecordClient(label,stage string,index int,start,end int64){guest.ExperimentRecordClient(label,stage,index,start,end)}
func ExperimentDump(path string)error{return guest.ExperimentDump(path)}
''')
(r/'evidence/overlay.json').write_text(json.dumps({'Replace':{str(src):str(a),str(src.parent/'experiment_probe.go'):str(b),str(r/'worktree/experiment_probe.go'):str(c)}},indent=2))
