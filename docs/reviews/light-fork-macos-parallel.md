# v0.5.1 macOS Light Fork — serial and four workers

2026-10-17。追加計測は完了。**mariamemのFork呼び出しと子DB処理は並行に進み、
今回の4子区間は約269→96ms、準備から全Closeまで約523→350msになった。**
Humanは提示していたLinux/pgmem比較も直列だったと確認した。このため、以前の比較を
「pgmemだけ並列だったための差」とは解釈しない。

## Human Review

**次は、既存のSnapshot走査統合の設計レビューへ戻ることを推薦する。**
並列利用は既存機能で成立しており、今回新たなruntime修正は不要。
Snapshotは直列・並列とも約193msで、並列全体約350msの約55%を占める。
子を並列化しても消えない共通費用なので、走査統合を検討する根拠は維持される。

**最も強い反論は、並列時は個々のFork呼び出しの所要時間が増え、4倍の高速化ではない点。**
4子Forkの操作時間の和は208→298ms、SQLの和も27→42msへ増えた。
待ち・CPUやmemory資源の競合等への帰属は今回していない。それでも4子全体の実経過時間は
全10対で短くなった。個々の合算時間と、利用者が待つ全体時間を混同しない。
ピーク資源と他platformでの並列性能は今回の結論に含めない。

## Fixed inputs and scope

- Released v0.5.1 source_commit `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、tag_object_sha `089b32e09608902f6d46e7ab9527d09922dcf065`。既存のtyped pin／git_identityで確認。
- Apple M1、macOS27.0.1 arm64、Go1.26.8、CGO=0、`-p 1 -trimpath -buildvcs=true`。
- cleanな独立cloneからbuildし、実binaryのVCS revision／modified=falseを照合。benchmark mainだけのoverlayを明示し、operation start/end時刻と最終mapping countersを追加。
- 同じobserver binaryでworkers=1／4を交互に各10回。trace、CPU profile、resource samplerは使わず、GOGC／GOMEMLIMIT／GOMAXPROCSの外部overrideは除去。別の無変更binary校正ではない。
- 既存Go Light：1表・1024-byte行1個、4子、app-connections。準備とSnapshotは1回、その後に4子が各々Fork→SQL→切断待ち→Close。並列時はgoroutine worker4個。
- SQLは既存のcount/point、別application接続からのcommit可視性、rollback、子の初期state確認を維持。各子の接続poolは別。全子完了後に基準Close。
- host／guest／生成Go／public API／GC設定／失敗oracleに変更なし。Linux、pgmem、Python、大規模fixture、ピークmemoryは今回測っていない。

## Elapsed time — main comparison

各10回の中央値、ms。各行の中央値の和は全体中央値に一致しない。

| 区間 | 直列1 worker | 並列4 workers |
| --- | ---: | ---: |
| 元DB起動・データ準備 | 59.42 | 57.80 |
| Snapshot | 193.45 | 193.37 |
| **4子のFork→SQL→切断待ち→Closeの実経過時間** | **269.03** | **96.32** |
| 基準Close | 0.001 | 0.001 |
| **product全体** | **522.62** | **349.76** |
| 診断GC等も含むharness全体 | 523.13 | 350.35 |

群中央値比で4子区間64.2%短縮（約2.79倍）、product全体33.1%短縮。
自然な10対の全体変化は−39.6%〜−27.6%、すべて並列側が短かった。
性能比の一般化、10試行を超えるtail分布、4倍のscalingは保証しない。

並列時のproductは既存harnessの定義どおり、準備＋Snapshot＋child-loop wall＋基準Close。
重なった操作の時間を足して全体時間としない。直列側は既存の各operation合計。
child-loop wallと診断込み全体も両群で保存し、境界の差を追跡できるようにした。

## Actual overlap, not only the workers flag

全operationの開始・終了offsetから試行ごとに確認した：

| 観測 | 直列10回 | 並列10回 |
| --- | --- | --- |
| 子workflowの重なり最大 | 毎回1 | 毎回4 |
| Fork呼び出しの重なり最大 | 毎回1 | 毎回4 |
| ready後〜Close開始前の子DBの重なり最大 | 毎回1 | 3〜4 |
| mutation（commit/rollback等）区間の重なり最大 | 毎回1 | 2〜4 |

ready後〜Close開始前は保守的な存在区間で、正確なactive-object counterではない。
区間の重なりは処理が並行に進むことの証拠で、同時に実行するhardware命令数やcore数の証明ではない。
個別operation時間の和は次のとおり。並列のwallとして使わない：

| 4子分のoperation合計 | 直列 | 並列 |
| --- | ---: | ---: |
| Fork呼び出し | 208.41 | 298.32 |
| SQL | 26.75 | 42.32 |
| SQL切断待ち＋Close | 34.14 | 37.85 |

今回のClose区間もWaitDisconnectedを含む。純粋なDB Closeやpgmem非同期解放との
比較値ではない。前回の[内訳計測](light-fork-macos-breakdown.md)は直列の別cohortとして保持する。

## Impact on the proposed optimization targets

[走査統合の設計提案](https://github.com/masahitojp/mariamem/blob/fb361eeebdce6c4df578696327747211bbb70875/docs/reviews/snapshot-two-pass-design.md)
のSnapshot150ms以下という仮説目標は今回も意味がある。
同資料の「4テスト480ms以下」は**直列条件**の目標なので、並列で350msになったことを
hash改善の目標達成とは数えない。将来の候補は同じworker数のbaselineと比較する。
今回、追加の並列目標値を自動設定したり、hash統合を実装したりしていない。

## Verification, evidence and stop

20実行／100 DBで既存SQL・独立性・回収oracle PASS。各processでmapping作成=解放=5、
最終active／reserved／RW／release failureゼロ。sourceのclean statusとbinary hashは実行後も不変。
全trialを保持し、失敗workloadの再試行・遅い試行の削除・guard緩和なし。

[全20実行／時刻interval／自然な対／集計](../../benchmarks/light-fork-parallel/evidence)、
[再現と計測定義](../../benchmarks/light-fork-parallel/README.md)、
[解析source](../../benchmarks/light-fork-parallel/analyze.py)を参照。
測定runnerはbuild後約29.4秒、owned peak1.453GiB、空き最小67.618GiB。
45秒/cell・outer1800秒、owned8GiB／空きreserve20GiBのguard内で完了。

測定結果を保存・pushして使い捨てclone／cache／binary／worktreeを削除する。
main統合、最適化、最終Qualification、公開は行わない。
