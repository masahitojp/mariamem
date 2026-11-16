from pathlib import Path
import json,statistics as st,math,collections
E=Path(__file__).resolve().parent;rows=json.loads((E/'records.json').read_text());out={}
def q(xs,p):
 xs=sorted(xs);f=(len(xs)-1)*p;i=int(f);return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(f-i)
def stats(xs):
 m=st.median(xs);return {'min':min(xs),'q25':q(xs,.25),'median':m,'q75':q(xs,.75),'p90':q(xs,.9),'max':max(xs),'mad_percent':100*st.median(abs(x-m)for x in xs)/m,'slow_over_1_2_median':sum(x>1.2*m for x in xs)}
def corr(a,b):
 if len(set(a))<2 or len(set(b))<2:return None
 return st.correlation(a,b)
def sched95(row):
 h=row['sched_histogram'];b=list(map(float,h['buckets'].strip('[]').split()));counts=h['counts'];target=sum(counts)*.95;s=0
 for i,c in enumerate(counts):
  s+=c
  if s>=target:return 1000*b[i+1] if math.isfinite(b[i+1])else None
 return None
for row in rows:row['sched_p95_upper_ms']=sched95(row)
for p in [1,8]:
 o={};rr=[x for x in rows if x['p']==p and x['block']>=0]
 for arm in ['maria','pg']:
  a=[x for x in rr if x['arm']==arm];aa=[]
  for b in range(10):
   x,y=sorted([x for x in a if x['block']==b],key=lambda x:x['seq']);aa.append({'block':b,'first':x['elapsed_ms'],'second':y['elapsed_ms'],'percent':100*(y['elapsed_ms']/x['elapsed_ms']-1)})
  fast=sorted(a,key=lambda x:x['elapsed_ms'])[:5];slow=sorted(a,key=lambda x:x['elapsed_ms'])[-5:]
  detail={}
  for label,group in [('fast5',fast),('slow5',slow)]:
   detail[label]={'names':[x['name']for x in group],'elapsed_mean':st.mean(x['elapsed_ms']for x in group),'cpu_mean':st.mean(x['cpu_ms']for x in group),'partition_mean':{k:st.mean(x['partition'][k]for x in group)for k in group[0]['partition']},'phase_p50_mean':{k:st.mean(x['phases'][k]['p50_ms']for x in group)for k in group[0]['phases']},'runtime_metrics_mean':{k:st.mean(x['runtime_metrics'][k]for x in group)for k in group[0]['runtime_metrics']},'sched_p95_upper_ms_mean':st.mean(x['sched_p95_upper_ms']for x in group)}
  o[arm]={'suite':stats([x['elapsed_ms']for x in a]),'process':stats([x['wall_ms']for x in a]),'cpu':stats([x['cpu_ms']for x in a]),'aa':{'pairs':aa,'median_percent':st.median(x['percent']for x in aa),'absolute_median_percent':st.median(abs(x['percent'])for x in aa),'range_percent':[min(x['percent']for x in aa),max(x['percent']for x in aa)]},'fast_slow':detail,'last_writer_counts':dict(collections.Counter(x['last_writer']for x in a)),'suite_cpu_correlation':corr([x['elapsed_ms']for x in a],[x['cpu_ms']for x in a])}
 blocks=[]
 for b in range(10):
  br=[x for x in rr if x['block']==b];av={arm:st.geometric_mean(x['elapsed_ms']for x in br if x['arm']==arm)for arm in ['maria','pg']};blocks.append({'block':b,**av,'gap_percent':100*(av['maria']/av['pg']-1)})
 o['comparison']={'blocks':blocks,'paired_gap_median_percent':st.median(x['gap_percent']for x in blocks),'paired_gap_range':[min(x['gap_percent']for x in blocks),max(x['gap_percent']for x in blocks)],'blocks_under_10_percent':sum(x['gap_percent']<=10 for x in blocks),'median_gap_percent':100*(o['maria']['suite']['median']/o['pg']['suite']['median']-1),'q25_gap_percent':100*(o['maria']['suite']['q25']/o['pg']['suite']['q25']-1),'q75_gap_percent':100*(o['maria']['suite']['q75']/o['pg']['suite']['q75']-1),'block_time_correlation':corr([x['maria']for x in blocks],[x['pg']for x in blocks])}
 out[str(p)]=o
(E/'summary.json').write_text(json.dumps(out,indent=2));(E/'derived-records.json').write_text(json.dumps(rows,indent=2))
for p,o in out.items():
 print('P',p,'comparison',json.dumps(o['comparison']))
 for arm in ['maria','pg']:
  a=o[arm];print(arm,'suite',a['suite'],'AA',a['aa']['absolute_median_percent'],a['aa']['range_percent']);print(arm,'fastslow',json.dumps(a['fast_slow']))
