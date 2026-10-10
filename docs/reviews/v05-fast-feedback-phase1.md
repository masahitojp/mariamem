# v0.5.x Fast Feedback — Phase 1

## Human Review

**①②は実装済み。③は設計のみ。mainへの統合は未実施。**
工程の計測と同一作業内のGo cache利用を、既存の呼び出しに追加した。
新しいビルド経路・Release保証の省略は導入していない。

| 評価項目 | Before | After | 結論 |
| --- | ---: | ---: | --- |
| 実host cold command、各1回 | 126.70 s | 127.44 s | 高速化は確認できない |
| 実host warm command、各3回の中央値 | 0.292 s | 0.297 s | 差は小さく、高速化を主張しない |
| 上記warm操作全体、中央値 | 0.292 s | 0.400 s | ON時のidentity/hash記録に費用あり |
| 同一wheel条件のGo stage、初回→再build | 131.56 s | 0.365 s | 同一variantで既存Go cacheが機能 |
| 小fixture、cold→warm中央値 | 4.807 s | 0.096 s | compile 60→0。Go標準cacheの確認 |

計測ONには、空Pythonコマンドで中央値約33 ms、実hostのidentity・約100 MBの
output hashを含む記録で約0.10–0.13 sの追加費用がある。OFFが通常動作。
目的は新しいcompiler最適化ではなく、互換性のあるcacheを同一作業で揃え、
重い工程の費用・入力・結果を追跡できること。

- **正しさ:** focused suiteの279ケースがPASS。うち1ケースはsandboxが
  process-group/psを拒否したため、そのケースだけ権限付きで再実行してPASS。
  stream、exit、timeout、signal、fallback、cache境界と既存source/license/guardを確認。
- **対象環境:** macOS arm64 / CPython 3.14.8、Linux arm64 container / CPython 3.12.3
  で観測helperを実行。native Ubuntu x86_64の新規runtime qualificationとは扱わない。
- **Release:** workflow、accepted pins、runtime/generated source、guardは変更なし。
  dev contract・1-build receipt・wrong guest hashは既存guardが拒否した。
- **実物のidentity拒否:** clean worktreeの`build_alpha.py --ci-candidate`は
  embedded VCS SHAが親mainを指す既存Go scanner制約により包装前に拒否した。
  source SHAの代入やguard緩和はしない。この開発測定をRelease証拠にはしない。
- **次のHuman判断:** ①②を統合するか。別途、[③の設計](v05-dev-guest-build-design.md)
  に基づく隔離された未承認guest経路の実装を承認するか。今回は③を実装していない。

## Identity / scope

- 起点main: `b1666e4a6f4b3b77269b294de0fe225031ad12ce`。
- 公開v0.4.6 tag object: `09d7b82e1900318dde45d08bebd9328ea35e6ef7`。
- 公開source: `b56be17206b6beef18f55c8ea39b254638da8590`。
- 作業branch: `experiment/v05-fast-feedback-phase1`。
- 測定した実装: `928506d62030587e75efd6284553b2fadf54b20e`、tracked diffなし。
- 後続`5eb0a936587a7e9086a683461aaac2d1403bbaea`はresource拒否/fallbackと
  diagnostic serializationの失敗処理のみを修正。正常時の測定経路を変えていない。
  `58abd6973ca4199ab1fd59cb9fdeb70e61be2c88`は再生成呼出しの引用符を修正し、
  重い処理を伴わない5入口の`--help`回帰を追加。再生成を実行する前の構文確認で発見した。
  最終report commitはこれらに文書・compact evidenceを追加する。
- 新規両OS runtime qualification、guest build、translationの再実行はない。
  最終branch SHAへの過去runtime qualificationの読み替えは行わない。

## 実際の変更

