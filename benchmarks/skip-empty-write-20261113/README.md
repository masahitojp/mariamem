# 混在iovecの空Write省略 — 有限試作、2026-11-13

## 結論と推奨

**空Writeの除去には成功。全体時間は固定5組すべて短縮したが、総CPUは4/5組で増加した。** 小さなlatency改善候補として保存し、現時点の即時main採用は勧めない。wallのペア改善中央値は1.63%、総CPUのペア増加中央値は1.68%。CPUも削減する改善という当初の期待は確認できなかった。

採用側の最も強い根拠は、約5,800回の空Writeを取り除き、全5組でwallが短く、WASI/transport/70 SQL assertionsを維持できたこと。最も強い反対材料は、改善量が小さい共有host上の5組で、user CPU増加がsystem CPU削減を上回ったこと。5組から原因や普遍的な性能を確定しない。追加反復で都合のよい結果へ更新せず、ここで有限試作を完了する。速度優先でCPU増加を許容するかは別のHuman判断。

## 試作の範囲と互換性

`code/base/base.go:writeVec`はiovecごとにWriter.Writeを呼び、空iovecもOSへ渡していた。試作は「非空のiovecを含む列」の空要素だけを省く。全要素が空の列は元の呼出しをそのまま維持する。閉じたWriterに対するall-empty呼出しのエラーを成功へ変えないための限定である。無効FD/メモリの検証はFd_write/Fd_write64の元の順序で先に行う。

同一binaryで、package初期化時に読む `MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE` でbaseline/candidateを選択するGo overlay。baseline=false、candidate=true。正式なgenerated source、guest C/WASM、SQL設定、公開API、transport、cleanup保証は変更しない。正式導入時には実験用環境分岐を持ち込まない。mixed/all-emptyの選別走査自体も今回のcandidate費用に含む。

任意のio.Writerが空Writeに持たせる副作用すべてを保存する変更ではない。検証したのはWASI返却値/FD・memory検証、代表的なerror/partial-writeと実os.File/pipe経路であり、全Writerの一般的な同値性を主張しない。

## correctness・境界確認

基準source_commit `0f5b26f370875d26bd337031f48856d8f57c10db` はbuild前にgit_identity.pyでcommit確認。通常設定のハーネスは `d6ddbc7b0ddb0c2dc31ec4b8c8ed8478e0b4b694`、DSNのinterpolateParams=trueを継承・assertする。同じ70 tests、parallel8、1,000 users/500 products/40 sample orders、明示prepared sample投入は固定。

両armで `go test -overlay ... -count=1 ./internal/generatedgo/code/base ./internal/guest` PASS。追加した名前付きテストも両armで再確認:

- leading/middle/trailingの空要素を含むmixed vectorsで出力abcd、返却4bytes。candidateでは空Writer呼出0。
- 最初のエラー、途中のエラー、short write、進捗の返却。
- all-emptyの成功とsentinel error・既存呼出し回数。
- wasm32/64 fd_writeのmixed vectors、無効FDのEBADF、iovec memory境界のEFAULT、closed os.Fileへのall-empty失敗。
- 既存のbroken pipe・partial/error mapping、内部framing/transport/cancel/終了のguest package tests。

unit-*.txtとfocused-details-*.txtに保存。最初の追加wasm64テストはFD引数int32/int64の型違いでcompile FAIL、修正後再実行。元のFAILはinitial-compile-*へ保持し、製品実行失敗やPASSに読み替えない。

## 速度とCPU

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0/GOMAXPROCS8/GOGC100。通常計測ではIPC observerを無効にする。warmup各1＋実行順を交互にした5pair。process起動前〜終了のwall、child processのgetrusage user/system CPUを記録する。CPUは全Go threadを含むuser+system合計で、特定SQL/工程のCPUではない。

|process中央値|baseline|candidate|
|---|---:|---:|
|wall ms|475.343|456.479|
|user CPU ms|2031.780|2099.048|
|system CPU ms|345.585|332.139|
|total CPU ms|2377.365|2424.620|

独立な中央値差よりペアの判定を優先する:

