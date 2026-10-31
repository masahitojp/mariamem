"""Paired topology comparison; preserve every ordinary sample and real median trace."""
import csv,hashlib,json,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
E=Path(__file__).resolve().parent
rs=json.loads((E/'records.json').read_text());assert json.loads((E/'completion.json').read_text())['result']=='PASS'
expected={f'read-{k}-{i:02d}' for k in range(5) for i in range(1,11)}|{f'write-{k}-{i:02d}' for k in range(5) for i in range(1,5)}
validation=[]
for r in rs:
 d=json.loads((E/r['report']).read_text());assert d['completed'] and d['cleanup_complete'] and set(d['cases'])==expected and all(d['cases'].values())
 hybrid=r['mode']=='mariamem-shared-read';fork=[x for x in d['spans'] if x['stage']=='fork'];read=[x for x in d['spans'] if x['stage']=='read-baseline-fork']
 assert len(fork)==(20 if hybrid else 70) and len(read)==(1 if hybrid else 0)
 assert d['max_forks']==r['parallelism']+int(hybrid)
 if hybrid:assert d['read_shared_final_pristine'] and all(x['case'].startswith('write-') for x in fork)
 windows={x['case']:(x['start_ms'],x['start_ms']+x['duration_ms'],x['slot']) for x in d['spans'] if x['stage']=='case-body'};assert set(windows)==expected
 for x in d['spans']:
  assert x['start_ms']>=0 and x['duration_ms']>=0
  if x['stage']=='case-cleanup':
   a,b,l=windows[x['case']];windows[x['case']]=(a,max(b,x['start_ms']+x['duration_ms']),l)
 active=peak=0
 for _,delta in sorted([(a,1) for a,b,l in windows.values()]+[(b,-1) for a,b,l in windows.values()]):active+=delta;peak=max(peak,active)
 assert peak<=r['parallelism']
 for slot in range(r['parallelism']):
  seq=sorted((a,b) for a,b,l in windows.values() if l==slot);assert all(a2>=b1 for (a1,b1),(a2,b2) in zip(seq,seq[1:]))
 validation.append(dict(label=r['label'],cases=70,forks=len(fork)+len(read),peak_active_cases=peak,final_read_pristine=d.get('read_shared_final_pristine'),slot_nonoverlap=True))
(E/'trace-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
modes=['mariamem','mariamem-shared-read'];names={'mariamem':'All 70 tests: independent Fork','mariamem-shared-read':'50 shared reads + 20 isolated writes (21 Forks)'}
rows=[];picked={}
for p in [1,2,4,8]:
 for m in modes:
  cell=sorted([r for r in rs if not r['warmup'] and r['parallelism']==p and r['mode']==m],key=lambda r:r['wall_ms']);assert len(cell)==5
  r=cell[2];d=json.loads((E/r['report']).read_text());picked[p,m]=(r,d)
  counts={stage:sum(x['duration_ms'] for x in d['spans'] if x['stage']==stage) for stage in ['boot','schema-master-sample','capture-disconnect','read-baseline-fork','fork','input-oracle','read','write','case-cleanup','read-baseline-cleanup','read-baseline-final-oracle']}
  rows.append(dict(parallelism=p,mode=m,median_ms=r['wall_ms'],min_ms=cell[0]['wall_ms'],max_ms=cell[-1]['wall_ms'],suite_ms=d['suite_ms'],median_run=r['report'],fork_count=21 if m==modes[1] else 70,phase_sum_ms=counts))
paired=[]
for p in [1,2,4,8]:
 by={m:{r['repetition']:r for r in rs if not r['warmup'] and r['parallelism']==p and r['mode']==m} for m in modes}
 a,b=[next(r['median_ms'] for r in rows if r['parallelism']==p and r['mode']==m) for m in modes]
 paired.append(dict(parallelism=p,ratio_of_medians=b/a,reduction_percent=100*(1-b/a),paired_ratio=[by[modes[1]][i]['wall_ms']/by[modes[0]][i]['wall_ms'] for i in range(5)]))
(E/'summary.json').write_text(json.dumps(dict(rows=rows,paired=paired),indent=2)+'\n')
with (E/'summary.csv').open('w') as f:
 keys=[k for k in rows[0] if k!='phase_sum_ms'];w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in keys} for r in rows)
P=E/'plots';P.mkdir(exist_ok=True);plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(10.3,4.9),layout='constrained')
for m,color in zip(modes,['#0072B2','#009E73']):
 vals=[r for r in rows if r['mode']==m]
 ax.errorbar([r['parallelism'] for r in vals],[r['median_ms']/1000 for r in vals],yerr=[[ (r['median_ms']-r['min_ms'])/1000 for r in vals],[(r['max_ms']-r['median_ms'])/1000 for r in vals]],marker='o',capsize=4,label=names[m],color=color)
