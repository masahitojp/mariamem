# Snapshot：保証を所有権で支え、内容の読み直しを不要にできるか

2026-10-17。設計検討・静的コード確認。ランタイム変更、試作、追加計測は行っていない。

## Spike前のHuman Review — 5条件の具体化

**状態：Humanの条件付き承認後、実装前の再レビュー待ち。専用branch/worktreeの準備のみ。**
この節が後述§7・§8を具体化する。以下は実施結果ではなく、確認してから着手する条件である。
承認対象はguest未接続の部品spike。製品契約、既存oracle、本番経路の変更は含めない。

### 1. strict oracleの棲み先と新経路の拒否

二層に分ける。unit testを残しただけで新経路を検証済みとは扱わない。

| 層 | 配置・責任 | 必要な結果 |
| --- | --- | --- |
| 所有層の内容oracle | 現行`heap_snapshot_test.go`の`TestHeapTargetCorruptionOracle`と`internal/snapshot/heap_test.go`の拒否を保持。新モデルでは所有層unit testが独立byteモデル/期待digestと内容を比較する | 内容・末尾・ゼロ・世代の一致。意図的に壊した内容をstrict検査が拒否する |
| 新しい受け渡し経路 | spike内の`freeze → Capture → acquire`を通す差し替え拒否oracle | 別root、未固定root、別capture、別guest、放棄済み/失敗済み候補を拒否し、使用可能な所有物を返さない |

新モデルの期待digestはtest側が保持し、通常取得へ隠れてhashを戻さない。
後に本番へ接続する場合は、同じ拒否oracleを実際のCapture/Owned配線へ移す必要がある。
unit testだけのPASSを本番配線のPASSとしない。

`TestHeapTargetCorruptionOracle`はdigest無しの本番経路では毎回呼ぶ検証ではなく、
所有層の内容保持を確かめるテストに位置づく。現行strict経路はこのspikeで変更しない。
新経路に対し同じrootの内部bytesだけを直接壊す注入も別に記録する。
それを所有権だけで検出できない結果は**検出能力の差**であり、差し替え拒否PASSで相殺しない。
この差を許容する製品判断は未承認。既存failureをsuccessへ書き換えない。

### 2. 読み直しゼロは経路別に判定する

計測区間は固定・Capture受け渡し・取得を分け、準備write、子write、内容oracleのreadを
混ぜない。read bytes、copy bytes、hash bytes、metadata訪問数を別々に記録する。
counterは実際のpayloadアクセス箇所に接続し、既知量のread/copy/hashで非ゼロになる対照も置く。
全てのpayloadアクセスがcounterを通ることをコードで確認し、未計測はゼロと報告しない。

| 経路 | 通常の固定/受け渡しで狙うこと | 除外せず別記録する費用 |
| --- | --- | --- |
| dirty heap | payload read/copy/hash = 0 | 準備writeでの入力copy、metadata固定 |
| inherited heap | payload read/copy/hash = 0 | 子が最初に変更するときのCoW copy、descriptor処理 |
| implicit zero | ゼロの全領域展開・走査・hash = 0 | 論理長と末尾/穴のmetadata確認。実readでは正しいゼロを返す |
| mapped base | **全経路ゼロを要求しない**。mapping寿命を切る移行を別判定 | source read、heap copy、必要な比較。実mmap未実行ならモデル結果と分けSKIPを記録 |
| private handoff | **ゼロ対象外**。別実体への転送/取得検証を維持 | 送信read/hash/write、受信copy/検証をそれぞれ記録 |

dirty/inherited/zeroが混在するfileも含める。mapped/handoffは部品adapterの確認と
本番OS/host経路の確認を区別する。ゼロ対象外の行を未実装のままPASSとはしない。

### 3. 利得は三つに分離する

