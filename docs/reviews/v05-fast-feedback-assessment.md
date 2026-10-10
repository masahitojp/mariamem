# v0.5.x Fast Feedback Assessment

## Human Review向け結論

v0.5.0の主目的はMariaDB alphaから安定版への更新のままとする。
まず既存の実行スクリプトへ工程別計測を加え、同じ開発作業中のGoキャッシュを揃える。
guest更新用の単発ビルド経路は有用だが、Release証拠と混ざらない設計を確認してから着手する。
外側のhost Go変更にC/C++ビルド・WASM生成・wasm2go変換は不要。
ただしshimの型や依存が変わると、WASMが同じでも大量のGo再コンパイルが起こり得る。
反復中は変更に直接対応するテストと小さい実guest確認を使い、候補が固まった段階で広げる。
両OSのruntime qualification、再生成性、最終artifact、公開物の検証はそれぞれ維持する。
今回変更するのはこの報告書だけ。CI・runtime・生成コード・計測実装は変更しない。
重いビルド／テスト／benchmarkの再実行、新規qualification、Release dispatchは行っていない。

## 1. 基準と証拠の同一性

調査日: 2026-10-10。開始時のmainとorigin/mainは
`b1666e4a6f4b3b77269b294de0fe225031ad12ce`、working treeはclean。
作業branchは `experiment/v05-fast-feedback-assessment`。

- v0.4.6 source commit: `b56be17206b6beef18f55c8ea39b254638da8590`。
- v0.4.6 annotated tag object: `09d7b82e1900318dde45d08bebd9328ea35e6ef7`。
  remoteのtagをpeelしたcommitと区別して記録した。
