import pathlib,json,statistics,argparse,math,html
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();root=pathlib.Path(__file__).resolve().parent
records=json.loads((root/'observations.json').read_text());med=statistics.median
summary={'scope':'Single-Mac Pipe shop70-case suite, P8, five runs each. Setup through public Close included; compile/download/process launch excluded. Same-source16/8 comparison, pgmem dialect-port reference. All tails retained.','arms':{}}
selected={}
for arm in ('mariamem16','mariamem8','pgmem'):
 runs=[r for r in records if r['arm']==arm and r['repeat']>=0];assert len(runs)==5
 for r in runs:
  meta=r['trace']['meta'];spans=r['trace']['spans'];assert meta['read_cases']=='50' and meta['write_cases']=='20' and meta['test_exit']=='0'
  assert len([x for x in spans if x['kind']=='read'])==50 and len([x for x in spans if x['kind']=='write'])==20
  assert len([x for x in spans if x['kind']=='fork'])==21
  if arm!='pgmem':assert meta['active_mappings_after']=='0' and meta['innodb_buffer_pool_size']==str((8 if arm=='mariamem8' else 16)*2**20)
 ordered=sorted(runs,key=lambda r:r['trace']['elapsed_ms']);selected[arm]=ordered[2]
 times=[r['trace']['elapsed_ms'] for r in runs];cpu=[float(r['trace']['meta']['cpu_ms']) for r in runs]
 stages={}
 for kind in ('boot','import','snapshot','fork','sample','read','write','cleanup'):
  v=[x['end_ms']-x['start_ms'] for r in runs for x in r['trace']['spans'] if x['kind']==kind];stages[kind]={'p50_ms':med(v),'sum_ms_by_run':[sum(x['end_ms']-x['start_ms'] for x in r['trace']['spans'] if x['kind']==kind) for r in runs],'max_ms':max(v),'over100ms':sum(x>100 for x in v)}
 summary['arms'][arm]={'suite_ms':times,'median_ms':med(times),'min_ms':min(times),'max_ms':max(times),'process_cpu_ms':cpu,'median_cpu_ms':med(cpu),'stages':stages,'representative_repeat':selected[arm]['repeat']}
