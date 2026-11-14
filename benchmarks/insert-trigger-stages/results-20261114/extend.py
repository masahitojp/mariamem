from pathlib import Path
import json
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';S=W/'worktree'
p=T/'overlay-internal_generatedgo_code_base_experiment_stages.go';s=p.read_text().replace('WriteNS int64; Writes int','TriggerNS int64; TriggerCalls int; TriggerDepth int; WriteNS int64; Writes int');s+='''
func ExperimentTriggerBegin(m *Module)int64{r:=m.ExperimentCurrent;if r==nil{return -1};r.TriggerCalls++;r.TriggerDepth++;if r.TriggerDepth==1{return ExperimentNow()};return -1}
func ExperimentTriggerEnd(m *Module,start int64){r:=m.ExperimentCurrent;if r==nil{return};r.TriggerDepth--;if start>=0{r.TriggerNS+=ExperimentNow()-start}}
''';p.write_text(s)
p=S/'internal/generatedgo/code/p4/p4_pure.go';s=p.read_text();key='func Fn15540(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32, l6 int32) int32 {';assert s.count(key)==1;s=s.replace(key,key+'\n experimentStart:=base.ExperimentTriggerBegin(m)\n defer base.ExperimentTriggerEnd(m,experimentStart)');out=T/'trigger-p4.go';out.write_text(s);o=json.loads((E/'overlay.json').read_text());o['Replace'][str(p)]=str(out);(E/'overlay.json').write_text(json.dumps(o,indent=2))
