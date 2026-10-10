# memfs optimization discovery — 調査のみ

日付: 2026-10-10。改善実装・新規性能計測・CI dispatch は行っていない。
`main`、v0.4.6 candidate、release workflow/tooling は変更していない。
調査ブランチ: `experiment/memfs-discovery`。
後に報告・証拠だけをmainへ集約した。改善実装の採用やv0.4.6 candidateの統合ではない。

## 結論と判断材料

**VFS を置き換える理由は見つからなかった。既存 memfs の局所改善を先に評価する。**
ただし、現時点で「拡張倍率を変更すれば主要 allocation が減る」とも判断できない。
最も強い追加発見は、既存 Fresh allocation profile の約4.62 GiBがほぼ全部
`Fd_allocate → Truncate → resizeMemData` に帰属していること。
Write の少量ずつの拡張が支配的という仮説は、今回の profile では支持されない。

- mariamem は既に容量を再利用し、1 MiB未満は2倍、それ以上は約1.25倍で拡張する。
  毎回正確な長さで再確保する旧実装ではない。
- pglite-go の WriteAt は常に2倍、最小4 KiB。Truncate の拡張は別経路で、
  毎回ちょうど必要な長さを確保・コピーする。mariamem より一律に効率的ではない。
- 2倍拡張は反復拡張の allocation/copy を減らせるが、保持容量・同時DBのRSSを増やし得る。
  大きな初回 Truncate が主要因なら効果は小さい。
- Fork の既存ファイルは private mapping。サイズを超える拡張時に旧内容全体を heap へコピーする。
  ここを避けるには、倍率変更より大きな内部ストレージ変更が必要。
- pglite-go の I/O は単一スレッドを前提にロックを省略する。MariaDB/WASIXへの移植条件に合わない。

次に許可するなら、**ファイル別の allocate/truncate 履歴を既存 harness で少数ケースだけ採る**。
初回確保、再確保、保持容量、既存内容コピー、mapped file の detach を区別してから、
倍率変更の小さな実験か、別の内部ストレージ実験かを選ぶ。
この報告は改善実装の承認を意味しない。

## 調査対象と同一性

| 対象 | 正確な identity |
| --- | --- |
| 調査開始 main | `0fef33c752053d3bd1e180f9e46f4a301cfcd5eb` |
| 既存 profile の実行ソース | `80a37385f9d1eda6604358dd5ba2235feb0b26ca` |
| 保存済み profile/report の Git revision | [inputs.json](memfs-discovery-evidence/inputs.json) の `profile_evidence_commit` |
| pglite-go | `c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f` |

profile ソースと開始 main の `base.go`、`memfs_growth.go`、`owned_prepared.go` は
`git diff <profile-source> <main> -- <files>` で差分なし。APIやbenchmarkを含む全treeが
同一という意味ではない。結果は既存 macOS arm64・Go1.26.8/1.27.2 campaign の観測であり、
今回の branch を新しく runtime qualification したものではない。

pglite は GitHub Contents API で pinned revision の6ファイルだけ取得した。
ソースのサイズ/hash、profile summary/hash、純粋な容量計算の結果を
[inputs.json](memfs-discovery-evidence/inputs.json) に保存した。外部ソース全体は保存しない。
参照コードのライセンスは Apache-2.0。今回コードの導入はない。

## 1. mariamem の現行実装

### 容量・コピー・ゼロ埋め

[resizeMemData](../../internal/generatedgo/code/base/memfs_growth.go) は `len` を論理EOF、
`cap` を再利用可能な容量として扱う。

| 条件 | 確保・コピー・ゼロ埋め |
| --- | --- |
| 新しい長さが既存cap以下 | 再確保なし。拡張して露出する `[oldLen:newLen]` をclear |
| capを超える、旧capが1 MiB未満 | `max(2×cap, required)` を確保、旧lenを一回copy |
| capを超える、旧capが1 MiB以上 | `max(cap + cap/4, required)` を確保、旧lenを一回copy |
| 空ファイルへの大きな初回確保 | 要求長だけを確保。コピーする旧内容はない |
| shrink / O_TRUNC | 論理長を短くするがcapを保持。後の再拡張で古い内容が見えないようclear |

