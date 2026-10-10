# Block Storage Design Discovery — absurd-sql / AbsurderSQL

2026-10-10。v0.4.x VFS文献調査の最終追加資料。調査のみ。
実装、外部コード導入、新規benchmark、Release CI、main、v0.4.6候補は変更しない。
Astraの技術判断のために、ソースで確定する挙動と未測定の仮説を分ける。

## 1. Executive summary

**論理EOFと実体化したブロックを分離する設計は、大きな初回予約を連続heapへ
即時確保する問題の候補になる。ただし、この二実装を移植する根拠はない。**

- absurd-sqlの通常IndexedDB経路はSQLite page単位のkey/value保存。
  EOFだけの拡張はmetadata更新で済み、未保存ブロックはzeroとして読める。
  memory backendとSharedArrayBufferなしのfallbackは別挙動である。
- AbsurderSQLのWASM main DBは固定4 KiBブロック。EOFだけの拡張では全fileを確保しない。
  ただしglobal store、cache、dirty buffers、restore/exportのコピーがあり、
  cache capacityを総メモリ上限と扱えない。auxiliary/WALも同じblock方式ではない。
- どちらも、この経路にmariamem相当の不変Snapshot＋独立ForkのブロックCoWを提供していない。
  同じDBへのconnection共有やcommit markerは、子間の書き込み隔離と違う。
- shrink後の旧block保持・regrow・EOF readにはWASIX移植上の問題がある。
  SQLite向けの成功例をMariaDBのzero-fill/FD/並列I/O契約の証明にしない。
- MAP_PRIVATEは既に容量内更新のOS page-level CoWを持つ。
  block化の追加価値は未使用reserveやmapped-file growthにあり得るが未測定。
- **ファイル別の初回確保・再確保の限定計測を優先する現行計画を変更する証拠はない。**
  allocation減少率・RSS減少率・wall time改善率をこの資料から推定しない。

## 2. Source provenance / 調査の範囲

| 対象 | 固定source commit / 範囲 |
| --- | --- |
| mariamem調査baseline | `f306fa697edb8410973d1a61ec3ebbcb16ac0e7d` |
| absurd-sql | `1bff34fc3482a78955f00640f080bd7ec7852828` — File、SQLiteFS、IndexedDB worker/channel、fallback、memory backend |
| AbsurderSQL | `1113358cc4c69fc980ceb1334fb3e9330c330dd1` — WASM VFS、block/cache/metadata/allocation、persist/restore/import/export/cleanup、関連tests |
| pgmem先行レビュー | [報告書（55c5639）][pgreview]。対象pgmem `3433a40bd4167daea2d8e364666bd5fcf18ef654` |
| memfs/pglite先行レビュー | [memfs-optimization-discovery.md](memfs-optimization-discovery.md)、同報告のprofile sourceと入力hash |

取得した61ファイル、819,617 bytesのpath/size/Git blob SHA1/SHA256を
[inputs.json](block-storage-evidence/inputs.json)に保存。
GitHub Contents APIのbase64をdecodeし、`SHA1("blob " + len + NUL + bytes)`をAPI blobと照合した。
READMEは入口だけに使い、以下の結論は固定ソースを参照した。
すべてのupstream機能・platformを認定したものではない。上流testsは読み、今回は実行していない。

再取得手順: `gh api repos/<owner>/<repo>/contents/<path>?ref=<source_commit>` の
`content`をdecodeし、inputs.jsonの三つのidentity（size/blob/SHA256）と照合。
報告中のsource anchorも同じ固定SHAを使う。取得source copiesは完了後削除する。
調査branchは `experiment/block-storage-discovery`、disk budget 1 GiB / minimum free 8 GiB。

主要参照位置:

