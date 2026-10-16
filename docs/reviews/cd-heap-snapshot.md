# C＋一時ファイルなし vs D＋一時ファイルなし

## Human Review

今回の判断は、**同一プロセス内のメモリSnapshotで、Cの単純さを優先するか、Dを引き続き主候補として扱うか**です。推薦は、Cを比較対象として残し、Dを主候補とすることです。実guestの準備→Snapshot→子2個のCRUD→終了で、DはCより小規模11.2%、中規模6.2%短く、各5組すべて速くなりました。別枠のメモリ計測でもDが小さく、Cのファイル全体コピーが小変更テストにも発生しています。**製品採用の決定や追加実験の開始はしません。**

最も強い反論は、Cなら既存の連続byte列と成長処理を活用でき、D固有のブロック境界・継承・部分更新を実装／保守しなくてよい点です。この利点はあります。ただし、両案共通の所有権と終了処理、Pythonへの接続は省けず、Cの単純さだけで製品化全体が大幅に安くなるとは言えません。macOS arm64の小・中規模、子2個だけの比較であり、他OS・大規模・多数同時Forkまで外挿しません。

承認範囲の比較spikeは完了。main、guest、公開API、リリースには反映せず、Human Reviewへ戻ります。

## 今回揃えた前提

直前の[D Go heap試作](go-heap-snapshot.md)を基点に、同じバイナリでC/Dを切り替えました。以前の[C＋E](https://github.com/masahitojp/mariamem/blob/21a01a20d8f453fb626fd6fb724ec0ec1ba287f7/docs/reviews/ce-file-cow-spike.md)はファイルmappingを共有元にしていました。今回はCもDもGo heapを所有するため、過去のPython E/D2との数値の直接比較はしません。

| 境界 | C | D |
| --- | --- | --- |
| 準備DB | 連続したbyte列、既存MemFSの成長規則 | 16 KiBブロック、未書き込み領域は暗黙のゼロ |
| Snapshot | 停止済みguestのファイルsliceを固定・所有移転 | 停止済みguestのブロックを固定・所有移転 |
| Snapshot payloadコピー／一時ファイル | なし | なし |
| 検査 | 元・固定後・所有取得時の3回、論理内容全量 | 同じ |
| Fork | ファイルsliceを共有、最初の変更でファイル全体を複製 | ブロック参照を共有、変更ブロックを子が確保 |
| 縮小と再拡張 | 縮小は長さ変更。成長前に私有化し、切り落とした領域をゼロ化 | 継承範囲の切断、dirtyブロック整理、ゼロ領域として再拡張 |
| Close／子から再Snapshot | Go参照の寿命で所有。子の変更は親・兄弟へ反映しない | 同じ契約 |

Snapshotの保存先・再読込・FD受け渡し・Snapshot用mmapは使いません。従来からある空のruntime管理ディレクトリ、SQL socket、Wasm線形メモリのmmapは残ります。「OS操作が一切ない」という意味ではありません。PythonのDBごとに別hostを起動する境界は未変更・未検証です。

Cは既存D用MemFS dispatchの内側に小さな連続ファイル実装を接続しています。D用フィールドが構造体に残りますが、Cデータにはブロックmap／ブロック分割I/Oを使いません。製品向けの型整理はしていません。元ソースと隔離overlayの対応は[実装](../../benchmarks/spikes/cd-heap-snapshot/instrument.py)を参照してください。

## 計測結果

macOS arm64、Go 1.26.8、MariaDB 12.3.3。小規模はusers/orders各100行・payload256 bytes、中規模は各10,000行・payload1,024 bytes。index/外部キーを含め、子1でinsert/commit、子2でupdate/commit・delete/rollback・delete/commitを実行しました。

fresh processをC/D交互に各5回。全体は準備DB起動・migration/seed・Snapshot・子2個の起動/接続/CRUD/切断/Close・基準Closeです。最終診断hash、scratch検査、資源採取の時間は除外。必要なSnapshotの3回検査は含みます。試行を除外していません。各区間の中央値の和は全体中央値と一致しません。

| 中央値（ms） | 小 C | 小 D | 中 C | 中 D |
| --- | ---: | ---: | ---: | ---: |
| **テスト全体** | **433.75** | **385.34** | **1229.98** | **1153.14** |
| 準備DB起動 | 50.03 | 47.90 | 49.59 | 47.42 |
| migration/seed | 13.95 | 14.60 | 734.20 | 727.28 |
| Snapshot | 209.59 | 188.48 | 237.27 | 218.07 |
| 子1個の起動 | 50.98 | 50.89 | 52.79 | 50.89 |
| 子1個のCRUD | 14.65 | 5.04 | 29.97 | 20.01 |
| 子1個のClose | 7.26 | 2.49 | 11.13 | 2.53 |

Dによる全体の短縮は中央値の差で48.41 / 76.84 ms。対応差は小41.38〜58.88 ms、中60.58〜82.02 msでした。**子起動そのものには大きな差がありません。** 全体範囲は小C426.72〜445.66 / D380.17〜389.05 ms、中C1224.54〜1235.01 / D1147.75〜1173.65 msです。

[集計と全試行範囲](cd-heap-snapshot-evidence/summary.json)、[plain生データ](cd-heap-snapshot-evidence/plain.json)。初回pilotは別保存し、集計に混ぜていません。sandboxでの初回listen拒否も計測値ではありません。

### メモリとコピーの内訳

別campaignで各3組。中央値です。maxRSSは**全体プロセスの最大値**、累積allocationはGo全体のTotalAllocであり、現在残っているメモリ量ではありません。

| 指標（MiB） | 小 C | 小 D | 中 C | 中 D |
| --- | ---: | ---: | ---: | ---: |
| 全体maxRSS | 540.47 | 129.31 | 675.89 | 165.53 |
| 全体Go累積allocation | 453.79 | 14.52 | 688.77 | 122.00 |
| 基準のpayload保持容量（plainから） | 138.39 | 3.05 | 162.86 | 27.31 |

基準の保持容量はslice capacity／保持ブロック容量の集計で、metadataや他のGo heapを含みません。Dは論理ゼロを実体化しないため、同じ論理ファイルサイズでも小さくなります。Cの余剰capacityも保持容量に含めています。

資源計測全12子のCコピーは、各子9ファイル、**138.23 / 158.58 MiB**。全例、CRUD時に`ib_logfile0`の96 MiB、Close時に残り8ファイルの42.23 / 62.58 MiBです。起動時の共有元コピーは0でした。残りはundo、ibdata、Ariaログ/制御、users/ordersです。小変更SQLでもMariaDBのログ書き込みと終了処理が全ファイルコピーを引き起こします。

Dの継承元コピーは全ワークフローで約0.094 MiB（2子合計）。dirtyブロックの確保は準備DBも含め約10.20 / 34.47 MiBでした。全ブロック上書きでは継承元を読まないため、コピー量と確保量は一致しません。これらはstorage層のカウンタで、Go全体の割当とは区別します。

Snapshot自体のDの約19〜21 ms差はコピー削減ではありません。両者ともpayloadをコピーせず全量検査し、Cは実体のある連続領域を読み、Dは暗黙のゼロを含む論理領域を読む違いがあります。内訳は元hash+metadata、固定後、所有取得時の検査に記録しました。cache/GC/メモリ帯域への厳密な因果分解はしておらず、全体差すべてをCoWコピーのせいにはしません。

資源campaignでも全6組でDが速く、小C438.56 / D383.09 ms、中C1225.56 / D1156.69 msでした。plainと混ぜて平均しません。最後の強制GC後のHeapAllocは両者約0.27〜0.30 MiBですが、OSへの即時RSS返却や任意の寿命での漏れ不在の保証ではありません。[資源生データ・ファイル/段階別コピー](cd-heap-snapshot-evidence/resources.json)。

## 変更コストの回答

**データ管理層の実装・保守はCの方が軽い、という理解で合っています。全体の製品化費用がどれだけ小さいかは未算定です。**

| 必要な仕事 | C | D |
| --- | --- | --- |
| byteデータ管理 | slice・共有フラグ・初回copy。通常read/writeと成長は既存規則を再利用 | ブロック番号/offset・継承範囲・dirty map・部分/全上書き・ゼロ領域 |
| 縮小/成長の検証 | 共有元を壊さず切り落とし/ゼロ化。ファイル単位 | 加えてブロック境界、最終partialブロック、継承とdirtyの重なり |
| 固定・親子・派生・Close・失敗・guest identity・内容検査 | 共通で必要 | 共通で必要 |
| Python別プロセスへの接続 | このGo spikeからは別途設計が必要 | 同じ |
| 今回より大きい/同時多数のケース・別native OS・製品検証 | 未実施 | 未実施 |

初めから書くならCは小さい。一方、**現在はDも実guestにつながり、同じ限定検証を通過済み**なので、今からCへ切り替えれば過去のD検証費を取り戻せるわけではありません。Cは少ないstorage機構と引き換えに、利用者側の各子のコピー・割当・最大メモリ負担を受け入れる案です。今回の結果からは、その交換を積極的に選ぶ理由よりDを継続する理由が強いと判断します。全面VFS置換や新たな公開APIを今回要求する結論ではありません。

## 検証・同一性・未確認

| 項目 | 判定・証拠 |
| --- | --- |
| C連続領域、初回copy、縮小/成長・ゼロ、overflow/境界、固定入力2000操作のreference比較 | PASS [unit](cd-heap-snapshot-evidence/unit.txt) |
| Cファイルrename/unlink/open handle、append/O_TRUNC、Allocate位置/readonly、同時64handle | PASS 同上 |
| 両方式の親子・派生・wrong guest identity・不正layout・2段階corruption拒否 | PASS 同上 |
| C/D関連base fixtureのrace実行 | PASS [race](cd-heap-snapshot-evidence/unit-race.txt)。全guestの証明ではない |
| 実guest Exportとの全ファイル/ディレクトリ/内容一致 | 両方式PASS [audit](cd-heap-snapshot-evidence/audit.json) |
| transaction拒否で元DB継続、親Close、派生、並行2子SQL、freeze/target/owner失敗 | 両方式PASS [boundaries](cd-heap-snapshot-evidence/boundaries.json) |
| Snapshot直後ファイル0、Close後ファイル/dir0、capture registry残留0 | 全成功ケースPASS。file export経路にも失敗guardあり |
| 独立overlay再適用 | PASS、全postimage一致 [replay](cd-heap-snapshot-evidence/overlay-replay.json) |
| Python tooling compile・証拠checksum/リンク・diff検査 | PASS |
| 公開source検査 | 追加ファイル限定PASS。全体は既存tracked `docs/reviews/v050-startup-tail-source-fix-evidence/ubuntu/measurement.log`でFAIL。[範囲記録](cd-heap-snapshot-evidence/public-source-scope.json)。既存ファイルやguardは変更せず |
| native Ubuntu x86_64、Python、永続保存/import、大規模、多世代/多数同時Fork、Release Qualification | SKIP：今回のGo/macOSの限定比較外 |
| 既存unitのOS file-map counter | SKIP：MARIAMEM_PROCESS_COST未設定。0という出力をOS mapping検証と解釈しない |

基点source_commitは`72400d1196c94e7372bb28af328f9fc2132a4416`、runtime preimageはmain `a8137b8b444f86068d3128a291e3a848adfdfd56`。`scripts/git_identity.py inspect HEAD`でcommitを確認し、今回のoverlay/harnessは個別SHA256で固定しました。guestは`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`、比較バイナリSHA256は`7ef12d1e565266e9596c3e35c2915c620d0b190f598910c4574c9308b35b9d52`です。[build入力](cd-heap-snapshot-evidence/build-input.json)、[最終source一覧](cd-heap-snapshot-evidence/final-source-sha256.json)、[環境](cd-heap-snapshot-evidence/environment.json)。

実装・再現手順は[spike README](../../benchmarks/spikes/cd-heap-snapshot/README.md)。最終commitにはtemplate/harness/証拠だけを保存し、canonical runtime変更は復元しました。mainの既存変更3ファイルは保持しています。新規のguestビルド・変換生成・release guardの緩和はありません。heapデータの不変性は内部所有規則で守り、OSページ保護ではありません。一般的な不正メモリアクセスを検出する機構の追加もしていません。
