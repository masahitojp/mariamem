from pathlib import Path
import json,sys
R=Path(__file__).resolve().parent
cells=json.loads((R/"summary.json").read_text())["cells"]
colors=['#94a3b8','#a78bfa','#10b981','#f59e0b','#64748b'];keys=['filesystem_prepared','memory_construct','execute_to_ready','ready_to_startup_end','api_host_other'];labels=['ファイル接続等','メモリ・module準備','guest実行→ready','ready後・診断読取','残りのAPI・観測処理']
html=['<!doctype html><html lang="ja"><meta charset="utf-8"><title>Current Fork stages</title><style>body{font:16px system-ui;max-width:1050px;margin:32px auto;padding:0 20px;color:#17243b}p{line-height:1.7}.bar{display:flex;height:36px;margin:8px 0 20px}.bar span{min-width:0}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}</style><h1>現在版のFork内訳・P4/P8</h1><p>同じショップ70ケース、各3組。観測なしのFork中央値はP4 26.4ms／P8 32.1ms。以下は観測ありの内訳です。特にP8は観測の影響が大きく、通常実行の精密な割合とは扱いません。</p><h2>Host側の分割（加算できる平均値）</h2>']
scale=max(cells[f'p{p}-on']['fork_ms']['mean'] for p in [4,8])
for par in [4,8]:
 c=cells[f'p{par}-on'];html.append(f'<b>P{par}: {c["fork_ms"]["mean"]:.2f}ms</b><div class="bar">')
 for k,label,color in zip(keys,labels,colors):
  v=c['host_ms'][k]['mean'];html.append(f'<span title="{label}: {v:.3f}ms" style="background:{color};width:{100*v/scale:.5f}%"></span>')
 html.append('</div>')
html.append('<p>'+ ' ／ '.join(f'<span style="color:{color}">■</span>{label}' for label,color in zip(labels,colors))+'</p><h2>guest内部（中央値・入れ子のため合算不可）</h2><table><tr><th>区間</th><th>P4 ms</th><th>P8 ms</th></tr>')
for k,label in [('server_init','サーバー初期化全体'),('common','↳ 共通初期化'),('plugin.InnoDB','↳ InnoDB'),('buffer_pool','　↳ buffer pool作成'),('innodb_open_recovery','　↳ 既存ファイル・回復処理'),('plugin.Aria','↳ Aria'),('myisam_key_cache','↳ MyISAM key cache')]:html.append(f'<tr><td>{label}</td><td>{cells["p4-on"]["guest_ms"][k]["p50"]:.3f}</td><td>{cells["p8-on"]["guest_ms"][k]["p50"]:.3f}</td></tr>')
html.append('</table><p>共通初期化が大きな残存区間。CPU・待ち・観測負荷は未分離。全ケースPASS、遅い回も保存。詳細・全実行・source identity・再集計方法は隣のREADME.mdを参照。</p></html>')
page='\n'.join(html)+'\n'
if '--check' in sys.argv:
 assert (R/'report.html').read_text()==page
 print('PASS: chart matches retained summary')
else:(R/'report.html').write_text(page)
