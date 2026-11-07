from pathlib import Path
import subprocess,os,json,argparse,tempfile
parser=argparse.ArgumentParser(description="Check extracted core failure oracles with Go source overlays; never edit the checkout.")
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
evidence=args.evidence.resolve();evidence.mkdir(parents=True,exist_ok=True)
base=Path(__file__).resolve().parents[3]
env=os.environ.copy()
mutants=[
('early_done','backend.go','return r.done','return r.executionDone','TestBackendDoneWaitsForHostRelayAfterExecution'),
('drop_startup_owner','backend.go','return disposal.Retain(cause, err, r.disposer)','return errors.Join(cause, err)','TestBackendCanceledStartupOwnsLateParentRemoval'),
('fixed_five_seconds','backend.go','limit: limit,','limit: uint64(5*time.Second) + limit - limit,','TestBackendOpaqueRelayAndTypedTimeout'),
('forgive_rejection','capture.go','if reply.kind == kindRejected &&','if false && reply.kind == kindRejected &&','TestBackendCaptureFenceRejectionAndOwnership'),
('overwrite_first_cause','backend.go','if r.failure == nil {\n\t\tr.failure = e\n\t\tclose(r.failed)\n\t}', 'if r.failure == nil {close(r.failed)};r.failure=e','TestBackendPendingOpenCaptureAndFirstCause'),
]
result=[]
for name,file,old,new,test in mutants:
 p=base/'internal/nativewire'/file;source=p.read_text()
 assert old in source,(name,old)
 with tempfile.TemporaryDirectory(prefix='native-core-control-') as directory:
  temporary=Path(directory)
  replacement=temporary/file
  replacement.write_text(source.replace(old,new,1))
  overlay=temporary/'overlay.json'
  overlay.write_text(json.dumps({'Replace':{str(p):str(replacement)}}))
  r=subprocess.run(['go','test','-overlay='+str(overlay),'./internal/nativewire','-run','^'+test+'$','-count=1','-timeout=20s'],cwd=base,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=40)
  (evidence/f'mutant-{name}.txt').write_text(r.stdout)
  detected=r.returncode!=0 and '--- FAIL: '+test in r.stdout and '[build failed]' not in r.stdout
  result.append({'name':name,'test':test,'exit':r.returncode,'detected':detected})
 if not detected:raise SystemExit('mutation not detected '+name+'\n'+r.stdout)
(evidence/'mutations.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