ax.set(title='Same 70 cases: change only read-only sharing policy',xlabel='Test parallelism (fixed GOMAXPROCS=8)',ylabel='Whole test process, seconds',xticks=[1,2,4,8],ylim=(0,None));ax.grid(alpha=.2);ax.legend(fontsize=9)
fig.text(.01,-.04,'M1 / MariaDB12.3.3 / Go1.26.10. Five paired repetitions; whiskers=min/max. Includes setup and cleanup. No Docker cells.',fontsize=8)
fig.savefig(P/'scaling.svg',bbox_inches='tight');fig.savefig(E/'scaling.png',dpi=160,bbox_inches='tight');plt.close(fig)
colors={'boot':'#56B4E9','schema-master-sample':'#E69F00','capture-disconnect':'#CC79A7','read-baseline-fork':'#009E73','fork':'#0072B2','input-oracle':'#B7B7B7','read':'#009E73','write':'#AA3377','case-cleanup':'#555555','read-baseline-final-oracle':'#B7B7B7','read-baseline-cleanup':'#555555','owner-cleanup':'#555555'}
legend=[('Boot','#56B4E9'),('Schema + seed','#E69F00'),('Capture + disconnect','#CC79A7'),('Writing / per-case Fork','#0072B2'),('Shared read Fork / read SQL','#009E73'),('Input / final oracle','#B7B7B7'),('Write SQL','#AA3377'),('Cleanup','#555555')]
xmax=max(d['suite_ms'] for r,d in picked.values())/1000*1.02
parts=[]
for p in [1,2,4,8]:
 fig,axes=plt.subplots(2,1,figsize=(11.5,max(4.5,1.9+.49*p)),sharex=True,layout='constrained')
 for ax,m in zip(axes,modes):
  r,d=picked[p,m]
  for x in d['spans']:
   if x['stage'] in colors:ax.barh(0 if x['slot']<0 else x['slot']+1,x['duration_ms']/1000,left=x['start_ms']/1000,height=.68,color=colors[x['stage']],linewidth=0)
  ax.set(title=f"{names[m]} | whole process {r['wall_ms']/1000:.3f}s; body {d['suite_ms']/1000:.3f}s",yticks=list(range(p+1)),yticklabels=['setup / finish']+[f'lane {i+1}' for i in range(p)],xlim=(0,xmax),ylim=(p+.6,-.6));ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);ax.title.set_fontsize(9)
 axes[-1].set_xlabel('Seconds since TestMain entry (same scale for all panels and parallelisms)');fig.suptitle(f'Actual median-wall runs — parallelism {p}',fontsize=12)
 fig.legend(handles=[Patch(color=c,label=n) for n,c in legend],loc='outside lower center',ncol=4,fontsize=8)
 fig.savefig(P/f'timeline-p{p}.svg',bbox_inches='tight');fig.savefig(E/f'timeline-p{p}.png',dpi=150,bbox_inches='tight');plt.close(fig)
 for_svg=(P/f'timeline-p{p}.svg').read_text();parts.append(f'<section id="p{p}"><h2>Parallelism {p}</h2>'+for_svg[for_svg.index('<svg'): ]+'</section>')
svg=(P/'scaling.svg').read_text();svg=svg[svg.index('<svg'):]
html='<!doctype html><meta charset="utf-8"><title>Shared-read Fork comparison</title><style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:1rem}svg{max-width:100%;height:auto}nav a{margin-right:1rem}section{margin-top:2rem}</style><h1>Read-only sharing: 70 Forks versus 21 Forks</h1><p>Identical SQL, seed, case assertions, Go compiler and product source. Parent-owned read child is shared by 50 SELECT-only cases; 20 writers retain independent Forks. Full process wall includes setup, final pristine audit and cleanup. An experimental benchmark policy, not a new library API or read-only enforcement feature.</p><nav><a href="#scaling">Scaling</a>'+''.join(f'<a href="#p{p}">P{p}</a>' for p in [1,2,4,8])+'</nav><section id="scaling">'+svg+'</section><p>Five paired repetitions, actual median runs. Timelines begin at TestMain entry; whole-process timing also includes work before/after it. Span sums overlap and are not wall-time estimates. Same seeded Snapshot as the previous benchmark, not an exact pgmem seed/machine comparison.</p>'+''.join(parts)
(E/'comparison.html').write_text(html)
for f in [*P.glob('*.svg'),E/'comparison.html']:f.write_text('\n'.join(l.rstrip() for l in f.read_text().splitlines())+'\n')
print(json.dumps(dict(rows=rows,paired=paired),indent=2))
