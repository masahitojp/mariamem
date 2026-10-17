# 共有メモリ：旧scalar／SIMD群とv0.5.2の静的照合

## Human Review

**次の判断は、purge共有状態の1経路について、元WasmとGoの限定比較へ進むか。推薦は進めること。**
旧censusのscalar 34署名・SIMD 2署名を固定集合にして現行コードへ照合した。
単なる「race detectorが見えない」という留保から、処理済みundo位置の読み書きが
異なるlockで保護されている具体的な確認点へ絞れた。修正や全guest censusの開始は推薦に含めない。

**最も強い反論は、元MariaDB側にも同じ状態管理があり、Go変換固有の違反ではない可能性。**
そのため、Goのrace報告だけで修正判断をせず、元Wasmが許す観測とGoの観測を比較する。
実際のSQL破損・停止・クラッシュは今回再現していない。既存リリース判断を取り消す根拠にも、
観測限界だけを受け入れてこの具体的な確認点を閉じる根拠にもしていない。

## 範囲と固定入力

- 起点資料：`d60afb96bff20dc468bc210d336ca83cc9756f68` の
  [既存証拠の照合](shared-memory-post-v05-reassessment.md)。
- 旧入力：`a427b83078071e4cee5d6aebe16d0ee55fb73041`。
  [旧census](../../benchmarks/direct-link-race-scope.json)の2群36署名、両端72件、関連21関数を対象とする。
- 現行入力：v0.5.2 source_commit `47f297cc7498625e076abb93322eb616c9560bb8`。
  tag_object_sha `2e98dee0ca94abe95dcef8351b71f7726320bf12` は別identityとして確認した。
- guest Wasm SHA256：`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- 現行Binaryen symbol mapのSHA256：
  `9072658996738894b86effc9b60911db92b413d35cb3c7863f3851666bb645b6` を機械照合に使用。
- MariaDB参照ソース：固定commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`。
  URL・file hash・過去selected-source hashとの一致/不一致は
  [source inputs](shared-memory-post-v05-evidence/source-inputs.json)に分離する。

新しいguest実行、race計測、ビルド、修正は行っていない。これは全149署名の再調査ではない。
後続調査との対応が未整理だった2群の、現行入力での位置づけを調べた。

## 対応づけの確度

[36件の台帳](shared-memory-post-v05-evidence/scalar-simd-ledger.json)は旧IDを1件ずつ保持する。
現行21関数の名前は正本symbol mapで確認した。11関数はアドレス・関数番号等を除いた
body templateが一致する。残り10関数はsource roleと周辺構造による対応候補で、bodyは異なる。
アドレスを消す比較は候補探索であり、同じオブジェクトや意味論を証明する手続きではない。

72端点すべてに現行候補を記録したが、**現在PCへの一対一対応が72件成立したという意味ではない**。
49端点は候補statementが1件、23端点は複数候補。58端点はexpression template、14端点は
同じ移設globalへの同種・同幅アクセスで追った。旧globalの移設先を別関数の一致する式で照合し、
現行のアクセス幅も記録した。関数bodyの変更や分岐の違いを「同じコード」として扱わない。

## 36署名の位置づけ

下記の件数は旧署名の分類であり、現在のrace件数・不具合数・確率ではない。

| 分類 | 旧ID / 件数 | 現行で分かったこと | 判定の限界 |
| --- | --- | --- | --- |
| lock word／waiter count | 12,18,19,25–28,58–64,118–120,140 / 18 | srw lockやlog待機にある通常32-bit readと32-bit CAS。旧分類の「other scalar」にはlock処理も含まれていた | R1の下位primitive・CAS再検査の説明と関連するが、これら全statementの同期証明や再実行ではない |
| LRU list長 | 20–24 / 5 | page cleanerが読むglobalと、LRU追加・削除の書き先が現行でも同じ4-byte領域。元ソースもdirty readと明記 | flush量の見積もりに影響しうる。SQL誤値を実証したものではなく、Go上の一般的な正当性の証明でもない |
| I/O heuristic counter | 47,48,53–57 / 7 | `buf_page_t::flush` と `buf_read_page_low` の通常4-byte加算が同じglobal `24089032` に残る。元ソースの `buf_LRU_stat_cur.io` はmutex非保護を明記 | 原子的な正確な件数を元ソースも約束しない。LRU方針・速度への影響とDB内容破損を混同しない |
| LRU aging判断 | 121,122 / 2 | `freed_page_clock` のglobalと、pageのoffset192にあるold/clock bitfieldの通常4-byte read/writeが残る | 元の用途はpageをLRU先頭へ動かす判断。隣接するatomic access_timeはoffset196で別領域。現在の並行実行や利用者被害は未観測 |
| transaction historyの近似読取 | 65 / 1 | coordinatorのrseg history件数読取とfree_history側の減算に対応する候補。元ソースには非保護の`history_exists`/`history_size_approx`と、保護する`history_size`の両方がある | 厳密な件数APIと近似APIを区別する。今回、全alias・全callerの証明はしていない |
| purge viewの下限 | 17 / 1 | `free_history`のreadと`clone_oldest_view`のwriteが現行でもglobal `24020776` の同じ8-byte領域 | 古い履歴を破棄してよいかに関わる値。次のpurge共有状態の比較に含める。無害と判定しない |
| purge headのコピー | 4,5 / 2 | 同じ16-byte領域を読む`purge_truncation_callback`と、書く`trx_purge`/`batch_cleanup`が現行にも存在 | 下記の別lockと実行順序の確認が必要。2署名は同じgenerated endpointの例で、2種類の独立欠陥ではない |

