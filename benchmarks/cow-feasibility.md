# v0.4 CoW feasibility

## Source / environment / scope

開始点はaccepted `v0.4/wasm2go-spike` **965da8c9d2702e6ecdd830d684e8463d31e94311**。
MySQL-wire startup-tail characterizationを含み、最終判定は
`GREEN CANDIDATE — TAIL UNDERSTOOD`。local/origin一致を確認してから
`v0.4/cow-spike`を作成した。main、production runtime、public API、Snapshot/Forkは変更していない。

2026-10-01、固定reference環境：Apple M1 / 16 GiB、macOS 27.0 (26A428)、
Go 1.26.8、Python 3.14.7、OS page 16 KiB。既存legacy-EH guestをそのまま使用：
SHA256 `6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3`。
converter/既存bounded WASIX shimは前spikeと同じ。legacy guestのWasmer 7.4.2による
cross-runtime validationができないという制限も継続する。

比較referenceはgenerated-Go RSS約108 MiB、footprint約88 MiB/DB、×16約1.375 GiB、
direct ready median約40 ms、wire+verification+SQL約99 ms、wire CPU約0.109 CPU-s。
Wasmer baselineはStart→SQL308.5 ms、prepared Fork→COUNT288.7 ms、約281 MiB/DB。
今回の測定は**direct guest process**で、wire/trust検証を含まない。製品benchmarkではない。

raw page hashes / logs / generated Go / binariesはignored `benchmarks/results/cow/` 内の独立go.modに隔離。
再現用[templates/scripts](spikes/cow/)と[compact trial evidence](spikes/cow/evidence.json)を公開する。
利用者の既存未追跡npm filesは保存し、check中の一時退避後に同じhashで復元した。

## Measurement method and limits

- stage/content系列：各workloadを独立processで3回、計15。mincoreでresidentページだけをSHA256 fingerprint。
  linearはOS page、MemFSは16 KiB logical blockごと。connection close後2秒の通常idleをpreparedとする。
- 別のOS-only系列：同じ15試行・同じstageで内部content observerを呼ばず、既存`process-cost`の
  RSS / physical footprint / CPUと`vmmap -summary -wide`だけを取得する。
  footprintのstage差はこの系列を使用する。
- content deltaは**残った内容差分**で、write history / VM dirty-bit / coherent snapshotではない。
  writeして元に戻す操作は見逃し、非resident→residentの変化は含む。background guest writesも含む。
  MemFS fingerprintは非resident blockをunknownとして扱い、完全なfile checksumではない。
- 最初のpilotで全150 MiBのMemFS内容をhashすると疎なzero pagesまでfaultし、footprintが約90→250 MiBに増えた。
  このpilotを除外してresident-onlyに修正した。修正後もobserverのJSON/hash-map allocationsが残るため、
  **content系列のfootprint増加をworkloadのメモリ増加と解釈しない**。強制GCやGOGC変更はしない。
- macOS `phys_footprint`はtaskへのphysical charge。Linux PSS/private-dirtyそのものではない。
  helperの`private_bytes`はnull。vmmapのDIRTY、mappingのSM=COW/PRVを併用するが、shared clean/dirtyを
  全DBについて厳密に分配した値は得ていない。file-backed mincoreはfile cacheも反映し、RSSと一致しない。
  shared-cache/libraryのvmmap総residentを足してprivate memoryと見なさない。

## A. Current memory attribution

readyのOS-only median：**RSS114.1 MiB / footprint89.1 MiB**。
前referenceの108/88 MiBとの差にはobserver/controlを含むbinary・時期・sampling boundaryがある。
proofには同じbinaryのfresh controlを置く。採用した代表vmmapではanonymous `Untagged`が
**2.2 GiB virtual / 86.1 MiB resident・dirty**で、footprint89.0 MiBの大半を占める。

