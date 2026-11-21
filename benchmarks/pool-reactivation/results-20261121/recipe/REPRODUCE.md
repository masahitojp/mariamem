# 再現手順

結果のみ再集計するには、結果ディレクトリで以下を実行する。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/analyze.py .
shasum -a 256 -c SHA256SUMS
```

## 候補を生成して測る

同一リポジトリの experiment-workspace を用意し、worktree/ に candidate.json の source_commit をクリーンにチェックアウトする。evidence/study/recipe/ にこのレシピをコピーし、空の測定出力先を使う。元のリング a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb と pgmem 由来の fixture 10665616ba6f00d72b5563158a50bfb7cb2305d2 の Git オブジェクトが必要。実測環境は Apple M1、macOS arm64、Go 1.27.4。静的イメージ生成には固定 Go 1.26.11、その他に C SDK、Python 3、ローカル Go モジュールキャッシュを使用する。

```sh
mkdir -p temp/gotmp
r=evidence/study/recipe
python3 -B "$r/regenerate.py" . temp/replay-a
python3 -B "$r/regenerate.py" . temp/replay-b
python3 -B "$r/guard.py" . 900 python3 -B "$r/layout.py" .
python3 -B "$r/check_sources.py" .
git -C worktree diff --exit-code
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . plain
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . current
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . split
python3 -B "$r/guard.py" . 180 python3 -B "$r/run.py" . smoke
python3 -B "$r/guard.py" . 180 python3 -B "$r/run.py" . pilot
python3 -B "$r/guard.py" . 1300 python3 -B "$r/run.py" . main
python3 -B "$r/analyze.py" evidence/study
```

generate_runtime.py は固定 guest の生成 Go を gofmt した後に runtime_pool_period.install を適用する。変換の入力は固定ハッシュの 2 ファイル。Fn16634 の通常間隔の初期化 1 か所と、Fn16626 の低頻度モードのミリ秒・マイクロ秒書き込み各 2 か所を変更する。regenerate.py は固定リングの Git オブジェクトからこの処理を再生する。layout.py は選択した候補のコンストラクタを実行し、リポジトリ標準の静的イメージ生成と provenance の更新を行う。check_sources.py は両回の生成 Go と記録済み候補の一致、初期イメージのメモリ内容、全ファイルのハッシュを検査する。

通常起動はオーバーレイなしの候補で TestMatchedSemantics を実行する。計測では各設定専用のバイナリに同じカウンターを加える。現行は固定リングのモジュールから、分離は候補のモジュールからビルドする。初回タイマー設定の実引数と、低頻度に切り替える際の書き込み値を検査する。計測用カウンターは DB ごとのモードと直前の保守呼び出しの時刻を保存する。

## 計測窓

同一プロセス・GOMAXPROCS=8。各試行とも、8 fork それぞれに 40 注文・100 明細を投入し、全接続を閉じる。8 秒の切断とバリアによる同時復帰を 8 波繰り返し、9 波目は 70.25〜73.25 秒切断してから同時復帰する。各波は読取 4 DB・在庫を 1 増やす更新 4 DB、対象は波ごとに反転する。各設定 4 試行で、条件の実行順も反転する。予備実行は分けて保存する。

CPU は各休止の前後でテストプロセスの user+system の差を取り、macOS の proc_pid_rusage から割り込みとパッケージアイドルによる起床の差を取る。各プロセス内で休止時間の合計を分母として率を求め、4 試行を等重みで平均する。長休止の率は休止全体についての値。各要求の経過は接続作成から最初の SELECT または UPDATE 完了まで、波の経過は共通バリア開放から最後の SQL 応答まで。開始時刻の広がりと全要求が同時に進行していたかも記録する。P95 は経験分布の最近順位。各 DB で最終在庫と件数・注文/明細金額の一致を確認する。
