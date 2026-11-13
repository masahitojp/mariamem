# Fork初期化のゼロ書き込み：用途の分類（2026-11-13）

結論：現行Forkで目立つゼロ書き込みは、(1) InnoDBバッファプールの全域初期化、(2) MyISAMキーキャッシュの管理領域の初期化まで具体化できた。server_init全体を一つのメモリ確保処理とは扱わない。次はバッファプール確保時のゼロ保証をどの層が担うべきか、malloc再利用も含めて契約を確認する小さな調査を推奨する。ゼロ書き込み削除や性能改善の実装・採用は今回行っていない。

## 証拠と対応付け

製品source_commitはeb175ae23292c1c40cfbeb4b9b73132873c4cc6f、guest SHA256は5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20。前回Fork-window計測bb459758917ebb82842e57aed29ecbefc9d5a1a1の16profileを再解析し、新しい時間計測は行っていない。CI43330322013のartifact13995083516から同一SHAのWasmを取得して照合した。外部ソースはMariaDB source_commit83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5eの該当ファイルのみ取得し、URLとチェックサムをsource-files.jsonに記録した。

重要な限界：guestのDWARFは残っていたが、22757個のlow_pcが全て0であり、関数番号→C名の直接マップには使用できなかった。前回の「デバッグ情報から対応付けできそう」という見込みは成立しなかった。古い別guestの関数番号マップは採用していない。

代わりに、同一guestに結び付いた生成Goのハッシュ、CPUサンプルの行番号、実際の命令・定数・call chainと固定Cソースおよび現行パッチを照合した。これは全関数のシンボル復元ではなく、以下の限定された処理のソース対応である。generated-snippets.mdとgenerated-hashes.jsonが照合対象。Wasmのpassive data segmentは生成GoのMemoryInitと同じアドレスに配置し、参照するInnoDB/Aria/charset診断文字列も抽出した（strings-*.json）。文字列単独を関数名の証明にはしていない。

## 1. InnoDBバッファプール全体

経路：InnoDB初期化の巨大な生成関数p0.Fn18569内 → buf_pool_t::create()に対応する領域確保 → my_large_virtual_alloc_aligned() → posix_memalign → memset(p,0,*size) → MemoryFill → Go memclr。

- CPUサンプルの主要siteはp0/p0_pure.go:675426。2MiB alignmentでFn239を呼び、成功時に返されたpointerをsize全体ゼロにする直前直後の命令を照合した。
- canonical guest/patches/12.3.3-buffer-alignment.patchはbuf_pool_t::createからこの関数を呼ぶよう変更している。同パッチに全域memsetが明記されている。これは#63で採用済みの整列修正であり、新しい候補ではない。
- upstream buf0buf.cc:1333以降のbuf_pool_t::create、および上記パッチのposix_memalign→memsetが対応する。Wasmは通常のPROT_NONE予約を使わず、コミット済み領域を確保する経路。
- pinされたlite4mariadbレシピの起動設定はinnodb-buffer-pool-size=16M、size-max=16M（wasm/lite4mariadb.c:335-336）。設定値と実行中の全呼び出しbyte数の計測は区別する。今回は各MemoryFillのbyte数をinstrumentしてはいない。

P8のこのsiteは0.14 CPU秒（全2.22 CPU秒の6.31%、64Fork合計）。P1では0.02/2.47秒。100Hz標本で逐次/並列差も大きく、この値からwall時間の削減見込みを算出しない。buffer_pool全体の起動費用でもなく、このゼロ書き込みsiteのサンプルである。

## 2. MyISAMキーキャッシュの管理領域

経路：init_simple_key_cache相当のp4.Fn4245 → my_multi_malloc_large相当のp7.Fn4181 → my_malloc相当のp7.Fn981 → MY_ZEROFILL分岐 → MemoryFill。

- p4/p4_pure.go:253349は複数領域をまとめて確保する呼び出し。blocks×72、hash entry数、hash link数、changed/file block配列というサイズ計算・分配を固定mf_keycache.c:535-575と照合した。
- C側は明示的なMYF(MY_ZEROFILL)。ゼロ対象はblock_root、hash_root、hash_link_root、changed_blocks、file_blocksの管理領域であり、keycacheのデータ領域全体をゼロにするという意味ではない。
- p7/p7_pure.go:47043はflagsのbit32を確認して、割当pointer+16のユーザー領域を指定sizeだけゼロにする分岐。固定mysys/my_malloc.c:105-117のheader/owner処理とMY_ZEROFILLのbzeroに対応する。

P8ではこのcall chainのゼロ書き込みが0.07 CPU秒（全体の3.15%）、P1では0.06 CPU秒。以前の関数単位profileでFn4245配下と表示された0.07秒は、この管理領域の初期化だった。全てのmy_mallocのゼロ書き込みをMyISAMと一括りにはしない。Ariaなど別callerも残る。

## 残る費用と正しい解釈

P8全体のmemclrは0.35秒=15.77%。上の2経路は合計0.21秒=全体9.46%を占める。残り0.14秒にはprepared file読み書き経路、別のInnoDB初期化、charset初期化、Aria等からのmy_malloc経路がある。分類はclassified.json、全stackはsites.json。CPU割合をserver_initの壁時計29.66msに掛けて「何ms削れる」とは計算できない。今回でserver_initの残り全体のC関数別wall時間まで特定したとは主張しない。

profile protobufを直接読んでinline frameも展開し、全サンプルとmemclr合計をpprofと照合した。P1は2.47/0.26 CPU秒、P8は2.22/0.35 CPU秒。テキストraw解析ではinline等の表現を落として一部を取りこぼしたため不採用とした。sites.pyが最終解析器。

## 推奨と進む条件

次の候補は、InnoDBバッファプールの確保直後のゼロ保証を分類すること。ここは固定16MiBの領域に対する明示的memsetで、処理の意味・境界が分かった。一方、最大の反論は、この関数がもともと「全実装でzero-filled bufferを返す」という契約を持ち、posix_memalignはmallocの再利用領域を返し得るため、単純なmemset削除は不正になり得ること。Wasmの新規memory.growがゼロであっても、malloc再利用を経由する全ケースの保証にはならない。

進むには、fresh allocationと再利用の到達条件、消費側が初期ゼロを必要とする範囲、失敗/再試行/解放の契約をソースで確認する必要がある。追加費用はこの境界のソース調査1件。情報不足なら限定instrumentationを1回追加し、その時点で元の速度対照と正しさの条件を決める。安全なゼロ保証と改善余地を確認できてから最小のspikeを判断する。MyISAM管理領域はnull/empty状態を作る意味が明示的で、現時点で削除対象には推奨しない。

#56のmemory.grow batching、#116のrootRead clear削減は以前の不採用を維持。#88の一律8MiB default変更も再開しない。今回の静的対応付けからいずれの性能判断も覆らない。MDEV-42129、Close、SQL/triggerの調査は行っていない。

## 再現と保全

前回profileはbb459758917ebb82842e57aed29ecbefc9d5a1a1:benchmarks/forkcost/results-20261113-current/runsのpprof.b64から復元可能。sites.pyのP変数を復元先に合わせて実行する。profileのパスは正規化済みであり、関数名・行番号・sample値は同じ。今回の本解析はローカルに保存した同一計測の元profileを使用した。

生成Goは上記source_commitをcheckoutしてgenerated-hashes.jsonを照合する。Cソースはsource-files.jsonのURL/sha256、buffer-alignment.patch.txtは現行canonicalパッチのコピー。今回の追加は調査資料のみ。製品のguest/runtime変更、新しいベンチ、CI投入はない。
