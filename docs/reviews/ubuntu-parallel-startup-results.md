# Ubuntu 10MiB parallel startup — bounded result / Human Review

## Human Review（提出時）

**推薦：この限定調査の結果を受理し、guest初期化の改善方式選定は予定どおりv0.7.xへ渡す。**
4子を並列に用意すると1子の待ちは延びるが、4テストの処理全体は約541→263msへ短縮した。
SQLを全子ready後まで止めてもForkの遅延は残り、今回の主要因は起動同士の実行資源の共有である。
後続SQL/Closeとの重なりを取り除く対策を、主な起動改善策として選ぶ根拠は得られなかった。

**最も強い反論：CPUの順番待ち・SMT・キャッシュ・メモリ帯域の寄与を個別には確定していない。**
そのため特定のguest関数を直せば何ms速くなるか、旧139.77msの絶対値がなぜ違うかまでは答えない。
ただし今回の目的である「起動同士か、他の子のSQL/終了か」は対照条件で切り分けられた。
実装の選定・最適化の採用は今回の判断に含めない。調査結果はHuman受理待ちで、main統合も未承認。

## 入力・証拠・完了判定

- [承認済みの範囲・32試行](ubuntu-parallel-startup-study.md)。新しい実験・修正を追加せず、終了したCIを解析した。
- [run 39099563649](https://github.com/masahitojp/mariamem/actions/runs/39099563649)、job117592859351は全step成功。
  source_commit `4e73abe126672869ad03575e84706b5ab2cb557c`。
  product baseline `3f514ebf14fbbe6aca6ba77d00a1bb6cdb35163d`との相違はbenchmark/workflow/docsのみ。
- 同じGo1.26.8・CGO0 binary、MariaDB12.3.3 guest、10MiB/8 tables/4 children。
  binary SHA256 `9c1c2a54790d4be8bb8f5b9feb7d161ea513fda67df09520bd524aaebb219dbd`。
  [receipt](ubuntu-parallel-startup-evidence/native/receipt.json)のcommit型、clean VCS刻印、実行前後identityが一致。
- [保存manifest](ubuntu-parallel-startup-evidence/native/manifest.json)にGitHub artifact ID/digestと133原本のhashを記録。
  GitHub ZIPのdigestはAPI記録値で、ローカルZIP照合済みとはしない。
  [圧縮原本](ubuntu-parallel-startup-evidence/native/evidence.tar.gz)はJSON・ログ・profile・traceを含む。
  別のtar.gzとして保存し、そのhashと各展開fileのhashを検証した。
- reducerを保存原本へ独立実行し、全32 case・出力hash・fixture・operation順・barrier・binary identityを再検査。
  [analysis.json](ubuntu-parallel-startup-evidence/native/analysis.json)と完全一致（PASS）。
- SQL/commit/rollback/親子隔離・切断/Close/cleanupの既存oracleは32試行ともPASS。
  scheduler race unitは3回PASS、Pythonは25 tests/12 subtests PASS。これは今回の利用条件の確認で、Release Qualificationではない。

| 依頼された項目 | 判定 | 根拠と限界 |
| --- | --- | --- |
| 起動同士か、先行子SQL/終了との重なりか | 確認済み | barrierでも約2倍の1子待ち。ordinary pipelineでは早い子のreadのみ重なり、mutation/切断/Closeの重なりは0件 |
| 主要因の特定 | 起動側の実行資源競合まで確認 | 4CPU枠の高利用・procs介入・CPU/traceを照合。CPU待ち/SMT/cache/帯域の内訳、単一の原因関数は未確定 |
| 1子と4子全体の利益/不利益 | 確認済み | 1子は遅いが4子全体は短縮。遅いSQL試行も保存 |
| 次の改善投資への引継ぎ | 整理済み・Human受理待ち | v0.7.xでは起動処理のCPU仕事量とscheduler挙動を候補選定に使う。変更方式/実装は未着手 |

## ordinary：同一環境での対照

各条件5 process反復。1子の値は「各processの4子中央値」をさらに5反復で中央値化した。
括弧内はその5値のmin–max。4子全体は最初のFork開始から最後の子Closeまでで、親の準備/Snapshotを含まない。
`analysis.json`のpooled20子中央値とは集計単位が異なる（pooledは43.57/84.33/81.32ms）。
4子を独立した20回のprocess反復として扱わない。

| 条件 | Fork 1子 ms | 4子全体 ms | 4子全ready ms |
| --- | ---: | ---: | ---: |
| 直列pipeline | 43.50（43.34–45.06） | 541.23（536.98–578.65） | 453.01 ※ |
| 4並列pipeline | 84.03（83.72–94.36） | 263.47（261.47–281.97） | 99.29（85.61–104.54） |
| 4並列barrier | 86.06（73.72–90.53） | 275.97（268.43–558.50） | 90.65（74.67–105.30） |

※ 直列の全readyまでには前3子のSQL/終了を含むため、並列との純粋な起動比較には使わない。
barrierとpipelineの小差はばらつきもあり、barrierによる1子の改善は成立していない。
pipeline全5試行で最終子ready前に始まったoperationはpoint_use15件、count_use6件、
mutation/切断/Closeはいずれも0件。barrierはいずれも0件。したがってSQLを待たせても残る
遅延を、先行子のcommit/rollback/終了によるものとする説明は今回の証拠と合わない。
point_useには接続準備も含むため、全時間を純粋なSQL実行時間とはしない。

旧campaignのFork70.47→139.77msという絶対値を再現したとはしない。今回も並列で1子約2倍という
傾向は観測したが、旧runnerのCPU型/枠数が記録されておらず、現runnerと同一性能環境とは証明できない。
今回の測定境界はFork APIで、旧guest l4m_open→readyの内部probeではない。

## 実行資源と診断：何が確認できたか

[environment](ubuntu-parallel-startup-evidence/native/environment.json)と
[lscpu](ubuntu-parallel-startup-evidence/native/lscpu.json)：Ubuntu24.04.5/amd64、
AMD EPYC9V45、4 logical CPU、2 core×2 threadのguest表示、affinity0–3、native GOMAXPROCS4。
読めた2階層のcpu.maxはmaxだがrootのcpu.maxは存在しない。quotaが一切ないという証明にはしない。
物理hostの混雑やCPU配置は確認していない。

ordinary barrierはstartup CPU/実経過時間が3.42–4.00（中央値3.61）で、4実行枠を高利用している。
別cohortのbarrier診断（各3反復）で、Goの実行枠だけを変えた結果：

| GOMAXPROCS | 全ready ms 中央値（min–max） | startup process CPU ms 中央値 | CPU/実経過 中央値 |
| --- | ---: | ---: | ---: |
| 1 | 232.24（232.24–237.16） | 233.34 | 1.003 |
| 2 | 108.45（103.05–126.37） | 216.95 | 1.999 |
| 4 | 91.28（66.34–98.52） | 361.56 | 3.961 |

実行枠の増加で待ちが減るため、起動の仕事を同時に実行する資源が重要である。
ただしCPU消費そのものも一定でない。直列4ForkのCPU合計中央値231.70msに対しordinary barrierは346.18ms。
後者は全ready窓の全workerを含み完全に同じ範囲ではないが、単に一定量の仕事が順番待ちするだけ、とは断定できない。
通常アクセスの帯域/キャッシュ/SMT、spin/yield、追加のworker処理の寄与は未分離である。
CPU会計にはメモリ待ちで実行中の時間も含み、使用率だけで帯域律速を排除できない。

CPU diagnosticはpipeline/barrier各3本を別々に合成した。
[barrier flat](ubuntu-parallel-startup-evidence/native/barrier-cpu-flat.txt)の1190ms samplesでは、
MemoryEA15.13%、MemSizeのatomic Load15.13%、MemoryInBounds13.45%、memclr13.45%、
Fn18085（buf_page_is_corrupted）9.24%、Fn456（my_uca_info_init）5.04%がflat上位。
[累積stack](ubuntu-parallel-startup-evidence/native/barrier-cpu-cum.txt)ではinit_embedded_serverと
page read/transaction初期化/charset初期化を確認した。
Fn対応は固定guestの[function-map](v050-ad-integration-evidence/function-map.txt)による。
MemoryInBoundsはMemSize.Loadを行う（`internal/generatedgo/code/base/base.go:1463`）。
このLoadをDBデータのlock競合や誤ったatomic実装の証拠とは扱わない。
サンプル比率はCPU時間の内訳で、wallの削減可能量ではない。累積比率を合算しない。

[trace sched](ubuntu-parallel-startup-evidence/native/barrier-trace-sched.txt)ではwake後の実行待ち218.14ms、
Sched_yield64.12msが見える。複数goroutineの合計なのでFork wallへ足したり差し引いたりしない。
[sync](ubuntu-parallel-startup-evidence/native/barrier-trace-sync.txt)のready待ち・barrier・futexには
正常な待ちも含まれ、全量を不要なlock待ちとはしない。
[Go mutex profile](ubuntu-parallel-startup-evidence/native/barrier-mutex-flat.txt)は合計2.31msだが、
guestのspin/atomic競合をこの小ささで否定できない。
ordinary barrierの5回中4回は起動中GC cycle0でも1子の遅延があり、GCを主因とする根拠はない。
GC CPU推定値をRUSAGE CPUから引く計算はしていない。

CPU/trace条件は計測器の費用を含むためordinaryの速度比較へ混ぜない。
StopCPUProfileは全ready後・SQL barrier解放前に行うので、診断cohortの4子全体には停止待ちも入る。
ordinaryと診断の値の差を製品の回帰としない。

## 遅い試行と未完了にしないための境界

ordinary-barrier-3の4子全体558.50msは除外していない。
Forkは各74.46–74.60ms、最初のpoint_use_00が397.00msで、遅延箇所はready後にある。
診断にもprocs-2-1のpoint_use_01約800.6ms、procs-4-0のpoint_use_02約404.5msがある。
これらのpoint_use内部原因は今回未特定で、単なるノイズ・起動競合・安全性欠陥とは断定しない。
今回依頼のFork起動区間を越えて新たなSQL tail調査は開始していない。

特定できたのは「起動自身の同時実行が主要な対象で、他子のSQL/終了を待たせても解消しない」まで。
特定関数/帯域/lockごとの原因寄与まで完了したとはしない。これはv0.7.xの方式選定時の残件である。
今の証拠からbarrier常用・GOMAXPROCS固定・境界検査の緩和を推薦しない。
利用者には、今回の条件では4並列の方が全体は約51%短い一方、各子のready待ちは長い、と説明できる。

## 保存・検証・次の判断

本報告と状態文書のみを更新し、runtime/guest/生成物/APIは変更していない。
既存の失敗oracleは維持。公開ガイド・生成input inventory・release台帳を変更すべき製品変更はない。
新しい本番採用候補やOS保証は作っていないので、独立再生成/追加runtime acceptance/Release Qualificationは実施していない。

CIはscratchを削除し[残量12MiB](ubuntu-parallel-startup-evidence/native/storage-after.txt)を記録。
ローカルは原本11.8MBを470767byteのarchiveへ圧縮保存し、参照用の主要JSON/textも保持した。
保存hashと再展開hashを照合し、一時downloadは削除した。今回追加の1GiB超残置・cleanup debtはない。
次のHuman判断は本限定調査結果の受理であり、main統合・実装・リリースとは分ける。

## Human決定（2026-10-18）

HumanはGOMAXPROCS診断の意味を確認した後、本限定調査の結果を承認した。
依頼された2aはクローズする。CPU待ち/cache/帯域の内訳や遅いSQL試行の原因まで解明済みとはしない。

GOMAXPROCSは自動設定を維持する。今回のnative既定値は4で、試した1/2/4では4が最速だった。
4超の指定・別環境・Fork同時数の最適値は未検証で、より良い設定が見つかったという結論ではない。
guest起動時の仕事量削減と同時実行の効率は、予定どおり0.7.xの改善方式選定へ引き継ぐ。
本承認にmain統合・最適化実装・Qualification・リリースは含めない。
