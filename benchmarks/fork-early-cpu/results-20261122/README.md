# Fork時の設定完了前に使うCPU

**照合順序の既定対応表を作る処理が主要区間。表の解析省略だけで直列70ケースの50 ms短縮を狙う案は見送る。** `Charset_collation_map_st::from_text` は84 Forkで中央値2.500 ms。このうち1.571 msは文字セット名の検索5回、初回だけで1.565 ms。5回を除く残りは0.926 msで、21 Forkでは約19 ms相当。初回の検索で文字セット登録も動くため、表だけを事前に作っても登録の費用は、その後の検索で発生しうる。[対応値](collations.csv) · [条件](protocol.md)

| 開始から設定完了まで（84 Fork） | 中央値 ms/Fork | 4試行の中央値の範囲 |
|---|---:|---:|
| 区間全体 | 3.406 | 3.390〜3.508 |
| 照合順序の対応表を作る `from_text` | 2.500 | 2.491〜2.533 |
| └ 初回文字セット名検索 | 1.565 | 1.561〜1.589 |
| └ 文字セット名検索5回以外 | 0.926 | 0.917〜0.950 |

4試行とも全21 Forkで `from_text` は1回、その内側で `get_charset_by_csname` は5回。初回だけが文字セット全体の登録を実行する経路と整合した。固定版MariaDB 12.3.4の既定値は5文字セットをUCA 14.0の照合順序に結び付ける。最初の名前検索は `pthread_once` を通って `init_available_charsets` を呼ぶ。同じ一度限りの処理を、後続の文字セット検索も要求する。登録を遅らせるだけでは、スイート全体で減った時間には計上できない。[既定値と起動時の呼び出し](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/sql/mysqld.cc#L4439) · [対応表の処理](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/sql/charset_collations.cc#L55) · [名前検索と初期化](https://github.com/MariaDB/server/blob/e4549ea60c98a8743ed4743d7f92174d8a0005d9/mysys/charset.c#L998)

別の24プロセスのCPU標本では、対象ラベル171件中、呼び出し元も確認できた170件で集計した。115件が `from_text` 配下、そのうち70件で `get_charset_by_csname` と `init_available_charsets` の両方がスタックに現れた。同じ `from_text` 配下ではメモリ拡張が43件、UCA照合情報初期化が34件に現れた。これらは経路が重なるため足し上げない。CPU標本は経過時間に換算しない。[CPU帰属表](attribution.txt) · [上位スタック](cpu-cum.txt)

**次の試作を判断するには、文字セット登録で再利用できる静的データの範囲を先に確認する。** 現在の2.500 ms全体から目標の2.4 msを削るには約96%を省く必要がある。既存のUCA・lexer初期化の事前準備と重複を避け、既定の照合順序、エラー処理、可変設定を維持しながら、登録と後続検索を合わせて減らせる証拠が得られた場合に限り試作を提案する。今回の計測では、目標を裏付ける単独の変更は選ばなかった。

## 再現

固定main 3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d、Go 1.27.4、macOS arm64、GOMAXPROCS=8。前回と同じ直列70ケース（21 Fork、21投入、21 Close）。同じ診断用バイナリでホスト時計のみと詳細計時の順序を替えて4組。別の24プロセスで、組み込み初期化の開始→設定完了だけをCPUラベルで記録した。各試行でベンチの既存テストと回数検査が成功した。詳細計時の経過は前回とは独立の試行で、問題箇所を絞るために使用した。

固定ソースのworktreeと監査済み関数表を含む履歴、temp/gotmp、evidence/runs、evidence/profiles、evidence/recipeを用意する。出力先が空の状態でlocalhostのDBを起動できる環境から実行する。

```sh
python3 -B evidence/recipe/overlay.py
python3 -B evidence/recipe/guard.py . 1400 python3 -B evidence/recipe/build.py observed
python3 -B evidence/recipe/measure.py times
python3 -B evidence/recipe/reduce.py > evidence/timing-summary.txt
python3 -B evidence/recipe/measure.py profiles
sh evidence/recipe/profile.sh
python3 -B evidence/recipe/source_lines.py > evidence/cpu-source.txt
python3 -B evidence/recipe/attribute.py > evidence/attribution.txt
```
