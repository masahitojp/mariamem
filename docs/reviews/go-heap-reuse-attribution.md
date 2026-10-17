# 100 MiB Go Fresh — heap allocation attribution

2026-10-17。承認された最大2対／上限1時間の追加確認を実施。
**割当元とサイズの分類は完了。増えたheap再利用CPUの割当元は未帰属のまま、停止条件に従い計測を終了した。**

## Human Review

**Human decision — 2026-10-17:** 今回の調査をここで終了する。通常利用や計測で同様の
Fresh悪化が再現した場合に、保存済みの証拠と照合して改めて調査する。
再現待ちの追加計測や修正は開始しない。初回32.6秒の原因とheap再利用CPUの割当元は
未解明のまま保持し、解決済み・noiseとは判定しない。以下は判断時の推薦と根拠。

**判断は、この限定調査をここで閉じ、修正へ進むかは別の目的・範囲で判断すること。私はここで閉じることを推薦する。**
新構成は確保総量を約44%減らしており、今回もFreshの持続的な悪化は再現していない。
D block確保とSQL運搬の内訳は判明したが、約2秒のheap再利用CPUをどちらかへ因果的に
割り当てる証拠はない。これを理由にGC設定やblock形式を変更する段階ではない。

**最も強い反論は、再利用CPUの増加が繰り返し現れており、利益を取りこぼしている可能性が残ること。**
その可能性は残す。ただしallocationの多さとsysUsedの原因は別であり、観測を増やすだけでは
systemstackの欠落を埋められない。追加するなら割当と再利用を直接結ぶ別の計測設計が必要で、
今回の延長として自動着手しない。元の32.6秒の原因も未解明であり、解決済みとはしない。

## 1. What changed, and what did not

