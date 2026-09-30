#!/usr/bin/env python3
"""Render comparable baseline evidence; retain observations without process IDs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from final_latency import distribution


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline',type=Path);p.add_argument('orm',type=Path)
    p.add_argument('--output',type=Path,default=Path('benchmarks/v04-baseline.md'))
    a=p.parse_args(); b=json.loads(a.baseline.read_text());o=json.loads(a.orm.read_text())
    if not b['completed'] or not o['completed']: raise ValueError('incomplete measurements')
    b['startup']['snapshot_then_fork'] = distribution([sum(s['latency_seconds'] for s in t['report']['samples'] if s['case'] in ('snapshot','fork_first_sql')) for t in b['trials'] if t['kind']=='startup' and t['phase']=='measurement'])
    def f(d,scale=1):return f"{d['p50']*scale:.3f} / {d['p95']*scale:.3f}" if scale==1 else f"{d['p50']*scale:.1f} / {d['p95']*scale:.1f}"
    def d4(d,scale=1000):return ' | '.join(f"{d[k]*scale:.1f}" for k in ('min','p50','p95','max'))
    lines=['# v0.4 performance/resource baseline','',
           'v0.3.0 公開済み成果物と current main を固定ローカル環境で測定。製品・runtime・cache・API・Snapshot/Fork の挙動は変更していない。', '',
           f"製品ソース: `{b['environment']['commit']}`。ブランチ: `v0.4/baseline`。測定日: 2026-10-01。",
           '固定参照: MacBook Air M1、16 GiB、macOS 27.0 (26A428) arm64、Go 1.26.8、Python 3.14.7。',
           '公開 native / wheel の SHA256 は GitHub Release の digest と照合済み。公開 guest に既存の段階計測マーカーがあり、追加 instrumentation は不要だった。', '',
           '## 再現・比較契約','',
           '公開 v0.3.0 native と wheel を使う。Go は main の public API、SQLAlchemy は installed wheel の consumer 経路。両経路を混同しない。',
           '各コマンドを順に単独実行し、回帰チェックを並行させない。将来の spike も同じ fixture、境界、回数、toolchain、sampling を使い、ソース・成果物ハッシュと環境差を記録する。', '',
           '```sh',
           'GOTOOLCHAIN=go1.26.8 /path/to/python benchmarks/v04_baseline.py \\\n  --native-dir /path/to/native --runs 30 --scaling-runs 10 \\\n  --json benchmarks/results/v04-baseline.json',
           '# installed v0.3.0 wheel + SQLAlchemy/PyMySQL/pytest; clear native overrides',
           '/path/to/python benchmarks/v04_orm.py --runs 3 --json benchmarks/results/v04-orm.json',
           '/path/to/python benchmarks/v04_report.py benchmarks/results/v04-baseline.json \\\n  benchmarks/results/v04-orm.json --output benchmarks/v04-baseline.md','```','',
           '生データは ignored results に保存。比較用の PID を除いた観測値・分布・ハッシュは [v04-baseline-values.json](v04-baseline-values.json)。失敗・遅い試行の除外はしない。',
           'startup は2 warmup + 30独立 Go プロセス。各プロセスで fresh Start、1,000行 fixture 作成、cold Snapshot、prepared Fork を行う。OS/AOT/file cache は flush しない。',
           'fixture は既存 InnoDB benchmark_rows (INT PK / VARCHAR(64)、32文字 payload)、1,000行 batch、commit、COUNT 確認。Snapshot は SQL 接続の切断 acknowledgement 後に開始し、source を消費する。',
           'API 復帰と最初の SQL 成功は別の境界。Start→SELECT 1 は空 DB、Start→fixture はschema/seed/COUNTを含む。prepared Fork→COUNT は fixture preparation を除外する。Snapshot の時間を Fork に暗黙に含めない。', '',
           '## 起動 (ms)','', '| 境界 | n | min | p50 | p95 | max |','|---|---:|---:|---:|---:|---:|']
    for key,label in [('start_first_sql','Start→SELECT 1'),('start_seeded','Start→1,000行 fixture ready'),('snapshot','cold Snapshot 作成'),('fork_first_sql','prepared Fork→COUNT')]:
        lines.append(f"| {label} | 30 | {d4(b['startup'][key])} |")
    lines.append(f"| Snapshot 作成 + Fork→COUNT (paired sum、seed除外) | 30 | {d4(b['startup']['snapshot_then_fork'])} |")
    for key,label in [('start_first_sql','Start API 復帰'),('fork_first_sql','Fork API 復帰')]:
        lines.append(f"| {label} | 30 | {d4(b['api_return'][key])} |")
    lines += ['', '## 孤立 DB scaling','',
              '各 concurrency は1 warmup + 10独立試行、round-robin。1,000行 prepared snapshot の独立 Fork を同時に開始し、全 DB の COUNT が成功するまで保持。G(0) は live runtime のない Go snapshot holder、G(n) は host + n runtimes。',
              'CPU は G(0)→all-ready カウンタ取得の host + runtime 累積 CPU 差。最終 SQL 後のカウンタ収集も含む。teardown・fixture preparation は含まない。sampling 50 ms + scan overhead。',
              '主メモリは process-tree physical footprint。shared pages/OS accounting の影響があり、exclusive allocation ではない。peak は観測した最大値。Close 後の host heap retention と runtime 残留を分ける。', '',
              '| DBs | ready ms p50/p95 | CPU s p50/p95 | CPU s/DB p50/p95 | incremental MiB p50/p95 | MiB/DB p50/p95 |',
              '|---:|---:|---:|---:|---:|---:|']
    for g in b['scaling']['groups']:
        lines.append(f"| {g['workers']} | {f(g['group_ready_seconds'],1000)} | {f(g['combined_cpu_seconds'])} | {f(g['combined_cpu_seconds_per_db'])} | {f(g['incremental_primary_bytes'],1/2**20)} | {f(g['average_incremental_bytes'],1/2**20)} |")
    one, sixteen = b['scaling']['groups'][0], b['scaling']['groups'][-1]
    lines += ['', f"CPU/DB の p50 は ×1 の{one['combined_cpu_seconds_per_db']['p50']:.3f} sから ×16 の{sixteen['combined_cpu_seconds_per_db']['p50']:.3f} sへ{sixteen['combined_cpu_seconds_per_db']['p50']/one['combined_cpu_seconds_per_db']['p50']:.2f}倍。CPU合計は{sixteen['combined_cpu_seconds']['p50']/one['combined_cpu_seconds']['p50']:.1f}倍。8 CPUの同一環境での実測であり、原因の帰属はこの表からは断定しない。", '', '| DBs | G(0) MiB p50/p95 | G(n) total MiB p50/p95 | peak total MiB p50/p95 | after Close MiB p50/p95 | after Close − G(0) MiB p50/p95 |', '|---:|---:|---:|---:|---:|---:|']
    for g in b['scaling']['groups']:
        lines.append(f"| {g['workers']} | "+' | '.join(f(g[k],1/2**20) for k in ('baseline_primary_bytes','ready_primary_bytes','group_peak_primary_bytes','after_close_primary_bytes','after_close_minus_baseline_bytes'))+' |')
    batches=[t['report']['samples'][0] for t in b['trials'] if t['kind']=='batch' and t['phase']=='measurement']
    assert all(len(s['after_close']['members'])==1 for s in batches)
    gap_count=sum(len(s['memory_sampling_gaps']) for s in batches)
    lines += ['', f'起動中のカウンタ scan は {gap_count} 回 temporarily unavailable。G(0)/ready/after-Close の必須取得は全試行成功。欠損は0として補完せず、sampled peak は過小観測の可能性を含む。PIDを除いたtimelineと欠損時刻も比較JSONに保持。']
    lines += ['', '40/40 measurement batches 成功。全 Close 後に runtime descendants は0。長寿命 host の leak soak は測っていない。', '',
              '## SQLAlchemy representative workload','',
              'v0.3 dogfood の `test_03_update_commit_and_delete` を直接呼ぶ。User/Address schema、1組の seed、通常の QueuePool と SQLAlchemy Session を利用。relationship read/join、update+commit、delete+commit、最終 COUNT を両経路で同じように実行。',
              'fresh は Start + schema/seed、prepared は Start + 同じ schema/seed + Snapshot をスイート冒頭に1回行い、各 test で Fork。両方とも fixture COUNT確認、同じ CRUD、pool dispose、WaitDisconnected、Close、PID消滅・一時ディレクトリ削除の確認を含む。prepared setup/Snapshot と最終 Snapshot cleanup は suite total に含む。',
              '各サイズ3スイート。mode順序を交互に切り替え、1 test warmup は集計から除外。pytest runner overhead は含まない。SQLAlchemy 経路は Python wrapper + 別 Go host であり、Go core の起動値とは直接比較しない。', '',
              '| tests | mode | suite s p50/p95 | setup s p50/p95 | per-test ready ms p50/p95 | CRUD ms p50/p95 |', '|---:|---|---:|---:|---:|---:|']
    suites=[]
    for n in (10,50,100):
        for mode in ('start','fork'):
            rows=[s for s in o['suites'] if s['phase']=='measurement' and s['tests']==n and s['mode']==mode]
            assert len(rows)==3 and all(len(s['samples'])==n for s in rows)
            row=dict(tests=n,mode=mode,suite=distribution([s['suite_seconds'] for s in rows]),setup=distribution([s['setup_seconds'] for s in rows]),
                     ready=distribution([v['ready_seconds'] for s in rows for v in s['samples']]),workload=distribution([v['workload_seconds'] for s in rows for v in s['samples']]))
            suites.append(row)
            lines.append(f"| {n} | {mode} | {f(row['suite'])} | {f(row['setup'])} | {f(row['ready'],1000)} | {f(row['workload'],1000)} |")
    lines += ['', f"packages: {o['packages']}。全18 measurement suites / 960 isolated tests成功。MariaDB: `{o['suites'][-1]['server_version']}`。", '',
              '## Architecture attribution','',
              '通常測定とは別に5独立試行で既存 guest/host stages を取得。以下は p50/p95 ms、nested scopes は重なるので合計しない。小標本は概算の帰属用。', '',
              '| cost / boundary | Start | Fork |','|---|---:|---:|']
    stages=b['stage_summary']
    def stage(case,scope,name):
        r=next(r for r in stages if r['case']==case and r['scope']==scope and r['stage']==name)
        return f(dict(p50=r['p50_seconds'],p95=r['p95_seconds']),1000)
    for label,scope,name in [('native resolution/verification','api_startup','native_resolved'),('host process spawn','host','spawn_returned'),('guest MariaDB init','guest','server_init_complete'),('guest bootstrap/ready','guest','bootstrap_complete'),('restore copy','guest','restore_complete'),('pre-main/runtime/ready envelope residual','startup_envelope','outside_recorded_guest_interval')]:
        lines.append('| '+label+' | '+' | '.join(stage(c,scope,name) for c in ('start_first_sql','fork_first_sql'))+' |')
    lines.append('| host snapshot validation | — | '+stage('fork_first_sql','host','metadata_snapshot_validated')+' |')
    residuals = {}
    for case in ('start_first_sql','fork_first_sql'):
        values=[]
        for t in b['trials']:
            if t['kind']!='attribution': continue
            sample=next(s for s in t['report']['samples'] if s['case']==case)
            z=sample['per_db'][0] if sample.get('per_db') else sample
            trace=z['stage_timings']
            api={e['name']:e['offset_ns'] for e in trace['api_startup']['events']}
            host={e['name']:e['offset_ns'] for e in trace['host']['events']}
            # Disjoint duration scopes; retain runtime-ready envelope as one bucket.
            accounted=(api['native_resolved']-api['begin'] + host['metadata_snapshot_validated']-host['begin'] + host['spawn_returned']-host['spawn_begin'] + host['guest_ready']-host['spawn_returned'])/1e9
            values.append(z['latency_seconds']-accounted)
        residuals[case]=distribution(values)
    lines.append('| remaining caller/host/client intervals | '+f(residuals['start_first_sql'],1000)+' | '+f(residuals['fork_first_sql'],1000)+' |')
    lines += ['', 'runtime envelope residual は host spawn-return→guest-ready から guest main→ready-prepared の実測 duration を引いた値。Wasmer/WASIX/CRT・static constructors・ready delivery・scheduling が含まれ、runtime creation の専用 timer は存在しない。',
              'guest main→restore開始、open準備、bootstrap、host wire/API handoff、client handshake/COUNT は残余の小さい区間として JSON に保持。MariaDB init は InnoDB を含み、個別エンジンの所有コストは未帰属。',
              'host/guest clock の絶対原点は合わせない。CPU/メモリを guest init/restore の各境界に割り当てる instrumentation はないため、段階別 memory/CPU の精度は主張しない。Snapshot export ack はshutdown+export、publish はcopy+inventory/hashを含む。', '',
              '## 回帰確認','', 'canonical `scripts/verify.py check`: Go tests/vet と `go test -race ./benchmarks/goisolation`、Python 368 passed / 3 skipped、public-source check 成功。`git diff --check` 成功。実 DB の COUNT、Snapshot consumption、session isolation、runtime cleanup は各 benchmark の既存 correctness checks も通過。',
              '最初の予備測定は回帰チェックと一部並行したため不採用。採用値は単独再測定。既存の未追跡 npm ファイルが public-source 検査を妨げたため、検査中だけ退避し、その後復元した。', '',
              '### Current bottlenecks','']
    # Ranked within commensurate categories; time and bytes cannot share one ranking.
    rows=[r for r in stages if r['case']=='fork_first_sql' and (r['scope'],r['stage']) in [('guest','restore_complete'),('guest','server_init_complete'),('host','metadata_snapshot_validated'),('api_startup','native_resolved'),('startup_envelope','outside_recorded_guest_interval')]]
    rows.sort(key=lambda r:r['p50_seconds'],reverse=True)
    lines += ['Fork の時間コストを実測 p50 順に並べる（独立scopeのため合計値ではない）:', '']
    for i,r in enumerate(rows,1):lines.append(f"{i}. {r['scope']} / {r['stage']}: {r['p50_seconds']*1000:.1f} ms。")
    g=b['scaling']['groups'][-1]
    lines += ['', f"Start の MariaDB init: {stage('start_first_sql','guest','server_init_complete')} ms。Snapshot 作成: {f(b['startup']['snapshot'],1000)} ms。", f"資源の最大実測規模は ×16: ready total {f(g['ready_primary_bytes'],1/2**20)} MiB、CPU {f(g['combined_cpu_seconds'])} s。時間とbyteを単一順位にはしない。", '', '### Candidate v0.4 KPIs','',
              '以下は比較対象の現状値（p50/p95）。改善の合格閾値は未設定。', '', '| KPI | current baseline |','|---|---:|',
              '| single DB Start→SELECT 1 | '+f(b['startup']['start_first_sql'],1000)+' ms |',
              '| Start→1,000行 fixture ready | '+f(b['startup']['start_seeded'],1000)+' ms |',
              '| prepared Fork→COUNT | '+f(b['startup']['fork_first_sql'],1000)+' ms |',
              '| cold Snapshot | '+f(b['startup']['snapshot'],1000)+' ms |',
              '| ×1 incremental memory/DB | '+f(b['scaling']['groups'][0]['average_incremental_bytes'],1/2**20)+' MiB |',
              '| ×16 incremental memory/DB | '+f(g['average_incremental_bytes'],1/2**20)+' MiB |',
              '| ×16 ready total / peak total | '+f(g['ready_primary_bytes'],1/2**20)+' (ready), '+f(g['group_peak_primary_bytes'],1/2**20)+' MiB |',
              '| ×16 group-ready | '+f(g['group_ready_seconds'],1000)+' ms |',
              '| ×16 CPU total / per DB | '+f(g['combined_cpu_seconds'])+' (total), '+f(g['combined_cpu_seconds_per_db'])+' s |',
              '| ×16 after Close footprint / increment | '+f(g['after_close_primary_bytes'],1/2**20)+' (total), '+f(g['after_close_minus_baseline_bytes'],1/2**20)+' MiB |',
              '| runtime descendants after Close | 0 (40/40 batches) |']
    for s in suites:
        if s['tests']==100:lines.append('| SQLAlchemy 100 tests '+s['mode']+' suite total | '+f(s['suite'])+' s |')
    lines += ['', '### Architecture questions','',
              '- 外部 runtime 境界を除く spike は、pre-main envelope と CPU、per-DB footprint のどこを削減できるか。MariaDB init の実測部分はどれだけ残るか。',
              '- CoW/shared prepared state は、同じ fixture・独立 DB semantics で ×1/4/8/16 の incremental footprint と total peak を下げられるか。初回書き込み後のコストはどう変わるか。',
              '- runtime sharing は CPU/DB と ×16 group-ready、Close 後の保持量を改善するか。1 DB の failure/teardown が他 DB に波及しないか。',
              '- restore-path redesign は restore copy と snapshot validation、Snapshot publish の各コストをどれだけ下げるか。検証・mutation拒否・Snapshot source consumption を保てるか。',
              '- 同じ SQLAlchemy CRUD の10/50/100 suitesで、setup+Snapshotを含む総時間とcleanupまで改善するか。prepared手法の償却がどのサイズから現れるか。',
              '- 長寿命 host の反復作成/Close でも runtime 残留0を維持し、host retained memory が増え続けないか。',
              '', '採用 architecture は未選択。上記の実測境界・資源指標で個別 spike を比較する。','']
    a.output.write_text('\n'.join(lines))
    startup=[dict(case=s['case'],latency_seconds=s['latency_seconds'],**({'api_return_seconds':s['api_return_seconds']} if 'api_return_seconds' in s else {})) for t in b['trials'] if t['kind']=='startup' and t['phase']=='measurement' for s in t['report']['samples'] if s['case'] in b['startup']]
    scaling=[{k:v for k,v in s.items() if k in ('workers','group_ready_seconds','combined_cpu_seconds','host_cpu_seconds','runtime_cpu_seconds','incremental_primary_bytes','average_incremental_bytes','group_peak_primary_bytes','incremental_peak_primary_bytes','cleanup_seconds')} | {state:{k:v for k,v in s[state].items() if k!='members'} for state in ('baseline','ready','after_close')} for s in batches]
    evidence=dict(schema_version=1,source_commit=b['environment']['commit'],environment=b['environment'],native_manifest=b['native_manifest'],artifact_sha256=dict(native_archive='c16d99c313f8464c6318bbefd9b26d74abb6500ca2f6fbe47a05420a0301db1a',wheel='e2d44afe877c1ad74b8f83529035df55859102d44f4955721c79ef9b8ed6cf4f'),remaining_intervals=residuals,settings=b['settings'],startup=b['startup'],api_return=b['api_return'],scaling=b['scaling'],stage_summary=stages,orm_summary=suites,startup_observations=startup,scaling_observations=scaling,memory_timelines=[dict(workers=s['workers'],samples=[{k:v for k,v in m.items() if k!='members'} for m in s['memory_samples']],gaps=[dict(at_seconds=g['at_seconds'],error='process counters temporarily unavailable') for g in s['memory_sampling_gaps']]) for s in batches],orm_suites=o['suites'],packages=o['packages'],orm_workload_sha256=o['workload_sha256'],wheel_origin=dict(asset=o['wheel_origin']['url'].rsplit('/',1)[-1],archive_info=o['wheel_origin'].get('archive_info')),harness_sha256=b['harness_sha256'],orm_harness_sha256=o['harness_sha256'],binary_sha256=b['binary_sha256'],helper_sha256=b['helper_sha256'],raw_sha256={a.baseline.name:hashlib.sha256(a.baseline.read_bytes()).hexdigest(),a.orm.name:hashlib.sha256(a.orm.read_bytes()).hexdigest()})
    a.output.with_name(a.output.stem+'-values.json').write_text(json.dumps(evidence,indent=2)+'\n')

if __name__=='__main__':main()
