"""Summarize matched memory samples and retain strict failures separately from controls."""
import csv,json,re,sys
from pathlib import Path
from statistics import mean,median
p=Path(sys.argv[1])
memory=[]
for metric in ('rss_ready','rss_done','rss_closed','peak_rss_bytes','live_heap_before'):
    for b in range(1,7):
        pair=[]
        for mode in ('os','both'):
            group=[json.loads(l) for l in (p/'memory'/f'{b}-{mode}.jsonl').read_text().splitlines()]
            assert len(group)==6 and all(r['wave']==i and r['all_workers_closed'] and r['workers']==8 for i,r in enumerate(group))
            amount=max(r[metric] for r in group) if metric=='peak_rss_bytes' else mean(r[metric] for r in group[1:])
            pair.append(amount/2**20)
        memory.append(dict(metric=metric,block=b,os_MiB=pair[0],both_MiB=pair[1],increase_MiB=pair[1]-pair[0]))
with (p/'memory-pairs.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=memory[0],lineterminator='\n');w.writeheader();w.writerows(memory)
text=(p/'fault-first.txt').read_text()+(p/'fault-repeats.txt').read_text()
events={}
for direction in ('input','output'):
    for action in ('cancel','disconnect','drain','serverClose'):
        key=direction+'/'+action
        outcomes=re.findall(r'--- (FAIL|PASS): TestQualificationFullStream/'+key+r' ',text)
        assert len(outcomes)==6
        events[key]=dict(pass_count=outcomes.count('PASS'),fail_count=outcomes.count('FAIL'))
public=(p/'public-drain.txt').read_text()
assert public.count('graceful_close=true')==12 and public.rstrip().endswith('PASS')
partial={}
for mode in ('os','both'):
    logs=(p/('control-'+mode+'.txt')).read_text()
    statuses=re.findall(r'transport='+mode+r' query_err=(\S+) shutdown_err=<nil> disposed=true',logs)
    assert len(statuses)==6
    partial[mode]=dict(eof=statuses.count('EOF'),response_ok=statuses.count('<nil>'))
    assert sum(partial[mode].values())==6
race=(p/'pipe-race.txt').read_text()
assert race.count('--- PASS:')==40 and '\nPASS\n' in race
report=dict(strict=events,strict_eof_occurrences=text.count('drain pending response EOF'),
            differential_partial_send=partial,public_drain_passes=12,standalone_race_cases=40)
(p/'diagnostics.json').write_text(json.dumps(report,indent=2)+'\n')
