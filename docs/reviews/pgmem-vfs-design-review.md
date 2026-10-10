# pgmem VFS design review — Discovery only

2026-10-10。**現行MAP_PRIVATEをfile-level CoWへ置き換える根拠はない。**
pgmemのCloneはheapファイルの全量コピーを遅延するが、最初の小さな更新でも
ファイルの論理内容全体をコピーする。大きな初回領域予約も連続bufferを確保する。
既存の「ファイル別の初回確保・再確保の限定計測」を先に進める推薦を維持する。
今回は実装・新benchmark・Release Qualification・main・v046候補を変更していない。

## 1. 調査対象・証拠の境界

| 対象 | 固定identity |
| --- | --- |
| pgmem | `3433a40bd4167daea2d8e364666bd5fcf18ef654` |
| mariamem開始main | `f306fa697edb8410973d1a61ec3ebbcb16ac0e7d` |
| 先行Discovery | `b5ae57121a285fe44a2f60015609591f60703807`（mainにも報告がある） |
| 既存allocation profile実行ソース | `80a37385f9d1eda6604358dd5ba2235feb0b26ca` |
| 先行pglite-go | `c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f` |

[先行memfs調査](memfs-optimization-discovery.md)はFresh×20のsampled alloc_space
5.77/5.80 GiBのうち4.62 GiBをresizeMemDataへ帰属し、呼出し側を
Fd_allocate→Truncateと特定した。これは累積allocationであり、同時heap、Peak RSS、
コピー量や削減可能量ではない。今回追加測定はなく、pgmemとの性能比較値もない。
profileソースと開始mainのbase.go/memfs_growth.go/owned_prepared.goはGit diffで同一。

固定SHAのGitHub Contents APIからVFS・host・engine・public lifecycle・LICENSE等15ファイルを
取得し、全サイズ/Git blob SHA1/SHA256を照合した。[inputs.json](pgmem-vfs-evidence/inputs.json)
にソース位置/hash/再現対象を保存。READMEの説明ではなく以下の実装を根拠にする。
pgmemはMITだが、今回はコード導入なし。全外部ソースやcacheは保存しない。

| pgmemの参照ソース | 主なコード位置・責任 |
| --- | --- |
| [vfs Node/FS][nodes] | L150–231: data/shared、node/FD、tree単位mutex |
| [writeAt/own/growCap][growth] | L681–724: detach、全file copy、連続buffer成長 |
| [Truncate/Ftruncate][truncate] | L1072–1118: shrinkはslice短縮、growはwriteAtへ |
| [FS.Clone/cloneNode][clone] | L1607–1652: node/tree複製、data共有 |
| [Open/Close][open] | L411–499: O_TRUNC、FDとsocket callback |
| [Unlink/Rename][rename] | L933–1023: namespace変更、node identity維持 |
| [WriteFile/PutFile/ReadFile][put] | L1313–1390: copy / ownership transfer / copy-out |
| [FS.Fork/ForkFDs/CloseAll][views] | L1458–1507: 同一treeのprocess views、FD整理 |
| [host fallocate/mmap][allocate] | L1001–1054: 領域確保・guest mmap shim |
| [host readv/writev][iov] | L1230–1312: positioned I/Oをseek/I/O/restoreで実装 |
| [public Snapshot/Fork/Close][snapshot] | L42–150: shutdown→Clone→restart、新server、closed flag |
| [engine untar/Tar][archive] | L140–218: heapへ読み込み、ownership transfer、直列化 |
| [cluster exit][exit] | L178–201: process FD CloseAll、segment detach |

## 2. pgmem実装の読み取り

### A. CloneとCoWの粒度

FS.Cloneはsource FS mutexを保持してNewの独立FSを作り、cloneNodeで木全体を再帰コピーする。
Node値（ino/mode/name/mtime等）・parent・children mapを独立させるが、regular fileのdataは
slice headerだけをコピーし、同じGo backing arrayを共有する。source/clone両方のshared=true。
新FSはrootをcwdにし、stdin/out/errだけ新treeへ再接続する。元のopen FD table、位置や
dirent cursorは継承しない。pipe bufferは別コピー。socket等の非regular fieldsは値コピーに
含まれるため、任意のlive treeの独立実行状態cloneを保証する仕組みとは解釈しない。

- 範囲内write: Node.ownがbytes.Clone(data)し、**現論理len全体**を一度コピーする。
- shared fileを伸ばすwrite: capに余裕があってもmake+copyで独立化。growCapのcurは
  旧capでなく旧len。detachと拡張を融合し、own→再拡張の二重コピーを避ける。
