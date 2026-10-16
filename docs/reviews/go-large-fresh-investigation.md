# 100 MiB Go Fresh: released-source investigation

2026-10-17。限定調査は計画した10実行と解析まで完了。**初回32.6秒の原因特定は未完了**。
今回の公開版対比較では持続的なFresh悪化を再現せず、ファイルI/Oの利益を相殺しうる
macOSのGoヒープ再利用処理が、CPUプロファイルで繰り返し確認できた。

## Human Review

**次の判断は、Goヒープの再利用費用を増やす割当元に絞った追加調査へ進むか。
私は上限1時間の限定追加確認を推薦する。** 新しいファイルI/OはCPUサンプルで約2.2秒分
軽くなった一方、ヒープ再利用経路が約1.9〜2.0秒増えた。利用者が期待する投入速度へ
この利益が反映されにくい理由の候補が具体化した。先にどの割当が関係するかを調べ、
ストレージ全体やGoのGC設定を変更する実装はまだ始めない。

**最も強い反論は、通常計測では新構成が遅くならず、追加費用はCPU計測中の観測だという点。**
これだけでは元の+29%や+7.2%の原因とも、通常実行で常に失う2秒とも言えない。
このため次も割当元・サイズとメモリ再利用の対応に限定し、説明できない場合は未帰属として
止める。修正や大きな方式変更を前提にした調査へ広げない。

## 1. Fixed inputs and finite scope

