# Fork は「同じ初期メモリを毎回作る」ために重いのか

**一部はそうだが、初期画像の共有を最初のCPU改善にする根拠は弱い。**
最初の領域確保は約0.01ms、Go側の初期構築は約1.56ms。
大きな仕事はその後のMariaDB起動にあり、子ごとに101回のメモリ拡張が発生した。
無変更エンジンのCPU profileでは、その経路の`mprotect`が作成・検証・破棄を含むcycleの
CPUサンプルの22–25%を占める。次の候補は、この拡張回数/単位/保護設定の費用を減らせるかの検討。
共有化・拡張方式の変更はいずれも未実装で、性能改善量を確定したものではない。

[前の資源比較](fork-resources.md)に続く、mariamem内部の原因候補を絞る調査。
同じM1/16GiB/macOS27.2、Go1.27.3、CGO0、GOMAXPROCS8、mariamem v0.6.0、TCP、
1,000整数行の`fork_probe`を使う。pgmemの再計測は行っていない。
[plan](forkattribution/plan.json)と[inputs](forkattribution/results/inputs.json)が条件とidentityを固定する。

## 領域確保と、その領域を使う処理は違う

5 fresh processesで、各2子を順に作って保持した。子ごとの中央値→5processの中央値。
メモリは各段階でのguest領域のresident page合計（Darwin `mincore`）。

| 観測点 | その工程のCPU時間 | guestのresident領域 |
| --- | ---: | ---: |
| 最初の仮想領域確保・保護設定の直後 | **0.0095ms** | **0MiB** |
| generated-Go構築・初期化の直後 | **1.558ms** | **15.11MiB** |
| MariaDBがreadyになった時点 | 段階実行では測らない | **75.41MiB** |
| 接続・SELECT1・seed確認・接続退役後 | 段階実行では測らない | **75.46MiB** |

最初に2GiBの仮想アドレスを予約し、256MiBをRW化するが、これを実RAM消費とは扱わない。
起動後のguest-visible/RW範囲は約626MiB（process内中央値の範囲626–630MiB）。
そのすべてがresidentになるわけではない。process RSSの1子増分はready時約76.63MiBで、
guestのresident領域約75.41MiBと近い。RSS/PSS/専有physical footprintは同一の指標ではない。

**初期構築時点の15MiBだけを共有しても、起動後の約75MiBを全部消せるわけではない。**
残り約60MiBは、その後のDB起動でresidentになる。どの内部bufferかの完全な割当一覧は今回は取っていない。

観測フックは`newMemoryModule`のreserve/construct前後にのみ入れ、外部RSS取得中に停止する。
このためstage版のFork全体時間は性能値にしない。工程CPUは停止前に採取するが、観測でcache/時間経過も変わり得る。
[overlay](forkattribution/overlay/)のbefore/after hashをinputsへ記録し、元のrelease checkoutは変更していない。

## 無変更エンジンのCPU profileでは、後続の拡張が目立つ

CPU profile版はoverlayを一切適用しない。seed準備とSnapshot作成後、
100子を順にFork→TCP接続/SELECT1/COUNT/SUM確認→接続退役→Closeする。これを独立2processで実行。
profileはこのcycle全体で、ForkだけのCPU内訳やアプリE2E全体の割合ではない。

| 関数/経路の累積CPUサンプル比率 | run0 | run1 |
| --- | ---: | ---: |
| 初期`newMemoryModule` | **1.68%** | **1.87%** |
| `MemoryMapping.Grow` → `mprotect` | **22.35%** | **24.72%** |
| guest `MemoryFill` | 8.01% | 6.18% |
| guest `MemoryInit` | 0.74% | 0.37% |

累積値には呼出先を含む。親子関数を足して比率にしない。
Go scheduler/同期処理のサンプルも多く、初期化だけが全CPUを占めるという結果ではない。
短い処理のsample割合は粗く、stage版のfresh-process所要時間との直接の同一視もしない。

