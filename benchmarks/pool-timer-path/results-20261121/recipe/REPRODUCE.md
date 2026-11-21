# 再集計と新規測定

結果ディレクトリで保存データを検証し、表を再生成する。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/analyze.py .
shasum -a 256 -c SHA256SUMS
```

新規測定では experiment-workspace 内の worktree/ に分離案 fa7d878d0bdc8616726db0e8a822285f987a2e91 のクリーンなチェックアウトを置き、evidence/study/recipe/ にこのレシピをコピーする。現行 a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb と pgmem 由来の fixture 10665616ba6f00d72b5563158a50bfb7cb2305d2 の Git オブジェクト、Go モジュールキャッシュ、macOS SDK、Python 3 が必要。Apple M1、macOS arm64、Go 1.27.4、GOMAXPROCS=8。通常モードの間隔は現行 400 ms、分離案 50 ms。低頻度時はどちらも 4 秒。測定出力は空のディレクトリを使う。

```sh
mkdir -p temp/gotmp
r=evidence/study/recipe
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . current
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . split
python3 -B "$r/guard.py" . 180 python3 -B "$r/run.py" . pilot
python3 -B "$r/guard.py" . 1300 python3 -B "$r/run.py" . main
python3 -B "$r/analyze.py" evidence/study
```

シナリオは前回と同じ。試行ごとに新規プロセスの 8 fork で、8 秒休止後に 4 読取・4 更新を同時開始する波を 8 回、70.25〜73.25 秒休止後にもう 1 回実行する。全接続の切断、在庫増分、40 注文・100 明細と各合計 1,888,173 セントを検算する。各条件 1 試行ずつを 1 組とし実行順を反転する。4 秒超の通常モードの観測から今回追加した独立記録で経路を特定できた組、または最大 4 組で終了する。

## 記録点

固定 guest の関数表から該当する行を symbols.txt に保存した。展開した表全体の SHA-256 は 1f8dcd20057090cde400f1439d0cc9d1c933b16490ba8ecd22269d909f1fe475。MariaDB の上流ソース識別は upstream.json と mysys-source.json に保存した。計測は生成 Go のオーバーレイで、各対象に元の演算の前後から記録を追加する。

コンストラクタで線形メモリの識別子、スレッド群を示す m.Threads、プールの guest 内アドレス、所有する timer_generic のアドレスを関連付ける。後者の +8 がヒープに登録される thr_timer_t。生成 Go の Fn5495 で期限到来後のヒープからの取り出し、直接ディスパッチ、周期の再確認、再挿入を記録する。Fn16625 と Fn16626 の進入・退出を個別に計数する。対象タイマーに対する Fn16636 のワーカー用タスク送信、初期設定、解除も照合する。メモリ単位だった前回の最終進入時刻と、m.Threads とプールアドレスで判別した今回の最終進入時刻を同じ観測窓で比較する。

各波の直前に各 DB の累積回数、各段の直近時刻、対象タイマーの最近 20 イベント、タイマースレッドの最後の処理を保存する。Handler の wait の Value は、ゲストが選んだキュー先頭の期限とハンドラの直前の now との差（ns）。dispatch の Value は関数テーブルの番号。再挿入の Value は周期（µs）、完了時は例外フラグ。各時刻はそのテストプロセス内の単調時計を使う。別のタイマーを処理中なら Handler の Address は対象タイマーのアドレスと異なる。通常モードの最終進入から 4 秒超の DB では、最初の該当波で全 goroutine のスタックも保存する。Fn5495 に入った goroutine の ID を同時に記録して照合する。

main の JSON は gzip で圧縮して保存する。analyze.py は JSON と gzip の両方を読める。summary.csv の経路別回数は各 DB の最終波の直前までの累積値で、後続の SQL と終了処理を含めない。snapshots.csv は各波の各 DB の測定点であり、連続監視した最大遅延の上限ではない。
