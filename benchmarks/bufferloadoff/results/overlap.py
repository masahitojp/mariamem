from pathlib import Path
import json,statistics,sys
E=Path(__file__).resolve().parent;rows=[]
for p in [4,8]:
 for variant in ['current','load-off']:
  for r in range(5):
   d=json.loads((E/f'{variant}-p{p}-r{r}.json').read_text());ss=d['samples'];con=[]
   for x in ss:
    a=x['offset_ms'];b=a+x['fork_ms'];con.append(sum(max(0,min(b,y['offset_ms']+y['fork_ms'])-max(a,y['offset_ms'])) for y in ss)/(b-a))
   rows.append({'parallel':p,'variant':variant,'round':r,'fork_overlap_p50':statistics.median(con),'first_eight_fork_p50_ms':statistics.median(x['fork_ms'] for x in ss if x['index']<8),'later_fork_p50_ms':statistics.median(x['fork_ms'] for x in ss if x['index']>=8)})
result={'scope':'Post-hoc reduction of public Fork intervals; not internal CPU/scheduler contention measurement; not an acceptance criterion','processes':rows}
if '--check' in sys.argv:assert result==json.loads((E/'fork-overlap-posthoc.json').read_text());print('PASS readonly posthoc interval reduction')
else:(E/'fork-overlap-posthoc.json').write_text(json.dumps(result,indent=2)+'\n')
