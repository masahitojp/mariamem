"""Read-only replay with --check; retained observations are sufficient."""
from pathlib import Path
import hashlib,html,json,math,statistics as st,sys
P=Path(__file__).resolve().parent
records=json.loads((P/'observations.json').read_text());arms=['v062','current','pgmem'];summary={'arms':{},'comparison':{},'scope':'Single-Mac shop70, P8/cap9, Pipe, five rotating rounds; all tails included. TestMain boot through public cleanup; process elapsed separately.'}
assert len(records)==18
for arm in arms:
 allruns=[r for r in records if r['arm']==arm];assert len(allruns)==6
 assert {r['repeat'] for r in allruns}==set(range(-1,5))
 for r in allruns:
  assert r['accepted'] and r['exit_code']==0
  d=r['trace'];m=d['meta'];ss=d['spans']
  assert m['parallel']=='8' and m['fork_cap']=='9' and m['read_cases']=='50' and m['write_cases']=='20' and m['test_exit']=='0'
  for kind,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(s['kind']==kind for s in ss)==n
  assert len({s['lane'] for s in ss if s['kind']=='read'})==50 and len({s['lane'] for s in ss if s['kind']=='write'})==20
  assert all(0<=s['start_ms']<=s['end_ms']<=d['elapsed_ms'] for s in ss)
  if arm!='pgmem':
   assert m['active_mappings_after']=='0' and r['scratch_empty']
   assert m['innodb_buffer_pool_size']==m['innodb_buffer_pool_size_max']==str(16*2**20)
 runs=sorted((r for r in allruns if r['repeat']>=0),key=lambda r:r['repeat'])
 wall=[r['trace']['elapsed_ms'] for r in runs];cpu=[float(r['trace']['meta']['cpu_ms']) for r in runs];process=[r['process_elapsed_ms'] for r in runs]
 stages={}
 for kind in ['boot','import','snapshot','fork','sample','read','write','cleanup']:
  v=[s['end_ms']-s['start_ms'] for r in runs for s in r['trace']['spans'] if s['kind']==kind];sv=sorted(v)
  stages[kind]={'p50_ms':st.median(v),'p95_ms':sv[math.ceil(.95*len(v))-1],'max_ms':max(v),'over100ms':sum(x>=100 for x in v),'over500ms':sum(x>=500 for x in v)}
 summary['arms'][arm]={'suite_ms':wall,'median_ms':st.median(wall),'range_ms':[min(wall),max(wall)],'cpu_ms':cpu,'median_cpu_ms':st.median(cpu),'process_ms':process,'median_process_ms':st.median(process),'stages':stages,'sample_over500_by_run':[sum(s['kind']=='sample' and s['end_ms']-s['start_ms']>=500 for s in r['trace']['spans']) for r in runs]}
