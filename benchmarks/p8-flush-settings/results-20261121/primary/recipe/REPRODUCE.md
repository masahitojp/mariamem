# 再現手順

候補 a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb を空の実験領域の worktree にチェックアウトする。recipe を同じ領域の evidence/published/recipe にコピーする。Go 1.27.4、macOS arm64、git、c++filt、Goモジュールのローカルキャッシュ、Python 3.9以降を使用した。build.py が固定候補と対照のsource_commitを検査し、前回の計測器と同じpgmem由来ハーネスを復元する。設定比較はリング候補の同じバイナリで行う。関数表は7c5893b3d5198d2c5087dbb100e631dfe63a58bbに収録されたものを使う。

実験領域で以下を実行する。

```sh
mkdir -p temp/gotmp
python3 -B evidence/published/recipe/guard.py . 1200 python3 -B evidence/published/recipe/build.py . diag
python3 -B evidence/published/recipe/guard.py . 300 python3 -B evidence/published/recipe/controls.py .
python3 -B evidence/published/recipe/guard.py . 300 python3 -B evidence/published/recipe/campaign.py . pilot
python3 -B evidence/published/recipe/guard.py . 900 python3 -B evidence/published/recipe/campaign.py . main
python3 -B evidence/published/recipe/reduce.py evidence/published worktree
```

各Forkで設定変更前後のGLOBAL値を読み戻す。順に innodb_max_dirty_pages_pct_lwm、innodb_io_capacity、innodb_io_capacity_max、innodb_flush_sync、innodb_doublewrite、innodb_buffer_pool_size、innodb_page_size。defaultは2回のSELECT、設定変更条件は間に該当項目のSET GLOBALを1回実行する。いずれもサンプル投入の計測窓の直前。プロセスのCPUとスイート全体の経過にはこれらの問い合わせも含む。条件は各プロセス内のDBにだけ適用した。

400 ms以上の投入を全件保持し、100 ms以上のfutex待ちについて実通知の発生元を追う。各プロセスの圧縮JSONにDBごとの待機イベント・スタック・設定実効値・投入窓を含めた。reduce.pyは不明な対応を除外せず、matched_pageとして区別する。データを再集計するときは、保存済みのrunsを持つ証跡ディレクトリと上記固定リポジトリを引数に指定する。

保存済み証跡の検証は各条件群のディレクトリで以下を実行する。

```sh
tar -xf runs.tar
python3 -B recipe/verify.py .
```
