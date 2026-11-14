# Sample loading and revenue-plan investigation — 2026-11-14

結論: 次の製品改善候補としては、SUMや索引の再変更より、既存の内部応答書込経路を局所的に調べることを推奨する。サンプル投入中のCPU profileではmulti_worker→multi_reply→fflush→WASI fd_write→os.File.Writeが大きい。一方、売上集計の事前集約SQLは単独DBで約51%短縮し、計画改善を確認したが、suite全体の安定した短縮や約44ms削減は未確立。SQL対照はアプリ側の選択肢として保持し、製品の既定や公式比較を置き換えない。

## 固定した条件

製品source_commit bb1e937ae75b5788c8548a52987d9d42f78292d5、guest SHA256 77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450。git_identity.pyでcommit型とworktree HEADを確認。比較対照はshibukawa/pgmem v1.18.2、source_commit a61005d37d01e6671f814fe8ca828222e8147df4。前回のtag/commit確認に加え、今回取得したGo moduleのOrigin.Hash一致をcomparison-module-identity.jsonへ保存した。比較対照は今回Git checkoutではなく同版のmodule配送を使用した。

Go1.27.4/macOS arm64/CGO0/GOMAXPROCS8/GOGC100、共有Mac。依存とビルドを終えてから全計測を開始。既存の条件合わせ済みハーネスを維持し、通常DSN補間・監査UPDATE OF status・元SUM trigger・既定16MiBを保持。製品guest/hostは変更なし。harness/には実際の計測sourceを保存。binary hash/コマンドはrecords.json。前回の579msとの増減を今回のSQL変更へ帰属させない。

初回ハーネスのos import重複、対照moduleのgo.sum不足を計測前に修正。最初の失敗ビルドのconsole.logを保持。再ビルドでは固定要求版のmodule取得を許可し、性能計測には不要なvetを省略した。tempは容量12GiB・空き8GiB、build各1200秒、各process180秒の予算。初回workspace準備はsandboxのref作成拒否で失敗し、別の所有workspaceで再準備した。ユーザー作業中のrootは変更していない。

## 1. サンプル投入中のCPU

8個の新しい子DBを先にForkしてから、8 LoadSampleを逐次実行する間だけCPU profileを採取し、停止後に行数検証とClose。8波、64ロード。各ロード40注文・100明細・100在庫UPDATE、既存の監査/合計triggerあり。全64ロードで明細100件を確認。8DBを保持する条件であり、アプリP8投入と同じ並列負荷ではない。CPU profileはprocess全体なので既存DBのbackground処理、profile終了時の短い余白も含む。明細INSERTだけの費用・正確なguest wall分解とはしない。

8 profile合計のCPU標本2.46秒、記録duration合計3.53秒。profile-top.txt/profile-cum.txt/profile-traces.txtを保存。

| 経路 | CPU累積標本 | 全標本比 |
|---|---:|---:|
| multi_reply→fflush→WASI fd_write→writeVec | 1.49s | 60.6% |
| host Process.write→writeAll | 0.17s | 6.9% |
| prepared execute/trigger UPDATEを含む経路 | 約0.13s | 約5.3% |
| dlmalloc | 0.10s | 4.1% |

累積値は包含関係を持つため加算しない。rawsyscallnのflatは1.77s/72.0%、runtime.keventは0.14s/5.7%。短いmacOS CPU samplingのsyscall帰属には限界がある。CPU標本比を削除可能なwall比へ変換しない。

採用guestに対応するbuffer-zero-candidate/validation/function-map.txtで生成FnとC名を照合した（selected-symbols.json）。Fn267=multi_worker、Fn265=multi_reply、Fn198=fflush、Fn140=__stdio_write、Fn76=__wasi_fd_write。実SQL側はFn5561=emb_advanced_command、Fn14824=Prepared_statement::execute_loop、Fn15540=Table_triggers_list::process_triggers、Fn15594=Sql_cmd_update::update_single_table。Fn152=dlmalloc。現在の有限標本では、InnoDB索引更新やSUM単独を支配的なCPU原因とする証拠は得られなかった。

以前の「guest経過時間81%・通信11%」と時計が異なる。guest受信→最初の非空応答Writeまでの区間と、応答Write内のCPU・待機の境界も異なり、旧割合を更新・否定する値ではない。新旧の差から費用の移動を計算しない。

