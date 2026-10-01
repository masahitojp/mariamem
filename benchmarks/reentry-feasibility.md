# v0.4 Ready-state reentry feasibility

## Source / environment / scope

開始SHA：**5676f901239c5ba4935c10061b8895216c212505** (`v0.4/prepared-clone-spike`)。
HEAD一致を確認して`v0.4/reentry-spike`を作成。main / production runtime / guest source / public APIは変更なし。
2026-10-01、Apple M1 / 16 GiB、macOS27.0 (26A428)、Go1.26.8、Python3.14.7、OS page16 KiB。
同じlegacy-EH guest、converter、bounded WASIX shims、prepared-files prototypeを使用。
guest SHA256：`6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3`。
観測binary SHA256：`a694f071993dd3afdd60425b9e50062a34dba53dfb417801b11c03b0727d651b`。
legacy artifactのWasmer7.4.2 cross-runtime validation unavailableという制限は継続。

目的はready heapの汎用reentry contractの有無。SQL quiesceの実測、実sourceのworker lifecycle、
3つのcomponent実験まで行った。任意のGo continuation / waiter queue serializationが必要になる境界で停止した。
**MariaDB-ready heapからSQLへ再entryした子は作れていない。**
既存prepared-files childを再entry成功として数えない。

[再現手順・隔離templates](spikes/reentry/README.md)、[測定・component evidence](spikes/reentry/evidence.json)。
生成Go / binaries / prepared images / raw stacksはignored results内の独立Go modules。
tracked Go templatesは`.go.txt`。public package discoveryに混入させない。

## A. Runtime-bound state inventory

分類は現guestと生成runtimeでの実際の利用に基づく。「RESETTABLE」は条件付きであり、
任意のready時点でzeroして安全という意味ではない。未検証部分を成功扱いしない。

| State | 分類 | 実際の利用 / 復元条件 |
| --- | --- | --- |
| committed row/schema/file bytes、immutable code/data | PURE GUEST STATE | clean filesystemの再利用は前spikeで実証。codeはOS通常共有。ready heap内の安全なbyte-range分割は未実証 |
| linear-memory offsets / allocator pointers | PURE GUEST STATE（同一guest image内） | generated loadsは`m.M + uint32(offset)`。新しいlinear baseでも相対参照可能。ただし参照先objectがexecution stateなら、そのobjectも復元が必要 |
| InnoDB buffer/dictionary/LRU/checkpoint state | 混在 | page bytesは候補。latches、wait条件、file objects、workerとの参照を含むgraph全体をPUREとは分類できない |
| generated function tables / MemMu / ThreadPool | RESETTABLE | `NewFromSnapshot`が新しいhost objectsを構築。function tableは同一guestのcodeから再生成。old Go mutexやWaitGroupをコピーしない |
| worker PC / Go call frames / locals / EH state | NON-RECONSTRUCTIBLE（現snapshot contract） | `ThreadLaunch`はentryから開始。`SaveGlobals`はmainの4値のみで、worker PC、Go locals、pending exception等のcontinuationを保存しない |
| pthread TID / handle / join state | REBINDABLE候補、未実証 | `WasiThreadStart/Fn217`がguest pthread descriptorにTIDを書き込む。fresh `nextTID`だけではcopied registryやjoin stateを修復できない |
| per-agent stack/TLS globals、TLS storage | REBINDABLE候補 | `Fn217`がstart argumentからG0 stack / G1 TLSを設定し、TLS segment初期化、descriptorへの参照を設定する。縮約は成功。既存musl pthread / MariaDB TLSへのgeneric rebindは未実証 |
| MariaDB thread bookkeeping | REBINDABLE候補、source-specific | `my_thread_init()`はTLSの`my_thread_var`があればskip。新規時はpthread_self、stack end、thread ID/count、mutex/condvarを登録する。TLS pointerだけ戻すと旧登録が残る |
| mutex / condvar guest words・待機中guest stack | RESETTABLEはowner/waiter-free境界限定 | condwaitはmutexをrelease→wait→reacquireする途中。waiter metadataやstack参照を残したcondvarを再初期化する正当性はない |
| host futex wait queue / wait channel | NON-RECONSTRUCTIBLE（現contract） | `ThreadPool.parked[guest address]`はGo channel列。guest bytesと独立。新しいqueueへのnotifyはold waiterをresumeしないことを縮約で確認 |
| timers / timeout deadlines / clock origin | RESETTABLE＋deadline変換が必要 | `AtomicWait`はGo timer、`clockNanos(1)`はWASI objectのmonoStart基準。remaining timeout / worker内deadlineの扱いが必要。今回保存・復元しない |
| signals / cancellation / abnormal exit | RESETTABLE候補、未実装contract | host `Thread_signal`等はfail-closedのまま。signal delivery/mask再bindを実証していない |
| regular-file logical FD / file identity / offset / flags | REBINDABLE（component成功） | guestはWASI logical FDを使い、host `fdTable`がMemFS objectへ対応。node identity＋offset/flagsをfresh objectへ復元可能。番号はtableから取得 |
| open-unlinked/renamed files / alias / locks / pending I/O | 混在、追加contract | pathだけでは復元不可。rename/unlink identityは縮約成功。dup alias、directories、OS lock、pending I/Oの復元は対象外 |
| stdio / sockets / host sessions / wire listener | RESETTABLE | fresh接続へ再設定が必要。今回direct guestのruntime表ではsocket0。host wire/session objectsのcloneはしない |
| resident session slots | RESETTABLE候補、source-specific | closeはMYSQL connectionを閉じるがworkerは存続。slotのstarted/pthread_t/mutex/condvar/op等はready memoryに残る |
| direct Go pointer / indexes in guest heap | 一括判断不可 | guest内のraw Go pointerの存在は立証していない。実証済みはTIDs/TLS pointers/FDとhost-side objectsへの依存。Go object graphはhostに残る |

