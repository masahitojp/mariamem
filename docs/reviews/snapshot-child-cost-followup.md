# 直接コピー後の子処理費用 — 限定追加確認

2026-10-14。承認された上限4時間のうち、固定した診断を実施。
**GC・回収時期・待機の限定診断は実施済み。大規模ケースの全体悪化の因果帰属は未判定。**
新しい修正、採用、リリース判断は行っていない。

## Human Review

**推薦は、直接コピーの製品化を今回は保留し、現行維持でこの追加確認を閉じること。**
今回、懸念していたGC増加の費用は小さく、Snapshotの節約を相殺する主因という説明は
支持されなかった。しかし全体時間は観測方式によって改善・悪化が残り、候補の影響と
実行ばらつきの内訳までは確定できなかった。事前の「混在なら現行維持」の終了条件に従う。
この結果は候補の欠陥・持続的な回帰の認定ではなく、製品化へ追加12～24時間を投入する
投資判断としての保留である。追加の試行数や修正を自動で増やさない。

最も強い反論は、既存の10 MiB・4 Forkで全体11.4%短縮し、今回もSnapshot自体は短く、
GCの重い副作用という懸念も弱まった点。これは採用に有利な証拠であり、取り消さない。
Goの一時Snapshotの応答改善を優先し、大規模の全体利益は未確定という条件を受け入れて
製品化を選ぶ余地はある。ただしそれは今回の混在時の既定判断を変更するHumanの選択となる。
現行維持の理由を「安全性が確認できない」「GCが増えたから危険」と説明しない。

[投資比較](storage-investment-reassessment.md)の小～中規模利益、pgmem/VFSとの比較、製品化費用は維持する。
広い保存方式変更の利益を示す証拠は追加されなかった。今回の結果から必要な修正箇所は特定されていない。

## 1. 固定した問い・実行範囲

問いは「100 MiB・16 Forkの子処理に、Snapshot短縮を継続的に相殺する候補由来の費用があるか」。
[事前にcommitした実行範囲](snapshot-child-cost-plan.md)に従い、同じCRUD・1 table・直列16子で
observer無効ABBA 4件、操作境界カウンタABBA 4件、CPU profile 2件、trace 2件を実施した。
最小1子の計測動作確認2件を加え、**14シナリオ／194子（準備DB込み208 DB lifecycle）**。
SQLのcount・payload・commit/rollback・子の初期状態のoracleは変更せず、全件PASS。

測定source_commitは`30046c949717a0eb95086cfbf0ceeb081f85e5c6`。
試作source `3341f99000246fc64ae17b4ea39118f55589de1e`とguest/runtime/host/SnapshotのGit objectは一致。
変更はbenchmarkの任意カウンタと子区間だけのprofile、事前文書のみ。
原経路と直接コピーは同じバイナリを既存の環境スイッチで切り替えた。
MariaDB 12.3.3、Go1.26.8、GOMAXPROCS=2、macOS arm64。Go GC設定の変更も新しい強制GCもない。
既存の終了診断GCは製品時間の外に一度だけ残す。UbuntuはSKIP、今回のローカル診断の対象外。

## 2. GC回数が変わる理由と、測れた費用

GCの回数だけを見た前回の仮説から、以下まで進んだ。

1. 元方式・候補とも、Snapshot直後には既に不要になった領域を含むGo heapが残る。
2. その時点の「前回GCが見たlive bytes」とヒープ目標が、次の回収時期に影響する。
3. 子の実行中に回収されると、heap objectsが十数MiB、ヒープ目標が約26～30 MiBへ下がる。
   16子が引き続き計約402 MiBを確保するので、その後は小さなGCが繰り返される。
4. 元方式でも、操作境界計測の一回では子の途中で回収され、15回のGCが発生した。
   他の元方式では子区間のGCは0回。したがって「元方式は常に0回」は成立しない。

| 記録 | Snapshot直後のheap objects | 子終了時のheap objects | ヒープ目標：Snapshot後 → 子終了 | 子区間GC回数 |
| --- | ---: | ---: | ---: | ---: |
| counters 元方式0 | 806 MiB | 14 MiB | 1066 → 27 MiB | 15 |
| counters 元方式3 | 698 MiB | 1101 MiB | 1333 → 1333 MiB | 0 |
| counters 直接1 | 543 MiB | 14 MiB | 753 → 26 MiB | 16 |
| counters 直接2 | 543 MiB | 14 MiB | 753 → 26 MiB | 16 |

