# macOS OS確認結果の再利用：実装・検証

## Human Review

**推薦：今回の成功キャッシュ修正をmainへ採用する。**
両native OSのfocused CIとmacOSの限定性能結果が採用条件を満たした。今回Humanに求める判断はmain採用・統合であり、公開ではない。
後続Forkと4子の実経過時間に利益があり、起動失敗・キャンセル・並列子・SQL・隔離・終了の既存oracleを維持した。
Humanはmain採用・統合を承認済み。公開は別判断。[承認した設計](macos-platform-cache-design.md)に対する結果を記録する。

**最も強い留保：少数試行であり、Python初回起動の1秒級上振れ、Python並列の1対の全体悪化、
並列Closeの小幅増加が残る。**
これらを削らず保存する。今回の利益は成功した環境確認の反復削減で、初回host起動や全区間の改善保証ではない。
有限な同一入力比較では後続Fork・4子区間の各群中央値が改善したため候補は維持するが、
両OSの機能回帰は通過したが、CI PASSを性能の普遍保証にはしない。
Ubuntu並列起動の原因調査と0.7.xのguest改善候補選定は別範囲。

## 入力と実装

- 基点 source_commit: `a43960b110a739a3c87b4a25757bb0f106464041`。最新mainへrebaseし、macOS先行を維持。
- 測定候補 source_commit: `160b272e1ce217f1ef2b7d9da19a2ad643927297`。
- 対照 source_commit: `6bdcd0e4fa9f29ef46fbae7e414ae965d5483b37`。
  候補から `internal/artifacts` だけを基点の実装へ戻した計測用commit。
  対照と候補の差分は同packageの実装2ファイルとtest1ファイルだけで、計測コードは同一。
- guest SHA256: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
  guest/Generated Go/converter/生成所有元inventoryの差分なし。

`ValidatePlatform` のmacOS arm64分岐にprivateなcheckerを置く。
mutexが成功状態と確認中channelを保護し、command中はlockを放す。
成功だけをプロセス寿命で保存。失敗・未対応OS・解析失敗・キャンセルは保存せず、別callerが再試行できる。
待機は各contextでキャンセルでき、panicでもdeferで状態と待機を解除する。
commandのkillエラーとcontextキャンセルが重なった場合は両原因を保持する。
Go側とhost側の入口を保つため、早期拒否の位置とPython共有hostの入口を維持できる。

成功後のsw_versの削除・返答変更は当該processでは再検出しない。
新processは再確認。Pythonの新root hostも初回確認を行い、同じhostの後続子で再利用する。
Linux経路・Python wheel/hash検証・公開API・DBの動作は変更しない。

## レビュー指摘への対応

| 指摘 | 対応と検出網 |
| --- | --- |
| mainとの差分と順序巻き戻し | a43960bへrebaseし、現行のmacOS先行を維持。設計のsource_commitも更新 |
| 失敗時の並列probe増幅 | N=32で、失敗時は合計N回・同時最大1・callerあたり最大1回と固定。成功時は合計1回 |
| globalのtest分離 | 注入testは個別checker。production globalは専用subprocessでのみ使用しresetしない |
| native macOSのrace検証 | localで3回実行。新native CIもmacos-15/Ubuntu各々artifactsをrace付き実行 |
| panic時のwaiterハング | deferで解除し、実際にwait状態へ入ったcallerがpanic後に回復するtest |
| 性能cohortの相違 | 新control/candidateを同じharnessで交互比較。旧17.5ms/9msを削減保証にしない |

失敗が続くN callerのコマンド試行は最大N回であり、負荷ゼロにはならない。
これは失敗の永久キャッシュを避ける設計上の交換条件。

## 証拠と再現

`benchmarks/platform-cache/campaign.py` は `scripts/git_identity.py` でcommit型を確認し、
normal cloneのclean sourceからGo1.26.8/CGO0で4バイナリをビルドする。
`verify_go_binary` で実刻印を検査し、実行後hashも照合する。
Goは既存ownedprepared、Pythonは既存sharedhostのSQL・commit/rollback・子独立性・cleanup oracleを引き継ぐ。
GoのdisconnectとCloseを分離し、Pythonの4子直列/4並列を追加。
Light直列各5対、4並列各3対をGo/Pythonで実行し、計32実行。全データを残す。

実行にはworkspace helperで容量予算10GiB・空き12GiBを設定し、disk guardで1500秒を上限とする。
起動wrapperの最初の試行は、cwdに対する相対script pathの誤りでguest実行前に失敗。
修正した絶対pathのguarded実行を本campaignとする。失敗を性能結果へ混ぜない。

