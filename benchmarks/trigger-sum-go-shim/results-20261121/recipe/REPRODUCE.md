# 再現手順

固定製品 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c を専用作業領域の worktree/ に checkout する。履歴に 7c5893b3d5198d2c5087dbb100e631dfe63a58bb（前回の CPU/イベント・ハーネス）と 706072d8dbfa76acb23d302d6bfaa08b91c444b5（SQL/seed）が必要。作業領域に temp/ と evidence/published/ を用意し、後者にこの recipe/ を置く。macOS arm64、Go 1.27.4、Python 3、固定 go.sum に対応するモジュールを使用。実行時にはループバックを使用する。

前回の証跡を任意のディレクトリに展開し、下記の prior をその results-20261121 ディレクトリとする。pprof は保存済みシンボルを使って生プロファイルを表示できる実行ファイルのパス。使用した /usr/local/go/pkg/tool/darwin_arm64/pprof は既存 Go 配布に同梱の解析ツール。ビルド・計測する Go は environment.json に記録されている。

作業領域直下から実行する。

```sh
python3 evidence/published/recipe/screen.py "$prior" evidence/published "$pprof"
python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . base
python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . shim
python3 evidence/published/recipe/guard.py . 300 python3 evidence/published/recipe/test_bounds.py .
python3 evidence/published/recipe/guard.py . 900 python3 evidence/published/recipe/campaign.py .
python3 evidence/published/recipe/reduce.py evidence/published
```

overlay.py は元コードが uint32 住所または表現可能な定数であり、変位と幅が定数であることを通常の全アクセスで確認する。幅と変位の和は 32 bit 以内。一般の MemoryEA と、通常命令以外のヘルパーは両方のバイナリに残る。差分テストは返却アドレスと panic の値を比較し、生成コードを使う既存テストで実際の load/store、境界越え、grow、worker の可視性と失敗伝播を確認する。巨大な生成コードを証跡として複製しない。変換する各ファイルの SHA-256 は binding.json にある。

observations.jsonl には事前検査と全 DB の生データを含む。最後のコマンドが pairs.csv と summary.csv を再構築する。プラスの gain は短縮。p95 は各プロセスの40件中38番目（昇順）。CPU は raw 窓を囲んだ getrusage の user+system の差で、同一プロセスのバックグラウンド処理を含む。
