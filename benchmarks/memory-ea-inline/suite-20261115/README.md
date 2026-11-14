# MemoryEA候補: 全体suiteの3者比較 — 2026-11-15

**結論: 通常の元SUM/70test suiteでも候補の全体短縮を支持する。P8では比較対照と中央値が近いが、差の変動が大きく安定同等とはまだ言えない。** 候補対baselineはP1/P4全5組、P8の4/5組で短縮。CPUは全15組で減少。局所INSERTだけの改善ではなかった。

## 固定対象・条件

source_commit25d70adf6c942bd147f43683916a5b1f9e09218d。baseline runtimeはbb1e937ae75b5788c8548a52987d9d42f78292d5と同一（baseline-runtime-diff.txt空）。候補は前回正規installerの生成baseを一行変更＋unused trap helper削除から復元し、前回installed-provenanceのhash一致0170988abb28903ff3824a0e5efbe7865b0ba4961a892de7ce5bfca842ba332aを確認してoverlayで使用。他runtimeは同一で、全面再生成/installerを今回再実行したとは主張しない。guest77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450。比較対照shibukawa/pgmemv1.18.2、module Origin.Hash a61005d37d01e6671f814fe8ca828222e8147df4を確認。

既存c09941e25ea8ca9ae77ea032d61a3268b72c7e50の条件合わせ済みharness。対照module/依存がGo1.27を要求するため、全3者Go1.27.4/macOS arm64/CGO0/GOMAXPROCS8/GOGC100の新cohort。前回の製品Go1.26.10専用probe値と差し引かない。共有Mac。

元SUM trigger、監査UPDATE OF status、既定16MiB、補間DSN、同じFK/CHECK/indexとname_lower、事前集約売上SQL REVENUE_PREAGG=1。共有readerは両側Snapshot後Fork。既存Maria harnessが元parentを閉じずsrv変数を上書きしていたため、今回Closeしてからreader Forkするよう対照へ合わせた。Closeエラーも両側失敗へ昇格。差分保存。観測hook/Module追加fieldなし。全10scenario/70body/20writerFork/21sampleを維持。

P1/P4/P8、各3者warmup1＋5round、実行順回転=54process。全process成功、70test body/20writer Forkをtraceで確認（計3780body、1080writerFork）。全標本保持、追加反復なし。build/依存取得を測定に重ねていない。

## 全体時間

単位ms、5processの独立中央値。suite elapsedはtrace RecorderのTestMain開始→Close後、process wallは実行起動→time wrapper終了まで。

| 並列度 | baseline suite | candidate suite | 対照suite | baseline process | candidate process | 対照process |
|---|---:|---:|---:|---:|---:|---:|
| P1 |1318.431|1176.639|852.964|1356.548|1217.338|914.532|
| P4 |684.280|630.075|506.333|744.103|659.025|648.507|
| P8 |627.325|555.889|574.436|669.210|610.907|658.633|

| 対応round比較・suite elapsed | P1 | P4 | P8 |
|---|---:|---:|---:|
| candidate−baseline 差中央値ms | -164.380|-58.235|-114.260|
| 同変化率中央値 | -12.47%|-7.60%|-16.80%|
| 候補が速い組数 |5/5|5/5|4/5|
| baseline対比較対照・率中央値 |+58.13%|+37.04%|+18.15%|
| candidate対比較対照・率中央値 |+35.74%|+24.44%|-1.70%|

独立中央値の差/比と対応差/率の中央値は異なる。P8候補対baselineは1組+1.82%悪化を保持。P8候補対対照は3/5組だけ速く、対応差-230.080〜+108.764ms、率-31.42〜+20.52%。対照自体のsuite値494.302〜732.351msと変動が大きい。単一runを除外せず、安定同等/目標10%達成/優位は断定しない。P1/P4では候補も対照より全5組遅い。

## 内訳

各process内の区間中央値を5processで中央値化。P8・ms。forkは20回、sampleは21回、test bodyは70回の分布。並列区間は重なるので加算しない。区間中央値差から全体改善の厳密な寄与量を算出しない。

| P8区間 | baseline | candidate | 対照 |
|---|---:|---:|---:|
| boot |51.380|51.015|60.876|
| schema/master import |35.696|26.558|78.597|
| Snapshot |6.268|5.701|19.790|
| reader Fork |18.359|15.111|12.085|
| writer Fork・1回中央値 |40.821|38.163|38.947|
| sample load・1回中央値 |117.525|79.512|65.302|
| test body・1回中央値 |2.740|2.159|0.923|

P1のwriter Fork中央値15.336→13.618ms（対照10.125）、sample36.663→31.878ms（対照21.025）。P4はFork27.797→26.519ms（対照22.869）、sample62.265→52.554ms（対照36.082）。sum_msもsummaryに保存するがwallとして扱わない。sampleは100明細INSERTだけでなく40注文/100在庫UPDATE等を含む。

CPU全体中央値ms: P1 1781.760→1606.954（対照1078.785）、P4 2521.782→2180.679（対照1527.274）、P8 2960.171→2411.372（対照1707.553）。候補対baseline対応率中央値-11.87/-16.31/-18.54%、全組低下。P8候補対対照CPUは対応中央値+41.19%で、wall接近はCPU費用同等を意味しない。最大RSS rawと集計も保存。

非strip test binary baseline110946866→candidate192846274bytes、約73.82%増。対照68091634bytes。配布host/wheelサイズではない。

## 判断・限界

候補を受入れ検討へ進める価値を支持する。全体suiteにも利益が出たことが決め手。最も強い反対材料は約74%binary増加とCPU残差で、P8中央値の接近だけでは解消しない。次の判断は配布host size/cold費用を含め候補化を進めるか。両OS/fullconsumer受入れ・main採用・releaseは未実施。別候補を自動探索しない。

再現: 固定sourceからworkspace memory-ea-suiteをprepare8GiB/最低空き8GiB。Python3.14でbuild.py→measure.py→analyze.py。buildはhelper監視（各1200秒）。measureは個別180秒/campaign900秒と各process開始前空き8GiB検査、helperの継続監視ではない。traceを含む全標本とbinary/source/moduleidentityを保存。失敗ビルドなし。rootの既存ユーザー変更は維持。固定証跡push後、temp/worktreeをcleanupする。