| component | 実測 / sourceで確認したこと | attributionの限界 |
| --- | --- | --- |
| Guest linear memory | 最大2 GiBのGo `[]byte`、ready resident約75.5 MiB、logical size中央値656.9 MiB | logicalは試行間639–729 MiB。heap reservation/growthはphysical allocationではない |
| MariaDB heap / state | C/C++ malloc領域、InnoDB、guest pthread stacks等はlinear内 | Go heapと別加算しない。guest allocator内訳を今回の非侵襲観測では分離できない |
| InnoDB | source `wasm/lite4mariadb.c:l4m_open`にbuffer pool16 MiB、log buffer2 MiB等 | 設定値であり、それぞれのresident量の実測ではない。変更なし |
| MemFS files | prepared logical/capacity150.18 MiB、hash可能resident内容約4.77 MiB | Go heap内。unresidentゼロ領域とarray境界があるためphysical privateの精密値ではない |
| Go heap / bookkeeping | ready HeapAlloc約2,201 MiB、うち2,048 MiBがlinear backing、約150 MiBがMemFS logical arrays | HeapAllocをRSSと比較しない。残る数MiBにtables、host、fs nodes、fd maps等が混在 |
| Go / native stacks | Go StackInuse約0.56–0.66 MiB、代表OS Stack resident160–176 KiB / virtual11–12 MiB | guest pthread stacksはlinear内。OS/Go/guestを同一stackとして数えない |
| Generated executable | proof binary約79.3 MiB、own `__TEXT`44.1 MiB virtual / 15.2 MiB resident / DIRTY0 | codeは通常OS共有済み。`__DATA_CONST`等は一部private relocation/runtime data |
| Other private / OS | page tables約0.6 MiB、malloc metadata、小さいlib/runtime writable state等 | 他の匿名領域を含む残差。正確なfunction単位の内訳は不明 |

したがって約88 MiBは「巨大なDB filesの全量」ではなく、主として**residentなlinear state約75 MiB**、
小さいresident MemFS内容、Go/runtimeのprivate stateで説明される。text/libraryの共有を新たに実装する必要はない。

## B. Prepared 1,000-row state

既存fixtureと同じ`benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB`、
ID0–999、32文字payload、transactionでload/COMMIT/COUNT。buffer/cache/timeout/durability設定は変更なし。
guest initializedはgenerated constructor終了、guest threads/MariaDB開始前。

| stage | OS-only RSS MiB | footprint MiB | resident linear MiB |
| --- | ---: | ---: | ---: |
| initialized | 37.27 | 22.70 | 15.16 |
| MariaDB ready / session open | 114.12 | 89.08 | 75.55 |
| schema created | 115.66 | 89.20 | 75.56 |
| fixture loaded / COMMIT / COUNT | 118.42 | 89.83 | 75.56 |
| connection closed / 2s idle | 118.44 | 89.83 | 75.56 |

readyまでに約66 MiBのphysical chargeが増え、fixture準備の追加は約0.75 MiB。
preparedにはsystem/undo/redo/temp files、schema/data、InnoDB buffer/metadata、auth keys、thread/TLS/locksが存在する。
residentな準備状態は小さいfixtureだけでなくMariaDB全体の初期化を重複している。

代表prepared MemFS：redo`ib_logfile0`96 MiB、`ibdata1`12 MiB、`ibtmp1`12 MiB、undo3 files各10 MiB、
fixture `.ibd`160 KiB、`.frm`1,208 B。redo resident内容約0.14 MiB、temp約2.05 MiB、
undo合計約2.14 MiB、fixture `.ibd`約0.14 MiB。**150 MiBのlogical file sizeを共有可能physical量としない。**
通常shutdown・worker join後にclean filesystemをexportして観察したが、filesystem共有prototypeは作成していない。

独立prepared instancesでOS-page alignmentが一致した13試行の同一offset/contentは
**66.77 MiB**、うちzero-content **38.09 MiB**。残る2試行は8 KiBずれのGo backingで比較から除外した。
これは候補内容の存在を示すだけで、safe-to-share/clone判定ではない。zero pageもmutex/allocator stateを持ち得る。

