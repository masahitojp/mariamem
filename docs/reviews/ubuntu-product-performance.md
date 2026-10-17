# Ubuntu性能確認：実行範囲と結果待ち

**性能結果は未取得。Ubuntu性能の確認を先に進めるというHuman指示に基づく計測準備。**
機能Qualificationの両OS PASSを性能の証拠へ読み替えない。結果取得後に、
macOSで観測した製品全体とSnapshot所有権変更の利益がUbuntuでも成立するかをHuman Reviewする。
今回の準備はruntimeの採用・変更・リリース判断を含まない。

## 比較対象

| 版 | source_commit | 比較の目的 |
| --- | --- | --- |
| v0.5.0 | `44100ec676c8c9064f32f3a01bd9a990d487bb61` | 起動順序・D backing・共有host・所有権を含む現在までの製品全体の差 |
| v0.5.1 | `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb` | v0.5.2との比較でSnapshot所有権変更の差を見る |
| v0.5.2 | `47f297cc7498625e076abb93322eb616c9560bb8` | 現在の公開版 |

tag_object_shaとsource_commitは[typed pins](../../release/baselines/)を用いて別々に検証する。
mainの後続文書変更を公開版のruntimeとして測らない。

native Ubuntu24.04 x86_64、Go1.26.8／CGO_ENABLED=0、Python3.14.8と既存dependency pins。
手元のDockerはLinux aarch64のため、native x86_64の代用にせずGitHub Actionsで実行する。
同じrunner上で版の順序を交替し、build時間は測定値から除く。
ハードウェア・OS・compiler・harness・runtime・guest・binaryのidentityを証拠に残す。

## 有限scopeと終了条件

[計測手順](../../benchmarks/ubuntu-product/README.md)と
[専用workflow](../../.github/workflows/ubuntu-product-performance.yml)が正本。

- 既存のGo／Python、Fresh／Fork、Light／10 MiB直列／10 MiB・4並列を各版3試行。
- 100 MiBはGo／PythonのForkだけ。再発待ちで閉じた100 MiB Go Freshの追加測定やprofilingは開始しない。
- 既存の準備済みDB→Snapshot→複数子のPythonシナリオを、小・中・100 MiBで再利用。
  v0.5.0→v0.5.2とv0.5.1→v0.5.2は別campaignとして、通常6対・資源観測3対ずつ。
- 合計246実行（比較matrix126、除外pilot12、再利用workflow108）。
  全体時間、Snapshot、子起動・SQL・Close、CPU、Go allocation／RSS、mapping回収を記録する。
- 元のSQL／transaction／隔離／cleanup oracle、入力identity、完了数・欠測を保持する。
  失敗・予算到達は未完了とし、遅い試行を除外・置換しない。
- buildを含むcampaign上限2時間。cell timeout900秒、再利用pair campaign1800秒、
  owned disk20 GiB、空きreserve8 GiB。Go RSSの観測上限6 GiBはhard RAM quotaではない。

完了判定は実行数・元oracle・identityの充足に対して行う。
改善しなかった結果も正当な結果として報告し、機能PASSから性能改善を推論しない。
macOS／Ubuntuの絶対時間、Go／Pythonの別observer、通常／資源観測を混ぜた順位づけはしない。
Testcontainersやpgmemとの新規比較、一般tail頻度の保証、性能原因の追加調査は今回のscope外。

## 提出前の検査

ローカルで新規toolingの5件のofflineテスト、既存Git identityの12件、Python構文、
workflow YAML、公開source検査、diffの空白を確認し、PASS。
記録済みmacOS cellをUbuntuと誤認する入力、欠測・未完了、未解放mapping、
observerの想定外変更を拒否する負例を含む。
3版のrelease identityと許容するobserver差分も既存Git blobで照合した。
native以外の環境ではclone／build前に停止し、未完了のfailure記録を出すことも確認した。
製品runtimeを変更していないため、ローカルで全面integrationやQualificationは再実行しない。

CI提出後はrun URLとharness SHAをHumanへ引き渡し、監視・pollを行わず停止する。
結果が返された時点でartifactの入力・完了receipt・全試行と集計を照合してレビューする。