stage版の既存mapping counterでは、最初のreserve後に全10子で**101回**のGrowがある。
[source](https://github.com/masahitojp/mariamem/blob/b3b3b46a8807482ad3f96725af86e031fe369b01/internal/generatedgo/code/base/base.go#L1145)では
zero-page要求を`MemoryGrow`の入口で返し、成功した正の拡張だけが
[MemoryMapping.Grow](https://github.com/masahitojp/mariamem/blob/b3b3b46a8807482ad3f96725af86e031fe369b01/internal/generatedgo/code/base/memory_mapping.go#L74)を呼ぶ。
そこでは増分範囲へ毎回`mprotect`を行う。観測したgrowth/release failureは0。
これは「最初のmmapが遅い」より、後続の小刻みな拡張を優先して調べる根拠になる。

**22–25%高速化できるという意味ではない。** CPU時間とwall timeは異なり、削減可能な回数/費用も未確定。
論理memory size、未許可領域、zero initialization、失敗時の状態、thread共有と所有者cleanupを
保ったまま変えられるかが次の設計上の条件で、PROT_NONEを無条件に外す提案ではない。

## 同じ内容のページは多いが、安全に共有できる量ではない

起動・seed確認後の子2個を保持し、**同じguestアドレスで両方residentなページだけ**を読み取り比較した。
既存residentページを確認してから読み、未residentページを検査のために全走査しない。
OSページは16KiB。5processの中央値と範囲、単位MiB。

| 両方residentなページの内容 | 中央値 | 範囲 |
| --- | ---: | ---: |
| 両方とも全ゼロ | **42.09** | 38.69–43.73 |
| 全ゼロではなく、内容が同じ | **26.97** | 26.58–28.20 |
| 内容が違う | 4.33 | 3.41–4.75 |

比較可能な重なり自体が69.25–75.47MiBで変動する。独立した分類の中央値を足して全体値にしない。
片側のみresidentなページは別計上し、同一/相違とは判定しない。
この表は保存された同一baselineからの1時点であり、変更が少ないfixtureなら同じ内容が多いこと自体は自然。

- 全ゼロの領域は、共有画像より「新しいzero-filled領域へ重複して書いていないか」の調査候補になる。
  ただし既に使ったbufferを正しくクリアしている可能性があり、ゼロ化を省いてよい証拠ではない。
- 同じnonzero内容にも、guest起動後のbuffer・データ・初期状態が含まれる。pgmem型の初期data imageだけで
  この全量を共有できるわけではない。
- guest background workerは凍結していない。SQLは退役済みだが、この読み取りはatomic snapshotではない。
  mutableなlock/thread/環境を含む状態をそのまま共有・複製できるという正しさの証明ではない。
- `mincore`はresidencyでありprivate/dirty/PSSを分けない。約69MiBを節約できるという予測には使わない。

## 結論と次の判断

元の仮説への答えは、**「繰り返し用意される同じ内容はある。ただし初期画像の構築だけがCPUの主因ではない」**。
改善の第一候補は、起動時の101回のメモリ拡張と保護設定変更の費用。
初期画像共有は保持メモリの候補として残すが、優先順位を下げる。
ゼロ初期化の重複も候補であり、安全に省けるかは未証明。

推奨する次の小さな調査は、拡張単位/回数の内訳を確認し、既存のmemory保護・grow失敗契約を維持する
最小案を選べるかまで。実装/採用は別判断とし、今回のプロファイルを改善後の性能証拠に読み替えない。
この調査で停止する。cold host、Linux、fixture size別、v0.7資源受入、releaseへ拡大しない。

## 入力の固定、検証、保存

release sourceは`b3b3b46a8807482ad3f96725af86e031fe369b01`、annotated tag objectは
`b57183b08d48884840111e8b53daa500734337f0`。build前に`git_identity.py`、HEAD一致、clean treeを検査。
最終計測ハーネスはinputsの`harness_source_commit`で固定。両binaryのVCS stampは同SHA/modified=false。
stage版のoverlay identityは別記録し、modified=falseを「無変更エンジン」の根拠にしない。

最初のpilotは初期256MiBのみを観測したが、grow counter guardが拡張を検出して停止した。
この予備結果は[GUARD_STOP](forkattribution/results/initial-span-assessment.json)として保全し、PASSへ貼り替えていない。
実際のlogical sizeをatomicに読み直す修正後、positive/negative各2pilotを再実行して成功。
`mincore`/page分類は既知の2ページで一致/不一致と変更後の一致を確認するself-testを毎回実行する。
全spanとactive-RW合計の一致、DBの独立更新、baseline不変、mapping/接続/temp cleanupも確認。

[observations](forkattribution/results/observations.json)はstage全点・外部RSS・CPU全関数表を保持。
[summary](forkattribution/results/summary.json)を再計算でき、[checksums](forkattribution/results/SHA256SUMS.json)が固定する。
[raw evidence](https://github.com/masahitojp/mariamem/tree/ce7ed65164602444f27c70f8ec299d010fbea42b/benchmarks/forkattribution/raw)
は別ref。raw CPU profileはlossless base64で保存し、decoded hashも保持。
[archive](forkattribution/results/archive.json)がmanifestを固定する。main向け提案はcompact final treeのみで、
raw/exploratory historyをmergeしない。owned pathだけを正規化しoriginal/published hashをrawに保存した。

```sh
python3 benchmarks/forkattribution/analyze.py --results benchmarks/forkattribution/results --check
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/forkattribution/test_analysis.py
```

5 focused tests: read-only再計算、改変summary、欠落反復、初期範囲のみの誤観測、page分類の不整合。
raw manifest、profile decode hash、raw→compact byte一致も確認。
`--collect <raw export> --results <new directory>`はtemp/buildなしで同じ数値を再抽出する。

再計測は専用workspaceをprepareし、`temp/product`にtyped release pinをcheckout、harnessをcommit。
`run.py`を`evidence/run.py`へコピーし、disk guardで`--phase build`→`pilot`→`measure`を実行する。
CPU全関数表は各raw profileについて次の追加抽出で保存する（binary不要、profile内のsymbolsを使用）：

```sh
go tool pprof -top -nodecount=0 -nodefraction=0 -unit=ms profile-0.pprof > profile-0-all.txt
```

active75分、tooling20分、heavy CI0回、disk8GiB/free reserve16GiB。
結果を保全後、owned source/build/cacheを削除する。今回のfinal diffはbenchmarks配下のみ。
canonical product/API/guest/generated/release変更、初期画像共有実装、main採用は行っていない。