- owned fileのwrite: cap内ならreslice、超過ならmake+copy。payloadも書き込む。
- shrink: slice headerだけ短縮し、sharedフラグは保持。後の範囲内writeなら短縮後のprefixだけコピー。
- shared O_TRUNC: nilへ切り替え、旧データをコピーしない。owned O_TRUNCはcapを残す。

**アプリケーションによるファイル単位CoWであり、page/chunk overlay、OS MAP_PRIVATEではない。**
read-only fileをいくつcloneしてもdataの追加コピーはないが、node/mapは各cloneに必要。
sharedは参照カウンタではない。最後の一人になっても他nodeのフラグを戻さず、次writeで
不要なcopyが起き得る。data寿命はGo参照とGCに依存し、Clone単位の明示的data releaseはない。

### B. growth、Truncate、allocation

容量はmax(2×cur, need, 8192)。Freshで空fileを100 MiBへ伸ばすなら100 MiBの連続Go backing。
2倍成長は複数回の拡張に作用し、巨大な初回要求を疎なzero rangeで表す方式ではない。
FtruncateのgrowはwriteAt(size−1, {0})。新規makeのzeroを使うが、owned cap内の再拡張は
clearせずresliceし、最後の1byteだけ0にする。

**静的correctness反例（今回は新fixtureを実行していない）:**
WriteFile("ABCD")→Truncate(1)→Truncate(4)ではowned cap内のためB/Cが再露出する経路がある。
seekで穴を開けてwriteする場合も同じ問題。mariamemは新しく露出する範囲をclearしており、
この「clear省略」を移植してはいけない。pgmem既存CoW testのgrow例は新規allocationになり、
このowned shrink/regrow条件をカバーしない。

host __syscall_fallocateはFstatしてoff+lenが現Sizeを超える場合だけFtruncateする。
予約専用capacity、sparse extent、deferred commitmentはない。mode引数を使わず、
加算overflow/negative offsetをこのshim内で包括検証していない。growCapにも
cur×2のoverflow/host int上限の専用checkがない。これらを安全なreserve helperとみなさない。FstatとFtruncateは別lockなので
一つのatomic reserve操作でもない。WASI fd_allocate登録は取得したhost import表にはない。
MariaDB/WASIXと同じsyscall契約・負荷だと仮定せず、相当するEmscripten shimとして比較する。

mariamem Fd_allocateはoffset+lengthを無条件にTruncateする。pgmemの「既存長より小さい予約では
shrinkしない」という区別は仕様監査の参考になる。ただし移植にはmode/EOF/overflow/競合を
含むreserve契約の確認が必要で、初回allocation削減策とは別のcorrectness項目。

host _mmap_jsはguest Memalignした領域へfileをcopy-inするshim。_munmap_jsはno-op。
これはhost OSのfile-backed private mappingではない。pgmemの別のshared-memory segment機構を
VFS file CoWと混同しない。

### C. ownership、削除、Close

FileはNode pointerとpos/flagsを持ち、unlinkはchildren mapから除くだけ、renameは同じNodeの
name/parentを変える。open FDは元Nodeを保持するのでnamespaceから外れたfileも使い続けられる。
Clone先のNodeは独立している。WriteFile/PutFileは既存regular Nodeのdataを差し替える。
PutFileはcallerが今後そのsliceを使わないという所有権契約が必要で、aliasの禁止は型で強制しない。
mariamem WriteFileは新Nodeをpathへ置くため、同じ名前でもopen FDへの影響がpgmemと異なる。
所有権transferだけでなく、replace時のnode契約も無条件に借りない。
LookupはNode pointer、Walk callbackはdata sliceを渡す。mutexの外に可変aliasを持ち出せば
内部CoW・同期規律を破れるため、このhost-facing APIもそのまま公開/移植しない。

FD Close/CloseAllはFD参照を落とし、socketの最終close callbackをunlock後に実行する。
node.opensはpipe/socket等のFD寿命用であり、shared dataのrefcountではない。
linked NodeのdataはCloseAllでnilにされない。public Snapshot.Closeもclosed.Store(true)だけで
sn.fsを保持する。Server.CloseもFSそのものをnilにしない。closed handleを保持したまま即座に
heap backingが解放される設計ではない。guest/shared-memory segment cleanupは別責任。

