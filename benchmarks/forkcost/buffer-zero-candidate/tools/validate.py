from pathlib import Path
import os,subprocess,json,hashlib
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';P=T/'native/product'
env=dict(os.environ,GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'))
assert json.loads((T/'native/development.json').read_text())['result']=='UNQUALIFIED'
def run(name,cmd,cwd=X):
 with (E/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
 print('PASS',name,flush=True)
run('candidate-harness-build',['python3',str(E/'build-harness.py'),'candidate'])
for v in ('baseline','candidate'):
 for case in ('basic','large'):
  if v=='baseline' and case=='large' and (E/'baseline-large.json').exists():
   assert json.loads((E/'baseline-large.json').read_text())['success'];continue
  run(v+'-'+case,[str(T/(v+'-correct')),'-case',case,'-out',str(E/(v+'-'+case+'.json'))])
  d=json.loads((E/(v+'-'+case+'.json')).read_text());assert d['success'] and d['Started']==d['Closed']
 run(v+'-extra-build',['python3',str(E/'build-extra.py'),v])
 for name,args in [('fault',[]),('recovery-clean',['-crash=false']),('recovery-dirty',['-crash=true'])]:
  binary='fault' if name=='fault' else 'recovery'
  run(v+'-'+name,[str(T/(v+'-'+binary)),*args,'-out',str(E/(v+'-'+name+'.json'))])
  assert json.loads((E/(v+'-'+name+'.json')).read_text())['success']
run('candidate-crc',['go','test','-p','1','-vet=off','./internal/generatedgo/code/p4','-count=1','-v'],P)
run('candidate-owner',['go','test','-p','1','-vet=off','./internal/generatedgo','-run','TestGuestEnvironmentIsPerInstance|TestControlledGuestFirstWorkerTrap','-count=1','-v'],P)
(E/'validation-complete.json').write_text(json.dumps({'result':'PASS','candidate_product':str(P),'scope':'actual candidate large/compressed/resize/Fork/fault/recovery/CRC/owner; not both-platform adoption'},indent=2)+'\n')
