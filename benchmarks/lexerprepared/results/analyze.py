from pathlib import Path
import argparse,json,statistics as st,hashlib,csv,io,tarfile
ROOT=Path(__file__).resolve().parent

def validate(r,rec):
 assert rec['variant']==rec['arm']
 assert r['cleanup'] and 0<r['max_active']<=rec['parallel']
 assert r['mode']==rec['mode'] and r['parallel']==rec['parallel'] and r['count']==rec['count']
 assert r['resolved_max_forks']==(rec['parallel'] if rec['mode']=='fork' else 0)
 n=rec['count']+(rec['mode']=='fork');c=r['cleanup_stats'];arm=rec['variant']
 assert c['lp_original']==(638*n if arm=='original' else 0)
 assert c['lp_hits']==(0 if arm=='original' else 638*n)
 assert c['lp_copies']==(0 if arm=='original' else n)
 assert c['lp_verified']==(638*n if arm=='verify' else 0)
 assert c['lp_fallback']==c['lp_unknown_verified']==(n if arm=='verify' else 0)
 if rec['kind']=='control':assert r['lexer_sql_checks']>=rec['count']

 assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 if rec['negative']:
  assert not r['success'] and rec['exit_code']==1 and 'pristine oracle' in r['error']
  return
 assert r['success'] and rec['exit_code']==0 and len(r['samples'])==rec['count']
 assert sorted(x['index'] for x in r['samples'])==list(range(rec['count']))
 for x in r['samples']:
  assert x['cleanup'] and x['oracle'] and not x.get('error')
  names=[z['name'] for z in x['spans']]
  assert len(names)==len(set(names))
  assert {'start_or_fork','connect','select1','count_sum','update','verify_update','retire','close'}<=set(names)
  assert ('seed' in names)==(rec['mode']=='fresh')
  assert all(x['begin_ms']<=z['begin_ms']<=z['end_ms']<=x['end_ms'] for z in x['spans'])
 assert r['suite_ms']>=r['batch_end_ms']>=r['batch_begin_ms']>=0

