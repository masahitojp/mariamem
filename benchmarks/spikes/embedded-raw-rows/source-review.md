# #65 — 現行wireを残した出力再利用の軽いソース調査

2026-11-10。Humanはnative再利用の意向を持ち、変更費用を下げる部分利用を調べるよう依頼した。今回はソース調査のみ。実装・build・CI・採用判断は行わない。

## 結論

**次に小さく確かめる候補は、embeddedが既に生成したpreparedのbinary rowを、列単位にdecode/re-encodeせず受け渡すこと。** 現行の入力decoder、MYSQL_BIND、同一MYSQL/session、接続・停止・Snapshot経路を維持できる見込みがある。server NET/Protocolをembeddedで新しく有効化する案とは別で、既に動く上流serializerの出力を利用する。

最も大きい懸念は、公開関数による列取得から`MYSQL_STMT.result` / `MYSQL_ROWS`の表現への依存に替わること。headerで参照できることは安定したraw-row API保証ではない。局所的な読取りadapterで済むか、実際の行bytes・metadata・寿命・エラー契約を保てるかは未実行。ゼロ追加patch・保守費用削減を認定しない。

先に提案した「embedded APIの出力先をそのままserver Protocolへ差し替える」案は小さな変更とは言えない。API自身がembedded用結果queueを読むため、出力だけ切り替えるとAPIの実行後処理を壊す。prepared入力を残すだけではこの結合を解けない。

## 固定した対象

- 現行main比較: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`。
- native比較: `54860bfe69c2e7cc0479ac451d8b1905b9edefb8`（glue分離後、host credit移設前）。
- MariaDB 12.3.3 source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`（mainのguest/input.json）。
- MariaDB 13.2 Preview source_commit: `c9f28ba0afec6d29e4688255dce8caaf7e91233d`。

固定commitの上流7ファイルをGitHubから読んだ。12.3.3のlib_sql.cc、13.2のlib_sql.cc/libmysql.c/protocol.cc/protocol.h/sql_prepare.cc/mysql.h。全source取得・patch適用・コンパイルはしていない。過去のローカル実験folderは不要。

## 直接確認したこと

### 1. 出力先だけの差替えが難しい理由