old=summary['arms']['v062'];now=summary['arms']['current'];pg=summary['arms']['pgmem']
summary['comparison']={'v062_to_pgmem_ratio_of_medians':old['median_ms']/pg['median_ms'],'current_to_pgmem_ratio_of_medians':now['median_ms']/pg['median_ms'],'current_vs_v062_percent_medians':100*(now['median_ms']/old['median_ms']-1),'v062_gap_ms':old['median_ms']-pg['median_ms'],'current_gap_ms':now['median_ms']-pg['median_ms'],'paired_current_vs_v062_percent':[100*(b/a-1) for a,b in zip(old['suite_ms'],now['suite_ms'])],'current_faster_pairs':sum(b<a for a,b in zip(old['suite_ms'],now['suite_ms']))}
summary['comparison']['median_paired_current_vs_v062_percent']=st.median(summary['comparison']['paired_current_vs_v062_percent'])
text=json.dumps(summary,indent=2)+'\n'
labels={'v062':'mariamem 0.6.2','current':'mariamem current','pgmem':'pgmem 1.18.2'};colors={'v062':'#6b7280','current':'#059669','pgmem':'#2563eb'}
maxwall=max(max(summary['arms'][a]['suite_ms']) for a in arms)
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><title>Shop70 / P8 comparison</title><style>body{font:16px system-ui;max-width:1050px;margin:36px auto;padding:0 20px;color:#17243b}p{line-height:1.7}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}.row{display:grid;grid-template-columns:180px 1fr 100px;align-items:center;margin:14px 0;gap:12px}.track{background:#f1f5f9;height:30px}.bar{height:30px}code{background:#f1f5f9}small{color:#475569}</style><h1>ショップ70テスト・並列8</h1><p>同一Mac・Go1.27.3・Pipe。読み取り50件＋独立した更新20件。起動・schema/seed・Snapshot・sample投入から最後のpublic Closeまでを含む。各5回、実行順を交代。コンパイル・ダウンロードは除外。共有reader用にもForkするため両製品21 Fork。公開サイトのM3/P8の204msとは別条件です。</p><h2>全体時間の中央値</h2>']
for arm in arms:
 d=summary['arms'][arm];width=100*d['median_ms']/maxwall;assert math.isfinite(width) and 0<=width<=100
 parts.append(f'<div class="row"><b>{labels[arm]}</b><div class="track"><div class="bar" style="background:{colors[arm]};width:{width:.6f}%"></div></div><span>{d["median_ms"]:.1f} ms</span></div>')
parts.append('<h2>全5回（除外なし）</h2><table><tr><th>条件</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>CPU中央値</th></tr>')
for arm in arms:
 d=summary['arms'][arm];parts.append('<tr><td>'+labels[arm]+'</td>'+''.join(f'<td>{v:.1f}</td>' for v in d['suite_ms'])+f'<td>{d["median_cpu_ms"]:.1f}</td></tr>')
parts.append('</table><p>単位ms。CPUはスイート中のプロセス全体のCPU時間。並列に重なるため経過時間とは異なります。</p><h2>工程別の中央値</h2><p>各工程の全観測をまとめた中央値。並列区間が重なるため、足して全体時間にはできません。</p><table><tr><th>工程</th>'+''.join('<th>'+labels[a]+'</th>' for a in arms)+'</tr>')
for kind in ['boot','import','snapshot','fork','sample','read','write','cleanup']:
 parts.append('<tr><td>'+kind+'</td>'+''.join(f'<td>{summary["arms"][a]["stages"][kind]["p50_ms"]:.3f}</td>' for a in arms)+'</tr>')
p4=json.loads((P/'p4-summary.json').read_text())
parts.append('</table><h2>P4との参考比較</h2><p>P4は前回の別時刻の測定です。同じ製品ソース・SQL・Goですが、並列度だけの因果効果とは断定しません。</p><table><tr><th>条件</th><th>P4 中央値 ms</th><th>P8 中央値 ms</th></tr>')
for arm in arms:
 parts.append(f'<tr><td>{labels[arm]}</td><td>{p4["arms"][arm]["median_ms"]:.1f}</td><td>{summary["arms"][arm]["median_ms"]:.1f}</td></tr>')
parts.append('</table><p>比較対象は同じアプリのSQL方言移植であり、同じDBエンジンではありません。pgmemはpublic Close成功まで、mariamemはmapping回収も確認します。終了保証は同等ではありません。単一ホストの小標本で、長い待ちも残しています。</p><p>入力SHA・全工程・制限は隣接するREADME.md、inputs.json、observations.jsonを参照してください。</p></html>')
page='\n'.join(parts)+'\n'
if '--check' in sys.argv:
 assert (P/'summary.json').read_text()==text
 assert (P/'report.html').read_text()==page
 for n,h in json.loads((P/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
 print('PASS: case census, cleanup, spans, summary, chart and checksums')
else:
 (P/'summary.json').write_text(text);(P/'report.html').write_text(page)
 print(json.dumps({a:{k:v for k,v in d.items() if k!='stages'} for a,d in summary['arms'].items()},indent=2))
 print(json.dumps(summary['comparison'],indent=2))
