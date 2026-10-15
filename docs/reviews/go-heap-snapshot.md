# Go同一プロセス・一時ファイルなしSnapshotの限定spike

2026-10-16。macOS arm64。実guest接続・小中規模の比較を行った。
製品採用、main統合、リリース準備は行っていない。

## Human Review

**今の判断は、このメモリ内方式を有力候補として残し、Pythonでの提供方式の比較へ進むかです。推薦は進むことです。**
Goの通常の「準備→Snapshot→2子のCRUD→Close」で、全体時間とメモリの両方に利益が出た。
Snapshot用のファイルを作らずに、独立した子と派生基準を実guestで扱えることを確認できた。
子のMariaDB起動そのものを大幅に速くした結果ではなく、主な利益はSnapshotの準備費用を減らした点にある。

**最も強い反論は、この利益がGoの同一プロセスという条件に依存し、現在のPythonのDB別プロセスへそのまま移せないことです。**
このため採用やPythonでの同率改善は推薦しない。利用者がdaemonを管理しない手軽さと独立DBの価値を
維持したまま、この所有形態をPythonでどう提供できるかを次の設計比較にする。構成はまだ一本化せず、追加実装も開始しない。

元の問いへの答えは「**一時ファイルを使わない方式は、Go版なら実guestで安く試せた。
今回の小中規模では、検査と隔離を維持したままテスト全体の利益が出た**」である。
Native Ubuntu x86_64は未検証であり、OS間の性能が同じという結論ではない。

## 何をなくし、何を残したか

[前回D2](d2-guest.md)はPythonの別hostへ基準を渡すために内部一時ファイルを使った。
今回は同一Goプロセス内に閉じ、16 KiBブロックをGo heapに保持する。
停止済み準備DBの内容を不変基準へ引き継ぎ、子にはブロックの参照を渡し、子の変更だけを新しいheapブロックへ書く。

- Snapshot内容を保持するホストの一時ファイル、file mapping、FD移管、配置表のJSON転送を使用しない。
- DB内部の論理ファイルはMemFSとして存在する。GoのStartが作る空の管理ディレクトリ、
  SQLのsocket、既存guest通信のpipe、Wasmの線形メモリ管理まで廃止したわけではない。
- 一時Snapshotの公開Go呼出しは従来どおり。計測用の診断メソッドは隔離overlayにだけ存在する。
- `snapshot_to`相当の明示保存、外部Snapshot import、Python接続はこの試作の対象外。
  保存APIを必須条件にしない仮定を試しており、正式なAPI削除決定ではない。
- guest整合停止と全workerのjoin後にcaptureする。元内容hash、固定した基準の検査、所有取得の検査という
  **3回の全論理内容走査を維持**する。未使用zero領域もhash対象。検査省略による高速化ではない。
- 子には書込可能な基準を渡さず、内部実装の所有規則で不変性を守る。OSのreadonly保護ではない。
  親Closeは参照を外す。開始済み子の参照は残り、最後の参照がなくなった後にGCが回収可能になる。

ホストfile exportを誤って通ると失敗する実験guardを追加し、Snapshot publish/importを通らないコード経路を確認した。
全heap workflowでSnapshot取得後のscratchはfile/dir/bytesすべて0、終了後も0だった。
`payload_file_bytes=0`は経路の設計値であり、全syscallを記録したI/Oトレースではない。
Snapshot時のpayloadコピーも構造上0。hash用bufferへの読み込み、SQL write、子の部分コピーまで0という意味ではない。

## 比較条件

比較は**Goの従来Snapshot経路対Goのheap経路**。同一binaryの環境変数切替で、同じSQLと終了手順を使う。
対照側は追加hookが無効な従来ファイル経路であり、無改変binaryを別にビルドした比較ではない。
以前のPython E/D2の数値とは、driver、プロセス構成、対照が違うため直接比較しない。

- users/ordersの2表、unique index・外部キー。小は各100行・payload256 bytes、中は各10,000行・payload1,024 bytes。
  論理Snapshot内容は約138／159 MiB。SQL投入は500行ずつ、同じtransaction/commit。
