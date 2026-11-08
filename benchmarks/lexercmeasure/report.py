"""Standalone HTML from the replayed summary; no new measurement or filtering."""
import argparse,html,json,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent/'results');parser.add_argument('--check',action='store_true');args=parser.parse_args()
R=args.directory
s=json.loads((R/'summary.json').read_text());inputs=json.loads((R/'inputs.json').read_text());cells=s['cells']
style='''body{font:16px/1.65 system-ui,sans-serif;margin:0;background:#f4f6fa;color:#18232d}main{max-width:1120px;margin:auto;padding:38px 28px}h1{font-size:32px;line-height:1.3}h2{font-size:22px;margin-top:38px}.card{background:white;padding:22px;border:1px solid #dce2e8;border-radius:12px;margin:20px 0}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:8px 12px;border-bottom:1px solid #e5e9ee;text-align:right}th:first-child,td:first-child{text-align:left}.muted{color:#52616b;font-size:14px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}svg{width:100%;height:auto}.base{color:#667587}.candidate{color:#087fa0}code{font-size:13px;overflow-wrap:anywhere}a{color:#087fa0}@media(max-width:750px){.grid{grid-template-columns:1fr}main{padding:22px 12px}table{font-size:13px}th,td{padding:6px}}'''
def cell(arm,mode,p,obs='off'):return cells[f'{arm}-{mode}-p{p}-{obs}']
def num(v):return f'{v:.2f}'
def chart(mode,p,metric):
 a,b=[cell(x,mode,p) for x in ['baseline','candidate']]
 values=[x['child']['start_or_fork']['p50'] if metric=='start' else x['process']['batch_ms']['p50'] for x in [a,b]];scale=300/max(values)
 title=('Start/Fork p50' if metric=='start' else '48子 batch wall p50')+' — '+mode.upper()+f' P{p}'
 svg=f'<svg viewBox="0 0 500 120" role="img" aria-label="{title}"><text x="0" y="20" font-size="16" fill="#18232d">{title}</text>'
 for i,(v,label,color) in enumerate(zip(values,['採用済み','実C候補'],['#667587','#087fa0'])):
  y=43+i*37;svg+=f'<text x="0" y="{y+18}" font-size="14">{label}</text><rect x="80" y="{y}" width="{v*scale:.2f}" height="25" rx="3" fill="{color}"/><text x="{90+v*scale:.2f}" y="{y+18}" font-size="14">{v:.2f} ms</text>'
 return svg+'</svg>'
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Prepared lexer — actual C measurement</title><style>'+style+'</style><main>', '<h1>字句解析表の事前生成：実C版の計測</h1>', '<p>同じMac・Go1.27.3・Pipe・1000行のseed・48子を使用。採用済み実装と実C候補を交互に3回ずつ実行しました。全観測・尾部を保持しています。</p>', '<p class="muted">通常実行のバイナリはGo試作オーバーレイなし。観測付き実行は別バイナリです。CI実ゲスト受入は両OSでPASS、性能値はこのMacだけの結果です。</p>', '<div class="card grid">']
for p in [1,4]:parts.append(chart('fork',p,'start'))
for p in [1,4]:parts.append(chart('fork',p,'batch'))
parts+=['</div><div class="card"><h2>通常実行</h2><table><tr><th>条件</th><th>Start/Fork p50<br>旧 → 候補 (ms)</th><th>48子 batch wall p50<br>旧 → 候補 (ms)</th><th>batch CPU p50<br>旧 → 候補 (ms)</th><th>process peak RSS p50<br>旧 → 候補 (MiB)</th></tr>']
for mode in ['fresh','fork']:
 for p in [1,4]:
  a,b=[cell(x,mode,p) for x in ['baseline','candidate']]
  pairs=[(a['child']['start_or_fork']['p50'],b['child']['start_or_fork']['p50'])]+[(a['process'][k]['p50']/unit,b['process'][k]['p50']/unit) for k,unit in [('batch_ms',1),('batch_cpu_ms',1),('lifetime_max_rss_bytes',1048576)]]
  parts.append(f'<tr><td>{mode.upper()} P{p}</td>'+''.join(f'<td>{x:.2f} → {y:.2f}</td>' for x,y in pairs)+'</tr>')
