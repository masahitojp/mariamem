# #65 — 上流を活かすhost/glue/guest境界のレビュー

2026-11-10。**推奨：既存のNET/Protocol/preparedを再利用し、hostを接続・資源・寿命の方針の所有者にする。guestにはエンジンの状態と、その状態を変える直前・終了時の小さな接続点を残す。現在の構成を土台にできるが、現パッチ全体を必要最小限と認定しない。**

理由は、Vioには既にread/write/wait等のcallbackがあり、独自decoderなしに輸送を分離できる一方、prepared拒否後の状態回復とSQL/captureの排他はMariaDB内部の実行位置に依存するため。
最大の反対材料は、embedded/native併存のための変更と独自の互換性修正が上流内部に残り、hostへの移設だけでは更新負担が減らないこと。
このため、全controller移設を先行せず、下記の接点を残す理由と代替条件を固定する。これは境界設計の推奨であり、製品採用・総費用改善の認定ではない。

Humanの目的は「MariaDBの既存実装を活かし、上流にパッチを当て続ける負担を減らすこと」。C++全廃、ゼロパッチ、検査数や移動行数の削減は目的にしない。hostへ移して第二のparameter decoderやprepared registryを作る案は採らない。

## 対象と確認方法

- 候補source_commit：`37e79f644e53bd8a38182621f66a58a87e38289a`。
- stable比較元：`47121e1be0b399ba4e2270ce3e25c411ade0e2eb`（0.6.2）。
- MariaDB評価source_commit：`c9f28ba0afec6d29e4688255dce8caaf7e91233d`（13.2 Preview）。13.3採用の証拠ではない。
- 前段の境界・到達性・構成レビュー：`f4507b514aabac2eb834170668c69f37067b6732`以下の文書。古い未完記述を今回の状態へ読み替えない。
- 上記対象は直前の作業記録から復元した。作業checkoutは別branchのため、候補はすべて`git show`で読んだ。#65/#131の現本文も読み、条件を照合した。

[13.2 descriptor][descriptor]から実際の7パッチを解決し、本文のSHA256を確認。13.0.2/native-textとの7本文はすべて一致した。native overlay内の追加5ファイルは後続hunkも順にメモリ上で適用し、最終postimage hashと一致を確認した。最初の古いcontroller断片だけで判定していない。
上流の[Vio][upstream-vio]・[Protocol][upstream-protocol]・[prepared更新順序][upstream-conversion]は固定commitから直接読み、callback、compile分岐、conversion更新順序を確認した。guest build・新runtime実行・CI提出はしていない。

## 推奨する責務境界

| 所有者 | 持つもの | 境界で守ること |
| --- | --- | --- |
| host | listener、TCP/Pipeの受付・容量予約、epoch/generation、Live/Forkの寿命、資源・cleanup debt、利用者向け設定・第一原因 | native退役とhostのread/write完了が揃うまで資源を解放しない。SQLの内容から状態を推測しない |
| 自前glue | memory Vio、THD作成/解放の呼出し、raw bytesの受渡し、workerとの同期、イベント通知 | MariaDBの内部型はglueで閉じる。GoにTHD/Item_paramのlayoutを公開しない。host方針を実行する最小限のbuffer/handle状態は必要 |
| MariaDB | SQL/transaction、prepared ID・型・LONG_DATA、NET packet状態、Protocolの通常応答 | 上流のparser/serializerを使う。hostは通常のgreeting/row/ERRを再実装しない |
| guestの実行境界 | command受付と最終dispatchのfence、rollback結果、native cancel/joinの事実 | 非同期の「idle」通知だけでcaptureを許可しない。外へ移すなら同じ原子性・寿命保証が必要 |

現在、[host Owner][owner]がslot/generationを発行し、guestは受け取ったidentityを検証する。ここは既にhostへ寄っている。
一方、再構築した`issue65_control.cc`の`Session`/`Manager`にはqueue、credit、deadline timer、phase、capture gate、killer/reaperが残る。「状態はすべてhostへ移った」は誤り。
hostが期限の設定値を決めても、guestでのfirst-byte受付とexpiryの実施位置は別問題。現在の非同期制御channelのままtimerだけ外へ移すと、通知遅延・stale commandの扱いが変わる。local watchdogを削除する根拠はまだない。

