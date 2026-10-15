# C方式の限定確認：Pythonの小変更CRUDとファイル単位コピー

2026-10-16。macOS arm64。**承認された限定確認は完了。C方式の実装・採用は未実施。**

## Human Review

今の判断は、**ファイル単位CoWのCを、次の方式比較の候補として残すか**。
推薦は **残す。ただし「小変更ならコピー量も小さい方式」とは評価しない**。
今回の少数CRUDでも、1子あたり約138～159 MiBをコピーするモデルになった。
追加した確保＋コピー自体は約22～24 ms/子であり、これだけでCを不採用とする根拠にはならない。

最も強い反論は、子の利用からCloseまでに基準のほぼ全データをコピーしてしまい、
共有によるメモリ節約を期待しにくい点。Fork開始が軽くても、費用がCRUD・終了へ移る。
一方、Cで省ける可能性のあるSnapshotのファイル化は今回実装していないので、
純利益の正負は未判定。少数Forkの用途まで否定せず、D/Eとの比較材料として残す。
この報告から新規実験・製品化・main統合を自動開始しない。

## 1. 問いと範囲

利用者が提示した `start → migrate/seed → snapshot → fork/create → fork/update` を基本に、
通常の接続、commit/rollback、各子のCloseを含めた。
対象は「Cなら最初の変更時にコピーする基準ファイルと量・費用」。
メモリ共有、保存API廃止、Go/Python間handoffの新設計は含めない。

- `users`（email unique index、status、payload）と`orders`（user_id index、foreign key）の2テーブル。
- 小規模：各100行、users payload 256 bytes。中規模：各10,000行、payload 1,024 bytes（payload約9.77 MiB）。
- first：userとorderを1行ずつINSERT、commitして確認。
- second：firstの追加が見えないことを確認し、userを1行UPDATEしてcommit。
  orderを1行DELETE→rollbackして復元を確認し、改めてDELETE→commitを確認。
- 子は順次2つ。各接続・CRUD・切断・Closeを区別。最後に基準の全ファイルhashが変わらないことを確認。
- 3モード×2規模×3巡＝18 campaign、36子。別途pilot 3 campaign/6子。
  本計測は各巡でモードの順番を回転。並列子・長時間保持・重い更新は未実行。

ソースは `a8137b8b444f86068d3128a291e3a848adfdfd56`。
[source identity](file-cow-crud-evidence/source-identity.json) は `scripts/git_identity.py` でbuild前に確認。
Go1.26.8、Python3.9.6、PyMySQL1.2.3。正確なOS・binary hashは
[inputs](file-cow-crud-evidence/campaign/inputs.json)、guestは
[verification](file-cow-crud-evidence/verification.json)参照。
主worktreeの未保存設計資料等は持ち込まず、専用 `experiment/file-cow-crud` で実行した。

## 2. 測定の意味と限界

| モード | 内容 |
| --- | --- |
| control | baselineのruntime。計測用Python harnessから公開APIを呼ぶ |
| observe | 実際のmapped基準ファイルを追跡し、Cなら最初にcopyする操作・長さを記録する。内容は複製しない |
| copy-probe | 同じタイミングで、実データを別のGo領域へ確保・copyして子終了まで保持する。**実際のI/O先は既存mappingのまま** |

copy-probeは追加コピーの費用を実測するための負荷であり、Cの実装ではない。
現行mappingと追加copyの両方を持つ。Cの最終RSS、GC、全体速度を再現するものではない。
copy時間は `make + copy` のwall time。CPU時間、帯域の保証、全体時間への単純加算値ではない。
sourceをFDからmapしているため、heap→heapで共有するCとは読み取り側の条件も異なる。

モデルは、基準から来た安定nodeを追跡し、最初の非ゼロwriteで現在の論理長を一度だけcopyする。
shrinkはcopyせず、後のwriteでは短くなったprefixをcopy。O_TRUNC/長さ0へのtruncateは共有を捨てる。
grow/allocateによる拡張は既存prefixをcopy対象にする。新規ファイルや置換後の新nodeは共有元ではない。
これはCの一つの明示モデルであり、pgmem全実装の再現ではない。
各操作のprobeは既存MemFS lock内。計測は生成物へのexact-preimage overlayとして隔離した。