これらはGoの集計で、RSS・物理footprintではない。heap objectsには未回収の不要領域を含む。
`/gc/heap/live:bytes`は前回GC時のlive量で、現在の到達可能量を即時測定した値ではない。
ヒープ目標はGC周期終了時の目標で、GC開始閾値そのものではない。特定の一ファイルが
何時まで保持されたかまでオブジェクト単位で証明したわけではない。

| GCがあった子区間の診断 | 観測値 | 解釈 |
| --- | ---: | --- |
| runtime推定GC CPU、idle分を含む | 約21～29 ms | Go自身の推定。OSのCPU秒から引いて正確な残余時間を作らない |
| 上記からidle GCを除いた推定値 | 約11～14 ms | 強制的に使ったGC処理量の目安。壁時計時間の上限ではない |
| アプリgoroutineのmark assist推定値 | 約0.7～1.7 ms | SQL処理がGC作業を手伝う費用も大きくなかった |
| scavengingの推定CPU | 約19～23 ms | OSへのページ返却関連。GC CPUとは別の集計 |
| trace直接コピー：GC停止区間合計 | 約3.061 ms | sweep terminationとmark terminationの合計、18周期 |
| 同trace：並行mark区間合計 | 約20.488 ms | アプリも動く区間であり、そのまま利用者の待ち時間にしない |
| 同trace：mark assist区間合計 | 約1.623 ms | 26区間。並行mark区間と重なるので単純に加算しない |

CPU profileでも直接側のGC/sweepスタックに帰属したサンプルは約0.02 CPU秒。
17回GCのあった直接側の子は18.232秒、0回の元方式は18.303秒だった。
カウンタとtraceとsampled profileは異なる観測であり、三つの値を合算しない。

**判定：GC増加・回収のタイミング変化は確認。GC自体が約0.4秒のSnapshot節約を相殺する
主因という説明は、この範囲では支持されない。** GC外のcache/page/scheduling影響がゼロという証明はしていない。
個別値は[cost-summary](snapshot-child-cost-evidence/cost-summary.json)、
[子別heap/goal](snapshot-child-cost-evidence/analysis.json)、
[trace区間の再集計](snapshot-child-cost-evidence/trace-ranges.json)を参照。

## 3. CPUと待機で分かったこと

子区間のCPU sample総量は元25.12／直接25.22 CPU秒で、主なstackの構成は似ている。
macOSの`pthread_cond_signal/wait`、`usleep`等のnative/runtime stackが大きく、
これをそのままguest関数別CPUや利用者の待ち時間へ割り振ることはできない。
memmoveサンプルは元0.78／直接0.98秒だが、一組のsample差からcopy量増加や恒常的悪化を断定しない。

traceではbenchmarkのメインgoroutineがSQL応答を待つnetwork待機は元17.459／直接17.360秒。
そのgoroutineのRunnable時間合計は両方約1 ms、syscall区間は元341／直接334 msだった。
この一組では、直接コピー側に新しい長いSQL応答待ちやメインgoroutineの実行待ちを確認していない。
network待機はローカルMariaDBの応答待ちであり、外部ネットワーク遅延を意味しない。

全goroutineの同期待機合計は元470／直接467秒、Runnable待機合計は元33.60／直接34.39秒。
多数のworkerの同時待機を足すため子区間の約18秒を超える。差0.79秒を製品の遅延と呼ばない。
支配的な待機stackは両方で既存のfutex/atomic wait・wake経路だった。
候補由来の新しい待機経路という証拠はなく、この調査から同期設計変更へ進まない。

## 4. 全体時間とobserverの限界

秒。off/countersは各2試行中央値、CPU/traceは各1試行。
観測方法が違う群をpoolして改善率を出さない。

| 観測 | Snapshot 元 → 直接 | 子区間 元 → 直接 | 製品全体 元 → 直接 |
| --- | ---: | ---: | ---: |
| observer無効 | 1.245 → 0.420 | 22.593 → 19.823 | 32.562 → 26.997 |
| 操作境界カウンタ | 0.710 → 0.370 | 18.136 → 18.620 | 24.838 → 25.364 |
| 子CPU profile | 0.696 → 0.358 | 18.303 → 18.232 | 25.155 → 24.843 |
| 子trace | 0.733 → 0.343 | 18.740 → 18.638 | 25.718 → 25.126 |

observer無効の元方式一回目は38.843秒、最後は26.282秒。
準備も10.803→6.633秒と大きく変わっている。最初の値を削除せず、約17%改善という中央値差を
安定した候補効果として採用しない。ウォームアップ・OS状態等の原因自体も、この記録からは確定しない。

