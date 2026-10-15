# D＋E: 子のブロックI/O限定spike

## Human Review

今回判断したいのは、**子のI/Oを全面的にブロック化する案を、速度改善のために
さらに深掘りするか**です。推薦は、今回のD＋Eをそのまま製品化する作業は保留し、
ブロック方式を割当削減の候補として残すことです。小変更テストで子のGo累積割当は
約73%減りましたが、テスト全体の時間と最大RSSの改善にはつながりませんでした。

最も強い反論は、割当削減そのものに価値があり、より多くの子・拡張・別の負荷で
効果が出る可能性があることです。それは未否定です。ただし今回の2子ではGC回数も
同じで、待ち時間・最大RSSを減らせた証拠はありません。追加投資をするなら
割当削減を何に結びつけたいかを選び直す根拠になります。今回の結果からD全般や
D独自のSnapshot所有移転まで棄却しません。

**承認されたD＋Eの子I/O比較は完了**です。共有基準とSnapshotをEのままに保つ
範囲へHumanが明示的に変更しました。D独自のSnapshot、Python host間の新しい
ブロック共有方式は未評価です。main統合・正式採用・リリース準備には進みません。

## 何を比較したか

| 境界 | E | D＋E |
| --- | --- | --- |
| 準備DB、Snapshot | Eの共有backing・停止後handoff・全内容検査 | 同一 |
| 子の基準ファイル | MAP_PRIVATE、OSのページ単位CoW | 読み取り専用mapping＋子専用16 KiBブロック |
| 子が新規作成するDBファイル | 既存の連続Go heap | 論理EOFと確保ブロックを分離 |
| 部分書き込み | OS CoW／既存の成長処理 | 未変更ブロックの必要な元内容をコピーして変更 |
| ブロック全体の上書き | 同上 | 元内容を読まず新ブロックへ書く |
| 子からのSnapshot | 既存export/copy経路 | 同じ経路。ブロックを論理ファイルとして読む |

**Eは既にページ単位CoWであり、Dだけが小単位コピーできるわけではありません。**
今回はEのSnapshotで残る検査・受け渡しを省いていません。Snapshot時間の差を
D独自のSnapshot改善とは呼びません。

実Python APIを使用し、同じbinaryでenv切替して比較しました。子の既存prepared
ファイルと新規`mariadb/`ファイルをD化し、それ以外の一時export領域は従来方式です。
namespace/node/FDとMemFS lockは維持。read/write/ReadAt/WriteAt、size/stat、
seek/append、Allocate、truncate、WriteFileを接続し、実際のI/Oをブロックへ向けました。
ブロックsizeは16 KiB固定の試作条件で、最適値を探索したものではありません。

## 全体時間と子の内訳

macOS 27.0.1 arm64、Go 1.26.8、Python 3.9.6、PyMySQL 1.2.3。
各規模・モード5回、順序を交互に変更。小規模は各100行・payload 256 bytes、
中規模は各10,000行・payload 1,024 bytes。users/orders、index、外部キーを準備し、
子2個で小さなinsert/update/delete、commit/rollback、兄弟隔離を確認しました。

全体はFresh開始→migration/seed→Snapshot→子2個の接続・CRUD・終了→基準Close。
各run後の追加全量hash確認は時間から除外。中央値、単位ms。各区間の中央値の和は
全体中央値と一致しません。同じSQLで各回準備し直すため、異なるrun間でDBファイルの
バイト列が完全同一という測定ではありません。

| 指標 | 小規模 E | 小規模 D＋E | 中規模 E | 中規模 D＋E |
| --- | ---: | ---: | ---: | ---: |
| **テスト全体** | **449.4** | **449.2** | **1,271.0** | **1,291.8** |
| 準備側合計（Fresh＋seed＋Snapshot） | 317.0 | 307.7 | 1,100.9 | 1,124.8 |
| Snapshot作成 | 249.4 | 248.9 | 270.4 | 276.0 |
| 子2個合計（起動・接続・CRUD・終了） | 126.2 | 126.6 | 160.7 | 159.8 |
| 起動・子1個 | 51.4 | 51.8 | 52.5 | 50.6 |
| CRUD・子1個 | 3.3 | 3.0 | 19.7 | 19.4 |
| Close・子1個 | 4.6 | 4.7 | 4.6 | 4.7 |