| ファイル | 責務 |
| --- | --- |
| `scripts/build_feedback.py` | opt-in subprocess観測、active workspaceのGo env設定 |
| `scripts/verify.py` | 既存source/check/test command境界を観測し同一envへ揃える |
| `scripts/build_alpha.py` | 既存Go host buildとwheel包装を観測、task cacheを利用 |
| `scripts/build_generated_guest.py` | 既存SDK/source/compile-link/postoptの観測。2-build/accepted hash条件は維持 |
| `scripts/regenerate_release_guest.py` | 既存translation/fixture/adapter/install工程の観測とtask env |
| `benchmarks/spikes/generated-go-integration/translate_guest.py` | converter build/translationの観測とtask env。translator自体は不変 |
| `tests/test_build_feedback.py` | subprocess・cache・Release拒否のfocused回帰 |
| `docs/development.md` | opt-in利用方法、Fast/Focused/Full、cleanup |
| 本report・evidence、dev guest設計 | 結果・再現条件・③の未承認設計 |
| `v05-fast-feedback-assessment.md` | 承認済み調査6a62fc1の保存。新規再調査ではない |

## ① 観測できる境界

| 工程 | 記録する単位 | input/outputの例 |
| --- | --- | --- |
| guest | SDK install、LLVM prepare、各trial source prepare、compile/link、Wasm postopt | pins/recipe/source record、linked/Wasm hash |
| wasm2go | converter build、translation | converter archive、Wasm、binary、代表generated files |
| regeneration | translation、memory32 fixture、source adaptation、installation | accepted guest/input manifest、生成proof |
| Go compilation | verifyの既存Go build、wheel host build | source commit/diff、pins/provenance、host hash |
| source/provenance | verifyの既存Python command境界 | source commit/diff、入力manifest |
| focused tests | verify runnerからGo/Python commandを呼ぶ | argv/exit/source、actual Go version |
| wheel | existing pip wheel | native manifest、wheel hash |

新たに各engine内部を分割しない。compile/link、source-only adapter内部などは
既存command単位。directory全体のhashを毎回追加せず、explicit filesとsource/diffを
記録する。完全な生成file inventoryは既存provenance検証の責務であり、telemetryは
その代替ではない。重なったparent/child phaseの時間・CPUを足してはいけない。

各recordはJSONL: phase/argv/cwd/source/diff、Go環境・実compiler version、
explicit input/output SHA256とbyte数、wall、user/system CPU、Peak RSS、exit/exception。
CPU/RSSは`wait4`の待ったchildのrusage。子孫の寄与はOS依存で、同時process-treeの
RSS合計ではない。Darwinはbyte、LinuxはKiBをbyteへ換算。取得不能はnull/Unavailable。
Python orchestrationのtool/versionは明示情報とPython versionで記録する。

OFFは標準`subprocess.run`へ直行し追加probes/hashなし。ONは標準のpipe/communicate/
waitを使い、commandを二重実行しない。diagnostic書込み失敗で本来のexitを変えない。
macOS/Linux CPythonの2つのprivate Popen wait hooksを局所利用するため、Python更新時に
このfocused suiteを実行する保守責務は残る。他実装・wait4取得不能は通常runにfallback。
この制約を解消する別wrapper process/managerは追加しない。

## ② cacheの範囲と実測

