# B1 measurement repeatability: same-binary A/A

**結論:** B1の短いcycle計測は、変更のない同一baselineでも大きく揺れる。48cycleではペア比の絶対値中央値5.85〜45.94%、480cycleでは1.23〜17.80%。処理量を10倍にすると全6条件でこの指標は低下したが、長い条件にも外れ値が残った。前回の「不安定」を候補の性能だけに帰属することはできない。

推薦: B1の速度採否は未確定を維持。再比較を選ぶなら、64MiB/480cycleを中心に同時期のA/Aを織り込む有限A/B計画を先に固定する。今回のA/Aを過去のA/Bから数値的に差し引いたり、過去の改善を実証/否定する用途に使わない。測定方法の再現性を検査した結果であり、mapping resetの採用判断ではない。

## 固定条件

Measured source_commit `526fd31f70d0f21cdd28b5f562acb7308f91e55e`、B1 base c5f4ad43f5a1de57f8b758f7bd8e13505d5451ed。同じ絶対パスの同一binaryを両labelで起動し、同じcellの引数・envは完全一致。labelはrunner出力だけでguest/testへ渡していない。複製binary・別build・reset候補は使用しない。ソースclean/git_identityをbuild前に確認。buildinfo/hashとimage hash/rangesはinputs/binary JSON。

Go1.26.10 darwin/arm64、CGO0、GOMAXPROCS8/GOGC100。B1と同じ2GiB予約・256MiB初期image・320MiBへのgrow、ページごと1byteのdirty0/1/64MiB。P1/P2、workerごと48/480cycle。reserve/overlay/grow/dirty/unmapと最終解放をbatch wall/CPUへ含む。各cell1warmup＋6ペア、計12warmup＋144measurement=156プロセス。6repでA→A-primeとA-prime→Aを交互、cell順はseed119固定shuffle。150ms間隔。除外/追加samplingなし。

全156実行が成功し、creates/releases件数とactive mapping/reserved/RW復帰を確認。実行総cycle数61776。今回はbaselineの計測ハーネス変更だけで、reset安全性/raceを再実行する必要はなく実施していない。実SQL・guest実行は含まない。

## A/A結果

各ペアは100×(A-prime/A−1)。下表はその**絶対値の中央値**と最大値。信頼区間・標準偏差・一般的なノイズ上限ではない。分母がAなので絶対比率も完全対称な距離ではない。signed比率と絶対ms、先行/後行差もsummary.jsonに保持。

|P|dirty MiB|48cycle 絶対比中央値|480cycle 絶対比中央値|48cycle 最大絶対比|480cycle 最大絶対比|
|---|---:|---:|---:|---:|---:|
|1|0|45.94%|17.80%|159.01%|41.47%|
|1|1|19.49%|3.33%|107.99%|15.03%|
|1|64|8.71%|3.44%|14.78%|10.21%|
|2|0|44.81%|11.22%|77.10%|105.13%|
|2|1|35.53%|6.85%|114.57%|14.17%|
|2|64|5.85%|1.23%|22.31%|7.60%|

P2/64MiBの480cycleではsigned差中央値+0.04%、絶対差中央値1.23%、最大7.60%。一方P2/0MiBの480cycleは最大105.13%。長くすれば必ず安定するわけではない。64MiBのbatch中央値はP1約252→2369ms、P2約312→2904ms。0MiBは480cycleでも約50ms程度で依然短い。

0MiB/48cycleには第2実行が遅い傾向（second/first中央値P1+93.90%、P2+30.05%）があるが、他条件に共通しない。先行labelを交互にしただけで全ばらつきが除去されたとはしない。CPU、page fault、context-switch値を全runへ保存したが、CPU配置・周波数・VM lock・アドレス配置・ホスト負荷の寄与を分離する実験ではない。

minor/major faults等はwait4の**プロセス全体**値で、batch限定ではない。64MiB/480cycleのminor faultsはP1約196.7万、P2約393.3万でrun間件数は近いが、同じ件数から同じ待ち時間や因果は導けない。major fault0のrunでもばらつきはあり、ディスクI/Oだけで説明できるとはしない。load averageとUTCは記録しているが電源・温度・CPU周波数は統制していない。

## 今後への含意・再現

A1aやA2の測定値は別workload/時点なので、このノイズ幅をそのまま適用しない。B1の64MiB候補が効く可能性は残るが、過去3ペアの−5.86/−12.12%を確定利益と扱わない。続ける場合の候補は、より長いbatch＋同時期A/A付きA/B。今回から自動で実行しない。

run.py <workspace>でfixtureを完全hash照合し、1binaryをbuild、固定156runを実行。analyze.pyは同ディレクトリruns.jsonを再集計。guard5400秒、scratch12GiB/free12GiB。原本からのruntime差分はtestのcycle数入力だけ。全raw値・入力・binary identityを保持し、再生成可能なimage/cache/worktreeは完了後cleanupする。main統合・製品採用・releaseなし。
