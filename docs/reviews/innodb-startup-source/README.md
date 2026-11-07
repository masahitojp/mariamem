# Fresh/Fork差を作るInnoDB既存データ起動のソース調査

**結論:** Forkの追加区間は、保存済みファイルを渡すだけの処理ではありません。
既存DBのチェックポイント・表領域・UNDOを読み検証し、復旧の要否を確認したうえで、
子専用の辞書・トランザクション管理状態を構築する通常起動経路です。
正常停止済みでも復旧の入口を通りますが、それだけで大量のredo再適用を意味しません。

**推奨:** 次に時間を分けるなら、まず`SysTablespace::open_or_create()`の1呼び出しを
測定対象にします。単なるopenではなく、既存システム表領域のヘッダー検証と
doublewrite領域の初期化／読込み関数の呼び出しまで含むことが確認できたためです。そこが支配的なら
さらに中を追い、小さければ元の約6msから残りの工程へ範囲を絞れます。
この調査では計測も最適化も実装していません。

**最も強い反対点:** 復旧のログ走査や辞書ロードの方が高価な可能性があります。
今回のソースだけでは各呼び出しの独占時間を順位付けできません。上記は次に
切る境界の提案で、doublewriteやヘッダー検証が遅延原因だと確定したものではありません。

## 調査の範囲と証拠

- 固定MariaDB12.3.3ソース`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`の8ファイル、約1MiB。
  GitHub contentsを固定refで取得し、Git blob識別とSHA256を確認。
  `srv0start.cc`は以前の詳細診断で参照したソースのSHA256とも一致します。
- canonical guest patch/input、既存計測マーカー、生成Go側の関連情報を読み取り専用で確認。
  上流ソースと移植パッチを同一視しません。local-inputs.jsonに参照したローカル入力のハッシュを保存。
- 最大1時間、ビルド0、新規計測0、heavy CI0。3つの分類と次の1境界を選んで終了。
  #68の調査再開や、復旧・検証を省く変更は行っていません。
- 直前の比較は測定source`398133d0a05f00e53c795f318aec7113261b6cac`、
  guest`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`。
  当該区間の診断平均はFresh/ForkでP1:0.71/6.52ms、P4:0.83/7.22ms。
  これを今回の新しい計測として扱ってはいません。