## C. Workload dirtying / retained state

各workloadの前に同じfixtureを独立に準備。数値は3回のmedian。
content差とOS-only footprint差は別系列なので、同じtrialの精密なaccountingではない。

| workload | linear content delta MiB | MemFS changed blocks / MiB | footprint増加 MiB | connection close後の増加 MiB |
| --- | ---: | ---: | ---: | ---: |
| COUNT + 20 PK reads | 0.672 | 0 / 0 | 0.000 | 0.000 |
| INSERT + UPDATE + COMMIT | 0.938 | 1 / 0.016 | 0.000 | 0.000 |
| INSERT + UPDATE + ROLLBACK | 0.938 | 3 / 0.047 | 0.172 | 0.172 |
| CREATE TABLE | 1.094 | 7 / 0.109 | 0.094 | 0.094 |
| SQLAlchemy representative workload | 1.938 | 14 / 0.219 | 0.562 | 0.578 |

詳細file namesとclose後content差はevidenceに保存。writesはredo/undo/data、DDLはschema/data/recovery filesにも及ぶ。
OS-only vmmapのanonymous `Untagged` DIRTY増加medianはread/write/rollback/schema/ORM順に
**0 / 0 / 約0.1 / 約0.1 / 約0.5 MiB**。vmmap表示の丸めと混在heapがあるため精密なprivate-dirty差ではない。
ROLLBACKもundo/log/runtime stateをdirtyにするため「SQL上取り消したのでimageも元通り」とは言えない。
小さいphysical増加は既存resident pageへのwriteを隠す。**将来のCoWではこの既存pageへのwriteにもprivate copyが必要**。
準備済み約75.6 MiBからcontent差を引いた73–75 MiBを「shareできるphysical」と断定できない。
長いsuite・大きいtables・purge/checkpointなど時間経過に伴うdirtyingは未測定。

### ORM compatibility finding

既存`tests/consumer/test_sqlalchemy_dogfood.py`を使った。
通常`prepare()`の`create_all`存在確認は、missing tableへの`DESCRIBE`で
**MariaDB1030 / Aria I/O error29**を返した。3試行とも再現し、runtime修正は行っていない。
失敗を記録したうえで、同じSQLAlchemy modelsを`create_all(checkfirst=False)`で作成し、同じUser/Address seedを投入。
既存`test_03_update_commit_and_delete`を変更せず実行し、update/join/commit/delete/countは成功した。
この測定はfailed probeと同等fixture setupも含む。**通常dogfood全体の成功ではなく、限定workloadの結果**。
generated-Goのfilesystem/Aria compatibilityに新しいhardening課題がある。CoWによる回帰ではない。

## D/E. Sharing layers and cloning models

| layer | plausible sharing / constraint |
| --- | --- |
| Generated code | OS executable mappingsで既にclean pages共有。code-only CoWの追加gainは小さい |
| Linear memory | C/guest pointersはlinear offset、same DB threadsは同じmemory backingを共有。2 GiB安定addressのprivate file mappingは実行可能。Go GC所有から外す場合、明示ownerとunmap、全threads/host callbacks停止が必要 |
| Prepared linear state | VM bytesだけではgoroutine/pthread実行位置、wait queues、TLS、fds、timersを再構成できない。mutex・thread identifiers・host参照のrestore契約が必要 |
| Filesystem | immutable base + block/file overlay、private mmap、APFS reflink等は概念上可能。現MemFSはGo arraysで、grow時に全copyする。reflinkだけではそのarraysは共有されない |
| InnoDB files | undo/redo/temp/system filesもprivate writesが必要。clean shutdown imageまたは検証済みconsistent snapshot、LSN/recovery/flush ordering、truncate/grow/unlink/renameを保持する必要 |
| Go/runtime | goroutines、sync primitives、channels、Go timers、fd maps、host objects、thread/TLS lifecycleをlive複製しない。OS `fork()`後にmultithreaded Go/MariaDBを継続する案はsafeなclone手段ではない |

