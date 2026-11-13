from pathlib import Path
import hashlib,json
E=Path(__file__).resolve().parent;W=E.parent/'worktree';S=E.parent/'temp/source';P=E.parent/'temp/patched';D=W/'benchmarks/forkcost/buffer-zero-contract-20261114';D.mkdir(parents=True,exist_ok=True)
text='''# バッファプール初期ゼロの契約確認（2026-11-14）

結論：全域memsetをそのまま削除するのは不可。一方、Wasmバッファプール専用の確保経路に限り、管理情報（descriptor）をゼロにしてページフレームの全域初期化を省く小さなspikeには、ソース上の根拠が得られた。既存のresizeは管理情報のみを再初期化し、通常のfree/reuseもページ本体の初期ゼロを保証していない。最大の反論は、圧縮ページ・復旧・汎用メモリ利用を含む全消費経路の実行検証はまだなく、初回だけ隠れてゼロに依存する不具合がないとは断言できないこと。今回の判断は「限定spikeを試す価値がある」であり、製品の安全性・改善率の証明や採用承認ではない。

## 固定入力と調査境界

- 前回の原因対応付け: cb4f43f9f2ec46a1afc79048b8689b1a46636ff2、Fork計測: bb459758917ebb82842e57aed29ecbefc9d5a1a1。今回のbranchは前者から開始した。
- 調査対象の製品source_commit: eb175ae23292c1c40cfbeb4b9b73132873c4cc6f。上記report commitまでinternal/guest/releaseの差分はない。guest SHA256: 5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20。
- MariaDB source_commit: 83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e。対象ソースを取得し、common-portability.patchと12.3.3-buffer-alignment.patchの該当ファイル分を実際に適用して確認した。パッチ後の行番号はsnippets.mdを参照。
- WASIX libc v2026-07-03.1のsource_commit: 09503b230e8acc721c1e013ca28a41bf149e4ee2。tagのcommit実体を確認し、固定commitから該当3ファイルを再取得してbyte一致を確認。allocatorの構造の補助証拠であり、生成guestでの実際のallocation/reuseイベントを計測したものではない。
- source-files.jsonに全取得URL/sha256、patch-application.jsonに適用結果、generated-identity.jsonにコンパイル済みlayoutの根拠を保存した。調査資料だけの変更。C/Go製品実装変更、再ビルド、ベンチマーク、CI投入は行っていない。

## 1. 確保した領域が必ず新しいゼロ領域とは言えない

現行のmy_large_virtual_alloc_aligned()はposix_memalignの後に全体memsetを行う。このhelperには従来からzero-filled bufferを返す契約があるため、共通helperのmemsetを無条件に削る案は退ける。

WASIX dlmallocのposix_memalignはinternal_memalignへ進み、通常のinternal_mallocから大きめのchunkを取得して、整列のための前後の余りをfree側に戻す。callocのようなpayload全域クリアはしない。HAVE_MMAP=0 / MORECORE_CANNOT_TRIM=1のwrapperであり、free後のメモリをOSへ返して次回必ず新しいゼロページを得る設計ではない。

現在のForkは個別Moduleの初期メモリから起動するが、そのことだけでは、Cヒープ上の個々の割り当てが必ず未使用のmemory.grow領域であるとは証明できない。初期化中の他の割り当て、解放、整列用の分割・再利用があるためである。今回、現行16MiB割り当てが実測で何回reuseされたかは測っていないし、必ずreuseするとも主張しない。

## 2. 管理情報は初期ゼロが必要

buf_pool_t::create()の各2MiB extentは、先頭のbuf_block_t管理配列と後続のページフレームからなる。createは管理情報全体を明示初期化せず、ゼロを前提にframe pointer、lock、free listを設定する。debugのmemcmp(block,field_ref_zero,sizeof *block)もそれを直接検査している。

buf_page_t::NOT_USEDは0であり、古いstate/hash/list/zip/oldest_modification等を残せばfree blockとしての不変条件を壊す。lock.init()だけで管理情報全体を初期化できるわけではない。したがって管理配列は必ずゼロにする。独立したfield_ref_zero（64KiBのゼロ参照領域）やpage hash table、その他の初期化も今回の削減対象に含めない。

## 3. ページ本体は通常運用でも非ゼロのまま再利用される

buf_LRU_block_free_non_file_page()はstateをNOT_USEDへ戻し、frameをMEM_UNDEFINEDにし、free listへ戻す。ページ本体を全クリアする処理はない。buf_pool_t::allocate()もfree listから取り出し、状態をMEMORYへ変えるだけでframeをゼロにしない。MEM_UNDEFINEDはメモリ診断用の注釈であり、ゼロを書き込む命令ではない。

ファイルから読み込む経路はpage-size（圧縮時はzip-size）のI/Oを発行する。新規ページ経路buf_page_create_low()も先行するページの内容を残し得る同じframeを受け取り、必要なheaderを初期化する。buddy allocatorもfree listへ追加する部分にstampを設定し、利用部分にはnonfree stampを置く。これらは「frameは常にゼロ」という契約ではない。

これは未初期化データが公開されてもよいという意味ではない。各ページ作成・復旧・圧縮・I/Oの消費側が必要なbyteを正しく初期化する責任は残る。その初回経路を非ゼロ入力で実行確認するまでは、pageフレームの初期クリア省略を安全と認定しない。

## 4. リサイズには既に管理情報だけの初期化がある

Wasm用my_virtual_mem_decommit(ptr,size)は会計更新だけであり、payloadをクリアしない。my_virtual_mem_commit(ptr,size)はptrがNULLの場合だけ新規確保してmemsetする。既存ptrを渡す再拡張では、内容をクリアせず会計更新して返す。

buf_pool_t::resize()の拡張経路は、追加されるbuf_block_tだけに明示的memsetを行い、その後frame pointer、lock、free listを設定する。既存の縮小→再拡張では、ページフレームに古い内容が残り得る。このソース上の事実が、createでも管理配列のみ初期化する案の最も強い根拠になった。今回resizeを実行したという主張ではなく、canonicalパッチ後のC実装を照合した結果である。

## 5. 失敗・再試行・解放

| 経路 | 現行の責任 | spikeで維持する条件 |
|---|---|---|
| posix_memalign失敗 | NULLを返してcreateのoomへ | 成功pointerを捏造しない。失敗時のsize/pointer更新を変えない |
| alignment余白不足による再試行 | 確保領域をreleaseしてsizeを調整し再確保 | 同じ2MiB整列、元allocation pointer/size、free互換性を維持 |
| commit失敗 | allocationをreleaseしmemoryとmemory_unalignedをNULLへ戻す | 管理情報の初期化位置変更で解放漏れを作らない |
| 正常create | 管理配列のゼロ前提の上に状態構築 | 全有効descriptorをframe/lock/list設定より前にゼロにする |
| startup途中のabort | buf_pool.close()がis_initialisedを見て解放 | 部分初期化の扱いと既存cleanup順序を変えない |
| close | decommitで会計減算、releaseでfree(ptr) | 途中に合わせた別のallocator/free方式へ変えない |
| resize/shrink/regrow | 追加descriptorのみゼロ、free frameを再利用 | 全page-size/partial extentを既存計算で扱う |

上記はコード経路の分類であり、OOM注入等の実行試験は未実施。共通helperの契約を維持するため、spikeはbuffer pool専用経路に限定し、他callerやmy_virtual_mem_commit(NULL)のゼロ保証を変えない。

## 6. 静的に分かった書き込み量

現行Wasm32の生成コードはdescriptor stride232byte。ページサイズdefaultは16KiB、extent2MiB、pool16MiB。upstreamのfirst_page/pages/get_n_blocks計算と生成コードのstrideを照合してlayout.jsonを算出した。

| 領域 | byte数 |
|---|---:|
| pool全体（現行helperがクリア） | 16,777,216 |
| 管理情報1008個 | 233,856（約228KiB） |
| ページフレーム本体 | 16,515,072（15.75MiB） |
| extent内のpadding | 28,288 |

管理情報のみに絞れれば、このsiteのクリア対象byte数を約98.6%減らせる計算。ただしruntime計測値でもForkの改善率でもない。異なるpage size、pool size、C ABIに232や1008を固定値として実装してはいけない。既存の型とextent計算を使う必要がある。

前回P8のこのsiteのCPU標本は64Fork合計0.14秒/全2.22秒。標本は粗く、P1との揺れも大きい。byte数削減をwall時間短縮へ換算しない。必要な管理情報書き込み、allocation/grow、cache fault、後続処理への費用移動も残る。

## 次の限定spikeの条件

推奨するのは「buffer pool専用の非ゼロ保証allocation＋create時descriptor全域ゼロ」の小さなspike。共通helper、初期ゼロ参照領域、容量default、hostのmemory.grow方針を変えない。実装する場合はguest/experimental.patchに置き、canonical guest/source.patchやrelease pinsには採用前に入れない。

最初の正しさの対照は、割り当てたpoolを意図的に非ゼロ（例0xA5）にしたうえで、descriptorだけゼロにして起動・Snapshot/Fork・データ整合を確認すること。単に通常実行がPASSしただけでは、たまたま新規ゼロ領域を引いた可能性を排除できない。初期descriptorゼロと整列の検査も必要。

最低限、初回/繰り返しForkの隔離、poolを超える読み書きとLRU再利用、resizeの部分extentとshrink/regrow、圧縮/buddy・復旧/新規ページ・I/O失敗時の既存oraclesに対して、非ゼロフレームで意味を保てることを確かめる。その後、観測処理なしの同一条件対照でForkとSQL/Closeを含む全体を比較する。後続へ費用を移しただけなら採用しない。canonicalソースからの実guestビルドが少なくとも1回、比較用candidateのビルドが1回必要で、ビルド時間は今回未見積もり。次の実装前に使える同一source baseline artifactの有無と費用を確定する。

今回のソース確認は完了。実装・実guestの非ゼロ対照・性能比較・製品採用は未着手。#56の拡張単位変更、#116のrootRead、#88のdefault容量変更、Close、MDEV-42129は再開していない。

## 再現

fetch.py → fetch-more.py → fetch-libc.py → pin-libc.pyで固定ファイルを取得し、inspect.pyでhash照合、対象canonicalパッチ適用、契約anchorとlayoutを確認する。inspect.pyは取得したソースをコピーし直してパッチを適用するため再実行可能。snippets.mdに今回読んだ箇所を保存し、入力が失われても結論の根拠を参照できる。製品を変更していないので、runtimeの回帰試験やRelease acceptanceは実行していない。
'''
(D/'README.md').write_text(text);(E/'README.md').write_text(text)
selections=[(P,'mysys/my_largepage.c',430,465),(P,'mysys/my_virtual_mem.c',70,108),(P,'mysys/my_virtual_mem.c',150,215),(P,'storage/innobase/buf/buf0buf.cc',1470,1500),(P,'storage/innobase/buf/buf0buf.cc',1990,2070),(P,'storage/innobase/buf/buf0buf.cc',1605,1630),(S,'storage/innobase/buf/buf0lru.cc',948,980),(S,'storage/innobase/buf/buf0buf.cc',1262,1290),(S,'storage/innobase/include/buf0buf.h',489,506),(S,'storage/innobase/buf/buf0buddy.cc',378,408),(S,'dlmalloc/src/malloc.c',4921,4942),(S,'dlmalloc/src/malloc.c',5345,5375),(S,'storage/innobase/include/univ.i',198,215)]
chunks=[]
for root,n,a,b in selections:
 lines=(root/n).read_text().splitlines();chunks+=['### '+('canonical patched ' if root==P else 'upstream ')+n+f':{a}-{b}','```c',*lines[a-1:b],'```','']
(D/'snippets.md').write_text('\n'.join(chunks))
for n in ['fetch.py','fetch-more.py','fetch-libc.py','pin-libc.py','inspect.py','publish.py','source-files.json','source-identity.json','libc-identity.json','layout.json','patch-application.json','generated-identity.json']:(D/n).write_bytes((E/n).read_bytes())
files={str(f.relative_to(D)):hashlib.sha256(f.read_bytes()).hexdigest() for f in D.rglob('*') if f.is_file() and f.name!='SHA256SUMS.json'};(D/'SHA256SUMS.json').write_text(json.dumps(files,indent=2)+'\n')
policy={'reproducible':{'temp':{'reason':'Downloaded fixed upstream C sources and selected patched copies; compact excerpts, hashes and recipes preserved','command':'fetch.py; fetch-more.py; fetch-libc.py; pin-libc.py; inspect.py','inputs':'source-files.json, source-identity.json and canonical patch hashes'}},'keep':{'evidence':{'kind':'durable-evidence','reason':'Unique buffer pool zero-contract analysis, layout and reproduction records'}}};(E.parent/'cleanup-policy.json').write_text(json.dumps(policy,indent=2))
print(D)