public Snapshotはcluster停止後にFS.Cloneし、元serverを再起動する。Forkはsn.fs.Cloneを
新serverのbootへ渡す。**running PostgreSQL heap/threads等を保存して復帰する方式ではない。**
mariamemのSnapshotは成功時に元DBを消費するため、pgmemのserver再起動・session継続という
製品契約を採用しない。pgmemのin-memory cloneとpersisted archive直列化も別の操作。

### D. concurrency

FS.muはtreeとFD table全体を守る。FS.Fork/ForkFDsは**同じ可変treeと同じmutex**を持つ
cluster内process viewで、FS.Cloneとは違う。Clone先treeは別mutexで並行利用できる。
source.sharedの変更もClone時のsource lock内。別treeのbytesはshared中に書き込まず、
各treeのown→writeで独立化する。raw aliasを使わないregular-file methodの規律として成立する。
copy/allocation、Cloneの再帰metadata複製、Walk callback/Tarの書き出し中もFS lockを保持する。
ファイル単位mutexやコピー中のunlockはない。既にshared=trueならcloneNodeはsourceへ再書込しないが、
FS.Cloneは元FSのmutexを取るので同じbaselineのcloneは直列化される。

host readv/writevのpositionedアクセスはSeek(save)→Seek(offset)→I/O→Seek(restore)で、
この複合全体を一つのFS lockで囲まない。同じFDへ並行アクセスするとinterleaveし得る。
これは静的な移植リスクであり、pgmem SQLでraceを実証した結果ではない。
mariamemのReadAt/WriteAtはnode lock内でoffsetを変えない。MariaDB/WASIXの複数workerに
pgmem shimを丸ごと移すことはできない。FS-level mutexという考え方自体は現memfsにもある。

## 3. mariamemとの比較

| Dimension | pgmem | mariamem | Implications |
| --- | --- | --- | --- |
| File storage | 主に連続Go []byte。Clone間でarray共有 | FreshはGo []byte、Fork既存fileはowned FDのMAP_PRIVATE | Go heapとOS mapped pagesのaccountingは別 |
| Buffer growth | 2倍/min8 KiB、共有時は旧len基準でdetach+grow | 1 MiB未満2倍、以上1.25倍、max(required,growth) | 再確保減とspare cap/RSSのtradeoff。初回大要求には倍率が効かない |
| Truncate | shrink headerのみ、growはwriteAt。owned regrowのzero欠落経路 | 共通resize、cap内再拡張clear | pgmem処理を無条件に採用不可 |
| File CoW | shared fileの最初のwriteで全論理内容copy | 容量内writeはOS page-level CoW | 少量更新×大fileでは全file copyの方が重い可能性 |
| Snapshot creation | 停止→tree Clone→元server再起動 | 停止/消費→guest snapshot copy→export→manifest/hash→owned backing | Cloneはcontent直列化を避けるが永続/検証/製品契約が違う |
| Fork creation | 独立tree Clone→新server boot、fresh FD table | AcquireでFD pin→新tree/MAP_PRIVATE→fresh MariaDB runtime | どちらもruntime-state cloneなし。node/map/startup費用は残る |
| Fork file growth | shared時は全lenをheap copy。owned時もcap超過で全len copy | mapped cap超過で全lenをheap copy、元mappingはCloseまで追跡 | pgmemは全file growth-copyを解消しない |
| Memory ownership | per-node shared bool、Go参照/GC、PutFile transfer | Snapshot Ownedは検証済みread-only unlinked FD、子PreparedFilesはprivate maps | refcountの対象、trust、alias、lifetimeを分ける必要 |
| Locking | 同tree/process viewsはmutex共有、Clone別mutex。copy中保持 | DB別MemFS mutex。allocation/copy/clear中保持、wasi FD-table lockも別にある | coarse lockの待ちは両方あり、lock省略の根拠なし |
| Resource cleanup | CloseAllはFD、bufferは参照/GC。Snapshot.Closeはclosed flag | worker join→descriptor close→maps munmap、Snapshot.Closeでowned FD解放 | mapping解放とGo heap reclaimを同じ指標にしない |

mariamemの具体的な根拠:

- [base.go](../../internal/generatedgo/code/base/base.go) L11698/11709/11915/11975/12012/12050/
  13491: MemFS/node/WriteFile/open FD/writeAt/Truncate/Fd_allocate。
