# PR #235のSUM付き100 INSERTの直接比較

元のSUMを維持した100件のprepared INSERTで、PR #235による対応差の中央値は1.616 ms短縮（9.41%）。6組中6組で短縮。同一方式を再測定した絶対差の中央値は0.219 ms。このSUM付きINSERT用途の改善候補としてPR #235を推奨する。 試作版での8.7%短縮を参照し、PR先頭a1ce4a7dと親be12aeb6の製品ソースから独立にビルドして測った。以前の製品候補比較は起動からCloseまでのpgmem由来スイート、以前の100 INSERT比較は旧ベース上の試作だった。[試作での直接比較](https://github.com/masahitojp/mariamem/blob/de04aaa7aaf2b8d67c764012111feed6b3d34bac/benchmarks/host-framed-transport/results-20261121/README.md)

| 組 | 実行順 | 親 OS (ms) | PR (ms) | 短縮 (ms) | 短縮率 | 再測定差 (ms) |
|---:|---|---:|---:|---:|---:|---:|
| 1 | os/ring/os | 17.108 | 15.592 | 1.516 | 8.86% | 0.297 |
| 2 | ring/os/ring | 16.899 | 15.701 | 1.198 | 7.09% | 0.200 |
| 3 | os/ring/os | 16.995 | 15.551 | 1.443 | 8.49% | 0.238 |
| 4 | ring/os/ring | 17.396 | 15.665 | 1.731 | 9.95% | 0.025 |
| 5 | os/ring/os | 17.483 | 15.438 | 2.045 | 11.70% | 1.068 |
| 6 | ring/os/ring | 17.127 | 15.412 | 1.716 | 10.02% | 0.079 |

OSは親コミットのOSパイプ、ringはPRの双方向16 KiBリング。各組で2回実行した方式は2値を平均した。短縮率はOS時間を分母とする。同一方式の再測定差には最初と最後の絶対差を使った。判定条件は全6組で短縮し、短縮msの中央値が同一方式の再測定差の中央値を上回ること。生データは[runs](runs)、精密値は[pairs.csv](pairs.csv)。

## 測った区間と検算

Go 1.27.4 / macOS arm64、GOMAXPROCS=8、アプリの投入並列度1。両コミットとも標準の保守周期。40親注文を準備したスナップショットをForkし、単一トランザクションで同一のprepared INSERTを100回逐次実行する。時計は最初のExec直前から最後のExecが戻るまで。要求ごとの時計、トレース、プロファイルは使わない。準備・PREPARE・COMMIT・検算・Closeは区間外。依存ドライバは両側とも製品のgo.modに一致させた。

各方式1 DBの予熱後、18プロセスを順に起動。各プロセス12 DBを個別に検算し、先頭2 DBを除く10 DBの平均をプロセスの値とした。測定対象180 DB・18,000 INSERT、予熱を含む検算は218 DB・21,800 INSERT。登録5トリガーの本文、各注文の合計と明細、40注文・100明細・監査40件、500商品すべて在庫100、FK/CHECK、Closeを確認した。今回の時間差は実行経路全体の改善であり、SUM計算内部の短縮率は分離していない。

## 再現

[build.json](build.json)のring.source_commitを専用worktreeに固定し、その隣にtemp/gotmp、evidence/runs、evidence/recipeを用意する。空の測定領域で以下を実行する。

```sh
python3 -B evidence/recipe/guard.py . 1200 python3 -B evidence/recipe/build.py
python3 -B evidence/recipe/guard.py . 900 python3 -B evidence/recipe/run.py
python3 -B evidence/recipe/reduce.py
```
