# Issue63：正規ソースから作った整列候補の比較

2026-11-02。**重複ゼロ化の除去と小さな保持RSS削減は確認。速度・CPUの改善は一貫せず、
総合改善／製品採用は判定保留。** この条件で「速くなった」として採用することは推奨しない。
局所的な無駄除去・メモリ改善候補として記録を残し、今回の有限比較は終了する。
最も強い反対論は、時間が4/5ペアで短くRSSも全ペア減ったため狭い修正を採る価値があること。
その価値は残るが、CPUとバッチの悪化例、欠測キューと未検証platformを相殺する証拠ではない。

## 条件とsource

Apple M1/16GiB/macOS27.2 arm64、非隔離のローカルhost。
Go1.26.10、CGO0、GOMAXPROCS8。同一Go host source、mysql driver1.9.3、TCP、
1,000行の同じschema/seed、read/write/purge=1/2/1、native AIO0。
MariaDB12.3.3は同じだがguestビルドidentityは異なる。

- mainの元runtime: `c4742390cf4553636ceaa23c6732d48f76a37c9c`。
- guest build source_commit: `d86153409067e6ad868b566872a3c4a9495ef5f7`。
- host-stage source_commit: `6460e64561be5779c837657bcc56993fb1f99f75`。
- 元guest: `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`。
- 新guest: `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`。

元版はこの同じhost sourceに付属する採用済みgenerated Go、候補は今回のguestを通常converter/
installerで再生成したGoを使う。比較前のproduction source差はgenerated runtimeとguest identity
constantだけであることを照合。同じ計測harnessを両方へ追加した。source inventory、生成差分、
compiler情報、binary hashは[inputs](bufferalignmentsource/results/inputs.json)に記録。
以前のGo1.27.3 overlay比較とは別cohortで、その数値を今回へ合成しない。

## 全5ペアの結果

各modeでwarmupを各variant1process行い除外。その後、元→候補、候補→元を交互に5ペア。
直列modeはprocess内4子の中央値を取り、その5processの中央値を示す。
RSSは同processのbaselineからの差。各checkpointで同じGCと500ms待機後にpsの現在RSSを採取。
RSSはPSS/footprint/各子の専有物理メモリではない。背景worker CPUをprocess CPUから分離しない。
48子batchは全子のFork→接続/SELECT1→COUNT/SUM→UPDATE/SELECT→Closeを含み、
root準備/Snapshot/build/downloadを除外する。P4とP8は別集計。

「ペア差」は対応するcandidate−baselineの5値の中央値であり、variant中央値の差ではない。
負の値は費用減。5組の記述統計であり有意差・普遍的な悪化許容幅の証明ではない。

| 指標 | 元版p50 | 候補p50 | ペア差p50 | ペア比率p50 | 改善ペア |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fork wall (ms) | 37.334 | 37.211 | -0.826 | -2.25% | 4/5 |
| Fork process CPU (ms) | 47.364 | 48.403 | +0.500 | +1.06% | 2/5 |
| 1子保持RSS増分 (MiB) | 77.766 | 77.000 | -0.734 | -0.94% | 5/5 |
| 2子保持RSS増分 (MiB) | 156.000 | 154.125 | -1.688 | -1.08% | 5/5 |
| 4子保持RSS増分 (MiB) | 312.375 | 308.672 | -3.500 | -1.12% | 5/5 |
| 48子/P8 batch (ms) | 962.189 | 808.129 | -7.288 | -0.93% | 3/5 |
| 48子/P4 batch (ms) | 1042.605 | 1095.146 | +129.444 | +11.56% | 2/5 |
| 子最大キュー待ちp95 / >100ms件数 | N/A | N/A | N/A | N/A | N/A |

P8のvariant中央値は962→808msだが、ペア差の中央値は−7.29ms（−0.93%）。
2ペアは+354/+384ms遅く、中央値の差だけで約16%のspeedupとは主張しない。
P4は3/5ペアで遅く、候補の最大1,627.9msも残す。CPUも3/5ペアで増加した。
ホスト状態・稀なSQL待ち・候補差のどれが寄与したかはこの計測から分からない。

4子RSSは全ペアで3.31〜5.05MiB減り、ペア差p50は−3.50MiB。
1子の直接差は全ペアで減り、ペア差p50−0.734MiB。4子合計÷4を各子の限界費用とはしない。