| 独立して評価する利得 | 省く仕事 | 成立しない場合に残せるもの |
| --- | --- | --- |
| G0：確認済み実体の所有権受け渡し（以前の比較表row1） | 所有取得時の3回目の走査 | 表現変更に依存させず、小案として残す |
| G1：Snapshot専用の再構成をやめる | 元hash作成と移行後比較のためのpayload走査（pass1/2の内容処理） | G1が不成立でもG0の成立性・費用を別報告 |
| G2：内容表現を統一する | base/zero等を取得時に別表現へ変換する仕事、readerの分岐/重複 | G2が不成立でも、既存表現を固定して使うG1が成立するか区別 |

pass1には固定・metadata構築も含まれるため、「pass1/2の時間が丸ごと消える」とはしない。
G2はゼロの意味を消すことではない。mappedの寿命切断も表現統一だけでは消えない。
部品spikeでは対応する経路/counterを分け、成立した取り分を全体案の成否で捨てない。
未実装の比較案について速度利益を実測済みとは報告しない。

### 4. 生成境界の変更と費用を設計出力にする

部品spikeは隔離packageに置き、本番生成物を変更しない。その成果物に、本番接続時の
変更対象と「変更が必要になる条件」を下表の粒度で残す。

| 対象 | 本番接続時の作業・費用 |
| --- | --- |
| `HANDWRITTEN_FILES` | MemFS/所有層adapter/testの追加・移動・削除を列挙し、`handwritten_owner`とclean再生成時の取り込みを確認。通常`internal/prepared`側のfileは生成treeとの所属を区別 |
| `runtime_memfs.py` | relative open/truncate、mapped install等の置換先を新APIと整合。各置換のpreimage/count検査と対応fixtureを確認 |
| pinned preimageの再ピン留め | **現在のhashは変更前のconverter出力断片を固定している。** 手書き実装だけ変える場合は再ピン留めしない。実際に断片が変わる場合に限り、旧新入力と出所・再生成結果を照合して更新する |
| `release/generated-go-inputs.json` | 現在はconverter側のcandidate source inventory。raw入力が変われば正式生成で更新。手書きfile追加だけなら、その理由でcandidate hashを書き換えない。更新要否を明記 |
| 出力inventory/provenanceと独立再生成 | 変換後出力・手書きownerの分類を保持し、正式経路で独立再生成して一致を確認。owner追加をraw入力inventoryだけで済ませない |

したがって「部品が通ったら数行の接続だけ」とは見積もらない。owner/API配線、生成変換、
inventory検証、独立再生成、本番経路oracleの各作業を別に残す。
このspikeでは再生成を実施したことにせず、本番接続を承認する際の範囲として提示する。

### 5. digest無しの表現とAPI/manifest設計

現行`NewHeapFile`はSHA-256形式のdigestを必須にし、`Digest()`はhandoff manifestに使われる。
空文字やダミーhashを入れて通す案は採らない。

推薦する設計出力は、**digest無しの内部固定rootと、digest付き転送表現を別型にする**こと。

- 通常の内部型：bytesを外へ出さない固定root、guest identity、構造、取得要求との結び付きを持つ。
  raw Heapを無検査でこの型へ変換する入口は作らない。
- Capture/Owned/復元：新型を渡す内部APIの変更点を列挙する。Go/Pythonの公開Snapshot/Fork APIは維持する案。
- 転送表現：handoff時に内容を読み、file digestを作る。受信側は既存同等の内容/identity検証を行う。
  既存manifest形式・digest必須を維持できるかを設計し、変更するならversion/受信側対応を明記する。
- digestを作る時点がSnapshot作成時からhandoff時へ移るため、作成からexportまでの
  内容破壊の検出能力は同じとは言えない。この差と製品契約の更新案を成果物に含める。

**この5条件で部品spikeへ進むことを推薦する。** 現時点では仕様提案のレビューであり、
各oracle・counter・API案の実証はこれから。本節をHumanが確認するまで実装/実行へ進まない。

## Human Review