| 実装 | Source / symbol / 行 |
| --- | --- |
| absurd block分割・RMW・EOF | [sqlite-file.js][afile]: getBoundaryIndexes L12、readChunks L19、writeChunks L59、File L105、read L185、write L230、fsync L374、setattr L442 |
| absurd backend通信・hole | [file-ops.js][aops]: positionToKey L3、invokeWorker L55、readBlocks command L69、delete L176、open L194 |
| absurd永続化・lock | [worker.js][aworker]: Transaction L23、withTransaction L344、lock protocol L367、handleRead/handleWrites/meta L497–572 |
| absurd例外経路 | [fallback][afallback] L132–260、[memory/backend.js][amemory] FileOps.readBlocks/writeBlocks |
| Absurder live VFS | [indexeddb_vfs.rs][bvfs]: register L297–327、IndexedDBFile L502、read L535、write L611、x_open L959付近、x_read L1379、x_truncate L1519、x_delete L1625 |
| Absurder cache/owner | [block_storage.rs][bstore]: BLOCK_SIZE L169、fields L262–344、new_sync L360、touch_lru/evict L932–976、reload L1442 |
| Absurder actual block I/O | [io_operations.rs][bio]: read_block_sync_impl L78、write_block_impl_inner L383、global update L498–696、cache/dirty L698 |
| Absurder allocation/reuse | [allocation.rs][balloc] L62/174/332 |
| Absurder persistence/copy | [vfs_sync.rs][bglobal] L12–105、[export.rs][bexport] L453–482、[import.rs][bimport] L189–281、[hybrid_store.rs][bhybrid] L44–75 |
| Absurder teardown | [cleanup.rs][bcleanup] cleanup_all_state L7–77、block_storage.rs Drop L147–167 |

## 3. absurd-sql の実装

### 保存・allocation・I/O

通常経路は `SQLiteFS → File → FileOps → SharedArrayBuffer channel → worker → IndexedDB`。
fileごとにIndexedDB database、object store `data`。block keyはpage index、`-1`はsize metadata。
block sizeは**SQLite headerのpage size**（512～65,536 bytes）から決める。
初回writeはheaderを含む必要があり、任意の空file末尾へ書く汎用FSではない。
codeの理由はSQLite pageとの対応。8 KiB推奨を最適なMariaDB chunk sizeの実測根拠にはしない。
worker readMetaはblock0からpage sizeを復元する。既存fileのpage-size変更もfsyncが特別処理する。

`setattr(size)`は論理サイズのみ更新。fsyncがsizeをpersistする。
通常FileOps.readBlocksは存在しないrecordをzeroのArrayBuffer(blockSize)へ変換する。
readChunksは要求長のbufferを作り、各blockの必要部分をcopyする。
File.readはEOF越えをzero埋めし要求lengthを返す。POSIX/WASIXのEOF/short-readとは区別する。
writeChunksは境界で分割し、触れたblockのbufferを確保。
full blockは直接pendingに置き、partial blockはloadして同block内RMWで既存bytesを保持する。
random writeはfile全体のresizeを要求しないが、block allocation/copyとchannel/IDB処理はある。

File.bufferはdirty blockのMap、fsync後に空になる。workerはSQLite cacheへ任せる設計で、
transaction中のfirst blockを保持する。これはdirty setやSQLite自身のcacheに対する全体上限ではない。
各openは二つの36 KiB SharedArrayBufferとbackend workerを使う。
同じblockを繰り返すwriteでもtemporary bufferを作るので「小writeがallocation-free」とは言えない。
page-size変更時は全pending writesを連続bufferへまとめて再分割する経路もある。

**shrinkはblockを削除もzeroもせずsizeだけ更新する。** fsync内に末尾block未削除のTODOがある。
regrowで旧blockが再び読めるため、一般FSのshrink→regrow zero保証として使えない。
physical保存量は論理sizeだけから求められない。全file deleteはdeleteDatabaseで非同期、
errorはwarning、open FDを維持するunlink semanticsを実装した証拠にはならない。

### fallback / memory を混同しない

