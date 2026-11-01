"""Compact phase and diagnostic evidence; --check never reads build scratch."""
import argparse,hashlib,json,re,statistics,math
from pathlib import Path
PHASES=['fork','sql','close']
def dump(d):return json.dumps(d,indent=2,sort_keys=True)+'\n'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def top(text):
 m=re.search(r'Total samples = ([0-9.]+)(ms|s)',text)
 if not m:
  m=re.search(r'of ([0-9.]+)(ms|s) total',text)
 total=(float(m[1])*(1000 if m[2]=='s' else 1)) if m else 0
 rows=[]
 for line in text.splitlines():
  v=line.split()
  if len(v)<6 or not v[1].endswith('%'):continue
  def ms(s):
   if s=='0':return 0.
   if s.endswith('ms'):return float(s[:-2])
   if s.endswith('s'):return float(s[:-1])*1000
   raise ValueError(s)
  rows.append(dict(function=' '.join(v[5:]),flat_ms=ms(v[0]),cum_ms=ms(v[3])))
 return dict(total_cpu_sample_ms=total,top=rows)
def collect(e):
 read=lambda n:json.loads((e/n).read_text())
 records=read('measure-records.json');out=[]
 for r in records:
  d=read(r['report']);phases=d.pop('phases');assert [p['name'] for p in phases]==PHASES*d['count']
  d['phase_totals']={name:dict(count=sum(p['name']==name for p in phases),wall_ms=math.fsum(p['wall_ms'] for p in phases if p['name']==name),cpu_ms=math.fsum(p['cpu_ms'] for p in phases if p['name']==name)) for name in PHASES};t=dict(r,result=d)
  if r['target']!='none':
   t['profile']=top((e/r['report'].replace('.json','-flat.txt')).read_text())
   t['profile_cumulative']=top((e/r['report'].replace('.json','-cum.txt')).read_text())
  out.append(t)
 return dict(inputs=read('inputs.json'),pilot=read('pilot.json'),completion=read('completion.json'),runs=out)
def summarize(d):
 assert d['pilot']['result']=='PASS' and d['completion']['result']=='PASS'
 runs=d['runs'];assert len(runs)==10
 assert {(r['mode'],r['target'],r['repetition']) for r in runs}=={(mode,target,rep) for rep in range(2) for mode,target in [('profile','none'),('profile','fork'),('profile','sql'),('profile','close'),('diagnostic','none')]}
 for r in runs:
  t=r['result'];assert t['success'] and t['cleanup'] and r['returncode']==0
  assert t['count']==r['count'] and t['queries_per_child']==32
  assert set(t['phase_totals'])==set(PHASES) and all(p['count']==r['count'] for p in t['phase_totals'].values())
  assert all(t['final'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes'])
  if r['mode']=='diagnostic':
   x=t['diagnostic'];assert sum(x[p]['spawn']-x[p]['exit'] for p in ['outside',*PHASES])==0
 controls=[r for r in runs if r['mode']=='profile' and r['target']=='none']
 control=[]
 for r in controls:
  phases={name:{k:r['result']['phase_totals'][name][k]/r['count'] for k in ['wall_ms','cpu_ms']} for name in PHASES}
  control.append(dict(repetition=r['repetition'],phases=phases))
 profiles=[]
 for r in runs:
  if r['target']=='none':continue
  p=r['profile'];names={x['function']:x for x in [*r['profile_cumulative']['top'],*p['top']]}
  functions={name:names.get(name,dict(flat_ms=None,cum_ms=None)) for name in ['runtime.pthread_cond_signal','runtime.pthread_cond_wait','runtime.goschedImpl','runtime.wakep','runtime.newproc','github.com/masahitojp/mariamem/internal/generatedgo/code/base.(*WasiStubs).Fd_write','github.com/masahitojp/mariamem/internal/generatedgo/code/base.writeVec','os.(*File).Write','github.com/masahitojp/mariamem/internal/generatedgo/code/base.SpinRelax','github.com/masahitojp/mariamem/internal/generatedgo/code/base.(*WasiStubs).Sched_yield','github.com/masahitojp/mariamem/internal/generatedgo/code/base.AtomicWait']}
  profiles.append(dict(phase=r['target'],repetition=r['repetition'],total_cpu_sample_ms=p['total_cpu_sample_ms'],selected_top50_functions=functions))
 diagnostics=[]
 for r in runs:
  if r['mode']!='diagnostic':continue
  x=r['result']['diagnostic'];diagnostics.append(dict(repetition=r['repetition'],peak_live_spawned_agents=x['peak_live_spawned_agents'],per_child={p:{k:v/r['count'] for k,v in x[p].items()} for p in PHASES},outside=x['outside']))
 return dict(controls=control,profiles=profiles,diagnostics=diagnostics,warning='Missing top50 flat/cumulative entry is not proof of zero CPU; wait_ns sums wall waits ending in phase, not CPU. Spin yield counters exclude WASI Sched_yield.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--collect',type=Path);p.add_argument('--results',type=Path,default=Path(__file__).parent/'results');p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.collect:
  assert not a.check;d=collect(a.collect);s=summarize(d);a.results.mkdir(parents=True,exist_ok=True);(a.results/'observations.json').write_text(dump(d));(a.results/'summary.json').write_text(dump(s))
 else:
  assert a.check
  for n,h in json.loads((a.results/'SHA256SUMS.json').read_text()).items():assert sha(a.results/n)==h,n
  d=json.loads((a.results/'observations.json').read_text());assert dump(summarize(d))==(a.results/'summary.json').read_text();print('CHECK PASS: complete phase set, cleanup, worker balance, summary, checksums')
if __name__=='__main__':main()
