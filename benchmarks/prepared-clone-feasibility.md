# v0.4 Prepared-clone feasibility

Historical scope note: these isolated modes combine a pre-init linear image with
prepared copy/private-map controls. Current production adopts prepared-file
private mappings but not the shared linear image or running-state clone. See the
[current CoW path audit](../docs/copy-on-write.md); original results are unchanged.

## Source / environment / result scope

開始SHA：**8658310fce7745c7a8df04bc0aed7d7a6ce5ce14** (`v0.4/cow-spike`)。
HEAD一致を確認して`v0.4/prepared-clone-spike`を作成した。
main、production runtime、public API、Snapshot/Fork semanticsには変更なし。
既存未追跡npm filesは保存する。

2026-10-01、Apple M1 / 16 GiB、macOS 27.0 (26A428)、Go1.26.8、Python3.14.7、OS page16 KiB。
前spikeと同じlegacy-EH MariaDB guestとbounded WASIX shimを使用。
guest SHA256 `6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3`。
legacy guestのWasmer7.4.2 cross-runtime validationができない制限は継続する。

**今回SQLに到達したのは、ready DBの通常shutdown後のprepared filesを共有し、execution stateをfreshに再構築する子。**
**MariaDB-ready linear heapを再開した子ではない。** InnoDB buffer/cache/background threadsは起動し直す。
warm heapを安全に保存・再開するcontractが現在の生成code/guest entryにないことを観測・source inspectionで確認した。
live Go objectをserializeしたり、個別guest addressをresetしてgreenにしたりはしない。

[再現用scripts/templates](spikes/prepared-clone/)と[trial evidence](spikes/prepared-clone/evidence.json)。
生成Go・binary・raw stacks/page fingerprints・DB imagesはignored結果directoryの独立go.modに隔離。

## A. Exact prepared boundary / state inventory

既存1,000-row fixture：`benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB`、
ID0–999 / 32文字payload、transaction load / COMMIT / COUNT。MariaDB設定は変更なし。

**観測したready点**はfixture COMMITを確認し、SQL sessionをclose、foregroundをrequest loopのstdin readに置き、
2秒ごとに4回観測した点。これはforeground idleであり、全guestのstop-the-world pointではない。

**採用したcapture点**は、そのready DBへ既存snapshot frame `0xfffffffe`を送り、
session workers join → `l4m_close()` / `mysql_server_end()` → guestの`/snapshot-out/data` copy →
snapshot reply → generated.Start return → 全generated workers joinの後。
この点からpersistent filesだけをexportする。templateは停止する。live templateを残すwarm snapshotではない。

| state | 再利用 / 再構築 |
| --- | --- |
| schema / committed rows / system / redo / undo files | clean-shutdown baseとして再利用。immutable host fileから子ごとにMAP_PRIVATE view |
| InnoDB buffer/data/dictionary memory | 内容には共有候補があるが、dirty flags、latches、LRU、thread/FD参照と結合。今回再利用せず、filesから再構築 |
| thread-free initialized linear image | 前CoW proofの15.16 MiB resident extentsを再利用。MariaDB ready時の約75 MiB imageではない |
| remaining ready linear heap | live stacks/TLS/pthread registry/locks/session metadataを含む。安全なbyte rangeの汎用分離を実証していない |
| Go goroutines / ThreadPool / mutex / channels | fresh objects。running stateは保存しない |
| guest pthread / TLS / mutex / condvar | fresh guest startupで再生成。ready stateの既存TID/ownershipをコピーしない |
| timers / signals | timerとclock origin、signal registrationをfresh startupで生成。signals/cancellationの未実装pathsは前spikeどおりfail-closed |
| FD / file offsets / stream objects | 新しいWASI fd table、MemFS nodes、open handles。旧番号・offset・Go File objectを継承しない |
| sockets / MySQL host sessions / listeners | direct guest protocolを使用。新規sessionをopen。wire listener/clientは継承・実装していない |
| auth / immutable code | guestの既存prepared test RSA keys setupを再実行。codeはOS通常共有。trust/distribution契約は製品化前に必要 |

## B. Quiescence findings

2つの独立parentでready→正常snapshot capture成功。sourceと実測を分けて記録する。

### Actual ready observation