| input | identity |
| --- | --- |
| released v0.5.0 | source_commit `44100ec676c8c9064f32f3a01bd9a990d487bb61`、tag_object_sha `bfd854da1cecbe71ad761d1578b3f2c710a1c07f` |
| released v0.5.1 | source_commit `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、tag_object_sha `089b32e09608902f6d46e7ab9527d09922dcf065` |
| observer recipe | `870b9a0903968f02a2bf6e6e3a2e2194ead5e9ed`。集計と報告は本資料のcommit |
| platform/toolchain | Apple M1／macOS27.0.1 arm64、Go1.26.8、CGO_ENABLED=0、`-p 1 -trimpath -buildvcs=true` |

型付き[baseline pins](../../release/baselines/v0.5.1.json)を`git_identity.py`で検査。
両sourceはcleanな独立Git clone。実binaryのGo VCS revision／modified=falseをbuild後に照合し、
実行後にもsourceとbinary hashが不変なことを確認した。
[receipt](../../benchmarks/go-large-fresh/evidence/receipt.json)に全identity、overlay hash、
実compiler情報と10件の完了記録を保存した。

100 MiB payload／8表、4個のFresh DBを直列に開始し、各DBで同じINSERT群、point query、
COUNT、2接続のcommit／rollback、Closeを行う既存`ownedprepared` workload。
FreshにはSnapshot/Fork操作を含まない。各DBの初期state／SQL結果と40個のmemory mappingの
作成・解放、最終active／reserved／RW／release failureゼロを検査した。
並列接続・Fork等の全面回帰試験は追加していない。

無変更binaryの対を1回、同じobserver binaryでCPU計測off/onを各2対、計10実行。
対の実行順は交替し、一度に1 campaignのみ。observerのGo overlayはbenchmark mainだけに限定し、
pprof import／任意flag／Start・Stopとfile Closeを追加。guest、生成Go、ライブラリ、SQL oracleは
変更していない。[overlay実体](../../benchmarks/go-large-fresh/evidence/observer-overlay)も保存した。
profile on/offは別集計で、計測負荷ゼロを証明したとは扱わない。

ディスク上限8 GiB／空きreserve20 GiB／supervised run上限3600秒、cell180秒。
実行は526.3秒で完了、owned usage最大2.349 GiB／空き最小68.042 GiB。
RSS8 GiB超の完了時停止はsampled safeguardで、hard RAM quotaではない。
Ubuntuは未実行、推定PASSにしない。v0.5.1は既に
[公開と両OS public smokeに成功](https://github.com/masahitojp/mariamem/actions/runs/38959312232)しており、
今回の調査はその公開判定をやり直すものではない。

## 2. Historical observations, without dropping the adverse trial

[以前の全4観測](../../benchmarks/main-product-verification.md#adverse-100-mib-go-case-and-bounded-repeat)を再利用した。
旧版wall `[25.258,25.448,29.455,27.783]`秒、候補
`[32.585,26.283,28.755,28.299]`秒はそのまま保持。
群ごとの中央値の比+7.2%は変わらない。同時点の自然な対ごとの変化は
`[+29.0%,+3.3%,-2.4%,+1.9%]`、その中央値は+2.57%。
CPUの群中央値比+6.3%に対し、対ごとの変化の中央値は+2.13%。
これらは異なる統計量であり、以前の算術の訂正や、遅い試行の除外ではない。
少数試行から安定した退行率を推定しない。

最初の大幅悪化は、各DBの投入wall／CPUで次の位置にある：

| DB | 旧wall→新wall (s) | 旧CPU→新CPU (s) |
| --- | ---: | ---: |
| 1 | 5.386→5.381 | 5.686→5.707 |
| 2 | 5.388→5.593 | 5.683→5.822 |
| 3 | 5.544→6.952 | 5.746→6.605 |
| 4 | 5.426→9.749 | 5.678→7.266 |

後半へ向かう伸びは追加3対では繰り返していない。起動／Closeが主増分ではなく、
投入・SQL実行が主な区間であることまでは分かる。
process CPUは複数threadの和なので、wallとの差をそのまま待ち時間とは呼ばない。
この時点のCPU profile／scheduler traceがないため、後から今回のprofileを付け替えて
元の32.6秒を説明することはできない。

## 3. New released-source observations

秒、旧→新。無変更のcalibrationは各n=1、observerは各n=2の中央値。

| 条件 | product wall | 変化 | process CPU | 変化 |
| --- | ---: | ---: | ---: | ---: |
| 無変更calibration | 26.631→26.042 | −2.2% | 29.956→29.401 | −1.9% |
| 同じobserver・CPU計測off | 26.436→26.285 | −0.6% | 29.680→29.549 | −0.4% |
| 同じobserver・CPU計測on | 27.160→26.180 | −3.6% | 30.359→29.514 | −2.8% |

通常3対は新構成が約0〜2.2%短く、最初の+29%や群中央値+7.2%は今回再現していない。
校正n=1と反復n=2ではobserverの影響や退行不在を証明できない。
Go product wallは既存diagnostic probeを除く実区間の合計、CPUには同じobserver／診断を含む。
CPU profileはさらにprocess全体をsampleするため、product wallと直接足し引きしない。

通常試行の累積allocationは旧5708.5〜5711.2 MiB、新3195.5〜3196.0 MiB。
GCは旧26回に対して新40〜50回だが、停止時間は旧1.69〜1.94ms／新2.38〜3.13ms。
GC回数増だけで秒単位の差を説明せず、concurrent／assistのCPUを停止時間から推定しない。

## 4. What the CPU profiles locate

4 profilesの全sample／location／mappingをtextとして保存し、同じparserでstackのunionを集計。
以下は**sampled CPU秒**であり、wall上の遅延や回収可能な秒数ではない。
カテゴリは重なるため、行を加算しない。

| stack分類 | 旧2回 (s) | 新2回 (s) | 確認できること |
| --- | ---: | ---: | --- |
| MemFS／memFile／blockStorageを通るI/O | 3.36 / 3.22 | 1.03 / 1.08 | 新構成の直接I/O費用は小さい。旧は主にmemmove、新はcopy／zeroing |
| Go heapの`sysUsed`再利用 | 0.02 / 0.08 | 2.03 / 1.92 | 新構成で繰り返し増加。sample全体の約7.5〜8.0% |
| Go heapの`sysUnused`返却 | 0.01 / 0.00 | 0.02 / 0.01 | 上記増分を「返却処理そのもの」と混同しない |
| GC／scanを含むstack | 0.02 / 0.01 | 0.03 / 0.02 | 今回のprofileでGC markが大半を占めるわけではない |
| allocationを含むstack | 0.29 / 0.30 | 0.70 / 0.63 | zeroing等を含む。systemstack側の再利用費用全体は含まない |
| Wasm memory境界検査のstack | 5.97 / 6.47 | 5.67 / 5.87 | 両版に共通の大きな費用。今回導入した費用ではない |

境界検査の2関数は両公開sourceでbyte一致を確認した。
[static audit](../../benchmarks/go-large-fresh/evidence/static-audit.json)にhashを保存し、
性能のために検査を外す変更はしていない。

sample総量は旧26.21／26.23秒、新25.24／25.69秒。process CPU全量と一致せず、
sampleされないCPUもある。Go／OS同期関数のsampleも大きいが、`pthread_cond_wait`等の
位置に現れたsampleを、そのままwallの待ち時間としては扱わない。
また、今回profile onで現れた約2秒が通常offでも同じと換算しない。

増えた経路は`runtime.madvise → runtime.sysUsedOS → mheap.allocSpan`。
使用したGo1.26.8の[source](https://github.com/golang/go/blob/go1.26.8/src/runtime/mem_darwin.go#L29)では、
`sysUsedOS`は返却済みheap領域を再利用する際のmacOS会計を`MADV_FREE_REUSE`で更新する。
[allocSpan](https://github.com/golang/go/blob/go1.26.8/src/runtime/mheap.go#L1400)はscavenged領域を
取得した場合にこの処理を呼ぶ。実際に使用したSDK fileのhashは
[sdk-inputs](../../benchmarks/go-large-fresh/evidence/sdk-inputs.json)へ保存した。

これは「ファイルI/Oの利益が、Go heap再利用の費用で相殺されうる」という具体的な仮説を
支える。ただしsampleがsystemstackへ切り替わり、**元の割当元のstackが失われている**。
Dの16 KiB block確保、SQL／transport等の別の割当、GC／scavengerのタイミングのどれが
この増分を作るかは未帰属。Dだけの反実仮想比較も今回行っていない。
v0.5.0→v0.5.1にはguest起動修正も含まれるので、差をすべてDへ割り当てない。

## 5. Judgment and bounded next work

| 問い | 判定 |
| --- | --- |
| 以前の遅い区間とDB内の位置 | 確認済み：投入／SQL、特に最初の試行の後半DB |
| 今回の通常実行で持続的な悪化 | 未再現。退行なしの証明ではない |
| 新しい直接ファイルI/Oが重いか | 今回のprofileでは逆に約2.2秒軽い |
| 新構成で増える具体的な経路 | 確認済み：profile中のGo heap再利用。元の割当元は未帰属 |
| 初回32.6秒の原因 | 未特定。単なるnoiseとも、既知のD欠陥とも分類しない |
| SQL／commit／rollback／Fresh独立性／回収 | 10実行・40 DBで既存oracle PASS |
| Ubuntuの性能／全体race／Release再Qualification | NOT RUN／今回範囲外 |

次の推薦範囲は、同じ4 Fresh workloadで割当profile、割当サイズ、DB区間ごとのheap／GCの
推移を最大2対だけ追加観測し、D block／SQL transport／その他へ帰属できるかを判断すること。
**上限1時間（build・解析・報告込み）**。得られるのは割当元の分類と再利用経路との対応で、
systemstackから直接の因果が取れなければ未帰属と明記して止める。
それを理由に無制限に観測や対象を広げず、追加instrumentationが必要なら別の範囲・費用で判断する。
修正実装、global GC設定変更、block形式変更やpool／arena設計はこの承認に含めない。
この追加調査はまだ実行していない。

## Evidence, replay and retention

[全区間・自然な対・profile分類の集計](../../benchmarks/go-large-fresh/evidence/analysis.json)、
[全10実行とbuild identity](../../benchmarks/go-large-fresh/evidence/receipt.json)、
[全profile report](../../benchmarks/go-large-fresh/evidence)、
[有限scopeと再現手順](../../benchmarks/go-large-fresh/README.md)、
[解析source](../../benchmarks/go-large-fresh/analyze.py)を参照。
全数値・sample stackを保持し、遅い試行を削除していない。
[tooling verification](../../benchmarks/go-large-fresh/verification.json)は、public textからの
全集計再現と、4 profilesのI/O unionがnode省略を無効にしたGo pprofと一致することを確認した。

原本の4つの小さなbinary CPU profileはローカルのcompact evidenceにKEEPし、
public sourceには全sample／location／mappingの`-raw.txt`とtop／cum／filter reportを保存した。
原本hashと公開textのpath・改行・末尾空白正規化前後hashは
[preservation ledger](../../benchmarks/go-large-fresh/evidence/preservation.json)に記録。
public textにはすべてのsampleがあり、集計はbinaryなしでも再実行できる。
Go pprof GUIで原本を再利用する場合はローカル原本または同recipeの新規profileを用いる。
再実行のsampleが原本と同一になるとは主張しない。

新しいライブラリ／guest修正、生成Goの手編集、mainへの統合、タグ／公開は今回行っていない。
他作業の未追跡`.node-version`は保持。調査branchの知識をcommit/pushし、
source clone／compiler cache／binary等の使い捨て状態を削除する。
