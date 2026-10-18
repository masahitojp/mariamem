# macOS OS確認結果の再利用：実装・検証

## Human Review

**推薦：macOSの限定結果は採用候補を支持する。native macOS15/Ubuntuのfocused CIを完了してからmain採用のHuman Reviewへ返す。**
後続Forkと4子の実経過時間に利益があり、起動失敗・キャンセル・並列子・SQL・隔離・終了の既存oracleを維持した。
main採用と公開は未承認。[承認した設計](macos-platform-cache-design.md)に対する結果を記録する。

**最も強い留保：少数試行であり、Python初回起動の1秒級上振れ、Python並列の1対の全体悪化、
並列Closeの小幅増加が残る。native CIも未完了。**
これらを削らず保存する。今回の利益は成功した環境確認の反復削減で、初回host起動や全区間の改善保証ではない。
有限な同一入力比較では後続Fork・4子区間の各群中央値が改善したため候補は維持するが、
native回帰失敗なら採用を止める。CI PASSを性能の普遍保証にはしない。
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
| native macOS15/Ubuntu focused CI | PENDING | 新workflowで両OS race/platform/起動/共有hostを実行する。Ubuntuの性能確認ではない |
| main統合・Qualification・公開 | 対象外 | 別Human判断 |

[環境](macos-platform-cache-evidence/environment.json)、
[回帰command/source](macos-platform-cache-evidence/regression.json)、
[原本/公開保存後hash](macos-platform-cache-evidence/preservation.json)も保持する。
保存時の絶対pathを正規化し、原本と保存後のdigestを分ける。binary/cache/source cloneは保持しない。

## 引継ぎと完了境界

runtimeは測定候補160b272のまま。後続差分は資料・証拠と、再実行時のcompiler tempをworkspaceへ
寄せるtooling修正だけ。履歴を書き換えるため、旧設計commit e0dc61dを基点に統合しない。
実装scopeは完了、macOSの限定検証は完了。native CIの確認と採用Human Reviewは未完了。
新workflowはfocused development checksで、最終Qualificationやリリースを起動しない。
