# main統合後のpgmem比較・投入内訳・PGOの採否

Go PGOの採用は見送る。今回の直列スイートで50 msの採用条件を満たさなかった。 主評価は元のSQL・同期Closeを含む70ケース全体のP1経過。mainは3831bd3c、pgmemはa61005d3、Apple M1・Go 1.27.4、GOMAXPROCS=8。P1/P8はテスト並列度。[開始条件](protocol.md) · [試作の判定条件](candidate.md)

## 通常版・直列6組

| スイート中の区間（ms） | main | pgmem | 対応差の中央値 |
|---|---:|---:|---:|
| 起動から最終Close | 1106.19 | 767.85 | 343.04 |
| データ投入21回 | 628.08 | 416.11 | 212.07 |
| Fork 21回 | 300.71 | 185.01 | 114.51 |
| 50読取 | 39.35 | 11.72 | 27.69 |
| 20更新 | 22.70 | 18.50 | 3.92 |
| Close | 40.55 | 1.75 | 38.85 |
| 起動 | 43.30 | 50.03 | -6.86 |
| 初期データ | 26.08 | 65.73 | -39.70 |
| Snapshot | 5.20 | 16.36 | -11.27 |

## 1投入あたり・診断用の別6組

| 区間（ms/1 DB） | main | pgmem | 対応差の中央値 |
|---|---:|---:|---:|
| 投入全体 | 30.16 | 20.11 | 10.01 |
| 親注文40行 | 4.37 | 3.04 | 1.32 |
| 明細100行 | 16.09 | 7.48 | 8.58 |
| 在庫更新100回 | 7.92 | 3.98 | 3.92 |
| Begin | 0.33 | 3.12 | -2.80 |
| 3文のPrepare | 1.14 | 0.54 | 0.60 |
| Commit | 0.12 | 1.74 | -1.62 |
| 残余 | 0.20 | 0.23 | -0.03 |

1プロセス21 DBの区間平均を作り、実行順反転6組の中央値を示す。Prepareは3文の合計。残余にはテストデータ生成、Goループ、終了処理、計時計算・診断出力を含む。エンジン間の差は実行系・ドライバも含み、Goで削減できる上限を確定しない。各区間の中央値は足し上げても全体の中央値と厳密には一致しない。[プロセス別入力](seed.csv) · [通常版各試行](trials.csv)

## 一つの変更を全体で検証

GoコンパイラのPGOを試した。明細と在庫予約は同じGo実行系を通るが、単独の既知の小処理（元の明細100件でJSON復号0.322 ms、索引候補評価0.494 ms）だけでは1投入あたり2.4 msに届かない。別4プロセスで学習したCPUプロファイルを固定し、同一ソース・同一検算の2実行ファイルをPGO offと指定プロファイルでビルド。評価にはCPUプロファイラとSQL別計時を入れず、既存スイートの経過を採用した。[学習標本](training-top.txt) · [対応値](candidate-pairs.csv)

| 指標（ms） | P1 | P8 |
|---|---:|---:|
| 通常のスイート中央値 | 1096.90 | 382.10 |
| PGOのスイート中央値 | 1116.20 | 428.51 |
| 対応短縮の中央値（正が改善） | -25.09 | -22.68 |
| 同一方式の再測定幅の中央値 | 16.86 | 35.42 |
| 短縮した組 | 1/6 | 0/6 |
| 通常 / PGO の6回相当の合計 | 6584.82 / 6707.49 | 2353.18 / 2706.08 |
| 通常 / PGO の観測最長 | 1115.61 / 1156.55 | 434.18 / 695.47 |

各並列度で通常→PGO→通常と逆順を交互に6組。1組で2回走った方式は平均し、遅い回もすべて含めた。通常main／PGO／pgmemで各注文合計・100明細・500商品の在庫・監査40件の独立検算。テスト本体は全70ケースの成功と50読取・20更新・21 Fork・21投入・21 Closeを確認。実験はビルド設定の単一候補に限定した。

## 再現手順

作業領域直下に固定mainのworktree、temp/gotmp、temp/pgに固定pgmemのクリーンなcheckout、evidence/runsと本レシピを配置。Go 1.27.4の依存モジュールを用意する。各ビルドの入力と実行ファイルのハッシュをJSONに保存した。

```sh
for arm in maria pg maria-diag pg-diag; do python3 -B evidence/recipe/build.py "$arm" || exit 1; done
python3 -B evidence/recipe/run.py base
python3 -B evidence/recipe/run.py diag
python3 -B evidence/recipe/reduce.py
python3 -B evidence/recipe/candidate.py train
python3 -B evidence/recipe/candidate.py build
python3 -B evidence/recipe/candidate.py measure
python3 -B evidence/recipe/decision.py
```

## 次点のForkで確認できた範囲

PGOを見送った後、同じmainとP1スイートで既存の起動時計を2プロセスだけ有効化した。42 ForkのAPI内経過の中央値14.55 msに対し、リンク済みゲストの実行開始→最初のreadyヘッダー受信は中央値13.95 ms、延べFork経過の96.1%。主な区間はゲスト起動からreadyまで。診断器のタイミングファイル書出しを含むので、採否の全体時間には使わない。[42 Forkの原表](fork-stages.csv)

server_init単体の時間は42件とも欠測。標準のReadGuestはホスト側transferパスから記録を読み、過去の診断は仮想FSのstartup-timing.jsonを取得する専用overlayを使った。旧版でserver_initが支配的との数字を現行に流用できない。次にForkについて判断を変え得る最小の作業は、この読出しを実験用に復元し、同じ21 Forkでモジュール準備・server_init・bootstrapの配分と、1 Forkあたり2.4 msを削れる具体箇所を特定すること。旧版のゼロ初期化試作には既に単体値だけではスイート全体の改善を示せなかった記録がある。今回の追加計測は2プロセスで終了。[以前の読出し実装](https://github.com/masahitojp/mariamem/blob/bb459758917ebb82842e57aed29ecbefc9d5a1a1/benchmarks/forkcost/results-20261113-current/overlay.py) · [以前のゼロ初期化比較](https://github.com/masahitojp/mariamem/blob/06022fa7253cd0de01f442fc194a58c763807abd/benchmarks/forkcost/buffer-zero-spike/README.md)

Fork確認の再現は、通常版のビルド後に実験ルートで `python3 -B evidence/recipe/fork.py`、続いて `python3 -B evidence/recipe/fork_summary.py` を実行する。