小規模は中央値で−0.06%、対応組ではD＋Eが3/5速い。中規模は中央値で+1.63%、
5/5組でD＋Eが遅い結果でした。しかし変更していない準備側にも差があり、
子2個の処理時間は近い値です。中規模の約21 ms全量をブロックI/Oの悪化とは
帰属しません。Snapshotや起動の数ms差も確立した効果とは扱いません。

対応差の中央値/範囲は、小規模−2.3 ms（−20.2〜+9.8）、中規模+17.7 ms
（+3.9〜+34.9）。メモリ採取付き別campaignでは、D＋Eが速い組は小規模1/3、
中規模2/3でした。少数試行・共有host上のばらつきを残したまま、今回確認できた
結論を「明確な全体高速化なし」とします。統計的同等性の証明ではありません。

pilotは別保存して集計から除外。最初のEのFresh開始には1,063.7 msの待ちがあり、
これをDの効果と比較しません。原因調査は今回行っていません。

[集計・対応差・範囲](d-block-cow-evidence/summary.json)、
[plain入力](d-block-cow-evidence/plain/inputs.json)、
[実行結果](d-block-cow-evidence/plain.txt)。

## 割当は減ったが、最大RSSは減らなかった

通常の時間比較と分けて各規模・モード3回、計6子を測定。単位MiB、子ごとの中央値。

| 指標 | 小規模 E | 小規模 D＋E | 中規模 E | 中規模 D＋E |
| --- | ---: | ---: | ---: | ---: |
| **Go累積割当量** | **12.85** | **3.46** | **12.86** | **3.46** |
| 終了処理内のHeapAlloc | 12.73 | 3.26 | 12.74 | 3.28 |
| プロセス最大RSS | 120.82 | 121.82 | 122.65 | 123.43 |
| GC回数 | 1 | 1 | 1 | 1 |

Go累積割当は約9.4 MiB/子、約73%減少しました。最大RSSは約0.8〜1.0 MiB増の
近い値で、低下は未確認です。準備hostの最大RSSは両方式とも小規模約252 MiB、
中規模約280 MiB。全体の最大メモリが減ったという結果ではありません。

Goの論理的な割当量と、OSが実際にresidentにしているページは別の量です。
未touch領域やOS CoW等が違いを説明し得ますが、今回その寄与は分解していません。
Go HeapAllocはguest linear memory等のmmapを含まず、物理メモリ総量でもありません。

採取位置はguest worker joinとguest memory/descriptor/mappingの解放後、runtimeの
終了通知前です。MemFS参照は残り、強制GCはしていないため、HeapAllocをClose後の
リーク量とは呼びません。最大RSSは各Go hostのRUSAGE_SELFで、Pythonを含む全体値
や同時プロセス合計ではありません。峰値を足し算して全体peakともしません。
同じhost・同じAPIで行った[bytes単位の照合](d-block-cow-evidence/rss-calibration.txt)を
前回C＋Eから再利用しました。今回の再計測と混同しません。

## 実際に使ったブロック

plainのD＋E・20子すべてで、子専用payload確保は**2.547 MiB**、基準からの
内容コピーは**49,204 bytes（約48 KiB）**でした。全ブロック上書きは基準を
コピーせず、SQL側の新内容を書きます。コピー量だけを総書込量とは扱いません。

| ファイル／処理 | 論理サイズ等 | D＋Eの実行結果・子1個 |
| --- | --- | --- |
| redo `ib_logfile0` | 96 MiB | 子専用32 KiB、基準コピー32 KiB |
| 新しい一時表領域 `ibtmp1` | 12 MiB | 130ブロック、2.031 MiBを確保。基準コピーなし |
| その他の更新ファイル | undo/ibdata/Aria/users/orders等 | 必要ブロックのみ確保。全ブロック上書きは元のreadを省略 |
| metadataだけのファイル・未変更箇所 | 基準の読み取り | 子専用payloadを確保せず基準を読む |