|pair|wall変化|total CPU変化|
|---|---:|---:|
|0|−0.43%|+4.51%|
|1|−2.09%|+1.68%|
|2|−1.63%|+3.45%|
|3|−1.13%|−1.53%|
|4|−6.77%|+1.64%|
|ペア中央値|**−1.63%**|**+1.68%**|

wallのペア差中央値は約−7.77ms。system CPUのペア中央値は−3.51%だがuser CPUは+3.67%。追加走査、syscall削減による実行/スケジューリング変化、共有hostの揺らぎを分離しておらず、CPU増加の理由は未特定。RSSは未計測、他platformの実測も無い。

フルtree走査による計測妨害を避け、workspace/free-space guardは各processの前後だけに実行する。timed processは130秒timeout、期待するtrace/test出力はsub-MiB。ビルド/ガード走査はtimingとgetrusage差分の外。前回比較とguard/cohortが異なるため、前回の477ms等をこの候補効果へ合成しない。

## 機構の計数

同じbinaryでobserverを有効にした別枠の3pair。各process22 DB、合計132 DBのguest execution+workersがjoined成功。各DBで両端のbyte/frame数を照合。全70 tests成功。観測の時間を通常計測へ混ぜない。

|1スイートの範囲|baseline|candidate|
|---|---:|---:|
|guest Write呼出|11,590–11,604|5,824–5,859|
|0byte Write|5,766–5,773|**0**|
|応答frame|5,795–5,802|5,795–5,830|
|応答bytes|1,587,141–1,588,422|1,587,145–1,593,560|

応答frame当たりWriteは2.000→約1.005。sampleは不変だがdatabase/sqlのpool接続生成数が変動するので、arm間の総frame/bytesの完全一致は要求しない。各DBの同じ通信の両端で一致することとSQL値/独立性を確認する。all-emptyを維持しても、今回観測された空Writeは全てmixed vectors内だったので0にできた。

全18 process・1260 leaf tests成功（warmup140＋primary700＋counts420）。固定回数を完了し、結果の除外・追加性能repeatなし。通常の選別テスト詳細確認は性能repeatに含めない。

## 正式導入へ進む場合の条件

この試作は製品candidateではない。`scripts/runtime_write.py` がwriteVecとwasm32/64 errno/progress修正のcanonical postprocessorであることをsource照合した。正式化するならそこへ最小差分とfocused testsを移し、preimage rejection・正規再生成・supported両OSのFD/SQL/framing/disposalを同じcandidateで検証する。generated base.goだけを直接修正して採用しない。guest C/WASM再buildはこのhelper変更自体の依存ではない。作業見積りはsource整理/検査30〜60分＋Go再生成/両OS CI1回（実時間はhost cache条件次第）。現時点で実行承認やrelease gateへ追加しない。

#66の外部TCP省略、#65のprepared出力再利用、#119非同期cleanup、#162 Close tail、#143の保留UPDATEをこの試作へ混ぜない。資源設定の増量も行わない。全体IPC方式の変更より小さな候補として結果を保存する。

## 保存・再現

plan.json / inputs.json / overlay.json、base helper差分・仮想追加test・IPC observer、harness、unit結果、全process/trace/IPC counter、summaryを保存。analyze.pyは1260 assertionsと固定5pair、132 joined DB、両端byte/frame、空Write抑制を保存データだけで再検算する。

新しいmanaged workspaceのworktreeを製品pinへ合わせ、temp/mariaへharnessを置く。harness go.modの../../worktreeを維持する。prepare.pyは元harnessとobserver、base helper overlayを再生成する。仮想追加testをtemp/experiment_empty_write_test.goへ置き、overlay.jsonの絶対パスを作り直す。build.pyで両armのfocused packagesと同じtest binaryをbuild。measure.pyが前後guard・130秒timeout下で固定5pair/3counter pairを実行する。10GiB/空き12GiB、build1800秒。新cohortとして保持する。main統合、正式生成、CI/releaseは未実施。

補足: original modelcase fixtureのprimary Close呼出しは返却errorを個別assertしない。counter別枠は全132DBのguest joined/exit errorを確認し、FD/transportのfailureはfocused testsで検証した。正式candidate受入れでは全経路の公開Close error/残件oracleも維持する。3つの破損証拠対照（空Write残存/DB欠落/bytes不一致）をすべて拒否した。
