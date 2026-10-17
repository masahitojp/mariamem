# Snapshot所有権 — 部品spikeの結果

2026-10-17。Humanが[5条件](snapshot-ownership-contracts.md)で着手を承認したguest未接続spike。

## 当初のHuman Review（回答済み）

Humanは実guest接続spikeを承認した。現在の判断依頼は[実guest結果](snapshot-owned-root-guest.md)を正本とし、以下は承認時点の記録。

**次の判断は、実guestへ接続する限定spikeに進むか。私は進めることを推薦する。**
共通の内容表現を固定して同じ実体を渡す部品では、準備した内容と子の独立性を維持し、
dirty/inherited/zeroの固定・取得でpayload read/copy/hashをゼロにできた。
目標の「保証を支える仕組みを変え、読み直す必要をなくす」ことに、実装可能性の証拠が得られた。
実際のMariaDBでの成立性・利用者が待つ時間の改善は、まだ確認していない。

**最も強い反論は、同じrootの内部bytesを直接壊す場合、所有権による取得は検出せず、
strict内容検証は拒否するという差が実際に出たこと。** 通常APIからの変更や別rootへの差し替えは
拒否できたが、この故障検出を同等とは扱えない。次の接続spikeにも差を持ち込み、
本番採用時に契約の更新案と一緒に判断する。今回はこの差の受け入れや製品採用を求めない。

## 1. 元の問いへの結論

**通常heapで、所有権を根拠に全量の読み直しを不要にする部品は成立した。**
任意の破壊をhashと同等に検出できるという結論ではなく、読み直しを削った既存runtimeでもない。
新しい部品と現行runtimeは隔離されている。

- 実装：[model.go](../../benchmarks/spikes/ownedroot/model.go)。guest/runtimeからimportされていない。
- 内容・拒否・寿命：[model_test.go](../../benchmarks/spikes/ownedroot/model_test.go)。
- 実mmap：[mapped_unix_test.go](../../benchmarks/spikes/ownedroot/mapped_unix_test.go)。
- [生ログ/receipt](../../benchmarks/spikes/ownedroot/evidence)、[機械集計](../../benchmarks/spikes/ownedroot/evidence/summary.json)、[再現手順](../../benchmarks/spikes/ownedroot/README.md)。

元のruntime `source_commit`: `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`。
部品一式の検証 `source_commit`: `653ec565464703685a46c9c1132671bfc81bc7b8`。
G0追加testの検証 `source_commit`: `38f62dcf5365e12e44db21eb4d6506833888e92e`。
両方ともbuild前に`git_identity.py inspect HEAD`とclean statusを確認した。
後者はG0 test追加だけで、先に検証したmodel.go/runner/mmap fixtureは同一bytes。
最終文書commitを、未実行のruntime候補として検証済みと呼ばない。

環境：Apple M1 / macOS27.0.1 arm64、Go1.26.8。通常CGO=0、race検査のみCGO=1。
Ubuntu x86_64は**SKIP（今回は実行していない）**。

## 2. 5条件への回答

### 条件1 — strict oracleの棲み先：部品の両層で確認

| 層 | 実施結果 |
| --- | --- |
| 所有層の内容oracle | 独立byteモデルで3 seed × 500操作、各20世代を比較。境界write、穴、Allocate、append、truncate/regrow、固定後readを確認 |
| strict破損oracle | 元の期待digestをtest側に保持し、内部bytesの直接破壊を`VerifyContents`が拒否 |
| 新経路の差し替え拒否 | 実装した`Freeze → Capture → Acquire`で別root、未固定、別capture key、別guest、放棄、欠落/余分file、block差し替え、size変更、directory変更を拒否 |
| 公開前の状態 | 未完了と取得済みcaptureの再使用を拒否。固定途中の失敗では取得できる結果を残さない |
| 既存strict oracle | 元の`TestHeapTargetCorruptionOracle`等6件を無変更で実行しPASS。新部品の証拠とは区別 |

内容oracleは通常取得から呼ばれていない。`VerifyContents`は比較・転送adapter用のstrict入口で、
通常`Acquire`はroot/capture/identity/metadataの対応を確認する。
本番Capture/Owned配線は未接続なので、その配線での拒否は**未確認**。

内部bytesだけを壊す注入では、`Acquire`は受理し、strict oracleは拒否した。
`TestStrictOracleAndInternalCorruptionLimit`のPASSは、この差を再現した意味であり、安全性PASSではない。
現行failureをsuccessへ変更したものではない。

### 条件2 — 経路別の読み直し：通常heapでゼロ、境界は非ゼロ

各fixtureで固定・取得を別phaseに記録し、通常とraceの両実行で同じ結果を確認。
表は部品の結果。時間の測定ではない。

