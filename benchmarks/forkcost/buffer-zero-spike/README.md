# Buffer-pool descriptor-only zeroing spike — 2026-11-14

結論・推奨：限定実験は完了。初期ゼロを管理情報だけに絞る方向には効果があり、最小の製品候補へ整理して再評価する価値がある。ただし、現プロトタイプの統合は見送る。逐次Forkは両計測系列で約6–7%短縮、8並列モデルケース全体は主計測の3組すべてで約6%短縮した。一方、8並列Fork単独は主計測ではほぼ同じで、補足系列では約10%短縮しており、安定した改善幅は未確定。逐次モデルケース全体も改善していない。最大の反論は、目的だった並列Forkの効果が系列間で揺れ、Linux実行と通常の採用ゲートも未完であること。今回の結果を「Fork全体が98.6%速くなる」と解釈してはいけない。

## 一次比較（観測なし）

同じ実験guest・同じバイナリのbaseline（従来全域ゼロ）とmetadata（管理情報だけゼロ）を主対照とする。canonicalは元のguestの外部アンカー。3process/セル、Fork probeは48children/process（144children/セル）。suiteは以前のmatched modelcaseを変更せず全テスト実行した壁時計中央値。suiteには起動・準備・Snapshot・Fork・SQL・Closeが含まれる。

| 並列 | Fork中央値 baseline→metadata | 変化 | suite中央値 baseline→metadata | 変化 |
|---|---:|---:|---:|---:|
| 1 | 18.01 → 16.75ms | 7.0%短縮 | 1402.52 → 1435.97ms | -2.4%短縮 |
| 8 | 42.32 → 42.26ms | 0.2%短縮 | 632.03 → 594.44ms | 5.9%短縮 |

負の「短縮率」は遅くなったことを表す。P1 suiteは約2.4%遅い中央値で、3組の内訳には大きな外れもある。外れ値を除去・再測定して置き換えていない。P8 suiteの組別短縮率は5.95/5.68/6.13%。標本は3processだけであり、統計的に一般化できる改善率ではない。

| canonical外部アンカー | P1 | P8 |
|---|---:|---:|
| Fork中央値 | 18.14ms | 51.88ms |
| suite中央値 | 1470.35ms | 621.66ms |

canonicalと実験guestのbaselineにも差がある。追加したモード分岐、生成コード・コード配置の違いと実行ばらつきが含まれるため、canonical→metadataの差の全量をゼロ削減の効果とは呼ばない。pgmemは今回再測定していない。

## Closeへの費用移動の補足

主probeにはClose単独のtimerがなかったため、同じ48children・3process/セル、各セルwarmup付きの固定系列を追加した。主系列48processを保存したまま、補足24process（計測18、warmup6）を実施。追加timerだけのGo harnessで、guest観測やpoisonはない。この系列を主系列と混ぜたり、良い方だけ採用していない。

| 並列 | Fork中央値 baseline→metadata | SQL＋接続処理※ | Close中央値 |
|---|---:|---:|---:|
| 1 | 17.28 → 16.24ms | 3.95 → 3.92ms | 2.18 → 2.10ms |
| 8 | 39.61 → 35.63ms | 4.00 → 3.99ms | 2.11 → 1.99ms |

※6テーブルの初期件数確認＋marker INSERTとSQLクライアントcloseを含む。modelcaseのサンプル投入時間とは別。disconnect待ちも別記録（中央値約0.04ms）。少なくとも、この限定対照ではSQL/Closeへの明確な費用移動は見えない。P8のFork効果は一次0.2%、補足10.0%と揺れるため、並列Forkが安定して10%速くなるとは結論しない。

## 実装と固定入力

