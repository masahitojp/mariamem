# 比較を再現する

保存結果を再集計するには結果ディレクトリで以下を実行する。P1 と P8 の観測ファイルにはセットアップを含む各スイートの全スパンを gzip 圧縮した JSON Lines 形式で収録した。idle-*.json はアイドル試行ごとの累積カウンター・各 DB の検算・復帰要求である。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/analyze.py .
shasum -a 256 -c SHA256SUMS
```

## 新規測定

Apple M1、macOS arm64、Go 1.27.4、C コンパイラと macOS SDK、Python 3 を使用。実験領域の worktree/ にリング候補 a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb をクリーンにチェックアウトする。evidence/study/recipe/ にこのレシピをコピーする。ローカルの Go モジュールキャッシュ、過去のハーネスコミット 10665616ba6f00d72b5563158a50bfb7cb2305d2 と対照 be12aeb6ebed61f291d98ffa08b872a03695900b の Git オブジェクトが必要。ディスク上限は 8 GiB、最低空き容量は 8 GiB。空の測定出力先を使う。

```sh
mkdir -p temp/gotmp
r=evidence/study/recipe
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . raw
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . idle
python3 -B "$r/guard.py" . 180 python3 -B "$r/run.py" . pilot
python3 -B "$r/guard.py" . 900 python3 -B "$r/run.py" . idle
python3 -B "$r/guard.py" . 900 python3 -B "$r/run.py" . p8
python3 -B "$r/guard.py" . 600 python3 -B "$r/run.py" . p1
python3 -B "$r/analyze.py" evidence/study
```

通常・アイドル計測用の各バイナリは 3 条件で共用する。current は 400/4000 ms、short は 50/500 ms、split は 50/4000 ms（通常/低頻度）。生成Goの Fn16634 で通常間隔を選び、初回タイマー設定の実引数を確認する。Fn16626 内の低頻度移行の 2 経路では、分離案だけ間隔計算の入力を 400 にする。従来の 10 倍計算、時間単位変換、タイマー更新、ロック、通常モードに戻す経路は共通。アイドル計測用バイナリは、期間の書き込み値を検査し、各プールの状態と保守コールバック時刻を記録する。MariaDB の固定バージョンの実装は upstream.json に記載した。

各アイドル試行で同一プロセスに 8 fork を保持し、全接続を切って 120 秒間 SQL を発行しない。30、70、120 秒でカウンターを読む。macOS の CPU は user+system、起床は proc_pid_rusage の ri_interrupt_wkups と ri_pkg_idle_wkups。70–120 秒の実経過で割り、2 試行を等重みで平均する。予備試験の 3 秒は集計から除く。

復帰は 120 秒から 450 ms ずつずらして、8 個の DB にそれぞれ 1 回ずつ行う。接続込み時間はコネクターの生成から初回の stock 読取完了または stock を 1 増やす UPDATE の完了まで。接続は sql.DB.Conn による接続確立まで、SQL はその接続を使った最初のアプリケーション文の実行時間である。復帰直前に同じ DB のタイマー状態と最後の保守呼び出しからの経過を読む。各試行は読取 4 件・更新 4 件、2 巡目に DB の位置と SQL 種別の対応を反転する。各 DB で更新対象の在庫、注文と明細の件数・金額を再検算する。

P8/P1 は GOMAXPROCS と test.parallel をそれぞれ 8/1 に設定する。各ブロックで 3 条件を 1 回ずつ実行し、6 通りの順序を 16/8 巡する。条件ごとに独立の意味検証 1 回とウォームアップ 1 回を除く。CPU はテストプロセス全体、wall はスイートの測定窓。P8 の並列スパンには重なりがある。対応差は同じブロックの 100 × (試験値 / 対照値 − 1)。区間はブロック間の独立を仮定した二項順位による中央値の両側 95% 区間である。
