# Issue188 — host要求受け渡しとSQL配下runtime、固定診断完了

**判断: 局所試作一案として、MemoryEAの境界検査を保持した関数呼出し削減（inline化/生成コードへの一体lowering）を推奨する。** SQLスタック内にMemoryEA/MemoryInBoundsが3processすべて現れた。一方、送信キューからgoroutine開始までの直接費用はP8約0.294ms/100件で、常駐senderを先に実装する根拠は弱い。候補の実装・採用・統合・releaseは行っていない。

最も強い反対材料: MemoryEA inclusiveは全CPU標本の4.16%にすぎず、SQL配下も47サンプル相当の有限観測。inline化が成立するか、コード増加とcacheの交換条件、wall利益は未知。従って速度向上や10%差達成は約束せず、一案の小試作としてのみ推奨する。

## 固定対象と検査

product source_commit bb1e937ae75b5788c8548a52987d9d42f78292d5、guest SHA256 77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450。git_identity.pyのsource.json、生成ファイルhash、最終overlay-hashes.jsonを保存。Go1.27.4/macOS arm64/CGO0/GOMAXPROCS8/GOGC100。706072d8dbfa76acb23d302d6bfaa08b91c444b5の差分加算harnessと区間観測を継承。任意SQLの採用済みbaselineを差分加算へ変更したものではない。

全5 trigger、status限定監査、注文UPDATE、時刻、制約/indexを保持。実登録本文、orders40/items100/audit40/合計/stock500/FK/CHECK/公開Closeを検査。Fork・親データ準備・PREPARE・COMMIT・oracleはraw100 Execの外。

- timeline off/on、P1/P8各warmup1＋交互3組: 16成功process、128 DB、12,800 raw INSERT。
- 独立CPU診断P8、3process×8wave×8 DB: 192 DB、19,200 raw INSERT、24 profile。
- 合計19成功process、320 DB、32,000 raw INSERT。失敗preflight（後述）は成功件数へ含めない。
- timeline on6,400件はDB instance serial/labelとrequest ID/slot、client逐次Execを照合。各DB100件の対応、重複/欠落、時刻の因果順、排他的区間合計=client Execを確認。warmupの同じIDが別DBに存在してもinstanceを混ぜない。
- parser focused tests: 1/3byte分割、連続frame、異DB同ID、oversize/short拒否、停止4byte frame。終了後の実raw変形fixtureで欠落/重複の拒否を確認（validation/）。これは計画の「事前」からずれた点で、事前に実施したと主張しない。

## 経過時間の結果

primary各Pのon24 DB平均、100 Exec合計。client_setupからreturnまでだけが排他的で、100件平均の合計がExecに一致する。kernel/CPU時間ではなく受け渡しとスケジューリング等を含む区間。

| 区間、ms | P1 | P8 |
|---|---:|---:|
| client Exec開始→host Call入口 |0.603|1.813|
| host Call入口→実write開始 |0.230|0.294|
| 実write開始→guest frame完了 |0.364|2.731|
| guest frame完了→worker開始 |0.268|0.381|
| worker開始→SQL開始 |0.238|0.325|
| SQL実行 |9.542|13.242|
| SQL終了→reply開始 |0.302|0.381|
| reply開始→host frame完了 |0.899|3.485|
| host JSON decode |0.350|0.441|
| decode後→client Exec復帰 |0.520|1.177|
| 合計 |13.315|24.269|

内包する別区間: P8送信キュー0.150ms、実write呼出0.124ms、guest reply全体0.462ms。上表へ加算しない。guestとhostが同時進行するwrite/readを直列に足していない。時刻は同一process monotonic clock。観測値はper-instance mutexとframeの観測用copyなどの負荷を含む。

P8でinput_delivery/response_deliveryが大きくても「OSパイプがその時間をCPU消費した」とは言えない。guest/hostの実write呼出は短く、区間には相手が次に実行されるまでの遅れも含まれる。待ちの所有者やscheduler原因は今回は未確定。Go execution traceを追加する自動延長はしなかった。

### off/on負荷

各process内の8 DB raw span中央値を3processで中央値化（上の排他的平均とは別の統計）。

| | off | on | on/offの対応変化率 |
|---|---:|---:|---|
| P1 |12.750ms|13.020ms|+2.73%, +1.69%, +3.85%|
| P8 |22.825ms|24.389ms|+4.21%, +13.60%, -2.92%|

P8 observer負荷/共有host変動は無視できない。0.1ms級の候補を精密に序列化できず、値を補正しない。offもhook分岐と追加Moduleフィールドを含み、無加工binaryではない。前回の異cohortとの差を改善効果と解釈しない。遅い標本を保持し追加反復なし。

## CPU診断 — SQL配下のruntime候補

timeline無効、別processでraw phase前にStartCPUProfile、raw phase後にStopCPUProfile。raw/Start/StopのUTC時刻をwaveごとに保存。24waveのraw wall合計0.595sに対しprofiler Start/Stop全体は4.974s、pprof報告duration4.92s。停止tailと背景threadを含み得る。全sampleをSQL CPUやraw内だけのsampleとは主張しない。

