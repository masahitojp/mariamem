# 照合順序ハッシュの先行確保を試す

**初期容量64→1024要素の試作は見送る。** 文字セット登録中の `my_realloc` は77→17回に減ったが、登録時間の対応差中央値は0.008 ms/Fork悪化。診断を外した直列70ケースの対応短縮中央値は0.34 ms、同じ設定を再測定した差は20.88 msで、6組中3組が短縮した。50 msは足切りに使わず、再測定幅と登録時間を根拠に判断した。[事前条件](protocol.md)

| 指標 | 初期64 | 初期1024 | 対応短縮中央値 | 同条件の再測定差 |
|---|---:|---:|---:|---:|
| 直列70ケース | 1,311.37 ms | 1,310.81 ms | +0.34 ms | 20.88 ms |
| スイート内の21 Fork | 351.35 ms | 351.56 ms | +2.24 ms | 8.34 ms |
| 診断時の登録時間/Fork | 1.982 ms | 1.967 ms | −0.008 ms | — |
| 診断時の登録中の再確保/Fork | 77 | 17 | 60回減 | — |

各条件列は組ごとの値の中央値、対応差は組内で計算してから中央値を取る。診断の各組では各プロセス21 Forkの中央値を使う。登録対象として計時した `add_compiled_collation` の呼び出し回数も両条件で一致した。登録初期容量を変えたのは照合順序名のハッシュ一つ。残る17回には同じ登録区間にある別の確保が含まれる。増分の初期要求サイズは要素12 B×960＝11,520 B/DB。プロセス最大RSSの対応中央値は+1.57 MiB、再測定差4.59 MiBで、実際の常駐差は分離できない。[スイート各組](pairs.csv) · [診断各組](registration-pairs.csv) · [Fork別](registration-by-fork.csv)

## 変更と検算

固定main 3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d。MariaDBの初期容量引数に対応する生成Goの `init_available_charsets` 内の1呼び出しを、プロセス開始時に設定する実験フラグで切り替えた。ハッシュ関数、登録順、動的伸長、XMLの経路は共通。照合順序一覧・文字セット一覧・既定値・非ASCII比較結果のダイジェストは両条件で一致した。セッションでの有効値と無効値、兄弟Forkへの非波及、既存の売上・監査検算を通過。全測定プロセスで70ケース、21 Fork、21投入、21 Closeを確認した。障害注入は含まれず、大きい初期確保の失敗時は別の検証が必要。[MariaDBの初期容量引数](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/mysys/hash.c#L80) · [対照の検算](oracle-0-0-control.log) · [候補の検算](oracle-0-1-reserve.log)

macOS arm64、Go 1.27.4、GOMAXPROCS=8、テスト並列度1。予熱後、通常比較は診断なしの同じバイナリで、交互に64→1024→64と1024→64→1024を実行し、2回測った方式を平均した（6組）。診断は別バイナリで順序反転の4組。壁時計は前回と同じ起動から最終Closeまで。比較はこの端末の短い直列モデルケースに限定した。

## 再現

固定mainのworktreeとtemp/gotmp、evidence/runs、evidence/recipeを同じ作業領域に配置する。

```sh
python3 -B evidence/recipe/overlay.py
python3 -B evidence/recipe/perf_overlay.py
python3 -B evidence/recipe/guard.py . 1400 python3 -B evidence/recipe/build.py observed
python3 -B evidence/recipe/guard.py . 1200 python3 -B evidence/recipe/build.py perf
python3 -B evidence/recipe/run.py oracle
python3 -B evidence/recipe/run.py perf
python3 -B evidence/recipe/run.py diag
python3 -B evidence/recipe/reduce.py > evidence/summary.txt
```