SharedArrayBufferなしではreadIfFallbackが**全保存blocksをMapへreadAll**。
local lockは常に成功、変更のcross-connection可視性を通常経路と同じにはしない。
fallback.readBlocksはmissing valueをそのまま返し、通常経路のblank-block変換がない。
したがって疎なholeの安全なread保証をfallbackへ広げない。

memory backendは一つの連続ArrayBuffer。writeBlocksが各writeの末尾までexact-size拡張し、
旧全内容をcopyする。**absurd-sqlの全backendがsparse/block-residentなのではない。**

### concurrency / Snapshot

通常workerはSQLiteのlockをIDB transactionへ対応させ、readwriteを直列化し、
upgrade時にfirst-page change detectionを使う。channelはAtomics.wait/notifyで同期する。
これは同DBを利用するSQLite接続の調停。MariaDB multi-workerのpread/pwrite/truncateを
同じ方式で安全にできるという証拠ではない。
block recordは更新される可変値。Immutable root、child overlay、shared-block refcount、
Snapshot後のbaseline保護、独立Forkの実装はこの経路にない。
IDB transaction isolationをSnapshot/Fork CoWと呼ばない。

## 4. AbsurderSQL の実装

### fixed block と実際の経路

WASM registerが結ぶのは `x_read/x_write/x_truncate`。名前にstubがある旧callbackを
live behaviorと誤認しない。native IndexedDBVFSはstorageを使わずdirect file I/Oという
明示commentがある。以下は**WASM main DB**を中心とした調査で、native test mirrorsと区別する。

BLOCK_SIZEは固定4,096 bytes。xSectorSizeも4,096、x_openは最大block IDからfile sizeを復元する。
SQLite page_size=1 KiBのpartial-block testがあるため、DB page sizeと常に同一ではない。
ソースは4 KiB固定を確定するが、Go/MariaDB向けに4 KiBが最適な理由・測定はUnknown。

main fileのEOFはhandle.file_size。x_truncateはその値だけ変える。
writeはoffsetをblock IDとin-block offsetへ分けて、read_block_sync→変更→write_block_sync。
**live経路はfull block writeでも最初にreadする。** readを省く分岐は
`transaction_active && false`で無効化されたwrite-buffer経路内にあり、現行最適化として数えない。
block I/Oはmissingをzero VecへできるWASM経路を持つが、visibility/versionによるzeroもある。
readはVecをcloneして返し、cacheに別cloneを置く経路を持つ。
main readはhandle.file_sizeでclipしない。x_readのshort-read zero処理をもって
logical EOF外のreadが隠れるとは言えない（main readは要求量を返す）。

ephemeral rollback journalは連続Vec、WALは別thread-local WAL_STORAGEの連続Vec。
writeには16 MiB WAL limitがある。これをMariaDB redo等の許容サイズへ転用しない。
main-file sizeと物理block数は別。ただし再openでmax-blockからEOFを復元するため、
metadata-only拡張/shrinkの正確なEOFがpersist/reopen後も保たれる保証は確認できない。

### cache は総メモリ上限ではない

WASMで `GLOBAL_STORAGE[db][block] = Vec<u8>`、metadata/commit/allocation mapを別に持つ。
BlockStorage.cache、dirty_blocksにもbytesを保持する。write時にglobal、cacheへのcloneとdirty所有がある。
new_syncはglobal mapをcloneしてpreloadし、reloadも全global blocksをcloneする。
read missはcache insert後のevictionを省略する。evict_if_neededはclean LRUだけを追い出し、
dirtyしかなければ終了する。capacity128は512 KiB相当の**block payload目安**に過ぎず、
総heap/RSS上限でも厳格cache上限でもない。async constructor等では別capacityも使う。
checksum/version検査、LRUの線形探索、hash maps、logging、auto-sync queueもコストになる。
IndexedDB/OPFS/Hybridのpersist/restoreは別backendで、Hybrid persistはblocks.cloneして両方へ送る。
ブラウザ永続化方式をGo内memory backendへそのまま追加する利益は示されていない。

### truncate / delete / allocation