次の有限試作提案: 現行sourceの応答1件につき、非空/空Write、header/body、read回数とサイズを再対応づけ、既存の空iovec試作との差を先に確認する。そのうえで重複するOS境界を減らせる小変更が1件あるか判断する。既に済んだ空write比較をそのまま繰り返さず、transport全面置換や#167の入力decoder置換へ直行しない。framing、short I/O、error、EOF、cancel、shutdown、有限容量を保ち、固定A/Bで全体wall/CPUを比較する。今回のCPU profileだけでは安全な変更と削減量を確定できない。

## 2. 売上集計の事前集約対照

元SQLはcategories→products→order_items→ordersを結合して外側でSUM。対照は対象statusのordersと明細・productsを内側でcategory_id別にSUMしてからcategoriesへLEFT JOINし、COALESCEと並び順を維持。新index・設定変更なし。SQL全文はharness/*/store/store.goのrevenueSQLに保存。

各エンジン3process、各process100組。元/対照の実行順を組ごとに交替。各呼出しの全結果・順序を元の結果とDeepEqualで照合し、全1200呼出しで一致。検証は今回の決定的fixtureに対する有限検査であり、全データ型・数値境界に対する一般証明ではない。別processで両SQLの実行計画を取得。

| 単独DB・各process中央値の中央値 | 元SQL | 事前集約 |
|---|---:|---:|
| mariamem | 2.000ms | 0.973ms |
| 比較対照 | 0.180ms | 0.173ms |

mariamemは3processすべて同方向、paired差のprocess中央値は-1.030/-1.029/-1.026ms。単独SQLでは約51%短縮。

MariaDB ANALYZE: 元計画はproducts500件から明細索引500回、明細pages_accessed600。対照はorders_statusのrangeで対象注文30件→明細索引30回（90明細、pages_accessed120）→products90回→カテゴリ別materialization。元query_block約1.994ms/optimization0.616ms、対照約0.745ms/optimization0.196ms。各1回の診断値で通常query時計に足さない。比較対照のEXPLAIN ANALYZEも保存。

### アプリsuiteでの確認

同一バイナリの環境変数でSQLだけ切替。P1/P8、各エンジン各arm3process、交互順。70 test body/20 writer Fork/共有readerを維持。全24 suite process PASS、保存traceの全processで70 bodyを確認した。summary.jsonに全標本を保持。

| 全体wall中央値 | 元SQL | 事前集約 | 対応3組の差（対照−元） |
|---|---:|---:|---|
| mariamem P1 | 1310.974 | 1304.454 | +14.964 / -6.520 / -15.472ms |
| mariamem P8 | 495.314 | 469.613 | -47.201 / -4.033 / +161.354ms |
| 比較対照 P1 | 803.969 | 802.544 | -38.667 / +3.626 / -9.056ms |
| 比較対照 P8 | 421.376 | 380.922 | -274.089 / -27.284 / -10.242ms |

P8の独立中央値差はmariamem約25.7ms短縮だが、対応差の中央値は約4.0ms短縮で1組は161ms悪化。したがって「25ms確実に短縮」「目標まで半分達成」とはしない。今回の両側中央値比も目標達成を示さない。原因未確定の遅い個体を除外・追加反復していない。単体SQL改善は確認済み、全体の安定利得は未確立として有限調査を終了する。

## 推奨・完了の範囲

1. 製品改善は内部応答書込の既存試作との差分確認を次の小候補とする。guest SQL実行へ広いパッチを入れる根拠は今回得られなかった。
2. 事前集約SQLは有効なアプリSQL候補として残す。元ハーネスの標準比較を維持し、採用する場合も別armで管理する。
3. 本調査は完了。約44ms目標は未達成・未実証。製品実装・main統合・releaseは行っていない。#143等の保留調査を再開しない。

再現: 同じsourceをgit_identity.pyで確認し、harnessのgo.mod内の製品replaceだけ新しいworktreeへ合わせる。build.py→measure.py→analyze.py。pprofコマンドはprofile-top/cum/tracesの形式でsample-0..7.pprofを合成する。再実行時は別cohortとし、original hashや旧観測へ結果を付け替えない。