| model | このspikeから言えること |
| --- | --- |
| A. Memory-image CoW | physicalの大きい対象。initialized imageは実証済み。MariaDB-ready imageはthread/runtime reconstructionが未解決 |
| B. Filesystem CoW only | runtime/threadsをfresh生成でき、snapshot整合性は比較的限定できる。ただし現fixtureのresident FS約4.8 MiBがmemory gainの目安であり、150 MiB削減ではない。bootstrap省略のlatency効果は未測定 |
| C. Hybrid | FS base + thread-free immutable memoryを共有し、runtime/TLSを再構築する可能性。何をreinitializeしてもMariaDB semanticsを保つか設計が必要 |
| D. OS process fork | Go multi-thread runtimeのcontinuationは採用可能と実証していない。fork-execではguest live heap cloneの利点を得られない。分析のみ、実装なし |

**大きい期待gainはlinear側**。filesystem側は重要なsnapshot/lifecycle論点だが、この小さいfixtureではresident量が小さい。
GC非所有mappingは技術的に可能でも、pointer/address stabilityだけではthread stateの安全な復元を証明しない。

## F/G. One bounded proof: initialized linear image

MariaDBやpthread開始前、generated constructorのTLS/data/BSS初始化だけを保存した。
既存converterの`NewFromSnapshot`を使い、4 mutable globalsとdropped data segmentsを復元。
新しいfunction tables / host / WASI / MemFS / thread poolを各processで生成し、通常guest startupを実行する。
MariaDB source・config・WASIX semanticsは変更なし。production Snapshot/Forkには接続しない。

- readonly sparse file：virtual2 GiB、captured resident extents15.16 MiB。論理初期memory256 MiB。
- **cow:** readonly fdから`MAP_PRIVATE`, RW child view。shared growは2 GiB backing内のlogical limit更新。
- **anon control:** private anonymous2 GiB mmapに同じinitial extentsをcopy。GC所有変更の効果を区別する。
- **fresh control:** 同じbinaryで元のGo `make([]byte, 2 GiB)` constructor。
- all guest workers join、observer HTTP server shutdown後にexplicit munmap。processをreapする。
- captured extents、representative sparse holes、globals/metadataを含むbase checksumを前後比較：
  `c3e456f1ff672743184b150d7bd8ade4dfe38726adaecd05a0caa725b0cd3e62`で一致。
  full2 GiBのdisk scanはしない。base readonly・private mappingによる非変更とSQL isolationも確認した。
- proof binary SHA256 `e9c1821173db0d5460a401a009837fb676b8495bec5f7b1ea97eb5d13d87e28c`。

fresh / anon / cowすべて、既存22-record SQL assertions（ready、SELECT1、CRUD、COMMIT/ROLLBACK、constraints、
2 sessions、shutdown）とauth self-test成功。cow children A/Bは各1,000 rowsを持ち、AのUPDATE/DDL/
uncommitted write/COMMIT/ROLLBACKがBのrows/schemaを変えない。A shutdown後BはSQLを続行できた。
20回のcreate/SQL/closeは成功、retained guest processes0。
これは**process isolationとmapping cleanup**の証拠で、同一Go processで多数DBをcloseしたheap回収の証拠ではない。
FSは各子独自なので、共有FS overlayのisolationを検証したという主張もしない。

## H/I. Exploratory scaling / startup

×1は各mode10試行、×4/8/16は各3group trials（合計57 groups）。modeを交互に実行。
guest process開始→ready→session open/SELECT1を測り、その後各DBにfixtureをloadする。
build/transpilation/base作成は起動時間に含まない。内部observerは呼ばない。

