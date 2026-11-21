# #233　SUM トリガーで実行計画を保存する際の割り当て

**判断は証拠不足。索引名のコピー削除を試作することは勧めない。** SUM では 2,400 件すべての UPDATE 計画でメモリアリーナ（MEM_ROOT）を1回補充した。2,376 件では候補索引名 `PRIMARY` のコピーが補充を引き起こした。残る24件は各 DB の最初の明細で、同じ索引名とリスト要素を既存ブロックに格納した後、同じ計画の別の要求で同じサイズを補充した。コピーを省いても、すぐ後に同じアリーナを使う要求が続く。差分加算も同じ索引名を2,400回保存したが、その計画区間での補充は0回だった。[経路別集計](summary.csv) · [同一アリーナの後続要求](arena.csv)

試作を支持する最大の材料は、前回の SUM トリガー CPU 標本の 66.2〜70.8% がこの経路のストア命令に集中したこと。今回は書き込み単体を直接計り、ページ状態を照会しない対照でも **100 INSERT あたり 0.022〜0.028 ms** だった。前回の同地点への帰属は 0.934〜1.030 CPU ms/100 INSERT。計測方法も分母も異なり、今回の経過時間から前回の CPU 帰属との差の原因や SQL の短縮時間は求められない。[前回の CPU 証跡と判定](https://github.com/masahitojp/mariamem/blob/7c5893b3d5198d2c5087dbb100e631dfe63a58bb/benchmarks/trigger-sum-bottleneck/results-20261121/T4.md)

## 何を確保していたか

注文 UPDATE は最適化後に計画を保存する。候補索引名 `PRIMARY` は、終端 NUL を含む文字列 8 B とリスト要素 8 B の2要求になる。SUM の各 DB の第2〜100明細では文字列要求が追加ブロックを必要とした。アリーナが `my_malloc` に要求したのは 8,160 B、ヘッダー込みで `__wrap_malloc` と `dlmalloc` に渡ったのは 8,176 B。前回の命令は文字列の書き込みとは別に、切り分けた残余空き領域のヘッダーを4 B更新する。文字列要求の直後に同じアリーナへの 8、44、8、3、8 B の要求が続いた。第1明細では、このうち 44 B の次の 8 B で補充した。[UPDATE の計画保存](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/sql/sql_update.cc#L642-L672) · [候補索引の列挙](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/sql/sql_select.cc#L31208-L31219) · [文字列とリストへの登録](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/sql/sql_explain.cc#L1757-L1767) · [アリーナ補充](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/mysys/my_alloc.c#L312-L357) · [実測した4 Bストア](https://github.com/masahitojp/mariamem/blob/5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c/internal/generatedgo/code/p1/p1_pure.go#L11783-L11793)

## 3組の結果

A は元の SUM、B は差分加算、C は明細 INSERT トリガーだけを削除した対照。各組は同一バイナリの独立3プロセス。各プロセスで 8 DB × 100 INSERT を実行し、4 DB でストア前後のページ状態を照会、4 DB で照会を外した。下表の時間は **各モードの全400 INSERT** を分母にした対象ストア時間の合計。B と C には他の呼出元から同じストアへの到達がある。

| 実行順 | 索引名のコピーでの追加確保 A / B / C（各800件） | SUM の対象ストア到達（照会あり / なし、各400件） | 照会ありで未常駐→常駐したストア | SUM のストア時間 µs/100 INSERT（照会あり / なし） |
|---|---:|---:|---:|---:|
| ABC | 792 / 0 / 0 | 396 / 297 | 43 / 396 | 24.115 / 21.563 |
| BCA | 792 / 0 / 0 | 396 / 396 | 42 / 396 | 25.469 / 28.365 |
| CAB | 792 / 0 / 0 | 396 / 396 | 42 / 396 | 22.063 / 27.344 |

第1組の照会なしでも文字列を契機とする追加確保は396回。99回は同じ dlmalloc 呼び出しの別経路を通り、このストアに到達しなかった。[全条件・全モード](summary.csv) · [生のリクエスト別記録](runs)

## ページと計時の照合

照会ありで対象に到達した1,188回中、127回（10.7%）が Mach disposition 0 → 13（常駐・参照・dirty）、1,061回が13 → 13。前者が対象ストアの計時合計の92.4%を占め、各組の中央値は1.83〜1.94 µs。後者の各組の中央値はタイマー分解能（41.67 ns）未満だった。対象のゲストオフセットは約645〜662百万バイトで、静的イメージの終端 27,754,496 B を越えた匿名領域にある。ファイルを私有マップした校正では初回書き込みが 141 → 45（external が消え copied が立つ）となった。対象の全ページでこの遷移は0回。観測は匿名ページの初回書き込みを支持する。個々のフォールトのカーネル内訳は計測していない。[ページ遷移](transitions.csv) · [校正用の初回・再書き込み・空計時](calibration.csv) · [静的イメージ範囲](https://github.com/masahitojp/mariamem/blob/5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c/internal/generatedgo/image/layout.json#L2-L6) · [匿名領域と私有ファイルページの構築](https://github.com/masahitojp/mariamem/blob/5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c/internal/generatedgo/code/base/static_pages.go#L19-L33)

## 検証と判断の限界

事前検査3プロセス・2,400 INSERT、本計測9プロセス・7,200 INSERT。全96 DBで登録済みトリガーの名前と本文、40注文の明細・合計、監査40件、在庫、FK/CHECK、Close を検査した。C の注文合計は投入前の値。各 INSERT と1回の対象 SQL の対応を確認した。実験は Apple M1 / macOS 27.2.1、16 KiB ホストページ、Go 1.27.4、P1。固定製品に対し診断ビルドだけに overlay と cgo タイマーを適用した。開発時にループバックの禁止による起動失敗が1回あり、接続可能な環境で事前検査から実施した。[ソースのコミット照合](identity.json) · [実行環境・バイナリ SHA-256](runs/environment.json) · [再現手順](recipe/REPRODUCE.md)

前回の独立 CPU 標本は全条件とも目標3,000に未達で、今回の計時はその分母に加えていない。計画情報は EXPLAIN の possible_keys 出力に使われる。次の判断を変える証拠は、同じ計画情報を保ったまま、SUM が1明細ごとに必要とした **アリーナの補充全体** を減らせるかどうか。続行する場合は、同じ MEM_ROOT の初期化・リセット・解放までのブロック寿命、再利用可能バイト数と補充全体の経過時間を同じ3組で照合し、費用を別の要求に移しただけの案は棄却する。既存ハーネスでビルド20分・再生15分を上限と見込む。CPU 標本基準の充足は別の長時間測定になる。[EXPLAIN JSON の候補索引出力](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/sql/sql_explain.cc#L2843-L2854)