**判断は、通常の同一プロセス内Snapshotを「元の状態そのものを固定して所有する」方式で
部品spikeするか。私は進めることを推薦する。** 現行も子の独立性は所有権とブロックCoWで
支えている。元とSnapshotで同じ内容表現を使い、書き込み権限を閉じて同じ実体を渡せれば、
受け渡すたびの全量hashに加え、比較用hashを作るためだけの全量読み取りも不要にする余地がある。
目標は走査回数や130msではなく、利用者が準備した状態と子の独立性を維持したまま、その仕事をなくすこと。

**最も強い反論は、現在の照合が検出する「期待hash確定後の内容破壊」まで所有権だけで
検出できるわけではないこと。** 通常の書き込みや受け渡し誤りは防止・拒否の対象にできるが、
所有層の内部まで直接書き換える故障を全量照合と同じように検出することは約束しない。
現行契約の「取得時に内容を完全検証する」との対応、および既存の破損oracleとの差を明示する必要がある。
今回、契約やoracleを変更する承認は求めていない。spikeはその差を具体化する判断材料であり、
保証維持を実証済みとするものでも、本番採用の承認でもない。

## 1. 結論と確認範囲

元の問いへの設計上の答えは、**通常操作に対する内容保持・独立性は、所有権を中心に
成立させる合理的な構成がある。現在の実装からVerifyを削るだけでは成立しない。**
また、現行の実行時破損検出まで一切変えずに全量読み取りをなくせる、という結論ではない。

確認した範囲は、現行heapの生成・受け渡し・取得・Fork・Close、内容変更入口、
別binaryへのprivate handoff、既存の失敗テスト、pgmemの固定commitのClone/書き込み/Snapshot。
これは設計判断のための静的確認であり、全guestの意味論監査や新方式の実行検証ではない。
新しい不具合や利用者のデータ破損を再現したものでもない。

- mariamem runtime `source_commit`: `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`。
- v0.5.1 `tag_object_sha`: `089b32e09608902f6d46e7ab9527d09922dcf065`。
  `scripts/git_identity.py inspect v0.5.1`でtag objectとpeeled commitを区別した。
- 文書の基点: `ebadbf92de0fe4ff50fcbfc830e77c520657d85d`。runtimeは上記releaseと同じ。
- pgmem `source_commit`: `a61005d37d01e6671f814fe8ca828222e8147df4`。
  Git commit APIで確認。現時点の最新版という意味ではない。
- 入力ファイルのhash・symbol位置・確認方法は[入力記録](snapshot-ownership-evidence/inputs.json)。

前の[two-pass提案](snapshot-two-pass-design.md)は比較候補として残すが、今回の主案ではない。
150ms/480msおよび会話中の130msという数値は、新設計の終了条件にしない。

## 2. いま、何を検証しているか

| 現行処理 | 実際の責任 | 検出できるもの | それだけでは分からないもの |
| --- | --- | --- | --- |
| `freezeHeap`の元内容読み取り/hash | 元の論理内容について期待digestを作る。固定とdescriptor移行も行う | 読み取りのerror | これは照合ではない。SQLの正しさ、hash前に既に間違っていた内容 |
| `freezeHeap`末尾の`Heap.Verify` | 新しいdescriptorで読んだ内容と元digestを比較 | コピー・ブロック選択・有効末尾等の誤りがbyte差になった場合 | 同じ誤りで元の読み取りと移行先の双方が一致した場合、将来の書き換え |
| `OwnHeap`の`Heap.Verify` | 所有取得直前の同じHeapをもう一度比較 | 前回確認後の変更、raw Heapから渡された不正な内容/hashの組 | その後も変更できないこと、同じ内容を持つ別実体への差し替え |
| `Heap.Check` / constructor | guest identity、名前/親子構造、file layout/hash形式 | identity不一致、不正な構造など | DBに必要な全fileが揃うことを、独立した元inventoryと比較しているわけではない |

