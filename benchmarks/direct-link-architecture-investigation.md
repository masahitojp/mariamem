# generated-Go direct linkage / process boundary investigation

Historical scope note: “prepared mapping … 未実験” describes this investigation's
boundary, not current production. Prepared file-backed `MAP_PRIVATE` views were
subsequently integrated, with fresh mutable runtime state. See the
[current CoW path audit](../docs/copy-on-write.md).

Source: `52b5e2ac5612222fe933134b0342dee6dc77b1c9`、branch
`v0.4/generated-go-integration`。2026-10-02、MacBook Air M1 / 16 GiB、
macOS27.0 arm64、Go1.26.8。guest SHA:
`5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`。

前タスクの未commit timestamp hookは撤回した。production source、generator、
生成source/image/provenance、public APIは変更していない。cache prototypeも実装していない。
実験コードは `.go.txt` とPython script、生成harnessはignoredな独立Go module。
[機械可読結果](direct-link-investigation-evidence.json)を参照。

## 1. 履歴: direct linkageから切り替えたのか

**同一process内のMariaDB libraryを採用してから外した履歴は見つからなかった。**
wasm2goへの変換は、既存のguest subprocess/framing ownershipを維持して始まった。

| Transition / commit | Evidence / reason |
| --- | --- |
| production new-EH WASM → legacy-EH → wasm2go (`fbe9ff4`, `c63f81e`) | EH/codegen/import adaptationの可否を検証。既存framingで1 DB＝1 Go processを維持。feasibility reportは「in-process embedding自体は未検証」と明記 |
| generated-Go spike → selected candidate (`965da8c`, `023796b`) | 通常SQL/準備filesを採用。`023796b:docs/v04-generated-go-architecture.md`は**cancellation、traps、bounded forced teardown、Python ownership**のためsubprocessを保持すると明記 |
| prepared-files / ready-state reentry (`5676f90`, `8b368a7`) | fresh execution stateを採用。ready-heap再入の拒否は、freshなin-process module生成の拒否ではない |
| candidate bundle → Go embedded image (`52b5e2a`) | zero-setup/no-downloadで専用guestを提供。Pythonはowned hostに生成Goをlinkして内部guest entryを新しいchildで実行。Goも生成sourceを保持してnative guestをbuildしgzip/base64化 |
| embedded image → per-DB private file (`52b5e2a:internal/builtinruntime/runtime.go`) | DB tempdirの既存cleanup ownership、完全SHA verification、consumer executableを再execしない構造。**fileをDBごとに複製する必要性を示す比較実験は記録されていない** |

consumerの任意initを再実行しない理由は、consumer再exec案を避ける理由である。
直接リンクしたfresh Moduleもconsumer initを再実行しないので、direct linkageを禁止する根拠ではない。
thread/TLS/FDのsingleton不具合がprocess化の契機だったという証拠もない。
専用imageはguest compilerをGo1.26.8に固定できる。default-migration reportは
Go1.27.1のlarge arm64 codegen/LDPSW failureを記録している。direct linkageでは
consumer compilerが生成codeもcompileするため、この互換性問題を別途解決する必要がある。

## 2. process boundaryが現在提供するもの

分類の「REQUIRED」は**現行実装のfailure/cleanup契約を変更しない場合**を意味する。
MariaDB本来の不可変な要件という意味ではない。

