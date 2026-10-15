# EをつないだSnapshot経路：コピー削減と2子テスト全体の限定比較

2026-10-16。macOS arm64。**今回の限定spikeは完了。製品採用・main統合は未実施。**

## Human Review

今の判断は、**Eを有力候補として製品化の設計へ進めるか**。
推薦は進める。今回初めてSnapshotのコピーを実際に省き、準備から2子のCRUD・終了まで
小規模で約132 ms（23%）、中規模で約138 ms（10%）短縮した。
各規模5巡の同じ巡どうしの比較で、全10組が短縮した。

最も強い反論は、大規模・多数Forkでの全体利益とメモリ/I/Oへの影響が未確認なこと。
以前の直接コピーspikeでは全体の改善が安定しなかったため、
今回の小〜中規模・2子の利益をそのまま広げて採用するべきではない。
それでも今回の用途では全体の利益と隔離・失敗時動作の限定証拠が得られたので、
Cの本格化よりEの所有・エラー処理・対応環境を具体化する価値がある。
**推薦は製品化設計への継続であり、この実験patchの採用ではない。**

前回は「共有可能な領域に保存しても準備が大幅に遅くならないか」の評価だった。
今回は「Snapshot時のコピーを省くと、利用者の全体待ちが減るか」を実測した。
ここを混同しない。

## 1. 実施した変更と、残した仕事

| 処理 | 現行 | 今回の試作 |
| --- | --- | --- |
| FreshのDBファイル | Go heap中心 | 最初から一時file-backed MAP_SHARED |
| 整合停止・全worker join | 実施 | 実施。通常Shutdownを使い、成功と終了後handoffの結果を待つ |
| guestの /mariadb → snapshot-out のcold copy | 実施 | 性能計測では省略。別auditだけ既存Exportを実行し同一性を確認 |
| GoによるSnapshot領域→ホスト一時fileの書出し | 実施 | 省略 |
| 保存先へのpayload copy | 実施 | 同じfile/inodeを移動するため省略 |
| 元内容のinventory/hash | 書出し後のfileを検査 | 停止した元mappingの論理範囲を検査 |
| 引き渡し後のinventory/hash | copy先を検査 | 移動したfileを元の期待inventory/hashと比較 |
| Pythonの所有取得・全量検証 | 実施 | **無変更で実施**。readonly FD取得、unlink、hash比較 |
| Forkの起動・変更分離 | fresh runtime＋MAP_PRIVATE | 同じ。Fork起動を省く変更ではない |
| 子からの派生Snapshot | 既存cold copy/export | 既存経路を明示的に維持。今回の高速化対象外 |

公開Python APIは無変更。
ユーザーが保存形式を選ぶ必要はなく、今回のharnessも
`start → migrate/seed → snapshot → fork/create → fork/update → Close` を使う。

受け渡しは新しいFD通信ではなく、ライブラリ所有の一時pathを介して**同じ実体**を渡す方式。
停止したwriterのshared mappingをunmapし、余剰容量を切り詰め、writer FDを閉じる。
元fileと引き渡し先fileのinode一致を確認する。
Pythonの既存取得処理がreadonly FDを保持してpathを消し、以降はそのFDからForkする。
これは今回選んだEの一手段であり、E一般の唯一の方式ではない。

引き渡し前の期待hashを引き渡し後のhashで置換しない。
取得時の完全性検証、guest identity、基準の不変性を省略して速度を出してはいない。
三つの内容走査は残っているため、Snapshotが数msになった実験でもない。

## 2. ソース・環境・試験数

- baseline source_commit: `a8137b8b444f86068d3128a291e3a848adfdfd56`。
  build前の[git_identity記録](e-handoff-evidence/source-identity.json)。