def reduce(records,load):
 assert len(records)==56,len(records)
 expected=set()
 for v in ['original','prepared']:
  expected.add((v,'fork',1,0,'negative'))
  expected.add((v,'fork',4,0,'diagnostic'))
  for mode in ['fresh','fork']:
   for parallel in [1,4]:
    expected.add((v,mode,parallel,-1,'warmup'))
    for rep in range(5):expected.add((v,mode,parallel,rep,'primary'))
 for v in ['original','verify']:
  for mode in ['fresh','fork']:expected.add((v,mode,1,0,'control'))
 assert {(r['variant'],r['mode'],r['parallel'],r['rep'],r['kind']) for r in records}==expected
 keys=[(r['variant'],r['mode'],r['parallel'],r['rep'],r['kind']) for r in records];assert len(keys)==len(set(keys))
 primary=[x for x in records if x['kind']=='primary'];assert len(primary)==40
 table={};children=[]
 for rec in records:validate(load(rec['report']),rec)
 for variant in ['original','prepared']:
  for mode in ['fresh','fork']:
   for parallel in [1,4]:
    rows=[r for r in primary if (r['variant'],r['mode'],r['parallel'])==(variant,mode,parallel)]
    assert len(rows)==5 and {r['rep'] for r in rows}==set(range(5))
    rows=sorted(rows,key=lambda x:x['rep']);process=[]
    for rec in rows:
     r=load(rec['report']);phases={};tails=[]
     for x in r['samples']:
      vals={z['name']:z['end_ms']-z['begin_ms'] for z in x['spans']}
      for k,v in vals.items():phases.setdefault(k,[]).append(v)
      for k in ['select1','count_sum','update','verify_update']:
       if vals[k]>100:tails.append({'index':x['index'],'phase':k,'ms':vals[k]})
      children.append(dict(variant=variant,mode=mode,parallel=parallel,rep=rec['rep'],index=x['index'],lane=x['lane'],begin_ms=x['begin_ms'],end_ms=x['end_ms'],**vals))
     process.append({'rep':rec['rep'],'suite_ms':r['suite_ms'],'cpu_ms':r['suite_cpu_ms'],'batch_ms':r['batch_ms'],'prepare_ms':r['batch_begin_ms'],'final_ms':r['suite_ms']-r['batch_end_ms'],'child_median_ms':{k:st.median(v) for k,v in phases.items()},'sql_gt100ms':tails,'root_spans':r['root_spans']})
    key=f'{variant}-{mode}-p{parallel}';table[key]={'processes':process,'median':{k:st.median(p[k] for p in process) for k in ['suite_ms','cpu_ms','batch_ms','prepare_ms','final_ms']},'range_suite_ms':[min(p['suite_ms'] for p in process),max(p['suite_ms'] for p in process)],'phase_process_median_ms':{k:st.median(p['child_median_ms'][k] for p in process) for k in process[0]['child_median_ms']},'sql_gt100ms_count':sum(len(p['sql_gt100ms']) for p in process),'sql_gt100ms_children':sum(len({x['index'] for x in p['sql_gt100ms']}) for p in process)}
 effects={}
 for mode in ['fresh','fork']:
  for parallel in [1,4]:
   a=table[f'original-{mode}-p{parallel}']['processes'];b=table[f'prepared-{mode}-p{parallel}']['processes'];pairs=[{'rep':i,'suite_delta_ms':y['suite_ms']-x['suite_ms'],'suite_change_pct':(y['suite_ms']/x['suite_ms']-1)*100,'cpu_change_pct':(y['cpu_ms']/x['cpu_ms']-1)*100,'start_or_fork_delta_ms':y['child_median_ms']['start_or_fork']-x['child_median_ms']['start_or_fork']} for i,(x,y) in enumerate(zip(a,b))]
   effects[f'{mode}-p{parallel}']={'pairs':pairs,'median_paired_prepared_wall_pct':st.median(x['suite_change_pct'] for x in pairs),'median_paired_prepared_cpu_pct':st.median(x['cpu_change_pct'] for x in pairs),'prepared_faster_pairs':sum(x['suite_delta_ms']<0 for x in pairs),'median_paired_start_or_fork_delta_ms':st.median(x['start_or_fork_delta_ms'] for x in pairs),'start_or_fork_faster_pairs':sum(x['start_or_fork_delta_ms']<0 for x in pairs)}
 ordering={}
 for variant in ['original','prepared']:
  for parallel in [1,4]:
   a=table[f'{variant}-fresh-p{parallel}']['median']['suite_ms'];b=table[f'{variant}-fork-p{parallel}']['median']['suite_ms'];ordering[f'{variant}-p{parallel}']={'fresh_ms':a,'fork_ms':b,'fork_vs_fresh_pct':(b/a-1)*100}
 gate=effects['fork-p1']['median_paired_start_or_fork_delta_ms']<=-0.5 and effects['fork-p1']['start_or_fork_faster_pairs']>=4
 return {'prototype_threshold_met':gate,'cells':table,'paired_version_effects':effects,'fresh_fork_ordering':ordering,'primary_processes':40,'primary_children':1920,'all_samples_retained':True},children

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
 records=json.loads((ROOT/'records.json').read_text());cache={}
 def load(name):
  p=ROOT/name
  if p.exists():return json.loads(p.read_text())
  compact=ROOT/"observations.json"
  if compact.exists():return json.loads(compact.read_text())[name]
  if not cache:
   with tarfile.open(ROOT/'raw-processes.tar.gz') as archive:
    for m in archive.getmembers():
     assert m.isfile() and Path(m.name).name==m.name
     cache[m.name]=archive.extractfile(m).read()
  return json.loads(cache[name])
 result,children=reduce(records,load);summary=json.dumps(result,indent=2,sort_keys=True)+'\n'
 out=io.StringIO();columns=['variant','mode','parallel','rep','index','lane','begin_ms','end_ms','start_or_fork','connect','version','select1','seed','count_sum','update','verify_update','retire','close'];writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader();writer.writerows(children)
 if args.check:
  assert (ROOT/'summary.json').read_text()==summary
  assert (ROOT/'children.csv').read_text()==out.getvalue().replace('\r\n','\n')
  print('Read-only replay PASS:40 primary processes /1920 children')
 else:
  (ROOT/'summary.json').write_text(summary);(ROOT/'children.csv').write_text(out.getvalue())
  print(json.dumps(result['fresh_fork_ordering'],indent=2))
if __name__=='__main__':main()
