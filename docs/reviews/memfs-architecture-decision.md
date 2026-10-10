# MemFS/VFS Architecture Decision — v0.4.x

2026-10-10。Principal Engineerによる技術判断。Human承認・実装採用とは区別する。
基準main: `64d6d8411fd4d47e904df7646c38d6ca421f5938`。
branch: `experiment/memfs-architecture-decision`。変更はこの判断書と再確認sourceのhashのみ。

## 1. Executive decision

**現行memfs＋MAP_PRIVATEを維持する。VFS全体の置き換えには進まない。**
最適性が証明されたからではなく、現在の製品性能・隔離契約が成立し、代替案の
追加利益を裏づけるfile別・phase別の証拠がまだないためである。

1. 次工程は既存harnessによる**一回の限定的なallocation帰属計測**とする。
   「何を知れば決められるか」は第7節で固定し、文献調査を延長しない。
2. 小規模PoC候補は最大2件: **B 成長倍率調整**、**C sparse/chunk storage**。
   どちらも条件付きで、計測なしに実装を始めない。最初に両方を作らない。
3. **D mmap prefix＋growth tailは保留**。Fork由来のdetach量が分からず、
   Freshの主題を解決しない。後述の昇格条件を満たす場合だけ候補枠を入れ替える。
4. E file単位CoWへの一律置換、F Overlay VFS全面導入、G browser block storageの
   直接移植は現状ではReject。各方式の有用な原理まで否定する判断ではない。
5. v0.4.6 qualification/release、v0.5.0安定guest更新、v0.6.0互換性Discoveryを進める。
   この性能最適化をrelease blockerにしない。**allocationが減るだけでは採用しない。**

継続投資は、suite wall/CPUか、同時DBの実メモリ予算を改善する場合に限る。
連続bufferは単純で有力な選択であり、無駄が小さいと分かれば現状維持で調査を終了する。

## 2. Established facts — 証拠と反証

### 確認した資料と同一性

| 資料 | 固定参照 |
| --- | --- |
| A/B memfs・pglite | [memfs discovery](memfs-optimization-discovery.md)、原branch `experiment/memfs-discovery` / `b5ae57121a285fe44a2f60015609591f60703807` |
| C pgmem | [pgmem review][pgreview]、`experiment/pgmem-vfs-review` / `55c5639aa43e6cad72a53d313c58a5e2ba9bdb20` |
| D block storage | [block discovery][blockreview]、`experiment/block-storage-discovery` / `9edb01a726345909a3590a42e10258c9cc28dc33` |
| E performance | [Go1.26/1.27](../benchmarks/go126-vs-go127.md)、[profile command](../benchmarks/go126-vs-go127-evidence/profile.py)、[alloc top](../benchmarks/go126-vs-go127-evidence/profile-1268-fresh-alloc-top.txt)、[CPU top](../benchmarks/go126-vs-go127-evidence/profile-1268-fresh-cpu-top.txt) |
| Product contract/acceptance | [v0.4.6承認済みreview][v046review]。この承認を再審議しない |

既存profileの実行sourceは `80a37385f9d1eda6604358dd5ba2235feb0b26ca`。
そのsourceと今回baselineの `base.go` / `memfs_growth.go` / `owned_prepared.go` はdiffなし。
reportの集約SHA、実行SHA、release候補SHAは同じではない。
外部4repoの重要13ファイルを元と同じ固定SHAで再取得し、Git blob identityを再確認した。
[再確認一覧](memfs-architecture-source-checks.json)。全文の複製は残さない。

