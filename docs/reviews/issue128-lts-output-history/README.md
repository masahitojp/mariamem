## Human確定：系列を選べる提供方法とLTSに沿う保守（2026-11-12）

- 当面は12.3 LTSのみ。将来は利用者がMariaDB系列別の提供物を選ぶ。
- mariamemのバージョン表記から対象系列を判別できるようにする。Humanの例は `0.7.1-12` / `0.7.1-13`。これは命名意図の例であり、正式なtag/package表記や0.7.1のrelease指示ではない。Go/Python等のバージョン規則・解決順序との整合は配布設計時に確認する。正確なengine版（例12.3.x）は入力/provenanceにも明示する。
- **提供する各系列の保守期間は、そのMariaDB LTSの保守期間に従う。** 新LTSを提供しただけで旧系列の利用者に移行を迫らない。単一の実行物内でengineを切り替える方式を要求しているわけではない。
- 従来の「直近2つ程度」は併存の想定規模。上流LTSの期間が重なる場合に「3系列目が出たから」と独自に旧系列の保守を打ち切らない。過去の全LTSの新規提供や11.4/11.8対応を今回要求するものではない。
- 具体的な終了日の確定時には、参照するMariaDB公式の保守区分・期間を明記する。Community/商用延長等の区分や具体日付を今回独断で決めない。

#128の費用比較では、系列別の入力/patch/adapterに加え、同じmariamem改修を複数系列へ適用し、各系列を生成・検証・識別可能に配布する増分を計上する。上流LTS期間に沿う併存を前提にし、必ず2系列以下とは仮定しない。

今回確定したのは提供・保守方針。命名の技術設計、配布実装、output候補採用、追加CIやreleaseは実行しない。

---

## Human方針の訂正：将来は直近2つ程度のLTSを提供（2026-11-12）

- **当面の対応対象は12.3 LTSのみでよい。** 11.4/11.8の追加提供や、今すぐ2系列を製品化する指示ではない。
- **将来は直近2つ程度のLTSを提供できる構成を目指す。** 新LTS提供時に利用者へ即時移行を迫らず、旧LTSを使い続けられる移行猶予を持たせる。
- 直前の「最新LTSのみ」「複数LTSの並行提供費用は前提にしない」は本訂正で置き換える。rolling/Preview版の製品対応は基本路線に含めず、13.2等は事前評価として区別する。
- 提供方法、旧系列の保守期間・終了条件、正確な系列数の上限は未決。「常にちょうど2系列」「同一プロセスで両engineを動かす」という実装要件までは決めない。

費用評価は **①新LTSを追加する負担、②旧/新LTSを併存させる負担** に分ける。②には版別のadapter/patch分岐、共通修正の適用・逆移植、系列ごとの生成/binding/CI/配布の増分を含める。共通で使える部分と系列固有部分を区別し、単純に全費用を2倍にしない。

