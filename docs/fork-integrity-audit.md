# Fork integrity verification — bounded architecture audit

## Decision — integrity verificationをv0.4.4にするか

**Recommendation: NO — keep current verification and proceed to v0.5.**
**Confidence: HIGH**（現契約のままverify-once/cacheへ置換できない判断）。
個別の最適化効果の確信度はLOWで、未測定。ここではv0.5作業も開始しない。

最も強い根拠は次の5点。

1. prepared filesは0700 directory/0600 filesにあるが、Path公開・明示的保存先・
   Pythonの再openがある。所有権は削除責任であり、内容の不変性ではない。
2. MAP_PRIVATEと子専用MemFSは通常の子書き込みを隔離する。しかし外部の同一ユーザー、
   ファイル復元、手動操作、誤ったcleanupは元ファイルを変更・置換・切り詰められる。
3. 毎Forkの全内容hashは、同じサイズの破損も現manifestとの不一致として検出する。
   inode/size/mtimeやhandleのgenerationには、全内容が変わっていないという保証がない。
4. 61–126ms/Forkの観測費用は実在する。ただし強い不変backingにはAPI、FD所有、
   import/export、Python別process、両OSの寿命管理をまとめて変更する必要がある。
5. 重いfixtureは既にN2からFork有利。軽いfixtureは全hash費用を差し引いてもN16でFresh有利。
   安全性・変更規模・v0.5より前に行う理由の3点が、独立releaseを支持していない。

**Current safety contract:** 安定した入力treeについて、Fork開始時に形式・guest互換性・
全path/kind/size/contentが、その時点のmanifestと一致することを確かめ、異常時はready前に拒否する。
これは公開パスに対する毎回の整合性検査であり、認証、原本の不変identity、
同時外部書き換えに対するatomic snapshot、稼働中の継続検証ではない。

**Smallest safe alternative:** 現行のGoの公開pathモデルで、同等の内容検出を維持して
hashを省く小さい代替は見つからない。現行full verificationを維持する。
強いowned immutable backingへの転換は可能性があるが、別のstorage/lifecycle設計になる。
Pythonの重複検証委譲やfull-hashのI/O tuningは、別の限定候補として残る（付録D）。

**Expected benefit:** 既存のGo測定はready 115/125/202ms、検証61/70/126ms。
検証だけを仮にゼロ費用にした算術的残差は54/55/76ms。これは実装予測や保証ではない。
追加のidentity確認、初回取り込み、ページ温め喪失などにより実際の削減は小さくなり得る。
安全な実装の測定済み改善は0件。

**What we give up / risk:** 毎Forkのread/hash費用と並列時のCPU/I/O負担を当面残す。
一方、verify-onceだけに変えると、作成後の破損・変更をready前に検出する保証を失う。

**Human decision:** 現行full verificationを維持し、この理由でv0.4.4を設けない判断を
採用してよいですか？ **Yes / No**。

## Appendix A — current data path and trust boundary

監査baselineは `a23e450af19fd2086a008cc85ed35173f0103801`。
Wasmer retirement候補A `26d9050be9004940315e2add8253e31b26538316` と
調査B `2715c44df0f567930a1d6ef272a18bcffd401a29` を比較した。
Snapshot handle、stored snapshot、Python snapshot、prepared mapping、growthの5ファイルは
3 SHAで同一Git blob。Aのhostからlegacy分岐が消えても、以下の検証契約は同じ。

```text
Database.Snapshot
  → busy/transaction/destination checks; exclusive destination creation
  → stop accepting; drain sessions; guest workers join; l4m_close
  → guest snapshot_copy: private MemFS /mariadb → /snapshot-out/data
  → exportTransfer: MemFS → host transfer directory
  → Publish: source inventory+SHA256 → exclusive file copy
             → destination inventory+SHA256 → exact comparison
             → manifest.pending → rename manifest.json
  → Go Validate (Python: Snapshot.open/validate) → return path handle

Go Snapshot.Fork: RLock + closed check → start(path)
  → host ValidateTimed(path, compiled GuestSHA256)
  → fresh guest instance → MapPreparedFiles(path/data)
  → open each file read-only → fstat → writable MAP_PRIVATE → close FD
  → independent MemFS/linear memory/threads → ready → child SQL
  → child Close: cooperative worker join → descriptors close → munmap

Snapshot.Close: block new Forks; wait admitted Go startups
  → remove owned temp root (explicit destination remains)
  → existing children continue from their mapping references
```