比較対象Eの新規ファイルは既存連続heap方式です。一時表領域の疎な確保が割当削減を
説明する主な実装差であり、CPU profileで全割当の因果帰属を完了したという意味では
ありません。D化した既存ファイルのブロックもGo heapへ加わるため、12 MiB全部が
そのまま削減されるわけではありません。

前回[C＋E](https://github.com/masahitojp/mariamem/blob/21a01a20d8f453fb626fd6fb724ec0ec1ba287f7/docs/reviews/ce-file-cow-spike.md)
では各子138〜159 MiBのファイル内容コピーが生じました。今回その全量copy-upは
避けられました。ただしEも元からOSのページCoWを使うため、これをEに対する
新しい速度利益とは扱いません。EのD用カウンタ0は「Dの計測経路なし」を意味し、
OS内のコピーやprivate pageが0という意味ではありません。

[小規模の全ファイル記録](d-block-cow-evidence/plain/n100-r0-de/result.json)、
[中規模](d-block-cow-evidence/plain/n10000-r0-de/result.json)。

## 検証と未確認範囲

| 項目 | 判定 | 証拠／範囲 |
| --- | --- | --- |
| ブロック境界、部分I/O、全量上書き、EOF、負の範囲・overflow拒否 | PASS | [統合unit](d-block-cow-evidence/integration-unit.txt)のD primitive 4件。決定的2,000操作と連続配列モデルを照合 |
| size/seek/append/Allocate、shrink/regrow、rename/unlink/開いたFD、親FD Close、兄弟隔離 | PASS | 同unitのD integration 4件 |
| 同一ファイルに複数handleから並行書込 | PASS | [限定race test](d-block-cow-evidence/unit-race.txt)。MemFS lock下の8件。guest共有メモリ全体の保証ではない |
| 既存E/backing/handoff、MemFS/Prepared/Owned tests | PASS | unitのcontrol経路。既存連続mapping内部assertionをDに適用したと主張しない |
| Python実DB、commit/rollback、基準不変hash、兄弟隔離 | PASS | plain20 workflow/40子＋resource12 workflow/24子 |
| 親Close後の2生存子、派生Snapshot、transaction拒否 | PASS | [E](d-block-cow-evidence/boundaries-e/result.json) / [D＋E](d-block-cow-evidence/boundaries-de/result.json) |
| 4種handoff失敗、元DB終了・保存先削除、Python同size破損拒否 | PASS | 同boundary。完全性検査は維持 |
| 一時ディレクトリcleanup | PASS | boundary＋campaign後scratch空 |
| overlay復元→再適用のidentity | PASS | [記録](d-block-cow-evidence/overlay-reproduction.json)。runtimeは再びbaselineへ戻した |
| 公開ソース検査 | 追加ファイルPASS / 全体FAIL | [結果](d-block-cow-evidence/public-source-scope.json)。baseline既存`v050-startup-tail-source-fix-evidence/ubuntu/measurement.log`のallowlist違反。削除・guard緩和はしていない |
| Ubuntu x86_64、macOS15、他Go/Python | SKIP | 今回はローカルmacOS27.0.1 arm64のみ |
| 大規模、4並列、多数子、長時間・深い派生世代、全異常終了 | 未実施 | 限定spikeの範囲外 |
| D独自Snapshot・新共有形式・保存形式 | 未評価 | Human合意により今回の範囲から外した |

16 KiBブロックのindex/境界処理・map・counterの費用は実時間に含まれています。
counter除去版との比較やCPU内訳測定は行っていません。D記録用に作成nodeへの参照を
guest終了まで保持しており、unlink後の最早解放を完成させた製品実装ではありません。
preparedの読み取り専用mappingは全worker終了まで保持します。実hostの経路である
MapPreparedHandlesを変更し、legacy MapPreparedFilesは変更していません。

E由来の同一filesystem内handoff制限と、派生Snapshotが従来copy/export経路である
制限は引き継ぎます。将来の採用にはcanonical所有元への実装、全エラー処理と解放、
対象platformの確認が必要です。このspikeは正式生成・Qualificationではありません。

## 所有元、入力と再現

- branch: `experiment/d-block-cow`。main baseline source_commit:
  `a8137b8b444f86068d3128a291e3a848adfdfd56`。
  [git_identity](d-block-cow-evidence/source-identity.json)をbuild/test前に確認。
- Eの所有元: `3ce25c29ebceb2bdfb6b430391f400ad3d8d90e0`。
  Python harnessはC＋E `21a01a20d8f453fb626fd6fb724ec0ec1ba287f7`から再利用。
- guest MariaDB 12.3.3、Wasm SHA256:
  `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- binary SHA256:
  `eab6ff4c3bb57f8c8c9a1fc56f6660fe2431b754d06b6855a4180e12b447b3bc`。
  [build identity/overlay hashes](d-block-cow-evidence/build-identity.json)。
- 試作所有元: [instrument.py](../../benchmarks/spikes/d-block-cow/instrument.py)、
  [block primitive](../../benchmarks/spikes/d-block-cow/block.go.txt)、
  [MemFS接続・観測](../../benchmarks/spikes/d-block-cow/integration.go.txt)。
  exact-baseline overlayを用い、canonical guest/生成物/provenanceは変更しない。

baselineから使い捨てworktreeを作り、このbranchの`benchmarks/spikes/d-block-cow`を
配置します。Go 1.26.8のgo/gofmtをGO_BIN/GOFMTへ、GOCACHEとTMPDIRをworkspace内の
絶対pathへ指定。source identityを確認し、以下を実行します。

```sh
python3 benchmarks/spikes/d-block-cow/instrument.py
"$GO_BIN" test ./internal/generatedgo/code/base -run 'Test(D|E|MemFS|Prepared|Owned)' -count=1 -v
"$GO_BIN" test -race ./internal/generatedgo/code/base -run '^TestD(Block|Integration)' -count=1 -v
"$GO_BIN" build -p 2 -o ../temp/d-host ./cmd/mariamem-host
python3 -m venv ../temp/venv
../temp/venv/bin/python -m pip install --no-cache-dir pymysql==1.2.3
mkdir -p ../temp/scratch
../temp/venv/bin/python benchmarks/spikes/d-block-cow/run.py --host ../temp/d-host --output ../evidence/pilot --pilot
python3 benchmarks/spikes/d-block-cow/campaign.py --workspace /absolute/path/to/workspace
python3 benchmarks/spikes/d-block-cow/summarize.py ../evidence
python3 benchmarks/spikes/d-block-cow/restore.py
```

実際はbuildも既存experiment_disk.pyで監視。空き16 GiB以上、所有12 GiB以下、
build上限1,200秒、campaign各段300秒。[campaign結果](d-block-cow-evidence/campaign.txt)。
overlayは復元後の再適用hash一致を確認し、再び復元。binary独立2回buildを行ったという
意味ではありません。共通binary/env切替でEとD＋Eを比較しています。

記録は小さなJSON/text。各runのresult.jsonにmanifest、handoff/publish、全D file記録を
保存し、重複個別出力は省略。logはtxtへ変更し、build/python-tools出力のhome絶対pathを
`<USER_HOME>`に正規化。値・判定は変更しません。[保存証拠hash](d-block-cow-evidence/checksums.json)。

先行の[block-storage調査](block-storage-design-discovery.md)と
[製品契約](../decisions/snapshot-product-contract.md)を参照。
古い調査内のA〜F記号は当時の分類で、今回のC/D/E記号とは異なります。
mainの既存project-status変更、未追跡設計資料2件は触れていません。
