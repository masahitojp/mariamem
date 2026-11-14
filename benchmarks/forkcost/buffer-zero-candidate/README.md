# Buffer-pool descriptor-only zeroing product candidate — 2026-11-14

結論：管理情報だけを初期ゼロ化する最小候補は、有限の正しさ対照と標準checkを通過した。1並列Forkは両計測系列で短縮したが、8並列Forkの安定した短縮は未確立。8並列suiteには短縮が見られ、1並列suiteは系列間で逆転する。独立再生成と両OSの候補CIへ進めることを推奨し、main採用は結果と交換条件を確認してHumanが判断する。最大の懸念は、補足系列の1並列suiteが12.6%遅く、並列Forkもほぼ同じであること。単一Mac・3process/セルの観測で、一般的な高速化を保証しない。

## 最初の固定系列：容量走査監視あり

基準mainは`eeef899a296be8aa38cc9e3de0a550c428d4dca9`（prepared出力変更を含む）。基準バイナリは`3cfd9854d235d4d472734206d2ba03c6944d7d3a`の既存canonical generated guestを使用した。全Go/assembly、internal/、cmd/、release/、go.mod/go.sumの345pathが基準mainと同一であることを空diffで確認した。新guestのC sourceは同3cfd9854、ホスト開発段階は`29d7e04a3822a01ec26f74e52290e1b0c8b2058b`。後のcanonical化では、計測した開発版とGo/assemblyおよびhost互換定数の同一性を検査する。実行記録を後のSHAの新規実行へ付け替えない。

Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、macOS arm64。同じSQL/schema/triggerと従来matched modelcaseを使用。P1/P8、基準と候補を交互に3process/セル、各warmup1。計測24process＋warmup8＝32process。Forkは48children/process（144children/セル）。最初から接続＋検証SQL、WaitDisconnected、Closeも計測した。起動・準備・Snapshot・Fork・SQL・Closeを含むsuiteの壁時計中央値は重複operation時間の合計ではない。

| 並列 | Fork中央値 基準→候補 | 短縮率 | suite中央値 基準→候補 | 短縮率 |
|---|---:|---:|---:|---:|
| 1 | 16.74 → 15.85ms | 5.3% | 1361.44 → 1327.67ms | 2.5% |
| 8 | 37.88 → 33.81ms | 10.7% | 498.60 → 475.54ms | 4.6% |

Fork process中央値の組別短縮率は、P1が5.71/5.30/4.56%、P8が9.47/12.76/7.52%。suiteはP1が2.66/2.53/−2.98%、P8が0.46/8.44/−4.37%。外れや遅くなった組を削除・良い結果へ差し替えていない。

接続＋検証SQLはP1 3.923→3.940ms、P8 3.859→3.790ms。CloseはP1 2.143→2.155ms、P8 2.129→1.955ms。明確な後続処理への費用移動は観測していない。前のspike系列とは混ぜず、pgmemは再測定していない。Fresh全体、保持RSS、別page size、実guest OOMの改善は主張しない。

## 補足の固定系列：重い容量走査なし

後のintegration中に、再帰的な容量監視がCPU1coreの93%を使う場面を観測した。最初の性能系列での監視CPU率は未記録であり、93%だったと断定しない。通常時の結果との区別が必要なため、全ビルド/テスト終了後に同じバイナリSHAで同じ32process matrixを1回だけ補足した。事前/事後に20GiB budgetと空き8GiBを検査し、実行中は軽量disk-free検査のみ。再帰走査は0回。数値を合わせるための再試行、個体除外、系列混合は行わない。

| 並列 | Fork中央値 基準→候補 | 変化 | suite中央値 基準→候補 | 変化 |
|---|---:|---:|---:|---:|
| 1 | 17.53→16.01ms | 8.7%短縮 | 1341.51→1511.03ms | 12.6%遅い |
| 8 | 40.58→40.67ms | ほぼ同じ | 532.51→494.46ms | 7.1%短縮 |

組別のFork短縮率はP1が3.60/4.63/15.78%、P8が−50.54/16.04/8.31%。suiteはP1が−1.39/−35.56/0.37%、P8が26.41/7.15/10.32%。監視有無だけを変化の原因として確定しない。#101でも並列/尾部の混在と原因未確定を保存しているため、今回CPU/thermal/scheduler等の追加原因調査を開始せず、固定回数で終了した。

接続＋検証SQLの中央値はP1 4.290→4.144ms、P8 3.987→4.318ms。CloseはP1 2.616→2.357ms、P8 2.221→2.362ms。大きなばらつきがあり、費用移動の有無は断定できない。`light-monitor/`に全raw matrix、summary、CSVと実行recipeを保存する。`evidence/comparison.json`は両系列を分離して収録する。

## 最小変更と正しさ

`guest/source.patch`のbuf_pool_t::create()だけを変更。WASIX/Emscriptenで同じposix_memalign/2MiB alignmentと元pointerを使い、既存のextent_end計算で有効なdescriptorだけを初期ゼロ化する。共通allocatorのゼロ保証、既定16MiB、grow、失敗/再試行/free、非WASM経路は維持。実験用env/mode/poison/abortは製品に含めない。前のspikeを丸ごとmergeしていない。

新guestは`77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`。LLVM23.1.0/Binaryen133と既存SDK/sysrootを固定し、新しいLinux arm64/root環境で公式single-pass開発ビルドが成功した。これはUNQUALIFIEDの1buildであり、独立2build PASSではない。worker3関数の全body、CRC全validator/body/table/offset、初期data全体は現canonicalと同一。新guest SHAだけが変わる。算術/CRC定数/table byteの3破壊対照も拒否された。事前変換と公式native経路の再変換は61Go/assembly fileが一致した。