- 各ケースを新しいGoプロセスと空のTMPDIRで実行。通常の2子は順番に起動し、insert/update/delete、
  commit/rollback、兄弟の初期状態を検査してCloseする。小中それぞれ5組、順序を巡ごとに反転。
- 全体時間にStart、migration/seed、Snapshot、2子の接続/CRUD/切断/Close、基準Closeを含む。
  Snapshot取得に必要な検査は含む。測定用のscratch走査と子終了後の追加基準hash auditは除く。
- 資源確認は別campaign各3組。MemStats/getrusage取得の所要時間を全体から除くが、その実行の影響はあり得るため主計測と混ぜない。
  最後に強制GCした値は診断用で、通常のCloseや全体時間に算入しない。
- 既存Export一致のaudit、寿命・失敗境界、pilotも主集計から分離。

## 最終測定

中央値、ms。各区間中央値の和は全体中央値に一致しない。

| 区間 | 小 従来 | 小 heap | 中 従来 | 中 heap |
| --- | ---: | ---: | ---: | ---: |
| 準備DB Start | 48.82 | 46.79 | 48.96 | 46.73 |
| migration/seed | 14.15 | 14.41 | 741.64 | 735.45 |
| Snapshot取得 | 354.01 | 192.52 | 359.99 | 218.19 |
| 子起動：1子 | 52.81 | 51.03 | 54.77 | 51.36 |
| CRUD：1子 | 4.66 | 4.95 | 19.60 | 19.75 |
| 2子の全処理 | 135.48 | 130.39 | 169.39 | 161.93 |
| 基準Close | 2.23 | 0.00 | 2.06 | 0.00 |
| **全体** | 556.12 | 386.16 | 1,333.00 | 1,163.72 |

小は中央値で30.56%短縮、同じ巡の短縮は164.01〜342.45 ms、速かった組は5/5。
中は中央値で12.70%短縮、同じ巡の短縮は151.82〜175.55 ms、速かった組は5/5。
小の対照には全体729.21 msの遅い1回も含む。除外せず保存し、中央値と全組の対応差を示した。
heapのSnapshotは、元hash・構成作成と2回の検査が合計でほぼ全時間を占める。

主な短縮はSnapshot取得。heap方式でも3回の全内容検査が残るため、Snapshotは無料にはならない。
子の起動に大幅な改善が出たとは判断しない。
全値と対応差は[主計測](go-heap-snapshot-evidence/plain.json)と[集計](go-heap-snapshot-evidence/summary.json)。

初回の対照ではWriteFileのcopyを`append(nil, data...)`で表現していた。
最終確認でcanonicalの`make(len)+copy`と一致させ、同じ範囲を再計測した。
スライス容量の扱いまで揃えるための修正であり、初回と最終の数字は混ぜていない。
[初回結果](go-heap-snapshot-evidence/initial/summary.json)も入力identityとともに保存。

## メモリと回収

別campaign各3組の中央値、MiB。Go累積割当は全体終了時点。

| 指標 | 小 従来 | 小 heap | 中 従来 | 中 heap |
| --- | ---: | ---: | ---: | ---: |
| Snapshot取得までの最大RSS | 532.44 | 123.02 | 641.86 | 163.03 |
| 全体の最大RSS | 548.16 | 128.98 | 655.45 | 166.27 |
| 全体のGo累積割当 | 455.76 | 14.51 | 690.80 | 121.99 |
| Close直後のHeapAlloc | 442.67 | 10.36 | 507.93 | 43.61 |
| 診断用GC後のHeapAlloc | 0.28 | 0.28 | 0.29 | 0.29 |

基準が保持するデータblock量は小約3.03 MiB、中約27.31 MiB。配置metadata・allocator overheadは別。
資源計測つき全体時間でも両規模3/3組でheapが速かった。小28.04%、中11.59%短縮。

最大RSSは一つのGoプロセスで準備と2子を実行した間の高水位。各DBのRSSを足した値ではない。
OSのfilesystem cacheを含むシステム全体のメモリや、Pythonでのメモリ使用量でもない。

