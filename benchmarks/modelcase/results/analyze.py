"""Validate every observed case/trace, then plot actual median runs."""
import csv,io,json,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
E=Path(__file__).resolve().parent
records=json.loads((E/'records.json').read_text())
assert json.loads((E/'completion.json').read_text())['result']=='PASS'
expected={f'read-{k}-{i:02d}' for k in range(5) for i in range(1,11)}|{f'write-{k}-{i:02d}' for k in range(5) for i in range(1,5)}
validation=[]
for record in records:
 d=json.loads((E/record['report']).read_text());assert set(d['cases'])==expected and all(d['cases'].values())
 assert d['completed'] and d['cleanup_complete'] and record['returncode']==0 and record['scratch_empty']
 windows={s['case']:(s['start_ms'],s['start_ms']+s['duration_ms'],s['slot']) for s in d['spans'] if s['stage']=='case-body'}
 assert set(windows)==expected
 for s in d['spans']:
  assert s['start_ms']>=0 and s['duration_ms']>=0
  if s['stage']=='case-cleanup':
   a,b,lane=windows[s['case']];windows[s['case']]=(a,max(b,s['start_ms']+s['duration_ms']),lane)
 endpoints=sorted([(a,1) for a,b,lane in windows.values()]+[(b,-1) for a,b,lane in windows.values()])
 active=peak=0
 for _,delta in endpoints:active+=delta;peak=max(peak,active)
 assert peak<=record['parallelism']
 for lane in range(record['parallelism']):
  spans=sorted((a,b) for a,b,s in windows.values() if s==lane)
  assert all(a2>=b1 for (a1,b1),(a2,b2) in zip(spans,spans[1:]))
 if record['mode']=='shared':
  for name,(a,b,_) in windows.items():
   if name.startswith('write'):
    assert all(b<=c or f<=a for other,(c,f,_) in windows.items() if other!=name)
 validation.append(dict(label=record['label'],cases=70,peak_active_cases=peak,slot_nonoverlap=True,shared_write_exclusion=True if record['mode']=='shared' else None))
