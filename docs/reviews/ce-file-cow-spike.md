# C＋E: 共有backingとファイル単位CoWの組み合わせ

## Human Review

今回判断したいのは、**C＋Eをさらに深掘りするか**です。推薦は、今回の
「Eの共有基準＋最初の変更でファイル全体を子のGo heapへコピーする」案を
ここで保留し、Eを比較対象として残すことです。準備・Snapshot・2つの子の
CRUD・終了を合わせると、Eに対して中央値で小規模12.1%、中規模5.4%遅く、
別枠の測定では子1個の最大RSSも約190 MiB増えました。利用者のテストを速く、
軽くする利益は今回確認できませんでした。

最も強い反論は、EとC＋Eとも少数試行で全体時間にばらつきがあり、Cの単純な
所有方式には別の設計上の価値があることです。ただし、小さなCRUDでも各子が
138〜159 MiBをコピーすること、CRUDと終了の時間、割当量と最大RSSの増加は
整合しています。今回のC＋EはEのOS backingを残すため、OS依存の解消も
得ていません。この用途での追加深掘りを優先する根拠は弱いと判断します。
C単独・別の保存/所有境界・他OSまで棄却する結論ではありません。

承認済みの限定spikeは完了です。製品採用は未決定で、main、公開API、リリース
には反映していません。Dのページ／ブロック単位方式も未評価です。次の探索を
選ぶ場合の候補として残し、この報告でHuman Reviewに戻ります。

## 問いと今回変えた箇所

問いは「EのSnapshot短縮を保ちつつ、子の変更方式をCにすると、典型的な
小変更テスト全体がさらに速く／軽くなるか」です。

| 境界 | 比較対象E | 今回のC＋E |
| --- | --- | --- |
| 準備DB | 共有可能なファイルbackingへ直接書く | 同じ |
| Snapshot | 停止後に固定・所有移転。payloadコピーなし、完全検査は維持 | 同じ |
| Fork | 読み書き可能なprivate mapping。OSがページ単位で変更を分離 | 読み取り専用mappingで開始 |
| 最初の書き込み | OSのページ単位CoW | 論理ファイル全体を子専用Go heapへコピーし、元mappingを解放 |
| その後のI/O | private mappingまたは既存の拡張後heap | 実際に子専用heapを読み書き |
| 子からのSnapshot | 従来のexport/copy経路 | 同じ従来経路。無コピー化はしていない |

