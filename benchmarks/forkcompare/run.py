"""Bounded same-host fork readiness and unchanged/transport-only suite comparison."""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, time
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence'
sys.path.insert(0,str(C/'scripts'))
from git_identity import require_commit,inspect_ref,verify_release_pin,ReleasePin
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','pilot','matrix'],required=True);a=p.parse_args()
pins=json.loads((E/'source-pins.json').read_text())
for label in ['mariamem','pgmem']:
 root=T/('product' if label=='mariamem' else 'pgmem');pin=pins[label]
 verify_release_pin(root,ReleasePin(pin['release_tag'],pin['tag_object_sha'],pin['source_commit']));require_commit(root,pin['source_commit'])
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
require_commit(C,subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip())
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C,text=True),'commit harness before building'
def save(n,d):
 q=E/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(d,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','MODELCASE_'))}
env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'))
for n in ['go-cache','go-mod','go-tmp','scratch','bin']:(T/n).mkdir(exist_ok=True)
go=shutil.which('go');assert subprocess.check_output([go,'version'],env=env,text=True).startswith('go version go1.27.3 ')
def command(cmd,cwd,log,timeout=900,ce=env):
 print('RUN',log,flush=True)
 q=E/log;q.parent.mkdir(parents=True,exist_ok=True)
 with q.open('w') as f:return subprocess.run(list(map(str,cmd)),cwd=cwd,env=ce,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
macro_maria=T/'maria-modelcase';macro_tcp=T/'pgmem-modelcase-tcp'
if a.phase=='build':
 info=dict(sources=pins,harness_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip(),go=subprocess.check_output([go,'version'],env=env,text=True).strip(),host=dict(cpu='Apple M1',ram_bytes=17179869184,macos=platform.mac_ver()[0],machine=platform.machine()),compile_timed=False,gomaxprocs=8,cgo_enabled='0',binaries={},scope='Same host; no product/engine changes; fork/physical-connect/SELECT1 boundaries; macro workloads remain distinct')
 for label in ['maria','postgres']:
  out=T/'bin'/('probe-'+label)
  assert command([go,'build','-mod=readonly','-p','1','-trimpath','-buildvcs=true','-o',out,'./'+label],C/'benchmarks/forkcompare','build-'+label+'.txt')==0
 macro_maria.mkdir(exist_ok=True)
 source='73a0e091ba15d0f007a2f5bd2f040040002f855d'
 for name in ['app.go','suite_test.go','go.mod','go.sum']:
  (macro_maria/name).write_bytes(subprocess.check_output(['git','show',source+':benchmarks/modelcase/'+name],cwd=C))
 assert command([go,'mod','edit','-replace=github.com/masahitojp/mariamem='+str(T/'product')],macro_maria,'macro-maria-replace.txt')==0
 assert command([go,'test','-c','-mod=readonly','-p','1','-vet=off','-trimpath','-o',T/'bin/maria-modelcase','.'],macro_maria,'build-maria-modelcase.txt')==0
 up=T/'pgmem/bench/modelcase'
 assert command([go,'test','-c','-mod=readonly','-p','1','-vet=off','-trimpath','-o',T/'bin/pgmem-modelcase','./store'],up,'build-pgmem-modelcase.txt')==0
 shutil.copytree(up,macro_tcp,ignore=shutil.ignore_patterns('results','bin'),dirs_exist_ok=True)
 f=macro_tcp/'store/fixture_test.go';before=f.read_bytes();assert before.count(b'cfg.DialFunc = s.Dial')==1
 after=before.replace(b'cfg.DialFunc = s.Dial',b'// TCP experiment: retain the default pgx network dialer.')
 f.write_bytes(after);info['macro_tcp_delta']=dict(file='store/fixture_test.go',before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),change='Only remove cfg.DialFunc=s.Dial in a disposable benchmark copy; root pgmem source unchanged.')
 assert command([go,'mod','edit','-replace=github.com/shibukawa/pgmem='+str(T/'pgmem')],macro_tcp,'macro-tcp-replace.txt')==0
 assert command([go,'test','-c','-mod=readonly','-p','1','-vet=off','-trimpath','-o',T/'bin/pgmem-modelcase-tcp','./store'],macro_tcp,'build-pgmem-modelcase-tcp.txt')==0
 for b in sorted((T/'bin').iterdir()):info['binaries'][b.name]=dict(sha256=digest(b),bytes=b.stat().st_size,build_info=subprocess.check_output([go,'version','-m',b],env=env,text=True))
 info['micro_source_sha256']={str(f.relative_to(C/'benchmarks/forkcompare')):digest(f) for f in (C/'benchmarks/forkcompare').rglob('*') if f.is_file()}
 info['macro_maria_source_commit']=source
 info['macro_source_sha256']={label:{str(f.relative_to(root)):digest(f) for f in root.rglob('*') if f.is_file() and f.suffix in ['.go','.mod','.sum','.sql']} for label,root in [('maria',macro_maria),('pgmem-original',up),('pgmem-tcp',macro_tcp)]}
 save('inputs.json',info);print('BUILD COMPLETE',flush=True);sys.exit(0)
info=json.loads((E/'inputs.json').read_text())
for name,b in info['binaries'].items():assert digest(T/'bin'/name)==b['sha256']
records=[]
def micro(label,route,parallel,rep,warmup=False,negative=False,count=20):
 name=f'micro/{label}-{route}-p{parallel}-r{rep}'+('-negative' if negative else '')
 out=E/(name+'.json');scratch=T/'scratch'/name;scratch.mkdir(parents=True,exist_ok=True)
 ce=dict(env,TMPDIR=str(scratch))
 cmd=[T/'bin'/('probe-maria' if label=='mariamem' else 'probe-postgres'),'-route',route,'-parallel',parallel,'-count',count,'-out',out]
 if negative:cmd+=['-corrupt-seed']
 at=time.monotonic();code=command(cmd,C,name+'.txt',ce=ce,timeout=240);wall=(time.monotonic()-at)*1000
 d=json.loads(out.read_text());assert d['cleanup_complete'] and not any(scratch.iterdir()),name
 if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error'],name
 else:
  assert code==0 and d['success'] and len(d['samples'])==count and d['root_closed_before_forks'],name
  assert all(s['oracle'] and s['cleanup_complete'] and not s.get('error') for s in d['samples']),name
 row=dict(kind='micro',backend=label,route=route,parallelism=parallel,repetition=rep,warmup=warmup,negative=negative,wall_ms=wall,report=name+'.json',returncode=code,count=len(d['samples']),scratch_empty=True)
 records.append(row);save('pilot-records.json' if a.phase=='pilot' else 'records.json',records)
 print('PASS',name,round(wall,1),'ms',flush=True)
def macro(label,route,parallel,rep,warmup=False):
 name=f'macro/{label}-{route}-p{parallel}-r{rep}';out=E/(name+'.json');scratch=T/'scratch'/name;scratch.mkdir(parents=True,exist_ok=True)
 binary='maria-modelcase' if label=='mariamem' else 'pgmem-modelcase'+('-tcp' if route=='tcp' else '')
 ce=dict(env,TMPDIR=str(scratch));cmd=[T/'bin'/binary,'-test.parallel',parallel,'-test.timeout','240s','-test.v']
 if label=='mariamem':ce.update(MODELCASE_MODE='mariamem-shared-read',MODELCASE_OUTPUT=str(out));cmd+=['-test.run','^TestModelcase$']
 else:ce['MODELCASE_TRACE']=str(out)
 at=time.monotonic();code=command(cmd,C,name+'.txt',ce=ce,timeout=255);wall=(time.monotonic()-at)*1000
 assert code==0,name
 text=(E/(name+'.txt')).read_text();leaf=[l for l in text.splitlines() if l.lstrip().startswith('--- PASS: ') and '/' in l];assert len(leaf)==70,(name,len(leaf))
 d=json.loads(out.read_text())
 if label=='mariamem':assert d['completed'] and d['cleanup_complete'] and len(d['cases'])==70 and all(d['cases'].values())
 assert not any(scratch.iterdir()),name
 row=dict(kind='macro',backend=label,route=route,parallelism=parallel,repetition=rep,warmup=warmup,negative=False,wall_ms=wall,report=name+'.json',returncode=code,count=70,scratch_empty=True)
 records.append(row);save('pilot-records.json' if a.phase=='pilot' else 'records.json',records)
 print('PASS',name,round(wall,1),'ms',flush=True)
cells=[('mariamem','tcp'),('pgmem','pipe'),('pgmem','tcp')]
if a.phase=='pilot':
 for label,route in cells:
  micro(label,route,1,0,count=2);micro(label,route,1,0,negative=True,count=1)
  macro(label,route,8,0)
 save('pilot-result.json',dict(result='PASS',micro_positive=3,micro_negative=3,macro_positive=3))
else:
 assert json.loads((E/'pilot-result.json').read_text())['result']=='PASS'
 for kind,fn in [('micro',micro),('macro',macro)]:
  for parallel in [1,8]:
   for label,route in cells:fn(label,route,parallel,-1,warmup=True)
   for rep in range(5):
    order=cells[rep%3:]+cells[:rep%3]
    for label,route in order:fn(label,route,parallel,rep)
 save('completion.json',dict(result='PASS',measured_processes=60,warmup_processes=12,micro_measured_children=600,macro_measured_cases=2100,scope='One local M1, three routes, parallel1/8; no performance gate, no heavy CI'))
