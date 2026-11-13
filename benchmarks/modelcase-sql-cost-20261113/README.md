# modelcase SQL費用・l4m資源設定調査 — 2026-11-13

## 結論と推奨

この70テストでは、l4mの小さい資源設定を一律に緩めることを次の改善として推奨しない。制限は実在するが、I/O並列度増加は全3組で全体悪化、buffer pool16→64MiBも公平な最終3組で全体悪化。cache/クエリ用メモリの増量は小さく混在した。16MiBで空きページが多く、観測した診断でbuffer pool不足待ち/log buffer待ちは0。これは小さいfixture限定の結論で、大きなデータの設定入口 #144 の価値を否定しない。

次の優先候補は、(1)繰り返す暗黙PREPAREの回避/再利用、(2)host↔guestのframed OS pipe往復、(3)集計SQLの実行計画とgenerated memory accessの費用。#65の出力再利用を速度の解答と認定する証拠は得ていない。最も強い留保は、各資源対照3組・shared Macで、設定SET費用を含み、短いprofileには起動/fixtureも含まれること。リソース不足の全可能性を排除した調査ではない。

## 固定範囲・検証

元の公式比較: https://github.com/masahitojp/mariamem/blob/894253bcf671ef11f8d555f5b58f67819b812733/benchmarks/pgmem-modelcase-20261113/README.md