13.2の[emb_advanced_command](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/libmysqld/lib_sql.cc#L108)は既存MYSQLのTHDへdispatchする。
[emb_read_query_result](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/libmysqld/lib_sql.cc#L296)は`thd->first_data`からmetadata/status/errorを取り出す。
[emb_stmt_execute](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/libmysqld/lib_sql.cc#L337)は入力bindを設定した後、この読取りまで行う。

したがって、通常出力をserver packetに変えてembedded queueを生成しなくすると、同じC APIを変更なしで使う前提が崩れる。queueとpacketを両方生成する案も二重出力・metadata・error同期の設計が必要。現在のnative patchがProtocolメソッドを改名・分岐して併存させている理由と一致する。

### 2. embeddedでもprepared行のserializerは既に上流

[Protocol_binary::prepare_for_resend / store_*](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/sql/protocol.cc#L1723)が行packetを作る。先頭0x00、NULL bitmap、型別の値が入る。
[embedded版Protocol_binary::write](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/libmysqld/lib_sql.cc#L1268)は`packet->ptr()+1`から`packet->length()-1` bytesを`MYSQL_ROWS.data`へコピーし、`length`には元packet長を保存する。

重要: 保存先を`length` bytesコピーしてはいけない。コピーされた有効範囲は`length-1`。wire行payloadへの復元候補は`0x00 + data[0:length-1]`で、4-byte packet header/sequenceは現行hostが付ける。これはソースからの推論であり、実行確認ではない。

この関数の12.3.3と13.2の本文はbyte一致した（signatureから閉じbraceまで、SHA256 `fd3dc12857c1e8c272e66c431b76e14dc2ea0fabc477e468c6b9f669da0df3b9`）。全関連構造/APIの安定性を示すものではない。

[emb_read_binary_rows](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/libmysqld/lib_sql.cc#L374)が結果をstmtへ移し、[mysql_stmt_store_result](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/libmysqld/libmysql.c#L4441)から使われる。[mysql.h](https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/include/mysql.h#L739)には`MYSQL_STMT.result`の定義がある。読み出す間だけ所有元を生かし、free/next_result前にコピーする局所adapterが候補となる。

### 3. 現行では同じ値を作り直している

[guest/prepared_api.inc](https://github.com/masahitojp/mariamem/blob/b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50/guest/prepared_api.inc#L232)の`ps_result_bindings` / `ps_cell` / `ps_capture_result`は、結果をMYSQL_BINDで列取得し、数値・時刻・文字列を自前変換してJSON hexにする。
[preparedSingleResultPackets](https://github.com/masahitojp/mariamem/blob/b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50/internal/mysqlwire/prepared_execute.go#L138)はhexを戻し、`EncodeBinaryRow`で行を再構成する。

候補はこの列単位の往復を行payloadの受渡しへ替えること。内部envelopeを当初そのまま使えばJSON/hex自体は残る。JSON廃止・streamingを同時に目的化しない。文字列/時刻の再変換がなくなる分の性能効果は未測定。

## 何を温存し、何を避けられる見込みか

| 部分 | この候補での扱い |
| --- | --- |
| Go handshake、framing、capability、上限 | 維持 |
| prepared入力decode、型cache、LONG_DATA、ID管理 | 維持。入力側の互換性保守は残る |
| 同一MYSQL/THD、transaction・一時table | 同じ接続のまま扱う。実行試験は未実施 |
| text結果、metadata、OK/ERR/EOF、OUT選別・複数結果 | 現行処理を維持。binary rowだけでは通信全体の上流化にならない |
| prepared行の型別出力変換 | 上流生成済みbytesの利用へ縮約する候補 |
| 現nativeのNET/認証/dispatch有効化、Protocol併存、Item_param拒否後回復 | この候補のためには導入しない想定。既存nativeから一部だけ削る変更ではなく、mainからの独立した小差分 |
| nativeのVio/controller/capture hook | 新設しない想定。現行経路の保証を既存検査で維持する |
| 現行legacyのprepared metadata/型修正等 | 引き続き必要。raw row採用だけで既存patchを消せるとは判断しない |

現native overlayの15既存ファイルは、こちらの案の導入前提から外れる見込み。ただし「15ファイルのpatchを削除して動いた」という結果ではない。追加adapterに必要な依存はまだ確定していない。

## 残る確認と、次に進む場合の有限な出口

次を行う場合は**実embeddedでprepared binary rowを読み出す限定spike**を別に計画する。フルnative移行や製品化は自動再開しない。

1. 既存と同じ入力/接続で、raw row候補と現行のclient行payloadを比較。NULL・整数の符号/幅・DECIMAL・時刻小数・浮動小数・binary文字列と、metadataの整合を確認する。差が出たら上流との相違か現行契約かを判定し、oracleを書き換えて通さない。
2. 同じstmtの繰返し実行、空結果、結果metadata変化、複数結果/OUT、エラー後再利用、free/next_resultの寿命と上限を確認する。現行の結果chain全体を検査してから送信する保証を維持する。
3. 追加のengine patchなし・guest内の局所adapterで済むかを記録する。THD/Item_paramの改変や第二の型decoderが必要になるなら拡張せず再判断する。

既存prepared出力・chain・capability・lifetime検査は継承するが、raw rowの長さ規約と解放前コピーは新しい境界なので専用の検査が必要。現CIは未実装案の成立を検出できない。

この調査では性能・実動作・全OS・新版の総更新費用は判断していない。buffer済み結果を使う案なので、全件保持や初回応答待ちの改善も主張しない。実験費用はこのソース読取りから見積もれないため、次のspikeでは使える正規成果物とbuild要否を先に確認して有限予算を定める。

#150の共通準備は独立して継続できる。本メモは#65の方式相談の材料であり、過去のnative未完条件の免除・#138再開・main採用・releaseを意味しない。
