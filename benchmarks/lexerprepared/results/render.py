from pathlib import Path
import json,statistics,xml.etree.ElementTree as ET
p=Path(__file__).resolve().parent;s=json.loads((p/'summary.json').read_text())
def chart(title,metric):
 groups=['fresh-p1','fresh-p4','fork-p1','fork-p4']
 def vals(c):
  return [x['child_median_ms']['start_or_fork'] if metric=='api' else x[metric] for x in c['processes']]
 limit=max(v for c in s['cells'].values() for v in vals(c))*1.1
 x=lambda v:150+v/limit*760
 svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 365" role="img">'
 for i in range(5):
  xx=x(limit*i/4);svg+=f'<line x1="{xx}" x2="{xx}" y1="15" y2="320" stroke="#ddd"/><text x="{xx}" y="348" text-anchor="middle">{limit*i/4:.0f} ms</text>'
 for i,g in enumerate(groups):
  svg+=f'<text x="0" y="{55+i*75}">{g}</text>'
  for j,arm in enumerate(['original','prepared']):
   c=s['cells'][arm+'-'+g];values=vals(c);m=statistics.median(values);y=40+i*75+j*24;col=['#737c8b','#00857b'][j]
   svg+=f'<line x1="{x(min(values))}" x2="{x(max(values))}" y1="{y}" y2="{y}" stroke="{col}"/>'
   for rep,v in enumerate(values):svg+=f'<circle cx="{x(v)}" cy="{y+(rep-2)*1.2}" r="4" fill="{col}"><title>{arm}, rep{rep}: {v:.3f} ms</title></circle>'
   svg+=f'<line x1="{x(m)}" x2="{x(m)}" y1="{y-8}" y2="{y+8}" stroke="{col}" stroke-width="3"/>'
 svg+='</svg>';ET.fromstring(svg)
 return '<section><h2>'+title+'</h2>'+svg+'</section>'
doc='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>字句解析表の事前生成・試作比較</title><style>body{font:16px system-ui;max-width:1050px;margin:32px auto;padding:0 20px;background:#f6f8fb;color:#162a3b}h1{font-size:28px}h2{font-size:21px}section{background:white;border:1px solid #dfe4ed;border-radius:12px;margin:20px 0;padding:20px}svg{width:100%;height:auto;font:14px system-ui}p{line-height:1.7}</style><h1>字句解析表を毎回作る → 準備済みの表を使う</h1><p>Go Pipe・1,000行・48ケース・各条件5ペア。点は全観測、太い線は中央値。灰色=元の処理、緑=試作。</p><p>単一Macの実験用Go overlay。製品への採用前。逐次Forkはペア差の中央値で2.20ms短縮（5/5改善）。並列4の約800ms SQL遅延は両側2件ずつあり、除外していません。</p>'''
doc+=chart('準備から最終Closeまでの全体時間','suite_ms')+chart('全体のCPU時間','cpu_ms')+chart('子あたりStart / Fork時間（各実行の中央値）','api')
doc+='<p>両側は同じ製品・同じClose契約です。全体比較は通常実行で行い、全表一致・追加SQL・UNDO診断は別枠です。生メモリ量やRSSの改善は測っていません。</p><p><a href="README.md">詳細と制限</a> · <a href="summary.json">集計JSON</a> · <a href="children.csv">子単位CSV</a></p></html>'
(p/'report.html').write_text(doc);print('Three SVG plots validated')