[先行測定](https://github.com/masahitojp/mariamem/blob/67b88dc4d5d1b997c43568769f90551091a09fc2/benchmarks/freshforkstartup/results/README.md)
· [起動ガイドのPR](https://github.com/masahitojp/mariamem/pull/124)
· [source-map.json](source-map.json)
· [source-files.json](source-files.json)
· [prior-measurements.json](prior-measurements.json)

## 起動分岐はファイルの有無から決まる

`innodb_init()`はシステム表領域の`check_file_spec()`で`create_new_db`を決め、
`srv_start(create_new_db)`へ進みます。Freshは新規作成側、SnapshotのDBファイルが
見えるForkは既存データ側です。アプリの`MARIAMEM_BOOT_MODE=restore`は仮想FSの
復元やroutineの検証に使うフラグで、MariaDB内部のmariadb-backup専用
`SRV_OPERATION_RESTORE`を選ぶものではありません。

以下は成功経路を簡略化したもので、実際のコードにはエラー終了・設定・アップグレード分岐があります。

```text
                         Fresh                         Fork
                         新規DB                         既存DB
                           │                              │
                 古いUNDO/redoの残骸を確認      redo/checkpointヘッダーを読む
                           │                              │
                    システム表領域を作る       システム表領域を開く・検証
                           │                    doublewrite確認処理を呼ぶ
                           └───────────┬──────────────────┘
                               UNDO領域の作成／オープン
                               子のtransaction管理を準備
                           ┌───────────┴──────────────────┐
                    初期ページ・辞書を作る          復旧の入口へ進む
                    （dict_bootも実行）              辞書をboot
                                                    必要なredoを適用
                                                    システム辞書の索引をload
                                                    transaction/UNDO状態をload
                                                    ログ形式・サイズ等を確認
                                                    表領域サイズ等を確認
                           └───────────┬──────────────────┘
                   ここまでが既存の「open/recovery」計測区間
                           ↓
                 doublewrite作成・rollback segment等の後続準備
```

**注意:** 「後続transaction区間」という先行集計の名前は、その前にtransaction関連
処理がないことを意味しません。`trx_sys.create()`や既存DBのtransactionリスト初期化も
広いopen/recovery区間の内側です。またdoublewriteの読込みは区間内、後続の
`buf_dblwr.create()`は区間外で、同じ処理を二重に数えているわけではありません。

## 何を読み、何を検証し、何を作り直すか

| 工程 | 読むもの／確認するもの | 子ごとに作る状態 | Freshとの違い |
|---|---|---|---|
| `find_checkpoint()` | redoファイルの存在・サイズ・形式、ヘッダー/checkpointのチェックサムとLSN | log handle、読み込み用buffer、復旧の開始位置 | 既存DB側で実行。Freshは新規ログを作成 |
| `srv_sys_space.open_or_create()` | システム表領域の先頭ページ、space ID・フラグ・整合性。`read_lsn_and_check_flags()`内でdoublewrite領域を初期化／読込 | fil_systemのspace/fileノードと開いたhandle | Freshは作成側。既存DBだけ先頭ページの検証を通る |
| `srv_undo_tablespaces_init()` | 既存UNDO領域の先頭ページ、space ID・フラグ・破損状態 | 子の表領域登録 | FreshはUNDO領域・ヘッダーを作成。既存DBは保存済み領域を開く |
| `trx_sys.create()` | 既存ファイルの内容そのものではなく、実行時管理の準備 | transaction管理オブジェクト | 両経路にある |
| `recv_recovery_from_checkpoint_start()` | checkpoint以降のredo走査、復旧要否、checkpointや状態の妥当性 | 復旧状態、必要なら復旧対象のページ情報 | 既存DB側。正常停止済みでも入口を通る |
| `dict_boot()` | 辞書ヘッダー、space ID、システム辞書の索引root等 | 辞書hash/cache、table/indexの実行オブジェクト | **両経路にある**。Freshは`dict_create()`から呼ぶ |
| `recv_sys.apply(true)` | 収集したredo対象ページ | 必要なページ更新と適用状態 | ページ適用の本体は`!pages.empty()`の場合。呼んだだけでは大量適用の証拠にならない |
| `srv_load_tables()` | 明示的にはSYS_TABLES/COLUMNS/INDEXES/FIELDSの索引、その後システム辞書load | 辞書の索引・管理状態 | 既存DB側。ユーザーテーブル全行を読み直したとする根拠ではない |
| `trx_lists_init_at_db_start()` | rollback segment、必要なら残ったUNDO/transaction | purge管理、rollback segment配列、必要ならtransaction状態 | 空判定の前に`purge_sys.create()`と`trx_rseg_array_init()`を行う |
| 最後の確認 | redo形式・サイズ/設定、表領域サイズ | 必要な場合のログ再構成等 | 同じ設定ならログ再構築を避ける経路がある。毎回再構築するとは限らない |

### 今回分かったこと

1. **Snapshotのファイル共有と、InnoDBの実行状態再利用は別です。** ファイルブロックを
   共有できても、新しい子のbuffer/dictionary/transaction管理を用意する仕事は残ります。
2. **辞書構築をForkだけの仕事とは呼べません。** Freshも`dict_create()`の最後に
   `dict_boot()`を呼びます。定義の文字列は定数でも、出来上がるcacheや索引オブジェクトは
   子のメモリ・ロック・ファイル状態を伴い、そのまま共有できるとは確認していません。
3. **正常停止や空UNDOだけでは起動費用がゼロになりません。** その状態を読み取って
   確認する処理と、確認前に必要な管理状態の構築があるためです。
4. Freshで後続transaction区間が約2ms、Forkで約0.14msだったことも矛盾しません。
   新規作成と既存データ起動は仕事の配置が違い、区間名だけでは同じ処理量になりません。

## 分かったことと、まだ分からないこと

| 分かったこと | 未確定なこと |
|---|---|
| 分岐・復旧入口・辞書/transaction準備はMariaDB/InnoDB側の起動設計 | 実行費用の何割が生成Go、ホストFS、メモリ、待機か |
| 既存表領域openにdoublewrite処理の呼び出し・ヘッダー検証が含まれる | そこが0.1msか数msか、何bytes/何pages読んだか |
| clean DBも復旧入口へ進み、redo適用本体には条件がある | 対象実行で`recv_needed_recovery`が何だったか、適用対象ページが0だったか |
| 辞書の骨格構築は両経路にあり、既存辞書のloadもある | 辞書・UNDO・redoそれぞれの独占時間とCPU費用 |
| ファイルサイズやログ形式が同じなら再構成を省く分岐がある | 各条件が測定実行で実際にどう評価されたか |

したがって、約6msを「redo再適用」「ファイルコピー」「物理I/O」のどれかと断定したり、
特定の検証を削ればその時間が消えると予測することはできません。
doublewrite関数の本体は今回の8ファイル制限の外です。実際の読込み条件・量を
確認せず、関数名だけから常に全領域を読むとは主張していません。
以前の約8.9MBのwrapped readと約0.56msのwrapped I/Oも、この複合区間の集計です。
ファイル名・呼び出し別の内訳がなく、doublewrite由来と結び付けてはいません。

## パッチ・計測点との照合

既存の始点は`srv_start()`内の「undo/redoの残骸を確認」する直前、終点は
後続のdoublewrite作成の直前です。バッファプール作成はこの区間より前です。
現在の区間を細分化せずに、buffer poolや共通初期化へ時間を割り当ててはいけません。

参照した移植パッチでは、InnoDBのファイルパス処理・WASIXでのファイルlock省略、
PMEM無効化、redoの条件付きmprotect対応等があります。確認した起動本体と復旧の
分岐を「WASIXが丸ごと省く」変更はありません。C側の起動設計が分かったことと、
ホストshimが性能に無関係と証明したことも別です。

生成Goの公開済みファイルにこのC++関数名と直接対応する索引は見つかりませんでした。
このため、既存Goへのoverlayで新しい関数spanを入れられるかは未確認です。
C側の既存マーカーだけでは`open_or_create()`の時間を単独で出せません。

## 次に進む場合の1つの境界と費用

対象は`SysTablespace::open_or_create()`の呼び出し前後の経過時間です。
これを現在の外側区間と同じ子で測れば、「このcall」と「残り」を足し戻せます。
目的は支配箇所の判別で、正常停止時の検証や復旧を無効にすることではありません。

- まず最大30分、固定guestの関数対応を確認し、生成Go overlayで2計測点を追加できるか判定。
  対応が確認できればguest再ビルドなし、Goビルド1回と、P1 Fresh/Fork各3回×48子の
  診断だけを候補とします。ビルド上限20分、実行上限15分、全ペア・尾部・所有者・cleanupを保持。
- 対応が取れない／inliningで境界を保てない場合は、guestへの追加フックと再生成が必要です。
  冷たいguestビルドの実費は今回未確認なので、軽いGoだけの計測と称して開始しません。
  その場合は必要なビルド・保存量を提示して別の予算判断へ戻します。
- 呼び出しの時間が小さければ、その事実を記録して残りの復旧・辞書/transaction区間へ絞ります。
  観測値なしに最適化候補や期待短縮量を作りません。

## 再確認と保存

source-files.jsonは8ファイルのcommit/blob/SHA256、source-map.jsonは29のアンカーと
行番号を保持します。原ソースは再取得可能なので一時領域を破棄します。
plan.json/source-files.json/acquire.pyを新しい専用workspaceのevidenceへコピーし、
`python3 -B evidence/acquire.py <source-files.jsonにある相対パス...>`で固定refを再取得できます。
各取得30秒、記録済み8ファイルを上限とし、既存のhashと照合します。

この成果物はソース調査の完了です。新規のruntime PASS、候補採用、main統合、
Qualification、releaseを意味しません。

主な上流参照: [srv_startの分岐](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/srv/srv0start.cc#L1400)、
[表領域ヘッダー確認](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/fsp/fsp0sysspace.cc#L566)、
[復旧入口](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/log/log0recv.cc#L4812)、
[辞書boot](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/dict/dict0boot.cc#L197)。
