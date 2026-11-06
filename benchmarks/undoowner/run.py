from pathlib import Path
import os,sys,json,subprocess,hashlib
w=Path(__file__).resolve().parents[1];t=w/'temp';s=w/'worktree';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));from experiment_disk import DiskGuard,run_guarded
inp=json.loads((e/'inputs.json').read_text());assert hashlib.sha256((t/'probe').read_bytes()).hexdigest()==inp['binary_sha256'];assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inp['harness_source_commit'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOGC','GOMEMLIMIT','GOFLAGS','DEFAULT_SETTINGS_','UPDATE_WAIT_','UPDATE_NOTIFY_','FORKSTAGES_'))};env.update(GOMAXPROCS='8',GOGC='100',GOTOOLCHAIN='local',DEFAULT_SETTINGS_VARIANT='both-off');guard=DiskGuard(w,12,6);records=[]
def run(name,p,count,artificial=False,negative=False,preflight=False):
 scratch=t/name;scratch.mkdir();tmp=scratch/'tmp';tmp.mkdir();stacks=scratch/'stacks';stacks.mkdir();out=e/(name+'.json');trace=scratch/'notify';trace.mkdir();v=dict(env,TMPDIR=str(tmp),UPDATE_WAIT_DIR=str(stacks),UPDATE_NOTIFY_DIR=str(trace))
 if artificial:v['UPDATE_WAIT_ARTIFICIAL']='1'
 if preflight:v['DEFAULT_SETTINGS_PREFLIGHT']='1'
 cmd=[str(t/'probe'),'-route','pipe','-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 with (e/(name+'.log')).open('w') as log:code=run_guarded(cmd,guard,cwd=s/'benchmarks/forkcompare',env=v,output=log,timeout=120)
 d=json.loads(out.read_text());assert d['cleanup_complete'] and d['root_closed_before_forks'] and not any(tmp.iterdir());assert d['parallel']==p and d['route']=='pipe' and d['gomaxprocs']==8
 if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error'];assert not list(stacks.glob('*'))
 else:assert code==0 and d['success'] and len(d['samples'])==count and {x['index'] for x in d['samples']}==set(range(count)) and all(x['oracle'] and x['cleanup_complete'] for x in d['samples'])
 if preflight:
  for c in [d['config']]+[x['config'] for x in d['samples']]:assert c['innodb_buffer_pool_load_at_startup']=='OFF' and c['innodb_read_io_threads']=='1' and c['innodb_write_io_threads']=='2' and c['innodb_purge_threads']=='1' and c['innodb_buffer_pool_size']=='16777216' and c['innodb_buffer_pool_dump_at_shutdown']=='OFF' and c['innodb_flush_log_at_trx_commit']=='1' and c['innodb_flush_method']=='O_DIRECT'
 else:assert not d.get('config')
 captures=[]
 for meta in stacks.glob('*.json'):
  m=json.loads(meta.read_text());textfile=meta.with_suffix('.txt');data=textfile.read_text();m['whole_profile_inside_exec']=m['exec_enter_ms']>0 and m['snapshot_begin_ms']>=m['exec_enter_ms'] and m['snapshot_end_ms']<=m['exec_return_ms'];assert m['whole_profile_inside_exec']==m['snapshot_inside_actual_exec'];m['usable']=m['whole_profile_inside_exec'] and m['labels_bound'] and not m['truncated'];assert m['artificial']==artificial;assert len(textfile.read_bytes())==m['bytes'] and m['bytes']<=2<<20
  (e/(name+'-'+meta.name)).write_text(json.dumps(m,indent=2)+'\n');(e/(name+'-'+textfile.name)).write_text(data);m['meta']=name+'-'+meta.name;m['text']=name+'-'+textfile.name;captures.append(m)
 notify=[]
 for path in trace.glob('child-*.json'):
  dd=json.loads(path.read_text());assert not dd['truncated'];assert dd['child'] in {x['index'] for x in d['samples']};dest=name+'-notify-'+path.name;(e/dest).write_bytes(path.read_bytes());notify.append(dest)
 if not negative:assert len(notify)==count
 assert len(captures)<=1
 if artificial:assert d['samples'][0]['update_ms']>=200
 if artificial:assert len(captures)==1 and captures[0]['usable'] and captures[0]['artificial']
 rec={'name':name,'parallel':p,'count':count,'artificial':artificial,'negative':negative,'preflight':preflight,'report':out.name,'exit_code':code,'captures':captures,'notify_reports':notify,'slow_update_children':[x['index'] for x in d['samples'] if x['update_ms']>100]};records.append(rec);(e/'records.json').write_text(json.dumps(records,indent=2)+'\n');print(name,'PASS','updates>100',rec['slow_update_children'],'usable',[m['child'] for m in captures if m['usable']],flush=True);return rec
# Dedicated controls precede the finite natural collection, not pooled with it.
run('effective',8,8,preflight=True)
run('sql-sleep-control',1,1,artificial=True)
run('wrong-seed',1,1,negative=True)
for i,p in enumerate([8,4,8]):run('natural-'+str(i),p,48)
valid=[c for r in records if not r['preflight'] and not r['negative'] for c in r['captures'] if c['usable'] and not c['artificial']]
slow=sum(len(r['slow_update_children']) for r in records if r['name'].startswith('natural-'))
result='NATURAL_UPDATE_CAPTURED' if valid else 'SLOW_UPDATE_WITHOUT_USABLE_CAPTURE' if slow else 'NOT_REPRODUCED'
(e/'complete.json').write_text(json.dumps({'result':result,'natural_processes':3,'control_processes':3,'natural_parallel':[8,4,8],'no_extra_repeats':True,'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'peak_workspace_bytes':guard.peak,'min_free_bytes':guard.minimum_free,'not_a_performance_comparison':True},indent=2)+'\n')
