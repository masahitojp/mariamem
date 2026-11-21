# 再現手順

保存済みの結果を検査するには、この証跡のルートで以下を実行する。`verify.py` はこの固定観測での件数、ペア順、要求、時刻の検査を含む。新しい測定で稀な待ちの件数は変動する。

```sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/verify.py .
```

再計測には空の実験領域を用意し、直下の `worktree` に候補コミット a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb をクリーンにチェックアウトする。OSパイプは be12aeb6ebed61f291d98ffa08b872a03695900b の linked.go を使用する。pgmem由来のハーネスを含む 10665616ba6f00d72b5563158a50bfb7cb2305d2 と監査済み関数表を含む 7c5893b3d5198d2c5087dbb100e631dfe63a58bb のGitオブジェクトが必要。Go 1.27.4、キャッシュ済みGo依存、Python 3、git、c++filt と8 GiB以上の空きを用意する。この recipe ディレクトリを実験領域の evidence/published/recipe にコピーし、実験領域から実行する。

```sh
mkdir -p temp/gotmp
python3 -B evidence/published/recipe/guard.py . 1200 python3 -B evidence/published/recipe/build.py . diag
python3 -B evidence/published/recipe/guard.py . 300 python3 -B evidence/published/recipe/controls.py .
python3 -B evidence/published/recipe/guard.py . 300 python3 -B evidence/published/recipe/campaign.py . pilot
python3 -B evidence/published/recipe/guard.py . 900 python3 -B evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py .
```

保存した各回を再集計する場合は、計測を走らせる代わりに同じディレクトリ構成の evidence/published/runs に保存済みの runs をコピーし、最後の reduce.py だけ実行する。生成Goの観測箇所は overlay.py、待機登録・通知・キューの対応付けは probe.go.txt、意味検証と試行順は campaign.py にある。