- 第一parentは**11 allocated TIDs / 11 registered host futex waiters / 15 goroutines**。
  mainは`Fd_read`経由のstdin syscall中。worker stacksには`AtomicWait`/`Futex_wait`、
  `ThreadLaunch`、`WasiThreadStart`の`Fn217`等が残る。
- DB/temp **15 FD entries**が残る。undo filesのoffsetは10 MiB、fixture `.ibd`は147,456 B。
  closeしたSQL sessionのworkerも`multi_slots[].started`を保持し、conditionで待機する。
- session内`@@in_transaction=0`。`SHOW ENGINE INNODB STATUS`にはnot-started transactions / row locks0、
  pending reads0 / pending writes0 / pending flushes0、**Modified db pages23**、
  history list2、purge running、master sleepingが表示された。
  log flushed LSN140492に対してcheckpoint36536。foreground transactionなし/現在I/Oなしでもclean imageとは言えない。
- 第一parentのidle2秒intervalではlinear contentが**160 / 144 / 144 KiB**変化。
  第二parentは**128 / 128 / 128 KiB**。resident-only content fingerprintの差であり、write-historyではない。
  同intervalのMemFS block差は0。background stateは止まっていない。
- host waiter addresses/FD表が4 samplesで同じでも、timers/Go execution framesを保存できることを意味しない。
  `/sample`はforeground/backgroundを同時停止しない診断endpointで、snapshotとして使用していない。

### Source-backed shutdown boundary

`guest/resident.inc`は全slotへstop/signal、started workersの`pthread_join`後に`l4m_close()`を呼ぶ。
`wasm/lite4mariadb.c:l4m_close()`は`mysql_server_end()`を呼び、`g_open=0`へ戻す。
`storage/innobase/srv/srv0start.cc:innodb_shutdown()`はpurge/undo sourcesを停止し、
`logs_empty_and_mark_files_at_shutdown`、file close、page-cleaner停止確認、remaining thread shutdownを行う。
`guest/snapshot_fs.inc`は明示的に「open前またはshutdown後だけcopyする」契約。

これをそのまま使用する。background behaviorやtimeoutsを変更しない。
exported baseにはredo/system/undo/schema/data等**11 files / 138.17 MiB logical**がある。
`ibtmp1`と`ddl_recovery.log`はclean baseに含まれず、child runtimeが再生成する。
capture utility自身がguestのsnapshot copyを省略したものではない。

## C/F. Ready-memory reconstruction blocker / stale state

実際の生成codeは次の復元範囲を持つ。

- `SaveGlobals`はmain Moduleの`G0,G1,G4,G5` **4値だけ**。
  ready時は`[24267888,1024,1024,1388]`、pre-init imageは`[24268272,1024,1024,1388]`。
  数値を個別resetする解決は行わない。workerは別Module agentに独自stack/TLS globalsを持つ。
- `ThreadLaunch`はModuleをcopyしてnew goroutineでguest entryを実行し、Go WaitGroup/parked channel mapを共有する。
  `WasiThreadStart/Fn217`はguest start-argumentから`G0` stack / `G1` TLSを読み、
  guest pthread descriptorへatomicにTIDを書き込む。**guest linear memory内にthread identityが実際に存在する。**
- `NewFromSnapshot`はmemory+4 globalsを復元し、**fresh ThreadPool / MemMu / function tables**を作る。
  各workerのGo call stack、PC、locals、pending wait/timeout、thread entry argumentsを復元しない。
  exported `Start`は通常entry `Fn21925`で、ready request loopのcontinuation APIではない。
- `l4m_open()`は`g_open`ならserver initをskipする。ready heapでそのflagだけを残すとengine stateを再開した扱いになり、
  threads/host objectsがない。flagだけ消すと初期化済み全global/allocator/thread graphへの再初期化になる。
  **flag1個のresetではgeneric reconstructionにならない。**
- resident `multi_slot`はpthread_t / mutex / condvar / started/live/busy / SQL pointersを持つ。
  WASI libc `FILE`やInnoDB file objectsはFD番号を通してhost tableへ依存する。
  第一parentのFD11はpath表示`ib_logfile101`だが、baseの実fileは`ib_logfile0`。
  rename後のopen file identityと診断pathが異なる実例で、単純な「同じpathをopenし直す」も十分ではない。