| State / behavior | Classification | Actual code evidence |
| --- | --- | --- |
| linear memory、MariaDB global/static、InnoDB heap | PER-INSTANCE GO OBJECT SUFFICIENT | `code/generated.go:NewWithWASIReserve`の新しいModule/Memory。MariaDBのC静的stateはguest memory内。2同時DBの同名schema/異なるrow成功 |
| WASM globals / function table / exception state | PER-INSTANCE GO OBJECT SUFFICIENT | `base.Module`のG0…G706、T0、ExcPending/Tag/Vals。全guest関数はModule引数でアクセス |
| thread IDs/registry | PER-INSTANCE GO OBJECT SUFFICIENT | `Module.Threads`のThreadPool、nextTID、wg。ThreadLaunchは親Moduleをworker-local copy、Memory/Threadsは同じDB内だけ共有 |
| TLS / stack pointer | PER-INSTANCE GO OBJECT SUFFICIENT | worker-local ModuleのG0/G1、WasiThreadStartがguest thread entry。既存TLS regressionと今回の2 DB SQLが補助証拠。全TLS異常系を証明したわけではない |
| futex / atomic wait queues | PER-INSTANCE GO OBJECT SUFFICIENT | `ThreadPool.parkMu/parked`にguest addressで登録。違うDBの同じaddressは違うpool |
| FD table / offsets / flags | PER-INSTANCE GO OBJECT SUFFICIENT | fresh `WasiStubs.fdTable/nextFD`、host.fdFlags/flagsMu。prepared handlesも各instanceに必要 |
| MemFS / prepared writable files | PER-INSTANCE GO OBJECT SUFFICIENT | fresh MemFS.root/node tree。MapPreparedFilesはprivate writable mappings。direct proofはfresh FSのみで、prepared mappingの直接リンク統合は未実験 |
| guest args/env/cwd | PER-INSTANCE GO OBJECT SUFFICIENT | SetArgs/SetEnv、Getcwdはprivate root `/`。artifactにchdir importなし。OS env/cwdをguest用に変更しない |
| clocks/timers | PER-INSTANCE GO OBJECT SUFFICIENT | WasiStubs.monoStart、AtomicWaitのlocal timer。ただしcancel時の全timer回収は未成立 |
| host listener/session | PER-INSTANCE GO OBJECT SUFFICIENT | `host.Server`のlistener/clients/slotsはinstance fields。通常TCP port allocationはOSが実施。direct harnessはframingのみ |
| guest socket objects | UNKNOWN | actual interfaceにsocket importsあり、一部host adaptersはfail-closed。通常SQL guest protocolはprivate stdioを使用。全socket経路のin-process isolationは未実験 |
| logical process ID | UNKNOWN | host.Proc_idが`os.Getpid()`。同一processの2 DBで同じIDでも通常SQL成功。全pid-dependent guest behaviorは未証明 |
| signal inheritance/delivery | UNKNOWN | Proc_signals_sizes_getはfresh-process disposition count=0を仮定、callback registrationのみ。Thread_signal等はpanic。consumerのsignal契約を組み込む設計はない |
| normal shutdown / sequential restart | PER-INSTANCE GO OBJECT SUFFICIENT | shutdown framing → generated.Start return → SpikeWaitでworker join。今回逐次6 DB、並行6 DBの正常終了成功 |
| startup failure / driver recovery | PROCESS BOUNDARY REQUIRED | `generatedgo.run`のrecoverが`os.Exit(1)`。missing prepared filesのdirect entry試験でconsumer全体exit1 |
| abnormal worker trap/exit | PROCESS BOUNDARY REQUIRED | ThreadLaunch recoverが再panic。注入worker panicでconsumer全体exit2。Thread_exit(nonzero)、unsupported importsもこの危険を持つ |
| timeout / startup cancellation / forced Close | PROCESS BOUNDARY REQUIRED | `guest.Process.Abort`がprocess groupをSIGKILL、pipes close、Wait/reap。pure guest functionにcontext cancellation checkなし、SpikeWaitは無期限Wait |
| forced resource/memory reclamation | PROCESS BOUNDARY REQUIRED | OS process exitでworker/FD/mappingsを強制回収。正常in-process proofのGC/joinはuncooperative workerに使える強制Closeではない |

`base.WasiStubs.Proc_raise`はlibrary全体にはあるが**このartifactのimport interfaceにない**。
それを今回のsignal blockerと誤認していない。実際のsignal gapは上表のWASIX imports。

## 3. generated-Go reentrancy / globals

- ModuleのG fieldsは**707**。pure生成codeのguest-global代入先はG0
  （56,991 sites）とG1（3 sites）だけ。package-globalなMariaDB singleton heapではない。
- tableはinstanceごとに**17,197 entries**。Memoryはfresh **2 GiB backing slice**、
  guest初期visible size **256 MiB**。virtual/Go heap accountingとresident footprintは違う。
- package-globalな初期data sliceは**6,918,839 bytes**、9 packagesの`_consts` arraysは
  arm64合計**245,128 bytes**。Goのtypeとしてはmutableだが、この経路では読取り専用。
  Newがdataを各Memoryへcopyする。DataSegsのdropはModuleのslice entryをnilにする。
  `_consts`/data bufferをguestが書き換える経路は今回のsource inspectionで見つからなかった。
- active arm64 CPU feature flags3個はinitで決定するprocess-wide hardware information。
- 明確なglobal mutable bookkeepingは`diagnostic`1個、atomic spin counters3個、
  sharedimage helperのOnce/image4個。spin counterは全DB合算のscheduler hintであり
  memory/FD ownershipではない。sharedimage helperのsingletonは現在のNewWithWASIで使用しない。
- `Run(args)`は**library APIではなくcommand driver**。stdio、diagnostic flag、os.Exitを使う。
  複数goroutineからRunを呼ぶことと、fresh Module/WasiStubsを生成することを混同しない。
  今回はdiagnostic=falseを最初に一度だけ設定し、instanceごとのpipesを注入した。

従ってpackage globalsを全面的にinstance fieldsへ移すgeneric generator redesignは、
通常2 DBを動かすためには不要だった。global diagnosticsやspin hintsのpolicy、panic/exit、
worker cancellation、PID/signal、memory releaseにはlibrary用契約が必要。

