# 再現手順

Apple M1、macOS arm64、Go 1.27.4、GOMAXPROCS=8、GOGC=100。固定候補 a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb を実験領域直下の worktree にクリーンにチェックアウトする。recipe を evidence/timer/recipe にコピーする。ビルドが参照する過去の証跡コミットとGoモジュールキャッシュが必要。候補と以前のパイプ対照のsource_commitはビルド前に検査する。今回使う転送は全てリング。

```sh
mkdir -p temp/gotmp
r=evidence/timer/recipe
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . diag
python3 -B "$r/guard.py" . 1200 python3 -B "$r/build.py" . raw
python3 -B "$r/guard.py" . 300 python3 -B "$r/controls.py" .
python3 -B "$r/guard.py" . 240 python3 -B "$r/campaign.py" . pilot diag
python3 -B "$r/guard.py" . 240 python3 -B "$r/campaign.py" . pilot raw
python3 -B "$r/guard.py" . 900 python3 -B "$r/campaign.py" . main diag
python3 -B "$r/guard.py" . 900 python3 -B "$r/campaign.py" . main raw
python3 -B "$r/analyze.py" evidence/timer
python3 -B "$r/worker_analysis.py" evidence/timer
python3 -B "$r/verify_timer.py" evidence/timer
```

各モードにつきバイナリは1本。POOL_PERIOD_MSで同じ生成GoのFn16634内の初期フィールド値だけを選び、set_timeの実引数と呼び出し数を検査する。診断ビルドはSQL要求のfutex待ちを10 ms以上から保存し、同じページ・AIO制御ブロック・タスクの登録から実行を関連づける。ワーカー生成数は、2つのpurge処理を含むプールのworker_main開始を22 DBの生存期間全体で数える。保守回数はmaintenanceコールバックへの進入回数。キュー待ちの最大値は各DBで分解能nsのまま更新し、短い待ちも含む。通常ビルドはタイマー選択・実効値確認とベンチ標準のスパンのみ。プロセスCPUは子プロセスのuser+system時間。2つのモードの数値はそれぞれのモード内で比較する。

既存の保存データを再集計するには、結果ディレクトリで `python3 -B recipe/unpack.py .` により6アーカイブを展開して上記の末尾3コマンドの出力先を「.」に置き換える。worker.csvには10 ms以上でSQLの長い待ちに結びついた段を記録するため、全タスクの分布とは区別する。paired.csvの区間はプロセスブロック内の50/400相対差についての二項順位による95%中央値区間。反復間の独立を仮定する記述的な区間である。