heap方式は論理zero領域を実体化せず、停止後も必要なブロックだけを保持する。
従来の全量連続領域・guest Exportコピー・ホストへの転送bufferを経由しない。
利益を「一時ファイルを作らないことだけの効果」とは分離していない。ブロック表現と取得経路を含む候補全体の結果である。

最後の強制GC後、両方式のHeapAllocは小さくなった。Close時点でOSへメモリが即時返却される保証ではない。
Maxrssは過去の最大値なのでGC後も下がらない。GC後の現在RSSは今回測っていない。
長期反復・多数の派生世代・巨大な基準での保持量は対象外。

## 正しさ・所有の確認

| 確認 | 結果・根拠 |
| --- | --- |
| 実guest Exportとメモリ内基準の全inventory/content一致 | PASS、小規模の分離[audit](go-heap-snapshot-evidence/audit.json)。大規模までの証明ではない |
| 小中のCRUD・commit/rollback・兄弟隔離 | PASS、主計測20 workflowと資源計測12 workflowの全run |
| active transaction拒否後の元DB継続使用 | PASS、`ErrTransactionActive`まで確認 |
| 親Close後の2子、子から派生基準、派生基準Close後の第3子 | PASS、[境界結果](go-heap-snapshot-evidence/boundaries.json)。兄弟は元の内容を維持 |
| 2子で同時に更新し、それぞれ別の結果を保持 | PASS、同境界結果。並列性能の計測ではない |
| freeze失敗、基準検査前破損、所有取得前破損 | PASS、想定した拒否理由・元DB終了・一時資源と登録の回収。破損注入はFresh候補に限定 |
| 部分write、EOF、shrink/regrow、rename/unlink・開いたFDのidentity、guest不一致・不正block範囲 | PASS、[部品/既存境界test](go-heap-snapshot-evidence/unit.txt) |
| heap/COW部品と並行FD操作のrace test | PASS、[記録](go-heap-snapshot-evidence/unit-race.txt)。全guestのrace評価や一般的安全性の証明ではない |
| overlayの再適用一致・canonicalへの復元 | PASS、[記録](go-heap-snapshot-evidence/overlay-replay.json)。独立binary再生成とは区別 |
| Native Ubuntu x86_64 | SKIP、今回利用可能なnative環境なし |
| Python、明示保存/import、全platform Qualification、大規模/長期/非協調worker終了 | 今回の対象外、未実施 |

子の構成metadataは別に作り、親のデータを直接更新しない。元guestのwriterが終了してから共有する。
開始済み子は自分の参照を持つため、Snapshot.Closeは子を壊さない。
取得後の任意のメモリ破損をForkごとに再検出する約束は追加していない。
heap captureの登録は事前条件通過後に行い、成功・失敗とも削除する。
製品化時には所有規則の正式実装・容量/世代管理・API/言語境界・対応platformの検証が必要。

## 入力と再現

- main runtime基点：`a8137b8b444f86068d3128a291e3a848adfdfd56`。
- 作業branch開始：`87008e22693eb0cae44252f6c5d2c3c4715ac8fc`。前回D2の記録とblock/FS fixtureを再利用。
- `git_identity.py`でcommit型を確認してからbuild/計測。実測は開始commit＋記録されたoverlayであり、開始commit単体の数値ではない。
- MariaDB12.3.3、Wasm SHA256 `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
  guest/converter/正式生成物の更新はない。
- macOS27.0.1 arm64、Go1.26.8、go-sql-driver/mysql1.9.3、既存go.mod/go.sumの固定依存を使用。
- [build入力とbinary hash](go-heap-snapshot-evidence/build-input.json)、[環境](go-heap-snapshot-evidence/environment.json)、
  [最終source hash](go-heap-snapshot-evidence/final-source-sha256.json)、[証拠checksum](go-heap-snapshot-evidence/checksums.json)。
- [再現コードと手順](../../benchmarks/spikes/go-heap-snapshot/README.md)。実験用テンプレートからoverlayを作り、
  計測後は復元する。canonical/generated runtimeの直接変更をcommitしない。

既存mainのユーザー変更3件は保持した。実験branchへ結果を保存し、再生成可能なbinary/cache/worktreeはcleanupする。
ここでHuman Reviewへ戻し、Python構成変更や製品採用を自動で開始しない。