| 分類 | 確定すること | 確定しないこと |
| --- | --- | --- |
| 実測 | 10 MiB/8 tables、20 DBのFresh診断でsampled allocation 5.77/5.80 GiB、resize 4.62 GiB（約80%） | 20 DBが同時に5.8 GiBを保持、起動だけで4.62 GiB、全量削減可能、という意味ではない |
| 実測 | alloc topでresize flatとFd_allocate/Truncate cumがほぼ一致 | 初回要求と反復予約の比率、file名、live/retained bytes、copy量は未分離 |
| 実測 | 4-test light Fresh ready p50約57.6 ms。10 MiB serial suite約3.34秒Fresh／1.94秒Fork（Go1.26） | すべての実workloadでForkが優位、またはstorageがcritical pathとは言えない |
| 実測 | 10 MiB serialの4-test Peak RSSはFresh約466 MiB、Fork約655 MiB。ForkはTotalAlloc約670 MiB、Fresh約1,185 MiB | 少ないGo allocationが少ないprocess Peak RSSを意味しない。Forkのpeakにはprepare/Snapshotも含む |
| 実測 | CPU profileのmemmove 5.29%、memclr 4.12%。同期・memory checkも大きい | この9.41%はmemfs専用ではなく、GC/lock間接費を含む改善上限でもない |
| コード | 空fileの大Truncateは要求長のmake、既存cap超過は旧lenを一回copy。cap内growはclear | make時に全capacityが即physical residentになるか、OS/Goのzero実装費用は不明 |
| コード | Forkはfile-backed MAP_PRIVATE、mapped cap超過でheapへ旧len copy、元mapはCloseまで追跡 | そのdetachが通常製品workloadで頻発し、wall/RSSを制約しているかは不明 |

### 先行結論へのchallenge

**同じ事実を使った複数報告は、独立した複数回の性能実証ではない。**
4.62 GiBの観測をすべてのDiscoveryが引用している。証拠の重みを件数分増やさない。
「Fd_allocateが主経路」は支持できるが、「巨大な初回確保が主因」はまだ仮説。
同じfileへの段階的なallocateでも同じstackになる。初回と再確保を区別する必要がある。

報告間の主要な実装事実に矛盾は見つからなかった。ただし次の読み替えは必要である。

- **Fresh allocationの範囲:** profileはstartup＋fixture/SQL＋Closeを含む。
  startup最適化の価値を主張するにはphase帰属が必要。SQL payload10 MiBもFS総量ではない。
- **世代が異なるFork数値:** v0.4.3のhash検証53–62%を、OwnedPrepared導入後の
  v0.4.6 Forkへ当てはめない。現在は取得時検証＋exact backing、Forkごとの全rehashなし。
- **現行設計への過大評価:** OS page CoWは容量内更新の長所であり、Snapshot作成時の
  file export/materialization、FD保持、grow時copy、FS全体lockの費用を消さない。
  既存testsは全host filesystem入力・全guest race correctnessの証明ではない。
- **pgmemへの過小評価:** FS.Cloneは不変化した冷たいfile treeをin-memoryで共有し、
  Snapshot作成の全量直列化を避けられる。read-mostly多数子・小file中心なら有力。
  first-write全file copyだけを比較して全体が劣るとは言えない。
  ただし永続Snapshot、Go/Python handoff、取得検証を含むmariamemへ採用する費用は別。
- **block方式への過小評価:** ブラウザ特有の実装コストが大きくても、EOFとpayloadを
  分離する原理はGoで有効になり得る。Absurderの重複cacheをCの必須コストにしない。
- **性能推論の限界:** 倍率の容量モデルは反復伸長を仮定する算術で、実workloadの改善率ではない。
  sparseは未使用領域の保持を避け得るが、全量write/exportで利益が消える場合もある。

correctness上の指摘にも確度を付ける。pglite/pgmemのshrink→owned regrowで旧bytesが
残る経路、Absurder main truncateのblocks保持/read非clipは**静的に追跡した具体的反例**。
本レビューで上流SQL実行により再現した不具合ではない。これを理由にプロジェクト全体を
「壊れている」と判定しない。一方、曖昧な不安だけでもなく、移植時に修正が必要な具体的条件である。
MariaDBでのlost updateや過大RSSは未実証の移植リスクとして扱う。

## 3. Cross-project comparison