`make([]byte, size, capacity)` はcapacity全体のbackingを確保する。
profile上のallocation量は論理長でもコピー量でもない。
Go allocatorの丸め、GC時点、OS物理ページの状態は、このコードの容量計算だけでは分からない。
Write/WriteAtでは、その後にpayloadを一回copyする。
cap内の拡張は、書き込まれる領域も一度clearしてからpayloadで上書きする。

[base.go](../../internal/generatedgo/code/base/base.go) の主要位置:

| 位置 | 責任 |
| --- | --- |
| 11700付近 MemFS / memNode | DBごとの木、安定したnode identity、単一FS mutex |
| 11770付近 OpenFile | O_TRUNCはsliceを長さ0にする |
| 11830付近 Rename | path変更でもnode identityを維持 |
| 11915付近 WriteFile | 入力をコピーして保持。外部sliceを借用しない |
| 12012 writeAt | EOF超過時のresizeとpayload copy |
| 12022 / 12030 Write / WriteAt | FS mutex内の操作。WriteAtはoffsetを進めない |
| 12050 Truncate | 同じresize関数を使用 |
| 13247付近 writeVec、13352 Fd_pwrite | iovecを順にWrite/WriteAt。総長を先にreserveする処理はない |
| 13491 Fd_allocate | 現行では `Truncate(offset+length)` へ委譲 |

全FS lockをallocation/copy/clear中も保持する。長いコピーは他のguest threadのFS操作を待たせ得るが、
その待ち時間は今回測っていない。ロックを単に外すとdata sliceの置換・offset・metadataが競合する。

Fd_allocate の現在の委譲は、要求終端が既存長より小さい場合にもTruncateを呼ぶ。
これは予約と論理長の区別を確認すべき既存境界であり、今回の最適化調査で修正・仕様変更はしない。
将来capacity reserveを導入するなら、論理EOFを変更するTruncateとは区別する。

### Fork の成長

[MapPreparedHandles](../../internal/generatedgo/code/base/owned_prepared.go) は、検証済みの
所有FDから `MAP_PRIVATE` でマップし、そのsliceをnodeへ入れる。
Snapshot backingのファイルを子の成長に合わせて伸ばすことはしない。

- マップの長さ/容量内のwriteは子専用のページになる。
- cap超過ではheap sliceを確保し、**旧論理長の全内容をコピー**して切り替える。
- 元mappingは [PreparedFiles.Close](../../internal/generatedgo/code/base/prepared_files.go) まで追跡される。
  detach後も即座にunmapする実装ではない。mappingと新heapが同時に存在し得る。
  mapped全ページが常にRSSに残るという主張ではない。
- shrink後の再拡張は、元Snapshotに存在したbytesを再露出させず、子の論理的なzero rangeになる。

これはfilesystemのbackingであり、別の `sharedimage_mmap.go` のguest linear memoryとは区別する。

### 既にある回帰検証

- [memfs_growth_test.go](../../internal/generatedgo/code/base/memfs_growth_test.go):
  64 KiBずつ4 MiBを拡張したallocation/copyが二次増大しないこと、gap/再拡張のzero、
  O_TRUNC、EOFとcapacityの区別、WriteAtとappend offset。
- [prepared_growth_test.go](../../internal/generatedgo/code/base/prepared_growth_test.go):
  private mapping上のtruncate/regrow、cap超過detach、gap、sibling/base不変、mapping追跡、rename。
- [owned_prepared_test.go](../../internal/generatedgo/code/base/owned_prepared_test.go) と
  [runtime isolation tests](../../tests/gointegration/owned_prepared_test.go):
  正確なbacking identity、DML/schema、世代・順序・並行・Close/失敗cleanup。

今回これらを再実行していない。実装を変える場合の検証責任として読んだ。

## 2. pglite-go VFS の事実

以下は pinned source の読み取り。mariamemで動かした比較結果ではない。