live main x_truncateは末尾blocksを保持し、境界blockの後半もclearしない。
regrow時は旧data再露出の経路が残る。旧x_truncate_stubはglobal末尾blocksをretainで消すが、
これをlive callbackの動作には数えない（size0でblock0を残す処理もある）。
block APIのdeallocateはcache/dirty/allocation/global/metadata等を削除し、
next_block_idを戻して再利用を試みる。これはfile truncateとは別で、
複数free holeの一般allocatorや重複ID回避を認定するものではない。
allocate_blockはID/set/metadataを確保し、直ちにfile全体のpayloadをmakeしない。
**WASIX fd_allocate相当のreserve contractは存在しない。**

x_deleteは主にWAL cleanup、main DBのPOSIX unlink＋既存FD寿命を完成させた証拠ではない。
x_closeはshared cache reloadを行い、全DB bytesの解放ではない。
cleanup_all_stateはregistry、pool、global/metadata/commit/allocationを落とす別手順。
引用箇所だけから全auxiliary/SHM/async taskのexactly-once releaseを認定しない。

### shared ownership / concurrency / export

WASM registryはRc<BlockStorage>とRefCell/thread_local、nativeはMutex/Arc。
同DB名の複数connectionは**同じ可変storage**を共有する。x_lockはhandle内のlock level/transaction flagを更新してOKを返す。
MariaDBのfile操作を排他する汎用lock managerではない。commit marker/versionはvisibility管理で、
過去versionのimmutable bytes/rootを複数子に保持するblock-CoW Snapshotではない。
write_bufferはmulti-connection visibilityのため無効化されている。
RefCell reentrancy検出は別OS threadからの並行RMWをserializableにするlockではない。
block単位read→modify→writeの全体をMariaDB用lockなしで移せばlost updateのリスクがある。

exportは全blockをreadして連続Vecへ連結、importは全入力を4 KiBへ分割してglobalへclone。
これは保存/読み込み能力であり、immutable blockを参照して複製する機能ではない。
同DB名へのimportは既存storageをclearする。別名へのexport/import複製は全dataコピー相当で、
独立Forkの共有寿命管理を提供しない。MVCCという名前やRc/ArcだけからCoWを推定しない。

## 5. 六つのallocationケース（ソース由来、今回実行なし）

条件: 100 MiB=104,857,600 bytes。SQLite main DBとしてblock sizeが既知で、
100 MiBの論理EOFを持つhandleを前提とする。4 KiB更新はaligned、境界を跨げば複数block。
「末尾4 KiB」はEOF直前で、EOFをさらに伸ばすwriteではない。

| 操作 | absurd通常IDB | Absurder WASM main DB | mariamem現在 |
| --- | --- | --- | --- |
| 空→100 MiB extend | setattr size＋fsync meta。data全量確保なし。ただし空fileのSQLite header/page-size初期化は別 | x_truncateはfile_sizeのみ、payloadなし。再openの正確なEOFはUnknown | Fd_allocate→Truncate→make100 MiB。旧bytesはないためcopyなし |
| 末尾4 KiBだけwrite | 触れたpageのみpending/persist、partialならRMW。空fileでheader未設定の直接末尾writeは不可 | 一つの4 KiB blockをzero/read→write。cache/global/dirtyコピーあり | cap内payload copy。予約全量は既に確保。mapped fileならdirty OS pages |
| 中央4 KiB update | 触れたpageのRMW/replace、file全体copyなし | 一つのblock RMW、Vec/checksum等。whole-file resizeなし | cap内copy、MAP_PRIVATEならページCoW |
| 100→1 MiB shrink | metaのみ、末尾blocks保持、境界残りもzeroにしない | main file_sizeのみ、末尾blocks保持、readにEOF clipなし | slice縮小、cap保持。元mappingもCloseまで追跡 |
| 再100 MiB extend | metaのみ、保存済み旧bytes再露出可能。一般FS zero保証なし | file_sizeのみ、旧block再露出可能。新holeはzero経路 | cap内reslice＋newly exposed range clear。再確保不要でもzero touchの費用あり |
| Snapshot相当からclone | 不変root/独立Fork APIなし、共有CoW copy粒度/lifetimeは該当なし。手動複製費用Unknown | export/importは全data materialize＋block copies。immutable shared cloneなし | verified OwnedPrepared FDを各子MAP_PRIVATE、独立metadata/runtime。容量超過時は旧論理内容全copy |