| 実装・固定source | 有用な設計 | mariamemの問題への適合・制約 |
| --- | --- | --- |
| [pglite-go][pglite] `c6b3b5d4…` | lowerをReaderAt等で直接利用、upperへcopy-up、WriteAt 2倍/min4 KiB、namespace overlay | read-only bundle統合には有用。grow-Truncateはexact-size copy、writable openで全file copy、I/O single-thread前提。巨大初回reserve削減にならない |
| [pgmem][pgmem] `3433a40b…` | FS.Cloneでmetadata独立/data共有、ownでfile単位detach、growthとdetachを融合、tree mutex | 冷たいin-memory Snapshotの作成費用とFD依存を減らせる可能性。初回reserveは連続heap、少量更新でも全file detach、grow時も全copy。GC寿命とalias規律が必要 |
| [absurd-sql][absurd] `1bff34fc…` | SQLite page単位record、metadata EOF、partial-page RMW、通常IDB経路のmissing zero | sparse表現の具体例。ただしheader/page-size依存、truncate後の旧block、SQLite transaction/worker通信。memory backendは連続、fallbackは全blocks readAll |
| [AbsurderSQL][absurder] `1113358c…` | 固定4 KiB、block map、cache/dirty/metadata分離、persist/export | 可変global storageをconnection間共有。独立Fork CoWなし。cacheは総量上限でなく、clone/RMW/checksumコストと全量restore/exportあり。nativeとWASMの経路も違う |
| mariamem現行 | [resize](../../internal/generatedgo/code/base/memfs_growth.go)、[prepared map](../../internal/generatedgo/code/base/owned_prepared.go)、[owner](../../internal/snapshot/owned.go) | Fresh heap＋child-private maps、EOF/zero/隔離の既存受入。大reserve実体化、cap超過copy、Snapshot materialization、coarse lockの改善余地は残る |

SQLiteのページ/transaction lock、PostgreSQLのheap/WALとclone lifecycle、MariaDB/InnoDBの
事前reserve・redo/data/temp・多workerという違いがある。InnoDB pageとOS pageとchunkは同一ではない。
どのサイズが最適かを他DBの定数から選ばない。外部のlock削除やEOF挙動をコピーしない。

## 4. Architecture trade-offs

A以外は未測定の候補。表の利点は可能性であって、mariamemでの改善実績ではない。

| 案 | Fresh / Snapshot / Fork startup | 更新・SQL / allocation | Peak RSS・多数DB | 解決しない問題 |
| --- | --- | --- | --- | --- |
| **A 維持** | 既存の実用性と一つの取得契約。Snapshotはmaterialize | slice I/Oが単純。大reserveとgrowth copyが残る | Fork clean-page共有、各DB heap/cap/dirty/runtimeは残る | allocation/lock/export費用の削減 |
| **B 倍率** | 反復growがstartup/setup/exportにあれば効く。初回要求は不変 | realloc/copy回数減候補。通常SQLのcap内I/O不変 | spare capacity増加で多数DBのRSS悪化もある | 未使用の初回reserve、最初のmapped detach、Snapshot形式 |
| **C sparse/chunks** | 未使用reserveを遅延。Snapshotの現形式exportは全論理内容処理が残る。Fork private mapsは維持可能 | 追加chunkで全file reallocを避ける。lookup/境界分割増でhot SQL悪化も | 未使用領域が多いと有望。全使用ならpayload＋metadata/fragmentation、上限自動保証なし | guest scan/同期、Snapshot hash、OS CoWの代替は自動では得られない |
| **D map prefix＋tail** | Freshに直接効果なし。通常Fork map startupほぼ同じ、二領域exportが必要 | mapped growth全copy回避。境界I/O追加、tail再確保は残る | 大prefixをheap重複保持せず済む候補。dirty prefix/元mapは残る | Fresh reserve、prefix内の大量dirty、Snapshot全量export |
| **E file CoW** | in-memory CloneならSnapshot materialization回避候補。tree copy＋新runtime | first writeは全file copy。small files/read-mostlyで合理性、large sparse writesで不利 | mmap/FD依存減候補、baseline heap常駐と全file dirty copy。GC寿命に依存 | 初回reserve、growing file全copy、persist/import設計 |
| **F Overlay** | immutable lower利用に強い。writable open copy-upはForkで逆効果になり得る | namespace/whiteout、全file copy-up。hot I/O改善の証拠なし | read-only共有可能だが現mapと重複、upper全量copy | 主なFd_allocate初回heap確保、runtime起動 |
| **G absurd型block store** | metadata-only伸長可。Snapshot/Forkは別途設計。full export/import費用 | random block RMW、cache/transaction/永続化税。追加copyにもなる | 未使用block省略可、dirty/cache重複とメタデータ管理が必要 | MariaDB意味論、immutable child isolation、総量上限 |