出典は[固定ソースの抜粋](shared-memory-post-v05-evidence/source-anchors.json)、
[現行コードの抜粋](shared-memory-post-v05-evidence/current-examples.json)と台帳。
`buf_LRU_stat_cur`、page cleanerのdirty read、LRU aging、history近似APIはそれぞれ
元ソースの明示的な用途・契約に基づく。これらをrace解消済みとしたわけではない。
`TPOOL_SUPPRESS_TSAN`等の元ソース注記も、Goの検証を抑制する許可には用いていない。

## 重要な実例：purge共有状態

purgeは、更新前の履歴から、もはや必要ないundo記録を回収する処理。
`head`はどこまで処理済みかを表す`trx_no`/`undo_no`の組である。
必要な履歴の選別を誤れば、履歴参照・回収の正しさに影響しうる。
これは利用者への影響候補であり、今回観測したSQL失敗ではない。

| 経路 | 現行generated source | 実際のアクセス |
| --- | --- | --- |
| 読み手 | `p8.Fn18171`、symbol=`purge_truncation_callback`、p8_pure.go:347610 | global `24020976` から16-byte load。その前に`24020736`のread lockを取得し、コピー後に解放 |
| 書き手 | `p1.Fn17161`、symbol=`trx_purge`、p1_pure.go:788995 | `Simd_p_fx262`が同じ`24020976`へ16-byte store。その前に`24020864`のwrite lockを取得 |
| 8-byteの関連読取 | `p2.Fn17151`、p2_pure.go:837614 | `24020776`を通常read。`p3.Fn16686`のclone_oldest_viewも同じ領域へ通常write |

sourceでは読み手が`purge_sys.latch`、`batch_cleanup`の書き手が`end_latch`を使う。
`head`の宣言コメントは「Protected by latch」。`purge_coordinator_task_group(1)`と
`purge_truncation_task_group(1)`は別で、coordinatorは通常ループでtruncation taskをsubmitする。
coordinatorが次のbatchへ進む前に必ずtruncation終了を待つ、という共通の保護は
今回調べたcallerからは確認できない。別の順序保証がないことの完全証明ではない。

これはアドレス・source・アクセス幅を結びつけた**具体的な保護前提の未確定箇所**である。
通常更新からの静的経路はあるが、v0.5.2での両アクセスの同時実行、torn head、SQL被害は未観測。
元ソース側の問題、変換固有の問題、実際には別の同期で保護される場合をまだ区別していない。
旧Wasmのopcode記録も通常のv128.load/storeであり、幅が16-byteというだけで
「Wasmが要求したatomicityをGoが失った」とは判定しない。

## 次に推薦する限定比較の範囲と終了条件

上限2時間の設計・小fixtureによる比較を提案する。これは見積り上限で、成功や完了の保証ではない。
対象を上のpurge head／viewと、その読取・更新・task順序に限定する。

1. 実行前に、利用者へ影響する不正なhead/viewの判定条件と、元Wasmが許す観測を固定する。
   単にrace detectorが報告することを失敗oracleにしない。
2. 既存のWasm/Go比較資産で、同じ幅・同じlock/順序を保った小fixtureを作る。
   簡略化したfixtureと実guestの対応条件も明記する。フルguest再build・新censusは含めない。
3. 結果を、Go固有の差／元Wasmでも起きる結果／保護成立／比較未成立に分ける。
   要修正なら所有元・範囲を別提案にする。比較未成立や予算到達を問題解決としない。

元guestにも同じ結果が出るなら、一般的なwasm2go adapter修正とguest固有の保護修正を分ける。
追加前提が必要なら、その具体的な前提と不足する証拠を残してHumanへ返す。

## 確認結果と未実施

| 項目 | 結果 |
| --- | --- |
| 文書指摘の修正 | 「reaffirmed after v0.5.2」を除去。元決定7068dd0のみを引用。並行した状態文書更新commit `ff5d442`にも同じ修正が含まれ、重複修正しない |
| 固定入力・36署名の棚卸し | PASS、36/36、72端点の候補集合、21関数を保存 |
| current-PC一対一対応 | 未成立。23端点は複数候補で、candidate探索と意味論確認を区別 |
| source取得 | 18ファイル取得。3つの初期候補パスは404で未取得・不使用。raw log0log.ccは既存prepared選択hashと異なり、compiled postimageとしては扱わない |
| 厳密な同期・元Wasm/Goの比較 | 未実施。上記の追加確認を推薦 |
| 新しい同時実行・SQL被害・race計測 | 未実施。mmap/ASMの無報告から安全性を推論しない |
| runtime・guest・生成物変更 | なし |
| 静的台帳の再現 | PASS。保存したscriptから独立に出力し、台帳JSONとbyte一致。コード抜粋8件と固定ソース抜粋のhash・行も照合 |
| 文書の関連チェック | PASS。`python3 scripts/verify.py check --scope docs`、参照先確認、`git diff --check`。runtimeの再build・再試験は対象外 |

再現：

```sh
python3 docs/reviews/shared-memory-post-v05-evidence/reconcile.py.txt \
  --symbol-map docs/reviews/v050-ad-integration-evidence/function-map.txt \
  --output /tmp/shared-memory-scalar-simd-ledger.json
```

この静的照合が済んでも、旧149署名全体の再census、一般shared-memory modelの確立、
または観測限界の受容が済んだとは数えない。既存R1–R5の完了範囲も縮小・再開扱いにはしない。