| 項目 | pglite-go | mariamemへの意味 |
| --- | --- | --- |
| [WriteAt](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/file.go#L49) | 連続slice、常に2倍/min 4 KiB、旧内容一回copy | 拡張係数だけは局所的に比較可能。chunk/page方式ではない |
| [Write/Pwrite](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/vfs.go#L415) | 同じWriteAt、Writeだけfd offsetを更新。単一thread前提でI/O lock省略 | offset区別は既存と同じ。lock省略は移植不可 |
| [Truncate](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/vfs.go#L648) | shrinkはslice短縮、growはcap内でもexact-size make+copy | 現行mariamemの共通resizeより不利になり得る |
| [Open](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/vfs.go#L315) | writable open時にlower fileを丸ごとcopy-up。O_TRUNCはempty upper | writable openだけでもコピー。現在のForkのpage-level sharingと違う |
| [copyUp](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/vfs.go#L196) | lowerの全内容をreadしてupper Node.Dataへ | write量が少なくてもfile全体のコピー。lazy dirty-page overlayではない |
| [openLowerHandle](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/vfs.go#L239) | lowerがFile interfaceを満たせば直接handle、その他は全read | read-only resourceでは参考になる。InnoDBの可変ファイルとは別問題 |
| [memFS](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/memfs.go) | upper tree、whiteoutでlowerの削除を表す | path/node/開いているFDの意味を新たに監査する必要 |
| [LoadSubtree](https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/persist.go#L86) | 各保存fileを全readしてupperへmaterialize | 保存DBを全部lazy mappingする方式ではない |

**zero-fillの処理をそのまま借りてはいけない。** pgliteのWriteAtはcap内の再拡張でclearしない。
ソース上、`ABCD → Truncate(1) → Pwrite("X",3)` のような順序では、既存capacityの
B/Cがgapに残る経路がある。これは静的な反例であり、今回実行した不具合再現ではない。
mariamemは同じ状況でgapをzeroにする回帰テストと実装を持つ。
O_TRUNC時のnil化と、単なるshrink後の再拡張も混同しない。

比較から借りられるのは「成長倍率の選択」「read-only handleの利用」「namespaceとstorageの責任分離」
という限定的な考え方。pgliteがMariaDB用のより良いVFSを提供していると結論する証拠はない。

## 3. 既存数値と、分からないこと

別campaignの診断profile。macOS arm64、8 CPU/16 GiB、10 MiB/eight tables、20 DB、
workers=1、app-connections、GOMAXPROCS=8/GOGC=100/GOMEMLIMIT=off。
各compiler/mode一回のsampled alloc_space。表のGiB/MiBはpprof表示に対応する概数。

| モード | Go | 全allocation | resizeMemData | share |
| --- | --- | ---: | ---: | ---: |
| Fresh ×20 | 1.26.8 | 5.77 GiB | 4.62 GiB | 80.04% |
| Fresh ×20 | 1.27.2 | 5.80 GiB | 4.62 GiB | 79.55% |
| prepare + Snapshot + Fork ×20 | 1.26.8 | 896.59 MiB | 636.15 MiB | 70.95% |
| prepare + Snapshot + Fork ×20 | 1.27.2 | 898.02 MiB | 633.75 MiB | 70.57% |

Freshのtopは `Fd_allocate` と `memFile.Truncate` のcumが約4.62 GiB。
resizeのflatと同じallocationを呼び出し側へ帰属した値であり、足してはいけない。
Fork側にはexportTransferの157 MiBもあるが、resizeとは別責任。
Forkの約634–636 MiBを20で割って「子一つのallocation」としてはいけない。
Fresh preparation・Snapshot時の一時memfsを含む。子のmapped growthがどれだけかは未分離。

FreshのGo1.26 CPU topでは全プロセスのmemmoveが5.29%、memclrが4.12%。
この合計もresize専用ではないし、allocator/GC/lockへの間接影響をすべて含まない。
**allocationの80%はCPU・wall time・RSSの80%ではない。**
初回に必要なbackingと再確保の区別もないため、「4.62 GiB全てを削減可能」という上限の置き方は不適切。

### 容量戦略の純粋な計算例

空の単一fileへ64 KiBずつ書く場合の式だけを計算した。DB実行・改善実装のbenchmarkではない。
1 MiB未満の2倍成長を共通にし、その後の係数を比較。
allocatorの丸め、GC、mapped backing、guestのallocate順序は含まない。

| 最終長 | 係数 | 再確保回数（初回含む） | 累積要求容量 MiB | 旧内容copy MiB | 最終cap MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10 MiB | 現行1.25 | 16 | 55.15 | 43.38 | 11.64 |
| 10 MiB | 1.5 | 11 | 33.11 | 21.69 | 11.39 |
| 10 MiB | 2 | 9 | 31.94 | 15.94 | 16.00 |
| 100 MiB | 現行1.25 | 26 | 539.04 | 430.19 | 108.42 |
| 100 MiB | 1.5 | 17 | 388.18 | 258.25 | 129.75 |
| 100 MiB | 2 | 12 | 255.94 | 127.94 | 128.00 |

2倍ではこのモデルの累積要求容量が約42%/53%減るが、最終capは約37%/18%増える。
初回 `Truncate(100 MiB)` なら係数に関係なく一回100 MiB確保、旧内容copyゼロ。
この違いがあるので実profileへの改善率の換算はしない。
一般にも指数成長は既に線形償却であり、pgliteの方式が新しく二次増大を解決するという説明は誤り。

## 4. 候補の分類と評価

| 候補・分類 | Fresh / Snapshotへの期待 | Forkへの期待 | 難易度・correctness risk | 推奨・検証 |
| --- | --- | --- | --- | --- |
| **C1 拡張係数を1.5/2などと比較 — 局所改善** | 反復Truncate/Write/exportでcopyと累積allocation減。初回巨大allocateには効果なし | heapへdetach後の再成長には効く。最初の全file copyは残る | 小。論理EOF/zero/overflowを維持。spare capと並列RSS増加リスク | ファイル別履歴を先に確認。growth/zero回帰→実SQL→同一harnessのalloc/RSS/CPU比較 |
| **C2 Write extensionのclear範囲限定 — 局所改善** | payloadで直後に全上書きされる領域の重複clearを避けられる | private mappingでの重複touchを減らす可能性。書いたpageは結局private | 小〜中。穴 `[oldEOF:writeOffset]` は必ずzero。Truncate regrowは全新規領域zero | allocation自体は減らない。現在主要のTruncate allocationには効かない。shrink/O_TRUNC/sparseの反例を先にテスト |
| **C3 known-length/iovecのcapacity予約 — 局所改善** | 複数iovec/逐次exportの途中再確保を避ける場合に有効 | detach回数と後続成長に限定 | 小〜中。EOFを増やさない内部reserve。全iovec一時bufferを新設しない。offset/部分write/lockを維持 | Fd_allocateは既に終端を渡すため主要経路への改善を期待しすぎない。実際に反復missする経路だけ対象 |
| **C4 chunk/sparse storage — 部分設計導入** | 巨大な初回Truncateを全heap確保せず、未書込rangeをzeroとして表せる可能性 | 増分chunkのみ確保するなら全file copyを避ける可能性 | 中〜大。node.data前提のread/write/stat/exportを変更。truncate後の旧bytes隠蔽、atomic metadata/lock必要 | 将来の別spike候補。pgliteの実装ではない。初回予約が支配的か、実際に触るbytesが小さいか確認してから |
| **C5 mapped prefix＋private growth tail — 部分設計導入** | Freshには直接効かない | mmap全内容のheap copyを避け、小さいtailだけ確保する可能性 | 中〜大。跨るI/O、再truncate/regrow、mapping寿命/alias、exportが複雑 | mapped detachの寄与が実測で大きい時だけ。旧mappingを早期unmapするだけの変更は不可 |
| **C6 lower read-only handleの直接利用 — 部分設計導入** | immutable bundle/resourceコピーが支配的な場合のみ | 既存OwnedPreparedの役割と重なる | 中。入力所有権、FD寿命、変更不能性の証明が必要 | 現profileでは主因の証拠なし。hot InnoDB fileの解決策として優先しない |
| **C7 pglite overlayへの置換 — VFS全体の再設計** | tree/whiteout等を再監査。TruncateとcopyUpはallocation改善を保証しない | writable open時の全copyで現在のpage sharingを失い得る | 大。単一thread前提、FD/node/path identity、WASI ABI、cleanup/ownershipを再設計 | **非推奨**。同じ目的は既存memfsの局所/内部storage変更で検討可能 |

C1〜C3は比較可能な小さい案だが、現profile主因に対する勝算は未確定。
C4は「80%が巨大初回予約の実体化なら、倍率よりこちらが効く」という条件付き仮説。
pgliteの2倍成長と、独自に考えたchunk/sparse案を同じ証拠として扱わない。
大きいbuffer poolや、heap確保を匿名mmapへ移すだけの案は優先しない。
allocationカウンターを下げてもRSS/CPUや保持期間を悪化させ得るため。

## 5. MariaDB / WASIX / Snapshotへの影響

MariaDB/InnoDBのdata・redo・temporary fileでは、予約/伸長とランダムpage更新を区別する必要がある。
SQL payloadの10 MiBはfilesystem全体のサイズではない。空に近い状態にも内部backingが存在する。
現profileにはfile名別履歴がないので、特定のredo/data fileが4.62 GiBを占めるとは言わない。
MariaDBの設定を縮めること、guestを変更することはこの調査の解決策に含めない。

維持すべき境界:

1. 新規領域/穴はzero、logicalEOFはcapacityと別。shrinkした内容を再拡張で戻さない。
2. positioned writeと通常writeのoffset、複数FDのnode identity、rename/unlink後のopen FD、
   file/directory replacement、短いread/EOFを保持する。
3. WASIX workersからの並行read/write/truncateを現lockと同等に安全にする。
   pgliteのlock省略を移植しない。lock分割は独立した大きな変更として扱う。
4. 全ての可変storageは子DB所有。Snapshotのowned FD/backingにはwrite/truncateしない。
   空間予約のための原file成長、MAP_SHARED、sibling間の可変slice共有は不可。
5. Snapshot作成はguest停止/worker join後の論理内容だけをexportする。
   spare cap、chunkの穴、切り捨てた古い内容をexportしない。
6. acquisition時の完全検証と同じowned resourceを使う契約、Fork/Closeのpin、失敗cleanupを維持。
   成長後のold mapping解放は、全alias/workerの寿命を証明してから。

page-level CoWが既にあるForkにfile-level copyUpを入れても、改善とは限らない。
RSS低下には、累積alloc低下とは別に、heap peak・同時保持capacity・private page増加・reclaimを確認する。
CPUはcopy/clear/GCだけでなくSQL・guest実行・thread同期を含む。

## 6. 次の限定検証案（未実施）

### まず帰属を決める

新frameworkは作らず既存 `benchmarks/ownedprepared` のminimal/10/100 MiBと
既存Snapshot characterizationを使う。ファイルごとに以下の**集計**だけを追加する候補:

- caller: allocate / truncate / Write / pwrite、初回確保と再確保の回数
- oldLen/oldCap、要求EOF、最大len/cap、累積確保容量、旧bytesコピー、clear bytes
- private mappingからのdetach回数とコピーbytes
- phase: Fresh起動、fixture投入、Snapshot export、Fork起動、子SQL

全callログや毎writeの時刻測定は避ける。既存profileと通常suiteを分け、instrumentation overheadも記録する。
旧Snapshot監査には「毎回exact-size make」の時代のpatchがあるので、そのgrowth集計を
現resizeへ無条件に適用しない。現在のcounter/phase境界に合わせる。
再確保が小さければC1を棄却できる。初回大規模確保後の実write量がほぼ全体ならC4の価値も弱くなる。

### 実装を別途承認した場合のみ

- 局所storageテスト: grow/shrink/gap/再grow/O_TRUNC、append/pwrite/iovec、int bounds、
  rename/unlink/replacement、open FDの同一性。対象handwritten/host primitivesのrace検証。
- 実SQL: INSERT/UPDATE/DELETE、schema、growth、commit/rollback、並行siblings、世代/順序、
  AからBを作った後に新Snapshot Cを作る場合の内容/cleanup。
- macOS arm64 / Ubuntu x86_64: relevant ownership/filesystem/runtime acceptance。
  今回はcodeを変えていないためこのgateを走らせていない。
- 性能: 同じsource/guest/fixture/compilerでserial ABBA。Fresh prepare、Snapshot全公開操作、
  Fork manyとSQL・Closeのsuite totalを別々に測る。allocation、copy、CPU、RSS/physical footprint、
  peak/close後reclaim、FD/mappingを記録。parallelを直列計測と競合させない。
- 合格条件: correctness先行。alloc減のみで採用しない。RSS悪化、余剰cap、並列pressure、
  suite wall/CPU、コード・寿命の複雑化を含めて人間が判断する。

### generated-sourceの正しい変更入口

将来のC1/C2/C3は `internal/generatedgo/code/base` の生成済みファイルを直接直して完了にしない。
現行のcanonical adaptation:

- [memfs-growth.go.txt](../../benchmarks/spikes/generated-go-integration/memfs-growth.go.txt)
- [patch_memfs.py](../../benchmarks/spikes/generated-go-integration/patch_memfs.py)
- [setup_audit.py](../../benchmarks/spikes/generated-go-integration/setup_audit.py)
- [generated input manifest](../../release/generated-go-inputs.json)
- [generate_runtime.py](../../scripts/generate_runtime.py)

memfs_growth.goはHANDWRITTEN_FILESのoverlayではなくcandidate入力としてhash固定されている。
正しいtemplate/adaptationを変更し、生成→input/provenance照合→再生成性を確認する。
source内容の更新とlicense依存追加は別であり、hashを合わせるだけの監査更新はしない。

## 7. 再現・保存・cleanup

既存profileの実行コマンドは [profile.py](../benchmarks/go126-vs-go127-evidence/profile.py) を保存した。
これは元campaignの再現手順であり、今回実行していない。
profileのraw binary checksumとsummary checksumを保存。
共有profileと再現手順は [Go比較証拠](../benchmarks/go126-vs-go127-evidence/README.md) に集約し、
この調査のinputs.jsonは `retained_path` と原保存commit/hashで同じ内容を参照する。
重複コピーは保持しない。原結果はGitのpinned revisionでも参照可能。

外部sourceの再取得:

```text
gh api repos/moriyoshi/pglite-go/contents/<file>?ref=c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f
JSON.contentをbase64 decode → inputs.jsonのsha256と照合
files: vfs/file.go, vfs/memfs.go, vfs/vfs.go, vfs/persist.go, vfs/persist_test.go, LICENSE
```

容量モデルの再計算式: oldLen=cap=0から64 KiBごとにEOFを増加。
EOF>capの場合 `growth = cap (<1 MiB) else floor(cap×(factor−1))`、
`cap=max(cap+growth,EOF)`、allocated+=cap、copied+=oldLen。その後oldLen=EOF。
モデルのbytesは [inputs.json](memfs-discovery-evidence/inputs.json) に保存している。

保存物はこの報告、入力/hash/model JSON、選択した既存profile summaryと再現コマンドのみ。
専用workspaceの外部sourceはhelperで削除済み。receiptと小さなcleanup証拠だけ残した。
helperの `retained_large_paths=[]` / `cleanup_debt=[]` を確認。build全体は約30 MiB、
元調査の選択profile証拠は約40 KiB（main集約時に共通保存物への参照へ変更）。今回のworkspaceに1 GiB超の保持物はない。
既存v0.4.6作業・結果は所有範囲外で変更していない。
文書・参照・JSON/hash・diff/statusを検証し、変更していないruntimeの再build/testは行わない。