[先ほどのLTS間source比較](https://github.com/masahitojp/mariamem/issues/128#issuecomment-6818523501)の観測結果は変わらない。raw-row接点が安定していた事実は、更新時の修正だけでなく、版別分岐を抑えられる可能性の材料にもなる。ただし2系列での実生成・受入れや配布方式は未検証。output候補の採否・製品化再開は引き続き未決。

---

以下は訂正前の前提で記録した調査。source観測値は維持し、提供方針と費用評価の前提は上記で置き換える。

## 最新LTSのみの方針と、出力接点のLTS間比較（2026-11-12）

### 前提（Human指定）

mariamemの基本路線は**最新LTSのみを対応対象とする**。複数LTSの恒常的な並行サポートや、rolling/Preview版の逐次製品対応を費用の前提にしない。次のLTS採用のための一時的な旧/新比較、過去版の証跡保存は別であり、禁止しない。LTS系列内の保守更新への追従も評価対象。切替の期限や旧mariamemリリースの保守期間までは今回決めていない。

従来の「12.3.3と13系を並行に扱える構成」は、比較・移行のための準備能力として利用できるが、複数系列の永久サポート義務とは解釈しない。13.2の事前評価は製品サポートではない。

### 調査対象・方法

LTS系列11.4→11.8→12.3は[公式発表](https://mariadb.org/11-8-is-lts/)および[2026年8月の保守リリース](https://mariadb.org/mariadb-server-12-3-11-8-11-4-and-10-11-q3-2026-maintenance-releases-and-goodbye-10-6/)で確認。

- **初回GAの比較**：11.4.2→11.8.2→12.3.2。各系列開始時点の累積差を見る。
- **同時期の保守版比較**：11.4.13→11.8.9→12.3.3。現行12.3.3に揃えた断面。修正の逆移植によって差が消える場合があるため、これだけで歴史的に変更なしとはしない。
- upstreamの5ファイル全体を固定commitから取得し、全差分を読んだ。GitHub APIのtag objectをcommitまで解決し、commit APIでも型を確認。build/benchmarkは行っていない。
- 下の数値はunified diffによる追加/削除行数。**両端の正味の差であり、途中のcommit件数・変更頻度・全履歴の累積churnではない。** runtime、ABI、呼出先/allocator等の推移的依存全体は検証していない。WASIX patch適用後の差分でもない。

### 結論

**このLTS標本では、試作が直接借りるraw-rowの構造・producer・受渡し部分は安定していた。内部依存という理由だけで大きな毎版修正を想定する根拠は弱い。** これは部分再利用の保守性に有利な具体的材料であり、以前の「内部依存が増える」という懸念の重みを下げる。

ただし、現行fetch経路も変更は小さく、この比較から大幅な工数短縮までは言えない。**「不安定な内部接点を抱える案」より「過去2回のLTS間で安定した接点に、自前の変換を置き換える案」として再評価するのが妥当。** 採用推奨の確定や製品化再開は今回行わない。

### 機能単位で見た差

| 接点/責務 | 初回GA間で見つかった差 | 費用評価への意味 |
| --- | --- | --- |
| `MYSQL_ROWS` / `MYSQL_DATA` / `MYSQL_STMT`の定義 | 11.4→11.8→12.3で当該定義に差なし。mysql.hの差はエラー名aliasだけ | 直接アクセスする定義の変更対応は、この標本では見当たらない。含まれるMEM_ROOT等の推移的ABI安定性までは証明しない |
| embedded `Protocol_binary::write`、`emb_read_binary_rows`、execute/query-result経路 | 当該コードに差なし。lib_sql.cc唯一の変更は12.3側の接続DB選択/名前保持 | raw行のlength、copy、linked list、result移管の方式はこの範囲で不変 |
| store/free/reset経路（両案で利用） | 11.8.2→12.3.2の`mysql_stmt_store_result`で未使用field変数と加算を削除。free/reset部分に差なし | 共通のレビュー項目。意味を変える所有権修正は今回のdiffに見当たらない |
| 現行のfetch/値変換側 | 11.4→11.8でtruncation判定macro変更、FLOAT取得を`float4get`から`get_float`へ変更 | Bが経由しなくなる処理に実変更あり。ただしAのmariamemコード修正が必要だったとは未確認。上流内部で完結する修正をそのまま節約工数にしない |
| binaryの値格納 | 11.8.2→12.3.2でfloat/doubleの負のゼロを正のゼロへ正規化する各4行が追加。同時期保守版間では差なし | 実際に表現が変わる例。Bは上流の行bytesを受け取る。ただしAも上流行をfetchするため、自動的にBだけの追従利益とは言えない。自前再encode/validatorが追加対応を要するかは別の対応表で評価 |
| metadata/終端/status/OUT等 | bulk unit resultの終端処理、OUTパラメータ破棄、metadata用text bufferの割当エラー処理などに差あり | 出力を丸ごと「不変」とは言えない。raw行だけ再利用してもこれらの公開契約確認は残る。native NET全体への移行理由にはしない |

### 全ファイル差分の規模

`+追加/-削除`。関係のない変更・コメントも含むので、変更量をそのまま保守工数へ換算しない。

#### 初回GA

| ファイル | 11.4.2→11.8.2 | 11.8.2→12.3.2 |
| --- | --- | --- |
| `include/mysql.h` | +2/−0 | +2/−0 |
| `libmysqld/libmysql.c` | +3/−5 | +3/−5 |
| `libmysqld/lib_sql.cc` | +0/−0 | +13/−1 |
| `sql/protocol.cc` | +43/−44 | +17/−8 |
| `sql/protocol.h` | +11/−11 | +0/−0 |

#### 同時期保守版

| ファイル | 11.4.13→11.8.9 | 11.8.9→12.3.3 |
| --- | --- | --- |
| `include/mysql.h` | +2/−0 | +2/−0 |
| `libmysqld/libmysql.c` | +3/−5 | +1/−1 |
| `libmysqld/lib_sql.cc` | +0/−0 | +13/−1 |
| `sql/protocol.cc` | +32/−39 | +8/−7 |
| `sql/protocol.h` | +7/−5 | +0/−0 |

### 指標への反映と次の判断材料

「内部依存があるか」ではなく、**LTS間で実際に変更された接点と、その変更でmariamem側に必要な作業**を指標1/2へ加える。複数LTSを同時に維持する分岐数ではなく、新LTSへ切り替える際の作業を比較する。

次に既存sourceで対比する項目は、(a) raw境界の版別修正が必要だった箇所、(b) fetch側の変更が現行adapterに要求した修正、(c) 負のゼロ等の表現変更で両案の自前コード/検査に残る対応。上流の変更があってもadapter無修正なら「調査は必要、修正不要」と記録する。buildの再実行ではこの区別は埋まらない。

本調査は直接接点5ファイルの両端比較まで。全履歴で一度も壊れていない、将来も変更不要、全体の更新費用が減った、という保証ではない。初回GA間にはLTS内の修正も含まれ、純粋な系列移行費とは分離していない。過去の実移行日に使った版の再現や全commit履歴の調査は未実施。

### 固定した入力

取得元は `MariaDB/server`。以下のsource_commitの各5ファイルを比較。再確認は各SHAのファイル取得とunified diffで可能。tag名の移動やローカル実験folderに依存しない。

| tag | tag_object_sha | source_commit |
| --- | --- | --- |
| mariadb-11.4.2 | `9b100a109a89a38d07ff7ad275d1dd1f69d7c3ac` | [`3fca5ed772fb75e3e57c507edef2985f8eba5b12`](https://github.com/MariaDB/server/tree/3fca5ed772fb75e3e57c507edef2985f8eba5b12) |
| mariadb-11.8.2 | `207e8823d19949e63fd985f19ffc1c111846ba68` | [`8d36cafe4fc700e6e577d5a36650c58707e76b92`](https://github.com/MariaDB/server/tree/8d36cafe4fc700e6e577d5a36650c58707e76b92) |
| mariadb-12.3.2 | `13e640debb54541d25390644cc63756f213bb729` | [`9f98f82b14a9b939834281672b6d0cf965db69a3`](https://github.com/MariaDB/server/tree/9f98f82b14a9b939834281672b6d0cf965db69a3) |
| mariadb-11.4.13 | `c02896e01b3e282f2377c70a5dcc38811716b1b3` | [`170b1d70737be6f134448f51713cdc1ae215b420`](https://github.com/MariaDB/server/tree/170b1d70737be6f134448f51713cdc1ae215b420) |
| mariadb-11.8.9 | `7e2a4ce676800d6d898e98100f88c7f0ad6db386` | [`bf9193a939f515e95dd8def1a5468088c91cede6`](https://github.com/MariaDB/server/tree/bf9193a939f515e95dd8def1a5468088c91cede6) |
| mariadb-12.3.3 | `bd852bcd567fedc89ad4521e2f1a64c7a1e0d0f0` | [`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`](https://github.com/MariaDB/server/tree/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e) |

<details>
<summary>取得した30ファイルのSHA256と固定URL</summary>

```json
[
  {
    "tag": "mariadb-11.4.2",
    "path": "include/mysql.h",
    "sha256": "f117fb11798dbf86be2bdac82838f5e8ea6f404d210057fffe490749f249f628",
    "url": "https://raw.githubusercontent.com/MariaDB/server/3fca5ed772fb75e3e57c507edef2985f8eba5b12/include/mysql.h"
  },
  {
    "tag": "mariadb-11.4.2",
    "path": "libmysqld/libmysql.c",
    "sha256": "eb02130a5bb0ce5700084d27eefc749a5aa8d336a7957b8f635debe50cfb5ed5",
    "url": "https://raw.githubusercontent.com/MariaDB/server/3fca5ed772fb75e3e57c507edef2985f8eba5b12/libmysqld/libmysql.c"
  },
  {
    "tag": "mariadb-11.4.2",
    "path": "libmysqld/lib_sql.cc",
    "sha256": "4da6ca787eea5e91673f5b8fb2a5f0a753c4871d7a169413f2d2a87f8fcccce6",
    "url": "https://raw.githubusercontent.com/MariaDB/server/3fca5ed772fb75e3e57c507edef2985f8eba5b12/libmysqld/lib_sql.cc"
  },
  {
    "tag": "mariadb-11.4.2",
    "path": "sql/protocol.cc",
    "sha256": "a405f4ed5ca06aa641099fcb5f78e3e8932a402b0667b2486b330d33ce4e4fc4",
    "url": "https://raw.githubusercontent.com/MariaDB/server/3fca5ed772fb75e3e57c507edef2985f8eba5b12/sql/protocol.cc"
  },
  {
    "tag": "mariadb-11.4.2",
    "path": "sql/protocol.h",
    "sha256": "fa44614e8d8b051952e9c1460289c629eef724804237bfea453c5289cf3d4f2b",
    "url": "https://raw.githubusercontent.com/MariaDB/server/3fca5ed772fb75e3e57c507edef2985f8eba5b12/sql/protocol.h"
  },
  {
    "tag": "mariadb-11.8.2",
    "path": "include/mysql.h",
    "sha256": "8a6cc1950a69219b060e31b90001e7557f6dabff36c19fd2ea51cbc68450deaf",
    "url": "https://raw.githubusercontent.com/MariaDB/server/8d36cafe4fc700e6e577d5a36650c58707e76b92/include/mysql.h"
  },
  {
    "tag": "mariadb-11.8.2",
    "path": "libmysqld/libmysql.c",
    "sha256": "233d1c24a89c8ff797b304a8f83b7542ea2b886300dd3ba6d2d0737f9b246110",
    "url": "https://raw.githubusercontent.com/MariaDB/server/8d36cafe4fc700e6e577d5a36650c58707e76b92/libmysqld/libmysql.c"
  },
  {
    "tag": "mariadb-11.8.2",
    "path": "libmysqld/lib_sql.cc",
    "sha256": "4da6ca787eea5e91673f5b8fb2a5f0a753c4871d7a169413f2d2a87f8fcccce6",
    "url": "https://raw.githubusercontent.com/MariaDB/server/8d36cafe4fc700e6e577d5a36650c58707e76b92/libmysqld/lib_sql.cc"
  },
  {
    "tag": "mariadb-11.8.2",
    "path": "sql/protocol.cc",
    "sha256": "7003754e6577513597b7c1dbca307c541cedae066ecafde385b37d7c6ced0e9d",
    "url": "https://raw.githubusercontent.com/MariaDB/server/8d36cafe4fc700e6e577d5a36650c58707e76b92/sql/protocol.cc"
  },
  {
    "tag": "mariadb-11.8.2",
    "path": "sql/protocol.h",
    "sha256": "8640f0b6ee5b9014492c40556dbf324f96f00f43b6fc55ea28baabd5a9705689",
    "url": "https://raw.githubusercontent.com/MariaDB/server/8d36cafe4fc700e6e577d5a36650c58707e76b92/sql/protocol.h"
  },
  {
    "tag": "mariadb-12.3.2",
    "path": "include/mysql.h",
    "sha256": "aff93c3ce50a8d3e2e56d42c9e2150af2cfc61c139098fae08d16c8427cd8a7c",
    "url": "https://raw.githubusercontent.com/MariaDB/server/9f98f82b14a9b939834281672b6d0cf965db69a3/include/mysql.h"
  },
  {
    "tag": "mariadb-12.3.2",
    "path": "libmysqld/libmysql.c",
    "sha256": "d8f0a9d4f7c638bd91d11453e1207ccfe6d3cda85f9c3082e51c37a69c9fc60c",
    "url": "https://raw.githubusercontent.com/MariaDB/server/9f98f82b14a9b939834281672b6d0cf965db69a3/libmysqld/libmysql.c"
  },
  {
    "tag": "mariadb-12.3.2",
    "path": "libmysqld/lib_sql.cc",
    "sha256": "5de14e2760c775701fe7dff7a9cbf4d47266990081f0abf94e88942a943d377e",
    "url": "https://raw.githubusercontent.com/MariaDB/server/9f98f82b14a9b939834281672b6d0cf965db69a3/libmysqld/lib_sql.cc"
  },
  {
    "tag": "mariadb-12.3.2",
    "path": "sql/protocol.cc",
    "sha256": "84f3e4a71fc6a44caf3af80a8a0d9b155ce43e9466a55daafc5744c422aa5242",
    "url": "https://raw.githubusercontent.com/MariaDB/server/9f98f82b14a9b939834281672b6d0cf965db69a3/sql/protocol.cc"
  },
  {
    "tag": "mariadb-12.3.2",
    "path": "sql/protocol.h",
    "sha256": "8640f0b6ee5b9014492c40556dbf324f96f00f43b6fc55ea28baabd5a9705689",
    "url": "https://raw.githubusercontent.com/MariaDB/server/9f98f82b14a9b939834281672b6d0cf965db69a3/sql/protocol.h"
  },
  {
    "tag": "mariadb-11.4.13",
    "path": "include/mysql.h",
    "sha256": "f117fb11798dbf86be2bdac82838f5e8ea6f404d210057fffe490749f249f628",
    "url": "https://raw.githubusercontent.com/MariaDB/server/170b1d70737be6f134448f51713cdc1ae215b420/include/mysql.h"
  },
  {
    "tag": "mariadb-11.4.13",
    "path": "libmysqld/libmysql.c",
    "sha256": "a3ead82a0918208c23f209d93521543e668dad530d333326a5b4f8c7c157d714",
    "url": "https://raw.githubusercontent.com/MariaDB/server/170b1d70737be6f134448f51713cdc1ae215b420/libmysqld/libmysql.c"
  },
  {
    "tag": "mariadb-11.4.13",
    "path": "libmysqld/lib_sql.cc",
    "sha256": "4da6ca787eea5e91673f5b8fb2a5f0a753c4871d7a169413f2d2a87f8fcccce6",
    "url": "https://raw.githubusercontent.com/MariaDB/server/170b1d70737be6f134448f51713cdc1ae215b420/libmysqld/lib_sql.cc"
  },
  {
    "tag": "mariadb-11.4.13",
    "path": "sql/protocol.cc",
    "sha256": "ec85cc0153b7980d00d9297eabb6680d88ac83a25c9af30a7c671721497373c6",
    "url": "https://raw.githubusercontent.com/MariaDB/server/170b1d70737be6f134448f51713cdc1ae215b420/sql/protocol.cc"
  },
  {
    "tag": "mariadb-11.4.13",
    "path": "sql/protocol.h",
    "sha256": "a81c50bb6cb45bc1b55c023dbd54429080ffcbfd2c0993e6a254b1ff9df89223",
    "url": "https://raw.githubusercontent.com/MariaDB/server/170b1d70737be6f134448f51713cdc1ae215b420/sql/protocol.h"
  },
  {
    "tag": "mariadb-11.8.9",
    "path": "include/mysql.h",
    "sha256": "8a6cc1950a69219b060e31b90001e7557f6dabff36c19fd2ea51cbc68450deaf",
    "url": "https://raw.githubusercontent.com/MariaDB/server/bf9193a939f515e95dd8def1a5468088c91cede6/include/mysql.h"
  },
  {
    "tag": "mariadb-11.8.9",
    "path": "libmysqld/libmysql.c",
    "sha256": "0180a69db3385f4ba3d4da74ded9d3a356cad6c8dc38b19036bef9929f061247",
    "url": "https://raw.githubusercontent.com/MariaDB/server/bf9193a939f515e95dd8def1a5468088c91cede6/libmysqld/libmysql.c"
  },
  {
    "tag": "mariadb-11.8.9",
    "path": "libmysqld/lib_sql.cc",
    "sha256": "4da6ca787eea5e91673f5b8fb2a5f0a753c4871d7a169413f2d2a87f8fcccce6",
    "url": "https://raw.githubusercontent.com/MariaDB/server/bf9193a939f515e95dd8def1a5468088c91cede6/libmysqld/lib_sql.cc"
  },
  {
    "tag": "mariadb-11.8.9",
    "path": "sql/protocol.cc",
    "sha256": "026490298e0d8a37844dd336260f1ba968f3561dbd389ff1096bc35929c1e4bd",
    "url": "https://raw.githubusercontent.com/MariaDB/server/bf9193a939f515e95dd8def1a5468088c91cede6/sql/protocol.cc"
  },
  {
    "tag": "mariadb-11.8.9",
    "path": "sql/protocol.h",
    "sha256": "8640f0b6ee5b9014492c40556dbf324f96f00f43b6fc55ea28baabd5a9705689",
    "url": "https://raw.githubusercontent.com/MariaDB/server/bf9193a939f515e95dd8def1a5468088c91cede6/sql/protocol.h"
  },
  {
    "tag": "mariadb-12.3.3",
    "path": "include/mysql.h",
    "sha256": "aff93c3ce50a8d3e2e56d42c9e2150af2cfc61c139098fae08d16c8427cd8a7c",
    "url": "https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/include/mysql.h"
  },
  {
    "tag": "mariadb-12.3.3",
    "path": "libmysqld/libmysql.c",
    "sha256": "d8f0a9d4f7c638bd91d11453e1207ccfe6d3cda85f9c3082e51c37a69c9fc60c",
    "url": "https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c"
  },
  {
    "tag": "mariadb-12.3.3",
    "path": "libmysqld/lib_sql.cc",
    "sha256": "5de14e2760c775701fe7dff7a9cbf4d47266990081f0abf94e88942a943d377e",
    "url": "https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc"
  },
  {
    "tag": "mariadb-12.3.3",
    "path": "sql/protocol.cc",
    "sha256": "84f3e4a71fc6a44caf3af80a8a0d9b155ce43e9466a55daafc5744c422aa5242",
    "url": "https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc"
  },
  {
    "tag": "mariadb-12.3.3",
    "path": "sql/protocol.h",
    "sha256": "8640f0b6ee5b9014492c40556dbf324f96f00f43b6fc55ea28baabd5a9705689",
    "url": "https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.h"
  }
]
```
</details>