| 案 | concurrency / file semantics / Snapshot correctness | 実装・guest更新・保守 |
| --- | --- | --- |
| A | 既存FS mutex/ownerを維持。ただしhostの負数/overflow/reserve edgeは全面保証なし | 最小。guest更新で既存contract再検証 |
| B | 現lockとzero/EOFを維持できる。容量算術overflowとRSSを確認 | 小。canonical growth template変更＋再生成 |
| C | holes/EOF/atomic RMW/shrink後不可視化、FD/node安定、exportが必要。初期PoCで共有chunk-CoWは不要 | 大。node.dataを前提としたI/Oを監査。標準的file contractに閉じればguest非依存にできる |
| D | prefix shrink/regrowの旧bytes隠蔽、境界write、map lifetime、export失敗処理 | 中～大。append中心ならCより狭いが、一般truncate対応なら単純な二sliceだけでは済まない |
| E | 全write入口でdetach、mutable alias禁止、owner/GC寿命、Clone境界を新設 | 大。API同一でもin-memory/persisted二実装を持つ費用。guest shutdown依存も再検証 |
| F | namespace/FD/unlink/rename/copy-up競合を広く再監査。single-thread最適化不可 | 大。FS置換はguest更新と互換性維持の変更面を広げる |
| G | SQLite前提を剥がしWASIX、partial I/O、durability、release/isolationを再定義 | 最大級。Goへ原理だけ移すとC。browser backend/cache/MVCCの移植は目的に過剰 |

### Q1/Q2 — Freshとsparseの判断

**削減余地はあるが量は未確定。** 初回makeの旧data copyはゼロなので倍率では解けない。
同じ予約が後でほぼ全部必要なら、sparseは必要payloadを消せず、確保時期と連続再確保を変えるだけ。
逆に大きな未書込領域を保持したままCloseするfileでは、sparse表現が問題に直接対応する。

「未書込」と「不要」は同じではない。guestがzeroをreadするholeも正しい論理dataであり、
backendはread先へzeroを返す必要がある。明示的にzeroを書いた領域はwrite済みとして数える。
zero圧縮/内容走査を今回の候補へ暗黙に足さない。Snapshot exportが全rangeをtouchすれば
Fresh中の利益がSnapshot時に移る可能性がある。phaseとlifetimeを測る理由はここにある。

Cは合理的な内部表現候補だが、`fd_allocate`を単なるEOF設定へ弱めて成功扱いにしてはいけない。
reservation/error保証を維持する資源accountingと実体化を分ける必要がある（第5節）。
永続Snapshotはlogical file bytesとしてexportすれば形式変更不要。sparse manifestや
immutable chunk refcountまで導入する必然性はない。

### Q3/Q4 — Fork growthとCoW

Dの価値は**mapped detach bytes × 発生する子数 × live期間**に依存する。
大fileへ小さくappendしてすぐCloseするなら全file copy回避の価値があり得る。
大半を上書きするならcopy節約と最終private memory節約は別になる。
現Fork profileはprepare＋Snapshotを含むため、そのallocationを子detachの根拠にしない。