phaseはPythonが境界で原子的に更新するファイルから読む。
記録は**その操作が発生した時間区間**であり、バックグラウンド書き込みの起因SQLを特定していない。
phaseファイルの読み取りやJSON出力は観測負荷になる。guard/provenanceの保証をこのoverlayへ流用しない。

## 3. 結果

### 1子あたりのコピー量・時間

各値は規模ごとに6子（first/second×3巡）。量はobserveとcopy-probeで総量が一致。
MiBは2^20 bytes。時間はcopy-probe内で測った確保＋コピー。

| 項目 | 小規模 | 中規模 |
| --- | ---: | ---: |
| 基準ファイルの合計 | 約138.24 MiB | 約158.58 MiB |
| Cモデルで全利用期間にcopyする合計 | 138.23 MiB | 158.58 MiB |
| Fork起動区間の基準ファイルcopy | 0 MiB（12/12子、両観測モード） | 0 MiB（12/12子、両観測モード） |
| redo logの初回copy | 96 MiB | 96 MiB |
| copy時間合計：中央値［最小～最大］ | 21.71［21.44～23.39］ms | 24.27［23.84～24.72］ms |
| controlのFork API時間：中央値 | 51.61 ms | 52.07 ms |

基準13ファイルのうち9ファイルがモデル上copy対象。schema定義等の小さいファイルは対象外。
今回の起動区間にcopyがなかったことは、他fixtureや別の待ち時間でも起動copyがない保証ではない。

### 費用が出るファイルと区間

| ファイル | サイズ（小／中） | 観測 |
| --- | --- | --- |
| `ib_logfile0` | 96 / 96 MiB | observeでは全12子でCRUD区間に初回copy。copy-probeでは11子がCRUD、1子がconnect区間。通常のCRUD区間のcopy時間中央値は小15.14 ms・中14.77 ms |
| `ibdata1` | 12 / 12 MiB | 主にClose区間 |
| `undo001`～`undo003` | 合計30 / 30 MiB | 主にClose区間 |
| `users.ibd` + `orders.ibd` | 約0.22 / 20.56 MiB | 主にClose区間。変更行数とファイルcopy量は比例しない |
| Aria log/control | 約16 KiB＋52 bytes | 主にClose区間 |

close区間のcopy量中央値は小42.23 MiB／中62.58 MiB、copy時間中央値は小6.42／中9.44 ms。
小規模copy-probeの1子では一部の書き込みが別区間へ動いた。中央値だけで全子同じ順序とはしない。
生のphase別量・時間・ファイル一覧は[summary](file-cow-crud-evidence/summary.json)の各childに保存。

少数CRUD区間に観測された共有元ファイルへの実write量の中央値はobserveで約1.75／2.25 KiB。
それでもCモデルは96 MiBをcopyする。これはコピー単位の違いであり、データ破損の観測ではない。
guestがbufferに持つ変更がCloseでファイルへ反映されるため、SQL完了までだけを測ると後続費用を落とす。

### 観測の有無と全体時間

以下は各3 campaignの中央値。準備・Snapshot・2子の利用/Close・baseline Closeを含む。
最後の検証用baseline全量hash時間は除く。採用候補間の速度比較ではない。

| 規模 | control | observe | copy-probe |
| --- | ---: | ---: | ---: |
| 小 | 627.80 ms | 588.63 ms | 616.23 ms |
| 中 | 1412.41 ms | 1435.98 ms | 1474.67 ms |

小ではobserveがcontrolより短く、計測外乱を無視できない。
中ではcopy-probeの増加が見えるが、これをC採用時の純悪化率とはしない。
全モードでSnapshotは既存のファイル化経路を維持しており、CのSnapshot短縮利益が入っていない。
controlのSnapshot時間は小369～427 ms・中391～434 msであったが、**全時間が除去可能とは扱わない**。
pilotのobserveに約1秒長い回もあった。原因は今回の範囲で調査せず、pilotも証拠に残した。