Publishの2回のinventoryはコピー成功の照合、作成後Validateは公開結果の再確認、
Fork Validateは時間を隔てた再利用時の整合性確認であり、同じ目的の重複とは限らない。
GoのFork→ready経路はstored.ValidateTimed 1回。2workerで全regular fileをhashし、
全workerの完了後にmanifestと比較する。単に2回同じtreeをhashする経路ではない。

Pythonでは `Snapshot.fork → Database(snapshot=...) → Snapshot.open(path)` が
Python inventory/hashを行い、起動するGo hostもValidateTimedを行う。
Pythonの保存済み `self.manifest` はhostへ渡す信頼tokenではない。
`--snapshot path` はpathの文字列をprocess間で渡すだけで、FDや検証済みgenerationを渡さない。

**保証の上限:** manifestは同じ書き込み可能なtree内にあり、署名/MACやhandle内の
作成時manifest digestで固定されていない。データとmanifestを一緒に整合的に置換すれば、
同guestの別の有効なsnapshotも受理できる。別guestならWASM identityで拒否する。
validationのLstat/WalkDir、hash用open、mapping用WalkDir/openは別操作で、
verified FDをmappingへ引き渡していない。従って検査中・検査後の外部変更を原子的に防がない。
hash後のlive backing変更も監視しない。既知の限界は検査削除の根拠にならない。

## Appendix B — check → invariant → failure table

「起こり得る」は安定した通常SQL操作だけでなく、公開された保存ファイルの操作・再利用を含む。
不正な同時外部書き換えは一般に完全防御対象とは扱わず、raceを明記する。

| Check / 実施箇所 | 守るinvariant | 現実的な失敗源 | 現API/所有関係で可能か | 検出しない場合 |
|---|---|---|---|---|
| Go handle RLock/closed/path、Closeのwrite lock | handle有効、同handleの開始済みForkが読む間tempを削除しない | Fork/Close並行、二重Close | Goでsupported concurrency、lockが制御 | startup中の消失・不正利用。hashだけでは防げない |
| rootとmanifestのLstat/type | rootは実directory、manifestはregular file | cleanup、linkへの置換、誤ったpath | 外部操作・Python openで可能 | 別tree読込、special fileへのアクセス、未完成snapshotの利用 |
| root children数/データtree照合 | dataとmanifestだけの完成形 | partial copy、余計なfile、古いstaging | 可能。Goは2 entriesを確認し、data walkとmanifest openで名前を拘束 | 未完成・想定外treeを受理 |
| JSON、format/version/source_storage | 認識可能なcold-memory形式 | 手編集、古い/異なる形式、破損 | 永続/輸入pathで可能 | 誤ったrestore前提。JSON parseだけではSQL整合性を証明しない |
| manifest.WASM == compiled GuestSHA256 | guest-compatibleなprepared state | guest更新、別buildからの持込 | 可能。Pythonはhex形式確認、hostがexact比較 | 非互換データを起動。package version/source commit全部の認証ではない |
| inventory WalkDir + type判定 | treeはdirectory/regularのみ、path集合が一致 | symlink、FIFO等、追加/欠落/rename | 同UID/保存先操作で可能。hard linkはregularとして許可 | 意図しない入力、欠落。親path成分を含めたrace-free no-followではない |
| 各entryのsize比較 | manifestが記録した論理長 | truncate、未完copy、追記 | 同UIDの書込み・復元で可能 | 短い/長いDB file。mapping後のtruncateはこの検査では防げない |
| 各fileのSHA256全量比較 | 同じ長さでも現在のbytesがmanifestに一致 | accidental overwrite、silent corruption、古いfileだけの混入、host書込bug | 可能。通常child writesは構造的に除外 | 間違ったfixture、後段DB破損・query誤動作。metadataでは置換不可 |
| inventory全体DeepEqual | 全path/kind/size/hashが一括で一致 | 上記の混在、部分restore | 可能 | file単位の取り違え/不足を見逃す。原本handleのidentityは拘束しない |
| mapping時DirEntry/type、open/fstat/size、mmap error | 実際に開いた対象がregularで表現可能・mapping可能 | 検査後の消失/置換、巨大size、resource failure | 可能 | setup failure/不正mapping。内容hashの代わりではない |
| guest SnapshotVersion確認 | guestがrestore protocolを実装 | executable/guest不整合、開発入力 | generated identityで絞られるが防御は残る | protocol不整合をreadyとして渡す |
| child MAP_PRIVATE、独立MemFS、growth detach | child SQL/write/truncate/renameでbase/siblingを変更しない | 通常のchild SQL・file growth | 通常操作は構造的に隔離。実装bugは別 | base/sibling汚染。hashは将来のFork前検出で、稼働中の防止ではない |
| guest/worker join後のdescriptor close/munmap | bytesを使うworkerよりmappingが長生き | cleanup順序bug、失敗経路 | lifecycle実装の責任 | use-after-unmap。毎Fork hashはこの保証を提供しない |
| 作成時exclusive Mkdir/O_EXCL、copy前後hash、manifest rename、失敗cleanup | 所有する新destinationに完成形を公開 | copy/write failure、既存destination、途中終了 | 実際の失敗境界 | 部分snapshot、既存データ上書き。manifestはcommit markerでありfsyncによるcrash durability保証ではない |

