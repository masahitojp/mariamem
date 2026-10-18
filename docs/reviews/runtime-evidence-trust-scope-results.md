# 検証証拠の再利用範囲 — 限定整理 / Human Review

## 今回の判断（提出時）

**推薦：計測器向けの再利用範囲拡張は今は実装せず、現行の判定を維持する。次回の公開は既存の一回実行手順を使う。**
直近の約91分の事前確認と約94分の公開は、計測器変更が理由で二重実行になったのではなかった。
途中の変更は版定数・文書だけで、既存のpath/version比較でも許容される種類だった。
公開まで一回で進める既存手順、または最終版番号を準備した同一SHAでverify→releaseする手順が、
この実例には少ない費用で直接効く。計測器を除外する新機構は、この二重実行の解決に必要ではない。

**最も強い反論：確認後に計測器だけを直した場合は、現行規則では古いruntime証拠を再利用できない。**
その場合のフルcheck/integrationは今回の公開でmacOS約24分、Ubuntu約16分を占め、無視できない。
ただし計測器は現行のqualificationのGo test/vet対象でもあり、その検証をどこへ移すかの設計が要る。
反復してその費用が発生した証拠は今回得ておらず、まず既存の再利用手順を使う方を推薦する。
将来、計測器だけの変更が実際に再利用を妨げる例が繰り返されたら、この依存表と拒否条件から再開できる。

今回求めるHuman判断は、この整理を受理し、再利用範囲拡張を保留すること。
公開の承認や版番号選択ではない。runtime/validator/workflow/既存oracleは変更していない。

## 範囲と成果の対応

[承認された計画](runtime-evidence-trust-scope-plan.md)の対象は `benchmarks/ubuntu-startup/` と専用workflow。
Humanの追加質問に従い、まず実際の長いCI二本の費用を照合した。
確認基点 source_commit `8abe93efe9698bfbe1d620aae6a1d7e995b8ede5`。

| 成果 | 結果 |
| --- | --- |
| 時間内訳と期待利得 | 過去2runのjob/step・候補commandログを照合。後述の実測区間と未計測の反実仮想を区別 |
| 依存経路 | runtime build、生成、qualification、source/package/license、guardの境界を下表に整理 |
| 再利用条件と拒否条件 | 現行36 negative例をsource-onlyで確認。追加が必要な例を別記 |
| 一つの推薦 | 現行維持。既存手順で二重実行を避ける。広い再設計や限定実装は未承認・未着手 |

依存整理と判断材料の作成は完了。将来の除外機構の実装・安全性検証が完了したという意味ではない。
上限2時間に達したことを完了理由にしていない。全リポジトリの依存グラフ・一般的な非影響証明は対象外。

## 1. 「長いCI二本」の実測