Dは「既存map＋一つのtail」で済むappend中心に限ればCより狭い。
ただしprefix途中でtruncate→regrowした旧data、gap、再Snapshotを扱う必要があり、
cheapなパッチと呼べない。Fresh優先の現在は保留する。

Eが有利になり得る条件は、Snapshot作成頻度が高い、主にin-memory利用、fileが小さい、
子が少数fileしか変更しない、FD/map setupが予算上の問題になる場合。
Aが有利なのは大きなfileの少数page更新、多数の独立child、保存/Load経路を一つに保ちたい場合。
MAP_PRIVATEにもpage fault/page table/exportの費用があり、常勝を主張しない。
Eを再考するならSnapshot全体の保存・検証・言語間利用を含む比較が必要で、
FS.Clone単体の安さだけでは変更を承認しない。

### Q5 — translator/runtime/storageの境界を決める

**fileの論理操作とstorage表現はmariamemのhost filesystem側の責任とする。**
WASM命令lowering、生成guest関数、MariaDBのfile名に応じた特例に押し込まない。

- Bは既存のcanonical `memfs-growth.go.txt` と出力adaptationで小さく保つ。
  生成済み `internal/generatedgo/code/base` だけを直接編集して終わらせない。
- C/Dへ進む場合は、現在のnamespace/node/FDとlockを維持し、file storageの
  ReadAt/WriteAt/Resize/Releaseの責任を狭く分離する。最初は内部concrete typeでもよい。
  public VFS interface、plugin system、独立backend packageの先行整備は行わない。
- WASIX host adapterがoffset/length/errno/reservationを検証し、storageがEOF/zero/bytes所有を扱う。
  初期PoCでlock分割やasync I/Oも同時に変えない。
- 汎用的なWASI bounds/reserve修正はgoccy/wasm2go由来のhost supportへの還元候補。
  mariamem固有のOwnedPrepared/mmap lifetimeや最適化policyはlocalに置く。
  upstream採用待ちをrelease依存にしない。
- 現在 [setup_audit.py](../../benchmarks/spikes/generated-go-integration/setup_audit.py) は
  自身をdiagnostic infrastructureと明記する。template/adaptationを再現する入口であり、
  これ単独をproduction regenerationの完了とみなさない。
  [generate_runtime.py](../../scripts/generate_runtime.py) はaccepted candidate inventory/data hashを
  [input manifest](../../release/generated-go-inputs.json)と照合してinstallし、provenanceを出力する。
  memfs growthはpinned candidate入力で、OwnedPrepared等のhandwritten overlayとは区別する。
  将来変更はcanonical入力→accepted inventory→install→source/provenance再現確認を一貫して更新する。

## 5. Critical correctness risks