操作境界カウンタ群は全体が約0.526秒（2.1%）悪化。内訳には、直接コピーを実行する前の
準備の中央値差約0.381秒、Snapshot約0.340秒短縮、子区間約0.484秒増加がある。
この不利な結果を、profile/traceで速かったことを理由に除外しない。
元方式でもGC0回／15回が分かれ、回収時期も変わった。

カウンタは各操作のtimer外、profile開始/終了は子window外に置いたが、runtimeの状態や
後続GCへの影響までゼロとは言えない。traceを有効にした子区間の割当は約430 MiB、
counters/CPU profileでは約401～403 MiBで、traceの追加費用も確認できる。
実行順に伴う変動とobserverの影響を分離し切れていないため「observerは無視できる」としない。
初回の大きい変動とこのobserver限界が、採用に有利な群も不利な群も過大解釈できない理由となる。

**確認済み：** Snapshot短縮、回収時期の違い、小さいGC処理費用、共通のSQL/同期待機経路。
**未判定：** 以前の悪化と今回のcounters群の悪化のうち、候補固有の費用がどれだけか。
「全部ばらつき」も「候補の性能回帰が確定」も結論にしない。

## 5. 三案への影響と終了判断

| 選択 | 今回で強くなった根拠 | 残る費用・不確実性 | 推薦 |
| --- | --- | --- | --- |
| Go一時Snapshotの直接コピーを製品化 | 既存の中規模全体11.4%短縮を維持。GC増加の重い副作用という懸念は弱まった | 大規模全体利益は未確定。製品化12～24時間＋CI待ち。Python高速化は別 | 合理的な代案として残すが、今回の採用推薦にはしない |
| さらに限定確認を繰り返す | 既知のGC費用は絞れた | 単純な試行追加は因果を解かず、未特定の間接費用探索へ広がる | 推薦しない。今回の固定診断で止める |
| 現行維持 | 修正が必要な具体的障害は特定されず、現行の準備再利用利益は保てる | Snapshot約0.2～0.43秒の改善機会を見送る | **推薦。既定の混在時終了条件に一致** |

新たな性能修正の作業範囲は提示しない。原因未確定のままGC強制、メモリ保持量の調整、
VFS置換等を「修正」と呼ばない。広い方式変更が今回の未確定を解く証拠もない。

予定した診断を実施できたため4時間上限を待たず終了する。上限を使い切ったことを完了理由にしていない。
元の悪化原因の確定は未完了であり、それを必要とする採用判断は今回閉じられなかった。
今回の承認で新たな実験や製品化は開始しない。

## 6. 同一性・検証・保存

- 観測source：`30046c949717a0eb95086cfbf0ceeb081f85e5c6`。
- binary SHA256：`6d81ba37d12066b714f7802f8a330fa29185b8caa29f5d4eb5d63b44d0e0e262`。
- guest SHA256：`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- Git commit型、clean standalone clone、実binaryのVCS revision/modified=false/Go versionを
  `scripts/git_identity.py`でビルド前後に確認。
- [入力](snapshot-child-cost-evidence/inputs.json)、[同一Git objects](snapshot-child-cost-evidence/unchanged-inputs.json)、
  [全実行](snapshot-child-cost-evidence/campaign.json)、[検証集計](snapshot-child-cost-evidence/verification.json)。
- 14シナリオのSQL oracle PASS。計測付き実行で追加の強制GCなし、元の終了診断GCだけ1回。
  FDは共通の5→6。線形mapping counterは今回のobserverでは取得していないため、ゼロだったとは報告しない。
- CPU/trace parserの全変換成功。rangeの未対応境界・未閉鎖rangeは再集計JSONに残す。
- Ubuntu、Python高速化、完全Release Qualification、性能修正はSKIP／未実施。
  元の試作の所有権・失敗試験は固定元実装の証拠を参照し、今回再実行したとは扱わない。
- 初回ビルドのmodule stat-cache書込警告を保存。ビルドは成功し、binary同一性検査も通過。
  付属Go toolchainにpprof/trace実行ファイルがなかったため、同じ固定toolchainの`cmd/pprof`・`cmd/trace`から構築。
- storage budgetは6 GiB、free reserve 8 GiB。guard記録と終了時の保持確認は証拠に保存。

証拠は[再現手順と保存形式](snapshot-child-cost-evidence/README.md)へまとめる。
実験branchに計測source・報告・全結果・圧縮traceをcommit/pushし、復元可能なclone/cache/binary/worktreeを片付ける。
mainの既存未commit文書と他作業のworktreeには触れない。Human Reviewで停止する。