今回のFreshでは**旧版もDBファイルはGo heap上のMemFS**。
Snapshotのファイル保存をmemory baselineへ移した説明と、Freshの割当形態を区別する。
旧版の`StartInstance → NewMemFS`／`resizeMemData`は、大きな連続sliceを拡張してcopyする。
新版の`StartInstance → NewBlockMemFS`／`blockStorage.writeAt`は、必要な16 KiB blockを確保する。
[公開v0.5.0の処理](https://github.com/masahitojp/mariamem/blob/44100ec676c8c9064f32f3a01bd9a990d487bb61/internal/generatedgo/code/base/memfs_growth.go)と
[公開v0.5.1の処理](https://github.com/masahitojp/mariamem/blob/7a82f338cf111d5d52538b5a3f7bf129c12e2dbb/internal/generatedgo/code/base/block_storage.go)、
[確認したsource hashes](../../benchmarks/go-heap-reuse-attribution/evidence/storage-source-audit.json)を参照。
前報の「file I/O CPU減」はMemFSの読み書き／copyの分類であり、ディスクI/O時間を測った意味ではない。

同じreleased sourceを使用：v0.5.0 source_commit `44100ec676c8c9064f32f3a01bd9a990d487bb61`、
tag_object_sha `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`。
v0.5.1 source_commit `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、
tag_object_sha `089b32e09608902f6d46e7ab9527d09922dcf065`。
Apple M1／macOS27.0.1 arm64、Go1.26.8、CGO=0、`-p 1 -trimpath -buildvcs=true`。
両sourceをcleanな独立cloneにし、typed pin／commit／実binaryのVCS revisionとmodified=falseを
`git_identity.py`で検査。実行後にもsource status／binary hash不変を確認。

100 MiB／8表／4直列Fresh DB、既存`app-connections`とSQL・commit・rollback・独立性・cleanup oracleを維持。
旧→新、新→旧の2対、4実行／16 DB。benchmark main/resourcesだけのGo overlayで、CPU profile、
既定rateのallocation profile、全操作前後のheap／GC／確保サイズ分布を追加した。
ライブラリ、guest、生成Go、GC設定、pool等は未変更。追加の強制GCも行わず、既存の最終診断GCを維持。
全4実行が計測ありのため通常実行の性能証明にはしない。操作前後のReadMemStats等はtimer外だが、
後続のGC／scavengerへ影響しうる。[前報のoff/on比較](go-large-fresh-investigation.md)も負荷ゼロの証明ではない。

## 2. Allocation origin and size

4 DB分の累積MiB。totalはMemStats差分、分類は既定512 KiB samplingのpprof推定。
推定分類の和と正確なtotalが一致することは要求せず、誤差を含め全sampleを保存。
分類はD→他MemFS→SQL driver/wire→他workload→backgroundの優先順で排他的。

| 量 | 旧2回 | 新2回 |
| --- | ---: | ---: |
| 累積確保total | 5710.1 / 5709.9 | 3196.1 / 3194.9 |
| MemFSの連続領域等 | 3411.8 / 3408.4 | 0.5 / 2.0 |
| D block storage | なし | 896.0 / 899.6 |
| SQL driver／wire運搬 | 2110.0 / 2124.6 | 2151.0 / 2124.7 |
| 他workload配下 | 94.2 / 96.2 | 88.6 / 89.2 |
| その他／background | 73.8 / 80.2 | 84.8 / 81.3 |

新版の主なD sampleは`blockStorage.writeAt → make([]byte,16384)`で、profileの割当サイズlabelも16384。
投入1 DBあたり、16 KiBを含むsize bucketの確保は旧1回、新13859〜14040回。
このbucket全数をDと断定せず、callerは別のprofileで照合した。
SQL側は両版とも約2.1 GiB。代表はdriverの文字列escape／interpolation、wire.read、Process.Call。
profileでは約136 KiB／264 KiBのbufferが大きく、block化後に新設された全量ではない。
新版totalの約2/3を占めるが、**それがheap再利用CPUの2/3を生むという意味ではない**。

MemFS側の大きな再確保が減ったことは、確保総量約2.45 GiB／44%減の説明と整合する。
これらは全suiteの累積量で、live heapや最大RSSでも、無条件に回収できるCPU時間でもない。

## 3. Per-DB evolution and CPU

各DB投入wallは旧5.600〜5.739秒、新5.485〜5.678秒。
投入中の確保は旧約1265 MiB/DB、新約782〜785 MiB/DB。
投入後heapは旧473〜476 MiB、新239〜336 MiB。
新版で後半DBほど単調にheap／投入時間が増える現象は今回確認していない。
Close直後にheapが直ちに減らないことを、そのままリークと呼ばない。mapping回収とは別のGC管理領域である。

| 指標 | 旧2回 | 新2回 |
| --- | ---: | ---: |
| product wall (s) | 26.125 / 26.460 | 26.138 / 25.703 |
| process CPU (s) | 29.071 / 29.449 | 29.379 / 28.837 |
| GC回数（suite全体） | 30 / 30 | 48 / 44 |
| GC停止時間 (ms) | 1.665 / 1.718 | 2.640 / 2.776 |
| MemFS stackのsample CPU (s) | 2.78 / 3.48 | 0.66 / 1.14 |
| heap再利用sysUsedのsample CPU (s) | 0.05 / 0.07 | 1.98 / 2.25 |

自然な対のwall変化は+0.05%／−2.86%。計測ありの小標本で速度保証をしない。
新版のDB別投入中GCは1回目 `[16,8,9,13]`、2回目 `[16,9,6,11]`、旧はすべて6回。
GC回数やSTW停止時間は並行GC／再利用CPUの所要時間ではない。
HeapReleasedの増減も現在返却中のpage量であり、区間内の累積返却／再利用回数には換算できない。

再利用sampleの新版1.97／2.24秒は`mheap.allocSpan → alloc.func1 → systemstack`で終わり、
アプリケーションの割当元を失っている。残る各0.01秒はstack拡張／GC配下であり、
その少量も全てDの確保へまとめない。
Go1.26.8の[macOS sysUsedOS](https://github.com/golang/go/blob/go1.26.8/src/runtime/mem_darwin.go)は
返却済みheapの再利用を`MADV_FREE_REUSE`で会計する。
[SDK identityと観測定義](../../benchmarks/go-heap-reuse-attribution/evidence/observer-inputs.json)を保存した。

**確認済みは「小さいblock確保が増えた」「SQL運搬確保は大きく残る」「再利用CPUが増える」の3点。
どの確保が何秒を生んだか、また元の32.6秒を生んだかは未確定。**
Dのallocation rate／live heapの変化がGC・scavengerのタイミングを変え、SQL側の確保にも影響する
可能性はあるが、今回の同時観測は反実仮想比較でも直接因果traceでもない。

## 4. Completion and preserved evidence

| 項目 | 結果 |
| --- | --- |
| 最大2対、割当元・サイズ、DBごとのheap／GC | PASS：4実行全数を保持・分類 |
| SQL／commit／rollback／Fresh独立性／cleanup | PASS：16 DB、mapping creates=releases=16、最終active/reserved/RW/failureゼロ |
| typed source/tag、clean clone、実binary stamp/hash | PASS：[receipt](../../benchmarks/go-heap-reuse-attribution/evidence/receipt.json) |
| allocation parserの総量／storage union | PASS：4件ともGo pprofのbyte単位表示と一致。[独立照合](../../benchmarks/go-heap-reuse-attribution/evidence/parser-crosscheck.json) |
| 再利用CPUの割当元 | 未帰属。合意済み停止条件で終了 |
| 以前の32.6秒の原因 | 未特定。noiseとも既知の欠陥とも分類しない |
| Ubuntu性能、修正、広い回帰／Qualification | NOT RUN：今回範囲外 |

build／4実行／profile text化のrunnerは327.1秒。owned最大2.693 GiB、空き最小66.546 GiB。
調査全体は開始から1時間以内に報告・保存し、試行数を増やさなかった。
準備中のcwd指定失敗とsandbox DNS拒否は実行前に解消し、DB workload失敗の再試行はない。

[全区間・全sampleの解析](../../benchmarks/go-heap-reuse-attribution/evidence/analysis.json)、
[4実行の原データと全profile text](../../benchmarks/go-heap-reuse-attribution/evidence)、
[再現・集計手順](../../benchmarks/go-heap-reuse-attribution/README.md)、
[公開保存hash台帳](../../benchmarks/go-heap-reuse-attribution/evidence/preservation.json)を参照。
原本8個の小さなbinary profileはlocal compact evidenceに保存し、公開資料には全sample/location/mapping textを保存。
既存`.node-version`等の他作業は保持。使い捨てclone／cache／binaryはcleanup対象。
main統合、修正実装、リリース操作は行わない。
