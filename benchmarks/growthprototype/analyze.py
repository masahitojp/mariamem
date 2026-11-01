"""Read-only compact validation and paired process summaries for Issue 56."""
import argparse,hashlib,json,statistics
from pathlib import Path

def summarize(records,results):
 assert len(records)==10
 rows=[]
 for i in range(5):
  pair=records[i*2:i*2+2];assert [r['mode'] for r in pair]==(['exact','batch'] if i%2==0 else ['batch','exact'])
  values={}
  for r in pair:
   assert r['repetition']==i and not r['negative'] and r['returncode']==0
   d=results[r['report']];assert d['success'] and d['cleanup'] and len(d['children'])==4
   assert d['final']['active_mappings']==d['final']['active_rw_bytes']==d['final']['active_reserved_bytes']==0
   assert d['final']['grow_failures']==d['final']['release_failures']==0
   assert all(c['fallbacks']==0 for c in d['children'])
   values[r['mode']]={k:statistics.median(c[k] for c in d['children']) for k in ['wall_ms','cpu_ms','protect_calls','grow_calls']}
   values[r['mode']]['rss_4_delta_mib']=(r['rss']['child-4']-r['rss']['baseline'])/2**20
   values[r['mode']]['rss_closed_mib']=r['rss']['closed']/2**20
  rows.append({'pair':i,**values,'change_percent':{k:100*(values['batch'][k]/values['exact'][k]-1) for k in ['wall_ms','cpu_ms','rss_4_delta_mib']}})
 return {'scope':'5 alternating process pairs, four sequential retained children; macOS arm64 only','pairs':rows,'medians':{mode:{k:statistics.median(r[mode][k] for r in rows) for k in rows[0][mode]} for mode in ['exact','batch']},'paired_change_percent':{k:{'median':statistics.median(r['change_percent'][k] for r in rows),'min':min(r['change_percent'][k] for r in rows),'max':max(r['change_percent'][k] for r in rows)} for k in rows[0]['change_percent']}}
def render(d):return json.dumps(d,indent=2)+'\n'
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--collect',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.check:
  assert a.collect is None
  for name,h in json.loads((a.results/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((a.results/name).read_bytes()).hexdigest()==h
  obs=json.loads((a.results/'observations.json').read_text());summary=summarize(obs['records'],obs['results']);assert (a.results/'summary.json').read_text()==render(summary)
  print('PASS: hashes and paired summary; read-only');return
 assert a.collect
 records=json.loads((a.collect/'measure-records.json').read_text());results={r['report']:json.loads((a.collect/r['report']).read_text()) for r in records}
 obs={'records':records,'results':results};summary=summarize(records,results);a.results.mkdir(parents=True,exist_ok=True)
 (a.results/'observations.json').write_text(render(obs));(a.results/'summary.json').write_text(render(summary));print(render(summary))
if __name__=='__main__':main()