[事前verify 39006279807](https://github.com/masahitojp/mariamem/actions/runs/39006279807)
はsource_commit `a390b6e496b5fa1d272dc46a9aecffe6129fcec4`、
[release 39013386987](https://github.com/masahitojp/mariamem/actions/runs/39013386987)
は `47f297cc7498625e076abb93322eb616c9560bb8`。どちらも成功した完了済みrunを調べた。
新しいCIは起動していない。[metadata/timing](runtime-evidence-trust-scope-evidence/timing-summary.json)を保存する。

| 区間・job実経過 | 事前verify | release | 今回の計測器除外だけで省けるか |
| --- | ---: | ---: | --- |
| guest：独立Wasm build×2＋生成/ソース検証等 | 17.92分 | 17.42分 | 省けない。full modeではruntime再利用の有無と独立に実行 |
| candidate macOS：check/integration＋wheel作成等 | 46.38分 | 28.60分 | runtime再利用が成立すれば一部のみ省略可能 |
| candidate Ubuntu（macOSと並列） | 22.47分 | 21.83分 | 同上。二OSの時間を待ち時間として足さない |
| final-artifact verification macOS | 17.42分 | 16.77分 | runtime証拠の再利用では省略しない |
| final-artifact verification Ubuntu（並列） | 11.28分 | 10.95分 | 同上 |
| aggregate復元＋guard等 | 8.25分 | 7.90分 | 省略しない |
| publication復元/再検査＋publisher | ― | 17.58分 | 今回の対象外 |
| public smoke最長job | ― | 4.70分 | 今回の対象外 |
| **最初のjob開始→最後の成功job終了** | **90.92分** | **94.02分** | どちらもqueue/開始前のHuman待ちを含まない |

jobの直列依存・起動間隔もあるため行の単純和は全体に一致しない。
この二本の観測CI時間は計約185分。次の一回のreleaseが必ず94分になるという予測ではない。
同じcheck/integrationでもrun間で大きく変動しており、runner性能やcacheの寄与は今回未分離。

candidate step名は「Build generated-Go host-only wheel」だが、中ではtest/vet/raceも実行している。
ログの**実際の `+ command` 行**から次のcommand開始までを計算した。shellが表示したif文の両分岐は実行証拠にしない。

| candidate内の主要区間 | verify macOS | release macOS | verify Ubuntu | release Ubuntu |
| --- | ---: | ---: | ---: | ---: |
| go test ./...（compile等込み） | 9.29分 | 5.44分 | 4.19分 | 4.07分 |
| go vet ./... | 3.82分 | 1.98分 | 1.51分 | 1.51分 |
| handwritten/runtime race set（compile等込み） | 21.89分 | 14.10分 | 8.85分 | 8.47分 |
| check開始→最後のSnapshot command開始 | 37.71分 | 23.56分 | 16.62分 | 16.14分 |

最後の行はcheck/integrationのほぼ全窓だが、最後のSnapshot commandの完了時刻までは含まない。
command間のwrapper/出力等を含む近似区間で、test本体だけのCPU時間ではない。
これは再利用で回避する**候補費用**であり、約24分丸ごとの短縮実証ではない。
再利用時も証拠認証とrelease_preparation_checksが必要で、cold wheel buildの費用も変わり得る。

## 2. なぜ二本ともfullだったか

二run間の変更は9fileで、Go/runtime/guest/生成/toolchain/qualification codeは同一。
版は事前verify時の0.5.1からrelease時の0.5.2へ変わり、README、Go/Python/releasing guide、
status、製品化報告/JSON、NOTESが変わった。
[実差分を現行比較関数へ渡した結果](runtime-evidence-trust-scope-evidence/version-transition.json)はPASS。
**ただし比較関数PASSは証拠全体の認証PASSではない。**

二つの再利用機構を区別する必要がある。

| 仕組み | 要件 | この二本では |
| --- | --- | --- |
| READYと最終成果物の再利用 | `scripts/release_plan.py:ready_bundle/plan` が同一source_commit・版・認証済みartifactを要求 | SHAも版も異なり再利用対象外 |
| runtime-only証拠の再利用 | `scripts/runtime_validation.py:read_intent/fetch_qualification/evidence/validate` が専用workflow、contract、両OS、hash、inventory、許容差分を確認 | 両sourceに `release/runtime-validation.json` がなく、事前runも専用runtime workflowではない |

事前runのworkflowは `.github/workflows/release-candidate-ready.yml`。
runtime-only再利用が要求するのは `.github/workflows/v044-product-validation.yml` の
`runtime-qualification-v1` 証拠である。同じテストに見えてもrun IDを流用しただけでは受理されない。
現在の契約を守った結果であり、直ちにverifierの欠陥とするものではない。

**既存手順で避ける方法：** Humanが版とcandidateの公開を承認したら `operation=release` を一回提出し、
必要なfull検証→READY→公開を同じtransactionで行う。事前verifyは必須ではない。
公開前に結果を見たい場合は、最終版の準備を先に済ませてverifyし、その後sourceを変えずにreleaseする。
その場合でもautoが既存READYを発見・再認証できることが必要で、artifact期限切れ/取得不能なら再利用できない。
公開時の復元・再guard・publisher・public smokeは残る。二本目をゼロ秒にできるわけではない。

## 3. 固定対象の依存経路

「入力台帳に含む」「検査でcompile/testする」「DBに組み込まれる」を分けて追った。
対象名のscripts/tests/cmd/internal/python内参照とGo importを検索し、下記ownerを実コードから確認した。
これは固定sourceでの結論で、未来の全変更まで非影響とする規則ではない。

| 境界 | 参照/実行するowner | 固定対象との関係 |
| --- | --- | --- |
| DB/hostのbuild | `scripts/build_alpha.py` → `go build ./cmd/mariamem-host` → root/internal | 対象Goはpackage main。DB側から対象packageへのimport参照はなし。対象からDBを呼ぶ一方向の計測器 |
| guestのbuild/生成 | `scripts/build_generated_guest.py`、`scripts/regenerate_release_guest.py` | 対象directoryは読まない。ただし別の `benchmarks/spikes/...` は正式recipeに使う。benchmarks全体の除外は不可 |
| qualificationのcheck | `scripts/verify.py:check` → `go test ./...`、`go vet ./...` | **対象Go packageもcompile/test/vetする**。対象scheduler testも含むため単なる未使用fileではない |
| qualificationのintegration | `scripts/verify.py:integration` の明示package/test/host build | 対象directoryの直接参照はなし。対象名以外の共有script/runtimeが変われば再評価が要る |
| 専用計測 | `.github/workflows/ubuntu-parallel-startup.yml` → campaign/reduce/test_tools、Go binary | 対象Pythonを実行する直接owner。qualificationのpytest testsはこのdirectoryのpytestを自動収集しない |
| 公開source・対応source archive | `check_public.py:public_files/check`、`generated_release.py:source_inventory/package_source` | benchmark/workflowもinventory・対応sourceへ含める。内容/権利/credential/path検査は省略できない |
| wheel/ライセンス | `build_alpha.py` → host/manifest、distribution_licenses、Python package | 計測器をwheelのruntimeに入れる経路は見つからない。source inventoryは計測器を含む。依存/license変更を単なる計測器修正とみなさない |
| 外部Go consumer | `consumer_module.py:source_files/prepare_proxy` | root/internalの非test Go/asmとgo.mod等を選ぶ。対象benchmarkはmodule fixtureに含めない |
| 最終guard/再利用 | `generated_release.py:guard/check_aggregate`、`runtime_validation.py:validate` | 全source identity、許容差分、guest、成果物証拠を確認する。DBへのimportがなくてもここで変更を検出する |

名前の直接参照は専用workflowだけだったが、globで読むGo test/vet・source archiveの経路も存在する。
したがって文字列検索ゼロを「依存なし」の証明に使っていない。
`go test` のpackage集合は追加/削除されるので、既存full checkの証拠を新packageの検証済みとして扱えない。
動的に共有helper化した未来の依存まで証明したものでもない。

## 4. 将来、限定対応するときの保証の分離

runtime-onlyの再利用と変更した計測器自身の検証は別にする必要がある。

| 証拠 | 仮に計測器のruntime非影響を認めても必要な扱い |
| --- | --- |
| DBの挙動/既存runtime境界 | guest/toolchain/Go依存/runtime/検証ownerが同一という条件つきでのみ再利用候補 |
| 変更したbenchmark package/test/vet | 新sourceで実行する。古いfull checkの成功を新しい計測器へ転記しない |
| qualification workflow/harnessの変更 | 自動同等扱いしない。どのoracleをどこへ移すかを再設計し、必要なら新contract/basisを作る |
| source/license/配布物 | 新sourceの完全inventoryと公開検査、必要な対応source/notice検証を継続 |
| 新wheel/moduleの動作 | そのexact成果物のacceptanceとguardを継続。benchmark成功で代用しない |

最小候補でも、単なるdirectory例外ではなく、対象file集合、Go package集合の変化、mode/type、
共有helper導入の検知、計測器の新しい検証receipt、既存runtime証拠との結合が必要。
既存guardの失敗を見かけ上消すための例外追加は推薦しない。

## 5. 拒否側の条件と検出網

[negative-matrix.json](runtime-evidence-trust-scope-evidence/negative-matrix.json)では現行
`compare_inventory` に12種類×変更/追加/削除の36例を渡し、すべてREJECTを確認した。
本番証拠のダウンロード認証や新方式の安全性を検査したものではない。

| 変更 | 現行の検知 | 限定対応を作るなら追加で必要な検知 |
| --- | --- | --- |
| runtime/guest/Go依存/recipe/qualification workflow/verify.py | inventory/treeの例外外として拒否。現行testsにも該当negative例あり | 例外化せず既存拒否を維持 |
| 計測器の変更/追加/削除 | 現在はすべて拒否（今回36例の一部） | 新fileを自動例外にしない。package/test集合、実行owner、内容を新検証へ束縛 |
| benchmarkの共有helper化 | 対象外script/runtimeの変更は拒否 | 既存許容fileからの動的読込等も含む。単なるpath許可だけでは未検出になり得る |
| 未知file | 拒否。`test_unreviewed_source_changes_rejected` | fail-closedを維持 |
| rename | 旧path削除/新path追加で現在は拒否 | 許容directory内移動も自動承認しない。新しいowner確認が必要 |
| mode/type、symlink | `validate` のtree mode/type検査、public_files、既存Git変更negative tests | inventory内容hashだけの判定に縮めない |
| 実行可能なdocs/consumer/recipe | `test_runtime_reuse_does_not_exempt_recipes_consumers_or_executable_docs` | docs/benchmarks全体の例外でoracleを失わない |
| 証拠取り違え、異なるguest/OS/toolchain/command、期限切れ | fetch_qualification/evidenceと既存test_runtime_validation | 変更せず維持。今回36例の簡易実行ではこの認証層を再実行していない |

既存の36例はPASS。mode/rename/証拠認証の全pytest suiteは今回再実行しておらず、test ownerの存在をコード確認した。
新方式が上記の追加条件を捕まえるという証拠はまだない。新実装をしていないため、それ自体は今回の未達ではない。

## 6. 選択肢と費用対効果

| 選択肢 | 利益 | 必要な作業/費用 | 判断 |
| --- | --- | --- | --- |
| **現行判定を維持＋既存の一回release/同一SHA再利用** | この実例の二重full実行を避ける方向に直接効く | 新validator不要。先行verifyするなら版を先に決め、確認後のsourceを固定する。実際の公開には別承認が必要 | **推薦** |
| 計測器だけ限定対応 | typed runtime証拠を得た後、計測器だけ直す場合のcheck/integration再実行を減らす余地 | 上記の新しい依存/検証receipt/negative tests/両OSでの確認が必要。今回の二重実行には不要で、今の費用対効果の優先度は低い | 保留 |
| 広いdependency-subset再設計 | helper/tooling変更も対象にできる可能性 | 動的依存、生成、検証harness、license/source、artifactを横断する設計・migrationが必要。今回の限定調査では全体工数を見積もっていない | 今回は進めない |

既存二runの時間差を実装利得の実測として提示しない。限定対応/広い再設計の実装工数は未確定で、
安いという前提で採用していない。復元やpublicationの費用は大きいが、原因分解や最適化へ今回は範囲を広げない。

## 保存・検証・残るもの

- [files.json](runtime-evidence-trust-scope-evidence/files.json)：run metadata、時刻、log抜粋/原本hash、
  command間区間、version差分、negative結果。runner pathは置換、ANSI除去。原本/保存後hashを区別。
- 保存JSONの時刻差分、36拒否、source差分、文書リンク、公開ソース境界とdiffを検査しPASS。
  実際のsource inventory/暗号認証が新方式で通るか、性能が改善するかは未実装・未計測。
- runtime、生成Go、guest、CI、release台帳は未変更。DB build/再計測/Qualification/公開は行っていない。
- 一時取得分を削除し、約115KBのテキスト証拠とその索引を保存する。今回追加の大きなcache・worktreeはない。
- 今回はHuman受理待ち。受理されるまで、既存の「信頼スコープ再設計」残件を無断でクローズしない。

## Human決定（2026-10-18）

Humanが限定整理の結果と推薦を受理した。再利用範囲の拡張は保留し、現行判定を維持する。
次回の公開は別途承認を得たうえで、既存の一回releaseを使う。
事前verifyが必要なら最終版番号まで準備し、確認後にsourceを変えず同一SHAでreleaseする。
今回の承認は公開そのものや版番号の選択ではない。

限定整理はクローズ。広い再設計を実装済みとはしない。
計測器だけの変更が繰り返し再利用を妨げる実例が得られた場合、この依存表と拒否条件から再検討する。
資料のmain統合も別判断のままとする。