既存のcallbackを利用する方向は成立している。ただし、現在はWASIX→wasm2goとprivate制御channelを通す構成で、直接Go callbackを差し込んだ実装ではない。新しいcgo/direct-import方式をこのレビューで選んだわけではない。

## Native overlay全20ファイルの分類

根拠は[固定native overlay][native]。既存エンジン12ファイル、build/recipe側3ファイル、新規自前5ファイルに分かれる。20を「上流内部20箇所の不可避な改造」と数えない。複数責務のあるファイル全体を削除可能とも判断しない。

| 対象 | 残す理由／外へ出せる部分 | 更新負担と判断 |
| --- | --- | --- |
| `include/violite.h`, `sql-common/client.c` | memory Vio種別とclient情報への対応 | callback機構は既存。独自enumの追加まで不可避とは未証明。既存種別の流用はsocket/secure-transport判定も確認してから。現状維持 |
| `libmysqld/lib_sql.cc` | THD生成、embedded/native Protocol分岐、glue include | bootstrapのtext C APIはまだ必要。既存関数の分岐は現在の併存方式の費用。includeを外へ出すだけでは解消しない |
| `sql/protocol.cc`, `sql/protocol.h` | server用出力の有効化・命名分離 | 通常packet生成は上流を利用。独自serializerへ置換しない。上流にはvirtual関数があるが`Protocol_binary`はfinalで、単純な派生クラス追加だけでは全差分を消せない |
| `sql/net_serv.cc` | server側NET有効化、入力header上限・出力packet上限 | 判定は長さ取得後、allocation/body読取りやpacket送出の前に必要。方針定数はglueへ置けるが、hostの事後通知では置換できない |
| `sql/sql_acl.cc` | handshake/parser有効化、capability、固定root/skip-grantsとの接続 | 上流parserを残し、profile方針を外付けに集約する候補。通常のサーバ認証へ置換すると製品契約が変わる |
| `sql/sql_class.h`, `sql/sql_class.cc` | THDのnative識別、cleanup内のrollback結果通知 | 識別は併存方式の費用。rollback結果は元のcleanup順序から報告する必要がある。cleanup全体の再実装や外側からの成功推測はしない |
| `sql/sql_parse.cc` | native dispatch有効化、実行直前fence、command/profile長検査 | policyの実体は外へ出せるが、判定位置は必要。先頭byteだけをhostが読んで済ませる案はwire再実装へ戻る |
| `sql/sql_prepare.cc`, `sql/item.h` | native decoder有効化、embeddedとの分岐、拒否時のconversion回復 | **最も注意する内部依存。** `PValue_simple`等の表現保存/復元は上流変更時に意味のレビューが必要。外付け関数へ移すだけでは減らない |
| `cmake/os/WASIX.cmake`, `wasm/CMakeLists.txt`, `wasm/lite4mariadb.c` | coherent build、native entry、text bootstrap/restore | build/recipeの責務。旧resident入口の除去は#127で実施済み。再び未着手の削減案として扱わない |
| `libmysqld/mariamem_control_abi.h`, `libmysqld/mariamem_wire_probe.inc`（新規） | callback ABIとVio/session glue | 自前sourceとしてパッチ外へ抽出できる候補。THD/NETの初期化・cleanup順序という内部依存は残る |
| `wasm/issue65_control.cc`, `wasm/issue65_deadline.h`（新規） | queue、制御、timer、native worker管理 | 自前source。hostへ方針を寄せる余地はあるが、移動だけでMariaDBの既存12ファイルへの変更は消えない。全移設は先行させない |
| `sql/mariamem_wire_policy.h`（新規） | 既にdecodeした値に対するprofile制限 | 自前glueとして所有。第二のparserやprepared registryを追加しない |

追加5ファイルの最終postimageはdescriptorのhashと一致した。新規自前sourceをdiffで運ぶ現在の形は整理対象だが、パッチ外への抽出は「所有の整理」であり、内部依存削減とは別に報告する。

## 実際に削減する候補と、単純には削減できない箇所