`Verify`は保持中のfile一覧を走査する。独立した元inventoryは別に持たないため、
例えば有効な構造を保ってfileを一覧から落とした場合、残ったfileのhashが一致しても欠落を
それだけでは検出しない。今回の既存資料にある「完全検証」を、任意の誤りを検出する意味に広げない。
この点はコード上の検出範囲の説明であり、通常利用で欠落を確認した報告ではない。

hash照合には意味がある。ただし役割は**時点間のbyte一致を確認すること**であり、
DBの整合した停止、将来のCoW隔離、寿命の保証とは別である。
同一の変更不能な実体を継承するだけなら、その都度byte一致を確認する理由は薄くなる。

根拠：[freeze][freeze]、[Heap/Block/Check/Verify][heap]、[OwnHeap][own]。

## 3. 現在の所有と変換を追った結果

| 経路 | 現在の実体・権限 | 読み直しをなくす際の意味 |
| --- | --- | --- |
| root/worker終了 → capture | `executeGuest`は全workerを待って戻り、その後freeze。Capture結果は実行完了後に取得 | 書き手停止の境界は既にある。エラー時の非公開・回収を引き継ぐ |
| dirty block → Snapshot | `TakeBlock`で同じ`[]byte`を渡す。元mapをnilにし、元storageをsealedにする | byteコピーはないが、書き換え可能なaliasを捨てる責任がcallerに残る |
| inherited block → Snapshot | descriptorを再利用し、`Limit`で有効末尾を狭める | 共有内容は変更しない。末尾の組み直しが正しい必要がある |
| implicit zero → Snapshot | 元readerは未配置領域をゼロとして読む。移行先ではzero Blockに表す | 同じ論理内容を別の表現で再構築している |
| mapped `base` → Snapshot | 必要な内容をheap blockへコピー。元mappingはinstance終了で解放 | **同じheapの移譲と同扱いにできない。** コピーと寿命切断の検証を残す別入口が必要 |
| Heap → Capture → OwnHeap | 同じ`*Heap`を渡す。`TakeResult`がtransport参照を外す | ここでは内容を再構築しない。再検証の重複が最も明確 |
| Owned → Fork | identity/構造確認後、descriptorを子へコピー。全量hashなし | 既に所有権を信頼している先例 |
| 子の書き込み | 子専用dirty blockへコピーしてから変更 | 親/兄弟の隔離はこの仕組みが支える。hashを毎回しても代替できない |
| Close | 受付を閉じ参照を外す。開始済み子は自分のdescriptorを保持 | 新方式でも元FS全体やguest moduleを不要に保持しないこと |

主な内容変更入口も照合した：

- `Write`/`WriteAt`/append → `blockStorage.writeAt`。書き込み入力は内部blockへcopyする。
- `Truncate`、絶対/相対openの`O_TRUNC`、拡張する`Allocate` → `resize`。
  `writeAt`/`resize`はsealedを拒否する。変更しないAllocateやゼロ長writeが成功する場合まで
  「全メソッドが必ずエラー」とは表現しない。
- `WriteFile`は新nodeへ書いてpathを置換する。rename/unlink/mkdir等は元treeを変えるが、
  現行Heapはmetadataをコピー済みなので基準には戻らない。
  新方式で元treeそのものを共有するなら、file bytesのsealだけでは足りない。
- 現行Blockは読む際にcallerのbufferへcopyし、bytesを返すAPIは持たない。
  ただし`TakeBlock([]byte)`はcallerにaliasが残せるため、「型が所有権を保証する」とは言えない。

これらの通常入口はFS lockを使う。今回は変更入口と参照の静的な照合までで、
新しい型の排他性・全alias遮断を実証したものではない。
根拠：[storage][storage]、[MemFS][memfs]、[relative][relative]、[runtime][runtime]、
[capture][heap]、[Acquire/Close][owned]、[mapped復元][mapped]。

## 4. pgmemから借りるのは何か

固定commitの[Snapshot][pg-snapshot]は停止後にFSをCloneし、元serverを再起動する。
[FS.Clone][pg-vfs]はmetadata treeを複製し、file dataは共有する。
`Node.own`/拡張writeは共有fileを自分のarrayへコピーしてから変更する。
通常のSnapshot/Clone経路には全file内容のhash照合がない。