この表はSQLite→WASIX変換を提案していない。現在Fd_allocateは`Truncate(offset+length)`へ
委譲しており、reserve、logical EOF、実体容量の責任分離とoverflowの受入条件は別途必要。

## 6. mariamemの比較境界

現行コード: [resizeMemData](../../internal/generatedgo/code/base/memfs_growth.go) L5–36、
[base.go](../../internal/generatedgo/code/base/base.go) L11970–12069/13491、
[owned_prepared.go](../../internal/generatedgo/code/base/owned_prepared.go) L14–64、
[prepared_files.go](../../internal/generatedgo/code/base/prepared_files.go) L71–81、
[OwnedPrepared](../../internal/snapshot/owned.go) Acquire/Close、
[Snapshot](../../snapshot.go) Fork/Close。

Freshは連続Go heap buffer、EOF/capを分け、1 MiB未満2倍、それ以上1.25倍、必要sizeが優先。
空file100 MiB要求は倍率を変えても100 MiBの初回確保。cap超過は旧lenを一回copy。
Forkは同じ検証済みread-only backing FDをPROT_READ|PROT_WRITE、MAP_PRIVATEでmap。
clean pageをOSが共有でき、書いたpageは子private。base/siblingにwriteしない。
map cap超過でheapへ旧file内容copyし、旧mappingもworker join後のCloseまで追跡する。
OS CoWはpublic memory保証ではない。runtime linear memory、FD/node/dirty pagesは別に必要。

先行profileのFresh5.77–5.80 GiB中4.62 GiBは累積allocationの帰属。
未使用reserve量、retained bytes、実際のcopy bytes、Peak RSS、wall割合とは違う。
ブロック化でその全量が削減できるとは主張しない。

下表のB/C/Dは**未実装候補**、E/Fも移植前の参考。効果は仮説。

| Dimension | A 現連続buffer | B growth倍率変更 | C sparse/chunks | D mmap prefix＋tail | E absurd型 | F Absurder型 |
| --- | --- | --- | --- | --- | --- | --- |
| Fresh初回allocation | 大reserveを全確保 | 空file大要求は不変 | EOF＋触れたchunkのみ可能 | Freshには直接効果なし | IDB mainはmetadata伸長可能 | WASM mainはmetadata伸長可能 |
| 再確保/copy | cap超過で旧len全copy | 回数減候補、余剰cap増 | old chunksを維持、追加chunk | prefix全copyを避けtail追加 | pageごと置換/RMW。memory backendは全copy | blockごとVec copy、global/cache/dirty複製 |
| Retained/Peak RSS | EOF/cap/dirty mapsに依存 | spare増でRSS増も可能 | 未使用holes多ければ減候補、metadata増 | mapとtail/dirty保持、減少未測定 | IDB resident量＋pending＋SQLite cache。fallback全block保持 | global resident＋cache＋dirty、上限保証なし |
| random Read/Write | 単純copy | 基本不変 | lookup/境界分割/RMW | prefix/tail境界処理 | channel/IDB、partial page RMW | hash/Vec clone/checksum/RMW |
| Snapshot作成 | file export/copy/inventory/hash | 原則不変 | logical filesへexportなら同形式、materialize必要 | 二領域をlogical fileへexport | mariamem型Snapshotなし | export全blocks→連続bytes。immutable cloneなし |
| Fork起動 | fresh FS＋private maps＋runtime | 基本不変 | baseline owner/overlayを別設計 | 現map維持可能、tail owner追加 | clone起動の評価不能 | importは全コピー、独立shared Forkなし |
| Fork後更新 | page CoW、grow時全copy | 最初のdetachは残る | dirty chunkのみ候補 | 容量内page CoW＋tail | mutable IDB blocks、子overlayなし | 同DBのmutable global。子overlayなし |
| CPU overhead | copy/zero/lock/GC | realloc減とzero/spare tradeoff | index/境界/GC増、copy減候補 | 分岐/境界/export増、detach減候補 | worker/Atomics/transactions/コピー | clone/checksum/LRU/logging/sync |
| fragmentation | 大連続heap＋spare cap | spare増、heap影響要測定 | 小object/lookup多、chunk末尾余り | map＋tailの二領域 | page records/JS objects、永続store管理 | 多Vec/hash entries＋duplicates |
| complexity/risk | 現契約を維持 | 小、overflow/zero維持 | 大、holes/truncate/FD/owner/race | 中～大、境界/shrink/unmap | browser/SQLite前提、一般FS不足 | multi-backend/visibility、WASIX契約不足 |
| Go/WASIX移植 | 現実装 | 局所変更可能 | 原理は可能、全I/O経路監査 | 内部抽象化必要 | 設計着想のみ。JS IDB移植不要 | 設計着想のみ。Rust/browser構成移植不要 |