**小さく削減できる候補：native profileに残る旧embedded TIME修正。**
[native-prepared.patch][prepared]の`MAX_TIME_WIDTH → MAX_TIME_FULL_WIDTH`はembedded版に当たる。
後続native overlayはその関数を`set_param_time_embedded`へ改名し、native sessionは別の上流関数へ分岐する。
[上流native関数][upstream-prepare]は既に`MAX_TIME_FULL_WIDTH`を使う。
bootstrapはtext C APIであり、旧MYSQL_BIND呼出しは#127で除去済み。通常native経路には不要と考えられるが、全entryの非到達や削除後のbuild/runtime同等性を今回証明したわけではない。
削除するならnative profileだけを対象にし、legacy-fullの修正、既存TIME oracle、完全source proofを維持する。これは小さな削減で、総費用改善の主根拠にはしない。

**残す理由が具体的な箇所：prepared拒否後のconversion回復。**
上流`setup_conversion_functions`は型情報を更新した後に値のdecodeへ進む。現候補はその後の拒否で以前の型状態を戻すため、`sql/item.h`の保存/復元と`sql_prepare.cc`の失敗経路に変更を加える。
Vio callbackはraw bytesの入出力なので、この意味上の境界には届かない。hostで同じ判定を行うには型・LONG_DATA等の追跡が必要になり、元の問題へ戻る。
現契約のままでは局所的なguest修正を残すのが妥当。将来の上流が同じ拒否/回復を提供するか、上流側に安全なhookができた時に置換する。今回見た上流経路には、そのまま利用できる回復callbackを確認できなかった。
「同じ契約を保つには現在のmemcpy方式だけが唯一」とまでは証明していない。配置だけ変えて解決済みにしない。

**Protocolの分岐は現構成に必要だが、絶対的な最小ではない。**
bootstrapのtext C APIを使い続けるため、全translation unitを単純に通常server扱いにする案は採れない。bootstrap自体をnative化すれば減る可能性はあるが、初期SQL結果、routine schema、restoreまで変わる。今回の小さな整理へ混ぜない。

## Native以外のパッチ・source書換えも更新費用に含める

| 系統 | 内容と落とし所 |
| --- | --- |
| common-portability | CMake/SDK設定、libc不足、memory/lock/timezone、absolute datadir等。getloginやdirectory fsyncなどOS境界のshim化候補と、エンジンのpath修正を分ける。失敗を一律成功へ変えるshimで代替しない |
| redo / buffer-alignment | WASIXの保護変更不可と、InnoDB要求alignmentへの対応。意味を確認した平台互換層の候補。単にmprotect/mallocを広く置換すると他の呼出しにも影響するため、今回削除可能とは判定しない |
| native-prepared | 上述のTIMEとbootstrap metadata allocation失敗のguard。後者はtext bootstrapのため残す |
| shared-source | recipe、stat/readability、UCA prepared table、pagecleaner sync-LSN修正が混在。UCAは既存最適化、pagecleanerはエンジン内部の同期修正で、wire方針をhostへ移しても消えない |
| pagecleaner-observe | #138分岐の観測。実験用だが現証跡の入力。停止中#138を再開したり、未観測を削除で免除したりしない |
| `guest_init_hooks.py` | 6ファイルへの診断挿入。patchファイルではないが上流anchorを追う費用。純粋な計測と必要な起動診断を分けて扱う |
| `guest_auth_hooks.py` | 2つのauth plugin sourceへの鍵検査・初期化結果・self-test挿入。製品側からready検査を呼ぶため、全てを不要実験コードとは扱えない |
| prepared UCA/routine schema、link wrappers、生成binding | table/schema/ABIの確認も毎版のレビュー対象。glueを別ファイルにしてもworker完全本文・TLS/ABIの確認は消えない |

これらは[prepare_guest.py][preparation]の実経路と、descriptor参照先を調べた分類。全OS互換処理の代替実装や、上流全call graphの調査はしていない。

## 検出網と既存条件

