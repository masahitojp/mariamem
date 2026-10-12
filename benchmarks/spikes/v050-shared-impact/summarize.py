from pathlib import Path
import json,collections,sys
p=Path(sys.argv[1]);r=json.loads(p.read_text());names={int(i):n for i,n in (l.split(':',1) for l in Path('docs/reviews/v050-ad-integration-evidence/function-map.txt').read_text().splitlines())}
counts=collections.Counter();sites=collections.defaultdict(set);words=collections.defaultdict(list);retries=0
for row in r['rows']:
 k=row['key'];kind=k['kind'];ea=k['ea'];fn=k['fn']
 if kind.startswith('subword'):counts[fn]+=row['count'];sites[fn].add(k['site'])
 if kind=='cas-retry':retries+=row['count']
 start=ea&~3 if kind.startswith('subword') or kind=='cas-retry' else ea
 end=start+k['effective']
 for word in range(start&~3,((end-1)&~3)+1,4):words[(k['memory'],word)].append(row)
examples=[];mixed=0;adjatomic=0
for (memory,word),rows in words.items():
 writers=[x for x in rows if x['key']['kind'].startswith('subword')]
 if not writers:continue
 for w in writers:
  a=w['key'];ea=a['ea'];requested_end=ea+a['requested']
  for o in rows:
   b=o['key']
   if a['actor']==b['actor'] or b['kind']=='cas-retry':continue
   bs=b['ea']&~3 if b['kind'].startswith('subword') else b['ea'];be=bs+b['effective']
   if max(word,bs)>=min(word+4,be):continue
   ordinary=b['kind'].startswith('ordinary')
   adjacent=b["ea"]+b["requested"]<=ea or b["ea"]>=requested_end
   # Includes same-target and extra-footprint overlap, with category distinct.
   if ordinary:mixed+=1
   elif adjacent:adjatomic+=1
   else:continue
   if len(examples)<250:
    examples.append({'word':word,'memory':memory,'writer':w,'other':o,'extra_footprint':adjacent,'relation':'ordinary' if ordinary else 'adjacent-atomic','same_time_or_hb':'UNPROVEN'})
summary={'input':str(p),'dropped':r['dropped'],'executed_functions':[{'fn':f,'symbol':names.get(f),'count':n,'executed_sites':sorted(sites[f])} for f,n in counts.most_common()],'cas_retries':retries,'cross_actor_ordinary_pair_count':mixed,'cross_actor_extra_atomic_pair_count':adjatomic,'examples':examples,'interpretation':'Address footprint evidence across distinct Module agents, aggregated over lifetime; no instruction simultaneity, allocation generation or happens-before proof.'}
p.with_name('summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('functions',len(counts),'subwordcalls',sum(counts.values()),'retries',retries,'ordinarypairs',mixed,'extraatomicpairs',adjatomic,'dropped',r['dropped'])
for ex in examples[:12]:print(ex['word'],ex['writer']['key']['fn'],ex['writer']['key']['ea'],ex['other']['key']['fn'],ex['other']['key']['ea'],ex['other']['key']['kind'],'extra',ex['extra_footprint'])
