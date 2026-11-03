# Buffer-pool alignment：main 採用後の再計測

2026-11-03。**保持 RSS の削減は今回も再現したが、速度改善は確認できない。Fork CPU は4/5組で増えた。**
4子保持 RSS のペア差中央値は −4.03 MiB、1子は −1.19 MiB、いずれも5/5組で減少。
Fork CPU のペア比率中央値は +4.77%、wall は +2.01%。この増加を無害なノイズとは断定しない。
局所的な不要処理除去としての既存採用を記録し、今回の再計測はここで完了する。
CPU 増加の原因や新しい最適化候補の調査は、この計測に追加しない。

## 固定した比較

- 変更前 source_commit: `b7d4f90ece837a422d2ea8217dfd09a61ee7feaa`（PR #76 直前の main）。
- 変更後 source_commit: `ca7d6216bf662288ac326b693e9f272127657553`（PR #76 の squash merge）。
- 元 guest: `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`。
- 新 guest: `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`。
- Apple M1 / 16 GiB / macOS 27.2 arm64、Go 1.26.10、CGO0、GOMAXPROCS=8。
- 同じ TCP/mysql driver 1.9.3、InnoDB 1,000行、read/write/purge=1/2/1、native AIO=0。

source は双方 clean clone で commit object を確認後、同じ checksum-bound Go harness
を追加して計測専用 binary を作った。通常の canonical runtime をそのまま使い、実験用
binding、guest rebuild、observer は入れていない。比較する Go/assembly の差は generated
runtime と guest identity 定数に限られる。ビルドは既存方法と同じ `-trimpath -buildvcs=false`。
元 source identity、全 source inventory の commitment、同一 harness hash、binary hash と
実際の build info を [inputs](alignmentpostmerge/results/inputs.json) に記録し、完全な inventory は raw ref に保存した。
これは release host の identity receipt ではない。

ビルド・取得・root準備・Snapshot は時間から除外。各 mode は双方1 processの warmupを除外し、
その後 baseline→candidate / candidate→baseline を交互に5組ずつ fresh process で実行。
serial は process内4子の中央値を1観測として、5 processの中央値を示す。
保持 RSS は同じ process の baseline からの差で、各 checkpoint は GC＋500ms待機後に
`ps` の現在 RSS を採る。PSS/footprint/子ごとの専有メモリではない。
48子 batch は Fork・接続・SELECT1・COUNT/SUM・更新・検証・Close を含み、P4/P8を別集計する。
process CPU は背景 worker 分を含む。

## 今回の全5ペア

ペア差は candidate−baseline を組ごとに計算した5値の中央値。比率も各組で計算する。
variant の中央値同士の差ではない。負は費用減、正は費用増。

| 指標 | 変更前p50 | 変更後p50 | ペア差p50 | ペア比率p50 | 費用減の組 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fork wall (ms) | 41.512 | 42.471 | +0.841 | +2.01% | 2/5 |
| Fork process CPU (ms) | 53.142 | 55.174 | +2.536 | +4.77% | 1/5 |
| 1子保持 RSS増分 (MiB) | 78.000 | 76.812 | -1.188 | -1.52% | 5/5 |
| 2子保持 RSS増分 (MiB) | 156.312 | 154.219 | -2.125 | -1.36% | 5/5 |
| 4子保持 RSS増分 (MiB) | 312.781 | 308.656 | -4.031 | -1.29% | 5/5 |
| 48子 / P8 batch (ms) | 879.327 | 863.821 | -20.923 | -2.36% | 3/5 |
| 48子 / P4 batch (ms) | 1066.682 | 1057.836 | -0.694 | -0.07% | 3/5 |

[全ペアの値・差](alignmentpostmerge/results/summary.json) / [CSV](alignmentpostmerge/results/summary.csv) /
[全38実行の compact observations](alignmentpostmerge/results/observations.json)。

RSS は再現性のある小さな利点。4子の差を4で割った値を各子の限界費用とはせず、1子の直接観測も示した。
一方 CPU は4/5組、wall は3/5組で増加した。5組・非隔離 host の記述統計であり、
この差の因果や統計的有意差は決められないが、「ゼロ化を減らしたので CPU も減る」とは説明できない。

P4 のペア差中央値はほぼ横ばい。P8 は3/5組で短縮したが、各ペアの比率は
−39.36%から+54.60%まであり、並列性能の安定改善を主張しない。
これは「P4で頭打ち」を判定する並列度 sweep ではなく、既存 P4/P8 条件の再計測。
キュー遅延は測定対象外で、古い数値 Fn anchor を使っていない。

[前回の実験比較](https://github.com/masahitojp/mariamem/blob/964a4cabcb6f2b2b0fa6828319ae3c362dfc8908/benchmarks/buffer-alignment-source.md)
とは別 cohort。元の RSS 削減傾向は今回も見られたが、時間/CPUの数値を合成しない。
pgmem の同時実行を再計測しておらず、その相対速度・CPU/RSSは今回からは分からない。

## 正しさ・保存・再検算

計測30 process、warmup6 process、意図的な SQL oracle 失敗2 process の計38実行。
計測serial40子とbatch960子で初期データ・独立更新を検証し、全実行で Close 後の active
mapping/RW/reservation が0、owned scratch が空。意図的な失敗は双方で検出・回収した。
集計は欠測・重複・失敗隠蔽・leakの4変異を拒否する。

```sh
python3 benchmarks/alignmentpostmerge/analyze.py --check
```

compact observations だけで JSON/CSVを再計算し、checksumを読み取り専用で確認する。
ビルド/source/cache を参照せず証拠を書き換えない。

raw runner/harness、完全な source inventory、実行ログ、個別観測は専用 evidence ref
`evidence/alignment-postmerge-20261103` / `2a8f01625a105713778f4a4bc4318b9e989380db` の
[raw.tar.gz](https://github.com/masahitojp/mariamem/blob/2a8f01625a105713778f4a4bc4318b9e989380db/raw.tar.gz) へ分離。
SHA256 `8c3c5c2b59e2865b0a11bb5f30624ebc485ae0d595491df4fef4faf8031a9a44`（569619 bytes）。
publication.json は各ファイルの original/published hashを持ち、workspace prefixは
`<WORKSPACE>`へ正規化済み。再実行する場合は raw から evidence/compare.py、plan、Go harness を
新しい owned workspace へ戻し、fixed commitを取得した clean report worktree から
`python3 ../evidence/compare.py` を実行する。Go download/compile と localhost接続が必要。
raw内 analyze.pyには compact結果への明示的な `--results` を渡せる。

古い receipt を新 sourceへ貼り替えず、性能結果の main 採用・追加調査・Qualification・
版・公開は行っていない。報告は別ブランチでレビュー可能に残す。

owned product clones・binary・Go cache を約 1.95 GiB削除後にも、compact結果だけで JSON/CSVの読み取り専用再計算・checksum確認がPASS。
集計4変異と公開ソース検査もPASS。製品/runtime はこの計測で変更していない。