- [memfs_growth.go](../../internal/generatedgo/code/base/memfs_growth.go) L5–36:
  logical EOF/cap、clear、成長時に一度make+copy。既にdetach+growthを一回で行う。
- [owned_prepared.go](../../internal/generatedgo/code/base/owned_prepared.go) L14–64:
  同じSnapshot-owned FDをPROT_READ|PROT_WRITE / MAP_PRIVATEでchildにmap。MAP_SHAREDではない。
- [prepared_files.go](../../internal/generatedgo/code/base/prepared_files.go) L11–14/71–81:
  旧mappingも追跡、全worker終了後munmap。memFile.Close単独ではunmapしない。
- [owned.go](../../internal/snapshot/owned.go) L96/154/277/304:
  Importコピー＋完全検証、AdoptCreated、read-only unlinked backing、Acquire pin、Close FD。
- [snapshot.go](../../snapshot.go) L33/87/103: source消費、Fork読lock、親Close後も子が利用可能。
- [runtime_instance.go](../../internal/generatedgo/runtime_instance.go) L19–72/78–94:
  fresh FS、prepared map、root/worker join、export、descriptor/map cleanup。
- [resident.inc](../../guest/resident.inc) L221–239と
  [main.go](../../internal/generatedgo/main.go) L451–503: guest終了後snapshot-outへコピー、
  exportTransferがfile-sized bufferでOS fileへmaterialize。ownershipやhashを省く理由にはならない。

MAP_PRIVATEのclean page共有はOSの実装挙動で、子の増分メモリゼロの保証ではない。
metadata、dirty pages、fresh linear memory/InnoDB状態、新規file heapは各DBに必要。
map容量超過後は旧mapとnew heapの寿命が重なり得るが、常に旧file全量がRSSに残るとは言わない。

## 4. 最適化候補（効果はすべて仮説、今回比較実測なし）

候補はpgmemの採用推奨ではない。先行DiscoveryのC1–C6との対応を示す。

| 候補 / 分類 | pgmem参照・現行との差 / 解ける問題 | Fresh / Snapshot / Fork | allocation / Peak RSS | CPU・wall / correctness / 難易度 |
| --- | --- | --- | --- | --- |
| L1 growth倍率比較 — Local / 先行C1 | growCap。mariamemの大file1.25倍を1.5/2と比較 | Fresh反復grow/exportに限る。Fork最初のdetachは残る | 累積alloc/copy減候補、spare capとPeak RSS増候補 | 再確保が多ければCPU/GC減、wallは未確定。EOF/overflow/zero維持。小 |
| L2 上書き範囲の重複zero限定 — Local / C2 | writeAtのclear省略という観点だけ参照。pgmemのregrow処理は借りない | Writeのpayload範囲だけ。Truncate初回allocには効かない。Forkの不要page touch減候補 | backing allocationは原則不変。dirty page数/RSSに限定的影響候補 | gapは必ずzero、shrink再growは古いbyteを隠す。CPU減は未測定。小〜中 |
| L3 所有bufferのtransfer — Local | PutFile/untarがexact-size bufferを譲渡。mariamem WriteFileは入力copy | もしproductionで二重copyがある場合のみ。現WriteFileの実データ導入は主に診断loadTransferで、通常Forkは既にmap | 対象の二重alloc/copyだけ減る。Fresh主要Fd_allocateには効かない。RSS不明 | caller alias禁止/失敗cleanupが必要。API変更なし内部実装は可能。小〜中、現時点低優先 |
| S1 mapped prefix＋private growth tail — Storage / C5 | pgmemにも同実装はない。data所有境界を分ける考え方の発展 | Fresh直接効果なし。Fork超過時の全file detachを避ける候補。Snapshotは両領域をexport | tailだけheap、旧全file heap-copy削減候補。map/dirty pagesは残るためRSS減は要実測 | 境界を跨ぐI/O、shrink/regrow、alias、munmap/exportが複雑。中〜大 |
| S2 chunk/page/sparse backend — Storage / C4 | pgmemは連続sliceであり参考実装ではない。両方式の弱点への別案 | Fresh初回大reserveを疎なzeroで表す、Fork増分だけ確保する候補。Snapshot/exportでmaterialize | 未使用予約領域が多ければalloc/RSS減候補。全領域を触るなら利益小、metadata追加 | read/write追加分岐・pointer前提・overflow/zero/truncate/snapshot/race。CPUも増え得る。大 |
| S3 pgmem型file-level CoW — Storage | Clone/own。mariamem MAP_PRIVATEを共有heap＋全file detachへ置換 | read-only filesは共有可。ただし現在もOS共有あり。Fresh初回reserveは変わらない。大file少量writeで不利候補 | OS dirty pagesよりfile-size heap allocが増え得る。mapping成長copyも本質的に残る | FD/mmap overheadを減らす可能性とcopy/GC tax。shrink・alias・shared flag全writepath監査。中〜大、置換非推奨 |
| A1 FS.CloneをSnapshot内部へ — Architecture / C6 | 冷えたtree/heap bytesを保持しmetadata clone。現export/hash/FD acquisitionとは違う | in-memory Snapshotのmaterializationを省ける候補。Forkはfresh runtimeのまま。persist/importは別ownerが必要 | Snapshot一時copy減候補だがbaseline heap常駐とfile detach増、closed handle pinningリスク | 整合停止、consuming API、取得検証、Python host handoff、再生成契約。大。現APIを変えずにも内部設計は広い |
| A2 node/namespaceとstorage ownerの分離 — Architecture | Node.data/ownの責務分離をさらに抽象化。pgmemにも独立backend interfaceはない | APIを変えずheap/map/tailを扱える土台。単独ではFresh/Forkの速度改善なし | wrapper/refcount/metadata増もあり得る。releaseを細粒度化する余地だけ | FDが指すnodeの安定性、owner alias、lock order、export/Close。大、必要なstorage案決定後 |