| mode / DBs | group ready p50 ms | first SQL p50 ms | RSS / DB MiB | footprint / DB MiB | total CPU to ready CPU-s |
| --- | ---: | ---: | ---: | ---: | ---: |
| fresh ×1 | 26.2 | 26.8 | 113.92 | 88.99 | 0.036 |
| fresh ×4 | 1047.7 | 1051.2 | 113.96 | 89.00 | 0.203 |
| fresh ×8 | 1066.4 | 1069.4 | 114.18 | 89.25 | 0.458 |
| fresh ×16 | 1117.5 | 1122.8 | 114.29 | 89.35 | 0.880 |
| anon ×1 | 27.3 | 27.8 | 105.46 | 86.81 | 0.037 |
| anon ×4 | 46.8 | 48.0 | 105.57 | 86.85 | 0.220 |
| anon ×8 | 1063.6 | 1065.5 | 105.66 | 87.04 | 0.478 |
| anon ×16 | 1124.9 | 1130.9 | 107.76 | 92.77 | 1.011 |
| cow ×1 | 29.3 | 29.8 | 100.88 | 80.45 | 0.040 |
| cow ×4 | 1050.4 | 1053.1 | 101.07 | 80.57 | 0.241 |
| cow ×8 | 1082.9 | 1086.0 | 101.12 | 80.68 | 0.555 |
| cow ×16 | 1132.3 | 1137.2 | 101.12 | 80.69 | 1.050 |

代表ready vmmap：cow linear mapping **2 GiB virtual / 70.9 MiB resident / 69.1 MiB DIRTY**、
other anonymous dirty約8.5 MiB、task footprint80.5 MiB。
そのDIRTYを全DBに対する精密private-dirty/PSS測定とは呼ばない。
anonymous control同×1の86.81→cow80.45 MiBは**約6.36 MiB / 7.3%**減。
fresh88.99→anon86.81 MiBの約2.18 MiBはownership/GC/bookkeeping等の別効果を含み、CoWだけに帰属しない。

×16 fresh89.35→cow80.69 MiB/DB、**9.70%減**。
`(cow×16 total − cow×1 total)/15`の追加DB chargeは**80.71 MiB**。
task footprint合計は1.261 GiB、base captured extents15.16 MiBを保守的に一度足すと約**1.276 GiB**。
matched fresh合計1.396 GiBに対して約8.6%減、過去reference1.375 GiBに対して約7.2%減。
15.16 MiBはshared file cacheの厳密なsystemwide residency計測ではなく、baseの一回分を無視しないための見積り。
RSSはshared pagesの重複計上を含むため、RSS差だけでCoW効果を主張しない。

fixture後footprint medians：fresh/anon/cow ×1は89.74/87.57/81.21 MiB、×16は90.14/93.53/81.46 MiB/DB。
instanceのclose/reap後guest charge0、全exit0。ただしbase file cacheは残り得るし、controller自身のmemoryは含めていない。
**他のmemory変動を隠さない：** anon×16の3 trialsは92.77/87.02/93.06 MiB、cow×8は80.50/92.84/80.68 MiB。
GC/runtime/cacheの候補はあるが今回因果を特定していない。×16 anonの高いmedianだけを選び大きなCoW gainを算出しない。
一部group vmmapはsandbox下で失敗したため、その数値は採用せず、別許可環境で各modeのready mappingを取得した。

単一first SQL min/p50/p95/max (ms)：fresh **25.6/26.8/587.0/1042.4**、
anon **25.9/27.8/33.9/36.0**、cow **28.5/29.8/33.6/34.2**。
10試行の補間p95はtailを代表しない。≥500msはfresh1/10、anon0/10、cow0/10。
×16は全mode3/3 groupsが≥500ms。既知guest-side約1秒pathは残り、頻度の改善を主張しない。

**子作成latencyの改善は実証していない。** initialized base→fresh MariaDB→SQLはcow29.8 msでfresh26.8 msより速くない。
fixture load/COUNTまでの×1 medianはfresh34.3 / anon35.4 / cow37.4 ms。
**prepared DB base→child→first SQLは未測定**。ready-memory/thread restoreを実装していないためである。
fast direct startupが既に数十msでも、public trust/wire境界やprepared Forkの同等性は別課題。

## J. pgmem conceptual reference