base=summary['arms']['mariamem16']['suite_ms'];candidate=summary['arms']['mariamem8']['suite_ms'];delta=[100*(c/b-1) for b,c in zip(base,candidate)]
summary['16_to_8']={'suite_paired_percent_changes':delta,'median_paired_percent':med(delta),'improved_runs':sum(c<b for b,c in zip(base,candidate))}
summary['sample_tails']=[{'arm':r['arm'],'repeat':r['repeat'],'over500ms':sum(x['kind']=='sample' and x['end_ms']-x['start_ms']>500 for x in r['trace']['spans']),'over800ms':sum(x['kind']=='sample' and x['end_ms']-x['start_ms']>800 for x in r['trace']['spans'])} for r in records if r['repeat']>=0]
text=json.dumps(summary,indent=2)+'\n'
if a.check:assert (root/'summary.json').read_text()==text
else:(root/'summary.json').write_text(text)
print(text)
# Standalone HTML embeds only each arm's median-total run; all raw observations stay in JSON.
data=json.dumps(selected,separators=(',',':')).replace('</','<\\/')
report='''
<!doctype html><html lang="ja"><meta charset="utf-8"><title>Issue88 · Pipe shop70 suite</title><style>body{font:15px system-ui;margin:32px;color:#17243b;max-width:1250px}h1{font-size:25px}small,p{line-height:1.6}.card{padding:18px;border:1px solid #cbd5e1;border-radius:10px;margin:18px 0}svg{width:100%;height:auto}table{border-collapse:collapse}td,th{padding:8px 15px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}.legend{display:flex;gap:12px;flex-wrap:wrap}.legend span::before{content:'■ ';color:var(--c)}label{display:block;margin:12px 0}code{background:#f1f5f9}</style>
<h1>Pipe · ショップ70テスト / 並列度8</h1><p>同一Mac、起動・schema/seed・Snapshotから全テストとpublic Closeまで。各5回。読み取り50件は共有DB、書き込み20件は独立Fork。共有DB用の1 Forkも両製品に含む。ダウンロード・コンパイル・プロセス起動は除外。公開ページのM3結果の再現値ではありません。</p>
<div id="summary"></div>
<label><input type="checkbox" id="zoom">各実行に合わせて横軸を拡大（既定は共通軸）</label><div class="legend" id="legend"></div>
<div id="charts"></div>
<p>各図は全体時間が中央の実行。準備行＋70ケースを同時実行スロットへ配置し、各区間を表示。バーにポインタを置くと処理・ケース・所要時間を表示します。pgmemのClose完了はmariamemの全資源処分完了と同じ保証ではありません。</p>
<script>const selected=DATA;const stats=STATS;const colors={boot:'#475569',import:'#7c3aed',snapshot:'#a855f7',fork:'#f59e0b',sample:'#06b6d4',read:'#22c55e',write:'#ef4444',cleanup:'#64748b'};const names={mariamem16:'mariamem ·16MiB',mariamem8:'mariamem ·8MiB',pgmem:'pgmem v1.18.2'};document.querySelector('#legend').innerHTML=Object.keys(colors).map(k=>`<span style="--c:${colors[k]}">${k}</span>`).join('');document.querySelector('#summary').innerHTML='<table><tr><th>条件</th><th>全体中央値</th><th>5回の範囲</th><th>CPU中央値</th><th>全5回のms</th></tr>'+Object.keys(names).map(k=>{const x=stats.arms[k];return `<tr><td>${names[k]}</td><td>${x.median_ms.toFixed(1)}ms</td><td>${x.min_ms.toFixed(1)}–${x.max_ms.toFixed(1)}ms</td><td>${x.median_cpu_ms.toFixed(1)}ms</td><td>${x.suite_ms.map(t=>t.toFixed(0)).join(" / ")}</td></tr>`}).join('')+'</table>';function draw(){document.querySelector('#charts').innerHTML='';let common=Math.max(...Object.values(selected).map(r=>r.trace.elapsed_ms));for(const [arm,r] of Object.entries(selected)){let limit=document.querySelector('#zoom').checked?r.trace.elapsed_ms:common;let spans=r.trace.spans, lanes={};for(const s of spans)(lanes[s.lane]??=[]).push(s);let tests=Object.entries(lanes).filter(([n])=>n.startsWith('Test')).map(([n,a])=>({n,a,start:Math.min(...a.map(s=>s.start_ms)),end:Math.max(...a.map(s=>s.end_ms))})).sort((a,b)=>a.start-b.start);let ends=Array(8).fill(0);for(const t of tests){let slot=ends.findIndex(x=>x<=t.start);if(slot<0)slot=ends.indexOf(Math.min(...ends));t.slot=slot;ends[slot]=t.end}let body='';for(let i=0;i<=5;i++){let x=120+i*196;body+=`<line x1="${x}" y1="22" x2="${x}" y2="258" stroke="#e2e8f0"/><text x="${x}" y="15" fill="#64748b" font-size="11">${(limit*i/5).toFixed(0)}ms</text>`}for(let row=0;row<9;row++)body+=`<text x="0" y="${45+row*25}" font-size="12">${row?'slot '+row:'setup/shared'}</text>`;const bar=(s,row)=>{const x=120+980*s.start_ms/limit,width=Math.max(.5,980*(s.end_ms-s.start_ms)/limit);return `<rect x="${x}" y="${30+row*25}" width="${width}" height="17" fill="${colors[s.kind]||'#999'}"><title>${s.lane}: ${s.name} · ${(s.end_ms-s.start_ms).toFixed(3)}ms</title></rect>`};for(const t of tests)for(const s of t.a)body+=bar(s,t.slot+1);for(const s of spans.filter(s=>!s.lane.startsWith('Test')))body+=bar(s,0);document.querySelector('#charts').innerHTML+=`<div class="card"><b>${names[arm]} · ${r.trace.elapsed_ms.toFixed(1)}ms · run ${r.repeat+1}</b><svg viewBox="0 0 1120 265" role="img">${body}</svg></div>
`}}document.querySelector('#zoom').onchange=draw;draw();
</script>'''.replace('DATA',data).replace('STATS',json.dumps(summary,separators=(',',':')))
if a.check:assert (root/'report.html').read_text()==report
else:(root/'report.html').write_text(report)