最初の計測版はcompiler一時領域をOSの通常tempへ作った。後続tooling差分でworkspace内へ明示指定する。
コンパイル後にGoが通常tempを回収したことを確認する。測定したruntimeの意味差ではない。

## macOS性能結果

native macOS27.0.1 arm64 / Apple M1 / 8 logical CPUs、Go1.26.8 / CGO0、
Python3.14.8 / PyMySQL1.2.3。通常値であり、profile/guest timing hookは使わない。
Go Lightは1行・1table、Python smallは100 users/100 orders・payload256Bの既存fixture。
言語間の性能順位を比較しない。

| 条件 | 子Fork中央値：対照→候補 | 4子の実経過時間：対照→候補 | 4子区間の差 |
| --- | ---: | ---: | ---: |
| Go 直列（5対） | 61.34→41.89ms | 314.68→229.89ms | −26.9% |
| Go 4並列（3対） | 97.83→56.94ms | 126.49→84.92ms | −32.9% |
| Python 直列（5対） | 51.87→41.98ms | 296.27→257.10ms | −13.2% |
| Python 4並列（3対） | 88.31→65.51ms | 126.13→109.50ms | −13.2% |

4子区間は起動・SQL/commit/rollback・切断・Closeを含み、親準備/Snapshotは含まない。
子Fork中央値は直列20子・並列12子であり、独立process試行数は各5/3。包含区間や中央値を合算しない。
親準備を含むGoの `suite_product_seconds`（処理区間の和を使う既存定義）は直列380.44→290.26ms、
並列210.64→143.35ms。Pythonの全体実経過時間は直列422.64→390.62ms、並列254.86→226.14ms。
この二つの全体指標の境界は異なるため言語間で比較しない。

### 上振れと残る不確実性

- Go初回Start中央値は直列62.37→49.34ms、並列群62.31→47.57ms。
  Goの初回二重確認の削減と整合するが、その差を全てcommand削減だけの厳密な因果量とはしない。
- Python初回Start中央値は62.58→68.82ms（直列）、58.95→65.79ms（並列群）。
  新しいhostの初回確認は残る。初回中央値の悪化理由は未特定。
- Python直列の最初の対ではStartが対照1375.27ms・候補1048.53ms、全体1746.74ms・1369.58ms。
  原因未切分けの上振れとして保持し、候補が初回の遅い試行を解消したとは主張しない。
- Python並列の全体は最初の対で241.17→276.21ms（+14.5%）、他2対で改善。
  全対の4子区間は改善したが、全体が常に改善するわけではない。
- DB Close中央値は直列Go2.79→2.79ms、Python3.04→3.17ms、並列Go4.35→5.17ms、Python4.50→5.30ms。
  約0.8msの並列増加が候補によるか条件差かは未切分け。Closeコード不変だけで性能影響なしと断定しない。
- 少数対の結果であり、tail確率、大規模fixture、他機種への改善量を保証しない。既存の上振れを理由に
  本範囲を自動で広げたり、完了済み100MiB Go Fresh調査を再開したりしない。

## 検証状態

