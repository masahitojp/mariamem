# Buffer-pool descriptor-only zeroing product candidate — 2026-11-14

結論：実験用mode/env/poison/abortを除いた最小候補でも、Forkは1並列・8並列の3組すべてで短縮した。正しさの有限対照も通過。独立再生成と両product platformの通常ゲートへ進めることを推奨する。main統合・リリースは未承認。最大の懸念は、テスト全体では遅くなった組が残り、観測が単一Mac・3process/セルに限られること。以下は局所的な計測結果であり、一般的な性能保証ではない。

## 同条件の現main対照

基準mainは`eeef899a296be8aa38cc9e3de0a550c428d4dca9`（prepared出力変更を含む）。基準バイナリは`3cfd9854d235d4d472734206d2ba03c6944d7d3a`の既存canonical generated guestを使用した。全Go/assembly、internal/、cmd/、release/、go.mod/go.sumの345pathが基準mainと同一であることを空diffで確認した。新guestのC sourceは同3cfd9854、ホスト開発段階は`29d7e04a3822a01ec26f74e52290e1b0c8b2058b`。後のcanonical化では、計測した開発版とGo/assemblyおよびhost互換定数の同一性を検査する。実行記録を後のSHAの新規実行へ付け替えない。

Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、macOS arm64。同じSQL/schema/triggerと従来matched modelcaseを使用。P1/P8、基準と候補を交互に3process/セル、各warmup1。計測24process＋warmup8＝32process。Forkは48children/process（144children/セル）。最初から接続＋検証SQL、WaitDisconnected、Closeも計測した。起動・準備・Snapshot・Fork・SQL・Closeを含むsuiteの壁時計中央値は重複operation時間の合計ではない。

| 並列 | Fork中央値 基準→候補 | 短縮率 | suite中央値 基準→候補 | 短縮率 |
|---|---:|---:|---:|---:|
| 1 | 16.74 → 15.85ms | 5.3% | 1361.44 → 1327.67ms | 2.5% |
| 8 | 37.88 → 33.81ms | 10.7% | 498.60 → 475.54ms | 4.6% |

Fork process中央値の組別短縮率は、P1が5.71/5.30/4.56%、P8が9.47/12.76/7.52%。suiteはP1が2.66/2.53/−2.98%、P8が0.46/8.44/−4.37%。外れや遅くなった組を削除・良い結果へ差し替えていない。

接続＋検証SQLはP1 3.923→3.940ms、P8 3.859→3.790ms。CloseはP1 2.143→2.155ms、P8 2.129→1.955ms。明確な後続処理への費用移動は観測していない。前のspike系列とは混ぜず、pgmemは再測定していない。Fresh全体、保持RSS、別page size、実guest OOMの改善は主張しない。

## 最小変更と正しさ

`guest/source.patch`のbuf_pool_t::create()だけを変更。WASIX/Emscriptenで同じposix_memalign/2MiB alignmentと元pointerを使い、既存のextent_end計算で有効なdescriptorだけを初期ゼロ化する。共通allocatorのゼロ保証、既定16MiB、grow、失敗/再試行/free、非WASM経路は維持。実験用env/mode/poison/abortは製品に含めない。前のspikeを丸ごとmergeしていない。

新guestは`77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`。LLVM23.1.0/Binaryen133と既存SDK/sysrootを固定し、新しいLinux arm64/root環境で公式single-pass開発ビルドが成功した。これはUNQUALIFIEDの1buildであり、独立2build PASSではない。worker3関数の全body、CRC全validator/body/table/offset、初期data全体は現canonicalと同一。新guest SHAだけが変わる。算術/CRC定数/table byteの3破壊対照も拒否された。事前変換と公式native経路の再変換は61Go/assembly fileが一致した。