pglite-go/pgmemは連続buffer＋file単位copyで、巨大初回予約とmapped growth全copyを
直接解決しなかった。本調査は**logical EOFとpayloadの分離**という新しい参考を加える。
しかしSnapshot CoW・MariaDB互換性・資源上限の完成した代替を見つけたわけではない。

## 7. Critical questions / 解ける・解けない問題

**Q1 — 巨大初回Fd_allocateを遅延できるか:** 原理上yes。EOF/reservationをmetadataで保持し、
holeをzeroとして読み、write時だけchunkを確保するGo backendなら可能。
両WASM main経路はmetadata-only伸長の具体例。ただしfd_allocateは未実装で、
space-reservation/ENOSPC、EOF、zero/overflowというWASIX契約を別に設計しなければならない。

**Q2 — 予約領域の大半を書いた場合:** 最終payloadはほぼ残る。
whole-file再確保/コピーを避ける利益はあり得るが、object/index/RMW/cache費用は増える。
初回確保を分散できても最終RSSやwall短縮を保証しない。sequential全writeなら連続bufferが有利な場合もある。

**Q3 — MAP_PRIVATEとの比較:** 既存mappingはOSがpage CoWとclean sharingを管理。
block管理は疎なFresh reservation、mapping以上のgrowth、chunk単位明示releaseの候補。
一方、immutable baseline/child overlay/ref lifetimeをmariamem側で管理し、余分なlookup/copyを負う。
block sizeとOS page/InnoDB pageは別。blockを導入しただけでSnapshot CoWが得られるのではない。

**Q4 — 永続形式/lifetime:** 内部chunkから現行logical datafilesをexportするなら、
Snapshot formatやpublic APIを変える必然性はない。ただしexport/hash/acquisition、
FD unlink/rename、parent Close後のchild、partial failureの内部owner契約は更新/検証が必要。
共有block manifestを直接persistする案なら別format/validation/refcount設計が必要。
それは局所memfs改善ではない。今回どちらも採用しない。

**Q5 — 限定計測より先に実装する理由:** なし。どのfile/phaseが何度reserveし、
何割をtouchし、どれだけmapped detachするかが不足。外部SQLiteの設計だけでは優先順位を変えられない。

**Q6 — 連続bufferが合理的な条件:** 初回要求が最終使用量に近い、再確保が少ない、
大部分をread/writeする、全file exportが必要、RSSが予算内、lookup/RMW overheadが支配し得る場合。
単純なlocking・slice I/O・zero保証・現Snapshot契約を維持する保守上の利益もある。
逆に大reserveのほとんどが未使用/多回再確保と実測されればchunk案を検討する材料になる。

