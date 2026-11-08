# Issue65 — bootstrap / native / legacy preparedの到達経路

2026-11-08。source_commit `28e962b0f25fec6c2f7787e9d0338319abdeaf60`。
[前段の棚卸し](upgrade-surface.md)の次のsource調査。

**結論：現nativeの通常起動にembedded text APIは必要だが、旧embedded prepared APIを呼ぶ経路は確認されない。まずbootstrapを旧resident/prepared入口から分離する小実験を推奨する。**
反対材料は、旧経路がexportや同一translation unitの依存として残り、直接呼出しを消すだけでは
上流パッチや生成bindingを減らせない可能性。よって現時点では削除可能・更新負担改善とは判定しない。

## 三つの経路

| 起点 | 呼出し・役割 | preparedとの関係 |
| --- | --- | --- |
| native controllerのmain | issue65_bootstrap → l4m_open → routine_bootstrap → bootstrap MYSQLをclose → Manager開始 | bootstrapはtext C API。旧ps_callは呼ばない |
| nativeのOPEN | Session worker → mariamem_spike_control_session → THD/NET/Vio初期化 → acl_authenticate → do_command → upstream dispatch | native prepared decoderを使用。client_paramsはNULLを要求 |
| 改名された旧main | resident.incのmain（build時issue65_legacy_mainへ改名）→ multi-session worker → op5のps_call → ps_dispatch → ps_prepare/ps_execute | MYSQL_BINDと旧typed envelopeを使用。native controllerのmainとは別 |

根拠はguest/experimental.patch、guest/source.patch、scripts/prepare_guest.py、
guest/resident.inc、guest/prepared_api.inc、guest/routine_bootstrap.inc。
controllerは同じファイルへの3つのpatch区画を順にfuzz=0で適用して再構築した。
[hashと確認結果](evidence/bootstrap-reachability.json)を保存し、一時sourceは削除した。
単にpatchの最初の古いOPEN実装だけを読んだ判断ではない。

bootstrapの詳細：l4m_openでserver初期化とembedded接続、test DB準備を行う。
routine_bootstrapはfreshでmysql schema/proc作成、restoreで構造を検証する。
mysql_query、mysql_store_result、mysql_fetch_row、mysql_select_db等を使い、
mysql_stmt_prepare/executeは使わない。restore検証は省略できない。
終了はManager.shutdown（session退役/join）→ issue65_shutdown → l4m_close。

## 呼ばれていないことと、除去できることの違い

controller内のstaticなconnect/query/embedded_preparedは、再構築後のsourceでそれぞれ
定義以外の呼出し構文がない。embedded_preparedは以前のMYSQL_BIND確認用の残骸と判断する。
ただし機械確認は字句上の直接呼出し検査であり、完全なcompiler/linker call graphではない。

scripts/prepare_guest.pyはwire_api.incへwire_core、prepared_api.inc、resident.incを組み立てる。
experimental.patchはlite4mariadb.cのmainを改名してcontrollerのmainを追加するが、
include構成を取り除いていない。source.patchにはl4m_query_v2等のexport追加も残る。
したがって通常のmainからの非到達を、linked artifactの削除や全entryからの非到達と混同しない。

さらに既存12.3.3-prepared.patchは、embedded bind、result metadata差替え、parameter metadata helper等を
上流に追加する。nativeには不要そうな変更もあるが、TIME幅修正等との混在とnative patchのpreimage依存がある。
パッチファイルを丸ごと外す作業から始めるとsource適用順・hashと関数宣言も変わる。

## 最初の小実験案 — entryの分離

変更案は一つに限定する：**bootstrapに必要なglueと、旧resident/preparedの入口を分離し、
native buildでは旧入口を組み込まずに済むか確認する。** MariaDB内部のdecoderやcapture gateは変更しない。

1. resident.incに同居するauth/routine/init等の共通includeと、bootstrapが使う定義を列挙する。
2. native entryだけを選択する明示的build構成で、legacy main/ps_call/exportの残留を確認する。
   一括して既存prepared.patchを削除しない。canonical release buildへの切替でもない。
3. ビルドできた場合のみ、同じ入力のnative guestでfresh/restore・routine・text/prepared・停止を確認する。
   旧経路欠落が検査を落とすこと自体はnative成功の証拠にしない。
4. 原則として現guestの意味が変わらないことを検証し、生成bindingの変化を明示的に照合する。
   worker join/capture/debtとC3の残件は保持する。
5. 除去できた独自機能、残る上流接点、build/検証の増減を記録して継続/棄却を判断する。

現在は1に必要なsource経路まで確認した段階。代替build、symbol inventory、runtime同等性、
パッチ減量、MariaDB更新試行は未実施。次の実験実行前にbuild回数・時間・disk予算を具体化する。
この文書は一つの案であり、native専用構成への製品変更を採用する判断ではない。

## 今回の検査と保存

source-onlyのpatch再構築、controller直接呼出し、文書の参照・diffを確認した。
新guest build、runtime、benchmark、CIは0。調査checkoutは記録のcommit/push後に削除する。
過去の作業フォルダや残存binaryは入力にしていない。C3と後始末の未完了項目は引き続きIssue65で追跡する。