- 前段のE評価:
  [9345a27](https://github.com/masahitojp/mariamem/blob/9345a270c3c5a15fd52e6734f6e854ebf1fe4fea/docs/reviews/shared-backing-probe.md)。
- guest MariaDB12.3.3、Wasm hash:
  `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- macOS27.0.1 arm64、Go1.26.8、CGO_ENABLED=1、Python3.9.6、PyMySQL1.2.3。
  [binary/overlay identity](e-handoff-evidence/build-identity.json)、
  [harness入力](e-handoff-evidence/campaign/inputs.json)。
- 小規模：users/orders各100行、payload256 bytes。基準約138.24 MiB。
- 中規模：各10,000行、payload1,024 bytes。基準約158.58 MiB。
- 各条件control/Eを5回、巡ごとに実行順を反転。計20 campaign・40子。
  pilot各1回、既存cold copyとのaudit1回、別のPython境界試験は性能集計に含めない。

controlは変更前にbuild。Eはexact-preimage overlayを適用した別binary。
両者のvcs.modified=trueを同一性の証拠にせず、source/preimage/overlay/binary hashを保存。
guestのビルド入力・Wasm・生成済みguest命令は変更していない。
Generated Goのbaseとhandwritten host adapterへの試作はscript/templateで保存し、
canonical生成物の編集として残さない。正式な再生成・provenance検証済みのcandidateではない。

## 3. 実測結果

### 中央値（各5回）

| 区間 | 小：現行 | 小：E | 中：現行 | 中：E |
| --- | ---: | ---: | ---: | ---: |
| Fresh Start | 45.64 ms | 48.53 ms | 48.01 ms | 47.63 ms |
| migration＋seed | 18.02 ms | 18.65 ms | 795.95 ms | 782.35 ms |
| **Snapshot API全体** | **378.48 ms** | **239.91 ms** | **388.66 ms** | **268.30 ms** |
| first Fork起動 | 51.63 ms | 54.12 ms | 54.18 ms | 51.68 ms |
| second Fork起動 | 49.89 ms | 52.93 ms | 51.26 ms | 50.57 ms |
| **準備＋Snapshot＋2子CRUD/Close＋基準Close** | **574.60 ms** | **442.84 ms** | **1404.64 ms** | **1266.76 ms** |

Snapshotの短縮は小138.57 ms（36.6%）、中120.36 ms（31.0%）。
全体の短縮は小131.76 ms（22.9%）、中137.88 ms（9.8%）。
数値は中央値どうしの差・比率。各巡の差の中央値とは区別する。
区間ごとの中央値を足して全体中央値を再構成しない。

- 全体の範囲：小は現行551.66～590.35 ms、E431.32～519.28 ms。
  中は現行1391.58～1426.21 ms、E1258.74～1283.88 ms。
- 同じ巡どうしの全体短縮は、小55.32～159.03 ms、中123.66～150.69 ms。
  全10組で短縮した。長期の分布や別環境での改善保証ではない。
- Fork起動・CRUD自体を速くしたとは判断しない。
  主な利益は再利用する基準を一度作る際の待ち時間削減。
- 全体には基準Closeを含め、確認用に最後に追加したbaseline全量hash時間だけを除く。
- pilot両binaryのFresh Startは約1秒。pilotを保存し、本計測の通常起動と混ぜて
  Snapshotの効果に見せていない。起動tailの原因調査はしていない。

[区間別の全値](e-handoff-evidence/summary.json)、
[差・比率・対応する巡の比較](e-handoff-evidence/comparison.json)、
[各campaign](e-handoff-evidence/campaign/)。

### 残っているSnapshotの費用

Eの内部計測の中央値は、元内容のinventory/hashが小72.92 ms／中82.33 ms、
mapping解除・サイズ確定・同じfileの移動が9.35／22.60 ms、
引き渡し先のinventory/hashが66.08／65.64 msだった。
さらにPythonの既存所有取得・hash、DB整合停止、manifest・後片付け等が残る。
Python hashと残りの厳密な分離は今回していない。

`payload_copy_bytes=0` は実験経路が保存用のpayload複製を呼ばないことの記録とコード上の性質。
検証の読み取りbufferへのコピーまでゼロという意味ではない。
OS内部のページ処理や物理I/Oがゼロという計測ではない。
全ファイルのinode一致と、性能試行にguest cold copyが存在しないことも毎回assertした。

## 4. 正しさ・失敗時の限定確認

| 対象 | 結果・証拠 |
| --- | --- |
| Eのサイズ変更・zero・ファイルidentity、子mappingの隔離と寿命 | PASS。前段からの境界テストを再実行 |
| 元fileと移動先の同一実体、source cleanup後も使えること | PASS。新handoff部品テスト |
| 同サイズ破損、余分/欠落file、異なるguest identity | PASS：拒否。失敗時manifestなし |
| 期待hashをcopy先hashで上書きしないoracle | PASS |
| 既存Snapshot/Owned/host境界 | PASS。該当する既存テスト選択を実行 |
| 実guest20 campaign・40子のSQL、commit/rollback、変更非伝播 | PASS |
| 子利用後の全基準file hash | PASS。20 campaign |
| 既存guest Export/cold copyとの内容・directory inventory一致 | PASS。別audit1回、13 file約138.24 MiB |
| active transactionのSnapshot拒否後に元DBを継続利用 | PASS。Python公開API |
| 基準Close後も二つの開始済み子を利用・隔離 | PASS。Python公開API |
| 子からの派生Snapshotと兄弟隔離 | PASS。**既存経路で確認** |
| 移動前／移動後／hash後破損／publish移動後の4失敗 | PASS：エラー、元DB終了、保存先削除、host退出 |
| Python取得時の同サイズ破損拒否 | PASS。既存adopter無変更 |
| 実験専用TMPDIRのmariamem資源残り | なし（境界試験・本計測後） |
| Ubuntu x86_64、macOS15、並列多数子、RSS/物理I/O、最終Qualification | SKIP／今回対象外 |

[Go境界試験](e-handoff-evidence/boundary-tests.log)、
[既存Snapshot試験](e-handoff-evidence/existing-snapshot-tests.log)、
[Python境界結果](e-handoff-evidence/python-boundaries/result.json)、
[実guest cold copy audit](e-handoff-evidence/audit/)。

新経路はguestのExport応答を偽装しない。
通常Shutdownの成功・worker join・runtime側handoff成功・host検証成功を確認して返す。
auditだけ既存Exportを選び、元状態との一致を確認した。
この終了protocol変更は製品化時のレビュー対象であり、既存Export ACKのguardを一般に削除する変更ではない。

## 5. 残件と推薦への影響

- **通常時の資源管理**：試作は削除済みnodeのbackingもDB終了まで保持する。
  open handleの寿命に従う回収、FD上限、disk pressure、ENOSPC、mmap失敗、
  部分失敗・cleanupのエラー伝播を製品向けに整理する必要がある。
  初回保持をheapからfile backingへ移しただけで、メモリ費用が減ったとは言わない。
- **同一filesystemの移動**：今回はライブラリの一時領域内でrenameが成立した。
  任意のsnapshot_to先、異なるfilesystemへのrenameは未対応・未検証。
  一時Snapshotのfast pathと保存/import経路を分ける設計が必要。
- **派生基準・拡張**：子は既存MAP_PRIVATEであり、変更内容は元FDへ入らない。
  今回は派生Snapshotを既存コピー経路に残した。派生も軽くするならD等との比較が必要。
- **性能の範囲**：小〜中規模の2子で利益を確認した。
  大規模、多数・並列Fork、保持時間、GC・RSS・dirty page/I/Oの費用は未測定。
  これは「Eは速くならなかった」という未確定ではなく、確認範囲の外である。
- **製品化の所有元**：MemFSの正式所有元、生成経路、終了・取得protocolへ落とし込み、
  独立再生成と対象platformの関連検証が必要。今回のoverlayをそのままmainへ入れない。

これらは今回の限定結果を否定しないが、製品採用へ直接進む条件は満たしていない。
Human Review後の次の作業は、追加の測定を無制限に増やすことではなく、
上記の所有・エラー・適用範囲を有限な製品化設計へまとめることを推薦する。

## 6. 再現・保存

[適用script](../../benchmarks/spikes/e-handoff/instrument.py)、
[共有backing](../../benchmarks/spikes/e-handoff/observer.go.txt)、
[停止後handoff](../../benchmarks/spikes/e-handoff/handoff.go.txt)、
[host側publish](../../benchmarks/spikes/e-handoff/publish.go.txt)、
[Python計測](../../benchmarks/spikes/e-handoff/run.py)、
[Python境界試験](../../benchmarks/spikes/e-handoff/boundaries.py)、
[集計](../../benchmarks/spikes/e-handoff/summarize.py)。

1. baselineを隔離checkoutし `scripts/git_identity.py inspect HEAD`。
2. Go1.26.8、隔離GOCACHE、CGO_ENABLED=1で `go build -p 2 -o <temp>/control-host ./cmd/mariamem-host`。
3. 計測source配置後 `python3 benchmarks/spikes/e-handoff/instrument.py`。
4. 同じGoで `go build -p 2 -o <temp>/handoff-host ./cmd/mariamem-host`。
5. `go test ./internal/generatedgo/code/base -run '^(TestE|TestMemFSGrowth|TestPrepared|TestOwnedMapped)' -count=1 -v`。
   `go test ./internal/snapshot ./internal/host -run 'Snapshot|Owned|Manifest|Verification|Publish' -count=1`。
6. 専用venvにPyMySQL1.2.3。TMPDIRも専用。
   runnerに `--control <control-host> --observed <handoff-host> --output <fresh-dir>`。
   pilotは `--pilot`、監査は `--audit`、本計測は `--repeats 5`、出力先を分ける。
7. `boundaries.py --host <handoff-host> --output <fresh-dir>`。
8. `summarize.py <campaign-dir> <summary.json>`。

budget12 GiB/min-free16 GiB、build上限1200秒、各harness呼出し上限300秒。
[pre/post hash](e-handoff-evidence/instrumentation.json)でoverlayを確認してruntimeを復元し、
source・小さな証拠だけをcommit/pushする。[証拠checksums](e-handoff-evidence/checksums.json)。
tempのbinary/cache/venvとworktreeは保存後にcleanup。実結果はworkspace receiptと最終報告に残す。
mainの既存未commit資料3件には変更を加えていない。