全CPU samples3.61s（10ms刻みで361相当）。guest reply→fflush→Fd_write/writeVec配下2.33s、host送信writeAll配下0.30s、embedded execute Fn5570配下0.47s。これは各々inclusiveであり合計しない。syscall比率やCPU%をwall寄与へ換算しない。macOSのsyscallサンプリング偏りもあり、これだけを根拠にパイプ置換を推奨しない。

Fn5570を含むstackに限定したMemoryEA inclusiveは0.15s、その内MemoryInBounds inline0.10s、MemoryEA flat0.05s。SQL配下0.47sの約32%だが全体3.61sの4.16%。各processでMemoryEA inclusive0.04/0.06/0.05s、いずれもSQL配下に現れる。atomic各関数は各1サンプル程度で、lock/atomic置換を優先するほどの証拠はない。未検出inline helperが費用ゼロとも言わない。

cpu-flat/cum/sql.txt、cpu-sql-process*.txt、merged.pprof、元24profileとwindowを保存。SQL関数map: Fn5570=emb_stmt_execute、Fn15540=process_triggers、Fn15594=注文UPDATE、Fn152=dlmalloc等（selected-function-map.txt）。flat/cumulativeの親子重複を避ける。

## 次の一案と出口

対象: base.MemoryEA/MemoryInBoundsを呼ぶ生成Goの通常load/store。仮説は、同じ論理境界検査を各accessで保ちつつ、関数呼出とアドレス計算をinline可能な形へまとめるとSQL内の実行費用を減らせる、というもの。

次の有限試作案（今回未実行）:

1. canonical生成/後処理の所有元を確認し、compiler出力でMemoryEAの呼出が残ることとinlineできない理由を確認。2時間内に局所変更へ落ちなければ見送り。生成済みファイルだけの手編集を製品候補にしない。
2. 一案だけ試作。addr+offsetのoverflow、論理MemSize、端点/zero-size access、grow後のbound、shared memoryの並行性とtrapを保持。検査・atomic・mutexを省いて速度を作らない。
3. focused bounds/grow/並行性のcanonical checkを通す。観測なしでbaseline/candidate P1/P8、warmup各1＋交互5組のraw対照を固定し、全標本/CPU/code sizeを保存。利益なし/回帰/複雑化なら棄却。
4. rawが改善しても製品採用は別判断。元SUM条件での効果、アプリ全suiteとP1/P4/P8、対応両OS、キャンセル/Close等の変更境界に応じた受入れを確認する。profile割合を利得の見積りへ直結しない。

sender常駐化・パイプ全面置換・JSON全面置換・入力上流再利用#167の同時試作は提案しない。次の一案の実装はHumanの別判断。

## 計画との差分・失敗

初回warmup前に観測Process.writeが停止用4byte frameを通常requestとして扱いpanic。失敗をfailed-preflight-0へ保存し標本から除外。id読取にlength guardを追加し、停止frameの回帰検査を追加してwarmupから再開。これが計画で許容した1回の観測器修正。その後の全19processは成功。

ビルドは実際には3回実行した（下書き、slot記録/fixture追加、preflight修正後）。計画の初回＋再build最大1回より1回多い。最初の2回に性能標本はなく最終binary hashを保存したが、ビルド回数は計画通りとは報告しない。次回はsource/hook/fixtureを揃えてから初回compileする。

欠落/重複の人工fixture検査はcampaign後に実施。warmup/primaryの実データ整合性は各process直後に検査した。これらの手順逸脱を隠して「全計画無差分PASS」とはしない。

## 再現・検証・保管

固定sourceからexperiment-workspaceをprepare（8GiB予算/最低空き8GiB）。workspace名host-shim-cost、repo root cwdでsetup188.py→finishsetup.py→repair.pyを実行し、保存overlay-hashes.jsonと最終harness/observerを照合してbuild.pyへ進む。setup188.pyは固定706072d8のbundleをGitから展開するので、当該refの取得が必要。campaign.pyはevidence/campaign188に新しい19process結果を保存。reduce188.pyにそのdirectoryとprocess名を渡して対応/合計を検査、summarize188.pyで再集計。保存bundleのcampaign/は今回のimmutable結果であり新campaignへコピーしない。

Go pprofで24profileを結合し、-top / -top -cum / -top -focus=Fn5570を実行する。生profileには関数名を含み、最終binary hashはbinary.json。巨大binary/cache/generatedコピーは残さず、source/recipe/hash、profile、raw、失敗、計算scriptを保管。

確認済み: 19process件数/終了code、192profile DBのoracleログ件数、6,400イベント対応、排他的合計、profile8wave×3、missing/duplicate拒否、保存hash。製品runtimeの変更や公開契約の変更はなく、無変更の全製品CIは再実行していない。現行mainへの自動移植はしない。