全値・ペア差は[summary.json](bufferalignmentsource/results/summary.json)、
[CSV](bufferalignmentsource/results/summary.csv)、
[全38実行の観測](bufferalignmentsource/results/observations.json)に残す。
キューは新guestに観測点を再bindしておらず欠測。古いFn番号を流用せず、
4指標の総合採用判定は **INCONCLUSIVE** とする。

## 機構・正しさ

別の観測付きpilotを両variant各1process（4子ずつ）実行した。全子で、16MiB+17.707MiBの
大きなゼロ化2回が、16MiBの1回になった。候補の対象アドレスは全て2MiB整列。
観測付き時間は上のplain比較へ含めない。
[各子のbytes/address/呼出しstack](bufferalignmentsource/results/zero-mechanism.json)。

実guest buildは989.55s（取得・準備含む）で成功。C/C++4ファイルの実prepared hashは
host contract検査の値と一致。最初のnative installationは新guestをcanonical ABI guardが拒否した。
Fn153/Fn131/Fn214の関数全体は既存hashと全て一致しており、実験用adapterだけがexact新guestへ
process内でbindする。通常の製品用guard・release入力は変更していない。
新guestからのhost buildと既存SQL/transaction/Snapshot/Fork/Close smokeはPASS、UNQUALIFIED。

focused Python46 PASS（5つの新binding検査を含む）。測定40子のpristine/独立更新、
960batch子とwarmupのSQL oracle、Close後active mapping/RW/reservationゼロ、owned scratch空を確認。
意図的なSQL oracle失敗は両variantで検出・cleanup。集計の欠落/重複/失敗の隠蔽/leakの4変異を拒否。

wrapperの相対path、write-threadの誤った想定、残った空scratchによる事前起動FAILを保存した。
write=2の実既定値へ検査を合わせたのは最初の測定ペア以前。guest/hostの設定は変えず、
失敗した測定ペアを捨てたり、結果が良くなるまで繰り返したりしていない。

## 保存・再検算・残件

[採用前のsource計画](../docs/reviews/issue63-buffer-alignment-candidate.md)と
[#63](https://github.com/masahitojp/mariamem/issues/63)が実装残件を管理する。
Ubuntu、実WASIXの確保失敗/低メモリ、キュー分布と正規採用bindingは未完了。
この結果からscopeを追加せず、追加検証の投資と採用は別に判断する。

```sh
python3 benchmarks/bufferalignmentsource/analyze.py \
  --results benchmarks/bufferalignmentsource/results --check
```

この読取り専用再検算はtempやbuild出力を参照せず、証拠を書き換えない。
raw commands、実行用harness/runner、full source inventory、最初のFAIL、観測付きpilotは
専用evidence ref `evidence/buffer-alignment-source-20261102`、commit `cc04b6925bc9df7b42826b86ca4c0de08aaf903f` の
[raw.tar.gz](https://github.com/masahitojp/mariamem/blob/cc04b6925bc9df7b42826b86ca4c0de08aaf903f/raw.tar.gz)へ分離。
SHA256 `07d5e1e9be211e50ba19b0557bc32257be09affd02d1b0590703678fe7f949df`（2253489 bytes）。
archive内publication.jsonは元bytesと公開bytesのhashを記録し、owned workspace prefixを
`<WORKSPACE>`へ正規化する。主報告にSDK・guest・binary・全ログを凍結しない。

実行を再現する場合は、guest source d8615340をexact experiment branchで単発buildし、
host stage6460e645へ進めて既存のorigin再検証を通す。archiveのevidenceへ保存したrunner/sourceを
同じowned workspace配置へ戻し、workspace prefixを実際のtask pathへbindする。
`comparison-plan.json`でfixture/5ペア/Go1.26.10を固定し、dev-native-reboundから
`compare.py`、次に分離した`observe.py`を実行する。正規guestの再buildとsource identity照合は
既存development guideに従う。公開済みreceiptを新しいsourceやhostのPASSへ貼り替えない。

このcheckpointはmain統合・Qualification・公開を行わない。owned SDK/source/generated/binary/
cacheの削除と保存済みcompact結果の再検算を完了してから作業を終了する。

owned SDK/source/generated/binary/cache約7.3GiBを削除後、compact結果だけで読取り専用の再検算とchecksum確認がPASS。nested converterの空Git初期化2個は、固定archive＋13patchから全ファイルを再構成し一致・ref/commitなしを確認して削除した。public-source checkは6,643files PASS。