| 検証 | 状態 | 証拠/範囲 |
| --- | --- | --- |
| platform unit / race / native macOS配線 | PASS | [race log](macos-platform-cache-evidence/artifacts-race.txt)、3回。generic checkerと実production入口の専用subprocess |
| 正確な入力・4 binaries刻印/hash・実行後hash | PASS | [builds](macos-platform-cache-evidence/builds.json)、[独立照合](macos-platform-cache-evidence/verification.json) |
| 固定32実行・全機能oracle・scratch/host回収 | PASS（限定fixture） | [receipt](macos-platform-cache-evidence/receipt.json)、全raw JSON/text |
| 全出力hashと集計の独立再計算 | PASS | verification.json、[全集計/min/max](macos-platform-cache-evidence/analysis.json) |
| Goの既存起動失敗・並列子・Snapshot/Fork・cleanup | PASS | [Go log](macos-platform-cache-evidence/go-lifecycle.txt)、tests/godefaultの選定4 tests |
| Python diagnostics / multiclient / 並列siblings / 子の再Snapshot | PASS | [Python log](macos-platform-cache-evidence/python-lifecycle.txt)、22 tests |
| 生成入力・guest identity・public境界・vet/diff | PASS | generated.txt/public.txt、変更は通常Go package。独立再生成は対象外 |
| native macOS15/Ubuntu focused CI | PASS（限定scope） | [run39091145992](https://github.com/masahitojp/mariamem/actions/runs/39091145992)。両OS race/platform/起動/共有host。Ubuntuの性能確認ではない |
| main統合・Qualification・公開 | 対象外 | 別Human判断 |

[環境](macos-platform-cache-evidence/environment.json)、
[回帰command/source](macos-platform-cache-evidence/regression.json)、
[原本/公開保存後hash](macos-platform-cache-evidence/preservation.json)も保持する。
保存時の絶対pathを正規化し、原本と保存後のdigestを分ける。binary/cache/source cloneは保持しない。

## 引継ぎと完了境界

runtimeは測定候補160b272のまま。後続差分は資料・証拠と、再実行時のcompiler tempをworkspaceへ
寄せるtooling修正だけ。履歴を書き換えるため、旧設計commit e0dc61dを基点に統合しない。
実装scope、macOS限定検証、両native focused CIの証拠確認は完了。Humanのmain採用承認と統合については末尾に記録。
新workflowはfocused development checksで、最終Qualificationやリリースを起動しない。

## CI照合と採用レビュー（2026-10-18）

[run39091145992](https://github.com/masahitojp/mariamem/actions/runs/39091145992)は
source_commit `dc183e438a65c13aa532e16e38e31e3378d0a1dd`、両job全step success。
[macOS job117567984061](https://github.com/masahitojp/mariamem/actions/runs/39091145992/job/117567984061)、
[Ubuntu job117567983754](https://github.com/masahitojp/mariamem/actions/runs/39091145992/job/117567983754)。
GitHub metadataのdigestとダウンロードZIPのSHA256を照合し、各7ファイルをそのまま保存した。

| artifact | ID | ZIP SHA256 |
| --- | --- | --- |
| macos-15 | 12123295742 | `009ca2cfd1a5b40332419190781aa7080dfc4bbe2afedb2e7d77027177441da7` |
| ubuntu-24.04 | 12123036878 | `484ba128c613b0db03e9d75521e9027401086dfa87e9d38bd1dd02e8609b62e6` |

[照合receiptと原本file hashes](macos-platform-cache-evidence/ci/receipt.json)、
[macOS race log](macos-platform-cache-evidence/ci/macos/artifacts-race.txt)、
[Ubuntu race log](macos-platform-cache-evidence/ci/ubuntu/artifacts-race.txt)。
実際のplatform.txtはmacOS jobでDarwin24.6.0 arm64、Ubuntu jobでLinux6.17.0 x86_64、両方Go1.26.8。
OS版の呼称はworkflow runnerのmacos-15/ubuntu-24.04で、未記録のpatch versionを補わない。

- 両OSでgeneric checkerの成功・失敗後回復・32caller上限・キャンセル・panic解除をrace付き3回PASS。
- macOSの実production Darwin入口は専用subprocessで3回PASS。Ubuntuではこの1 testだけを明示SKIP。
  UbuntuのSKIPをmacOS経路のPASSへ読み替えない。
- 両OSでGo既存4 lifecycle testsとPython22 testsがPASS。
  FD/goroutineの回収記録も保存され、Goのfailure-path testはmacOS11→11/2→2、Ubuntu9→9/2→2。
- source.jsonはいずれも上のexact commit。生成inventory/guest identity/public source検証もPASS。
  CIはbenchmarkやQualificationを実施していない。

### 採用条件・gapの結論

| 確認点 | 判断 |
| --- | --- |
| 最新mainのmacOS先行方針、成功だけ保存、失敗再試行、独立キャンセル | 満たす。実装と専用oracleを照合 |
| 失敗時のN回上限、test分離、panic解除、native macOSのrace | 満たす。既存レビューgapを両OS logsで閉じた |
| 公開API/対応OS/minimum Go、README/Go/Python/releasingの契約 | 新しい矛盾なし。変更は成功済み環境確認の寿命。architectureに明記 |
| 生成所有元、guest/converter、release inventory/台帳 | 差分なし。生成物の手編集・guard緩和・再生成済みの誤記なし |
| 選定した起動/SQL/transaction/子隔離/終了の回帰 | 両nativeの限定oracleでPASS。全guest意味論の保証にはしない |
| 性能の例外 | 上記の通り未解明。CI不可視であり、少数試行の測定から取り除いていない |
| 未実施 | Ubuntu性能・大規模fixture・最終Qualification。今回の内部確認削減の採用条件に追加せず、結果を保証したとも記載しない |

採用を妨げる未充足の条件は見つからなかった。最大の反論は初回Python/並列Closeの不確実性だが、
本修正が狙う後続Forkと4子区間の利益、両OS機能回帰の維持、変更範囲の小ささから採用を推薦する。
旧実験履歴の無条件mergeではなく、a43960bからの本branch差分が対象。
本branchにはguest/VFS/生成Goの実験差分や、対照側のuncached revert commitは含まれない。

この照合後の差分は文書・証拠のみで、runtimeはCI source dc183e4および測定候補160b272と同一。
このCI照合時点ではmain統合前であり、その後のHuman承認・統合は末尾を参照。Ubuntu並列起動調査は別の承認済み作業として残す。

## Human採用・main統合の記録（2026-10-18）

Humanは採用・統合を承認し、main CIでrace検証を継続する条件を追加した。
`scripts/verify.py integration` の既存 `go test -race` 集合へ `./internal/artifacts` を追加した。
`.github/workflows/check.yml` のmain push/PR → scope判定 → macos-15 integrationを通るため、
実験専用workflowのtriggerに依存せず検証が続く。Linuxの通常checkは従来どおり。

この追加はCI実行対象と採用文書だけで、runtime/testの実装は両OS CIが確認したdc183e4と同一。
[配線確認記録](macos-platform-cache-evidence/main-race-wiring.json)のとおり、source scope selectorの既存57 testsと、integration先頭commandを捕捉する確認で、
artifacts変更がintegrationを選び、race flag付きでpackageが含まれることを確認した。
変更していないruntimeの再ビルドや性能再測定は行わない。main push後の開発CIへ引き継ぐ。

採用対象はa43960bから本branchまでの実装・通常計測コード・証拠と、このCI配線差分。
対照専用6bdcd0eのuncached revertは祖先に含まれない。mainはfast-forwardで統合する。
過去の採用前レビューは当時の状態を記録するもので、この節が現在のHuman決定を所有する。
リリース準備・公開は今回の採用に含めない。

## main開発CIの時間切れと再提出（2026-10-18）

main統合source `94d0a21a4efbedbaf6247d969d3810b3399034bd` の
[run39092465869](https://github.com/masahitojp/mariamem/actions/runs/39092465869)はcheck PASS、
integrationはjob全体15分上限でcancelled。成功として扱わない。
[該当job117571958635](https://github.com/masahitojp/mariamem/actions/runs/39092465869/job/117571958635)の
annotationは `The job has exceeded the maximum execution time of 15m0s`。
ログではartifactsを含むrace集合の全packageがPASSした後、
`go test -tags=integration ./tests/gointegration -count=1 -timeout=3m` の実行中に停止した。
後続のgodefault/generatedmemory/Python検証まで完了した証拠ではない。

Human承認に従い、job全体の枠のみ15→30分へ変更する。テスト集合・race flag・各test commandの
3分deadlineは維持する。cold buildと実行を含む全job予算の調整であり、未完了結果をPASSへ変えない。
workflowだけの変更では既存scope selectorがintegrationを省略するため、check workflowへ
`workflow_dispatch` を追加する。手動eventは既存selectorのevent-baseなし→full判定を使い、
更新したexact sourceをフル検証へ再提出する。selector自体は変更しない。
新runの結果はHumanが完了を通知した後に確認する。runtime変更・公開は行わない。

## main開発CIの再確認完了（2026-10-18）

更新source `8907a4e19da104fd9cd110a91e36543097e43ba4` の手動
[run39094406383](https://github.com/masahitojp/mariamem/actions/runs/39094406383)は
scope・full check・integrationが全てsuccess。
[integration job117577789799](https://github.com/masahitojp/mariamem/actions/runs/39094406383/job/117577789799)の
ログでartifactsを含む全race packageのPASSと、後続のgointegration/godefault/generatedmemory、
Python18 tests、Snapshot33 checksの成功を照合した。
[照合receipt・原本log hash・該当行](macos-platform-cache-evidence/main-ci-completed.json)を保存。

元の15分timeoutは当時の未完了記録として維持し、今回のsuccessと区別する。
テスト内容と各commandの3分timeoutは変更していない。main採用後の開発検証は完了。
Ubuntu並列起動調査は別作業として残り、今回の確認はリリースQualificationや公開ではない。
この完了記録の追加はdocs/evidenceのみで、検証したruntimeは不変。