block storageだけでは、MariaDB/InnoDBのscan、generated-runtime synchronization、
server startup、linear-memory管理、Snapshot整合停止/hash validationを解決しない。
allocation削減とwall短縮を別に評価する。

## 8. Correctness / concurrency risks と次の受入条件

- **zero/EOF:** 未保存hole、partial blockの未変更bytes、shrink境界のsuffix、再grow、
  O_TRUNC後の旧blockを正しく隠す。引用二実装のtruncate方式は一般FSとして移植しない。
- **並行RMW:** 同block異range更新を失わない。grow/read、truncate/write、append、iovec、
  partial failureを含める。複数mapへの短い個別lockだけではfile操作の線形化を証明できない。
- **offset:** negative、offset＋length overflow、block ID変換、access width、最大file sizeを定義。
  JS int32 channelやRust offset castをGo/WASIXへ盲目的に移さない。
- **namespace/FD:** unlink/rename後も開いたFDは適切なnode/storageを保持。
  path/database-name削除とFD Closeを同じ操作にしない。
- **Snapshot isolation:** baseline不変、child overlay独立、元/兄弟へのwrite禁止。
  親Close後の子、再Snapshot、export中の一貫性、共有block寿命を別々に検証。
- **cleanup:** joined workers後のrelease、部分初期化/失敗/反復Close、dirty/cache/async taskの残留。
  GC参照寿命とmunmapを混同しない。
- **durability:** SQLite xSync/transaction/WAL、IDB visibility/checksumはWASIX filesystem仕様と別。
  atomic-write広告やcommit markerをMariaDB durability/多thread互換性の根拠にしない。

将来実装時はdeterministic FS tests→handwritten race/isolation→小SQL/session/Fork→platform受入。
生成codeの一箇所をpatchして終わらせず、canonical template/generation/provenance契約を守る。
今回は変更していないので、runtime/SQL/release suiteを再実行しない。

## 9. Licensing and provenance

absurd-sqlの[LICENSE][alicense]はMIT（James Long、2021）。直接移植・相当部分再利用なら
copyright/license noticeを保持し、導入範囲と派生元SHAを記録する必要がある。

AbsurderSQLの[Cargo.toml][bcargo]は `AGPL-3.0`、[LICENSE.md][blicense]はAGPLv3全文。
`-only`/`-or-later`の厳密な許諾をmanifestの短い文字列だけで断定しない。
直接portはmariamemの配布・対応ソース・ネットワーク利用時の義務を含む別ライセンス判断が必要。
現在のNOTICEへ名前を足すだけで十分とは扱わない。

一般的な「logical EOFとblock payloadを分離する」という着想、
独自仕様からのアルゴリズム再実装、外部sourceの翻訳/直接移植は区別する。
再実装という呼称だけで派生元の義務がなくなるとは主張しない。
実装を選ぶ場合は独立の設計/由来記録とlicense reviewを行う。
**今回は両外部sourceをmariamemへ取り込んでいない。報告とhash evidenceだけをcommitする。**

## 10. Verification / unresolved measurement

今回実施: 固定SHA/source blob/hash照合、live callback registration追跡、
EOF/zero/copy/cache/ownershipのsource inspection、既存testsの範囲確認、
文書link/source anchorとdiff、canonical docs-scope check。
upstream/browser runtime tests、MariaDB新benchmark、RSS/CPU比較は未実施。
「source由来の経路」と「受入済みruntime結果」を明確に区別する。

不足する測定は先行計画のまま: file/phase/callerごとに oldLen/cap、requested EOF、
初回/再確保回数、allocated/copy/clear bytes、mapped detach、最終cap、
written/read rangesを小数ケースで採る。profile累積4.62 GiBをfile別の利用実態へ分解する。
必要ならchunk候補を選ぶ前に、既存traceからreserveの未使用割合を集計する。
新しいbenchmark基盤を作る必要はない。

完了後、取得source、worktree、tempをGit-aware cleanup。compact report/hash/refsのみ保持。
本調査自身はruntime cacheを作らない。他taskのactive workspaceは削除しない。