- [Release run 38040418075](https://github.com/masahitojp/mariamem/actions/runs/38040418075)
  は上記sourceで完了・成功。両OSのqualificationとpublic smokeも成功。
- released sourceから現在mainへの差分は資料整理と公開後discovery tooling/tests。
  guest・generated Go・製品runtimeの差分はない。しかしmain SHA自体をReleaseで
  qualification済みとは扱わない。
- [Verification Economics](v045-verification-economics.md)のnative計測は
  `34eaea1df86b57765a4d8b0840845a33d539065f`、
  [run 37994377940](https://github.com/masahitojp/mariamem/actions/runs/37994377940)。
  v0.4.6／現在mainの時間へ読み替えない。

一次入力は[開発手順](../development.md)、[現況](../project-status.md)、
[Infrastructure Audit](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)、
[P1のruntime/artifact分離](v045-p1-runtime-artifact-migration.md)、
[Economicsの証拠](v045-verification-economics-evidence.json)。
既に実装済みのhandwritten一覧一本化・source/license oracleの早期実行を再提案しない。

## 2. 実行時間と容量: 分かること／まだ分からないこと

### v0.4.6 Releaseの既存step時計

ActionsのUTC開始・終了時刻の差。guest builderはLinux arm64、製品検証は
Ubuntu24.04 x86_64 / macOS15 arm64。Go1.26.8 / Python3.14。
1回の既存runであり、分散・cold/warm差・速度改善を測った比較ではない。

| 工程 | Ubuntu / Linux builder | macOS | 実際に含む範囲 |
| --- | ---: | ---: | --- |
| source→WASM独立2回 | 663 s | — | SDK/archive準備、source準備、C/C++ compile/link、postopt |
| generated Go再現＋GPL source closure | 272 s | — | converter build、変換、fixture、adapter/install、比較、ソース検証 |
| candidate「host-only wheel build」 | 1261 s | 1238 s | pip、runtime検証またはreuse確認、source checks、wheel build、freeze |
| final consumer検証step | 346 s | 410 s | 外部Go lifecycle/failure/load、GORM、installed wheel、SQLAlchemy/pytest |
| public module / wheel step | 233 s | 284 s | 公開tag/module・wheel取得、同一性、install、最小動作 |

再現用step開始→終了:

```text
run=38040418075 source=b56be17206b6beef18f55c8ea39b254638da8590 UTC
guest build        09:11:05 → 09:22:08
regeneration/GPL   09:22:08 → 09:26:40
candidate Ubuntu   09:27:09 → 09:48:10
candidate macOS    09:27:24 → 09:48:02
consumer Ubuntu    09:50:16 → 09:56:02
consumer macOS     09:50:18 → 09:57:08
public Ubuntu     10:22:39 → 10:26:32
public macOS      10:22:46 → 10:27:30
```

resolve開始09:10:00から最後のpublic job完了10:27:36まで77分36秒。
queue時間は含まず、並列jobの時間を加算した値でもない。
aggregate job 668秒、publication job 762秒には入力復元・hash照合・guard・公開が含まれる。
272秒をwasm2goだけ、1261/1238秒をGoコンパイルだけと呼ばない。
Release全体の待ち時間を、日常開発の必要時間とも扱わない。

### v0.4.5 runtime-onlyの既存分解

| exact 34eaea1 qualification | Ubuntu | macOS |
| --- | ---: | ---: |
| job全体 | 1075 s | 1495 s |
| canonical check | 419.870 s | 587.544 s |
| check内Go test processの報告時間合計 | 1.257 s | 1.620 s |
| check内pytest報告時間 | 16.80 s | 28.14 s |
| canonical integration | 622.941 s | 856.910 s |
| race/tagged Go test process報告時間合計 | 38.243 s | 30.402 s |
| real-host pytest報告時間 | 50.14 s | 32.54 s |

check残差約402/558秒はcompile/link/vet/source確認/process起動等を含む。
`snapshots.py`の49確認にはelapsed記録がなく、integration残差もcompileだけではない。
環境準備/upload/cleanup等を含む「job全体−check−integration」は約32/51秒。
以前の約15分Ubuntu／31分macOSとは別runで、改善率として比較できない。
成功時の主な削減余地はPythonテストの件数よりGo build variantsと再利用にありそうだが、
現状の時計ではその寄与を確定できない。

[古いguest build記録](../../release/generated-go-build.json)には
source `1687465bcbaff74a334b3e89181c47e66478792c` のprepare 13.081秒、
toolchain probe 5.214秒、guest build 658.249秒、postopt 15.928秒がある。
別環境の記録なので、上の663秒との直接比較・単純な半減推計に使わない。
その `accepted_guest_identity_match:false` も当時の比較対象に対する記録であり、
今回のRelease失敗を意味しない。

### resourceとcache

- 現在の `internal/generatedgo` 内Go/asmは76ファイル、233,173,919 bytes
  （222.37 MiB）。同じsourceを4か所へ複製するとそれだけで約889.49 MiB。
  これはfile sizeであり、compiler Peak RSS・累積allocation・cache sizeではない。
- accepted WASMは18,560,271 bytes、linked WASMは22,051,175 bytes。
  SDK、unpacked source、翻訳中間物、normal/race/packaging Go cache、link scratchが別途必要。
- guest build recipeはJOBS=3、Goの多くのbuild/testは `-p 1`。
  並列度を増やした速度／Peak RSSの実測はなく、今は増やさない。
- [Go比較のbuilds](../benchmarks/go126-vs-go127-evidence/builds.json)では
  source `80a37385f9d1eda6604358dd5ba2235feb0b26ca` のGo1.26.8 buildは4.561秒。
  事前に温めたcache・別対象・別flagsであり、coldからの改善率や現在のtest時間ではない。
  Go1.27への更新をfeedback改善策にしない。
- 今回確認したstage記録にはcommand別CPU、Peak RSS、cache成長の実測がない。
  欠測をゼロ扱いせず、次の計測対象とする。workspace budgetも消費実測ではない。

資源取得の土台は既にある。[process_cost.c](../../benchmarks/tools/process_cost.c)は
指定した生存PIDのCPU/RSSとmacOS physical footprint／Linux PSSを取得し、
[goisolation/cost.go](../../benchmarks/goisolation/cost.go)はprocess treeをsampleする。
前者は終了済みcompiler全体のPeak RSSを自動で取得せず、後者もsample間に終了した
短命processを見落とし得る。compiler工程の集計へそのまま正確な数値として転用しない。

## 3. 現行経路と再利用の境界

```text
guest inputs / source.patch / overlays / toolchain
  → prepare_guest → C/C++ compile/link → Binaryen postopt → exact WASM
  → translate_guest (patched wasm2go) → source-only adapter → generate_runtime
  → committed Go + handwritten glue → Go compile/link
  → relevant tests → canonical check/integration → both-OS runtime proof
  → final module/wheel + consumers/source/license guards → publication smoke
```

| 現行owner | 反復時の扱い / 正しさの境界 |
| --- | --- |
| [build_generated_guest.py](../../scripts/build_generated_guest.py) | fresh Linux arm64/root、2回以上の独立build、accepted WASM hash一致必須。新guestを試すための単発入口ではない |
| [regenerate_release_guest.py](../../scripts/regenerate_release_guest.py) | exact accepted WASMからtranslator→memory32 fixture→source-only adapter→installer。生成・handwritten全byteを比較 |
| [translate_guest.py](../../benchmarks/spikes/generated-go-integration/translate_guest.py) | guest/archive/7 patchのidentity、converter build、変換を記録。新WASMなら旧生成outputは使えない |
| [setup_candidate.py](../../benchmarks/spikes/generated-go-integration/setup_candidate.py) | productionはsource-only。historical native bundle作成分岐をfast routeへ戻さない |
| [generate_runtime.py](../../scripts/generate_runtime.py) | canonical adaptation・provenance・14 handwritten file inclusion。生成outputを直接編集しない |
| [verify.py](../../scripts/verify.py) | scope docs/python/full、別integration。source/license oracleは既にGoより前 |
| [validate_product_candidate.py](../../scripts/validate_product_candidate.py) | exact source・両native OS。1run内のcheck/integrationは同じtask cacheを既に共有 |
| [build_alpha.py](../../scripts/build_alpha.py) | final host/wheel、CGO=0・trimpath。GOCACHE未指定時はroot/build/gocache。普通のtest/raceと同じcompile variantではない |
| [generated_release.verify_build](../../scripts/generated_release.py) | exactsource/pins、独立2build、link/WASM/translation/全inventoryをfail-closed照合 |

`build_guest.py` / `build_guest_wasm.py` はretired Wasmer toolとして停止する。
名前だけを見てguest開発の入口に使わない。spikes下でも上表のrecipeは現行callerがある。
移動・削除・新framework導入はこの調査の提案に含めない。

Go cacheはsource/compiler/options等で再利用を判定するが、test-result cacheとは別。
外部C library変更はGo cacheが検知できない場合があるため明示invalidateが必要。
参照: [公式Go build/test caching](https://pkg.go.dev/cmd/go#hdr-Build_and_test_caching)。
同じcache pathでもOS/arch/toolchain/race/CGO/trimpathの差による必要なbuildは残る。
同じhost binaryを使い回す際は、cacheとは別にsource/build flagsの一致が必要。

| 再利用対象 | 使える条件 | 再利用しない境界 |
| --- | --- | --- |
| downloaded upstream/SDK/converter archive | canonical pinのchecksumを実bytesで再確認。同じactive task内 | 別input/hash、未検証download。cache保持はtask終了まで |
| exact WASM | guest source/patch/overlay/toolchain/flagsが不変 | guest更新、ABI/import変更。旧hashを書き替えて承認扱いにしない |
| translated/adapted source | WASM、converter source/patch、adapter/formatterが不変 | converter変更なら翻訳以後、adapter変更なら対応後段を再生成 |
| checked-in generated Go | guest/生成recipeが不変。host-onlyでは既存treeを使用 | 直接生成output編集、guest更新、未分類handwritten追加 |
| Go build cache | compatible source/tool/options/platform。task内の反復 | test実行の省略やruntime proofの代用ではない |
| runtime receipt | 既存validatorがexact inputsと両OSを認証し、期限内 | guest/host/harness等の非例外変更。expired/missingは拒否 |

現行Release builderは既存SDK/work/source/outputを拒否し、translatorも新しいoutputを使う。
archiveを再利用できることと、unpacked SDK・converter executable・C objectを現在の入口で
増分再利用できることは別。後者は現行のfresh検証経路には用意されていない。

**ビルド再利用と検証証拠の再利用を分ける。** 前者は計算結果の再利用、後者はその入力へ
保証が成立したという主張。旧WASMと同じでもhostを変えれば旧runtime proofは使えない。
guestを変えればguest互換性に束縛された旧Snapshot／旧SQL成功も新guestの証拠ではない。

## 4. 変更範囲に応じた検証マトリクス

以下は反復開発の提案であり、既存CI selectorの変更や新しいproof契約ではない。
対象を絞るのは最初のfeedback。候補が固まれば必要なcanonical verificationを実行する。

| 変更 | 初回feedback | 作り直すもの | 安定候補で必要な検証 |
| --- | --- | --- | --- |
| docs | wording/link/diff、docs scope | なし | docs/public boundary。unchanged runtime不要 |
| pure Python tooling | affected unit/negative paths、python scope | なし | touched identity/license/release owner。trust変更はHuman Review |
| 外側のhost/API/wire Go | affected package test＋該当のreal SQL regression | changed Go依存closureとbinary | full check、該当integration、両OS新runtime proof。WASM/変換は不要 |
| WASI/MemFS/FD/ownership handwritten glue | inclusion/source oracle、focused race/FD/growth/failure | installer inclusion確認、依存Go。通常guest C再build不要 | Snapshot隔離/lifetime・FS semantics・該当integration、両OS新proof |
| converter/patch/adapter/formatter | fixtureとgenerated/source/license oracles | exact unchanged WASMから変換または該当後段を再生成 | regeneration byte proof、runtime/integration、両OS、final consumers |
| MariaDB版/source.patch/guest overlays/SDK/compile flags | source/toolchain確認→単発build試行→小さいrealguest確認 | C/link/WASM、変換、生成Go、hostすべて | 独立再build・source/license review・SQL/wire/session/auth/FS/Snapshot/failure・両OSproof・guest race census |
| Python host連携/API | affected Python contractとfresh host実行 | hostが変わればrebuild、Python実装 | realhost/scenario、両OS必要範囲、installed artifact consumers |
| packaging/consumer harness | artifact/identity focused tests | affected final artifacts | final Go/wheel consumers。runtime receiptの適用は既存guardが決定 |
| provenance/license evidence | actual content deltaとbinding/mirror/source tests | 根拠がある派生記録だけ | 法的義務はHuman review、source closure/final notices。hashだけの自動refresh禁止 |

hostの外側を変える場合とgenerated `base` の型を変える場合を区別する。
`internal/host → internal/guest → internal/generatedgo → code/p*/base` の依存があり、
後者は大きいtranspiled packageの再compileを伴い得る。shimのABI/guest import契約まで
変えるなら「Goだけの変更」扱いはできない。
現在のDevelopment CIはこれらを細分化せず、runtime/unknownをfull check＋integrationへ送る。
小さいrealguest smokeだけでCI／Releaseが合格するよう変更する提案ではない。

## 5. 最小の開発feedback経路

1. diffから入力境界・test ownerを決める。source変更なら既存の安いoracleを先に使う。
2. active taskのcache・toolchain・flagsを揃え、affected unit/negative testを実行する。
3. runtimeへ影響するなら小さい実MariaDB確認と変更に固有のregressionを実行する。
4. 候補が安定したらcanonical check/integrationへ拡張し、必要な両OS proofを取る。
5. Release時にexact candidateの再生成／最終artifact／consumer／guard／publicを検証する。

既存の初回入口例（今回実行していない）:

```sh
# 生成／handwritten／provenance変更がある場合の安い入口
python3 scripts/verify_generated_runtime.py
python3 -m pytest tests/test_generated_runtime_inventory.py \
  tests/test_distribution_licenses.py tests/test_packaging_license_mirrors.py -q

# host / Snapshot変更に対応するpackage確認の例
GOTOOLCHAIN=go1.26.8 go test -p 1 ./internal/host ./internal/snapshot -count=1

# 小さいrealguest確認: Fresh、固定、sibling隔離、Close
GOTOOLCHAIN=go1.26.8 MARIAMEM_TEST_DEFAULT=1 \
  go test -p 1 -tags=integration ./tests/godefault \
  -run '^TestDefaultNoBundleAndForkIsolation$' -count=1 -timeout=3m
```

最後の1caseはprotocol/type/auth、many/concurrent、FD/mapping failure、全raceを保証しない。
新guestでは追加の該当SQL/互換性/隔離検証が必要。部分testはqualification receiptにならない。
Python実guesttestはその作業のsourceからbuildしたhostを使い、古い `MARIAMEM_TEST_HOST`
overrideを信用しない。通常 `check` はそのoverrideを消し、integrationが新hostをbuildする。
Go full checkのtest-result cachingと、integrationの `-count=1` は現行のまま保持する。

## 6. 重複、CI、Releaseとの境界

- `go test` とexplicit custom vetは似ていても同じ保証ではない。generated dead-controlの
  狭い例外とhandwrittenの全analyzerを保つ必要がある。実行traceなしにvetを消さない。
- integrationの複数Go invocationは同じcompatible package cacheを使える。
  コマンド数だけをcompile重複回数と数えない。race variantは普通のbuildと別に必要。
- DevelopmentのUbuntu checkとmacOS integrationは別workerでcacheは共有されない。
  両OS native runtime qualificationはそれとは異なり各OSでcheck＋integrationを行う。
  一方が他方のplatform証拠を代替しない。
- runtime workflowのsetup-goはcache falseだが、1run内のscratch cacheは共有済み。
  既にある再利用を新しい改善量として数えない。
- full checkのsource suitesの二重実行はv0.4.5で除去済み。
  generator/source byte proof、runtime SQL、installed consumer、public取得は
  検出する失敗が違うため統合・削除対象ではない。
- Developmentは過去artifactの期限に依存しない。runtime proofは90日、final Release
  inputsは14日。失効・wrongsourceならRelease reuseは拒否され、通常のqualificationへ進む。
  約束された必要検証をsilent downgradeしない。
- [runtime_validation.py](../../scripts/runtime_validation.py)は全tracked inputとmode、
  tools/harness、native両OS、authenticated artifact/run identityを照合する。
  docs/version等の既存の限定例外を越えてreuseしない。guest/host/executable harness変更は
  旧証拠を無効にする。このtrust scopeの縮小は別Human Decisionが必要。
- [Release workflow](../../.github/workflows/release-candidate-ready.yml)のfresh source
  独立2build・生成byte比較・GPL closureと、最終artifact consumersは維持する。
  正当なruntime reuseはこのsource/artifact境界の免除ではない。
  publication smokeはaccepted artifactの同一性を根拠に公開経路を確認する。

## 7. 改善候補: 最大3件

### 1 — 既存orchestratorのcommand別時計・resource記録（先行推奨）

**問題:** 数百秒の残差をcompiler/vet/linkへ割り当てられず、改善を選ぶ根拠が不足する。
**最小案:** `verify.py` の既存 `run` とguest/regenerationの既存stage呼び出しで、任意の
trace出力へargv/source/tool/flags/exit/wall/cache状態を記録する。新workflowやmanifest、
benchmark frameworkは作らない。次に元々必要な実行があった際に測り、計測だけのfull runをしない。
CPU/Peak RSSは既存process measurement helperを先に確認し、取れる境界だけ追加する。
子process全体・Linux/Darwinの単位差・max RSSの非加算性を明記し、欠測はunknownにする。

**期待効果:** 誤った最適化と重い再調査を避ける。成功runの短縮率はまだ主張できない。
**負荷:** 小〜中。command包装とfocused tooling tests、失敗時にも記録を残す処理。
**リスク:** wrapperがexit code/env/orderやstdioを変えること。
**検証:** 成功/失敗/子終了、source oracle失敗ならGo未実行、traceなし時の同一argv/env、
resource単位・aggregationのfocused tests。必要検証と証拠identityは変えない。

### 2 — active task内のGo cache配置・build環境を揃える（先行推奨）

**問題:** developer既定cache、task scratch、`build_alpha` のroot/build/gocacheで再利用が分断
され得る。完了の度に全cacheを破棄する方針と、同じactive task内の反復再利用は両立する。
**最小案:** 既存workspace/development手順で1taskの絶対GOCACHE/GOPATHを共有し、
Go test・Python用host buildが同じtoolchain/envを使用する。既存のworkspace budget監視を使う。
新cache manager、永続KEEP、cross-OS compiled cache、Release CI cache変更はしない。

**期待効果:** unchanged generated dependencyの再compileを回避し得る。
warm 4.561秒の過去記録は可能性の参考であり、現行cold比較の改善率ではない。
race/CGO/flags差、shim変更の必要な再compileとlinkは残る。
**負荷:** 小。既存手順／env引き渡しの整理が中心。canonical qualificationは既にrun内共有済み。
**リスク:** stale host binary、cgo external input、複数作業のcache容量蓄積。
**検証:** env継承・task path/budget/cleanupのfocused checks。runtime testは実行し、binaryの
source/build identityは別に確認する。active task終了時にcacheを削除する。

### 3 — 既存guest recipeを使う明示的な開発用単発経路（条件付き）

**問題:** 現行release builderはfresh2build＋旧accepted hash一致を強制する。
そのままでは新MariaDBの未知のWASMを反復試行できない。
**最小案:** 既存recipeに開発用の実行modeを設計し、1buildのinput/tool/patch/observed hashを
保持して後段試行へ渡す。outputはRelease evidence directoryと分離し、UNQUALIFIEDとする。
既存のRelease default、accepted pins、人による新入力採択、独立2build、source closureは保持する。
`--repetitions 1` をRelease receiptとして許す変更にはしない。
新guest shapeでadapter/translationの修正が必要なら、その依存を明示して別reviewへ戻る。

**期待効果:** 不安定なguest試行ごとの2回目のC buildと最終artifact検証を後へ移せる。
SDK準備も含む663秒を半分になると推計しない。実際の効果は候補1の時計で確認する。
**負荷:** 中。既存accepted input制約と新guest試行の区別、後段の仮入力の扱いを設計する必要。
**リスク:** 仮のWASM/pins/receiptをRelease保証へ混入、固定build pathやsourceの使い残し。
**検証:** dev receipt・単発・wrong hash・experimental patchが既存Release guardで必ず拒否、
デフォルト2build/clean/compare維持、dev失敗cleanup。新guestのqualificationは別に全境界を実行。
**判断:** 案1・2を先行。案3はguest試行開始前に小さい設計を確認してから着手する。
これは再生成保証を反復中にまだ与えない経路であり、最終保証の緩和ではない。

## 8. 後回しにする改善

| 候補 | 今回推奨しない理由 |
| --- | --- |
| 永続／remote CI cache、precompiled test artifact | stale/cross-platform/flags/容量/identity設計と効果の計測が未完。まずactive task内共有で十分か確認 |
| runtime proofを「host intent」等で広く再利用 | whole-tree trust scope変更にはdependency closure・negative proof・Human Reviewが必要 |
| incremental CMake/ccacheとSDKの長期常駐 | clean buildと不一致検出の責任が増える。実stage/容量データと単発経路の効果を先に確認 |
| 巨大Go package分割、コンパイラ変更、並列度引き上げ | 局所tooling変更ではなく再生成/メモリ/qualificationに影響。未計測の推測で進めない |
| Python toolingのGo書き換え | Python実行時間より未分離のGo build予算が大きい。言語統一に価値を仮定しない |
| Snapshot/MemFS最適化、新benchmark campaign | stable MariaDB移行のfeedback経路と別テーマ。既存Decisionと測定を保持、実装しない |

## 9. 再現・引き継ぎ

読み取りのみの確認コマンド:

```sh
git ls-remote origin refs/heads/main refs/tags/v0.4.6 'refs/tags/v0.4.6^{}'
git diff --stat b56be17206b6beef18f55c8ea39b254638da8590..b1666e4a6f4b3b77269b294de0fe225031ad12ce
gh run view 38040418075 --repo masahitojp/mariamem \
  --json headSha,status,conclusion,jobs,url
```

既存入力のSHA256（このmainのfile bytes）:

```text
docs/reviews/v045-verification-economics-evidence.json
21a153b2ce04fc6660fd5f9de184e2fddfb7f65e27f7922848b9311e01eaa830
release/generated-go-build.json
09121869e401b1ae2e67dff943d02df6f57c6c0568c05878017056ae1551cf40
docs/benchmarks/go126-vs-go127-evidence/builds.json
9c140128610d1066d9a6d1d78a31e84bce62794dd714680ec9f8d218840e552a
```

工程別CPU/Peak RSS/temporary bytesは未計測。次の必要な実行時にcold/warm、正常/race、
Go flags、source/hash、OS/CPU/parallelismを併記して埋める。
新guestの成功基準は起動だけではなくSQL/wire/session/auth、Snapshot/Fork独立性、
FS/growth/FD/failure、両OS、現在のguest race制約の再確認を含む。
full generated guestがrace-cleanという保証は現状存在せず、新版でも勝手に主張しない。

提案の実装はHuman Review後。調査用worktreeはreport commit/push後に削除し、
compactな時刻JSONと観察記録だけを保持する。build/cache/source copyは保持しない。
