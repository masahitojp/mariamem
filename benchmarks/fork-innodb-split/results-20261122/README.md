# 現行ForkのInnoDB起動とrollback segment復元

**rollback segment復元は、直列スイートを50 ms縮めるための主候補から外す。** 同じ70ケースの計測で、復元の中央値は1.54 ms/Fork、4試行の各中央値は1.39〜1.78 ms/Forkだった。84回中78回で2.4 msを下回った。中央値を21回分に換算すると全復元を省く仮定でも約32 ms相当で、復元処理にはデータ整合性のために必要な仕事も含まれる。旧版の約5.02 msとの絶対値の差はゲスト・環境・計測が異なり、CRC変更単独の効果量には使わない。[事前条件](protocol.md) · [旧版の復元内訳](https://github.com/masahitojp/mariamem/blob/397aaf82f5b52abb6a7c1e02bafcc0ce88d2b29c/benchmarks/trxstartupsplit/results/README.md) · [CRC高速化](https://github.com/masahitojp/mariamem/pull/125)

| 時間（ms/Fork、84回） | 中央値 | 最小〜最大 |
|---|---:|---:|
| MariaDB初期化 | 17.56 | 14.27〜49.93 |
| ├ InnoDB初期化 | 5.28 | 4.13〜18.56 |
| │ ├ InnoDBサーバー起動 | 5.22 | 4.08〜18.50 |
| │ │ ├ トランザクション一覧の初期化 | 1.62 | 1.41〜3.54 |
| │ │ │ └ rollback segment復元 | 1.54 | 1.34〜3.21 |
| │ │ └ 一覧の初期化以外の起動 | 3.56 | 2.67〜16.29 |
| ├ Aria初期化 | 2.46 | 1.89〜9.77 |
| └ 上記2プラグイン以外 | **9.81** | 8.18〜31.11 |

各Forkで親から子を引いたあと中央値を集計した。辞書の `dict_boot` は0.065 ms/Forkで、辞書関連処理の全部を表す値ではない。採用候補を探すなら、最大の未分類区間である**2プラグイン以外の9.81 ms**を優先する。ここにはほかのプラグインも含まれる。固定生成Goの `mysql_server_init` から `init_embedded_server` が呼ばれ、オプション読込、サーバー設定、システム表を使う処理などが存在する。既存の初期化境界を使い、プラグイン登録前後と残りのどちらに2.4 ms級の単独処理があるかを確かめるのが次の判断点。InnoDBを続ける場合の次点はトランザクション一覧以外の3.56 ms。現在の証拠で試作を選ぶ段階には達していない。[生成Goの起点](https://github.com/masahitojp/mariamem/blob/3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d/internal/generatedgo/code/p0/p0_pure.go#L46755) · [測定表](phases.csv)

## 計測と再現

Apple Silicon / macOS arm64 / Go 1.27.4、GOMAXPROCS=8、テスト並列度1。mainは3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d。既存のゲスト時計を仮想FSから取得し、生成Goの7関数を監査済みの関数表とprovenanceのハッシュに照合して、モジュールごとの時刻と回数を採った。Fork中の `mysql_server_init` 2回の時間和は、既存ゲスト時計の区間と全84件で0.25 ms以内。Aria、InnoDB、起動、辞書、一覧、復元は各1回。

標準、ホスト時計のみ、ゲスト時計と関数計時の3条件を各4回。全12プロセスで70ケース、21 Fork、21投入、21 Closeが通り、予備の注文監査・売上結果の意味検査も通過した。ゲスト計時ありのスイートは1.51〜3.79秒とばらつきが大きい。区間の大きさを選ぶ調査として使い、観測あり／なしの差を診断の費用や製品性能の変化には帰属させない。[試行データ](suites.csv) · [全区間の集計](summary.txt)

専用worktreeを固定mainとし、隣にtemp/gotmp、evidence/runs、evidence/recipeを用意する。監査の関数表を含む履歴とGoモジュールキャッシュを使う。

```sh
python3 -B evidence/recipe/overlay.py
python3 -B evidence/recipe/guard.py . 1400 python3 -B evidence/recipe/build.py observed
python3 -B evidence/recipe/guard.py . 1200 python3 -B evidence/recipe/build.py maria
python3 -B evidence/recipe/guard.py . 350 python3 -B evidence/recipe/measure.py
python3 -B evidence/recipe/reduce.py
```