## 4. 最小direct-link proof

`benchmarks/spikes/direct-link/prepare.py`がcanonical host adapterをpackage名だけ変更してcopyし、
canonical `internal/generatedgo/code`を直接importする。host methods、生成関数、MariaDB source、
memory/SIMD semanticsにはpatchしない。Run driverは正常試験では使わず、fresh WASI/FS/Module、
instance専用OS pipes、generated.Start goroutine、SpikeWaitを組み合わせた。
**native guest executableのdecode/materialize/execはゼロ**。

3 independent harness processes、各processで次を行い全成功:

| Step | Result |
| --- | --- |
| direct linked process / New / MariaDB-ready | PASS |
| SELECT 1 / CREATE / INSERT / shutdown | PASS |
| Close → second fresh instance、同名CREATE | PASS、前DBのschemaなし |
| 2 simultaneous starts / both ready | PASS |
| 同名tableにA=11 / B=22 | PASS、write/schema isolation |
| A transaction write → ROLLBACK | PASS |
| A shutdown後B query | PASS |
| all workers joined / goroutine count | before=after=2、全3 runs（main + watchdog）。FD/memory leakの長期保証ではない |

最初の`io.Pipe`版ではready frame受信後、WasiStubs.writeVecの**ゼロ長Write**が
io.Pipeで待ち、次のrequest送信と相互待ちになった。stack traceで確認し、同一process内の
OS pipesへ変更して解消。これはtest transport差異であり、MariaDB/global reentrancy failureではない。

二次的なready latency（各3観測、product benchmarkではない）:
first instance **18.9–60.1 ms**、second instance **232.9–467.4 ms**、
concurrent instances **457.7–723.3 ms**。
public wire/trust/firstSQL timerではなく、Newからready frameまで。GCを各Close後に明示している。
2 GiB Go heap backing再利用/GC/schedulingの影響を切り分けていないので、Cを高速と結論しない。
新しいresident memory測定は行っていない。過去の~88–108 MiB/processをそのままlibrary値に使わない。

故障試験は正常系と別processで実施:

- ThreadLaunchにworker panicを注入 → **exit2**。main側recoverだけでは別goroutineのpanicを隔離できない。
- canonical Runに存在しないprepared-files directoryを渡す → **exit1**。
  driver recoverがconsumer全体を終了する。checksum mismatchを無視した実験ではない。

workerの回収不能を直すruntime redesignは行わなかった。通常SQLのreentrancyは実証されたが、
**public cancellation/failure isolationを保ったdirect-linked runtimeは実証されていない**。
Snapshot/Fork direct integration、auth/full ORM/long-run acceptanceも今回の範囲外。

## 5. executable ownershipは別問題

既存Python hostは、checksum-boundな**同じinstalled executable**を各DB childに再利用する。
今回も同じ`build/mariamem-host`から2 DBを起動して、同名schema/異なるwrite、片方Close後の
他方SQL、前後SHA不変を確認した。SHAと結果をevidence JSONに保存。
初回localhost sandbox拒否は権限付きで再実行し成功、製品failureとは数えない。

このcontrolはcache実装ではない。process/Module/MemFSはfreshのままで、
executable fileのprivate ownershipを必要としないことを確認した。
content-addressed cacheのpermissions、atomic publish、concurrent materialization、
corruption/TOCTOU対策、eviction等は未実装・未検証。

## 6. ~326 MiBの内訳

HEAD tracked file size sum（Go proxyの実測zip sizeではない）:
**341,726,382 bytes / 325.9 MiB**。

| Component | Bytes / approximate MiB | Included in module source? |
| --- | --- | --- |
| accepted raw legacy-EH WASM | 18,560,224 / 17.7 | build/cache intermediate、これをさらにfull payloadとして足さない |
| canonical generated package source/shims/tests/provenance | 205,710,793 / 196.2 | yes。data6.6 MiBはGo hex literalで約26.4 MiB、残りは生成functions/aliases等 |
| darwin native executable | 78,034,498 / 74.4 | raw fileはno、次のcompressed sourceに含まれる |
| linux native executable | 80,265,934 / 76.5 | same |
| gzip darwin / linux | 42,731,042 / 40.8、45,249,242 / 43.2 | 次のbase64 sourceの中身 |
| 2 platform base64 Go image source | 117,307,672 / 111.9 | yes。gzip bytesに約4/3 encoding expansion、2 platform分を加算 |
| other tracked source/docs/reports/licenses | 約18,707,917 / 17.8 | yes。上記raw exe/gzip/WASMを二重加算しない |