- 実prepared Cの共通allocator契約：dirty bufferから全ゼロ、alignment/size、ENOMEM、元pointer free、C/C++ link、4破壊対照を通過。pool専用の確保/clear文もdirty memory上で範囲・frame非変更・ENOMEM/freeと3破壊対照を通過。後者のlayoutはhostモデルであり、実buf_block_tの全実行に代わるものではない。
- 基準/候補ともbasicのroot＋4ForkでSQL・rollback・エラー後継続・分離を確認、開始5/Close5。
- 基準/候補とも通常/COMPRESSED各32MiB・8192rowsを全byte/value照合。実read miss増加を確認し、16→9→11→16MiB（566/692/1008pages）と2Fork分離を通過。候補のread missは520→35121、開始3/Close3。
- `.ibd`/`ibdata1`の実read EIOをそれぞれ1hit確認。双方とも再試行後に正しい値を返し、健全な別Forkを確認。SQLエラー発生を必須とはしていない。
- test-only host overlayでfast_shutdown2のdirty fixtureを取得。実crash-recovery分岐はcleanで0/0、dirtyで1/1。双方とも512row payload/valueと2Fork分離を確認。通常Snapshotのfast_shutdown1は製品で変更していない。
- 候補のCRC832 length/alignmentと80実validator valid/corrupt/LSN対照がPASS。per-instance env/controlled first-worker-trapの単体対照がPASS。実guest worker-trapと広い通常ゲートはcanonical CIの別のownerであり、この単体PASSへ含めない。
- 公式Go1.26.10のUNQUALIFIED native SQL/transaction/Snapshot/Fork/Close smokeがPASS。事前normal source ownerは87件＋23subtest PASS。canonical化後の標準checkはGo1.26.10でPASS（source owners87＋23subtests、Go全package/vet、Python1915＋119subtests、native C8、public-source）。新しいclean-source host（953ffbe0、Go1.26.10、vcs.modified=false）で12library familyのretained symbolを再照合し、ライセンス証跡も新guest/generated provenanceへ結び付けた。依存archive・notice・条件は変更していない。

fault/recovery観測overlayは計測バイナリと製品に入っていない。前のspikeの意図的bad-descriptorsは20秒でkillした履歴を維持するが、そのmode/abort経路は今回削除した。今回の有限対照PASSは任意OOM・全破損入力・全OSの証明ではない。

## 受入状況と次の判断

ローカルで標準checkを通過。standard integrationでは15 race packages、Go integration/default/generatedmemory/実worker＋dictionary、Go/Python source Live、Python53件（1skip）、Snapshot33項目まで通過した。固定Connector/Python26.7.0はOpenSSL4で接続前のimportに失敗する。Humanは2026-11-14にこれを既存のConnector/Python不具合として明示的に受容し、今回の実装の未完項目から除外した。元のコマンドの非ゼロ終了・実行していない後続stepはそのまま保持し、未実行をPASSへ書き換えない。追加調査、driver改変、重複issueは行わない。

canonical CI用buffer wrapperもGo1.26.10でbasic/large/COMPRESSED/resize/Fork/EIO/clean-vs-dirty redoを実行してPASS。保存した計測harnessのGo1.27 directiveだけをCIのscratch copyで1.26.0へ下げ、SQL/data/判定は維持した。

次は正確なcandidateをcanonical入力/recipeから独立2buildし、両product platformで通常check/integration・worker ownership・CRC・実SQL/Fork/cleanup・buffer対照を実行する。CIの対応consumer環境は通常の固定profileを使う。canonical build recordは独立再生成PENDING、UNQUALIFIED bootstrapは履歴のまま保持。CI提出後はURL/SHA/operationを返して引き渡し、監視しない。main採用とReleaseは別判断。


初回のsourceチェック/依存取得ではsystem Pythonのpytest欠如、Python3.9のtar安全抽出API不足、sandboxのDNS/Docker/local bind拒否があった。適切なtask venv/許可で同じsourceを再実行した。fault harness初回は旧spikeのmode必須ガードでStart前に停止したため、双方からその起動専用ガードだけを除去。EIO・値・sibling・Closeのoracleは維持した。各failureは保存した。保存用overlay断片の.goはnormal package discoveryに衝突したため、同じ内容を.go.txtで保存してテスト時だけ復元する。標準unit依存のPyMySQL1.2.3/SQLAlchemy2.0.54/xdist3.8も既存requirementsに揃えた。通常のライセンスguardは旧guest証跡を正しく拒否したため、新バイナリで再auditした。入れ子/外部worktreeのGoビルドは親の別SHAまたはVCS stampなしとなり、auditが拒否。PWD変更では解消せず、同じコミットの通常cloneで正しいSHAとclean stampを確認してから採用した。元のユーザー変更は削除していない。

## 保存と再現

`evidence/summary.json`、`runs/`が全観測、`tools/analyze.py`が完全matrix検査と再集計。`harness/`は使った入力（go.modのreplaceだけportable化）。`tools/`は実行recipe。`ci_validate.py`はcanonical sourceにtest-only overlayを適用し、両OSで同じbuffer対照を実行する。`verify_saved.py`はnetwork/buildなしで両系列のhash・summary・CSVを再現する。

公開記録のpath/行末空白は正規化し、`publication.json`に元/公開hashを併記。これらの記録を現在のinstallation入力へ流用せず、固定sourceとrecipeから新しいreceiptを生成する。guest/build/source/toolchainのidentityはbuild-evidenceとsource-identitiesに保持。SDK、downloads、generated source、native binaries、cacheは再作成できるため作業完了時に削除する。mainと元のユーザー変更は触らない。#56/#116/#88やMDEV-42129の再調査・issue変更は行っていない。