| 経路 | 固定/取得のpayload | 非ゼロ対照・残る仕事 | 判定 |
| --- | --- | --- | --- |
| dirty heap | read/copy/hash/zero-fill/allocation **0** | 準備writeと通常readでcounterが増加。metadata確認は残る | PASS |
| inherited heap | 同上 **0** | 子が最初に書く時のCoW copyを別phaseで記録 | PASS |
| implicit zero | 全量展開/読み取り/hash **0** | read時には正しいゼロを返し、zero-fill counterが増加 | PASS |
| dirty/inherited/zero混在 | 同上 **0** | 同一fileの境界と末尾をbyte oracleで確認 | PASS |
| mapped base | ゼロ対象外 | 実mmapから32,771 bytesをheapへcopyし、source/targetを各32,771 bytes hash。unmap後の内容保持も確認 | PASS：コピー境界として |
| handoff | ゼロ対象外 | 16,387 bytesのfileを出力/hash。受信でcopy/検証し、同サイズ破損・別guestを拒否 | PASS：メモリ上の転送adapterとして |

handoff受信hashの生counterは正常＋破損注入の2回分で32,774 bytes。1回分の費用とは呼ばない。
本番のpath/FD/IPC handoffは**未実行**。実mmap fixtureもMariaDBの復元経路の実行証拠ではない。

counterはcopy、clear、SHA-256、block確保の共通helperに接続し、model.go内のpayloadアクセス箇所を照合した。
空欄をゼロと扱わず、通常read/strict hash等の既知量対照も集計で確認した。
値はhelperが扱ったbyte数であり、CPU命令数やmemory bus trafficではない。
test自身の内容比較は固定/取得のphaseに含めない。

### 条件3 — 利得の分離：G0を残し、G1/G2と混同しない

| 利得 | 部品で得た証拠 | まだ言えないこと |
| --- | --- | --- |
| G0：確認済み実体を所有移転 | 別testで8 bytesを一度strict hashし、取得では追加payload処理0。root/capture対応で受け渡せた | 現行Heapの3回目を削る実装や速度は未検証 |
| G1：Snapshot専用再構成を廃止 | mutable/fixed共通readerを使い、固定・取得で内容を読み/hashせず内容保持を確認 | 本番MemFSからの移行と実guestの結果は未確認 |
| G2：表現統一 | sparse heap/zero/有効末尾を共通表現にできた | mappedからheapへの寿命切断は残る。G2全体成立や全base処理消滅とはしない |

したがって、実guest接続でG1/G2が成立しなくても、G0を別の小案として再判断できる。
pass1の固定・metadata作業まで消えたとは報告しない。

費用の移動もある。部品はFreezeでfile/block metadataのstampを複製し、Acquireで照合し、
Forkでmetadataを複製する。payload全量走査はなくてもO(file/block metadata)の仕事は残る。
100MiBの論理長に1 byteだけ配置したfixtureではblockは1個のまま、子の変更で有効prefix 1 byteを
コピーし、新たに16KiB blockを確保した。これは疎な部品fixtureの説明であり、
100MiBのMariaDB性能調査や既存Fresh問題の再開ではない。
子は祖先rootを保持せずflatなblock参照を持つ。weak参照testでも親rootの回収を確認した。

### 条件4 — 本番接続時の生成境界と作業

このspikeではruntime/guest/converter/生成inventoryを一切変更していない。
本番接続を選ぶ場合は、次の作業が必要になる。部品をそのままmergeする計画ではない。

| 所有元/境界 | 必要な作業と費用 |
| --- | --- |
| `internal/prepared` | digest無しroot、writer失効、copy/strict変換の責任を移す。旧`Heap`との入口を区別 |
| 手書き`code/base/{block_storage,heap_snapshot,memfs}.go` | 新所有層へのadapter。絶対/相対open、Allocate、writer、metadata操作の配線と既存reference testを確認 |
| `HANDWRITTEN_FILES`/`handwritten_owner` | base adapter/testを追加・移動する場合に一覧と取得元を更新。通常`internal/prepared`のfileをraw generated inputに混ぜない |
| `runtime_memfs.py` | `.apply_relative`/`.apply_mapping`の出力が新adapterと合うか確認。既存wrapperを保持できるなら置換先を変えない選択もある |
| pinned preimage | converter出力の切り出し対象が変わらなければ固定hashは維持。変わる場合のみ旧新入力を根拠付きで再ピン留め。テストを通すためのhash更新は禁止 |
| `release/generated-go-inputs.json` | raw converter入力が変わらないならcandidate inventoryは維持。実際の入力変更があれば正式経路で更新 |
| runtime/Capture/host/Owned/復元 | guest終了後だけ固定し、同じroot/requestを引き渡す。本番の失敗・cancel・Close競合oracleを新経路に接続 |
| source/provenance | `generate_runtime.py`/`verify_generated_runtime.py`の所有分類を維持し、正式な独立再生成で入力・変換後出力・手書きownerを照合 |