[pgmem README](https://github.com/shibukawa/pgmem)と
[v1.18.0 API documentation](https://pkg.go.dev/github.com/shibukawa/pgmem@v1.18.0)は、
snapshot時のserver停止/CoW data clone/restart、forkごとのfresh backend・private buffer cacheを説明している。
作者の約64 MB追加/fork、数十msという目安は、小さいbuffer設定とshared prepared filesを前提とする参考値で、
こちらの測定ではない。README参照時`postgresql/18` HEADは`04afc37ae24d8349d705b78b42096cd3ff584286`。
[AOT base API](https://pkg.go.dev/github.com/shibukawa/pgmem@v1.18.0/internal/aot/pgaot/base)にはGC非所有の
private CoW memory-image mappingもある。

mariamemにもfresh backend + immutable FS base、thread-free initialized memory imageという対応候補はある。
ただし現在のMemFSにはoverlay契約がなく、MariaDB/InnoDBのundo/redo/temp/buffer dirtyingも異なる。
pgmemの64 MBをMariaDBの達成値に置き換えず、prepared cloneの停止・再構成契約から検討する必要がある。

## Decision inputs / remaining questions

- **約88 MiBの主要因：** resident linear約75 MiB。proof後もlinear DIRTY約69 MiBが最大。
- **理論的共有候補：** preparedの同一内容約66.8 MiBとworkload後の小さいcontent deltaは有望。
  ただしcopy-on-write faultのwrite履歴、長期background dirtying、安全なclone境界は未証明。
- **read/write/ORM後：** content差約0.67/0.94/1.94 MiB、physical新規増加約0/0/0.56 MiB。
  前者をprivate-copy量の下限保証や上限保証として使わない。
- **Linear CoW：** mmap ownership/address/growは実証。MariaDB-ready cloneにはmeaningful thread/TLS/FD/lifecycle設計が必要。
- **Filesystem CoW：** plausibleだが未実証。このfixtureでのmemory対象はresident約4.8 MiB、larger gainはlinear側。
- **共有できないもの：** running Go/runtime objects、host waiters、timers、fd/TLS lifecycle。per-child auth/trustも保持する。
- **追加DB physical：** initialized-image proof約80.7 MiB、matched fresh約89.4 MiB。約9.7%のcharge削減は実証したが、
  OS-shared base/cacheを一回分含めると×16全体の削減は約8.6%。半減やpgmem並みのmemoryは実証していない。
- **fork cost：** prepared clone未実装・未測定。initialized imageだけではstartup/CPU改善なし。
- **wasm2go後もworthwhileか：** 大きいresident linearと小さいworkload content差は追加探索の価値を示す。
  今回の約8–10% gainだけでproduction化コストが正当化されるとは断定できない。

次に勧めるarchitecture experimentは、**MariaDB-ready linear stateの安全なclone境界とthread/TLS/FD再構成の縮約検証**。
warm snapshotの安全性・必要private bytes・background write historyを先に確認する。
このtaskでは開始しない。FS-onlyとのproduction architecture選択も保留する。
加えてAria schema-discovery、signals/abnormal termination/cancellation、thread cleanup、legacy-EH pipeline、
shared image verification/ownership、multiplatform memory accountingが未解決。

## Regression / verdict

通常`verify.py check`：Go unit / vet成功、Python **368 passed / 3 skipped (8.57s)**、public source **364 files**成功。
通常Wasmer `verify.py integration`：Go race **9.030s**、Python lifecycle/multiclient **3 passed (2.41s)**。
生成filesは独立module、tracked Go templatesは`.go.txt`。`git diff --check`成功。

### YELLOW — COW POSSIBLE, ARCHITECTURE WORK REQUIRED

bounded initial-image sharingはisolationを保ちphysical chargeを削減した。
しかし主要なprepared stateをcloneするにはruntime/thread/filesystemの復元契約が必要で、prepared-child latencyは未実証。
この結果だけでproduction architectureを選ばない。