前回の[C観測probe](https://github.com/masahitojp/mariamem/blob/ed78c0e901ae864573408d9c8797a5e6bfc1a512/docs/reviews/file-cow-crud-probe.md)
はコピーを追加しつつ実I/Oを元mappingに残していました。今回は読み書き先を
切り替え、不要になったmappingを早期解放しています。そのため、以前の
追加コピー時間をそのまま今回の全体差とは扱いません。

E部分は[接続済みhandoff試作](https://github.com/masahitojp/mariamem/blob/3ce25c29ebceb2bdfb6b430391f400ad3d8d90e0/docs/reviews/e-snapshot-handoff.md)
を再利用しました。今回の数字はE対C＋Eであり、main対C＋Eの再測定では
ありません。以前得られたE対mainの改善率と掛け合わせません。

## 結果: テスト全体と内訳

macOS 27.0.1 arm64、Go 1.26.8、Python 3.9.6、PyMySQL 1.2.3。
各モード・規模5回、実行順を交互に変更。準備1回から子2個を順番に使用します。
小規模は各100行、payload 256 bytes、中規模は各10,000行、payload 1,024 bytes。
users/orders、index、外部キーを用意し、insert/update/delete、commit/rollback、
兄弟隔離を確認しています。各実行で同じSQLを準備し直すため、DBファイルの
バイト列そのものがモード間で同一という測定ではありません。

以下は中央値、単位msです。全体はFresh開始、migration/seed、Snapshot、
子2個の接続・CRUD・終了、基準Closeまで。計測専用の終了後全量hash確認は除外。
各区間の中央値の和は全体中央値と一致しません。

| 指標 | 小規模 E | 小規模 C＋E | 中規模 E | 中規模 C＋E |
| --- | ---: | ---: | ---: | ---: |
| **テスト全体** | **444.0** | **497.9** | **1,279.3** | **1,348.1** |
| Snapshot作成 | 242.2 | 237.9 | 267.0 | 273.1 |
| Fork起動・子1個 | 53.1 | 52.0 | 51.7 | 57.1 |
| CRUD・子1個 | 2.9 | 20.3 | 19.9 | 39.2 |
| Close・子1個 | 4.6 | 14.4 | 4.7 | 19.9 |

全体中央値の差は+53.9 ms / +68.9 ms。対応する実行同士の差の中央値は
+46.4 ms / +73.3 msです。小規模4/5、中規模5/5でC＋Eが遅くなりました。
Snapshotは同じ実装なので、数msの差をCによる改善・悪化とは解釈しません。
Fork開始の高速化も確認できていません。

ばらつきを隠さないため、小規模Eの遅い1回も除外していません。この回の全体は
737.8 ms、Snapshot 427.8 ms、最初の子起動154.3 msでした。対するC＋Eは
515.7 msで、この1組ではC＋Eが222.0 ms速くなっています。原因は今回特定
していません。メモリ計測付きの別campaignでも、中規模1/3組はC＋Eが8.6 ms
速く、残り2組は遅くなりました。「必ず遅くなる」「全体差が全てコピーに由来」
とは判定しません。

初回動作確認はwarmupとして別保存し、集計に含めていません。そのE実行には
Fresh開始1,085.4 msがありました。原因調査やstartup tail評価は今回の対象外です。

[集計・全範囲・対応差](ce-file-cow-evidence/summary.json)、
[plain実行入力](ce-file-cow-evidence/plain/inputs.json)、
[小規模Eの遅い回](ce-file-cow-evidence/plain/n100-r3-e/result.json)、
[同じ組のC＋E](ce-file-cow-evidence/plain/n100-r3-ce/result.json)。

## コピーの実行とメモリ

plain campaignのC＋E・20子すべてで13ファイル中9ファイルをコピーしました。
小規模138.234 MiB、中規模158.578 MiB/子です。96 MiBのib_logfile0は全例CRUD中。
残りはほぼClose中で、undo、ibdata、Aria制御/ログ、users/ordersの内容です。
小規模1子だけundo/ibdataのコピーがCRUD中へ移りました。SQLの小さな変更量と
ファイル全体コピー量は一致しません。

確保・コピー・元mapping解放を囲んだ時間の中央値は22.6 / 26.7 ms/子。
これは追加I/O観測やGCの全影響を分離した因果推定ではなく、当該処理の経過時間
です。初回コピー中は元と新しい内容が一時的に共存します。切替後にmappingを
解放しても、その一時的なピークや既に行ったコピーはなくなりません。

最大RSS・Go割当量は通常時間計測と分け、各規模・モード3回、計6子で確認しました。
単位MiB、子ごとの中央値です。

| 指標・子1個 | 小規模 E | 小規模 C＋E | 中規模 E | 中規模 C＋E |
| --- | ---: | ---: | ---: | ---: |
| プロセス最大RSS | 120.9 | 310.7 | 122.7 | 312.4 |
| Go累積割当量 | 12.9 | 151.1 | 12.9 | 171.4 |
| 終了処理内のHeapAlloc | 12.7 | 150.9 | 12.8 | 171.2 |
| GC回数 | 1 | 2 | 1 | 2 |

準備hostの最大RSSは両モードとも小規模約252、中規模約280 MiBで、目立つ差は
子側です。Go累積割当量の増分はファイルコピー量とほぼ一致します。
Eの「コピー記録0」はアプリ側の全ファイルcopy-upがないという意味で、OS内の
ページCoWが0という意味ではありません。

RSSは各Go hostのRUSAGE_SELF最大値で、Pythonや同時稼働プロセスを合計した
値ではありません。各hostの最大値を足して全体ピークとは扱いません。macOSの
[timeとの小規模照合](ce-file-cow-evidence/rss-calibration.txt)でbytes単位を確認。
終了時の採取はguest worker join、guest memory/mapping/descriptorの解放後ですが、
MemFSの参照が残り、強制GCもしていません。HeapAllocを「Close後の残留量」や
リークと呼びません。最大RSSも物理footprint・OS page cache・仮想予約量とは
異なり、その厳密な分解は未実施です。

[小規模C＋Eの全コピー記録](ce-file-cow-evidence/plain/n100-r0-ce/result.json)、
[中規模C＋E](ce-file-cow-evidence/plain/n10000-r0-ce/result.json)、
[resource実行入力](ce-file-cow-evidence/resources/inputs.json)。

## 正しさと制限

| 確認 | 判定 | 証拠・意味 |
| --- | --- | --- |
| Cの内容保持、兄弟隔離、早期unmap、1回だけcopy-up | PASS | [unit](ce-file-cow-evidence/unit.txt) |
| shrink/regrowゼロ埋め、O_TRUNC、空ファイル、Allocate、rename/unlink/open handle | PASS | 同unit。独立nodeの所有と内容を検査 |
| 複数handleの同一ファイル同時書き込み | PASS | [限定race test](ce-file-cow-evidence/unit-race.txt)。共有メモリ全体の保証ではない |
| 既存owned backingテスト・Eモード | PASS | [owned-e](ce-file-cow-evidence/owned-e.txt)。OS mapping量カウンタは未設定 |
| 同テスト・C＋Eモード | **FAIL 1件** | [owned-ce](ce-file-cow-evidence/owned-ce.txt)。truncate/regrow後も同じmappingアドレスという既存方式のassertionと不一致。他2件PASS |
| Eの既存freeze/handoff・破損/欠落oracle | PASS | unit。既存テストは変更していない |
| 実DB CRUD、親/兄弟隔離、使用後の基準全量hash一致 | PASS | plain20 workflow/40子、resource12 workflow/24子 |
| 親Close後の2生存子、派生Snapshot、transaction拒否 | PASS | [E](ce-file-cow-evidence/boundaries-e/result.json) / [C＋E](ce-file-cow-evidence/boundaries-ce/result.json) |
| 4種handoff失敗時の拒否・元DB終了・保存先削除、Python破損拒否 | PASS | 同boundary。保存物の完全性・所有の検査は省略していない |
| 実験scratchにruntime一時ディレクトリを残さない | PASS | boundary + campaign終了後に空を確認 |
| 公開ソース検査 | 追加ファイルPASS / 全体FAIL | [結果](ce-file-cow-evidence/public-source-scope.json)。既存`v050-startup-tail-source-fix-evidence/ubuntu/measurement.log`がallowlist違反。今回の追加ではなく、削除・guard緩和はしていない |
| macOS 15、Ubuntu x86_64、他Go/Python | SKIP | 今回のローカルmacOS 27.0.1でのみ実行 |
| 大規模、4並列、多数子/深い派生世代、異常終了全面評価 | 未実施 | 小規模なC＋E比較の範囲外 |

既存のmappingアドレスassertionは緩めていません。C＋Eはregrowで新しいheapへ
切り替える設計なので、そのassertionを満たしません。C専用テストでは保持prefix、
新領域ゼロ、offset、兄弟/基準の不変を確認しています。失敗をPASSへ読み替えず、
製品化時に内部実装契約と検証を整理すべき差分として残します。

shrinkは論理長だけ変更し、再拡張時は保持prefixをコピーして新領域をゼロにします。
truncate 0は内容をコピーせず共有viewを破棄します。Allocateが既存範囲内なら
copy-upしません。first-writeの確保は要求extentも含め一度で行います。以後の成長は
既存MemFSの成長方針です。失敗時のpanicは実験を停止させる実装で、製品向けの
全エラー回復を完成させてはいません。

実Python APIが使うMapPreparedHandlesを変更しました。legacy MapPreparedFilesは
元方式のままです。Eの同一filesystem内handoffという制限、子の派生Snapshotが
従来コピー経路であることも引き継ぎます。EとC＋Eは同じbinary内のenv切替で、
共通hook分の差を揃えています。C側の初回copy記録はplainにも含まれ、観測コストを
厳密に除去した測定ではありません。各mutation全件を記録する方式ではありません。

## 入力・再現・保存

- 実験branch: `experiment/ce-file-cow`。
- baseline source_commit: `a8137b8b444f86068d3128a291e3a848adfdfd56`。
  [git_identity出力](ce-file-cow-evidence/source-identity.json)をbuild前に確認。
- E採用元: `3ce25c29ebceb2bdfb6b430391f400ad3d8d90e0`。
- guest: MariaDB 12.3.3、既存Generated Go/guest入力を変更せず使用。
  guest SHA256: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- 比較binary SHA256: `fe73e3089079d58e3c70beeae6f7b8070b17492a49e33397c4d930f425355207`。
  [build identity](ce-file-cow-evidence/build-identity.json)にGo/VCSとoverlay各ファイルhash。
- [試作所有元](../../benchmarks/spikes/ce-file-cow/instrument.py)と同directoryの`.go.txt`。
  exact baselineを検査して一時overlayを適用。canonical生成物やprovenanceには採用しない。
- baselineへ戻して再適用し、全overlay hash一致を確認。その後runtimeファイルは再び
  baselineへ復元。[再適用記録](ce-file-cow-evidence/overlay-reproduction.json)。
  binaryの独立2回buildや正式再生成・Qualificationを行ったという意味ではない。

再現はbaselineから作った使い捨てworktreeに本branchの`benchmarks/spikes/ce-file-cow`
を配置し、`instrument.py`、Go unit/host build、Python harnessを順に実行します。
`ROOT`はworktree、workspace直下に`temp/`と`evidence/`を用意。GOFMT環境変数とGO_BINはGo 1.26.8のgofmt/go絶対pathを指定します。
計測時のtoolchainはbuild identityに保存しています。

```sh
# GOFMT環境変数にGo 1.26.8のgofmt絶対pathを指定
python3 benchmarks/spikes/ce-file-cow/instrument.py
# GOCACHEはworkspace/temp/gocacheの絶対path、GOTOOLCHAIN=local、Go 1.26.8を使用
# GO_BINは同toolchainのgo絶対path
"$GO_BIN" test ./internal/generatedgo/code/base -run 'Test(CE|E|MemFS|Prepared|MapPrepared)' -count=1 -v
"$GO_BIN" test -race ./internal/generatedgo/code/base -run '^TestCE' -count=1 -v
"$GO_BIN" test ./internal/generatedgo/code/base -run '^TestOwned' -count=1 -v
# 下は既存mapping維持assertionが1件失敗することを保存。変更・無視してPASSにしない
MARIAMEM_CE=1 "$GO_BIN" test ./internal/generatedgo/code/base -run '^TestOwned' -count=1 -v
"$GO_BIN" build -p 2 -o ../temp/ce-host ./cmd/mariamem-host
python3 -m venv ../temp/venv
../temp/venv/bin/python -m pip install --no-cache-dir pymysql==1.2.3
mkdir -p ../temp/scratch
# pilotは別出力。TMPDIRをworkspace/temp/scratchの絶対pathに指定
../temp/venv/bin/python benchmarks/spikes/ce-file-cow/run.py --host ../temp/ce-host --output ../evidence/pilot --pilot
python3 benchmarks/spikes/ce-file-cow/campaign.py --workspace /absolute/path/to/workspace
python3 benchmarks/spikes/ce-file-cow/summarize.py ../evidence
python3 benchmarks/spikes/ce-file-cow/restore.py
```

実行時はbuildにも既存`experiment_disk.py`を使用し、空き16 GiB以上、所有12 GiB以下、
build上限1,200秒、campaign各段300秒。campaignは[保存script](../../benchmarks/spikes/ce-file-cow/campaign.py)
で同条件を監視。今回の所有量ピークは約1.11 GiBで正常終了。
[実行log](ce-file-cow-evidence/campaign.txt)。

最終証拠は本directoryに圧縮せず小さなJSON/textで保存。log拡張子はtxtへ変更し、
build/python-tools出力のユーザーhome絶対pathだけを`<USER_HOME>`へ正規化しました。
実測値・判定は変更していません。各runのresult.jsonは
handoff/publish記録、manifest、全コピー記録を内包し、重複する個別出力は省いています。
[checksums](ce-file-cow-evidence/checksums.json)に保存対象のhashを記録。
主checkoutの既存`docs/project-status.md`変更と未追跡設計資料2件は触れていません。
このspikeからの製品原則変更・main統合・リリース準備は行っていません。