製品source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`、M1/16GiB/macOS27.2.1、Go1.27.4/CGO0、GOMAXPROCS8/GOGC100、test.parallel8。前回と同じ70 assertions/fixture、最終ハーネスはharness/。ドライバのContext interfaces/Rows/transactionを観測wrapperで委譲し、SQLや結果は変更しない。query_returnとrows_completeは包含するため加算しない。観測offでも薄いwrapperは残る。

- 最初のcohort35プロセス: 資源/driver診断6、warmup5、本計測5群×3、observer off/on各3、別profile3。34成功。pool64の最初のpilotだけ実験observerのSIGBUS（後述）。成功2300 leaf tests。
- poolfix10プロセス/560 leaf testsは探索負荷が非対称な参考値として全保存。最終poolequal10プロセス/560 leaf testsは探索を同条件に揃えた別cohort。計55プロセス、成功3420 leaf tests、SQL/trigger/independence assertionsと追加したClose error検査成功。元の失敗を除去しない。
- CPU profileはRevenue/GetOrder/CreateOrderをそれぞれ20回反復した別診断。前二者200 cases、後者80 cases。fixture・startup・background処理も含み、profile drain時間もある。単一SQL CPUとして読まない。
- 製品/guestの正規生成、既定値変更、main統合、CI/releaseは行っていない。64MiBのみ実験用Go overlayで生成初期image中の二つのNUL終端起動引数を同長で16M→64Mへ変更。各1箇所を厳密に検証し、初期化済みengineを複製しない。runtime variableで両値64MiBを確認。これはcanonical candidateではない。

## 設定の実在と対照

固定l4m source_commit `24be9371a2f6c71250a2356631ad6feab2280b02` のwasm/lite4mariadb.cを取得し、製品guest/input.jsonのSHA256 `c0a959b6755d3463de31d9d08d2a43031cc418a332768a0956ebfd5046e15526` と一致した。起動argvと実行時SHOW VARIABLESの両方を保持。

|項目|l4m起動指定 / 実測|対照|
|---|---|---|
|buffer pool / size_max|16MiB / 両方実測16MiB|両方64MiB、実測確認|
|log buffer|2MiB / 2MiB|固定。診断log waits=0|
|read I/O|1 / 1|4|
|write I/O|1 / **2**|4。起動指定と実値の差を保持|
|purge threads|1 / 1|固定。別worker変更へ広げない|
|table_open_cache|32 / 32|256|
|max_connections|10 / 10|32（cacheと一群）|
|thread_cache_size|0 / 0|固定。hostは既存worker slotsを保持|
|join_buffer_size|l4m明示指定なし / 256KiB|2MiB|
|sort_buffer_size|l4m明示指定なし / 2MiB|8MiB|
|tmp_table_size / max_heap_table_size|l4m明示指定なし / 各16MiB|各64MiB|

最後の三つはMariaDBの通常値であり、l4mが追加で絞った値と混同しない。thread_pool_size/max_threads/innodb_thread_concurrencyはこのSHOWの応答に無く、名前から有効なworker上限を推測しない。globalの設定は各接続初期化時、session設定は各sessionへ適用するため、そのSQL設定費用をwhole wallに含む。cache256はcacheと接続上限を分離した因果比較ではない。

|最初のcohort・70テストprocess wall中央値 ms|値|現行より短い組|
|---|---:|---:|
|現行|496.756|—|
|read/write I/O各4|770.910|0/3|
|table cache256・接続32|482.567|2/3|
|query memory増量|488.474|2/3|
|text parameter interpolation|458.171|3/3|

io4では一部のquery/Forkは短くても、全体は全組悪化した。cache/querymemの差は小さく、3組で既定変更を支持しない。資源armの数字を前回のpgmem数値に組み合わせない。

最終pool比較（同じ初期literal探索を同じ生成layout内で実施）:

|median ms|16MiB|64MiB|
|---|---:|---:|
|process wall|501.776|543.396|
|boot|68.770|70.210|
|Snapshot|5.584|11.011|
|各process内Fork中央値の中央値|29.522|36.917|
|sample中央値の中央値|75.223|72.440|

64MiBは全3組で全体悪化。sampleだけ少し短くてもFork/Snapshotの費用が増えた。等しい探索を追加した別binary/cohortなので最初のcohortと算術合成しない。

単一のseed済みDB診断では、16MiBのfree pages943、64MiBは3670、両者buffer_pool_wait_free/log_waitsは0。Opened_tables6、table cache hits587/misses6。cold起動からの累積read counterをcache miss率やquery単体のI/Oと解釈しない。Max_used_connections/Threads_connectedはembeddedでは0を返し、同時接続需要が0という証拠に使わない。tmp disk tables1は累積値であり、特定集計のspillや容量不足を証明しない。

## サンプル投入・PREPARE

LoadSampleはtransaction内で注文40 INSERT、明細100 INSERT、在庫100 UPDATE。明細INSERTのtriggerが注文合計を更新し、注文INSERTのtriggerが監査行を作る。各writer20と読取共有1で繰り返す。明細INSERTを単なる100行copyと扱わない。

観測あり3スイート（全query/test混在）で、明細INSERT EXECUTEは各2108回、per-call中央値0.242–0.251ms、在庫UPDATE各2109回で0.106–0.115ms、注文INSERT RETURNING各844回でquery_return中央値0.149–0.168ms。件数は21サンプル投入に加えテスト本体を含む。CPUではなく並列時のrequest elapsed。全DBのsumをsuite wallへ加算しない。triggerだけの独立CPU/待ち時間は未分離。

注文取得の二種類のSQLは、観測各スイートで107回PREPAREと107回EXECUTE。デフォルトmysql driverのInterpolateParams=falseは、単発のパラメータ付きQueryごとにPREPARE→EXECUTE→closeへfallbackする。明示Prepare済みのsample3 statementsはこの切替では変わらない。

textparams対照はmariamem公開DSNが通常指定するinterpolateParams=trueを使い、単発parameter SQLをtext protocolへ補間する。pgxの同じprotocolを再現する案ではなく、通常利用可能なdriver選択の対照。pooled scenario中央値はGetOrder6.271→2.407ms、Revenue9.565→8.982ms、CreateOrder3.055→2.760ms。特にGetOrderは複数SQLを使うので往復回数削減と整合する。ただしstore EXECUTE本体/結果転送だけの差には分離されていない。既定API変更は不要で、明示prepared statementの再利用との比較は次の候補。

observer off wall中央値483.168ms、on486.359ms。ただしoffの1回700.404msを保持し、pairedな観測影響は一定ではない。監視を加えたら何ms分の純粋な原因が得られた、と断定しない。今回は400/800ms PREPAREの同因再発を示す記録ではなく、#140/#143を再開しない。

## 集計・注文取得: SQLと結果の境界

ANALYZE FORMAT=JSON（並列suiteとは別の単一DB）で注文ヘッダはPRIMARY const、明細はorder_id索引のref、2行を取得。query execution0.003/0.017ms、optimization0.087/0.100ms。索引が無く全表走査している状況ではない。数値は一回の診断で、通常クライアント往復に足して正確な内訳にしない。

売上集計はderived tableをmergeし、categories20→products各25→明細索引500回→orders100回のnested loop。約600明細pages accessed。baseline query execution2.467ms、optimization0.605ms、sort0.127ms、sort buffer31KiB、出力20行。資源対照でも基本的に同じplan。products全500件から明細へ探すので、明細/対象注文を先に集約するSQL案には調査価値があるが、同値性・実速度は未検証。

観測suiteのRevenue query_return中央値8.576–13.014msに対しrows_completeは8.606–13.047ms。driverへRowsが返った後の消費差は小さい。**serverがRowsを返す前に行う実行・C側結果構築・IPCはquery_return内に含まれる**ため、出力変換費用がゼロとは言わない。

CPU profile Revenue（200 cases、total2.10 CPU秒）: rawsyscall0.74秒/35.2%、うちguest Fd_write→writeVec→os.File.Write0.70秒/33.3%。MemoryEA累積0.65秒/31.0%（うちMemoryInBounds flat0.49秒/23.3%）もある。GetOrder（total0.83秒）はrawsyscall0.49秒/59.0%、guest writeVec経路0.30秒/36.1%、host guest.writeAll0.08秒/9.6%。短いmacOS sampleの帰属限界があり、これらの割合をwall改善上限に換算しない。generated Fnを未検証C名に置換しない。

外側mysql接続は既にnet.Pipeだが、internal/guest/linked.goは二つのos.Pipeでframed host↔guest要求応答を行っている。#66のTCP省略後にもこのカーネル経路は残る。これは次の具体的調査対象。pipe write回数・サイズ・wakeupsと同じ完了/キャンセル/error契約を持つ対照が必要であり、今回輸送方式を変更していない。

#65/#131のraw prepared output再利用は変換責務削減として関係するが、JSON/hexとframed IPCを残す候補。今回のRevenue profileではGo encoding/json/preparedproto/mysqlwireにsampleが当たらず、同候補の速度利益も未検証。C出力側の処理を除外した意味ではない。採用をこのprofileで正当化しない。bounds checkについても安全性を弱めずcaller/source対応・同義な低費用化の実現性が先。

## 既存Issueとの対応と次の条件

- #144: workload別資源設定の設計は継続価値がある。一律増量を推奨しない。#88の8MiB見送りと今回の64MiB比較は別cohort/方向。
- #122/#121: startup支配は既知。ただし今回のsample/SQL差には別の往復・実行費用がある。
- #56/#116/#64: 過去のgrowth/clear候補の再試行根拠にはしない。bounds check profileはzero clear省略とは別問題。
- #140/#156: 長いPREPAREと今回の通常の暗黙PREPARE往復を混同しない。#143保留継続。
- #119/#162: cleanup設計と長いCloseは別owner。今回の設定変更で修正済みとしない。
- 次の有限調査を選ぶなら、まず(1)既存driver設定/明示statement再利用、(2)内部IPCの要求当たりwrite/read回数とサイズ。集計SQLの同値なplan対照は別の小候補。製品transport実装やbounds省略に直行しない。

## 保存・失敗・再現

runs.json / poolfix-runs.json / poolequal-runs.json、全trace/log、query操作、実設定、ANALYZE JSON、選別profileのtop/caller tree、最終harness/overlay/source identityを保存。raw pprofはローカルevidenceにも保持する。analyze.pyは保存データだけから21本のprimary/1470 testsと中央値を検算する。

最初のpool64 pilotはm.Memory全sliceを探索し、論理メモリ境界外でSIGBUS。製品障害ではなく実験observerの誤り。次のpoolfixは256MiB内へ限定して正常化したが、baselineには同じ探索が無く初回touchが非対称だったため、性能結論へ使わない。最終poolequalは生成layoutの初期write window内へ限定し、両群で同じ探索/検証を行う。途中のローカル変数名衝突build failureも計測開始前に修正。失敗・参考値を成功へ読み替えない。

再現: 新しいmanaged workspaceのworktreeを製品pinへ合わせ、temp/mariaへharnessをコピーし、go.modのreplaceをそのworktreeへ合わせる。overlay.jsonのimage.go→image_overlay.goパスを新workspace絶対パスで作る。専用GOCACHE/GOMODCACHE、build.py、run.py（最終overlayでは全armが実行可能、元の失敗は再現しない）またはrun_poolequal.pyをdisk guard下で実行。10GiB/空き12GiB、build1800秒、各process130秒、通常計測900秒。結果は新cohortとして扱う。新C/WASM生成・既定変更・CIは不要。
