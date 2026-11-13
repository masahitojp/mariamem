from pathlib import Path
import subprocess,json,os,sys,hashlib,time
w=Path(__file__).resolve().parents[1];t=w/'temp';s=t/'harness';b=s/'benchmarks/forkcompare';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));from git_identity import require_commit,verify_release_pin,ReleasePin;from experiment_disk import DiskGuard,run_guarded
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pins=json.loads((e/'plan.json').read_text())['products'];inputs={'products':pins,'binaries':{}}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,head);assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True);inputs['harness_source_commit']=head
for label,pin in pins.items():
 d=t/label;require_commit(d,pin['source_commit']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=d,text=True).strip()==pin['source_commit'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=d,text=True)
 if label=='pgmem':verify_release_pin(d,ReleasePin(**{k:pin[k] for k in ['release_tag','tag_object_sha','source_commit']}),**({'fetch_remote':'origin'} if label=='release' else {}))
 if label!='pgmem':
  guest=json.loads((d/'release/generated-go-inputs.json').read_text())['guest_sha256']
  if 'guest_sha256' in pin:assert guest==pin['guest_sha256']
  pin['guest_sha256']=guest
for name in ['gocache','modcache','gotmp','scratch','bin','modfiles']:(t/name).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG'))};env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version=='go version go1.27.4 darwin/arm64';inputs['toolchain']=version
for label in ['candidate','baseline']:
 mod=(b/'go.mod').read_text().replace('../../../candidate',str(t/label)).replace('../../../pgmem',str(t/'pgmem'));(t/'modfiles'/(label+'.mod')).write_text(mod);(t/'modfiles'/(label+'.sum')).write_bytes((b/'go.sum').read_bytes())
 models=subprocess.check_output(['go','list','-mod=readonly','-modfile='+str(t/'modfiles'/(label+'.mod')),'-m','-json','github.com/masahitojp/mariamem','github.com/shibukawa/pgmem'],cwd=b,env=env,text=True);dec=json.JSONDecoder();rest=models;items=[]
 while rest.strip():
  item,n=dec.raw_decode(rest.lstrip());items.append(item);rest=rest.lstrip()[n:]
 assert Path(items[0]['Replace']['Dir']).resolve()==(t/label).resolve() and Path(items[1]['Replace']['Dir']).resolve()==(t/'pgmem').resolve();(e/(label+'-module-binding.json')).write_text(models.replace(str(w),'<WORKSPACE>'))
guard=DiskGuard(w,12,12)
for label,package,mod in [('candidate','maria','candidate'),('baseline','maria','baseline'),('pgmem','postgres','candidate')]:
 binary=t/'bin'/label;start=time.monotonic()
 with (e/('build-'+label+'.log')).open('w') as log:
  code=run_guarded(['go','build','-p','1','-mod=readonly','-modfile='+str(t/'modfiles'/(mod+'.mod')),'-trimpath','-buildvcs=true','-o',str(binary),'./'+package],guard,cwd=b,env=env,output=log,timeout=1200)
 assert code==0,label
 info=subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True);assert 'vcs.revision='+head in info and 'vcs.modified=false' in info and 'CGO_ENABLED=0' in info
 raw=info.encode();published=info.replace(str(w),'<WORKSPACE>');inputs['binaries'][label]={'sha256':sha(binary),'bytes':binary.stat().st_size,'original_buildinfo_sha256':hashlib.sha256(raw).hexdigest(),'published_buildinfo_sha256':hashlib.sha256(published.encode()).hexdigest(),'buildinfo':published,'build_seconds':time.monotonic()-start}
 (e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(label,'BUILD PASS',flush=True)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True)
(e/'build-complete.json').write_text(json.dumps({'result':'PASS','harness_source_commit':head,'peak_owned_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free})+'\n')
