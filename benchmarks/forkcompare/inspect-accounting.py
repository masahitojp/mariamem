"""Supplemental residual-case attribution; not part of the preregistered gate."""
import argparse,collections,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();E=a.evidence
 source=(Path(__file__).parent/'analyze-read4-light.py').read_text().replace('[[0,16],[4,4],[0,16],[4,4],[0,16]]','[[0,16],[1,1],[0,16],[1,1],[0,16]]')
 ns={'__name__':'supplemental'};exec(compile(source,'source-bound-light-case-decoder','exec'),ns)
 out={}
 for rec in json.loads((E/'measure-records.json').read_text()):
  path=E/rec['report'];r=json.loads(path.read_text());tp=Path(str(path)+'.trace.json');trace=ns['reduce_trace'](tp,r);raw=json.loads(tp.read_text());events=raw['events'];cases=[]
  for c in trace['cases']:
   ticks=[]
   for tick in c['maintenance']:
    ticks.append(dict(offset_from_count_ms=(tick['begin_ns']-c['count_begin_ns'])/1e6,policies=[{k:s[k] for k in ['active','standby','accounted_waiting','long_tasks','concurrency','concurrency_gate_allows']} for s in tick['policies']]))
   markers=[dict(kind=e['kind'],worker_pointer=e['b'],worker_state=e['c'],offset_from_count_ms=(e['ns']-c['count_begin_ns'])/1e6) for e in events if e['instance']==c['instance'] and e['kind']=='account_null_begin' and c['count_begin_ns']<=e['ns']<=c['count_end_ns']]
   cases.append(dict(child=c['child'],instance=c['instance'],count_ms=c['count_ms'],max_queue_ms=max((x['queue_ms'] for x in c['queued_tasks']),default=None),read_waits=[dict(ms=x['duration_ms'],thread=x['thread'],null_trx=x['trx_is_null'],query_scope=x['query_scope_overlap'],background_scope=x['background_load_scope_overlap']) for x in c['read_waits']],account_markers=markers,maintenance=ticks,add_route_counts=dict(collections.Counter(x['route'] for x in c['add_thread_requests']))))
  out[rec['report']]=dict(variant=rec['variant'],cases=cases)
 a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