部品の成功から、これらの配線・再生成が安価/完了済みとは推論しない。
guest/Wasm/converterを更新する理由は今回得られていない。
最終Qualification、release、全guestのrace censusはこの作業へ追加しない。

### 条件5 — digest無しの内部APIとmanifest設計

部品では`root`/`Owner`にdigestを持たせず、`Transfer`だけがdigestを持つ。
`HeapFile`の必須digestや既存constructorを緩めていない。

本番の設計案：

- Captureは固定済みrootと取得要求の対応を持つ内部型を運ぶ。Ownedにはその内部型専用の取得入口を設ける。
  raw Heap/bytesを「固定済み」として包む入口は設けない。
- `prepared.Entry`/復元は固定rootかstrictな旧Heap/FDかを区別し、guest identityと寿命を維持する。
  公開Go/PythonのSnapshot/Fork APIを変える必要は、この部品結果からは生じていない。
- handoff時にfile内容を読み、digestを作って現行version-1 manifestへ出力する。
  部品のJSONを現行`stored.Manifest`へunknown field拒否付きでdecodeし、field名/必須値を確認した。
  schema変更は不要という見込みだが、本番受信処理での検証は残る。
- 本番では全fileを追加bufferへ保持する部品の`Transfer.Data`方式を移植せず、出力とhashをstreamで行う案。
  受信側の独立copy/内容検証は維持する。

digestを作る時点が取得時からhandoff時へ動くため、取得後export前の内部破壊について、
元digestとの比較はなくなる。転送先の一致を確認できても、その差は埋まらない。

採用時に提示する製品契約の更新案は、次の責任を明文化するもの：
「同一プロセスの取得は、停止完了した正確なfile集合・論理状態を固定し、
変更不能な同一実体の所有権とidentity/構造を確認する。コピー/転送境界では内容digestを照合する。」
これが現行の「取得時に内容を完全検証する」の実現方法変更として妥当か、
実行時の検出能力差も含めてHumanが採用時に判断する。今回は契約本文を変更していない。

## 3. 検証と限界

| 項目 | 結果 |
| --- | --- |
| 部品の通常テスト | PASS：top-level 10件、subtest込み27 pass event |
| 部品のrace検査 | PASS：同じ27 event。報告なしを一般的なrace解消の証拠にしない |
| 独立G0 test | PASS：追加後のsourceでtargeted `-race`実行 |
| 既存strict/寿命oracle | PASS：6件、ソース変更なし |
| 旧writer、入力slice、兄弟/世代隔離 | PASS：8種類の旧操作拒否、入力copy、shrink/regrow、親Close後の子 |
| 失敗・放棄・参照回収 | PASS：固定前/途中、transport移転後、親root回収。子は使用可能 |
| 並行Fork後の子操作/親Close | PASS：部品4子。実SQLの並行動作は未実行 |
| 実mmapの取り込み・unmap後保持 | PASS：macOSの部品adapter |
| 内部bytes直接破壊の取得時検出 | **未対応を再現**。strictは拒否、所有取得は検出しない |
| 本番のguest・FD/relative-open・cancel再試行・handoff | 未接続/未確認。部品では同じfile handleや直接APIを使い、WASI/FD配線は模擬していない |
| Ubuntu・実guest速度・独立再生成・Qualification | SKIP：今回の部品実行には含めない |

部品Captureはone-shotで、放棄前後の通常データ保持は確認したが、同じrootでcapture要求を
再発行するprotocolは未実装。本番のcancel/事前拒否/再試行規則をそのまま満たすとは報告しない。
renameは同directory内のみなど、FS全機能の代替でもない。

初回は部品全件PASS後、長いtest2json行の分割をcollectorが処理できず失敗した。
初回ログを保存し、集約を修正して残る検証を完了した。遅い試行/失敗を除いた性能集計ではない。
再現scriptと生ログhashは保存。追加の実行時間比較や実guestの短縮率は算出していない。

## 4. 次へ進む範囲と停止条件

推薦する次段階は**一つの実guest接続候補**。root/worker終了後の固定から、
本番Capture/Owned/Forkへ同じrootを通すところまでを対象にする。
既存strict経路を維持し、mapped/handoffは明示したcopy/検証境界にする。

終了条件は、通常SQL準備後のSnapshot/Fork、子/兄弟/派生の独立性、失敗/cancel/Close/回収、
本番配線への差し替え拒否oracle、正式なsource/生成所有検証、経路別counter、
同一fixtureでの利用者が待つ全体時間を揃えて報告すること。
初期の193msや130msを到達済み/採用条件とはしない。
G1/G2が成立しない場合はG0の小案を残して戻す。別のVFS設計へ無断で広げない。
新しい採用判断はここから別途行い、現段階でmain統合・公開は行わない。

今回の部品spikeの実装・限定検証・5条件の整理は完了。
実guestへの適合、検出能力差の受け入れ、製品採用は未完了であり、上の次段階の判断対象である。
