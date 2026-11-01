"""Show all repetitions at suite, probe-process and child-readiness levels."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
E=Path(__file__).resolve().parent
rows=json.loads((E/'compact/summary.json').read_text())['rows']
fig=plt.figure(figsize=(11.8,8),layout='constrained');gs=fig.add_gridspec(2,2)
axes=[fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,:])]
profiles=[('mariamem','tcp','mariamem / TCP','#0072B2'),('pgmem','pipe','pgmem / in-process','#009E73'),('pgmem','tcp','pgmem / TCP','#D55E00')]
for ax,kind,metric,title in zip(axes,['macro','micro','micro'],['wall','wall','ready'],['70-case suite: whole process','20-child probe: whole process','Fork to first SELECT: median of20 children per process']):
 for backend,route,label,color in profiles:
  r=next(r for r in rows if r['kind']==kind and r['backend']==backend and r['route']==route)
  stat=r['wall'] if metric=='wall' else r['stages']['ready_ms']
  y=[v/1000 if metric=='wall' else v for v in stat['values_ms']]
  ax.plot(range(1,11),y,marker='o',linewidth=1.2,markersize=4,color=color,label=f"{label} (CV {stat['cv_percent']:.1f}%)")
 ax.set(title=title,xlabel='Measured repetition (routes rotate within each round)',ylabel='Seconds' if metric=='wall' else 'Milliseconds',xticks=range(1,11),ylim=(0,None));ax.grid(alpha=.2);ax.legend(fontsize=7.5)
fig.suptitle('Parallelism4 / same M1 / Go1.27.3 / GOMAXPROCS8',fontsize=13)
fig.text(.01,-.025,'10 fresh-process repeats per route +1 excluded warmup. CV=sample SD/mean. No outlier exclusion. Readiness excludes later oracle/mutation SQL. Finite samples do not prove tail absence.',fontsize=8)
p=E/'p4-variability.svg';fig.savefig(p,bbox_inches='tight');fig.savefig(E/'p4-variability.png',dpi=150,bbox_inches='tight');p.write_text('\n'.join(l.rstrip() for l in p.read_text().splitlines())+'\n')
