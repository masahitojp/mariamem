# wasm2go差分管理 — 調査・提案

## 推奨

**短期はAの固定commitを維持。次の実装候補はB「goccy本家＋必要最小パッチ」。
Dは入力形式・未対応命令に限定して併用候補とし、Cの独自forkは現時点で作らない。**

理由は、現行forkの大きな変更群がmariamemで使っていない生成レイアウト機能で、
一方trap・shared memory・host境界・メモリ所有権の修正は変換器/生成runtime側に必要だから。
Dだけでconverter修正をなくす案は推奨しない。Bは静的調査では有望だが、まだ移行実装も
実行qualificationもしていない。現在の動作を置き換える承認とは区別する。

- main baseline: `386a62c3669e37bb8aaad58cd0aca8da893b3d80`。
- 現行fork: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`。
- 本家: `730057c146463f663e8774587bc96fb2bea91af8`。調査時の本家HEADでもあり、forkのmerge base。
- pglite-go: `c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f`。
- Binaryen version_133: `fba5005a132d85d578be5bd010e0487ed8e2ce3e`。
- 固定SHA・archive hash・25ファイルのblob差分・14 commitsの分類は
  [compact evidence](wasm2go-diff-management-evidence/identity.json)以下に保存。

今回行ったことはソース読解、GitHub compareと取得archiveの照合、既存patchの個別
`git apply --check --unidiff-zero`のみ。patchの適用、Wasm rewrite、converter build、
guest build、runtime/CI変更、性能計測はしていない。

## 1. 現行構成とfork差分

現行は **shibukawa fork＋mariamem管理の7パッチ＋既存のsource adapter/handwritten host**。
canonical入力は `release/generated-go-{toolchain,translation,inputs}.json`、順序は
`benchmarks/spikes/generated-go-integration/translate_guest.py`で固定される。
「shibukawa forkのみで現在のcorrectnessが成立している」と捉えるのは誤り。

本家から固定forkへは **14 commits ahead／0 behind／25 files**。archiveを取得し、
固定forkのarchive SHAを既存pin `1fcd91ee...`と照合、ファイル内容も比較した。
14件のうち3件はREADME説明。残る変更は下表で網羅する（個別commitはCSV）。

forkの`main`は本家mirrorで、機能branchは`pgmem`。
調査時のfork default HEADも本家の730057cだった。branch名/`@latest`で現行ac98の代替を
取得してはいけない。[forkの構成](https://github.com/shibukawa/wasm2go-fork/blob/ac98bcf00c17d8531f0c071a9836d0b50975e7ff/README_ABOUT_FORK.md)

| fork差分 | 現行mariamemの依存 | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| export名のGo識別子衝突をsuffixで解決 | 常時有効な修正だが、現行guestで必要な衝突は今回未実証 | 既存修正を保持 | 実際のexport集合を確認し必要な場合だけ移植 | 同修正を自社保守 | 必須exportを残すstrip/renameなら候補。host ABIとDCE roots維持が必要 |
| Go1.27 gcasm header／未知jump table fallback | canonicalは`-pure`、native asm変換を選択しない | 未使用変更も含む | 現行routeには持ち込まない。将来asm使用時に別評価 | 不要な保守を抱えやすい | guest rewriteではGo compiler header問題を直せない |
| caller-provided memory向けInitData | 現行productionに`InitData`呼び出しなし。`NewWithMemory`とactive data初期化は必要 | 追加APIも保持 | 不使用APIは省く候補。Fresh ctorの初期化を実行で確認する | 同じ判断が必要 | host-owned memoryの初期化/寿命をguestだけで代替できない |
| symbol名＋固定chunks＋name section parser | 現行CLIは`-pure`のみ。これらはopt-inでOFF | 他製品向け機能も保持 | オプション群と専用parser/testsを持ち込まない候補 | 独自forkに持ち込む理由なし | Wasmを書き換える問題ではない |
| group-files＋Windows device名修正2件 | 上記opt-in機能に従属しOFF | 保持 | 対象機能ごと省く候補 | 同左 | 不要 |
| addr-consts＋use-site key修正 | opt-inでOFF | 保持 | 持ち込まない候補 | 同左 | 静的データをguestで再配置しても保守コストを増やすだけ |
| ForceContendedAtomics＋bulk bounds＋memBound（2 commits） | shared memoryの境界と7パッチの依存。ForceContendedはproduction callなしだがWait fixtureが使用 | 既存helperを保持 | 必要なhelper/fixture能力だけ移植。non-shared aliasを全sliceで許すpgmem契約は採用しない | 自社runtime policyとして保持 | ordinary atomic化、shared削除、固定巨大memoryで代替してはいけない |
| fork README 3件と各機能tests | 根拠/回帰。pgmemの要件はmariamem要件ではない | upstream履歴として保持 | 必要な修正の回帰は残す。無関係な機能を採用する理由にしない | 文書/fixtureも自社保守 | 適用対象外 |

生成layout変更は主にGoソースのdiff/Git転送量対策。現行で有効になっていないので、
それを除くことによるstartup/SQL速度改善は主張しない。オプションOFFでも共有emitterの
変更はあるため、Bで生成物のbyte identityが必ず同じになるとも主張しない。

## 2. mariamemの7パッチ — 各方式で置き換えられるか

A/Cは各修正をconverter内部に保持できる。Bでは下表の必要部分を最小seriesにする。
Dの「可能性」は未実装・未検証の仮説であり、根拠のない代替を採用しない。

| patch／source | 守っていること | Bの扱い | Dで解消できる可能性・限界 | correctness risk／検証 |
| --- | --- | --- | --- | --- |
| `imported-memory.patch` → CLI module metadata | importされたmemoryのmin/max/sharedをemitterへ伝える。任意外部memory linkerの実装ではない | 小さなparser/metadata修正を保持候補 | 限定的にimport memoryをdefined memoryへ内部化する候補。limits/shared/memory export・index・root/workerの同一ownerを保存する必要 | 中。`imported-memory.wat`／`defined-memory.wat`、実guestのconstructorとgrow、thread visibility |
| `import-function-index.patch` → `emit_ssa.go` | 関数indexはimport全種類の位置ではなくfunction importsだけを数える | 汎用的bug fixとして保持/upstream提案候補 | memory importを消せば特定入力で回避し得るが、table/global/tag混在問題を一般には直さない | 高。`imported-memory-calls.wat`で実際のimport呼び先/値を検証。変換成功だけでは不可 |
| `relaxed-madd.patch` → decoder/lower/SIMD helper | `f64x2.relaxed_madd`を認識し、両laneでFMAという許可されたprojectionを選択 | 小さい局所機能として保持候補 | compilerで発生を防ぐか、対象opcodeのみmul＋addへ正規化する仮説。ただし既存FMA結果とbit一致しない。prebuilt sysrootとpostoptも確認が必要 | 中〜高。`relaxed-madd.wat`＋数値fixtureのoverflow/cancellation/NaN/±0/subnormal。結果の仕様許容とSQL数値契約を区別 |
| `pure-memory32.patch` → emitter/SSA/passes | 論理size/width/OOB、offsetの非wrapping、atomic alignment、SIMD bounds。unused trapping loadをDCEしない、trap前のstore順序を変えない | 必須correctness修正。`memBound`依存を取り込んで移植 | 最大memoryやguest sourceの「安全そうなアクセス」で代替不可。全load/storeにcheckを計装する案は新たなcompiler相当で最小化にならない | 高。actual generated trap test、patch内DCE/width/store-order tests、shared MemOpt gate |
| `controlled-thread-traps.patch` → thread pool | worker panicをjoin境界へ保持し、繰返しjoinでも失敗を失わない。cooperativeであり即時全agent強制停止ではない | host/runtime終了policyとして保持 | guest error code化やlongjmpはWasm trapと別物。worker goroutine panicをguest命令調整だけでrootへ届けられない | 高。root/worker trap、retained failure、WaitThreads、失敗時Close。既存containment限界は維持 |
| `host-logical-memory.patch` → accessMemory/WASI | 予約backing全体ではなく現在のguest-visible sizeまでhost buffer/string/iovecを許可 | host境界修正として保持 | guest load/store rewriteではhost import検証が変わらない。memoryを最初から最大にすればobservable sizeを変えてしまう | 高。`TestHostImportLogicalMemory`のEFAULT/unsigned overflow/zero-length/grown window |
| `linear-memory-owner.patch` → grow hook/module field | backing ownerがzero/commit等のgrow準備を完了してからshared sizeをpublish、失敗ならsize不変 | 小さなowner callbackを保持 | guestのmemory.grow設定だけではOS reservationの寿命/公開順序を保証しない | 高。stable pointer、shared growth、zero-fill、失敗時owner cleanup、両OS |

個別の本家dry-runは**6/7適用可能**。`pure-memory32.patch`だけはfork helperの`memBound`
追加に依存して適用失敗した。[check記録](wasm2go-diff-management-evidence/upstream-application-check.json)
これはordered seriesの成功、生成物の同値性、SQL correctnessを証明しない。Bには少なくとも
その依存の整理と、Wait fixtureが使うForceContended能力の保持/同等fixtureへの明示的移行が必要。
「7本をそのまま本家へ当てれば完成」とは結論しない。

`linear-memory-owner`はguestの実行用linear memoryの所有権。
Snapshotのprepared database files/MAP_PRIVATE所有権とは別資源であり、削除できる関係ではない。

## 3. A〜Dの費用と判断

| 方式 | 強み | 更新・再現性・保守コスト | 判断 |
| --- | --- | --- | --- |
| A 固定shibukawa fork継続 | 実guestが通った正確なbaseline。移行自体のリスクを増やさない | 本家→fork→ローカル7パッチの2段差分を毎回読む。forkのオプションOFF変更も確認。現行はarchive/patch/hash pinsで再現可能 | **短期継続**。guest更新とconverter全面移行を同時にしない |
| B goccy本家＋最小patch | 1本のbaseと目的別series。不要なpgmem layout/API契約を抱えない。汎用bug fixをupstreamへ戻しやすい | emitter/SSA/helperの内部context変更でpatch衝突は残る。必要なsemantics修正はmariamem保守。初回は再生成・資格確認が必要 | **推奨する移行候補**。静的根拠は強い、runtime同値性は未確認 |
| C mariamem独自fork | 結合した内部修正/fixturesを同じGit履歴で扱いやすい | repository/release/security/license/build ownership追加。upstream追従は消えない。Bと同じcode保守＋独自forkの管理責任 | **今は不要**。seriesが実際に維持困難と分かった場合のみ再評価 |
| D guest/compiler/限定Wasm処理 | 入力形状・特定の未対応命令ならconverter差分を減らせる | compiler/library/postoptの全段に影響。新しいguest hash、source→Wasm再現性、rewriterの仕様/版本、両OS/runtime/SQL qualificationが必要。rewrite自体の保守が移動する | **限定併用候補**。2つの小patchをなくすために汎用rewriterを新設しない |

差分数や行数だけで最小化しない。「7 converter patches→1巨大Wasm rewriter」は保守負担が
増え得る。Bでもqualification費用は消えず、converterを変えれば生成source/input identityが
変わる可能性がある。source/provenance/license evidenceはcontent deltaに基づき更新判断する。
hash変更だけで新しいlicense義務と見なさず、逆にCIを通すため自動refreshもしない。

## 4. Dの先行実装で確認できたこと／今回の仮説

### pglite-goで確認した実装

[固定sourceのTransform/Prelink/Instrument](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/internal/wasmpass/passes.go)
を読み、次を確認した。

1. 必須export集合だけを残すStripExports。
2. Emscriptenのmemory/table/base-global importsをdefined領域/固定初期値にするPrelink。
   memory limitsの`shared`属性もencodeへ渡している。
3. longjmp throwへ到達するcall（indirect含む）にflag check/early returnを追加するInstrument。

これは実在するコードである。一方、PostgreSQL/PGlite固有の固定address/base値とhost
longjmp ABIを使う。MariaDB/WASIXにその設定を適用できる証拠ではない。
[wasmpass tests](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/internal/wasmpass/wasmpass_test.go)
のtoy fixtureはround-trip/site count/構造確認が中心で、mariamemのthread/futex/trap
同値性を証明しない。shared bitを運ぶことと並列実行の正しさを検証することは別である。
longjmpをcooperative returnにする手法をWasm memory trapの代替にしてはいけない。

### Binaryenで確認した不適切な候補

固定version_133の
[`RemoveRelaxedSIMD.cpp`](https://github.com/WebAssembly/binaryen/blob/fba5005a132d85d578be5bd010e0487ed8e2ce3e/src/passes/RemoveRelaxedSIMD.cpp)
はRelaxed SIMDの子expressionを評価した後`unreachable`にする。
**通常SIMDへの意味保存loweringではない。正常な演算をtrapに変えるため除外。**
feature enable/disable flagも、それだけで意味保存loweringになったと判断しない。

### mariamem向けの未検証仮説

- **compiler側でRelaxed SIMDを出さない**：LLVM/wasixccの設定候補だが、この固定recipeで
  compiler・sysroot library・Binaryen後処理すべてから対象opcodeが消えるかは未検証。
  SIMD全体を無効にして速度/浮動小数点挙動を変える案を安易に推奨しない。
- **対象maddだけの限定rewrite**：仕様上、fused/unfused両projectionが許される。
  mul→addは後者の候補だが、stack operand評価順/重複評価/lanes/typeを保存し、NaN/±0等を
  検証する必要がある。現在のFMA固定fixtureを黙って緩めない。
  [公式Relaxed SIMDの許容結果](https://github.com/WebAssembly/relaxed-simd/blob/c3f9359af2cd607cc46b0a3274f90ea52543a2f2/proposals/relaxed-simd/Overview.md)
- **import memoryの内部化**：単一memory/standalone/WASIX host-owned実行という限定入力なら
  対応余地がある。ただしpgliteのtable/global/longjmp処理を一式導入せず、shared/max/grow/
  host供給bufferとworker共有を検証する。現在の12行metadata patchより安くなるとは未実証。
- **MariaDB側最小patch**：未対応instructionの発生箇所が具体的に特定され、同じC/SQL契約を
  守れる場合だけ候補。trapを返り値に置換、atomic→ordinary load/store、pthread/futex削除、
  shared memoryのunshared化、最大memoryへの固定化は却下する。

Dを試す順序は「標準toolの意味保存設定で済むか→限定された変換が本当に小さいか」。
現状では56行のrelaxed-madd patchを維持する方が小さく理解しやすい可能性も強い。

## 5. correctnessと再現性の採用ゲート

**変換成功、Go compile成功、SELECT 1のみでは採用しない。** 既存fixtureを起点に、
次の独立した失敗検出を維持する。今回は実行していない。

| invariant | 再利用する実物/fixture | 補足 |
| --- | --- | --- |
| import kinds/index、initial segments、limits/shared | `imported-memory.wat`、`defined-memory.wat`、`imported-memory-calls.wat`、upstream parser/memory fixtures | 新guestのimport/export inventoryを固定。削除したexportのDCE rootsを確認 |
| scalar/SIMD/atomic bounds、width、alignment、wrap、DCE、partial stores | `tests/generatedmemory/pure_memory32_test.go`、pure-memory32 patch内SSA/width/store-order tests、upstream `cg_memops`/trap tests | numeric trap testだけではmemory trapを検証しない。unused OOB loadと境界storeを独立に確認 |
| shared visibility、TLS/stack、growth、wait/notify | actual generated trap test、`threads.wat`/`thread-globals.wat`/`wasix-futex.wat`、upstream `cg_threads`/shared MemOpt | logical size公開前のzero/commit、lost wake/count/timeoutを維持 |
| root/worker trapと終了時failure | actual generated trap test、`TestWaitContract`、`TestPageCleanerOrdering`、`thread-exit.wat`、startup failure/Close | cooperative join contractを維持。即時全thread停止/一般race-cleanとは主張しない |
| host importのlogical memory window | `internal/generatedgo/code/base/host_memory_test.go` | reserved mmap tailへの書込みを拒否。guest側loadだけでは代替不可 |
| FMA/projection | `relaxed-madd.wat`＋`relaxed-madd-test.go.txt` | fused/unfused変更は仕様適合と既存数値期待値の両方をレビュー |
| real MariaDB/isolation/lifecycle | `tests/gointegration/owned_prepared_test.go`、wire/auth/session、両OS acceptance | Fresh、Fork-many、順序/並列、growth、commit/rollback、FD/mapping release |
| recipe/source/artifact identity | canonical input/source/translation/provenance、独立2build、installed consumers/Release guard | unqualified dev routeを検討に使う。以前のqualified SHAの証拠は新converter/guestへ読み替えない |

### 既存の限定性と追加確認候補

本家のscalar emitterには動的boundsを省く実装があり、Wasm validationをaddress安全性と
同一視している。mariamemのpure-memory32修正を省く判断材料にはならない。
[本家の実装](https://github.com/goccy/wasm2go/blob/730057c146463f663e8774587bc96fb2bea91af8/internal/codegen/emit_memops.go)

また、固定本家/forkと現行generated `MemoryFill`/`MemoryCopy`は、`n==0`でbounds検証前にreturnする。
仕様は長さ0でもlogical endより先のaddressを拒否する。この**既存の静的な仕様不一致**を確認した。
今回の移行による新規回帰ではなく、実guestのSQL影響も未実証。方式選択をもって完全なtrap適合が
証明されたとは扱わず、次のbounded correctness確認候補として記録する。
[bulk memory規則](https://webassembly.github.io/threads/core/exec/instructions.html#memory-fill)
追加fixtureではzero-length-at-endは成功、past-endはtrap、copyのsource/destination双方を区別する。
今回の範囲では修正・実行は行わない。

現行guestの非atomic sharedアクセスを含むGo race censusの既知限界も方式変更だけで解消しない。
既存保証の維持と完全なWasm/Go memory-model証明は別に扱う。

## 6. 次のHuman判断と実装順序の提案

提案する次の小spikeは **Bの最小port**：本家730057cを固定し、7パッチの目的を保持、
`memBound`/fixture依存だけを整理して移植する。optional pgmem layoutや未使用InitDataを
持ち込まない方針で、Fresh初期化・trap/thread/futex・owned growthを確認する。
ここで生成/実行同値性や保守費用が期待に合わなければAへ戻せる。

Dのmadd/metadata処理は、Bと同時に変更しない。新guestで具体的なinstruction障害が出て
標準設定が使える場合、または明確に小さい意味保存rewriteが示せる場合だけ別spikeとする。
Cは、Bのpatch seriesが実際に継続困難になるまでは作らない。
MariaDB安定版探索とこの移行を必ず同じ変更へ混ぜる必要はない。

この報告は差分管理方針の提案のみ。main/pins/guest/generated runtime/Release経路は不変。
未承認Wasmや新converterのqualificationを主張せず、実装は別Human Decisionに委ねる。