| 確認したいもの | 現在の検出手段と限界 |
| --- | --- |
| 版混在・patch内容・適用前後source | `guest_input.apply_series`の全pre/postimageとfuzz=0、selected preparation検査。変化を検出するが意味上の互換性は証明しない |
| worker本文・TLS/ABI | `tests/test_selected_binding.py`のconstant/control/duplicate、TLS/noop/ABI負例。無関係な古いguestを通さない。保守負担が大きいかはCIでは検出できない |
| host identity・予約・退役 | `internal/nativewire/owner_test.go`とpublic capacity検査。nativeの実join/cleanup全条件の代替ではない |
| prepared回復・limits・fence・設定 | 元G1/G2/P1、lifecycle、#129/#130のoracleを使う。現selected workflowは初期public5 Go testsとPython smoke中心で、これらの全再接続は未完。既存の緑だけで修正後の等価性を認定できない |
| 不要な内部接点が増えること | 現CIは上流依存の数・理由や手作業費用を判定しない。この表の接点単位でレビューする。行数・PASS数を代理指標にしない |

確認済みで再調査不要：旧resident入口とlegacy metadata/bind修正の縮約（#127/#137）、hostのidentity発行、7パッチ本文の13.0.2→13.2一致。
支持された非圧縮NETでのread-ahead迂回は既に除外済みで、この懸念を理由に新hookを増やさない。

未完：全設定・実fault/join・元oracle・installed wheelの両OS受入れ、恒久CI、consumer/性能、最終監査。#138は停止/未免除。今回の調査で条件を落とさない。
公開ガイド4点、canonical生成ledger、stable guest入力について今回新たな変更・矛盾はない。native採用後の整合性はまだ認定しない。
候補の`runtime_wire.go.txt`等に残るexperiment表記は現在の未採用状態と整合するが、正式所有へ移す際の整理対象。

## 次の具体的な作業単位

1. **自前glueの所有を分離する（#134/#131）。** 追加5ファイルをversionedな自前sourceとして運び、上流diffは接続点だけにする案を作る。準備後の全sourceが一致することを出口にする。この抽出自体は内部依存削減と数えず、新buildを目的にしない。既存#127/#137をやり直さない。
2. **残す上流接点を維持しながら、native専用の不要修正を削る。** 最初の小候補は上記TIME hunk。新しいguestになるため、source proof/正規生成/bindingと影響する元oracleが必要。単独の費用測定buildは追加せず、必要な公開受入れcohortにまとめる。手直しが大きければ小削減のために範囲を拡大しない。
3. **host状態の残作業は別境界として進める（#131）。** queue/credit/総pendingと輸送watchdogを一つずつ扱い、guestには同期・実行判定・cancel/joinを残す。controller全移設、direct callback化、bootstrap native化を同時にしない。

順序1–3は今回の推奨であり実装済みではない。#132の全受入れや#128の費用判断を、これら全ての完了待ちに変更しない。今回の結論だけで境界の方針は判断でき、製品化完了までレビューを延期する必要はない。
次版で広範なProtocol/prepared修正が毎回必要になる、又はglue分離が同等以上の内部layout追従をhostへ持ち込む場合は、この方式の利点を再評価する。

今回の成果はsourceに基づく境界の判断と削減候補。上流への変更を完全になくせる証明や総工数削減率ではない。過去の実験フォルダ・binaryに依存せず、生成物は作成していない。

[descriptor]: https://github.com/masahitojp/mariamem/blob/37e79f644e53bd8a38182621f66a58a87e38289a/guest/versions/13.2.0/native-text.json
[native]: https://github.com/masahitojp/mariamem/blob/37e79f644e53bd8a38182621f66a58a87e38289a/guest/versions/13.0.2/inputs/guest/experimental.patch
[owner]: https://github.com/masahitojp/mariamem/blob/37e79f644e53bd8a38182621f66a58a87e38289a/internal/nativewire/owner.go
[prepared]: https://github.com/masahitojp/mariamem/blob/37e79f644e53bd8a38182621f66a58a87e38289a/guest/versions/13.0.2/inputs/guest/patches/13.0.2-native-prepared.patch
[upstream-prepare]: https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/sql/sql_prepare.cc#L677
[upstream-vio]: https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/include/violite.h#L199
[upstream-protocol]: https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/sql/protocol.h#L243
[upstream-conversion]: https://github.com/MariaDB/server/blob/c9f28ba0afec6d29e4688255dce8caaf7e91233d/sql/sql_prepare.cc#L4762
[preparation]: https://github.com/masahitojp/mariamem/blob/37e79f644e53bd8a38182621f66a58a87e38289a/scripts/prepare_guest.py
