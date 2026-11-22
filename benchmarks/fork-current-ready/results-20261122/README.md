# マージ後mainのFork初期化を計測

**直列70ケースを50 ms短縮する次の調査対象は、Fork時のMariaDB初期化（server_init）内部。今回の計測からは、1 Forkあたり2.4 msを削れる具体的な変更は選べなかった。** 84 Forkすべてでゲスト時計を取得し、server_initは中央値13.88 ms、Fork API全体は16.45 ms。延べFork時間の83.9%がserver_initだった。ホストのprepared handle割り当てとモジュール準備は合計で中央値0.46 ms。この2区間をすべて省いた場合でも、21 Forkで約10 ms相当となる。[事前条件](protocol.md) · [各Forkの計測値](forks.csv)

| ゲスト時計を回収した84 Forkの区間 | 中央値 |
|---|---:|
| Fork API全体 | 16.45 ms |
| ホストのprepared handle割り当てとモジュール準備 | 0.46 ms |
| ゲスト実行開始からreadyヘッダー受信まで | 15.26 ms |
| MariaDB server_init | 13.88 ms |
| server_init完了からbootstrap完了まで | 0.10 ms |
| ルーチンスキーマ処理 | 0.92 ms |

実行開始からreadyまではserver_initやルーチンスキーマ処理を含む。ホストとゲストは別の単調時計を用い、各時計の開始・終了の差で集計した。4プロセス別のserver_init中央値は13.17、13.37、14.11、14.05 ms。標準版のスイート中央値は1,265.14 ms、ホスト時計のみは1,368.39 ms、ゲスト記録回収ありは1,282.92 ms。試行間にばらつきがあり、今回の診断値は処理の優先順位に使った。短縮量は独立した通常ビルドでの比較が必要。[試行別のスイート結果](suites.csv)

## 次に判定する箇所

server_initの中では、InnoDBの起動・復元を一段だけ分けるのが有力。旧版ではrollback segment復元に約5.02 ms、その経路の読み込み完了処理の大半はCRC32Cだった。CRC高速化は現行版に入っており、旧版の5.02 msを今の削減余地には使えない。バッファプール初期化の旧試作でも、直列Forkの短縮は約1.26 msでスイート全体は短縮しなかった。今の生成GoでInnoDB起動のうちrollback segment復元と残りを分け、2.4 ms級の処理に絞れれば初めて試作を提案する。[旧版の復元内訳](https://github.com/masahitojp/mariamem/blob/397aaf82f5b52abb6a7c1e02bafcc0ce88d2b29c/benchmarks/trxstartupsplit/results/README.md) · [CRCの既採用変更](https://github.com/masahitojp/mariamem/pull/125) · [バッファプール試作](https://github.com/masahitojp/mariamem/blob/06022fa7253cd0de01f442fc194a58c763807abd/benchmarks/forkcost/buffer-zero-spike/README.md)

## 再現

mainは3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d、macOS arm64、Go 1.27.4、GOMAXPROCS=8、テスト並列度1。マージ後の70ケースと同じ入力を利用。標準版、ホスト時計のみ、ゲスト時計の回収ありを順序を変えて各4回。全12プロセスで70ケース、21 Fork、21投入、21 Closeを検査し、予備試験で既存の意味検査も通過した。診断版は以前の仮想ファイルシステムからの回収を現行APIに合わせ、既存のゲスト時計を読み出した。細分化した初期化カウンターはこのゲスト時計に含まれていない。

ワークスペース直下に固定コミットのworktree、temp/gotmp、evidence/runs、および本レシピを配置する。ローカルDBを起動できる環境で実行する。

```sh
python3 -B evidence/recipe/overlay.py
python3 -B evidence/recipe/guard.py . 1400 python3 -B evidence/recipe/build.py observed
python3 -B evidence/recipe/guard.py . 1200 python3 -B evidence/recipe/build.py maria
python3 -B evidence/recipe/guard.py . 350 python3 -B evidence/recipe/measure.py
python3 -B evidence/recipe/reduce.py
```