- 実prepared Cの共通allocator契約：dirty bufferから全ゼロ、alignment/size、ENOMEM、元pointer free、C/C++ link、4破壊対照を通過。pool専用の確保/clear文もdirty memory上で範囲・frame非変更・ENOMEM/freeと3破壊対照を通過。後者のlayoutはhostモデルであり、実buf_block_tの全実行に代わるものではない。
- 基準/候補ともbasicのroot＋4ForkでSQL・rollback・エラー後継続・分離を確認、開始5/Close5。
- 基準/候補とも通常/COMPRESSED各32MiB・8192rowsを全byte/value照合。実read miss増加を確認し、16→9→11→16MiB（566/692/1008pages）と2Fork分離を通過。候補のread missは520→35121、開始3/Close3。
- `.ibd`/`ibdata1`の実read EIOをそれぞれ1hit確認。双方とも再試行後に正しい値を返し、健全な別Forkを確認。SQLエラー発生を必須とはしていない。
- test-only host overlayでfast_shutdown2のdirty fixtureを取得。実crash-recovery分岐はcleanで0/0、dirtyで1/1。双方とも512row payload/valueと2Fork分離を確認。通常Snapshotのfast_shutdown1は製品で変更していない。
- 候補のCRC832 length/alignmentと80実validator valid/corrupt/LSN対照がPASS。per-instance env/controlled first-worker-trapの単体対照がPASS。実guest worker-trapと広い通常ゲートはcanonical CIの別のownerであり、この単体PASSへ含めない。
- 公式Go1.26.10のUNQUALIFIED native SQL/transaction/Snapshot/Fork/Close smokeがPASS。事前normal source ownerは87件＋23subtest PASS。canonical化後の通常検証は別記録とCIで確認する。新しいclean-source host（953ffbe0、Go1.26.10、vcs.modified=false）で12library familyのretained symbolを再照合し、ライセンス証跡も新guest/generated provenanceへ結び付けた。依存archive・notice・条件は変更していない。

fault/recovery観測overlayは計測バイナリと製品に入っていない。前のspikeの意図的bad-descriptorsは20秒でkillした履歴を維持するが、そのmode/abort経路は今回削除した。今回の有限対照PASSは任意OOM・全破損入力・全OSの証明ではない。

## 残る条件と判断

正確なcandidateをcanonical入力/recipeから再生成し、通常check/integration、worker ownership/CRC/実SQL/Fork/cleanupと上記buffer対照をmacOS arm64/Linux x86_64で通す。canonical build recordは独立再生成PENDING、UNQUALIFIED bootstrapは履歴のまま保持。CI提出後はrun URL/SHA/operationを返して引き渡し、監視しない。CI成功後のmain採用判断とRelease承認は別。

初回のsourceチェック/依存取得ではsystem Pythonのpytest欠如、Python3.9のtar安全抽出API不足、sandboxのDNS/Docker/local bind拒否があった。適切なtask venv/許可で同じsourceを再実行した。fault harness初回は旧spikeのmode必須ガードでStart前に停止したため、双方からその起動専用ガードだけを除去。EIO・値・sibling・Closeのoracleは維持した。各failureは保存した。通常のライセンスguardは旧guest証跡を正しく拒否したため、新バイナリで再auditした。入れ子/外部worktreeのGoビルドは親の別SHAまたはVCS stampなしとなり、auditが拒否。PWD変更では解消せず、同じコミットの通常cloneで正しいSHAとclean stampを確認してから採用した。元のユーザー変更は削除していない。

## 保存と再現

`evidence/summary.json`、`runs/`が全観測、`tools/analyze.py`が完全matrix検査と再集計。`harness/`は使った入力（go.modのreplaceだけportable化）。`tools/`は実行recipe。`ci_validate.py`はcanonical sourceにtest-only overlayを適用し、両OSで同じbuffer対照を実行する。`verify_saved.py`はnetwork/buildなしでhash・summary・CSVを再現する。

公開記録のpath/行末空白は正規化し、`publication.json`に元/公開hashを併記。これらの記録を現在のinstallation入力へ流用せず、固定sourceとrecipeから新しいreceiptを生成する。guest/build/source/toolchainのidentityはbuild-evidenceとsource-identitiesに保持。SDK、downloads、generated source、native binaries、cacheは再作成できるため作業完了時に削除する。mainと元のユーザー変更は触らない。#56/#116/#88やMDEV-42129の再調査・issue変更は行っていない。