借りるべき考え方は「同じ内容を共有し、変更は別の所有物に向ける」こと。
名前付きの所有権tokenだけを足すことでも、pgmemの全コードが正しいと仮定することでもない。
pgmemはfile単位、mariamemは16KiB block単位なので、mariamemがfile単位コピーへ戻る必要はない。
pgmemの元server再起動、Shutdown errorの扱い、Closeの実装もそのまま移植しない。
mariamemの元DB消費、停止失敗時の非公開、子の独立性を維持する。

同一Go host内ならこの共有を利用できる。Pythonも通常は同じroot lineageのhost内で
Snapshotと子を扱うため適用可能な設計条件を持つ。一方、別binaryへのhandoffは別の信頼境界。
pgmemの速度はこの設計の実現速度の証拠にしない。

## 5. 同じ基準で比較した設計

| 案 | 読み直しが不要になる理由 | 残る費用・代償 | 今回の評価 |
| --- | --- | --- | --- |
| 現行表現＋一度確認したHeapの所有権を渡す | 検証後の同じ実体を再利用 | 元hashと移行後比較は残る。alias封鎖は必要 | 小さな改善候補として成立性あり。ただし問いへの到達点をここに固定しない |
| **元とSnapshotで共通の内容表現を持ち、固定して所有** | 内容の再構築をなくし、変更権限を閉じた同一実体を渡す | storage所有API/表現の整理、metadata確認、従来の実行時破損検出との差 | **推薦する部品spikeの対象** |
| 更新時にblock hash等を維持する | 取得時の仕事を更新時へ移す | SQL writeへhash費用、digest更新漏れ、root構築費用。hash保持だけでは現在bytesの破壊を検出できない | 厳密な再照合の代用品とせず、今は推薦しない |
| 現行を維持 | 今の2つの比較時点を残す | 論理fileサイズに比例する全量走査 | 所有案が条件を満たせない場合の選択肢 |

### 推薦案の具体像（実装済みではない）

1. blockのbytes、論理長、有効末尾、ゼロ領域、block配置を、一つの所有層で管理する。
   通常readとSnapshot readは同じ内容表現・readerを使う。Snapshot時だけ別reader用に
   `dirty/inherited/inheritedLimit`を再解釈する構造をなくす。
2. mutableなblockを所有層の内部で確保する。通常入力は`WriteAt`等でcopyし、
   callerがraw `[]byte`を渡して所有済み実体を作れる入口と、信頼済み固定rootの入口を分ける。
   同一packageのバグやunsafeまでGoの型で排除できるとは言わない。
3. worker終了・FS lockの下で内容とmetadataを固定する。凍結後の旧writer handleも
   同じowner stateを見て変更を拒否する。型変換だけで古いaliasが消える設計にはしない。
4. 全pathと正確なfile root・size・block範囲の対応を確認してrootを確定する。
   byte読み取りと独立にmetadataを走査してよい。元と異なるinventoryやrootを
   tokenに結び直せないようにする。raw Heapを「信頼済み」と包むだけの関数は作らない。
5. Captureはこの取得要求に結び付いた固定rootを渡し、Ownedは同じrootを保持する。
   guest identity、nil/未固定/別capture/失敗済み状態は拒否する。途中失敗で公開しない。
6. Forkは独立metadataと子の変更領域を持ち、共有blockへ直接書かない。
   元FSのmutex/node/FD/moduleを保持し続けず、blockと必要なmetadataだけを保持する。
   派生世代を無制限に連結してreadや回収の費用を増やす案は避け、metadataの平坦化も比較する。

これは「全てO(1)」という案ではない。file/block metadataの走査・複製は残り得る。
取り除く対象は論理内容の全byte読み取りと、移行のためだけの内容表現変換。
canonical表現へ直す費用がwrite/Forkに移る可能性は、部品spikeで別途可視化する。