(E/'trace-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
modes=['mariamem','shared','workers'];names={'mariamem':'mariamem helper — independent Fork per test','shared':'Testcontainers — shared DB, serialized writers','workers':'Testcontainers — independent worker schemas'}
rows=[];selected={}
for p in [1,2,4,8]:
 for mode in modes:
  rs=[r for r in records if not r['warmup'] and r['parallelism']==p and r['mode']==mode];assert len(rs)==5
  rs=sorted(rs,key=lambda r:r['wall_ms']);mid=rs[2];selected[p,mode]=(mid,json.loads((E/mid['report']).read_text()))
  sp=[x for x in selected[p,mode][1]['spans'] if x['stage']=='case-body'];first=min(x['start_ms'] for x in sp);last=max(x['start_ms']+x['duration_ms'] for x in sp)
  closing=[x for x in selected[p,mode][1]['spans'] if x['stage']=='case-cleanup'];last=max([last]+[x['start_ms']+x['duration_ms'] for x in closing])
  rows.append(dict(case_window_ms=last-first,parallelism=p,mode=mode,median_ms=statistics.median(r['wall_ms'] for r in rs),min_ms=rs[0]['wall_ms'],max_ms=rs[-1]['wall_ms'],median_run=mid['report'],suite_body_ms=selected[p,mode][1]['suite_ms'],repetitions=5,all_cases_passed=True))
(E/'summary.json').write_text(json.dumps(dict(rows=rows,scope='External process wall; min/max whiskers, not confidence intervals; no performance gate'),indent=2)+'\n')
with (E/'summary.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
P=E/'plots';P.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(10.4,5.1),layout='constrained')
for mode,color in zip(modes,['#0072B2','#D55E00','#009E73']):
 rs=[r for r in rows if r['mode']==mode];med=[r['median_ms']/1000 for r in rs]
 ax.errorbar([r['parallelism'] for r in rs],med,yerr=[[r['median_ms']/1000-r['min_ms']/1000 for r in rs],[r['max_ms']/1000-r['median_ms']/1000 for r in rs]],label=names[mode],color=color,marker='o',capsize=4)
ax.set(xlabel='Test parallelism (helper MaxForks / native worker count)',ylabel='Whole suite, seconds',title='Same 70 application tests: 50 reads + 20 committed writes',xticks=[1,2,4,8],ylim=(0,None))
ax.grid(alpha=.22);ax.legend(fontsize=8.5);fig.text(.01,-.04,'Median of 5 fresh-process suites; whiskers = observed min/max. Includes setup and owned cleanup. One local M1 + arm64 Docker VM.',fontsize=8)
fig.savefig(P/'scaling.svg',bbox_inches='tight');fig.savefig(E/'scaling.png',dpi=160,bbox_inches='tight');plt.close(fig)
colors={'boot':'#56B4E9','boot-container-ryuk':'#56B4E9','schema-master-sample':'#E69F00','capture-disconnect':'#CC79A7','fork':'#0072B2','reset-sample':'#D55E00','input-oracle':'#B7B7B7','read':'#009E73','write':'#F0E442','case-cleanup':'#555555','owner-cleanup':'#555555'}
legend=[('Boot / container + Ryuk','#56B4E9'),('Schema + master + sample','#E69F00'),('Capture + disconnect','#CC79A7'),('Fork admission','#0072B2'),('Reset + sample','#D55E00'),('Pristine-input oracle','#B7B7B7'),('Read test','#009E73'),('Write test','#F0E442'),('Cleanup','#555555')]
xmax=max(d['suite_ms'] for r,d in selected.values())/1000*1.025
for p in [1,2,4,8]:
 fig,axes=plt.subplots(3,1,figsize=(11.6,max(5.3,2.7+.68*p)),sharex=True,layout='constrained')
 for ax,mode in zip(axes,modes):
  r,d=selected[p,mode]
  for s in d['spans']:
   if s['stage'] not in colors:continue
   y=0 if s['slot']<0 else s['slot']+1
   ax.barh(y,s['duration_ms']/1000,left=s['start_ms']/1000,height=.68,color=colors[s['stage']],linewidth=0)
  ax.set(title=f"{names[mode]} | actual median-run whole process {r['wall_ms']/1000:.3f}s; TestMain body {d['suite_ms']/1000:.3f}s",yticks=list(range(p+1)),yticklabels=['setup / finish']+[f'lane {i+1}' for i in range(p)],xlim=(0,xmax),ylim=(p+.6,-.6))
  ax.grid(axis='x',alpha=.22);ax.set_axisbelow(True);ax.title.set_fontsize(9)
 axes[-1].set_xlabel('Seconds since TestMain entry (same axis across all panels and parallelisms)')
 fig.suptitle(f'Observed execution spans — parallelism {p}, same 70 tests',fontsize=12)
 fig.legend(handles=[Patch(color=color,label=label) for label,color in legend],loc='outside lower center',ncol=3,fontsize=8)
 fig.savefig(P/f'timeline-p{p}.svg',bbox_inches='tight');fig.savefig(E/f'timeline-p{p}.png',dpi=150,bbox_inches='tight');plt.close(fig)
parts=[]
for p in [1,2,4,8]:
 svg=(P/f'timeline-p{p}.svg').read_text();svg=svg[svg.index('<svg'):];parts.append(f'<section id="p{p}"><h2>Parallelism {p}</h2>'+svg+'</section>')
scaling=(P/'scaling.svg').read_text();scaling=scaling[scaling.index('<svg'):]
html='''<!doctype html><meta charset="utf-8"><title>mariamem / Testcontainers: parallel application suite</title><style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;background:#fafafa;color:#222}svg{max-width:100%;height:auto;background:white}nav a{margin-right:1rem}section{margin-top:3rem}p{line-height:1.5}</style><h1>70 tests, three execution models</h1><p>50 read-only + 20 committed writing cases; same MariaDB12.3.3 fixture and assertions. Local Apple M1/macOS with native-arm64 Linux Docker VM. Whole-suite medians/ranges include preparation, SQL, owned cleanup and process exit; image acquisition and compilation excluded.</p><nav><a href="#scaling">Scaling</a><a href="#p1">P1</a><a href="#p2">P2</a><a href="#p4">P4</a><a href="#p8">P8</a></nav><section id="scaling">'''+scaling+'''</section><p>Timelines show real spans from each cell's median-wall run. Their zero is TestMain entry; whole-process totals additionally include work before/after that interval. Overlapping spans are not added to create a wall time. Schema isolation shares a native server; each mariamem Fork has a separate embedded server.</p>'''+''.join(parts)
(E/'comparison.html').write_text(html)
print(json.dumps(rows,indent=2))

# Normalize generated XML/HTML line-end whitespace for the repository boundary.
for generated in [*P.glob('*.svg'), E/'comparison.html']:
    generated.write_text('\n'.join(line.rstrip() for line in generated.read_text().splitlines())+'\n')