**最初の構造的blockerは、ready linear bytesを再開するentry/worker-continuation contractがないこと。**
停止中Go runtimeをcopyせずにgeneric reset/rebindできる仕組みを実証していない。
不整合なlive imageをchildへ渡す実験、unsafe Unix fork、MariaDB internals/address patchは行わない。
これはready memoryを永久にclone不可能と証明した結果ではなく、bounded shimを超えるdesign workの特定である。
guest内の直接Go object pointerの存在は立証していない。guest handles/FD、TLS pointers、TIDsとhost objectsの依存は立証した。

## C/D. Bounded child prototype

ready DBの**persistent prepared files**を正常snapshotで取得し、metadata manifestを付ける。
live heap/Go objectsは保存しない。capture前にforegroundはCOMMIT/close済み。

1. 同一legacy guestと前CoWのpre-init imageから新しいguest Moduleを作る。
2. immutable DB filesをMAP_PRIVATE/RWでmapし、各child独自のMemFS nodeへ入れる。
3. WASI fd table/offsets、host objects、guest threads/TLS/locks/timers/session stateをfresh startupで作る。
4. ordinary `l4m_open`がexisting datadirをopenし、MariaDB operational、session open、SELECT1、fixture COUNTへ進む。
5. guest shutdown→全workers join→observer shutdown→linear/FS mappings unmap→process reap。

現MemFS grow/truncate logicは維持。mapped fileがgrowするとprivate Go arrayへcopyされ、旧mapはteardownまで保持する。
production restoreのfilesystem copyをprototype側でprivate viewsに置き換えたが、public API/runtimeには接続しない。
guest source、transactions、durability options、buffer sizes、background configurationは変更していない。
new auth keys setupも既存guestのまま。

Controls：**fresh-db**は前CoW pre-init image＋empty MemFS、
**prepared-copy**は同じprepared filesをanonymous mmapへ全copy、
**prepared-cow**はそのfilesのMAP_PRIVATE view。全modeでpre-init linear imageを使う。
copy controlだけをbaselineにして大きなmemory削減を主張しない。

## E. Functional / isolation results

prepared-copy/cow両方で、既存22-record SQL assertionsとauth callback self-testを確認。
さらにprepared fixtureに対してSELECT1、COUNT1000、payload読取り、INSERT+COMMIT、UPDATE、DELETE、
ROLLBACK、CREATE TABLE、duplicate-key1062、2 sessions / uncommitted write visibility、clean shutdown成功。

同じbaseからcow children A/Bを同時に作成：

- AのUPDATE/COMMITがBの1000 rows/payloadを変更しない。
- A-only schemaはBに存在せず1146。active transactionとROLLBACKも独立。
- A shutdown後もBがCOUNT1000を返し、Bも正常shutdown。
- base全11 filesのsize/SHA256をtrial前後で比較して一致。
- 20 independent create/read/close cycles成功。全77 measured groupsでexit0、teardown後guest process0。

processごとのisolation / cleanupの証拠であり、同一Go processで多数DBをcloseしたheap回収は未検証。
private mapsに対するwrites、fresh nodes/handlesによるDDL、base integrityを確認した。
以前のAria missing-table DESCRIBE issueはこの経路の検証をblockしなかった。ORM確認を追加せず、deferredのままにする。

## G. Clone latency — direct persistent-files boundary

**prepared base→new process→runtime reconstruction→MariaDB-ready→first SQL**。
prepared-cowは30 independent children。raw trialsをevidenceに保存。
build/transpilation/capture/base作成を除外。base hashesはtrial前に一度検証、終了後に再検証。
first hash verification実測 **137.5 ms**。この検証をper-child latencyに含めていない。
製品で必要なtrust checksを削除する提案ではなく、このprototypeがpublic Start/Forkではないという境界制限。

| prepared-cow metric | min ms | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| first SELECT1 (30) | 31.9 | **34.2** | **37.8** | 40.2 |

