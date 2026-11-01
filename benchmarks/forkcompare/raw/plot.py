"""One overview plot from compact statistics; no raw/build inputs."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
E=Path(__file__).resolve().parent
rows=json.loads((E/'compact/summary.json').read_text())['rows']
fig,axes=plt.subplots(1,2,figsize=(11,4.7),layout='constrained')
labels=[('mariamem','tcp','mariamem / TCP','#0072B2'),('pgmem','pipe','pgmem / in-process','#009E73'),('pgmem','tcp','pgmem / TCP','#D55E00')]
for ax,kind,title in zip(axes,['micro','macro'],['Child Fork to physical connection + SELECT 1','70-case suite, whole process']):
 upper=0
 for j,(backend,route,label,color) in enumerate(labels):
  points=[next(r for r in rows if r['kind']==kind and r['parallelism']==p and r['backend']==backend and r['route']==route) for p in [1,8]]
  v=[r['ready_ms']['median_of_process_medians'] if kind=='micro' else r['median_wall_ms'] for r in points]
  lo=[r['ready_ms']['min_process_median'] if kind=='micro' else r['min_wall_ms'] for r in points]
  hi=[r['ready_ms']['max_process_median'] if kind=='micro' else r['max_wall_ms'] for r in points]
  upper=max(upper,*hi)
  x=[i+(j-1)*.24 for i in [0,1]]
  bars=ax.bar(x,v,width=.23,label=label,color=color)
  ax.errorbar(x,v,yerr=[[a-b for a,b in zip(v,lo)],[b-a for a,b in zip(v,hi)]],fmt='none',ecolor='#333',capsize=3,linewidth=1)
  for bar,value,bound in zip(bars,v,hi):ax.text(bar.get_x()+bar.get_width()/2,max(value,bound)+upper*.025,f'{value:.1f}',ha='center',fontsize=8)
 ax.set(title=title,xticks=[0,1],xticklabels=['Parallelism 1','Parallelism 8'],ylabel='Milliseconds',ylim=(0,upper*1.2));ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
axes[0].legend(fontsize=8);fig.suptitle('Same M1 / Go1.27.3 / five fresh-process repetitions',fontsize=13)
fig.text(.01,-.025,'Micro: median of 20-child run medians; whiskers=range of 5 run medians. Macro: median/range of 5 processes. Different workloads; no engine-wide speed ratio.',fontsize=8)
p=E/'same-host.svg';fig.savefig(p,bbox_inches='tight');fig.savefig(E/'same-host.png',dpi=150,bbox_inches='tight');p.write_text('\n'.join(l.rstrip() for l in p.read_text().splitlines())+'\n')