**現状維持は現host adapterの全意味論を承認することではない。**
[Fd_allocate](../../internal/generatedgo/code/base/base.go) L13491は
`Truncate(offset+length)`へ無条件委譲するため、既存EOF内の要求で縮小するコード経路がある。
Truncate/ReadAt/WriteAtの負数・加算overflowも包括検査ではない。
これはコードで確認できるedge behaviorで、guestからの実到達性・SQL損失は今回未実証。
[WASIX fd_allocate説明](https://www.wasix.org/docs/api-reference/wasi/fd_allocate/)は追加空間の確保・伸長を扱う。
無条件truncateをそのまま新backendの仕様にしてはいけない。

次のstorage変更の前に、小さいcontract testでreserveが既存bytes/EOFを縮めないこと、
zero length、上限/overflow、失敗時不変を固定する。資源不足時の失敗契約も確認する。
これは性能PoCと別のcorrectness責任で、単なる調査先送りにはしない。
現releaseのデータ損失が再現された場合は独立bugとして優先するが、本レビューに
その実行証拠はなく、性能改善をv0.4.6/v0.5のblockerに変える根拠はない。

C/Dの必須条件:

1. 新規holeとtruncate後のsuffixはzero。部分chunk内の旧bytesも隠し、regrowで戻さない。
2. 同block異range write、read/grow、truncate/write、append/pwrite、iovec/short I/Oを
   現在と同等以上に同期する。単なるmap mutexとRMWの原子性は別。
3. unlink/rename後もopen FDが指すnode/ownerは安定。storage切替が既存FDを置き去りにしない。
4. Snapshot-owned backingは不変。子間隔離・親Close後の子・新Snapshot・Loadを維持。
   public保存形式を変えず、holesを正しいlogical bytesでexport/hashする。
5. root/worker join後にexactly-once release。partial init、失敗、反復Close、旧map aliasを検証。
6. fd_allocate成功を「メモリが必要になったら後で確保できるはず」と読み替えない。
   sparse payloadとreservationの資源保証は別。保証を守れないPoCは不採用。

上流の静的反例を直すことだけではmariamem受入にならない。Goのrace test範囲、
SQLite単thread、MariaDB共有workerを区別し、両supported platformで必要な受入を行う。

## 6. Adopt / Experiment / Defer / Reject

| 判定 | 対象 | 今回の決定・覆す条件 |
| --- | --- | --- |
| **Adopt** | A、既存MAP_PRIVATE/OwnedPrepared/保存形式、最小測定 | v0.4.6/v0.5の基盤を維持。元と子の所有権、zero/EOF、source再現性を最適化の制約にする |
| **Experiment 1** | B growth倍率 | 再確保が主要fileのallocation/copyを実際に増幅している場合だけ。一つの係数（まず1.5）を比較。初回reserve主体なら起動しない |
| **Experiment 2** | C sparse/chunks | 初回reserveの未使用rangeがlifetime中に大きく残り、メモリ予算または時間に影響する場合。Fresh heap fileを対象、既存mapped Forkは維持する最小PoC |
| **Defer** | D prefix＋tail | mapped detachが子単独の主要なcopy/資源費だと判明した場合、未開始のB/Cいずれかと枠を入れ替えて再判断。第三の並行PoCを足さない |
| **Defer** | in-memory Snapshot取得経路、lock分割、zero-write検出、buffer pooling | 異なる問題を混ぜない。Snapshotのmaterializationかlock待ちが製品上支配する証拠が出た時の別review |
| **Reject（現在）** | Eへの一律置換 | 大file少量更新で全file detachを導入し、現page sharingを失う。in-memory Snapshot中心でfile/FD/作成費用が支配するなら再検討 |
| **Reject（現在）** | F全面置換 | hot mutable fileにcopy-up税、namespace/FD/raceの広い再認定。複数immutable lowerの合成という製品要求が生じれば再検討 |
| **Reject（現在）** | Gの直接移植、Absurder cache/IDB/MVCC導入 | browser永続化問題をGo disposable DBへ持ち込む根拠なし。blockの原理はCで評価。cacheが必要な外部storage製品要求が生じれば別判断 |
| **Reject** | 無条件2倍化、GC/mmapへ費用を隠すだけ、clear/bounds/隔離の緩和 | allocation表示を良くするだけでは製品改善にならず、意味論を犠牲にした改善は受け入れない |

E/F/GのRejectはライセンスだけで決めていない。直接移植には別途、pglite Apache-2.0、
pgmem/absurd MIT、Absurder AGPL-3.0の由来・義務の評価も必要。
本案は外部コードを取り込まず、自身のhost契約に基づく内部実装を前提とする。

## 7. Minimum next measurement — これで次の選択を決める

既存案を概ね採用するが、**phaseとnode lifetimeを必須にし、全callログ・内容走査は加えない**。
pathはrenameされるので安定node IDで集計し、表示用file名/categoryを添える。

| 最小集計（file × phase） | 判断への用途 |
| --- | --- |
| allocate/truncate/writeによる初回・再確保のcount、requested EOF、max len/cap、allocated capacity合計 | Bが解ける反復growか、Cが対象とする初回reserveか |
| old logical bytes copied、clear bytes、mapped detach count/bytes | copy/zeroとallocationを分離。Dへの昇格条件 |
| 成功したwriteのrange union、総read/write bytes、EOF/capのphase末値。shrink/O_TRUNCでepoch更新 | 予約のうち未write範囲と再利用を推定。反復上書きを「大量の実体使用」と誤認しない |
| phase末live heap/cap、process Peak RSS/physical footprint、suite wall/CPU、Close後の既存counter | 削減が製品予算に効くか。Go heapとmaps、ピークと累積を分離 |

phaseはFresh readyまで／fixture+SQL／Snapshot作成／Fork readyまで／child SQL+Close。
Snapshot exportのread/writeはguest利用と別集計にする。nodeを削除した時も集計を失わない。
明示zero writeもwriteに数える。range unionはbounded interval/bitmap等で計測専用に保持し、
粒度誤差・observer allocationを記録する。正確なper-write time、全bytesログ、
全file内容のnonzero scan、全組合せのblock size sweepは不要。

最初は一つのcompiler・同一source/guestでminimalと10 MiB/8 tables、Freshと
Prepare→Snapshot→Fork→use→Closeを各3回、最大1 active DBで帰属を採る。
既存unmodified harnessとのtimingを比較しobserver影響を明示する。採用判断用の速度値にはしない。
既存4並列のresource evidenceを参照し、candidateを選べた場合にだけ同条件を再測定。
100 MiBは小caseで説明できないgrowth/detachがある時だけ追加。別benchmarkと同時実行しない。

**routing rule（今回定める工学上の選択基準、測定済みの性能予測ではない）:**

- **Bを選ぶ:** 再確保由来のcapacity要求がmemfs allocationの少なくとも25%を占め、
  old-data copyも同じfile/phaseに集中する。既存growth modelを実traceへ当て、
  並列live cap予算に収まる係数だけを試す。allocation比だけで採用しない。
- **Cを選ぶ:** readyまたはfixture終了時点で少なくとも32 MiB/DBかつreserveの25%以上が
  未writeとして残り、その状態が主要phaseを跨ぐ。同時DBのメモリ予算に効く見込み、
  またはallocation/zeroが時間上の費用と対応することを条件にする。full-file export後のpeakも評価する。
- **両方成立:** 実traceのcopy節約余地が大きくBで予算を満たせるなら低コストのBから。
  初回reserve主体でBが主要問題を残すならCから。一つが有効なら二つ目は不要。
- **mapped copyだけが支配:** Dを再reviewへ昇格。子だけのcopy量とlifetime/peakを根拠にし、
  prepare/Snapshot込みのallocation値は使わない。Cより狭く解けるなら枠を置き換える。
- **allocationだけ多い:** suite wall/CPUへの寄与が小さく、同時DBのメモリ予算も満たすならAで終了。
  80%という比率自体を実装投資の理由にしない。

32 MiB/25%はPoC候補を絞るscreening値で、予想削減量や自動承認閾値ではない。
時間の帰属が不明な場合に限り、resize部分の集計時間と既存CPU profileを一回追加する。
全I/Oへのtimerや広いlock profilingへ発展させない。

**PoC終了・採用条件:** correctnessを先に通し、同一条件ABBAでinstrumentationなしの
既存suiteを比較する。目標はwallまたはCPUで10%以上、あるいはactive physical footprintで
20%以上かつ32 MiB/DB以上の削減で、ばらつきに埋もれない実用的利益。
これは期待値ではなく複雑性を負担するための目安。memory目的なら時間改善は必須でないが、
別指標の5%以上の持続的悪化、Close後累積、FD/map leak、保存互換性破壊を受け入れない。
境界的な結果はチューニングを繰り返さずHumanへ戻す。B/Cとも根拠が消えれば実装せず終了。

## 8. Roadmap recommendation

**既定方針を支持する。v0.4.6を完了し、v0.5.0安定MariaDBへ進める。**
accepted consumer/product結果をstorage literatureのために再審議しない。
v0.6.0のcompatibility/workload Discoveryにも新backendを前提条件として追加しない。

最適化は独立の将来タスク。開始条件はrelease trackと競合しない担当/資源、固定baseline、
明示disk/memory予算、上記限定計測と終了条件への合意。性能だけの理由でv0.5を待たせない。
現在のalpha guestで先に測る場合はallocation patternをguest依存と明示する。
**v0.5前のprofileで選んだPoCをstable guestへ無検証で統合しない**。
実装投資を急ぐ資源障害がないので、本格的なPoCはstable guestの同じ小caseで
帰属が維持されることを確認してから着手するのが合理的である。

終了成果は「一案を採用」「一案をreject」「A維持」のいずれでもよい。
canonical runtime再生成・必要な両platform受入・保存互換性・cleanupまで完了できない変更は
productionへ入れない。実験worktree/cacheを残して完了とはしない。

## 9. Open questions — 判断の境界

不足情報は第7節の計測で答える四点に限定する:

1. 初回reserveと再確保は、どのfile/phaseで何bytesか。
2. reserve後のwrite coverageとlive期間はどれだけか（zero内容の比率は今回測らない）。
3. Forkの子単独でmapped detachは発生し、どれだけcopy/peakに寄与するか。
4. 節約対象がwall/CPUか実メモリ予算に意味を持つか。

未知の最適chunk size、全OS page挙動、全MariaDB file patternを先に網羅する必要はない。
fd_allocate edge/資源保証は性能効果とは別のcontract test責任として扱う。

## 10. Human decision points

1. **現行memfsを維持してv0.4.6完了・v0.5へ進むか。推薦: Yes。**
   VFS置換に値する性能証拠はなく、既存の実用性と隔離を維持する利益が上回る。
2. **独立した限定計測を次の最適化タスクとして承認するか。推薦: Yes、release/guest更新を待たせない範囲。**
   PoC枠は条件付きB/Cの2件、Dは枠の入替review、E/F/G直接置換は見送る。
3. **allocation減だけでなく時間か実メモリ予算の改善を採用条件にするか。推薦: Yes。**
   閾値は第7節を初期予算とし、未達なら現状維持で終了する。

上記はHumanへの最終推薦であり、このbranchから実装やreleaseを開始しない。

### Review verification / preservation

固定source13ファイルのGit blob/SHA256を確認し、mariamemのresize/FD/map/owner/exportと
canonical adaptation/installを読んだ。既存profile command・alloc/CPU top・製品数値の範囲を照合。
原報告へのリンクはbranch latestではなくcommit固定。docs-scope canonical check、
local links、diff/statusを確認。新benchmark、runtime build/test、CI dispatchなし。
main/v0.4.6候補を変更せず、文書とhashを独立branchへcommit/push。
取得sourceと完了worktreeはGit-aware cleanupし、compact証拠・refsだけ保持する。

[pgreview]: pgmem-vfs-design-review.md
[blockreview]: block-storage-design-discovery.md
[v046review]: https://github.com/masahitojp/mariamem/blob/8c07a9bd3278f7c8d2c633c38b7c41377d43100a/docs/reviews/v046-human-review.md
[pglite]: https://github.com/moriyoshi/pglite-go/blob/c6b3b5d4ae4744e97eb320ff03e1a1d472b4522f/vfs/file.go#L49
[pgmem]: https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/internal/vfs/vfs.go#L681
[absurd]: https://github.com/jlongster/absurd-sql/blob/1bff34fc3482a78955f00640f080bd7ec7852828/src/sqlite-file.js#L230
[absurder]: https://github.com/npiesco/absurder-sql/blob/1113358cc4c69fc980ceb1334fb3e9330c330dd1/src/vfs/indexeddb_vfs.rs#L535
