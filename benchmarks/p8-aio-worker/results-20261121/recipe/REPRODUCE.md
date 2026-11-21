# 再現手順

候補 a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb を空の実験領域の worktree にチェックアウトする。recipe を同じ領域の evidence/doublewrite/recipe にコピーする。Go 1.27.4、macOS arm64、git、c++filt、Goモジュールのローカルキャッシュ、Python 3.9以降を使用した。build.py が固定候補と対照のsource_commitを検査し、前回の計測器と同じpgmem由来ハーネスを復元する。ワーカー観測器を含む計測バイナリをビルドし、既定ONとOFFを同じバイナリで比べる。関数表は7c5893b3d5198d2c5087dbb100e631dfe63a58bbに収録されたものを使う。

実験領域で以下を実行する。

```sh
mkdir -p temp/gotmp
python3 -B evidence/doublewrite/recipe/guard.py . 1200 python3 -B evidence/doublewrite/recipe/build.py . diag
python3 -B evidence/doublewrite/recipe/guard.py . 300 python3 -B evidence/doublewrite/recipe/controls.py .
python3 -B evidence/doublewrite/recipe/guard.py . 300 python3 -B evidence/doublewrite/recipe/campaign.py . pilot
python3 -B evidence/doublewrite/recipe/guard.py . 900 python3 -B evidence/doublewrite/recipe/campaign.py . main
python3 -B evidence/doublewrite/recipe/reduce.py evidence/doublewrite worktree
```

各Forkで innodb_doublewrite のみを既定ONまたはOFFにして比較する。計96組をON→OFF／OFF→ONの交互で測定する。各Forkで設定変更前後のGLOBAL値を読み戻す。順に innodb_max_dirty_pages_pct_lwm、innodb_io_capacity、innodb_io_capacity_max、innodb_flush_sync、innodb_doublewrite、innodb_buffer_pool_size、innodb_page_size。defaultは2回のSELECT、設定変更条件は間に該当項目のSET GLOBALを1回実行する。いずれもサンプル投入の計測窓の直前。プロセスのCPUとスイート全体の経過にはこれらの問い合わせも含む。条件は各プロセス内のDBにだけ適用した。

400 ms以上の投入を全件保持し、100 ms以上のfutex待ちについて実通知の発生元を追う。各プロセスの圧縮JSONにDBごとの待機イベント・スタック・設定実効値・投入窓を含めた。reduce.pyは不明な対応を除外せず、matched_pageとして区別する。データを再集計するときは、保存済みのrunsを持つ証跡ディレクトリと上記固定リポジトリを引数に指定する。

保存済み証跡の検証は各条件群のディレクトリで以下を実行する。

```sh
tar -xf runs.tar
python3 -B recipe/verify.py .
```

## ワーカーの追跡

この証跡のrecipeは、前回のdoublewrite診断を出発点にしたGoビルド用オーバーレイである。同じ設定比較でワーカーの時刻を集める。上記のreduceに続いて実行する。

```sh
python3 -B evidence/doublewrite/recipe/worker_analysis.py evidence/doublewrite
python3 -B evidence/doublewrite/recipe/verify.py evidence/doublewrite
```

worker-summary.json の associated_slow_stages が0のときだけ campaign.py の main を extend に替え、97–192組を追加してから再集計する。再現率は実行ごとに変動する。

worker_eventsの各行は [時刻ns, 種別, pool, TID, worker, キュー登録時刻, x, y, maintenance]。時刻はプロセス内の単調時計。同一DBの世代を示すキュー登録時刻はsubmit中とAIO呼び出し時に記録する。workerはプール内部のworker_dataポインタ、TIDはイベントを実行したゲストスレッド（futex待機イベントでは待機者）。1–4は空のキュー・実行中数超過・notify_one呼び出し・生成試行。5–8は最大スレッド数・生成間隔・既に生成中・実際のスレッド生成呼び出し。9–12はworker_main開始、条件変数待ち開始／復帰、タスク取り出し。13は最初の模擬I/Oタスクの実行、14はタスク実行終了。15–17は条件変数内のfutex登録、実通知、選択分岐（1がnotify、2がtimeout）。18はdoublewriteバッチを送信した最初の模擬I/Oタスクの実行。対応する待ちや長い初回AIOがあったDBの時系列を保存し、他のDBは集計数だけ保存した。

バッファを経由したページでは、そのデータファイルI/Oを実際に発行した先行コールバックの引数と、先行するバッチの模擬I/Oタスクの引数・登録時刻・実行時刻を照合する。バッチが複数に分かれる場合の「先行タスク」はこのコールバックの親を指す。登録から実行までを foreground のfutex待ちに加算すると重複する。

保存した11件に関する独立検査は、runs.tarの展開後に `python3 -B recipe/verify_worker.py .` を実行する。
