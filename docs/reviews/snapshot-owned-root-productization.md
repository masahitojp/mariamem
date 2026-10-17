# Snapshot所有権方式の製品化

2026-10-17。通常heapの内容を再構成・再走査せず、停止後に同じ実体を固定して受け渡す。

## Human decision と現在の境界

Humanは、通常APIによる変更防止・同一実体・親子隔離・転送時検証を維持し、通常heapでの全量走査による
private-byte故障の事後検出を約束しないという限定契約を明示的に承認した。
FileStore/Root/capture bindingとadapter、独立byte参照・差し替え拒否・寿命/世代testの最小差分による
製品化も承認済み。**main統合とリリースは引き続き別のHuman判断**である。
[承認された契約](../decisions/snapshot-product-contract.md)へ反映した。

この文書は実装と検証の状態を記録する。前の契約承認を再び判断待ちには戻さない。
統合の判断に必要な製品化差分の確認は、下記の結果が揃った時点で返す。

## 基点・抽出

- 最新main/source baseline：`7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`。fetchしたorigin/mainと一致。
- 採用元の実装：`c2a7664bc2cf5b62a5931bf521f060c4fe11a4b8`。
- [実guestのレビュー・証拠](https://github.com/masahitojp/mariamem/blob/9763869bdfb802dbbc5a087422755e9bfde5c3b9/docs/reviews/snapshot-owned-root-guest.md)。
- 採用元Ubuntu：[run38998771860](https://github.com/masahitojp/mariamem/actions/runs/38998771860)。
- 製品化branch：`experiment/snapshot-owned-root-productization`。mainを基点にファイル単位で抽出。
  実験branchのcommit履歴、model、計測runner、破損注入hook/overlay、raw測定群をmergeしない。

## 最小差分

所有層は`internal/prepared`のFileStore/FrozenFile/Root。
FileStoreはcallerの可変bytesを保持せず、seal後はwrite/resizeを拒否する。
Forkは平坦な独立metadataを持ち、初回writeでblockをprivate化する。祖先root/FS/runtimeの連鎖を保持しない。
Captureを実行前にsourceへbindし、worker完了後のfreezeを通じたrootだけを取得する。
別root/source/guest、未完了・放棄・再取得、inventory/size/block差し替えを拒否する。

adapterは既存handwritten base/runtime、guest、host、snapshotの配線のみ。
通常heapは同じreader/表現を使い、seal/取得時にpayload hashを計算しない。
Root.CheckはO(files + materialized blocks)の構造検査で、byte内容の検査ではない。
既存timingのfreeze/own区間を維持し、環境変数が既に有効な時だけ経路counterを記録する。

strict Heap/転送のinventory・digest・guest検証は維持する。
raw Heapから新所有層へ移入する際はprivate copyと元digest照合を行う。
借用mappingはsource/targetをhashし、heapへmaterializeして寿命を切断する。
既存strict破損oracleの期待値は変更していない。
private bytesの直接破壊をRootが受け入れ、strict oracleが拒否するtestは、承認された検出境界の特性testとして残す。

採用元との差はコメント/importの整理と、mapped adapterでBorrowMapping失敗時にもFS mutexを解放するerror経路。
新規storeへの借用は通常成功するが、error returnをlockの内側から直接返さないよう整理した。
構造の拒否範囲にはnil file/dataを加え、不正metadataをpanicでなくerrorで返すtestも追加した。
アルゴリズムや同期方式の追加設計は行っていない。

## Testと生成所有元

- 独立byteモデル3seed×500操作、固定後writer拒否、truncate/regrow、子の隔離。
- capture差し替え拒否、replay/失敗/破棄後の解放、親rootの寿命を子から切断するweak参照test。
- 実FDによる10世代、既存block storage/strict oracle。
- strict Heap移入のalias切断と破損拒否、Root転送のstrict受信・別guest/同サイズ破損拒否。
- Pythonの明示handoff→mapped子→新baseline→孫/兄弟、元baseline不変・cleanupを既存test suiteへ追加。
- 既存Go/Pythonの通常受け入れを再利用する。

変更したgenerated tree内のファイルは全て既登録HANDWRITTEN_FILESのowner。
新Rootのソース/testはtree外。変換済み関数、guest、converter SHA/patch、
`runtime_memfs.py` preimage、`release/generated-go-inputs.json`とprovenanceは変更しない。
canonical inventory/clean installer/owner inclusionの既存oracleを維持する。
採用元での99file独立再生成一致は上記レビューに記録済み。
今回の製品化SHAでの独立guest/Wasm→Go再生成や最終Qualificationを実施済みとは扱わない。

## Snapshot高速化の停止点（承認済み）

今回のLight条件ではSnapshotの比重が十分小さくなったため、追加のSnapshot高速化は行わない。
理論的な速度下限に到達したという主張ではない。
既存の同一交互比較で、Snapshot中央値はv0.5.1の204.76ms→候補2.85ms。
候補の診断付き1試行は約3.08msであり、これを「v0.5.1の3.07ms」とは記載しない。
Light直列の子Forkは40子の中央値59.38ms、4子を準備・SQL・終了まで含む全体中央値363.95ms。
残る利用者時間は主に子の起動と利用にある。新たなFork/SQLの最適化調査をこの作業に追加しない。
数値は採用元のmacOS結果を引用したもので、新しい測定やUbuntuの性能結果ではない。

## 検証状態

runtimeの所有層と全てのMemFS file操作の実装が変わるため、source-only確認だけでは閉じない。
最初にcanonical source/ライセンスとprepared/snapshot/baseのrace testで抽出ミスを検出し、
正規`verify.py check`と`verify.py integration`を製品化候補SHAに対して両native CIへ提出する。
これは開発検証であり、リリース承認・最終Qualification・新たな性能計測ではない。
結果はsource identity、原出力、終了値とともに記録し、未実行をPASSにはしない。

| 項目 | 状態 |
| --- | --- |
| source inventory / ownership | PASS：抽出後のverify_generated_runtime |
| source/license/mirror | PASS：22 pytest、typed baseline pin/source inventory |
| prepared/snapshot/base focused race | PASS：source266186b、全対象testでSKIP/FAILなし。下記receipt参照 |
| 製品化候補のcanonical check/integration | このbranchのpushで両OS CIへ提出。結果未取得 |
| 性能の再測定 | SKIP：追加Snapshot高速化は行わず、既存証拠を参照 |
| main統合・リリース | 未承認・未実施 |

ローカル検証の[receipt/原出力](snapshot-owned-root-productization-evidence)と
[hash/集計](snapshot-owned-root-productization-evidence/summary.json)は、実装commit266186bに対する結果。
その後の証拠・文書commitを新しい実装の検証結果とは呼ばない。
CIへ提出する最終SHAでは通常Goソースが同一であることを確認する。
