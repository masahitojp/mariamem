"""Plot compact resource summaries; matplotlib is only needed to redraw the figure."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p = argparse.ArgumentParser()
p.add_argument('--results', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
s = json.loads((a.results / 'summary.json').read_text())['backends']
fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), layout='constrained')
colors = {'mariamem': '#2864b4', 'pgmem': '#e77830'}
for offset, (name, data) in enumerate(s.items()):
    x = [i + (offset-.5)*.32 for i in range(2)]
    vals = [data['phases']['fork'][m] for m in ['wall_ms', 'cpu_ms']]
    med = [v['median'] for v in vals]
    axes[0].bar(x, med, width=.3, color=colors[name], label=name)
    axes[0].errorbar(x, med, yerr=[[v['median']-v['minimum'] for v in vals], [v['maximum']-v['median'] for v in vals]], fmt='none', ecolor='#333333', capsize=3)
    for xx, yy in zip(x, med): axes[0].text(xx, yy+1, f'{yy:.1f}', ha='center', fontsize=9)
    for ax, stages, metric, xs in [
        (axes[1], ['baseline_gc', 'held_1_idle', 'held_2_idle', 'held_4_idle'], 'rss_bytes_delta_from_baseline_gc', [0, 1, 2, 4]),
        (axes[2], ['baseline_gc', 'held_4_idle', 'closed_children_natural', 'closed_children_gc'], 'rss_bytes', [0, 1, 2, 3])]:
        values = [data['stages'][stage][metric] for stage in stages]
        med = [v['median']/1048576 for v in values]
        ax.errorbar(xs, med, yerr=[[(v['median']-v['minimum'])/1048576 for v in values], [(v['maximum']-v['median'])/1048576 for v in values]], marker='o', color=colors[name], capsize=3, label=name)
        for xx, yy in zip(xs, med): ax.annotate(f'{yy:.0f}', (xx, yy), xytext=(0, 8), textcoords='offset points', ha='center', fontsize=9, color=colors[name])
axes[0].set(xticks=[0, 1], xticklabels=['Elapsed', 'Process CPU'], ylabel='Milliseconds per Fork', title='Fork work: CPU cost remains higher')
axes[1].set(xticks=[0, 1, 2, 4], xlabel='Retained children (sequential creation)', ylabel='RSS increase from baseline (MiB)', title='Additional RSS: grows with each child')
axes[2].set(xticks=[0, 1, 2, 3], xticklabels=['Baseline', '4 held', 'Closed', '+ GC'], ylabel='Total process RSS (MiB)', title='Lower baseline, larger child increment')
for ax in axes:
    ax.set_ylim(bottom=0)
    ax.grid(axis='y', alpha=.2)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False, loc='upper left')
fig.suptitle('Per-Fork resources | M1 / TCP / 1,000 rows / 5 fresh processes per engine', fontsize=13)
fig.supxlabel('Medians and min-max ranges. Held RSS observed after 500 ms idle. RSS is not exclusive physical memory.', fontsize=9)
fig.savefig(a.output, dpi=160, metadata={'Date': None} if a.output.suffix == '.svg' else None)

# SVG path lines emitted by matplotlib contain trailing spaces.
if a.output.suffix == ".svg":
    a.output.write_text("\n".join(line.rstrip() for line in a.output.read_text().splitlines()) + "\n")
