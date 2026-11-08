# Issue65 — MariaDB更新コストの初期棚卸し

2026-11-08。調査source_commit: `9f8dad6cb1b3730f190ed3cdd5176e6bdff9dadd`。
MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`（12.3.3）。

**結論：native wireの成立は確認済みだが、MariaDB更新コストの低下は未実証。現在のパッチを最小構成として製品化するのは早い。**
推奨はC3の受入れ条件を保ったまま、まず起動時embedded依存とprepared内部状態への依存を整理すること。
最大の反対材料は、配置を変えてもMariaDB内部APIへの依存が残り、再検証費用だけ増える可能性。
したがって大規模な再配置を先に実装せず、以下の限定したsource調査と小さな比較で削減可能性を判断する。
この記録は設計候補の採用レビューではなく、既存sourceの棚卸し。build・更新試行・新runtime実行は未実施。

## 目的と比較の境界

Humanが明確化した目的は、MariaDBの更新に必要な修正・調査・検証を減らし、早く追従すること。
wire縮小、host移設、glue集約は手段。行数や動作PASSだけで達成とはしない。

[機械可読inventory](evidence/upgrade-patch-inventory.json)は実験パッチの26区画、20ファイル、
うち新規4ファイルを拘束する。2,013行はパッチテキストの長さ。
同じファイルへの後続変更を含むため、追加/削除行数は最終sourceの純増や不可避な変更量ではない。
既存のportability/prepared/source.patch、auth/init/UCA等のsource書換え、生成bindingも別の更新負担として残る。
このinventoryはそれらを含む全guest変更の一覧ではない。

## パッチ20ファイルの分類

分類は主たる役割。複数の責務があるファイルを、丸ごと移動/削除できるとは判断しない。
「接続点」は現在のembedded/native併存構成に必要という意味で、代替構成まで不可避と証明していない。

| ファイル | 役割・再配置候補 | 更新時に確認するもの |
| --- | --- | --- |
| include/violite.h | memory Vio種別の接続点 | Vio enum/利用側との整合。独自種別追加の必要性は未再検証 |
| sql-common/client.c | memory種別を既存transport情報へ接続 | Vio種別の扱い。glue化だけでenum参照は消えない |
| libmysqld/lib_sql.cc | embedded/native Protocol切替、THD生成、probeのinclude | 既存embedded出力とnative出力。起動にもembeddedを使用 |
| libmysqld/mariamem_control_abi.h（新規） | 独自glue ABI | callbackの契約。自前配置へ移す候補 |
| libmysqld/mariamem_wire_probe.inc（新規） | Vio実装、session起動/停止、イベント通知 | 自前glueへ集約する候補。ただしTHD/NET初期化・cleanup順序は内部依存 |
| sql/net_serv.cc | server側NETの有効化、入出力上限 | buffered readでも適用する制限。host通知では代替不可 |
| sql/protocol.cc | native出力をembedded buildで使うための分離 | native/embedded二経路の必要性、Protocolの変更 |
| sql/protocol.h | 上記の宣言 | 上流クラスと宣言の整合 |
| sql/sql_acl.cc | native handshake/auth初期化とprofile | skip-grants、capability、initial DB/charset、通常の認証との分岐 |
| sql/sql_class.cc | THD構築とrollback結果hook | cleanup順序と失敗通知。hostへ結果を遅延通知するだけでは安全性を代替できない |
| sql/sql_class.h | native判定とTHD constructor | THD layout/constructor依存。native専用化で減らせるか未確認 |
| sql/sql_parse.cc | native command有効化、dispatch直前gate、profile検査 | SQL開始/captureの原子性とcommand長。policyと最終実行gateを分離 |
| sql/item.h | native temporal経路、conversion保存/復元 | **PValue_simple等の内部表現依存**。glueへの移動だけでは解消しない |
| sql/sql_prepare.cc | native decode有効化、入力検査、失敗時復元、観測counter | cached type/long-data/charset/alias/NULL fallbackと拒否後の回復 |
| wasm/CMakeLists.txt | controller結合と旧main改名 | 正式なentry/build構成へ整理する対象 |
| cmake/os/WASIX.cmake | native defineの全translation unitへの適用 | mixed buildを防ぐ。target単位へ狭める可否は未検証 |
| wasm/lite4mariadb.c | native向けbootstrap/shutdown | embedded C APIを使う起動処理との接続 |
| wasm/issue65_control.cc（新規） | 独自controller、queue、timer、worker管理 | host方針へ移せる部分とnative同期/停止を分ける。新規自前sourceだが内部API依存はある |
| sql/mariamem_wire_policy.h | 独自profile方針 | 制限の定義を集約可能。呼出し位置の変更は別の安全性問題 |
| wasm/issue65_deadline.h（新規） | 独自deadline計算 | 上流より自前policy依存。first-byte/overflow/stale-token契約を保つ |


## 判明した二つの縮約上の障害

1. **bootstrapにもembeddedが必要な現構成。** `issue65_bootstrap`は`l4m_open()`と
   `routine_bootstrap(g_mysql, restore)`を実行してからbootstrap接続を閉じる。
   `guest/source.patch`の`mysql_real_connect`/初期SQL、`guest/routine_bootstrap.inc`の`mysql_query`に
   到達する。したがって「公開sessionがnativeなのでembedded経路を全削除」は現状のままでは成立しない。
   起動でtext C APIを使うことから、旧prepared経路まで必要と推論することもできない。
2. **prepared回復は内部表現へ依存。** `sql/item.h`に追加したconversion保存/復元は
   type handler、unsigned flag、`PValue_simple`のobject representation等に依存し、
   `sql_prepare.cc`の拒否時に復元する。これはupstream decoderを呼ぶだけのglueより追従確認が多い。
   host側にdecoderを戻す案は本来の重複削減と衝突する。まず上流の状態変更点と
   prevalidation/rollback境界をsourceで追い、現在の契約を保って依存を減らせるか確認する。

## 次の限定作業と進行条件

次は**起動・公開native・旧preparedそれぞれの到達経路の一覧**を作り、
bootstrapに必要なembedded機能と、互換用に残しているだけの機能をsourceで分ける。
上記で意味のある削減候補が見えた場合だけ、別の小さな実験で同じguest入力・同じoracleを使い比較する。
最初からbootstrap/Protocol/prepared/controllerを同時に変更しない。

検出根拠は既存G1/G2の拒否後回復・descriptor/charset/LONG_DATA、P1-bのtimeout8/負例3、
C2の公開factory負例、native lifecycle22とworker join/capture-debt controls。
これらは過去の固定候補での証拠であり、配置変更後のPASSではない。
C3の設定継承・実worker/relay/debt・公開Linux受入れを削除も完了扱いもしない。

不足証拠は、代替構成でのbuild/runtime等価性と別MariaDB版への実際の追従量。
source到達性の整理は新build/CI不要。その後の小実験は変更案を具体化し、build回数・時間・disk予算を
定めてから進める。更新先の版はまだ選んでいない。製品採用とreleaseも未承認。

## ローカル依存と保存

調査入力は上記commitの追跡sourceとmanifestであり、過去の実験workspaceは参照しない。
成果はこの文書とhash付きinventory。調査用checkoutはcommit/push後に削除する。
6件の歴史的public-source FAIL、正式生成経路への移行、clean環境での再現確認は引き続き残件。
