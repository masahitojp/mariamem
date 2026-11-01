# Fork起動時のゼロ化：量・呼出元・範囲の重なり

**ゼロ化は小さくないが、省略できると分かったわけではない。**
1子のFork中に約82.07MiBをゼロ化し、観測した実行時間の合計は約5.11ms。
その中に同じguestアドレスへの16MiB、その後17.707MiBのゼロ化が全6子であった。
次に進むなら、この2回の間のallocation/free・書込み・初期化の意味を限定して調べる。
メモリ共有やゼロ化省略の実装はまだ勧めない。必要なバッファ再利用だった可能性が、
この候補に対する最も強い反論である。

今回は「ゼロ化量と主な呼出元を特定する」観測で終了する。
[前の16MiB保護設定試作](https://github.com/masahitojp/mariamem/blob/1e1b46b0a2208ad66eea8752e1c2d54475a9cbdc/benchmarks/growth-prototype.md)
の再受入や、製品化・main採用・releaseではない。

## 先に除外できた仮説

既存MemoryFillの `for k := range b { b[k] = 0 }` は、Go1.27.3/darwin-arm64では
すでに `runtime.memclrNoHeapPointers` になる。clear(b)だけへ書き換えても、
最適化済みcompiler出力の368命令バイトと全relocationが一致した。
これは公開linked binaryの逆アセンブルではなく、同じexact base packageのcompiler
listing比較。ローカルtoolchainにobjdumpがなかったため、package指定の `-S` を使用した。
命令とhashはraw/codegenに保存し、Go1.26.10/Linuxへの一般化はしていない。
「1バイトずつの素朴なループをclearへ置換して高速化」は、この環境の候補から外す。

## 観測範囲

v0.6.0、Apple M1/16GiB/macOS27.2、Go1.27.3、CGO0、GOMAXPROCS8。
従来と同じ1,000整数行を準備しSnapshotを作成、各processで2子を順にForkする。
子ごとのCOUNT/SUM、独立更新、次の子のpristine baseline、DB/Snapshot/temp cleanupを検査。
観測off/onのfresh processを順序交互に3組、各mode6子を観測した。

MemoryFillだけにread-only観測hookを追加したGo overlayを使う。
全nonempty fillの回数/bytes、zero/nonzero別の実行経過nsを集計し、
64KiB以上のzero fillにはdestination/sizeと最大8frameのcall stackを保存した。
hookはguest bytesを読みも変更もしない。上限20,000大規模eventを超えたら不合格。
観測offも同じbinaryのnil-hook経路であり、未変更release binaryとは呼ばない。

phaseはfill開始時にatomicに取得する。background workerの完了がFork戻り値より
後になる可能性があり、時間の合計をcallerのwall timeに厳密に割り当てない。
計時はfillの直前から直後までで、stack収集・集計mutexはその後。
clock overhead、初回アクセス、scheduler、他threadの実行の影響は分離していない。
全guest memset/store/copyを捕捉する主張でも、未使用領域を証明するwrite trackerでもない。

## 結果

数値は6子の記述的中央値。独立したprocess反復は3であり、6独立反復として扱わない。

| 1子のFork中 | 中央値 / 観測範囲 |
| --- | ---: |
| zero fill回数 | 2,469 / 2,469–2,481 |
| zero fill累計 | 82.065MiB / 82.065–82.070MiB |
| zero fill観測経過時間の合計 | 5.108ms / 4.983–5.217ms |
| 64KiB以上のzero fill累計 | 78.109MiB（全6子一致） |
| そのguestアドレス範囲のunion | 61.797MiB（全6子一致） |
| 累計−union（同じ範囲への追加書込み量） | 16.313MiB（全6子一致） |
| 64KiB未満のzero fill累計 | 約3.956MiB |

unionは64KiB以上のzero fillだけの範囲の和集合。物理resident/dirty量ではない。
累計−unionは、途中の利用を無視した追加書込み量であり、無駄・省略可能量ではない。
5.108msもCPU時間ではなく、複数thread分を含む計時の合計。削減可能な5msとは扱わない。

| 上位の呼出元（exact generated function） | 累計bytes / 子 | 所見 |
| --- | ---: | --- |
| p0.Fn18568:676523 ← p3.Fn7108 ← p6.Fn14747 | 33.707MiB | 同じdstへ16MiBと17.707MiB、2回 |
| p7.Fn980:47338 ← p7.Fn4180 ← p4.Fn4244 | 15.916MiB | 1回の大きなzero fill |
| p7.Fn67:38 ← NewWithMemory | 8.566MiB | data/TLS初期化経路の明示ゼロ領域 |
| p5.Fn18283:1033160 ← p0.Fn18568 | 4MiB | Fn18568の起動経路内 |

最上位2回のdstは各子内で同じだった。phase1/4を分けて照合し、全processで
mapping creates=3（準備root1＋子2）、最後はactive=0を確認した。
最上位のfull stackはFn244、すなわち公開生成wrapperのL4mOpenまで到達する。
ただしFn18568やFn4244の正確なMariaDBソース名・バッファ用途は未同定。
古いguestのfunction mapを現在のindexへ当てはめず、InnoDB buffer pool等と推測で命名しない。

16MiBの最初のclearは中央値1.198ms、後続17.707MiBは0.441ms。
初回アクセスの費用が違う可能性とは整合するが、cache・途中の利用・page faultを
分離していないため原因確定ではない。どちらかをなくしても、残したclearに初回アクセスの
費用が移る可能性がある。2回の時間全部を節約できるという推定はしない。

Fn67はDataSegsを配置した後、guest offset15,244,864から8,982,576bytesをゼロ化する。
G0=8MiBというstack/global値からBSS量を推測する必要はなく、この明示ゼロ範囲は実測と
sourceで一致する。用途上必要か、fresh mappingの既存zeroを利用できるかは別の契約判断。

## 観測の影響と未解明の点

| Fork全体・6子の記述的中央値 | hook off | hook on |
| --- | ---: | ---: |
| wall | 36.526ms | 37.616ms |
| process CPU | 49.369ms | 51.585ms |
| minor faults | 4,968.5 | 4,956.5 |
| major faults | 0 | 0 |

観測が無害・時間が完全に同じとは主張しない。fault数はGo allocationや他のguest処理を
含むprocess全体の値であり、fill由来のfaultや新規物理ページ数ではない。
今回RSS/residencyは再測定しておらず、以前の約75MiBとの正確な対応も未証明。

次の具体的な問いは、**同じ大きな領域を2回ゼロ化する間に何が起きているか**。
exact guestのsymbol map/対応するMariaDB sourceでFn18568の用途とallocation lifetimeを
同定し、その間の利用を確認する。現在の調査にはそのmapがない。まず既存のpinned build
artifactに対応map/linked wasmがあるかを確認する読み取り調査が必要で、入手できずguestの
再ビルドが必要なら、その取得・ビルド費用を別途見積もって止める。
今回の範囲で消去省略・allocator変更・追加matrixへ自動展開しない。

## 検証・保存・再現

source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`、annotated tag object
`b57183b08d48884840111e8b53daa500734337f0`。観測harnessはinputs.jsonのsource_commitで固定。
clean HEADと型付きtag/commit identityをbuild前に検査し、binaryのVCS stamp/hashと
元base.go/overlay hashを保存。canonical product/guest/generated/releaseファイルは未変更。

既知のzero/nonzero/no-op/out-of-boundsのobserver selftest、正常pilot2・異常pilot2、
本計測12子のSQL/cleanupはPASS。分析5testsは欠落pair、event overflow、不整合なbyte数、
range unionを検査。raw manifestとraw→compact再生成も確認。
Linux、parallel Fork、全write追跡、最適化後の性能測定は行っていない。

[inputs](zerofill/results/inputs.json)、[summary](zerofill/results/summary.json)、
[observations](zerofill/results/observations.json)、[same-range evidence](zerofill/results/same-range.json)、
[checksums](zerofill/results/SHA256SUMS.json)、[raw archive](zerofill/results/archive.json)。
compact observationsは全phaseの集計とFork内大規模events、先頭3つのgenerated callerを保持。
root/verify/closeの詳細eventとfull stackは別のpinned raw refに保持する。

```sh
python3 benchmarks/zerofill/analyze.py --results benchmarks/zerofill/results --check
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/zerofill/test_analysis.py
```

rawのchecksum確認後、analyze.py --collect RAW --results OUTでcompact observations/summaryを
byte一致で再生成できる。再計測はinputsのharness SHAでowned workspaceを作り、run.pyを
evidenceへコピーしbuild→pilot→measure。Go版固定、disk8GiB/free16GiB、単一host・3組で停止。
最終report commitを測定sourceに読み替えない。生データはevidence refへ分離し、
将来mainへ記録する場合もexploratory historyをmergeしない。