active owned workspaceの`temp/gocache`、`temp/modcache`、`temp/gopath`に揃える。
他checkout、completed receipt、symlink cache、矛盾する既存envは拒否。
`GOTOOLCHAIN`の既定は従来の1.26.8、実compilerを記録。最低サポート1.26.0は不変。
直接Goを呼ぶ場合も[同じenvを明示](../development.md#optional-development-observations-and-task-local-go-cache)。
Go自身がversion/platform/flags/sourceをkey化する。新しいcache invalidation機構はない。
外部guest/provenanceの正しさはGo cacheでは確認できない。

小moduleの実際のbinary出力を検査してcache hit/missを確認した:

| 入力変化 | wall s | compile command数 |
| --- | ---: | ---: |
| Go 1.26.8 cold | 4.807 | 60 |
| 同一入力3回、中央値 | 0.096 | 0 |
| host Go変更 | 0.173 | 1 |
| shim変更（generated依存の代用） | 0.190 | 2 |
| Go 1.27.1へ切替 | 4.506 | 58 |
| 1.27.1 warm | 0.096 | 0 |
| 1.26.8へ戻す | 0.164 | 0 |
| workspace/trace OFFの標準pathへ戻す | 0.101 | 0 |

変更後の出力constantとruntime.Version、artifact hashを確認。
Go 1.27.1を使ったfixture検証は既定toolchainやサポートversionの変更ではない。

実host cold CPU(user/system)はBefore190.20/6.45 s、After193.44/6.24 s、
Peak RSSは2.418/2.400 GB（decimal、process high-water）。各1回なので優劣は言えない。
同じoutput pathのBefore binaryが残ったAfter coldではmain packageが既存出力判定で
省かれ、compile数138/137。OS page cacheをflushしたcoldではない。module downloadは
別途初期化済みの条件も含む。どちらもbinary SHAは同じだった。

wheelはCGO=0/trimpathなので、通常host(CGO=1/trimpathなし)のcacheがあっても
初回の互換でないvariantをcompileする。全wheel操作136.20→4.85 s、Go131.56→0.365 s、
包装3.76→3.80 s。再buildのcompile数0を`-x`で確認した。初回wheelは`-x`なしなので
compile数はUnavailable。これらは既存Go cacheの効果で、guest build高速化の証拠ではない。
キャッシュ共有が全variantの初回buildを省くとも主張しない。

## 検証とReleaseの境界

Focused 279ケース: observer、development scope、generated release、runtime validation、
guest reproducibility tooling、CI publication definition、generated inventory、distribution
licenses/mirrors、git identity、experiment workspace。sandbox制約の1ケースのみ再実行。
Linux helper probeはstdout/stderr、nonzero、SIGTERM、timeout partial output、CPU/RSSを確認。
Linux arm64 containerでありUbuntu x86_64のnative correctnessを代替しない。

既存`build_generated_guest.py --repetitions 1`がdownload前に拒否すること、実際の
`generated_release.verify_build`が未承認contract・1-build・wrong hashを拒否することを
負例で確認した。`build_alpha.py --ci-candidate`もembedded source不一致を実際に拒否。
Release tooling、CI、pins、生成source、license義務は変更しない。選択した検証の順序と
command自体も維持。Fast/FocusedでFullが完了したと扱う機能はない。

③の設計は**source/recipeを承認してから独立clean Release buildsで昇格**する。
dev receiptをreleaseと名付け直す昇格はない。旧generated/source-hostの取り違え対策、
namespace隔離、installerがcanonical pinsを読む現状の制約は設計書に残した。
実装承認までは単発guest経路を作らず、MariaDB更新も開始しない。

## Evidence / reproduction

詳細JSON: [host cold](v05-fast-feedback-phase1-evidence/host-comparison.json)、
[warm paired](v05-fast-feedback-phase1-evidence/host-warm-paired.json)、
[cache invalidation](v05-fast-feedback-phase1-evidence/cache-validation.json)、
[wheel phase](v05-fast-feedback-phase1-evidence/wheel-phases.json)、
[observer overhead](v05-fast-feedback-phase1-evidence/observer-overhead.json)、
[Linux probe](v05-fast-feedback-phase1-evidence/linux-observer-probe.json)、
[hardware](v05-fast-feedback-phase1-evidence/hardware.json)、
[verification/input SHA](v05-fast-feedback-phase1-evidence/verification.json)。
JSON中`$SOURCE`=作業checkout、`$WORK`=owned workspace、`$GO126/$GO127`=実Go binary。
実測はApple M1/8 logical cores/16 GiB/macOS27.0.1 arm64、Go1.26.8、Python3.14.8。
venvはpytest8.4.2、PyMySQL1.2.3、setuptools80.9.0、wheel0.45.1。
全measurementを直列、GOMAXPROCS=2、Go-p1で実施。cold各1回、warm各3回、
空commandは20回のON/OFF交互paired。raw logはSHAを保存し、再現可能なbuild/logは削除。

既存workspaceをprepareし、development.mdのenvを設定する。
既定cacheのBeforeは別の空`temp/baseline-gocache`、Afterはtask`temp/gocache`を指定する。
Beforeはtrace/workspace envを外し同じargvを標準subprocessで実行する。CPU/RSS比較は
同じwait4観測adapterのみを使用し、Git/tool/hash metadataを含めない。
Afterは既存helperを呼び、command wallと操作全体を別々に記録する。
各warmは同じcache/output/flagsで3回、`go -x`のcompile command数を比較する。

```sh
# Toolchain binaryは各環境で実際の1.26.8を選ぶ。download時間は別に記録。
export GOMAXPROCS=2 GOENV=off GOWORK=off GOFLAGS='' GOEXPERIMENT=''
export CGO_ENABLED=1
PYTHONPATH=scripts python3 -c 'from verify import run; run(["go", "build", "-x", "-p", "1", "-o", "build/feedback-host", "./cmd/mariamem-host"])'
# wheelのGo flagsは変更せず、既存pathを実行
python3 scripts/build_alpha.py --go /absolute/path/to/go1.26.8/bin/go
```

cold比較には新しい個別cache pathを使い、使用中cacheを消さない。
小fixtureは次の3ファイルをtask tempに作る。host0→host1、shim0→shim1の順で
1ヶ所ずつ変更し同じ`go build -x -p 1 -o ... .`とbinary出力を確認する。
次に1.27.1で同じcacheを使い、1.26.8へ戻す。production生成sourceは編集しない。

```go
// go.mod: module example.com/cache-fixture ; go 1.26.0（実ファイルでは各行）
// main.go
package main
import("fmt";"runtime";"example.com/cache-fixture/shim")
func main(){fmt.Println("host0:"+shim.Value()+":"+runtime.Version())}
// shim/shim.go（別ファイル）
package shim
func Value() string {return "shim0"}
```

focused再現command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
 tests/test_build_feedback.py tests/test_development_scope.py \
 tests/test_generated_release.py tests/test_runtime_validation.py \
 tests/test_guest_repro_tools.py tests/test_ci_publication_workflow.py \
 tests/test_generated_runtime_inventory.py tests/test_distribution_licenses.py \
 tests/test_packaging_license_mirrors.py tests/test_git_identity.py \
 tests/test_experiment_workspace.py
```

owned temporary binary/wheel、cache、venv、fixture、source copy、worktreeは作業終了時削除。
保持するものはbranchの実装・本report・JSON・input/output hashes。main/他作業/tag/assetsは
触らない。統合/Release判断はHuman Review後。

---

## Bounded implementation plan

Human approved assessment candidates 1/2; candidate 3 is design only.
Baseline main: `b1666e4a6f4b3b77269b294de0fe225031ad12ce`.
Released v0.4.6 source: `b56be17206b6beef18f55c8ea39b254638da8590`.
Branch: `experiment/v05-fast-feedback-phase1`.
The [approved assessment](v05-fast-feedback-assessment.md) is retained as input.

1. Add a small shared opt-in subprocess observation helper to the existing
   verification, guest-build, regeneration and host-wheel build call sites.
   Keep command order, streams, exit/timeout behavior and qualification gates.
   JSONL is diagnostic data, never release qualification evidence.
2. Use an explicit active experiment workspace to assign task-local Go cache
   paths through existing callers. Reject conflicting/other-task paths. Default
   execution without that opt-in stays unchanged. Go owns cache invalidation.
3. Focused tests cover process success/failure/timeout/signals, observer-off
   equivalence, resource units/unavailability, caller environment consistency,
   current source oracles and unchanged release rejection gates.
4. Sequential bounded measurements compare uninstrumented/instrumented cold and
   warm host builds; a small compiled fixture proves host/shim/toolchain cache
   invalidation without altering production generated files. Preserve hashes,
   actual compiler, flags, trials and uncertainty. Build the wheel through its
   existing path; do not rerun platform runtime acceptance for tooling changes.
5. Describe the dev-only guest lifecycle and promotion/contamination controls in
   [design review](v05-dev-guest-build-design.md). No dev flag or guard changes.
6. Commit/push reports and implementation; remove task caches/builds/worktree.
   Main, v0.4.6 tag/assets, runtime/converter/guest inputs and CI stay unchanged.