主な確認箇所：同一build sourceの`mysys/my_thr_init.c:my_thread_init/my_thread_end`、
`tpool/tpool_generic.cc:worker_main/get_task/wait_for_tasks/worker_end`、
`storage/innobase/buf/buf0flu.cc:buf_flush_page_cleaner`、[resident worker](../guest/resident.inc)、
生成baseの`ThreadLaunch/AtomicWait/SaveGlobals`と`WasiStubs/clockNanos/pathOpen/fdSeek`。
source hashesはevidenceに保存。numeric generated function IDはこのartifactの診断用で、restore contractには使用しない。

## B. Candidate safepoints — actual observation

既存clean prepared filesをfresh runtimeでopenした独立DBを3つ使用。
fixtureは前spikeと同じInnoDB `benchmark_rows`、ID0–999、32文字payload。
各DBでCOUNT1000、`@@in_transaction=0`を確認し、sessionをclose、2秒の通常idle観測。
次に新しいadmin sessionでtable export quiesce、unlock、global read lock、unlock、session close、normal shutdown。
MariaDB settings / timeout / thread orderingは変更しない。

| 候補境界 | trials | host waiters | generated TIDs allocated | goroutines | DB/temp FD entries | page-cleaner frame |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| fixture確認後、client close | 3 | 各8 | 各8 | 各12 | 各15 | 全て残る |
| clientなし、通常idle 2秒後 | 3 | 各8 | 各8 | 各12 | 各15 | 全て残る |
| `FLUSH TABLES benchmark_rows FOR EXPORT`後 | 3 | 各8 | 各8 | 各12 | 各15 | 全て残る |
| `FLUSH TABLES WITH READ LOCK`後 | 3 | 各8 | 各8 | 各12 | 各15 | 全て残る |
| unlock / client close後 | 3 | 各8 | 各8 | 各12 | 各15 | 全て残る |

SQL操作は全て成功、COUNTは1000、3 DBともexit0。normal ready-pathの証拠でありreentry childの結果ではない。
SHOW ENGINE INNODB STATUSは各DBでhistory list0、row locks0、modified pages0、pending reads/writes0、purge running but idle、master sleeping。
**clean bufferとI/Oなしでもexecution waiterは残る。** 前spikeの新規fixture load直後とはdirty-page状態が異なる。
observerはcoherent stop-the-world captureではない。3 DB / 15 samplesの範囲であり、全てのpossible schedulingを証明したものではない。

