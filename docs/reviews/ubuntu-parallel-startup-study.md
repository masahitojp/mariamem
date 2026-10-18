# Ubuntu 10MiB 並列起動の限定調査

## 範囲と現在地

Humanが承認した0.5.x残件2a。**起動同士の競合と、先行子のSQL/終了との重なりを区別し、主要な伸長要因を特定する。**
macOS確認再利用のmain採用・開発CI完了後、main source_commit
`3f514ebf14fbbe6aca6ba77d00a1bb6cdb35163d` を基点に開始した。
現在は計測器の準備・ローカルmechanical検証の段階で、Ubuntuの新しい結果は未取得。
main変更、guest改善の方式選定/実装、Qualification、公開へ進まない。

旧[費用帰属](https://github.com/masahitojp/mariamem/blob/bbf5d1c27f3cea3e2135e8fae053f875ceb234b5/docs/reviews/child-lifecycle-attribution.md)では、
Ubuntuの同じ10MiBでguest open→readyが65.84→133.95ms（直列→4並列）。
通常Forkは70.47→139.77ms/子だが、4子のSQL/切断/Closeを含む実経過時間は989→538msへ短縮。
「1子が遅い」と「4テスト全体が遅い」は異なる。
旧campaignはCPU型/core数を記録していない。今回のrunner情報で昔のCPU構成を補完しない。

## 仮説と切り分け

1. 起動4件自体がCPU実行枠を分け合う。SQL前のbarrierでも遅くなり、CPU時間/実経過時間と
   GOMAXPROCS介入がCPU供給の上限と整合するなら、その根拠にする。
2. 先行子のSQL/接続処理/終了が、後続子の起動を圧迫する。barrierで起動が短くなり、
   timelineで実際の重なりが確認されるかを見る。barrier化は起動順序と資源保持も変えるため、差をSQLだけの厳密な因果量としない。
3. GC・同期待ち・メモリアクセス等で並列時の仕事/待ちが増える。別profile/traceとcounterで検討する。
   CPU使用率だけでmemory bandwidthや特定lockを断定しない。

主因を支持できなければ、その不足を具体的に報告する。CPU/memory/同期の一般調査へ自動で拡大しない。

## 同じfixture・同じbinaryの有限campaign

Go1.26.8 / CGO0 / Ubuntu24.04 x86_64。MariaDB12.3.3、guest hash
`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
10MiB（10240行×1024B）、8 InnoDB tables、4子、各DB16接続という現行構成。
既存ownedprepared/platform-cacheのapp-connections workloadを引き継ぎ、通常接続・別application接続・
read/count・commit/rollback・子の独立初期値・切断・Close・Snapshot破棄のoracleを維持する。

| cohort | 条件 | process実行数 |
| --- | --- | ---: |
| ordinary | 直列pipeline、4並列pipeline、4並列barrierを順序ローテーションで各5回 | 15 |
| procs diagnostic | barrierのGOMAXPROCS=1/2/4を各3回（process内の実験指定のみ） | 9 |
| CPU diagnostic | pipeline/barrier、native procs、各3回。CPU/block/mutex profile | 6 |
| trace diagnostic | pipeline/barrier、native procs、各1回。Go trace | 2 |
| **合計** | ordinaryへ診断試行を混ぜない | **32** |

- pipeline：各workerがFork→SQL→切断→Closeを進める従来方式。
- barrier：4子のFork完了とcounter採取までSQLを開始せず、その後4子が同じSQL/終了を進める。
  4子に4workerを要求し、足りないworker数のdeadlockを拒否する。
- 各operationのbegin/endを同じprocessのmonotonic originから記録し、SQL/接続・mutation・切断・Closeが
  最後のFork完了より前に始まった件数を算出する。barrier違反はFAIL。
- per-child Fork中央値・各processの4子実経過時間を併記する。4子の値を独立したprocess反復数に数えない。
- nativeのGOMAXPROCS、NumCPU、CPU型、affinity、cgroupのCPU制約情報を保存する。
  GOMAXPROCS指定はscheduler介入で、物理CPU/帯域を増やす操作ではない。
  cgroup階層がmount namespace等で読めない場合は未確認とし、rootのcpu.maxだけで無制限と推論しない。

## 計測の意味と限界

- `startup_wall_seconds` はworker起動から全4子ready通知のcallbackまで。
  barrierではSQLを含まない。pipelineでは他の子のSQL/終了を含み得る。
  直列の全ready区間は前3子のSQL/終了を含むため、純粋な起動時間として比較しない。
- callbackの遅れを最後のFork終了timestampとの差として記録する。CPU採取境界を最後のFork終了と厳密に同一とはしない。
- process CPUはRUSAGE_SELFで全Go/guest workerを含む。barrierのCPU/実経過時間は平均利用CPU数の観測で、
  任意区間の最大並列度やCPU制約の原因そのものを証明しない。
- GC CPUはGo runtime metricの推定値。Goの定義上system CPUと直接比較できないため、
  RUSAGE CPUから差し引いたり、そのままGC比率へ変換しない。GC cycle数とCPU samplesも併用する。
- block/mutex/traceはprocess scopeで、意図的なbarrier/WaitGroupやidle worker待ちも含む。
  その合計をguest内部のlock contentionへ読み替えない。Wasmのspin/atomic競合をGo mutex profilerだけで捕捉できるとはしない。
- CPU profileは短い試行をmode別に3本合成する。累積stackは重複し、wall削減量ではない。
- 旧l4m_open境界probeを製品runtimeへ再導入しない。今回の新しいwall値は公開Fork API区間で、
  guest初期化の細部は現guestに対応したFn symbol mapとCPU stacksから判断する。
- trace/pprofは同じGo1.26.8のGOROOT sourceからtoolをビルドし、tool hashとsource hashを記録する。
  traceの解析flagは当該versionの `-d=parsed` を使い、異なる版のtoolへ暗黙fallbackしない。

## 機械検証・identity・停止条件

`benchmarks/ubuntu-startup/schedule_test.go` はbarrier前のuse禁止、pipelineの実際の重なり、直列順序、
不正worker数の拒否をrace付きで検査する。
`test_tools.py` は固定32caseと、不足/重複operation・早すぎるSQL・不正counter境界・procs不一致・fixture不一致の拒否を検査。
`reduce.py` は全case集合・寸法・Go刻印/clean source・JSON hash・各子のoperation順序を検査して全min/median/maxを残す。

ビルド前に `scripts/git_identity.py` のcommit型検証、HEAD一致、clean checkoutを確認する。
source差分は新benchmark/workflow/docsだけに限定し、runtime/guest/生成物変更はpreflightで拒否。
normal checkoutでbinaryのactual vcs.revision/modifiedとGo1.26.8/CGO0、実行前後hashを確認する。
旧function-map hash `9072658996738894b86effc9b60911db92b413d35cb3c7863f3851666bb645b6` も記録する。

CI：`.github/workflows/ubuntu-parallel-startup.yml`。1 native job、全体35分。
compile/32実行/解析はdisk guardで1500秒・空き8GiB・owned6GiB、個々の実行180秒。
ローカルはguestを走らせず、scheduler race unit・Python failure oracles・tool format smokeを行う。
不足/機能失敗/入力不一致/予算超過では停止してFAIL/未完了とし、検査を弱めない。

終了時は、(1) pipelineとbarrierの差、(2) 起動自体の並列競合の根拠、(3) CPU/GC/同期の確認済みと未特定、
(4) 1子とスイートの利用者時間、(5) 次の投資判断への影響をHuman Reviewへ返す。
32実行の終了や時間上限到達そのものを、原因特定の完了とは扱わない。
CI提出後はrun URLとsource_commitを返して停止し、Humanの完了通知後に証拠を確認する。

## ローカル準備確認

macOSでschedulerのrace付きunitを3回PASS。
Pythonの新しい13 testと既存Git identity testsを合わせて25 tests・12 subtests PASS。
同じGo1.26.8 sourceからtrace/pprofを作り、小さな非DB fixtureでCPU profileとtraceの
parsed/sched/sync/syscall形式が読めることを確認した。
これらは計測器の検証であり、Ubuntuの実guestシナリオや原因特定のPASSではない。
[ローカル準備証拠](ubuntu-parallel-startup-evidence/local/manifest.json)を保存する。

## 初回CIの準備失敗と修正

[run 39098455094](https://github.com/masahitojp/mariamem/actions/runs/39098455094)
（source_commit `b01d400484f0763544dcc131b364ca83d464c275`）はsetup-go内の
`go env`で失敗した。job環境のGOTMPDIRを作るstepがsetup-goより後にあり、
`temp/compiler: no such file or directory`となった。guest・unit・計測は未実行で、
原因調査の結果は得られていない。証拠directoryも未作成のためcleanup/uploadも二次失敗した。

toolchain設定前にdirectoryを作る順序へ修正する。always cleanup自身もdirectoryを作り、
cleanup前のjob statusとsource_commitを保存して、早期失敗でも後片付けと証拠保存を可能にする。
32試行・失敗oracle・runtime・guestには変更しない。
修正のローカル確認はYAML読込・全run shell構文・埋め込みPython構文・step順序がPASS。
準備前失敗／準備後失敗／成功の3条件でcleanupを各2回実行し、status保存とscratch削除を確認した。
これはworkflowの確認であり、Ubuntu計測の成功を意味しない。