## 4. 検証判定と未確認

| 項目 | 判定 | 証拠・範囲 |
| --- | --- | --- |
| Cモデルの境界 | PASS | zero write、同一ファイル二重計上防止、shrink後write、truncate/O_TRUNC、allocate範囲内/拡張、probe領域の独立性。`TestCowObserver*` |
| Python start/snapshot/fork/Close | PASS | 本計測18 campaignが完了 |
| CRUD、commit/rollback、次の子への変更非伝播 | PASS | 36子のassert成功 |
| 基準の不変性 | PASS | 18 campaignで子利用後の全ファイルhash一致 |
| 起動・CRUD・終了のcopy対象区別 | PASS（限定） | 24観測子。phaseは時間区間でありSQL因果の追跡ではない |
| 追加copyの費用 | PASS（限定） | 12子の確保＋copy計測。最終CのRSS/GC/速度の代替ではない |
| Ubuntu x86_64 | SKIP | 今回はmacOSでの軽量確認 |
| CのSnapshot作成、共有実装、Python新handoff、派生Snapshot | 未実装・範囲外 | 本格方式の実現性や純利益は未判定 |
| 並列多数子・長時間稼働・性能安定性・Release Qualification | 未実行・範囲外 | この限定結果で保証しない |

判定材料として得られたのは、**小変更CRUDでもCのコピー量は小さくならないが、今回の直列2子では
確保＋コピー時間は数十ms/子だった**という点。コピー量と利用者の待ち時間を混同しない。
Cの本格試作に進むか、D/Eと比較するかはHuman判断。今回の完了をC採用可やRelease READYとはしない。

## 5. 再現と所有元

計測ソース：[instrument.py](../../benchmarks/spikes/file-cow-crud/instrument.py)、
[observer](../../benchmarks/spikes/file-cow-crud/observer.go.txt)、
[model tests](../../benchmarks/spikes/file-cow-crud/observer_test.go.txt)、
[Python workflow](../../benchmarks/spikes/file-cow-crud/run.py)、
[aggregation](../../benchmarks/spikes/file-cow-crud/summarize.py)。

1. baselineから隔離したcheckoutを用意し、`scripts/git_identity.py inspect HEAD`でsource_commitを確認する。
2. Go1.26.8、`GOTOOLCHAIN=local`、CGO_ENABLED=1で`go build -p 2 -o <temp>/control-host ./cmd/mariamem-host`。
3. この報告の計測ソースを配置し`python3 benchmarks/spikes/file-cow-crud/instrument.py`。
   全preimageをbaselineと照合する。[overlay hashes](file-cow-crud-evidence/instrumentation.json)。
4. 同じGoでobserved-hostをbuildし、`go test ./internal/generatedgo/code/base -run '^TestCowObserver' -count=1`。
5. venvにPyMySQL1.2.3をinstall。`run.py --control <control-host> --observed <observed-host> --output <evidence>/pilot --pilot`。
6. `run.py --control <control-host> --observed <observed-host> --output <evidence>/campaign --repeats 3`。
7. `summarize.py <evidence>/campaign <evidence>/summary.json`。

disk guardはworkspace budget 12 GiB/min-free 16 GiB。build上限1200秒、各campaign呼び出し上限300秒。
baseline runtimeとobserver overlayを明確に分ける。converterやguestを更新・再生成した実験ではない。
source ownershipの変更は計測scriptのみ。実行時に適用したgenerated/base変更は保存patchとhashで再構成でき、
canonical generated sourceとしてcommitしない。両binaryの`vcs.modified=true`は実験tooling/overlayを含むためで、
それだけで同一性を主張せず、preimage・overlay・binary hashを照合する。

## 6. 保存とcleanup

小さなJSON証拠、計測source、overlay、build情報を本ブランチに保存する。
build cache、venv、binary、実験worktreeは結果保存後に削除する。
cleanupの実結果はworkspaceのreceiptと最終報告に残す。commit時点では成果の保存まで完了。
