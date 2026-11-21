# Darwin/arm64 での再生

製品コミットは 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c。実験用の空の作業領域を作り、その直下の `worktree/` にこのコミットを checkout する。`temp/` と `evidence/published/` を用意し、この `recipe/` を後者に置く。計測元リポジトリには関数表・ハーネスの証跡コミット 7c5893b3d5198d2c5087dbb100e631dfe63a58bb と SQL ハーネスの 706072d8dbfa76acb23d302d6bfaa08b91c444b5 も必要。Go 1.27.4、Apple SDK と C コンパイラ、Python 3、および固定 go.sum のモジュールが利用可能な環境で行う。ハーネスはローカルのループバックで待ち受ける。

作業領域のルートから実行する。guard.py は前回の証跡で固定した時間・ディスク監視。ビルドは worktree のコミットを照合してから、読み取り専用モジュール設定で 1 個のバイナリを生成する。

```sh
git -C worktree show 7c5893b3:benchmarks/trigger-sum-bottleneck/results-20261121/recipe/guard.py > temp/guard.py
python3 temp/guard.py . 1200 python3 evidence/published/recipe/build.py .
python3 temp/guard.py . 900 python3 evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
```

保存データだけから表を再計算するには最後のコマンドを実行する。各 .json.gz は通常の JSON。Requests のキーは DB と Ordinal（ともに 0 始まり）。Events の順序は同一リクエストの実行順。Possible は固定 Fn14079 の possible_keys への直接追加区間、SameArena は Fn783 に渡された MEM_ROOT と計画の MEM_ROOT の一致を示す。ストアの HostPage は DB の線形メモリ先頭ページを 0 とするホストページ番号。Guest と InPage はバイト単位。Ticks のナノ秒換算は `Ticks * Controls.Numer / Controls.Denom`。Before と After がともに -1 の場合はタイマーのみ。値 0 は Mach が返した実際の disposition。

各プロセスは 8 回、新しい fork に同じ 100 明細を投入する。ページ照会ありは DB 0, 3, 5, 6、残りはタイマーのみ。C の計時区間は 32-bit の volatile ストアと arm64 の完了バリアを含む。前後のページ照会、cgo 呼び出し、経路記録、アドレス検査は区間外。校正用の empty は同じバリアとタイマーで書き込みを省く。照会はプロセス自身のタスクだけに行う。全 SQL 中の当該ストアを計測し、目的の経路は記録されたフレームで抽出する。

上流ソースは MariaDB/server の e4549ea60c98a8743ed4743d7f92174d8a0005d9。codeload の tar.gz の SHA-256 は 628eef6d789b563e46f362b4a98dd32ff3dd86050929215fb4cf773ec0549ff6。固定製品の生成 Go では my_malloc の第 1 引数がサイズで、第 2 引数がフラグ。上流 C の PSI key 引数はこの生成関数のシグネチャに含まれない。