`internal/prepared`と手書きMemFS/storageを中心に責任をまとめる構成が候補。
host/Capture/Owned/復元はその型を受け渡す。生成関数を手編集しない。
手書きownerの移動や参照変更に応じ、`scripts/runtime_memfs.py`と生成inventory/provenanceの
正式経路を後の実装で確認する。guestの停止手順、SQL API、接続数、OS backingの再設計は含めない。

### private handoffを混ぜない

現行[Handoff][handoff]は保存済みfile digestをmanifestに載せて内容を出力し、受信側がcopy/検証する。
通常経路がdigestを作らなくなるなら、handoff時に内容を読みhashを作る責任が必要になる。
これで転送先との比較は維持できるが、「Snapshot作成時からexport前までに内容が変わったか」の
照合まで同じになるわけではない。その差は明記する。
mapped復元からの再Snapshotも、mapping寿命を越えて共有できないため、検証付きのheap移行を残す。
これらを所有権だけで省略する結論へ広げない。受信側のidentity/内容拒否oracleは保持する。

## 6. 維持する保証と、実行時検出の差

| 性質・失敗 | 推薦案で担うもの | 判定 |
| --- | --- | --- |
| 停止時点の内容をそのまま使う | 共通reader/同一root、metadata対応の確認、停止完了 | 維持を目指す。設計条件を列挙済み、試作未検証 |
| 子・兄弟・世代の独立性 | 共有block不変、子専用write、truncate/regrow規則 | 維持必須。hashで代替できない |
| 別guest、未完成、別captureの取り違え | 実体に結び付いたidentity/state/取得要求の確認 | 全量読み取りなしで拒否できる設計対象 |
| block順序・末尾・file集合の取り違え | Snapshot専用変換を廃止し、metadata同一性を確認 | 元表現の誤りまで自動的に検出するわけではない |
| 旧writer経由の変更 | owner stateが変更を拒否。metadataも独立/固定 | writerの全入口を対象にした実証が必要 |
| callerのraw aliasによる変更 | 所有層がbytesを確保し、raw入力から固定rootを作らせない | API経由の作成経路を閉じる。既存`TakeBlock`を包むだけでは不可 |
| 正しいhashを保持したまま所有層内部のbytesを直接壊す | 所有権は検出装置ではない | **現行の取得前照合と同じ検出能力はない** |
| SQL実装自体の誤り、hash以前からの誤った状態 | DB/ランタイムの検証 | 現行hashも解決しない。今回の調査を全guest監査へ広げない |

bit反転などを、内容を観測せずmetadataだけで完全検出することはできない。
正常状態とbytesだけが異なる状態が同じmetadataを持てば、そのmetadata検査は同じ結果になる。
これは「所有方式は危険」という結論ではなく、**防止する性質と再照合で検出する性質の違い**。
現行もhash以前の破壊や取得後の任意破壊を網羅的に検出するものではない。

現行の[製品契約](../decisions/snapshot-product-contract.md)は取得時の内容完全検証を明記する。
所有方式の同一実体保証をその実現方法として採るか、取得前の実行時hash照合まで必須にするかを
無言で決めない。契約文の更新案と失敗注入結果を後の採用レビューへ同時に出す。
ここでは契約本文を変更しない。

## 7. 既存oracleをどう扱うか