reserveのEOF/overflow/zeroの監査は別correctness責任。pgmemのfallocate shimは「予約」と
Truncateを区別する入口の参考になるが、capacityだけ予約する最適化やsparse storageの実装ではない。

## 5. Critical questionsへの回答

**Q1 — FS.Clone対MAP_PRIVATE:** Cloneはmetadataコピーだけでin-memory baselineを作り、
OS backing/FDなしでread-only dataを共有できる。一方、最初の小さなwriteも全file heap copy、
baseline/closed handleのheap保持、GC accountingを負う。mariamemは取得時materialize/validate/FDを
負う代わりに、容量内writeのpage-level CoWと明示munmapを得る。永続化・言語間handoff・
consuming Snapshotという契約差があるので、Cloneの単体コストから製品Snapshotの優劣を決めない。

**Q2 — mapping超過の全copyを避けられるか:** pgmemのshared growも旧len全体をcopyするため
直接解決しない。detachとgrowthを融合する点は参考になるが、mariamemは既に融合済み。
prefix+tail/chunk storageは別案であり、pgmem採用によって得られる既成の解決策ではない。

**Q3 — 初回Fd_allocate:** 同等shimはfallocate→Fstat→必要ならFtruncate→writeAt→make。
空fileの巨大要求は連続buffer確保。min8 KiB/2倍の成長は初回100 MiB確保を避けない。
既存長より小さい要求でshrinkしない点だけ異なる。Fresh4.62 GiBの主要因を解消する根拠なし。

**Q4 — InnoDB書込パターン:** 大きなdata/redo等のfileの一部pageだけ変える場合、file-level
copyは更新bytesよりはるかに多くなる可能性がある。例として100 MiB fileの16 KiB更新なら、
pgmem型は初回約100 MiBの論理内容copy、mariamemは触ったOS pagesのprivate化が基本となる。
16 KiBは説明モデルで、実際のfile別dirty範囲/OS page size/alignment/回収率を測った値ではない。
全file更新、再成長、guest startupで多数fileが変わる場合はpage sharingの利益も小さくなり得る。
InnoDB workloadだというだけで一律の勝敗やRSS予測はできない。

**Q5 — 現APIを維持して改善できるか:** L1/L2、実在するcopy経路だけのL3は内部改善として
可能。S1/S2も公開API/保存形式を維持する案はあるが全内部I/O/export/lifetimeを変える。
pgmemのSnapshotが元serverを再起動する振る舞いは移植しない。FS.Cloneの導入は局所改善ではない。

## 6. pglite-goとの接続・推薦

pglite-goはlower/upper overlayとwritable open時のcopy-up、単一thread想定のI/O lock省略。
pgmemは独立metadata tree＋write時file detach、同tree/process viewsで共有mutexを使う。
**pgmemは「参考VFSは全部single-threadだから不適合」という一般化への反例**だが、
そのpositioned shimやalias/zero semanticsをMariaDB用と見なす根拠にはならない。
両方ともfile単位copyで、mariamemのpage-level private mappingや巨大初回reserveを改善する
直接の代替ではない。pgliteのgrow-Truncateがexact-sizeである点と、pgmemがwriteAt経由で
capacityを再利用する点も区別する。mariamemにもcapacity再利用は既にある。

