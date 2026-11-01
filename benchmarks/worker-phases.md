# Worker負荷のphase分離：起動中の同期とSQL書込みを区別する

2026-11-01。**Fork中のscheduler負荷と短いguest wait/wakeは確認できたが、worker生成そのものが
主因、または不要な同期だとは確定していない。worker再利用・yield削減の実装はまだ勧めない。**
SpinRelax由来のyieldは今回の診断で0回だった。

次の改善候補としては、SQL区間でより直接的に現れた `Fd_write → os.File.Write` の
宛先・回数・書込みサイズを調べることを勧める。host/guest間のOS pipeが有力な照合先で、
外側のTCPを変えれば解消するとは言えない。これはFork初期化とは別のSQL実行コストの候補。
最も強い反論は、今回のSQLは32回の同じ集約クエリであり、他の用途の代表ではないこと。
また、この調査だけではfdの宛先やCPUコストの因果関係は確定しない。まず少数queryの
fd・iovec・byte数を観測する読取り調査に留め、通信実装や結果分離契約は変更しない。
Forkだけを優先する場合は、短い待機のguestアドレス・呼出元を同定する調査が次になる。

固定した観測は完了。ゼロサンプルだったCloseの関数別CPU帰属は未解明のまま明示する。
追加matrix、変更案、製品採用、releaseへ自動的に展開しない。

## 調べた境界

以前のprofileはFork→SQL→Close全体だった。今回は製品runtimeを変更しないprofile binaryで
各phaseだけサンプリングし、別のdiagnostic binaryの読取りカウンタで照合した。