ready p50は33.7 ms、prepared COUNT p50は34.8 ms。
matched fresh-db10 trialsはfirst SQL30.1 ms、schema+1000 load+COUNT34.0 ms。
prepared-copy10 trialsはSQL53.3 ms、COUNT54.0 ms。
**このfixtureではprepared-cowにstartup latency優位はない。** schema/loadの再実行は省いたが、MariaDB startupは省いていない。

前reference：direct generated ready約40 ms、initialized-image→SQL29.8 ms、
wire+verification+SQL約99 ms、Wasmer prepared Fork→COUNT288.7 ms。
今回34.2/37.8 msはdirectの探索値。wire/listener/client/verificationを含む99/288.7 msと同等boundaryではない。
warm ready-heap child→SQLのp50/p95は**未測定**。

30 singlesの≥500 msは0/30。×16 prepared-cowは0/3 groups、fresh-dbは3/3 groupsが約1秒pathを含む。
prepared existing-datadirとempty-datadirで起動workが異なり、今回guest timeoutを短縮/強制wakeしていない。
traceによるtail attributionは本taskに含めず、tailが一般に消えた/同期semanticsを改善したとは言わない。

## H. Incremental memory / CPU / teardown

×4/8/16は各mode3 group trials、×1はcow30 / controls10。countersはSELECT1とCOUNT後、guestを生存させて取得。
fresh-dbだけfixture loadを含むため、CPU boundaryにもその差がある。
internal content observerはperformance trialsで呼んでいない。

| mode / children | group ready p50 ms | SQL p50 ms | RSS/child MiB | footprint/child MiB | total CPU CPU-s |
| --- | ---: | ---: | ---: | ---: | ---: |
| fresh-db ×1 | 29.6 | 30.1 | 104.88 | 81.20 | 0.044 |
| fresh-db ×4 | 1052.6 | 1054.9 | 105.24 | 81.61 | 0.277 |
| fresh-db ×8 | 1073.8 | 1077.4 | 105.08 | 81.40 | 0.614 |
| fresh-db ×16 | 1117.7 | 1123.1 | 105.19 | 81.54 | 1.184 |
| prepared-copy ×1 | 52.8 | 53.3 | 237.64 | 215.33 | 0.061 |
| prepared-copy ×4 | 98.3 | 99.1 | 237.66 | 215.30 | 0.332 |
| prepared-copy ×8 | 256.0 | 257.8 | 213.10 | 215.51 | 0.829 |
| prepared-copy ×16 | 534.9 | 539.1 | 119.02 | 215.61 | 1.759 |
| prepared-cow ×1 | 33.7 | 34.2 | 105.98 | 76.95 | 0.042 |
| prepared-cow ×4 | 47.2 | 48.0 | 105.95 | 76.93 | 0.192 |
| prepared-cow ×8 | 78.7 | 80.5 | 106.08 | 77.04 | 0.468 |
| prepared-cow ×16 | 151.8 | 154.7 | 106.14 | 77.15 | 0.956 |

×16 total RSS約1.66 GiB、task footprint合計 **1.205 GiB**。
`(×16 footprint − ×1 footprint)/15`の追加child chargeは **77.16 MiB**。
前pre-init CoW80.71 MiBより **4.4%減**、matched fresh-db×16より約5.4%減、
前generated-Go baseline89.35 MiBに対して約13.6%減。大きいready-state duplicationの解消ではない。

別の許可環境でfull vmmapを取得。prepared-cow childのlinear mapは
**2 GiB virtual / 70.9 MiB resident / 69.1 MiB DIRTY**。
11 prepared filesのmapは約138 MiB virtual / 約6.6 MiB resident clean、診断時DIRTY0。
scaled代表summaryではcombined mapped-file DIRTY約69.5 MiB、other anonymous DIRTY約5 MiB。
最も大きいduplicated/private stateは引き続き**linear約69 MiB**。

macOS phys_footprintはtask chargeで、Linux PSS/private-dirtyやmachineのexact resident bytesではない。
helperの`private_bytes`はnull。vmmap DIRTYとSM=COWで補うが、全childのprivate-dirtyを精密分配した値はない。
copy×16は代表vmmapに56.6 MiB swapped/compressed表示があり、RSS低下をmemory節約と解釈しない。
fresh-db×4の1 trialは105.23 MiB/childへ増えた。medianから除外せずraw evidenceに残した。