根拠は付録FのS1–S8。破損testは内容を変更して戻す・linkを追加して消す・WASMを
変えるという明示的な公開file操作を使う。hash検査はこれを拒否する現在の動作そのもの。
同一guestの完全に整合した別snapshotへの置換、元から論理的に壊れたDBをproducerが
正しくhashして公開したケース、稼働中の外部変更は、上の内容一致だけでは検出を保証しない。

## Appendix C — ownership and mutability

**A. 既に構造で守るもの**

- Go temporary Snapshotは削除対象rootを所有する。明示Destinationは保持し、上書き作成を拒否。
  同handleの複数Fork startupは並行可能で、Closeが起動完了まで待つ。
- 各childは独立したMemFS nodes/FD offsets/private mappingsを持つ。
  書込みはnode.dataへのcopy、truncateはslice長変更/zero-fill、capacity超過はmake+copy。
  backing FDへのwrite/ftruncateやMAP_SHAREDへ切り替えるfallbackはない。
  Rename/RemoveもMemFS tree内で完結。childをSnapshotしても新しい出力先を作る。
- OSのmapping参照はopen FDのclose後も残る。Snapshot.Closeによるunlinkは既存childの
  mapping参照を解除しない。Go integrationにはtemplate削除後も両childがSQLを続ける確認がある。
  child側はjoin後にmappingを解除する。[POSIX mmap](https://pubs.opengroup.org/onlinepubs/9799919799/functions/mmap.html)。

**B. 現在は再検査に依存するもの**

- Path/`saved.path`は公開。temporaryも0600/0700であり、同UIDに対するread-only/sealではない。
  パスを知った呼出元は通常のfilesystem APIで書込・truncate・replace・削除できる。
  SQL経路にbase編集APIがないことと、baseが変更不能なことは異なる。
- Go Snapshotにはpath/options/closed/mutexがあるだけで、open backing FD、作成時manifest、
  inode集合、generation、original snapshot IDはない。Goにpublic Open(path)はないが、
  PythonにはOpen/constructor/Database(snapshot=path)、hostには--snapshotがある。
- 複数Python handles/processesは同じtreeを参照できる。reopenしたhandleに元のtemporary
  ownershipやlockは共有されない。Python SnapshotにGo相当のFork/Close lockはない。
  ownerのCloseと別handle/processのstartup競合をhashが解決するわけではない。
- MAP_PRIVATEはchildのmapping経由の書込みからbaseを守る。外部からbaseへ行う変更の
  可視性や、mapping後のfile size変更の結果はportableな安定snapshot保証ではない。
  readonly FDも他のwriterによるinode変更を止めない。
  [POSIX mmapの規定](https://pubs.opengroup.org/onlinepubs/9799919799/functions/mmap.html)。
- 保存/コピー/別process再openはpath+manifestの交換。製品wheelのhost hash、release provenance、
  元guestのsource hashはユーザーprepared treeの所有・不変性を与えない。
  再open/importでは信頼を改めて構築する必要がある。

snapshot_copy先のhashはcopy後の状態を測るため、guestがコピーする以前の論理正当性まで
証明しない。data/manifest両方が整合的に変わった場合の改ざん検出も提供しない。
現在の保証は、通常安定した入力に対する破損/不整合検出として有用だが、同UID攻撃者への
安全境界ではない。新しい設計でその保証を暗黙に変更しないことが重要。

## Appendix D — bounded alternatives

| 案 | そのまま同等保証か | 減る費用 / 残る費用 | 必要な変更・限界 | 判定 |
|---|---|---|---|---|
| A. 毎Fork full verification | Yes、現baseline | O(total bytes) read/hash、O(files) inventory。既に2worker | 現行の外部変更検出とimportを維持。TOCTOUは残る | 維持 |
| B. 作成時に1回verify | No | 再Forkのbytes scanを省ける | 作成後の同size corruption、truncate、置換、stale filesを検出しない。importは別途full検証必須 | 現契約では不可 |
| C. strong owned immutable backing | 条件を満たせば可能、未立証 | 取り込み時O(bytes)、以降cheap metadata/handle確認 | 実体をpathから切離し、writerを排除し、verified identityとmappingを結び、import/export/APIとFD寿命を設計 | storage設計として延期 |
| D. metadata + selective content | No、一般の公開fileで全内容検出を代替できない | O(files)＋選択bytes | inode/sizeは同size書込を見逃す。mtime/ctimeはcontent checksumでなく、silent corruption・timestamp精度・競合を覆えない。manifest hashだけではdataは拘束できない | full検証の補助のみ |
| E. cached verification + identity/generation | 現在はNo | cache hitならbytes scan省略 | 全writerが必ずgenerationを更新する構造が必要。今の外部path writerは更新しない。FDはobjectをpinするがbytesを凍結しない | 信頼できるgenerationが成立すればC、なければB/D |

**Cを本当の主張にするための最小要件**

1. 信頼するmanifest/guest identityと、その検証対象の実体をhandleに保持する。
   同じpath名を再openする方式から、検証済みの同じbackingをmapする方式へ変更する。
2. 内容・長さを変更する全alias/writerを排除する。chmod、隠したpath、readonly FD、
   directory lockだけでは同UIDの既存writerや外部変更を禁止できない。
   作成から公開までwriterが残らないことも保証する。
3. public Path/明示Destination/importと、内部immutable representationの関係を決める。
   外部pathを独立exportとして扱うなら、変更後にForkが何を見るかというAPI意味が変わる。
   disk corruption検出を何が担うかも明示する。不変性だけで媒体破損が不可能にはならない。
4. child startup・失敗・Snapshot.Close・child Closeとresource所有を結び付ける。
   Go同processだけでなくPythonの新host processへのhandle受け渡しを設計する。
5. macOS/Ubuntu両方で同じ保証を成立させる。Linux memfdにはwrite/grow/shrinkを禁止する
   sealsがあるが、現行の通常disk directoryにそのまま付くportable機能ではない。
   FD受渡し・作成時コピーとmacOS側の代替は未設計。
   [Linux file seals](https://www.man7.org/linux/man-pages/man2/F_GET_SEALS.2const.html)。

これはForkの数行のfast pathではない。匿名/privateなmemoryへ一度取り込む案も、
childごとのコピー・CoW共有方法・メモリ保持・永続化を評価する必要がある。
内容一致の契約を満たす実体を新たに作れば、毎回hashすること自体は数学的な必須条件ではない。
ただし現在のstorageでは、その実体の不変性を安価に証明するtokenがない。

**小さい候補を見落とさないための確認**

- Pythonのfull content検証をGo hostへ委譲する案なら、hostの全hashは残せる。
  ready時のcontent gateは維持し得るが、現在のValueError/HostError、起動前失敗、
  Snapshot.validate単独APIを維持する調整が必要。Python側の時間内訳は今回未測定。
  これはGoの61–126msを削減する案ではなく、今回のrelease根拠にならない。
- 全bytesを読むままbufferingやworker配分を調整する案は、ownership変更よりbounded。
  Snapshot profileのread syscall費用は調査の手掛かりだが、Forkでのbuffer/worker比較はない。
  profileの大きい割合をそのまま改善可能率にしない。実装・microbenchmarkは今回行わない。
- import時だけ検証、定期的scrub、失敗時だけ再検証、samplingは、後のForkまでに起きた
  corruptionの即時検出を遅らせたり見逃す。silent successを後から回復検査できるとは限らない。

## Appendix E — value, crossover and release criteria

既存single-child stage evidence（macOS arm64、small sample）の再計算。
server initの内訳はnestedなので、35ms＋plugin12ms＋recovery7msとは加算しない。

| Payload / actual prepared MiB | Fork ready実測 ms | 検証実測 ms | mapping / linear ms | guest enter→ready ms | 検証ゼロ時の算術残差 ms |
|---|---:|---:|---:|---:|---:|
| minimal / 138.08 | 115.10 | 61.18 | 0.94 / 1.39 | 33.65 | 53.92 |
| 10 / 157.02 | 125.22 | 70.19 | 0.87 / 1.40 | 35.74 | 55.02 |
| 100 / 262.02 | 202.30 | 126.39 | 1.29 / 1.52 | 49.83 | 75.90 |

実際の代替時間は概念上 `Tnew = Told − V + cheap_checks + shifted_costs`。
shifted_costsにはhashで温まらなくなったOS cacheへのpage access、immutable取り込み/コピー、
追加resource管理がある。初回取り込みはsuite準備費用へ移る。
53–62%は観測された段階の割合で、保証された短縮率ではない。
仮にその段階が丸ごと消え他が不変なら、latency約53–62%削減、速度比約2.1–2.7倍だが、
これは到達を示した測定ではない。新設計の現実的な改善範囲は未確定。
prepared bytesが増えるほど検証費用は増えるが、3サイズだけで普遍的な傾きを断定しない。

**Suiteへの影響を上限でchallengeする。** 既存の順次suiteから、各Forkに同サイズの
single-child検証時間Vが掛かると仮定し、`Fork suite − N×V` を計算した反実仮想。
別cellからの外挿であり、新しい測定や将来の保証ではない。Snapshot費用は据え置く。

| Fixture / N | Fresh実測 s | Fork実測 s | 検証ゼロ外挿 s | 含意 |
|---|---:|---:|---:|---|
| minimal / 16 | 1.196 | 2.476 | 1.498 | 最大に差引いてもN16ではFreshが有利 |
| 10MiB / 2 | 1.275 | 1.356 | 1.215 | N2の僅差は反転し得る。余裕約60msで追加設計費用/測定noiseに敏感 |
| 10MiB / 16 | 10.271 | 3.755 | 2.632 | 最大約1.12s（Fork suiteの30%）は可視的だが、既にFork有利 |
| 100MiB / 1 | 5.815 | 6.691 | 6.565 | N1は依然Fresh有利 |
| 100MiB / 2 | 11.495 | 7.193 | 6.940 | N2からFork有利という選択は変わらない |
| 100MiB / 16 | 96.036 | 14.274 | 12.252 | 最大約2.02s（Fork suiteの14%）改善余地。準備再利用の利益は既に大きい |

現実のmigration/fixtureはMiBだけで決まらず、SQL準備時間・test内容・繰返し数で変わる。
従ってmoderate workloadの境界を動かす可能性はあるが、幅広い現実workloadで
Fresh/Fork選択が変わる証拠はない。COUNTの反復約338/357msはこの検証を省いても残る。
並列Forkのread/hash競合削減も可能性はあるが、single-childのN倍で並列wall短縮を推定しない。

| v0.4.4条件 | 評価 |
|---|---|
| 1. user-visibleな費用 | Yes（61–126ms/Fork、suite上限約1–2s）。ただし実workload一般化は限定 |
| 2. 相当部分がmariamem制御 | Yes（検証呼出し・I/O・表現・所有契約） |
| 3. 同等integrity保証を維持 | B/D/EではNo。Cは設計・両OS検証前。full-hash tuningは効果未検証 |
| 4. boundedで理解可能 | 現APIのcheap cacheは理解可能でも安全でない。安全なCは複数境界に拡大 |
| 5. storage/lifetime複雑性を増やさない | Cについて未達。Go/Python/import/export/Closeまで影響 |
| 6. v0.5前が望ましい | 根拠なし。guest更新がこのhostコードを必ず変更するとは主張しないが、阻害依存もない |

全条件を支持できないためNO。今のcorruption検出は再現性と異常入力の早期切り分けに価値がある。
「重いfixtureに比べれば常に無視できる」も言い過ぎで、moderate suiteの費用は記録する。
将来Cを選ぶなら所有/API契約を先にhuman decisionへ出す。v0.5の安定guest移行による
新しい準備データ/起動費用のbaselineで再評価できるが、今回その作業を開始しない。

## Appendix F — exact references and reproduction

source permalinkは特記なければmain baseline。S2/S3/S5/S6はretirement候補でも同一blob。

- S1: [public Go ownership/Fork/Close](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/snapshot.go#L15)、
  [retirement host: validation before mapping](https://github.com/masahitojp/mariamem/blob/26d9050be9004940315e2add8253e31b26538316/internal/host/server.go#L55)。
- S2: [manifest, inventory and validation](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/snapshot/snapshot.go#L19)、
  [Publish](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/snapshot/snapshot.go#L216)。
- S3: [Python Snapshot](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/python/mariamem/snapshot.py#L35)、
  [retirement Python revalidation/spawn](https://github.com/masahitojp/mariamem/blob/26d9050be9004940315e2add8253e31b26538316/python/mariamem/__init__.py#L61)。
- S4: [guest shutdown/export](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/guest/resident.inc#L224)、
  [cold copy](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/guest/snapshot_fs.inc#L7)、
  [host exportTransfer](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/main.go#L450)。
- S5: [mapping and munmap](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/code/base/prepared_files.go#L16)、
  [worker join/lifetime](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/runtime_instance.go#L20)。
- S6: [write/truncate](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/code/base/base.go#L12011)、
  [growth detach](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/code/base/memfs_growth.go#L6)。
- S7: [private-view tests](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/code/base/prepared_files_test.go#L10)、
  [growth tests](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/internal/generatedgo/code/base/prepared_growth_test.go#L11)、
  [Go Fork/Close tests](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/mariamem_test.go#L365)。
- S8: [corruption/symlink/build rejection cases](https://github.com/masahitojp/mariamem/blob/26d9050be9004940315e2add8253e31b26538316/tests/snapshots.py)、
  [unlink then child queries](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/tests/gointegration/lifecycle_test.go#L209)、
  [Python persistent reopen](https://github.com/masahitojp/mariamem/blob/a23e450af19fd2086a008cc85ed35173f0103801/tests/consumer/test_database.py#L49)。
- E1: [stage/crossover report](https://github.com/masahitojp/mariamem/blob/2715c44df0f567930a1d6ef272a18bcffd401a29/benchmarks/v043-snapshot-characterization.md)、
  [machine-readable values](https://github.com/masahitojp/mariamem/blob/2715c44df0f567930a1d6ef272a18bcffd401a29/benchmarks/v043-snapshot-characterization-values.json)。
- E2: [first-use attribution and profiles](https://github.com/masahitojp/mariamem/blob/2715c44df0f567930a1d6ef272a18bcffd401a29/benchmarks/v043-first-use-attribution.md)。

[監査入力identity・算術結果](fork-integrity-audit-evidence.json) にexact SHAs、blob IDs、
入力SHA256、再利用cell名、算術式を保存する。元の巨大source/build/cacheを複製しない。

```sh
git show a23e450af19fd2086a008cc85ed35173f0103801:snapshot.go
git show 26d9050be9004940315e2add8253e31b26538316:internal/host/server.go
git show 2715c44df0f567930a1d6ef272a18bcffd401a29:benchmarks/v043-snapshot-characterization-values.json
git diff a23e450af19fd2086a008cc85ed35173f0103801 26d9050be9004940315e2add8253e31b26538316 -- snapshot.go internal/snapshot/snapshot.go python/mariamem/snapshot.py internal/generatedgo/code/base/prepared_files.go internal/generatedgo/code/base/memfs_growth.go
```

変更は本reportと小さいJSONだけ。確認対象はコード根拠・リンク・数値再計算・diff/status。
runtime変更、instrumentation追加、benchmark、runtime/ORM/release acceptanceは実行しない。
終了時はreport/evidenceをcommitして保持し、監査worktreeを削除する。既存のreview証拠は保持する。

INTEGRITY VERIFICATION DECISION READY
