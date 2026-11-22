# Forkの組み込みサーバー初期化を区間別に計測

**初期化開始から「設定完了」マーカーまでの4.14 ms/Forkが、InnoDB・Ariaを除いた最大区間。** 設定ファイル読み込みとオプション解析を合わせると、その区間で0.12 ms。ホットスポットをさらに探すなら、同じ区間に残る4.03 msを対象とする。今回の結果から、直列スイート50 msの短縮に向けて1 Forkあたり2.4 msを削れる具体的な変更は選べなかった。[事前条件](protocol.md)

| `init_embedded_server`の排他的区間 | 中央値 ms/Fork | 4試行の中央値の範囲 |
|---|---:|---:|
| 開始から「設定完了」 | **4.14** | 3.98〜4.26 |
| └うち `my_load_defaults` と `handle_options` | 0.12 | 0.11〜0.12 |
| └上記2関数以外 | **4.03** | 3.86〜4.14 |
| MyISAMキーキャッシュ初期化 | 1.45 | 1.40〜1.51 |
| プラグイン初期化（InnoDB・Ariaの実測時間を除く） | 1.81 | 1.68〜1.86 |
| プラグイン完了からDDLリカバリ完了 | 0.21 | 0.20〜0.21 |
| DDLリカバリ完了から組み込み初期化完了 | 0.72 | 0.69〜0.74 |
| その他の各境界間 | 各0.04以下 | 最大0.05未満 |
| **組み込み初期化全体からInnoDB・Ariaを除いた値** | **8.49** | 8.08〜8.55 |

列の値は各Forkの区間または差を計算してから中央値を取った値。全体行を各中央値の和としては扱わない。開始から設定完了までに両プラグインの実行はない。プラグイン区間全体は8.67 msで、InnoDB 4.56 ms、Aria 2.20 msを各Forkで除いた。MyISAMの1.45 msはほぼ `init_key_cache` に対応し、管理情報のゼロ初期化を含む。システム表を開いてロックする `open_and_lock_tables` は関数単位の和で0.046 ms、`servers_reload` は0.038 ms。これらは経路中の計測値で、システム表処理全体の費用を表さない。[区間別CSV](intervals.csv) · [関数別CSV](functions-by-fork.csv)

## 次の判断

最も大きい4.03 msには、生成Goの設定準備、ステータス変数登録、文字集合・照合順序の解決など複数処理が入る。次の計測を行うなら、この区間だけのCPUスタックまたは生成Go内の境界を取り、繰り返し省ける単位があるかを確認する。固定コードの呼び出し箇所は `init_embedded_server` の既存マーカー間にある。キーキャッシュと他プラグインを個別に全て省く仮定はいずれも2.4 ms未満。これらを除去する試作は推奨しない。[固定生成Go](https://github.com/masahitojp/mariamem/blob/3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d/internal/generatedgo/code/p0/p0_pure.go#L46755) · [キーキャッシュ初期化の既存調査](https://github.com/masahitojp/mariamem/blob/cb4f43f9f2ec46a1afc79048b8689b1a46636ff2/benchmarks/forkcost/caller-map-20261113/README.md)

## 計測と再現

main 3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d、macOS arm64、Go 1.27.4、GOMAXPROCS=8。標準、ホスト時計、ゲスト時計と関数計時を順序を変えて各4回。同じ70ケース、21 Fork、21投入、21 Closeを全試行で通過し、別の予備試験で既存の意味検査を通過。84件すべてで既存マーカー9個の順序と、区間の合計を検査。生成Goの15関数はguest・関数表・元ソースのハッシュを確認し、対象モジュールの時刻を記録した。区間と関数の時刻は同じホスト単調時計。独立したゲスト時計とも全84件で0.25 ms以内で一致した。`mysql_server_init` は組み込み初期化の外側にあるため、その時間は2回の全範囲を示す。他の関数は組み込み区間内の呼び出しを集計した。

前回の9.81 msと今回の8.49 msは別キャンペーンかつ集計範囲が異なる。今回の実行は区間ごとの優先順位を付けるために使い、製品の性能差や50 ms短縮の実証には通常版の独立比較を使う。[各スイートの経過時間](suites.csv) · [中央値と範囲](summary.csv)

固定mainのworktree、temp/gotmp、evidence/runs、evidence/recipeをワークスペース直下に用意し、localhostのDBを起動できる環境で実行。

```sh
python3 -B evidence/recipe/overlay.py
python3 -B evidence/recipe/guard.py . 1400 python3 -B evidence/recipe/build.py observed
python3 -B evidence/recipe/guard.py . 1200 python3 -B evidence/recipe/build.py maria
python3 -B evidence/recipe/guard.py . 350 python3 -B evidence/recipe/measure.py
python3 -B evidence/recipe/reduce.py > evidence/summary.txt
```