- **優先して実験する価値:** 既存harnessのファイル別allocate/truncate集計を維持。
  phase、caller、初回/再確保、oldLen/cap、要求EOF、copy/clear量、mapped detach、
  最終保持capと実際にwrite/readした範囲を分離する。反復growが支配するfileがあればL1、
  重複zeroの寄与があればL2へ。これは推薦であり今回instrumentationは追加していない。
- **有望だが保留:** mapped detachが大きければS1、初回reserveの大半が未使用ならS2。
  A2はその必要が確定してから。L3は通常production経路の二重copyを確認できた時だけ。
- **採用しない方がよい:** whole pgmem VFS、MAP_PRIVATEからfile-level CoWへの一律置換、
  clear省略、seekでpositioned I/Oを代用するshim、無条件2倍growth、Snapshot再起動の製品契約。
  A1は独立の広い設計Reviewが必要で、現在のallocation調査より先に実装しない。

**既存計測計画より先に新しい性能実験を行うだけの根拠は見つからなかった。**
必要なzero/EOF/reserve/aliasの回帰項目を整理することはできたが、pgmemのコードだけから
allocation/RSS/CPU/wall改善率は出せない。allocationが減ってもsuite wallが改善するとは限らない。

## 7. correctnessと次の受入条件

将来の変更では、以下を対象backendのdeterministic tests→handwritten race tests→
小さなSQL/多session/子間isolation→必要な両platform受入の順で確認する。

1. logical EOFとcapacity、穴と新規rangeのzero、shrink/O_TRUNC後の再grow、境界/overflow。
2. Clone/shared backingがあるなら全write経路のdetachとalias禁止、shared状態の並行変更。
3. offsetを変えないpread/pwrite、append、iovec/partial failure、同FD/異FDの競合。
4. node identity、open FDのunlink/rename/replacement、ownerとstorage寿命の分離。
5. Snapshot元backing不変、子間・世代間の独立、exact acquisition検証、parent Close後の子。
6. joined worker後のrelease、失敗・部分初期化・反復Close。GCとmunmapを混同しない。
7. snapshot exportは論理内容だけ。map/tail/chunk/spare cap/旧bytesを誤って出力しない。

生成baseを直接patchして終わらせず、先行Discoveryで示したcanonical memfs-growth template/
patch_memfs/setup_audit→generate_runtime→inputs/provenance→再生成照合の契約を維持する。
ライセンス追加が必要ならコード導入とともに監査する。今回はいずれも変更なし。

## 8. 今回の検証・再現・cleanup

pgmem既存TestCloneCopyOnWriteを取得した**変更なしのVFS二ファイル**で独立実行した。
Go1.26.8 darwin/arm64、GOTOOLCHAIN=local、GO111MODULE=off、専用GOCACHE。PASS。
source/cloneのin-place write、append/grow、O_TRUNC、shrink後prefix detach、shared spare-cap
の独立化等を確認する既存testであり、SQL、race、owned regrow zero、性能の認定ではない。
新fixture・新benchmarkは作らず、mariamem runtimeの再build/再qualificationはしていない。

再取得: `gh api repos/shibukawa/pgmem/contents/<path>?ref=<固定SHA>` のcontentをbase64 decodeし、
inputs.jsonのサイズ、Git blob SHA1、SHA256と照合。元repo最新mainを使い直さない。
15ファイル一覧とtestコマンドはinputs.json。先行profile数値は先行報告/同hashのsummaryを参照。
文書のローカルlink、pinned code anchor、JSON/hash、diff/statusをチェックした。

workspaceはmin-free8 GiB/budget1 GiB。取得source/test compiler cacheは完了後DELETE、
報告/input hashes/Git refsだけKEEP。main・v046候補・Release CIを変更/dispatchしない。
独立branchをpush後、Git-aware worktree removalとguard/残存大容量監査を実施する。

[nodes]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L150
[growth]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L681
[truncate]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L1072
[clone]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L1612
[open]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L411
[rename]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L933
[put]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L1313
[views]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L1458
[allocate]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/host/host.go#L1001
[iov]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/host/host.go#L1230
[snapshot]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/snapshot.go#L42
[archive]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/engine/engine.go#L140
[exit]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/host/cluster.go#L178
