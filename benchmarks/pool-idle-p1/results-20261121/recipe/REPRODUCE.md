# 測定と再集計

新しい測定には macOS arm64、Go 1.27.4、C コンパイラと macOS SDK、Python 3、ローカルの Go モジュールキャッシュを使う。この測定機は Apple M1、macOS 27.2.1 (26B131)。空き 8 GiB を維持し、実験領域の上限は 8 GiB とする。

実験領域の `worktree/` にリング候補 `a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb` のクリーンなチェックアウトを置き、この recipe ディレクトリを同領域の `evidence/study/recipe/` にコピーする。ビルドは pgmem 由来のモデルケースを mariamem の証跡コミット `10665616ba6f00d72b5563158a50bfb7cb2305d2` から復元し、ローカルの候補モジュールを使う。候補と過去の対照 `be12aeb6ebed61f291d98ffa08b872a03695900b` の Git オブジェクトが必要。実行は以下の順序で、複数の測定プロセスが重ならないようにする。

```sh
mkdir -p temp/gotmp
r=evidence/study/recipe
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . idle
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . raw
python3 -B "$r/guard.py" . 260 python3 -B "$r/campaign.py" . idle-pilot
python3 -B "$r/guard.py" . 600 python3 -B "$r/campaign.py" . p1
cp temp/suite.json evidence/study/p1-main-48-1-400-trace.json
python3 -B "$r/guard.py" . 1300 python3 -B "$r/campaign.py" . idle
python3 -B "$r/analyze.py" evidence/study
```

両条件でバイナリを共用し、`POOL_PERIOD_MS` が Fn16634 の初期間隔を選ぶ。タイマー初期設定の実引数が指定値と等しいことを各呼び出しで検査する。P1 の通常ビルドは前回の P8 と生成 Go、fixture の置換後ハッシュが一致する。アイドル用の別ビルドは Fn16626 の進入、OFF と ON への書き込み、ワーカー開始を atomic カウンターで記録する。複数回書き換えた p5 ファイルについて bindings の左側は最後の置換の直前、右側はビルドに使う最終状態のハッシュ。

アイドル試験では root を閉じ、fork ごとに初期データを投入し、件数・合計を検算する。全接続の切断を待ち、snapshot を閉じてから、同一プロセス内の 1 または 8 fork だけを保持する。0、30、70、120 秒の 4 点で累積値を読み、最後に各 DB に再接続して同じ検算を実施する。OS の値はテストプロセス自身の user+system 時間と `proc_pid_rusage(RUSAGE_INFO_V0)` の `ri_interrupt_wkups`・`ri_pkg_idle_wkups`。分母は各区間の実経過秒。後半は 70–120 秒、各条件の代表値は 2 試行の平均（中央値と同値）。各試行の値は idle-windows.csv にある。

P1 は GOMAXPROCS=1、test.parallel=1。P1 の elapsed は fixture のスイート測定窓、CPU はテストプロセス全寿命の user+system。各ブロックの相対差は 100 × (50 ms 設定の値 / 400 ms 設定の値 − 1)。区間は独立したブロックを仮定する二項順位による中央値の両側 95% 区間。予備試験、意味検証、ウォームアップはいずれも比較から除く。

保存データは結果ディレクトリで以下の手順で検証できる。前半の検証は観測時のファイルと照合し、後半の検証は保存した観測から得られる集計が元のファイルとバイト単位で一致することを確かめる。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/analyze.py .
shasum -a 256 -c SHA256SUMS
```
