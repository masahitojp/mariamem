# 再現手順

数値を再集計するには証跡ディレクトリで次を実行する。Python標準ライブラリのみを使う。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/reduce.py .
shasum -a 256 -c SHA256SUMS
```

実測には macOS、Go 1.27.4、Python 3.9以降、ローカルDBの起動、固定コミットのソースとGo依存モジュールが必要。mariamemの完全な履歴から次のレイアウトを用意する。実験補助スクリプトへの引数はワークスペースのルートである。

- `worktree/` はクリーンな mariamem `5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c`。履歴にはMaria側ハーネス `10665616ba6f00d72b5563158a50bfb7cb2305d2`、pg側ハーネス `bac82de41a87849f23564117825e00fc43b0017a`、リング `de04aaa7aaf2b8d67c764012111feed6b3d34bac` の実験ブランチも含める。
- `temp/pg/` はクリーンな上流 pgmem `a61005d37d01e6671f814fe8ca828222e8147df4`。両ソースはビルドのたびに `git_identity.py` で検査する。
- 本ディレクトリの `recipe/` を `evidence/published/recipe/` にコピーする。新規ワークスペースで使う。Goのコンパイルキャッシュと一時ディレクトリは `temp/` に作成する。依存モジュールは事前にローカルモジュールキャッシュに入れる。ビルドは `GOPROXY=off`。
- 上記の配置でワークスペースのルートから実行する。

```sh
for mode in maria pg frames
do
  python3 -B evidence/published/recipe/guard.py . 1200 python3 -B evidence/published/recipe/build.py . "$mode" || exit 1
done
python3 -B evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
```

1プロセスにつき1スイート。意味検証は各条件1回。ウォームアップを各P・各条件1回実行した後、3条件の全順列を各Pで1巡する。ブロックごとにP1/P8の順序も反転する。比較は同じブロックのOSとリングを使う。PはGoテストの並列度。すべてのプロセスは `GOMAXPROCS=8`、`GOGC=100`。更新用Forkと共有readerを含めて最大16 Fork。スイート終了まで同期Close。OSとリングは同一バイナリの `MARIAMEM_BENCH_STREAM=os/both` で選ぶ。`frames` は別ビルドで各P・各条件2回ずつ。応答ヘッダ4バイトを含めた、JSON復号後に要求IDを照合できた全応答のサイズを記録する。

`runs/*.json.gz` は終了コード、CPU、最大RSS、時系列RSS、Goの全スパンと該当する場合のフレームサイズ度数。`suite_ms` はTestMain内の起動準備から最終Close完了後のトレース取得まで。`process_ms` は起動直前から外部の終了検知までで、約5 msのポーリング粒度を含む。CPUは `wait4` のプロセスuser＋system、最大RSSは同じくDarwinの `ru_maxrss`（バイト）。現在RSSは外部から `proc_pidinfo(PROC_PIDTASKINFO)` の `pti_resident_size` を約5 ms間隔で読み、トレース開始時の実時間に合わせる。採取目的のGCは入れない。各フェーズの最大は、そのスパンに実際に入った観測点で算出する。同時に動くフェーズの試料は重複し、5 ms未満の処理では観測点が欠けうる。メモリの所有者や解放済みヒープの量をこの値から推定することはできない。