同sourceの`row0quiesce.cc:row_quiesce_table_start`はpurgeをstopし、table flush、pending writes drain、cfg出力を行う。
table exportのquiesceはpersistent tableを対象とし、page cleaner / pool / resident workerのexecution drain契約ではない。
global read lockもsessionに保有されるDB lockで、host waiterを消さない。
通常shutdownはworker joinまで進められるが、`mysql_server_end()`でready engineを破棄するためwarm boundaryにはならない。

## C/D. Worker execution position / TLS reduction

実page cleanerのidle stack：`ThreadLaunch → WasiThreadStart/Fn217 → Fn18163 → condwait/Fn219 → Futex_wait → AtomicWait`。
page cleanerの関数入口は`my_thread_init()`、thread naming、timeout、activity/flush/archive localsを初期化し、
loop内のmutex/condvarで待つ。source line2775付近のlocalsはloopをまたいで存続する。
`buf_flush_page_cleaner_init()`はactive=falseを前提にflush LSNを初期化してdetached threadを作る。
**既存ready objectへのresume entryではない。**

pool workerはstandby listへ登録されてcondvarで待ち、task授受・wake reason・list移動をloopの前後で行う。
`worker_main()`をそのまま再実行するとTLS callback / counters / registrationと、既存standby stateの整合性を取る必要がある。
そのworkerの生成functionを入口から呼ぶだけのrestoreは行わない。

縮約WATでは、persistent target/resultをlinear memoryに置き、**1 work unit終了→return→join**を明示的handoff点にした。
memory＋globalsだけを取得し、old execution contextを捨て、fresh Module / thread poolから同じsemantic work entryを実行。
new logical TID、agent別mutable-global TLSとTLS storage、main TLS、A/B/base独立性、全workers joinを確認。
race detector付き**20/20 PASS**。

これは「semantic entryならexact instruction positionは不要」を実証する。
現page cleaner / poolには同じreturn/handoff契約が存在せず、実MariaDB background workerのTLS rebindは未達。
縮約TLSはmusl pthreadの全TLS/destructor/registryを再現していない。
現guestの待機中frameをそのまま再開するならPC＋locals＋condwait continuationが必要。
exact PC保存を避けるには、workerごとにsafe pause/return、locals export、登録解除/再登録を設計する必要がある。
それはbounded host identity shimだけでは済まず、今回のstop条件に達する。

## E. Regular-file rebind reduction

full generated baseのMemFS/WASI実装を使用し、実prepared filesの`ib_logfile0`とfixture `.ibd`をRW open。
FDは新しいtableから取得し、offset32へseek。redoをrenameし、別fileをopen→unlinkしてpath-only復元の限界も確認。
captureはnode ID / current name / data / logical FD / offset / fdflags / nextFDのみ。
old handlesをcloseしてA/Bのfresh MemFS nodes、file objects、fd tableへ同じlogical FD namespaceを復元した。

- WASI `Fd_read`が元offset/contentを返す。fdflags保持、new host objectsを確認。
- AのWASI writeを読み戻し、Bとcaptured base checksumが変化しない。
- rename後のstale diagnostic path、open-unlinked fileもnode identityで再構成。
- A全FD close後もBのread成功。Bもclose。
- race detector付き**3/3 PASS**。番号やguest addressesをrestore用にhard-codeしない。

これはregular MemFS handlesのgenericな再bindが可能というcomponent証拠。
captureはcoordinated reduced testであり、running MariaDBの全FD graphをatomicにcaptureするものではない。
stdio/socket/dir/dup alias/refcount/lock/async I/Oは含めず、全WASIX descriptor layerは実装しない。
inherited hostの`Fd_fdstat_set_rights`はexists確認のみでrightsを保存・enforceしない。
この未完成contractも製品化前のhardening対象で、今回変更しない。

## F. Waiter / mutex / condvar result

実生成baseでwaiter registrationをbarrier確認し、guest bytesをfresh Moduleへcopy。
fresh queueへのnotifyは0、old queueへのnotifyは1で、元workerは正常にreturn/join。
**3/3 PASS**。guest wordだけではhost queueとblocked continuationは戻らない。
既存futex/condvar semanticsのbugではなく、capture表現が持たないexecution stateの確認。
以前の約1秒tailのGUEST-SIDE BEHAVIOR分類は変更しない。

全workerがlockを所有せず、condvar待機のguest/host transient stateも解消してsemantic handoffした場合に限り、
new synchronization objectsへのreconstructionを検討できる。
今回観測した境界はその条件を満たさない。mutex/condvarをblind resetせず、sticky wakeupsも追加しない。
任意のwait queuesを保存する方針には進まない。