## 11. Astra Decision Handoff

### Established facts

- 現Fresh allocationの大きな帰属先はFd_allocate→Truncate→resize（先行実測）。
  ファイル別初回/再確保と実使用量はまだ不足している。
- 二つのWASM main DB経路にmetadata-only伸長とblock単位保存がある（固定source）。
  memory/fallback/auxiliaryを含む全経路のsparsity保証ではない。
- 二実装のblock storageは独立Snapshot/Forkのimmutable block-CoWではない。
- mariamemは既にMAP_PRIVATE page CoW。容量超過のwhole-file heap copyは残る。
- Absurderのglobal/cache/dirty、full restore/reload/exportは複製/保持の経路を持つ。
  上流のcache limitやnative testsからMariaDBのmemory ceilingを保証できない。

### Hypotheses

- 未使用reserveが多ければsparse/chunkはFreshのallocation/zero-touch/RSSを減らし得る。
- 全file reallocが多ければchunks、mapped detachが多ければprefix＋tailがcopyを減らし得る。
- 大半を使うfileでは最終payloadは減らず、lookup/RMW/metadataによってCPU/wallが悪化し得る。
  どれもmariamem比較実測なし。

### Rejected approaches — 現時点で採用根拠なし

- absurd/Absurder全VFSの移植、browser persistence machineryの導入。
- block保存＝Snapshot CoW、cache capacity＝総メモリ上限という一般化。
- SQLiteのtruncate/locking/aux-file制約をWASIXの受入条件とすること。
- MAP_PRIVATEを未検証のapplication block-CoWに置き換えること。
- 外部設計だけを理由に性能改善やv0.5スコープ拡大を承認すること。

### Open questions

どのfileが初回reserveを繰り返すか、未使用領域はどれだけか、shrink/regrow頻度、
mapped growth-detachの量、hot I/Oのrange/alignment、lock待ち、export時materializationの影響。
block size/representation/cacheを選ぶにはこれらと予算が必要。改善率はUnknown。

### Candidate experiments（承認後、最小の順）

1. 現行harnessでfile別initial/reallocation/touch/detachの限定計測。新backendなし。
2. 反復growthが主要ならgrowth倍率だけ比較。未使用reserveが主要ならsmall FS-only
   sparse/chunk prototype、mapped detachが主要ならprefix＋tail prototypeを別々に候補化。
3. 候補を選んだ後にzero/shrink/regrow/concurrent RMW/FD lifetime testsを先行。
   正しければ既存小Fresh/Fork workloadでallocationとwall/RSSを別評価。

### Decision requested

Astraには、**限定計測を次工程として採用するか**、その結果に応じて
B growth / C sparse-chunks / D prefix-tailを採用候補・保留・却下のどれにするかを委ねる。
E/Fは着想の参考として残すか、直接導入候補から外すかを判断してほしい。
この資料はstorage実装の採用や性能保証を承認しない。
v0.4.x VFS関連文献調査はここで一区切りとし、追加文献より不足測定を判断材料にする。

[pgreview]: https://github.com/masahitojp/mariamem/blob/55c5639aa43e6cad72a53d313c58a5e2ba9bdb20/docs/reviews/pgmem-vfs-design-review.md
[afile]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/src/sqlite-file.js
[aops]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/src/indexeddb/file-ops.js
[aworker]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/src/indexeddb/worker.js
[afallback]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/src/indexeddb/file-ops-fallback.js
[amemory]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/src/memory/backend.js
[alicense]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/LICENSE
[bvfs]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/vfs/indexeddb_vfs.rs
[bstore]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/block_storage.rs
[bio]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/io_operations.rs
[balloc]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/allocation.rs
[bglobal]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/vfs_sync.rs
[bexport]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/export.rs
[bimport]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/import.rs
[bhybrid]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/storage/hybrid_store.rs
[bcleanup]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/cleanup.rs
[bcargo]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/Cargo.toml
[blicense]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/LICENSE.md
