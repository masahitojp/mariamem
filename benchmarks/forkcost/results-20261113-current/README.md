# 現行 Fork 再計測（2026-11-13）

結論：今回も最大の費用は MariaDB の server_init。逐次では内訳平均の86.1%、8並列では73.3%を占める。次に調べるなら guest のゼロ初期化の用途・呼び出し元を分類する小さな調査を推奨する。メモリ拡張のまとめ処理やrootReadのclear削減は既に不採用のため、そのまま再実装しない。今回、最適化の採用判断はしていない。

## 入力・測定境界

- source_commit: `eb175ae23292c1c40cfbeb4b9b73132873c4cc6f`（測定開始時のmain）。前回 `0f5b26f370875d26bd337031f48856d8f57c10db` と tree `2dd9b08343685a0ae29b6572171f49dd42d62f06` が完全一致。証拠は tree-identity.json / source-identity.json。
- guest SHA256: `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`。Goのバージョン・依存関係はbuildinfo.txt。
- matched modelcase: categories20/products500/users1000、orders/items/auditは0。Migrate/SeedMaster/Snapshotを測定前に完了。MODELCASE_MATCHED=1、MARIA_AUDIT_OF=1。GOMAXPROCS=8、GOGC=100。
- 各waveは8childrenをForkし、全Fork完了後にSQLで初期データ・他childの書き込み非混入を検査してCloseする。P1でも8childrenを保持する。実アプリのFork→SQL→Close交互実行とは異なる。
- canonical（オーバーレイなし）と observed（段階イベントのみ追加）を3組、順序を交替して測定。各cellは3process×48children=144。warmup4、positive pilot2、negative pilot1、profile2を加え、計21process。全成功分でoracle/Closeを確認。負の対照はusers期待値1001で意図通り失敗し、8children全てClose。
- CPUはcanonicalで各P64children、8wave。StartCPUProfile→Fork群→StopCPUProfileで切り、検証SQL/WaitDisconnected/Closeは窓外。CPUサンプルはprocess全体なので、窓内の既存child/Goランタイムのbackground処理は含む。短いwave・100Hz標本のため小さい割合を厳密視しない。

## Fork時間（ms）

| 並列 | canonical中央値 | canonical平均 | p95 | observed中央値 |
|---|---:|---:|---:|---:|
| 1 | 16.18 | 16.33 | 17.08 | 16.46 |
| 8 | 37.88 | 39.26 | 55.71 | 38.56 |

observer平均差はP1 +1.60%、P8 +3.13%。P8のprocess別中央値はcanonical 36.37/41.66/39.63ms、observed 35.15/40.18/37.96msと揺れが大きい。以下はobservedの加算可能な平均内訳であり、canonical中央値にそのまま足す・引くことはできない。

| 段階（平均ms） | P1 | P8 |
|---|---:|---:|
| host_setup | 0.279 | 0.414 |
| filesystem | 0.101 | 0.156 |
| image_module | 0.372 | 2.677 |
| server_init | 14.286 | 29.663 |
| bootstrap | 0.111 | 0.446 |
| routine_schema | 0.940 | 2.022 |
| guest_other | 0.034 | 0.102 |
| execution_residual | 0.405 | 4.766 |
| post_ready | 0.067 | 0.239 |

内訳合計はP1 16.596ms、P8 40.486ms。execution_residualはguest実行窓とready観測の差分で、スケジューリング・起床・応答伝搬など未分離の費用。通信だけの時間とは断定しない。image_moduleもimage.Acquireのロック・マッピング・Module作成を含むため、全て除去できる費用ではない。

前回の同一treeの内訳平均はP1 15.904ms / P8 32.808ms、server_init 13.756 / 24.105ms。今回P8が遅いが、ソース差はなく実行パターンも違うため回帰とは判定しない。前回値と今回値を混ぜて改善率やpgmemとの差を算出しない。今回はpgmemを再測定していない。

## Fork窓だけのCPU

P8は2.22 CPU秒（64children）。flatでmemclr 0.35秒=15.77%、syscall.rawsyscalln 0.29秒=13.06%、memmove 0.15秒=6.76%。Wasm生成コードのMemoryInBoundsは10.36%、MemoryEAは5.86%。これらのCPU割合と、上の壁時計のstage割合は別の尺度で足し合わせない。

- memclrの直接caller内訳：guest MemoryFill 0.27秒（全CPUの12.16%）、blockStorage.readAt 0.07秒（3.15%）、blockStorage.writeAt 0.01秒（0.45%）。inlineで中間関数が省略されるため、readAtの0.07秒を特定のclear一行だけに断定しない。
- MemoryMapping.Grow配下のsyscallは0.24秒（10.81%）。メモリ拡張は今も観測できるが、まとめて拡張するだけで速くなる証拠ではない。
- P1ではmemclr0.26秒/2.47秒=10.53%。usleep/pthread_cond_wait/signalも多い。Darwin上のGoランタイム処理を含むため、MariaDBのSQL処理時間やそのまま削れる待ち時間とは解釈しない。
- この測定にSQL/Closeの明示呼び出しはない。前回の全cycle CPU（Closeのmunmap等を含む）よりForkの調査境界を絞れた。

## 次の判断

推奨：#122の残課題として、MemoryFillの上位callerを元のC初期化処理へ確実に対応付け、何の領域を何byte初期化しているかを分類する小さなspike。初期化そのものの省略可否が分かるまではguest変更に進まない。最大の反論は、ゼロ書き込みが必要な初期化であれば、目立つCPUを見つけても省けないこと。この調査は「削れる」と結論するためではなく、その不確実性を潰すために行う。追加費用はcaller対応表・用途/byte分類の小調査1件、必要なら限定instrumentationビルド1回。C再ビルド・最適化・速度評価は別判断とする。

二番手はprepared.Block.ReadAtのvalid prefixコピーとhole/short suffixのゼロ保証の分類。sourceではclear後にvalid prefixをcopyするが、契約・入力範囲・aliasを確認する前にclear全削除しない。今回のreadAtサンプルは全CPUの約3%で、単独では大幅改善の根拠は弱い。

既存調査との境界：#56のmemory.grow/mprotect batching、#116のrootRead clear削減は既に性能条件未達で不採用。今回のCPUで同種の費用が見えたことだけでは再開しない。#123のstatic image、#63のbufferpool整合、#117/#145の終了処理改善は既に採用済み。#64の旧fresh-zero constructorも現行Fork毎の主因とみなさない。#119/#162のClose課題、MDEV-42129は今回の対象外。

## 再現・保存

`harness/`をprivate moduleに置き、replace先を上記source_commitのcheckoutに合わせる。build.pyのworkspace配置に従ってcanonical/observedを作成し、measure.pyを容量監視下で実行する。overlay.pyはMariaDB側のみの観測差分。analyze.pyがJSONから集計し、各childの段階加算一致をassertする。profile.pyで8waveを合算する。

runsの各pprof.b64はgzip protobuf profileをbase64化したもの。文字列表のローカルパスだけを<workspace>/<home>に置換し、標本・時刻・callstackは保持した。JSONにも同様のworkspaceパス置換を行った。元の生profileはローカルevidenceに保持し、公開コピーのチェックサムはSHA256SUMS.json。私有パスを含む元profileとのバイト同一性は主張しない。
