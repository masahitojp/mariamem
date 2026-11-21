# 再現手順

保存結果の再集計は結果ディレクトリで実行する。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/analyze.py .
shasum -a 256 -c SHA256SUMS
```

新規測定は experiment-workspace の worktree/ に候補 fa7d878d0bdc8616726db0e8a822285f987a2e91 をチェックアウトし、evidence/study/recipe/ にこのレシピを置く。現行 a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb、モデルケースの fixture 10665616ba6f00d72b5563158a50bfb7cb2305d2 の Git オブジェクトとローカルの Go モジュールキャッシュが必要。測定環境は Apple M1、macOS arm64、Go 1.27.4、GOMAXPROCS=8、GOGC=100。出力には新しいディレクトリを使う。

```sh
mkdir -p temp/gotmp
r=evidence/study/recipe
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . current
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . split
python3 -B "$r/guard.py" . 200 python3 -B "$r/control.py" .
python3 -B "$r/guard.py" . 180 python3 -B "$r/run.py" . pilot
python3 -B "$r/guard.py" . 3650 python3 -B "$r/run.py" . main
python3 -B "$r/analyze.py" evidence/study
```

## 記録点

元の軽い計測は各プールの保守進入時刻と通常・低頻度モードを保存する。今回追加した進入通番を Fn16626 から出る際に保存する。mysys タイマーハンドラ Fn5495 が対象の timer_generic をヒープへ再挿入し、例外フラグが 0 で戻った際に、直前の退出通番を保存する。対象は固定関数表のディスパッチ番号 12334 と、コンストラクタで登録したタイマーオブジェクトの +8 アドレスの両方で照合する。入退出は同一タイマーハンドラ上で直列。各ハンドラの goroutine ID は開始時に一度読み、スレッド群と関連付ける。通番の読み取りは個別の atomic load であり、発火の最中には 1 回の記録途中が見える場合がある。

SQL と別の goroutine が実験対象の 8 fork を監視する。各スキャン時点で最も早く条件を満たしうる時刻まで休む。条件は「通常モードが継続し、最後の進入と直近の通常モード移行の両方から 4 秒以上」。低頻度時の 4 秒周期と、通常モードに戻った直後を除外する。該当時はその DB をもう一度読み確認し、初めての 1 件だけ全 goroutine のスタックと前後の通番、該当ハンドラのスタックを保存する。捕捉はアプリケーション SQL の波と独立して行う。検出器の制御試験は、低頻度状態・直後のモード移行・通番が 1 で止まった人工のプールを別プロセスで検査する。

## 比較条件

8 DB を 8 秒切断してから一斉に 4 読取・4 更新を行う波を 8 回、さらに 70.25〜73.25 秒切断してから 1 波。この 4 種の長休止を繰り返す。各試行は新しいプロセスで行い、現行→分離と分離→現行を組ごとに反転。12 組または実事象の最初の捕捉で終了する。捕捉プロセスの SQL と終了時の検算は完了させる。各 DB の在庫、40 注文・100 明細、注文と明細の各合計 1,888,173 セントを検査。summary.csv の通番は試行の最終応答後に各 DB から読み出した値の合計。アラームを記録した時点の値は個別の capture.json で確認できる。予備と制御試験は本計測から除く。