## G/H/I/J. Whole reentry / isolation / resource gate

| 指標 | 今回の結果 |
| --- | --- |
| safe ready execution safepoint | 未発見。idle / table-export / global-read-lockにはwaitersとframesが残る |
| worker/TLS rebind | semantic worker縮約成功。実page-cleaner / MariaDB pthread rebind未達 |
| FD rebind | regular MemFS component成功、whole ready instance未達 |
| ready state→reentered child→SELECT1 | 未達。fresh runtime over prepared filesではCOUNT/SQL成功 |
| two ready-heap children / SQL isolation | 未実施。component A/B isolationのみ成功 |
| 約69 MiB dirty linear stateの新たな共有量 | 未実証、削減量を算出しない |
| reentry incremental footprint / private dirty | N/A：operational reentry childがない |
| reentry first-SQL min/p50/p95/max | N/A：同理由。30 trial benchmarkを行わない |

比較対象は前spikeのprepared-files **77.16 MiB追加physical / child、SQL p50 34.2 / p95 37.8 ms**。
generated-Go baseline約89 MiB、pre-init CoW約81 MiB、remaining linear dirty約69 MiB。
今回それらを上回る新しいmemory/latency gainは測定できていない。
readiness/SQL/shutdownのみを確認するfresh startupをready reentryとしてbenchmarkしない。
Aria schema issueは本実験をblockせず、前spikeどおりdeferred。

## K. Complexity / maintenance / checks

少なくとも**8 mechanisms**が必要：①全worker semantic pause/return coordination、②worker-local continuationのsemantic化、
③pthread/TLS/registry/join再bind、④owner/waiter-free synchronization保証、⑤FD/node/alias/offset/rights graph復元、
⑥timer/deadline/clock再設定、⑦signal/cancellation/abnormal-exit lifecycle、⑧foreground/session entryとcoherent capture。
FD componentと明示handoff worker reduction以外の全体contractは実証していない。

特に①②③④はMariaDB threadpool / page cleaner / libc condwaitの内部状態に依存する。
thread count8、Fn番号、memory offset、FD番号を固定する設計は採用しない。
現runtimeのsnapshot APIを延長するだけではworkerのGo locals/PCは復元できない。
汎用continuation runtime、arbitrary waiter serialization、個別address patches、unsafe OS forkには進まず停止。
maintenance burdenは単一FD adapter以上で、MariaDB・libc・converter変更ごとのworker lifecycle監査を要求する。
縮約成功を全workerのgeneric再bind成功へ一般化できない。

通常Go unit/vet成功、Python **368 passed / 3 skipped (9.26s)**、public source **380 files PASS**。
既存Wasmer integrationはGo race **PASS (8.765s)**、Python **3 passed (2.43s)**。
再現setupから生成し直した縮約testもPASS。`git diff --check`成功。
sandboxのGo cache / localhost bind拒否は権限付きで再実行して解消した。製品regressionではない。
利用者の未追跡npm filesはpublic-source check中だけ退避しhash一致で復元。

## Recommendation

**このbounded v0.4探索はprepared-files architectureで止める。**
77 MiB / 34 msからさらに約69 MiBの一部を共有できる可能性はあるが、現guestにその安全なreentry contractはなく、
追加gain未実証のままworker continuationを製品設計へ持ち込む根拠はない。
production Snapshot/Fork採用を自動決定する結論ではない。
将来ready reentryを再検討するなら、先にsource-level cooperative safepoint / worker semantic lifecycleの設計判断が必要。
このbranchではそのfollow-upを開始しない。

## Feasibility verdict

### RED — READY-STATE REENTRY NOT PRACTICAL

**現guestのready heapを維持し、boundedなruntime identity再作成だけで再entryする方式についての判定。**
filesと明示的にreturnした縮約workerは再bindできるが、実MariaDB-readyでは複数background/session workersが
condwait continuationとregistryを保持したまま。安全なworker handoffは発見できず、現contractでのrestoreは
任意のexecution/waiter復元、または相応のMariaDB/runtime lifecycle改修を必要とする。
将来のsource/runtime redesignまで不可能と証明したものではない。