| 現行test | 何を壊す/確認するか | 次のspikeで必要な対応 |
| --- | --- | --- |
| `TestHeapTargetCorruptionOracle` | 元digestを残して別bytesのHeapへ差し替え | 現行strict経路の拒否を残す。新経路では別root/未固定入力への差し替え拒否を実証。内部bytesの直接破壊とは区別 |
| `TestHeapOwnerRejectsCorruptionAndWrongIdentity` | TakeBlockに渡したsliceを後から変更、異なるguest | raw入力のstrict取得は維持。新入口にはそのsliceを所有済みとして渡せないこと、identity拒否を実証 |
| `TestHeapFreezeFailureAndIdentityOracle` | 固定途中失敗とidentity違い | 新しい取得経路でも失敗→公開なし・参照回収を確認 |
| `TestHeapOwnershipAcrossGenerations` | 旧FD書き込み、世代派生、末尾ゼロ、親の不変 | 新しい本番候補経路で同じ性質を検証。古いwrapperだけPASSでは不足 |
| `TestBlockStorageReference`等 | read/write/allocate/truncateを参照実装と比較 | 共通reader自体の誤りを独立したbyteモデルとの比較で検出 |
| Capture/Ownedのweak参照test、Fork/Close競合test | transport残留、Close後解放、子の寿命 | 新rootで保持が増えていないか確認 |

既存oracleを削除したり、failureをsuccessへ書き換えたりして新方式を成立扱いにしない。
新方式で表現できなくした不正入力は、入口での拒否/作成不能を別の証拠にする。
所有層内部を直接破壊する注入は「安全だから不要」と消さず、検出能力の差として結果を残す。
strict経路のテストだけを残し、新しい通常経路を無検証にすることも認めない。

## 8. 次に進む場合の有限な部品spike

承認対象候補は、guest未接続のstorage所有モデル一つ。今回その実装はしていない。
終了条件は以下の表の各行に、成立/不成立/具体的な不足を付けてHuman Reviewへ返すこと。

| 項目 | 必要な証拠 |
| --- | --- |
| 内容が同じ | 独立byteモデルに対し境界write、穴、shrink/regrow、世代派生を比較。元と固定後のreader一致 |
| 読み直しがない | 固定/受け渡しでpayloadのread・copy・hashがゼロであることをcounterで確認。metadata操作数を別記録 |
| 書き手を閉じる | 旧writer、入力slice、絶対/相対truncate等から基準が変わらない。未固定/別capture/別identityを拒否 |
| 失敗と寿命 | 固定途中の失敗、受渡し放棄、基準Close、子/兄弟/派生保持、不要参照の回収 |
| 既存検出との差 | 上記oracleの対応表、所有層内部bytes破壊を含む結果。契約更新案を提示 |
| 費用の移動 | 書き込み時copy量、固定時metadata量、派生時の参照深さ/保持量。全量copyや無制限の祖先保持が必要なら明記 |

新しい速度目標や実guest改善率はこの段階で設定しない。約193msの支配区間に内容走査が
含まれるという既存証拠はあるが、全てを消した際の残差・metadata費用は未測定。
成立すれば次に実guestへ接続する範囲を提案する。不成立なら原因と残せる小案を示して止める。
論点を全Wasm安全性や全VFS置換へ拡大せず、未達を理由に際限なく試行を追加しない。

## 9. 今回完了したもの

読み直しの目的/限界、内容と所有権の経路、pgmemとの前提差、設計比較、保証と検出能力の差、
次の有限な成立条件を整理した。新方式の成立実証・性能・製品採用は未完了で、今回の設計検討と区別する。
文書と入力記録のみ変更。参照・hash・差分を確認し、runtime test/build/benchmarkは未実施。
mainの`.node-version`と他worktreeは保持。専用branchにcommit/pushし、作業worktreeと取得sourceを片付ける。

[freeze]: ../../internal/generatedgo/code/base/heap_snapshot.go
[heap]: ../../internal/prepared/heap.go
[own]: ../../internal/snapshot/heap.go
[owned]: ../../internal/snapshot/owned.go
[storage]: ../../internal/generatedgo/code/base/block_storage.go
[memfs]: ../../internal/generatedgo/code/base/memfs.go
[relative]: ../../internal/generatedgo/code/base/relative.go
[runtime]: ../../internal/generatedgo/runtime_instance.go
[mapped]: ../../internal/generatedgo/code/base/owned_prepared.go
[handoff]: ../../internal/snapshot/handoff.go
[pg-snapshot]: https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/snapshot.go
[pg-vfs]: https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/vfs/vfs.go