- 製品基準source_commit: eb175ae23292c1c40cfbeb4b9b73132873c4cc6f、canonical guest: 5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20。既存canonical CI証拠と、チェックサムに結び付いた既存生成Goを再利用。canonical probeのruntime_instance.goは基準commitのbytesにoverlayで戻した。
- 実験Cの初回固定: 5c21cf758ba5879931f16b668f4bd460419eaff5。Cコンパイル時source_commit: ff6027ce（完全SHAはevidence/resumed-source-identity.json）。契約チェック修正だけを加えた。host adapter source_commit: 8d458e86125573b54572832dfdd733bb0170c413。
- 実験guest: 5da1c72aceb2c5db760e1dfb17bda0352ffad02b5f9b51a200da5d6ec0b2fd3c、development-unqualified-v1 / UNQUALIFIED。Linux arm64 builder、固定LLVM23.1.0 / Binaryen133 / WASIX sysroot。Cコンパイルは1回。基準の再コンパイルによるqualificationではない。
- guest/experimental.patchでbuf_pool_t::create()だけを変更。共通のzero-filled allocator、field_ref_zero、容量default、memory.growは維持。baseline/metadata/poison/bad-descriptorsを一つの実験guestに置き、明示的な実験envだけを渡す4行のhost adapterを追加した。baselineが既定。metadataでは同じ2MiB整列のposix_memalignを使い、各extentの有効descriptorをsizeofベースでゼロにする。232/1008を製品コードへ固定していない。
- 全計測バイナリGo1.27.4、CGO=0、GOMAXPROCS=8、GOGC=100、macOS arm64。開発用host生成/スモークは既定のGo1.26.10。measurement-binaries.jsonに実際のbuildinfoとhashがある。
- MODELCASE_MATCHED=1 / MARIA_AUDIT_OF=1。DSNのinterpolateParams=trueを既存harness自身が検査。probeはmaster categories20/products500/users1000、orders/items/audit0からSnapshotし、全Fork後にSQL検査・Close。suiteとprobeの実行モデルは別で、両者の時間を加算しない。
- 主系列はP1/P8×3variant×3反復×2harness=36計測process＋12warmup。canonical/baseline/metadataの順序を回転。補足を合わせ計72performance process。追加パラメータ探索はしなかった。child標本は同一process内で相関するため、144独立反復とは扱わない。

## 正しさの結果

| 検査 | 結果・範囲 |
|---|---|
| 元のC allocator契約 | dirty bufferのゼロ保証、整列、size不変、ENOMEM、元pointer free、C/C++ link、4意味変更の拒否を維持してPASS |
| metadataの基本ケース | fresh、4回Fork隔離、rollback、SQL error後の再利用・全Close PASS |
| poisonの実メモリ | poolを0xA5で埋め、全有効descriptorのゼロと全1008frameの全byteが0xA5であることを使用前に検査。各DBでpool=16777216 / descriptor=233856 / frames=1008 / page=16384 / aligned=1を確認 |
| compiled poison | MemoryFill(165)と実byte load/比較が最適化後Goにも残っていることを確認。compiled-poison-sites.json |
| 大規模・圧縮 | 通常/COMPRESSED各32MiBのpayload、8192行ずつ。全byte/値の一致、更新、LRU read misses、9→11→16MiB resize、Snapshot後の2回Forkの一致・隔離とClose PASS（canonicalとpoisonで同じoracle） |
| 既存matched modelcase | poisonで全テストP8 PASS。計測時はpoisonを使わない |
| 実read-I/O故障 | .ibdとibdata1に各1回EIOを注入。canonical/poisonとも実readに到達し、再試行後の正しい結果とhealthy siblingを確認。fault wrapperは正しさ専用binaryのみ |
| 実REDO復旧 | テスト専用overlayでfast_shutdown=2のcold fixtureを作成。通常Snapshotのmode1は製品で変更しない。ログが出ないため復旧分岐の到達点をhost counterで観測。canonical/poisonともclean対照は0/0、dirty対照は1/1回、復旧後512行の内容とFork間の隔離が一致 |
| worker/CRC binding | 全function mapのSHAはcanonicalと同一。workerはBSSの128byte移動、CRCは表/グローバル/同一logging文字列のアドレス移動のみ。全制御フロー・呼び出し・他定数を照合し、runtimeでは新guest/完全body/tableの厳密hashへ束縛。算術変更/非アドレス定数変更/表破損の3対照を拒否 |
| CRC実行対照 | 832長さ/alignmentケース＋独立bitwise/既知vector、80個の実validator valid/corrupt/LSNケース PASS。fixtureのaddressだけを新layoutへ移した |
| owner controls | per-instance environment / first-worker-trapの既存テスト PASS |

