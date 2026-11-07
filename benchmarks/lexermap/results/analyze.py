from pathlib import Path
import json,hashlib,statistics as st,argparse
from compact import unpack
P=Path(__file__).resolve().parent
def analyze(observations):
 assert set(observations)=={f'{mode}-{i}' for mode in ['off','timed'] for i in range(5)}|{'inventory-0'}
 process=[];inventory=[];expected=None;fullmaps={}
 for name,r in observations.items():
  mode,rep=name.split('-');assert r['Mode']==mode
  assert r['Success'] and not r['Error'] and len(r['Samples'])==5
  assert r['TimerIterations']==100000 and r['TimerNS']>0
  assert all(r['Cleanup'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
  rows=[]
  for n,s in enumerate(r['Samples']):
   kind='fresh' if n==0 else 'fork';assert s['Kind']==kind and s['Index']==max(0,n-1) and s['API_NS']>0
   calls=s['Rows'] or [];assert (mode=='off')==(len(calls)==0)
   sig=[(c['number'],c['descriptor_offset']) for c in calls]
   assert len(sig)==len(set(sig))
   if mode!='off':
    if expected is None:expected=sig
    assert sig==expected
   for c in calls:
    assert c['result']==c['exception']==0
    assert (c['elapsed_ns']>0)==(mode=='timed')
    if mode=='inventory':
     raw=bytes.fromhex(c['pair_hex']);assert len(raw)==512
     h=hashlib.sha256(raw).hexdigest();assert h==c['pair_sha256']
     if h in fullmaps:assert fullmaps[h]==c['pair_hex']
     fullmaps[h]=c['pair_hex']
   rows.append({'kind':kind,'index':s['Index'],'api_ms':s['API_NS']/1e6,'calls':len(calls),'map_sum_ms':sum(c['elapsed_ns'] for c in calls)/1e6,'max_call_ms':max([c['elapsed_ns'] for c in calls] or [0])/1e6})
   if mode=='inventory':inventory.append({'kind':kind,'index':s['Index'],'calls':len(calls),'unique_pairs':len({c['pair_sha256'] for c in calls}),'bindings':[{'number':c['number'],'descriptor_offset':c['descriptor_offset'],'pair_sha256':c['pair_sha256']} for c in calls]})
  process.append({'name':name,'mode':mode,'rep':int(rep),'timer_pair_mean_ns':r['TimerNS']/100000,'samples':rows,'fork_api_median_ms':st.median(x['api_ms'] for x in rows[1:]),'fork_map_sum_median_ms':st.median(x['map_sum_ms'] for x in rows[1:])})
 timed=sorted([p for p in process if p['mode']=='timed'],key=lambda p:p['rep'])
 off=sorted([p for p in process if p['mode']=='off'],key=lambda p:p['rep'])
 med=st.median(p['fork_map_sum_median_ms'] for p in timed)
 paired=[(a['fork_api_median_ms']/b['fork_api_median_ms']-1)*100 for a,b in zip(timed,off)]
 assert all(x['bindings']==inventory[0]['bindings'] for x in inventory)
 bindings=inventory[0]['bindings']
 for item in inventory:item.pop('bindings')
 result={'bindings':bindings,'processes':process,'inventory':inventory,'map_pairs':fullmaps,'calls_per_initialization':len(expected),'unique_pairs':len(fullmaps),'generated_bytes_per_initialization':len(expected)*512,'unique_pair_bytes':len(fullmaps)*512,'timed_fork_map_sum_ms_median':med,'timed_fork_map_sum_ms_range':[min(x['map_sum_ms'] for p in timed for x in p['samples'][1:]),max(x['map_sum_ms'] for p in timed for x in p['samples'][1:])],'timed_fresh_map_sum_ms_median':st.median(p['samples'][0]['map_sum_ms'] for p in timed),'off_fork_api_ms_median':st.median(p['fork_api_median_ms'] for p in off),'timed_fork_api_ms_median':st.median(p['fork_api_median_ms'] for p in timed),'paired_fork_api_pct':paired,'paired_fork_api_pct_median':st.median(paired),'empty_timer_pair_mean_ns_median':st.median(p['timer_pair_mean_ns'] for p in timed),'threshold_ms':1,'threshold_met':med>=1,'all55_initializations_retained':True}
 result['timer_pair_budget_ms_per_initialization']=result['empty_timer_pair_mean_ns_median']*len(expected)/1e6
 return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 out=analyze(unpack(json.loads((P/'observations.json').read_text())))
 data=json.dumps(out,indent=2,sort_keys=True)+'\n'
 if args.check:assert (P/'summary.json').read_text()==data;print('Read-only replay PASS:11 processes /55 initializations')
 else:(P/'summary.json').write_text(data)
 print(json.dumps({k:v for k,v in out.items() if k not in ['processes','inventory','map_pairs','bindings']},indent=2))
if __name__=='__main__':main()