parts+=['</table><p class="muted">Start/Forkは各cell144子のp50。バッチ/CPU/RSSは3プロセスのp50。RSSはプロセスの生涯最大値で、子1個の保持量ではありません。Freshは毎子seed作成、Forkは準備済みseedを分離して利用します。</p></div>','<div class="card"><h2>3ペアそれぞれの変化</h2><table><tr><th>条件</th><th>Start/Fork p50変化率</th><th>batch wall変化率</th><th>batch CPU変化率</th></tr>']
for k,pairs in s['pairs'].items():
 if not k.endswith('off'):continue
 parts.append('<tr><td>'+k+'</td>'+''.join('<td>'+', '.join(f'{r[field]:+.1f}%' for r in pairs)+'</td>' for field in ['start_p50_change_pct','batch_ms_change_pct','batch_cpu_ms_change_pct'])+'</tr>')
parts+=['</table><p class="muted">負値が短縮。小標本であり、交互実行でも温度・OSスケジューリング・SQL尾部の交絡は残ります。</p></div>','<div class="card"><h2>Forkの内訳（観測付き）</h2><table><tr><th>工程 p50 (ms)</th><th>P1 旧 → 候補</th><th>P4 旧 → 候補</th></tr>']
for k,label in [('memory_prepare','メモリ準備'),('server_init','サーバー初期化'),('routine_schema','routine構造'),('filesystem_handles','子FS・ファイル接続'),('bootstrap_connection','内部接続'),('host_outside_startup','startup外のhost'),('execution_residual','実行開始・受信などの残り'),('guest_other','その他guest'),('after_ready','ready後のhost')]:
 parts.append('<tr><td>'+label+'</td>'+''.join('<td>'+ ' → '.join(num(cell(a,'fork',p,'on')['child'][k]['p50']) for a in ['baseline','candidate'])+'</td>' for p in [1,4])+'</tr>')
parts+=['</table><p class="muted">工程p50の和は全体p50になりません。各子の内訳は実測Fork時間へ一致することを再生で検査しています。server_init内部のcommon/InnoDB/Ariaは今回分離していません。</p><h3>観測によるFork p50の変化</h3><p>']
parts.append(' / '.join(k+f': {v["off_ms"]:.2f} → {v["on_ms"]:.2f} ms ({v["change_pct"]:+.1f}%)' for k,v in s['observer_effect'].items()))
parts+=['</p></div><div class="card"><h2>尾部を残した分布</h2><table><tr><th>条件</th><th>Fork p95 (ms)</th><th>Fork &gt;100ms</th><th>COUNT/SUM &gt;100ms</th><th>UPDATE &gt;100ms</th></tr>']
for arm in ['baseline','candidate']:
 for p in [1,4]:
  c=cell(arm,'fork',p)['child'];parts.append(f'<tr><td>{arm} P{p}</td><td>{c["start_or_fork"]["p95"]:.2f}</td><td>{c["start_or_fork"]["over_100ms"]}/144</td><td>{c["count_sum"]["over_100ms"]}/144</td><td>{c["update"]["over_100ms"]}/144</td></tr>')
parts+=['</table><p class="muted">特定閾値を超えた子やバッチを除外していません。SQL尾部の所有者を観測していないため、UNDO待ちとは断定しません。</p></div>', '<p class="muted">Harness source: <code>'+html.escape(inputs['source_commit'])+'</code><br>Host binding: <code>'+inputs['plan']['host_binding_source_commit']+'</code><br>C origin: <code>'+inputs['plan']['c_source_commit']+'</code><br>Candidate guest: <code>'+inputs['plan']['candidate_guest_sha256']+'</code></p><p><a href="summary.json">集計JSON</a> · <a href="children.csv">全primary子のCSV</a> · <a href="README.md">結論・条件</a></p></main></html>']
data='\n'.join(parts)
if args.check:assert (R/'report.html').read_text()==data
else:(R/'report.html').write_text(data)
