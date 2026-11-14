from pathlib import Path
import shutil,subprocess,os,json,hashlib
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';H=T/'lifecycle';shutil.copytree(T/'probe',H,dirs_exist_ok=True);p=H/'main.go';s=p.read_text();s=s.replace('ForkMS float64 `json:"fork_ms"`;','ForkMS float64 `json:"fork_ms"`;SQLMS float64 `json:"validation_sql_connection_ms"`;WaitMS float64 `json:"disconnect_wait_ms"`;CloseMS float64 `json:"close_ms"`;')
# The preserved source is compact; this anchor deliberately fails if it changes.
a='for _,c:=range cs{if e:=oracle(ctx,c.s,c.Index,negative);e!=nil{';b='for _,c:=range cs{at:=time.Now();oe:=oracle(ctx,c.s,c.Index,negative);c.SQLMS=float64(time.Since(at).Nanoseconds())/1e6;if e:=oe;e!=nil{';assert s.count(a)==1;s=s.replace(a,b)
a='e:=c.s.WaitDisconnected(ctx);err=errors.Join(err,e);e=c.s.Close();if e==nil';b='at=time.Now();e:=c.s.WaitDisconnected(ctx);c.WaitMS=float64(time.Since(at).Nanoseconds())/1e6;err=errors.Join(err,e);at=time.Now();e=c.s.Close();c.CloseMS=float64(time.Since(at).Nanoseconds())/1e6;if e==nil';assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'));bins={}
for variant,product in [('canonical',X/'worktree'),('spike',T/'native/product')]:
 mod=(H/'go.mod').read_text();mod=mod[:mod.index('replace github.com/masahitojp/mariamem')]+f'replace github.com/masahitojp/mariamem => {product}\n';(H/'go.mod').write_text(mod);cmd=['go','build','-p','1','-trimpath','-buildvcs=false']
 if variant=='canonical':cmd+=['-overlay',str(T/'canonical-overlay.json')]
 binary=T/(variant+'-lifecycle');cmd+=['-o',str(binary),'.'];subprocess.run(cmd,cwd=H,env=env,check=True);bins[variant]=hashlib.sha256(binary.read_bytes()).hexdigest()
(E/'lifecycle-binaries.json').write_text(json.dumps(bins,indent=2)+'\n');R=E/'lifecycle-runs';R.mkdir(exist_ok=True);records=[]
for p in (1,8):
 for rep in (-1,0,1,2):
  order=[('canonical','baseline','metadata'),('metadata','canonical','baseline'),('baseline','metadata','canonical')][max(0,rep)]
  for v in order:
   name=f'life-p{p}-{v}-r{rep}';runenv=env.copy()
   if v!='canonical':runenv['MARIAMEM_BP_ZERO_MODE_INTERNAL']=v
   else:runenv.pop('MARIAMEM_BP_ZERO_MODE_INTERNAL',None)
   binary=T/(('canonical' if v=='canonical' else 'spike')+'-lifecycle');out=R/(name+'.json')
   with (R/(name+'.log')).open('w') as log:subprocess.run([str(binary),'-parallel',str(p),'-waves',str(2 if rep<0 else 6),'-out',str(out)],env=runenv,stdout=log,stderr=subprocess.STDOUT,timeout=140,check=True)
   d=json.loads(out.read_text());assert d['success'] and all(c['oracle'] and c['closed'] and 'close_ms' in c and 'validation_sql_connection_ms' in c for c in d['children']);records.append({'p':p,'variant':v,'repetition':rep,'name':name});(E/'lifecycle-records.json').write_text(json.dumps(records,indent=2)+'\n');print(name,flush=True)
(E/'lifecycle-complete.json').write_text(json.dumps({'result':'PASS','processes':len(records),'purpose':'supplement missing Close timing; original 48-process primary series retained unchanged'},indent=2)+'\n')