- 製品はv0.6.0 source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`。
  #63 alignment・#64 fresh-zero・#56 batchingは入れない。
- 1,000整数行からSnapshotを作り、各子でpristine COUNT/SUM、更新後SUMを検査しClose。
  次の子も元のseedを確認する。
- SQL phaseは1接続で32回のCOUNT/SUMと更新確認。接続・SELECT1・UPDATE・更新後SUM・切断も
  区間に含む。単純に32で割って1queryの性能と呼ばない。通常の1テストを代表する条件ではない。
- 各phase40cycleを2回、合計240個のprofile window。順序はfork/sql/closeとその逆。
  profileなし40cycleを2回（80子）、diagnostic 6cycleを2回（12子）も実行。
- profilerは対象phase直前にStart、終了直後にStopし、個別profileを合算する。
  GoのStopはsamplingを止めてからwriterを待つため、この待ち時間はsampleに含まれない。
  ただし約200msのprofile flush間隔が後続処理やbackground活動を変え得る。
  profileのDurationやCPU%を実際のphase時間/CPU使用率として使わない。
- diagnosticはworker spawn/exit、SpinRelax/yield、AtomicWait戻り値/経過時間、notify/wokenを
  数えるoverlayのみ。同期条件、timeout、allocation、worker数は変えない。
  コール開始/終了の時点のphaseへ分類し、跨ぐwaitの全時間を開始phaseへ帰属させない。
  wait_nsは重複する壁時計時間の合計でありCPUではない。

## 結果：起動・SQL・終了

profileなしcontrol（40cycleの平均、2process）は以下。

| phase | wall / cycle | process CPU / cycle |
|---|---:|---:|
| Fork | 35.67–36.40ms | 46.77–47.81ms |
| SQL batch（32確認＋更新等） | 36.62–37.19ms | 35.82–36.38ms |
| Close | 2.39–2.42ms | 2.71–2.74ms |

CPU profileの内訳は、時間の比率ではなく観測CPU sample内での割合。

| phase | 1回目 | 2回目 |
|---|---:|---:|
| Fork: total sampled CPU | 1,610ms | 1,610ms |
| Fork: pthread_cond_signal + pthread_cond_wait | 330ms / 20.5% | 260ms / 16.1% |
| SQL: total sampled CPU | 1,180ms | 1,180ms |
| SQL: 同signal + wait | 110ms / 9.3% | 170ms / 14.4% |
| SQL: guest Fd_write累積 | 800ms / 67.8% | 840ms / 71.2% |
| Close: total sampled CPU | 0 | 0 |

Closeは1回の区間が100Hz samplingの周期より短く、両方ともサンプルを得られなかった。
**CloseのCPUがゼロという意味ではない。** 関数別の帰属を必要とするなら、別のtrace方式か
長い区間の設計が必要になる。今回の終了条件に追加しない。

schedulerのstackは、主に `pthread_cond_signal ← semawakeup ← startm ← wakep ← ready` と
`pthread_cond_wait ← semasleep ← stopm ← findRunnable`。Goが実行可能goroutineを動かす/OS threadを
parkする経路を示す。guestのpthreadとhostのOS threadを一対一で対応付ける証拠ではない。
`runtime.systemstack` で途切れるstackもあり、どのguest待機がどのwakepを生んだかは未同定。

診断2processの1子あたり平均:

| Fork中のイベント | 観測値 |
|---|---:|
| guest worker spawn | 8 |
| AtomicWait開始 | 120.3–138.8 |
| wokenで完了したwait | 112.2–128.5 |
| そのうち経過1ms未満 | 106.8–124.8 |
| notify呼出 | 181.7–181.8 |
| SpinRelax / そこからのyield | 0 / 0 |

短い待機・起床が存在し、単に8workerを作るだけの回数ではない。ただし必要な起動handshakeか、
削れる繰返しかは分からない。notifyにはwaiterゼロの呼出もあり、回数だけで無駄と判定しない。
WASI `Sched_yield` と遅延reclaim用yieldはこのcounterの対象外。SpinRelax=0から
「全yieldなし」とは言えない。各processのspawn/exit総数は一致し、全mappingを回収した。

## SQL書込みという次の手がかり

SQLの累積stackには `Fd_write → writeVec → os.File.Write → syscall.write` が現れ、
`os.File.Write` も同じ800/840msだった。階層の各数値を加算してはいけない。
測定processのstderrログは空であり、ベンチマークの大量stderr出力による説明ではない。

同じsourceの `internal/guest/linked.go:24` はhost/guest間の入出力に二組の `os.Pipe` を作り、
`runtime_instance.go:55` はそれをguest stdin/stdoutへ設定する。`base.go:13004` の
fd解決はstdoutや登録fileへwriterを返し、`writeVec` はiovecごとにWriteを呼ぶ。
したがって内部pipeへの細かな書込みは具体的な次の仮説になる。ただし今回のCPU profileには
fd番号/宛先/byte数がないため、全Fd_writeをpipeと確定することはできない。
外部client→hostのTCPとhost→guestの内部通信を区別して調べる。

## 検証・制限・保存

環境: Apple M1/16GiB/macOS27.2、Go1.27.3 darwin/arm64、CGO0、GOMAXPROCS8。
非隔離desktopの記述的結果。Linux・並行Fork・他SQL・最適化の速度改善は未検証。

measured harness source_commit: `c1498beb124f1d3964313764b5560fc0e57c845c`。
annotated v0.6.0 tag_object_sha: `b57183b08d48884840111e8b53daa500734337f0`。
clean sourceと型付きidentityをbuild前に確認。profile binaryはcanonical productを直接build、
diagnosticだけbase overlay。全binary/source/overlay hashとVCS情報は
[compact observations](workerphases/results/observations.json)のinputsに保存。
ローカルのGoにpprof実行ファイルがなかったため、同じGoの `cmd/pprof` ソースをbuildした。
依存取得はsandbox DNS制限で一度失敗し、同じsourceで権限付き再実行した。

正常pilot2、意図したseed破損検出2、332個の測定childのSQL/分離/cleanupがPASS。
5分析テストは欠落phase、phase数、worker漏れ、profile単位、path正規化を検査する。
Closeの0sampleも保存し、除外・追加反復はしていない。

[summary](workerphases/results/summary.json)と累積stack/traceテキストを保持。
compactは各runのphase合計とカウンタを保存し、全cycle時系列は別rawへ分離する。
raw ref `evidence/worker-phases-20261101`、commit
[`fd61ec0428b2fe97dd09946bf4587f616509f21e`](https://github.com/masahitojp/mariamem/blob/fd61ec0428b2fe97dd09946bf4587f616509f21e/raw.tar.gz)、
archive 373,563bytes、SHA256
`9e68973b85b8c77ecefb8673aaafa83b9bd25aabcb4c25dab35439feb0bbec54`。
317メンバー分のprofile/JSON/logとchecksumを保持。ローカルworkspace prefixを正規化し、
original/published hashを保持した。pprofはstring_tableだけを書換え、sample/stack IDは不変。
六つの正規化済みmerged profileはGo付属pprofで再読し、元とtop50/total sampleが完全一致した。

```sh
python3 benchmarks/workerphases/analyze.py --check
python3 -m unittest discover -s benchmarks/workerphases -p 'test_analysis.py'
```

上記はtemp削除後も動き、input receiptを変更しない。runtime再現はmeasured sourceのdisposable
workspaceでbudget8GiB/free reserve16GiBを設定し、次を実行する。

```sh
cp benchmarks/workerphases/run.py ../evidence/run.py
python3 ../evidence/run.py --phase build
python3 ../evidence/run.py --phase pilot
python3 ../evidence/run.py --phase measure
```

新runの還元にはreport refのanalyze.pyの `--collect <evidence> --results <new-output>` を使う。
[checksums](workerphases/results/SHA256SUMS.json)はcompactだけに依存する。
mainのproduction/guest/generated/API/releaseファイルは変更せず、exploratory historyのmergeは提案しない。
