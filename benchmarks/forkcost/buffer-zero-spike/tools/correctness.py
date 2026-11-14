from pathlib import Path
import subprocess,os,json,time
E=Path(__file__).resolve().parent;T=E.parent/'temp';env=os.environ.copy();env.update(TMPDIR=str(T/'tmp'),GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1')
for mode,case in [('metadata','basic'),('poison','basic'),('poison','large')]:
 name=f'spike-{mode}-{case}';runenv=dict(env,MARIAMEM_BP_ZERO_MODE_INTERNAL=mode)
 with (E/(name+'.log')).open('w') as f:subprocess.run([str(T/'spike-correct'),'-case',case,'-out',str(E/(name+'.json'))],env=runenv,stdout=f,stderr=subprocess.STDOUT,timeout=950,check=True)
 d=json.loads((E/(name+'.json')).read_text());assert d['success'] and d['Started']==d['Closed']
 print('PASS',name,flush=True)
name='spike-poison-suite';runenv=dict(env,MARIAMEM_BP_ZERO_MODE_INTERNAL='poison',MODELCASE_TRACE=str(E/(name+'.json')))
with (E/(name+'.log')).open('w') as f:subprocess.run([str(T/'spike-suite'),'-test.parallel=8','-test.count=1','-test.timeout=120s'],env=runenv,stdout=f,stderr=subprocess.STDOUT,timeout=135,check=True)
print('PASS poison matched modelcase suite P8',flush=True)
(E/'correctness-primary-complete.json').write_text(json.dumps({'result':'PASS','cases':4},indent=2)+'\n')