したがって78–80 MBを単純に326 MiBへ展開したのではない。
**生成Go約196 MiB + 両platform encoded executable約112 MiB + その他約18 MiB**の重複配布。

Bのcacheだけではmodule sizeは変わらない。同じembedded sourceを使う限り112 MiBは残り、
per-DB一時raw executable/stream decodeが一度のprovisioningになる。
Bを外部分離artifact配布にすればencoded payloadを除ける可能性はあるが、download/trust/offline
contractの別設計が必要。今回は採用しない。
CはGo consumerからencoded platform images約112 MiBを外せるが、生成source約196 MiBと
consumer native binaryのMariaDB codeは残る。platform-specific shims/asmは依然必要。
Python wheelはCのGo consumer経路でもowned host binaryの配布が必要。

## 7. A / B / C comparison

| Criterion | A: private executable + process | B: shared immutable executable + fresh process | C: direct linked instance |
| --- | --- | --- | --- |
| normal DB isolation / multi-instance | acceptance済 | same ownership、今回2 DB control成功 | 今回通常framing成功、full acceptance未実施 |
| cancellation / worker panic containment | kill/reap、既存契約 | Aを維持可能 | current shimではconsumer exit、強制worker stopなし |
| normal lifecycle | acceptance済 | Aと同じ | sequential/join成功、long-run未証明 |
| implementation complexity | 現在の方式 | provisioning ownership/trust/cleanup policy | library entry、errors、worker stop/join、signals/PID、memory ownership必要 |
| module size | 325.9 MiB | embedded inputなら同じ | image分約111.9 MiB除去可能 |
| startup evidence | Go public p50~1242 ms | Python control public~89 msはinstalled exe再利用。ただしGo cache benchmarkではない | first ready18.9–60.1 ms、later232.9–723.3 ms、境界が異なる |
| distribution | offline embedded、各DB materialize | checksum-bound provisioningを一度実施、cache信頼設計追加 | Go source直接build、consumer compiler互換性が必要 |
| testability | process faultを隔離して検証 | 同じ | object unit test可能、worker panic試験はtest processも死ぬ |
| portability | pinned supported platform binary | same | Go build/asm/runtimeがconsumer toolchainで動くことを追加検証 |
| Snapshot/Fork | production cold-file semantics acceptance済 | fresh runtime/file isolationは維持可能、cache版未acceptance | prepared files再構築は概念上可能、direct export/restore/API契約未検証 |

### pgmem structural reference

確認revision: `ed2c23f79a93feb267070784576dd2eedb6cdef2`、branch `postgresql/18`。
[internal/aot/aot.go](https://github.com/shibukawa/pgmem/blob/ed2c23f79a93feb267070784576dd2eedb6cdef2/internal/aot/aot.go)
ではFactoryがgenerated Moduleとhost importsを各instanceに生成し、初期data imageを共有、
memoryはprivate view。callVoidがexit/abort/trapをerrorに変換し、Closeでowned mappingを解放する。
[root aot.go](https://github.com/shibukawa/pgmem/blob/ed2c23f79a93feb267070784576dd2eedb6cdef2/aot.go)
はFactoryをengineへ登録する。[engine](https://github.com/shibukawa/pgmem/blob/ed2c23f79a93feb267070784576dd2eedb6cdef2/internal/engine/engine.go)
はfactoryとper-cluster FSを使う。これはlibrary contractが明示されている構造例である。
PostgreSQLのvirtual processとMariaDBのpthread workerは異なり、callVoidのrecoverだけで
mariamemの別goroutine panic/cancellationが解決するとは推論しない。pgmemを移植しない。

## 8. Verdict / smallest next step

### `PROCESS BOUNDARY REQUIRED, PRIVATE IMAGE NOT REQUIRED`

**現行v0.4のbounded failure/cancellation契約を維持する限り**、process boundaryを残す理由は
実測とcodeで裏付けられた。MariaDBの正常実行が本質的にOS processを要求するわけではない:
一instance、逐次instance、並行instanceは直接リンクで成功した。
将来のdirect libraryには実行中の全workerを安全に停止/回収し、trapをconsumerから隔離する
新しいlibrary lifecycle contractが必要で、今回それがboundedに実現できるとは証明していない。

DBごとのprivate executableは不要だった。最小の次の作業は、**immutable checksum-bound
executableを一度provisionしfresh childから再利用する限定prototype**のtrust/isolation/
concurrency/cleanup検証。Go cache warm/coldの効果を測ってから製品化を判断する。
このtaskではその実装も、direct runtime redesignも開始しない。

Validation: 3 direct functional campaigns、2 failure containment probes、shared-executable control、
generated source/image provenance verifier、`git diff --check`。production source変更がないため
full ORM/Go/Python acceptanceや性能campaignは再実行していない。Windows検証なし。