### 合格扱いにしない項目

- bad-descriptorsは実際のBP_ZERO_REJECT nonzero_descriptorを検出したが、自律終了しなかったため20秒で所有processを停止した。negative-descriptor.jsonのtimed_out=trueをそのまま残す。これは意図的に壊したguestの検知対照であり、正常なcleanup PASSではない。この終了経路は未解明で、今回の有効metadata/poisonケースの全Close成功とは区別する。
- 通常のverify.py checkは、採用済みprofileを調べる2テストがexperimental.patchを拒否して停止した（experimental patch remains）。ゲートを削除・緩和して総合PASSにはしていない。したがって通常の全check、製品採用、Release acceptanceは未達。実行した実験用検証と同一視しない。
- 実行platformはmacOS arm64のみ。Linux x86_64、他page size、任意設定/全OOM経路の受け入れを主張しない。復旧はREDO付きのテストfixtureであり、あらゆる破損・復旧の保証ではない。

## 作業中に分かったことと保存した失敗

最初のproducerは、既存Issue63チェックの「直接共通helperを呼ぶ」という固定コード形状で止まった。共通allocatorのC oraclesはそのまま維持し、実験に限り準備済みpool sourceの全hashを固定して分岐を許した。新しいゲートを通してから、同じfresh SDKと未コンパイルの準備sourceを再照合してCコンパイルを再開した。compile/postoptは成功したが、既存の空output directoryで収集が一度止まったため、成功phaseのoutput hashを照合して収集だけ再開した。再コンパイルで良い結果を選んでいない。

基準の大規模SELECTは最初、payload32MiB＋応答metadataで既存32MiB frame上限を超えた。データ量は減らさず256行ずつ取得するoracleへ修正。初回failureはcanonical-large-unbounded-response.*。最初のfault wrapperは全fileを包みentropy/authの型契約を壊したため、対象データfileだけに限定し、canonicalで成功を確認してからpoisonを評価した。復旧ログが出ないことも基準で確認し、clean/dirtyを区別する実行分岐observerへ変更した。これらを候補の性能失敗/成功と混同しない。

## 次段階の条件

次へ進むなら、mode分岐・poison・意図的abort・実験envを落とした最小のbuffer-pool専用変更を作り直す。現実験履歴を丸ごとmainへmergeしない。共通allocatorのゼロ保証、page/extent計算、再試行・失敗・freeの責任を維持する。新しい正式guest identityとworker/CRC bindingをレビューし、通常ゲート、両product platform、同じ正しさ対照と最終candidateの速度比較を通してから採用判断する。Releaseは別判断。

今回の目的だった「全域初期ゼロを省く仮説の検証」は、有効入力の正しさと限定性能比較まで完了。安定した並列Fork短縮、壊した対照の自律終了、製品品質化/統合/リリースは未達である。#56/#116/#88、MDEV-42129、pgmem再比較、別のengine最適化は今回実施していない。

## 再現と証拠

summary.jsonは主系列とClose補足を分離し、process別値も保持する。analyze.pyはraw JSONの完全matrix/成功/子件数を検査して再生成する。runs/とlifecycle-runs/が全観測で、失敗記録はvalidation/に分けて保存。tools/は今回使ったrecipe/解析コード、harness/は実際のGo入力。新規環境では現branchのclean source、同じ入力pinsから通常のsingle-pass development producerでguestを作り、同じSHAを確認して再生成する。今回は上記の段階再開を使った事実を保持しており、fresh replayをもう一度実行したとは主張しない。

guest.jsonとdevelopment.jsonは圧縮して保存した。公開時に<workspace>/<repo>/<home>へpathを正規化した資料（ログの行末空白と旧harnessの空行の空白も除去）にはpublication.jsonで元hashと公開hashを併記する。新しい再現では新しいsource origin/pathsに結び付いたrecordを生成し、正規化済みrecordをそのままinstallation inputに流用しない。C/Go binary、SDK、module/compiler cache、生成sourceは再作成可能なため削除対象。canonical source.patch、release pins、mainと既存のユーザー変更は変更していない。