baseのclean file cacheはchild footprint合計に含まれない。一度だけ全prepared base138.17 MiB＋initial image15.16 MiBを
保守的に加えると×16全体約**1.355 GiB**。cacheのexact systemwide residencyを測った値ではない。
前pre-init CoWの同様のbase込み約1.276 GiBより**小さいという証拠はない**。
したがってper-child private chargeの改善とoverall machine RAM改善を分ける。
parent/captureの一時メモリもchild metricsには含めていない。

teardown後は全guest processをreapしguest charge0。shared base/cacheは残り得る。
同一process内のrepeated-close retention、large-file grow時のold map retention、long-run dirtyingは未測定。

## I. Separate latency / memory conclusions

- **Latency:** prepared persistent rows/schemaは再利用できるが、InnoDB startupを避けられていない。
  SQL34.2 msはtens-of-ms direct pathとして動くが、前29.8 msやmatched fixture34.0 msより改善していない。
- **Memory:** file private viewsはnaive full-copyの215 MiBを避ける。ただし適切な前81 MiBとの比較では追加gainは約4 MiB。
  warm ready linear-memory reuseの大きいgainは未実証。
- **Correctness:** ordinary SQL/isolationはfiles+fresh executionで成立。ready heap continuationの安全性は未検証。

## Explicit answers / next architecture step

| question | answer |
| --- | --- |
| exact boundary? | fixture COMMIT/close後、既存snapshotによるMariaDB正常停止・workers join後のfiles |
| safely reusable ready bytes? | committed/schema/system/undo/redo filesをclean imageとして実証。pre-init linearだけ既存proofを再利用。warm heapのsafe rangesは未特定 |
| runtime state to rebuild? | threads/TLS/locks/waiters/timers/fds/host sessions。今回すべて通常startupで再生成 |
| stale guest thread/TLS/FD state? | あり。thread-entryがguest pthread descriptorへTIDを書き、ready FD/offset/tableとwait queuesが存在 |
| generic reset possible? | 現在のconstructor/Start/4-global APIだけでは実証できない。ready entryとthread/FD graphの復元契約が必要 |
| child reaches SQL / isolation? | persistent-files childは成功。warm heap childは安全なcapture/reentryがなく未実行 |
| child SQL p50/p95? | files再構築34.2/37.8 ms (30)。warm heap cloneは未測定 |
| incremental physical? | 77.16 MiB追加child。task charge、shared base/cacheを別計上 |
| materially beats ~81 MiB? | 約4.4%だけ。linear DIRTY69 MiBは残り、base込み全体改善は未証明 |
| production Snapshot/Fork justified? | この結果だけではready-memory Snapshot/Fork実装を正当化しない。files pathのcorrectnessは有用だがarchitectural decisionが必要 |

推奨next experimentは、**ready heap continuationに必要なguest reentry / cooperative safepoint / thread・FD再構成契約を縮約し、
既存MariaDB APIsだけで構成できるかを検証すること**。
guest semanticsを維持できる明示境界が見つからなければ、warm heap cloningのcost/benefitを再評価する。
このtaskではguest internals patchやcontinuation implementationを開始しない。
runtime sharing、production Snapshot/Fork、他architectureの選択も行わない。

## Regression checks

通常`verify.py check`：Go unit / vet成功、Python **368 passed / 3 skipped (8.49s)**、
public source **372 files**成功。
通常Wasmer `verify.py integration`：Go race **8.980s**、Python lifecycle/multiclient **3 passed (2.35s)**。
installerのfresh moduleへの適用・Go syntax・snapshot export/control配置も確認。
最初のcapture pilotは観測HTTP handler配置不足で停止し、修正後の2成功capturesのみをevidenceに含めた。
利用者のnpm filesはcheck中だけ退避し、同一hashで復元。`git diff --check`成功。

### YELLOW — PREPARED CLONE POSSIBLE, RUNTIME RECONSTRUCTION COMPLEX

clean persistent prepared stateからisolated SQL-capable childrenは作れた。
主要なready linear stateを再利用するためのcapture/reentry/thread/TLS/FD復元契約は未解決で、
現在のbounded prototypeはInnoDB startupと約69 MiBのprivate stateを再生成する。
production architectureは選ばない。
