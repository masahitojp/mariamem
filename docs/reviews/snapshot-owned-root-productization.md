# Snapshot所有権方式の製品化

2026-10-17。通常heapの内容を再構成・再走査せず、停止後に同じ実体を固定して受け渡す。

## Human Review — main統合の判断

**判断依頼：この製品化差分をmainへ統合するか。私は統合を推薦する。**
承認済みの所有権契約を、実験履歴を含まない最小差分へ移し、製品化候補890f770に対する
macOS15 arm64 / Ubuntu24.04 x86_64の正規check・integrationが両方PASSした。
strict Heap/転送検証、mapped寿命切断、独立byte参照、差し替え拒否、寿命/世代の境界を維持している。
今回の製品化に未解決のFAILはなく、追加のSnapshot高速化は行わない方針も反映済み。

**残る大きな留保は、最終リリース構成のQualificationと、この製品化SHAでの独立再生成は未実施なこと。**
今回の変更は既登録handwritten ownerとtree外の所有層で、変換済み関数・guest/converter・provenanceは不変。
既存canonical inventory/clean installer/inclusion/ライセンス検証がPASSしているため、
mainの開発基盤への採用を推薦する。今回のCIを公開資格とせず、公開前の検証は別のリリース判断に残す。
限定契約自体はHuman承認済みで、再承認を求めない。main統合・リリースはまだ実施していない。

## 承認済みのHuman decisionと境界

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
正規`verify.py check`と`verify.py integration`を製品化候補SHAに対して両native CIへ提出し、両方PASSした。
これは開発検証であり、リリース承認・最終Qualification・新たな性能計測ではない。
結果はsource identity、原出力、終了値とともに記録し、未実行をPASSにはしない。

| 項目 | 状態 |
| --- | --- |
| source inventory / ownership | PASS：抽出後のverify_generated_runtime |
| source/license/mirror | PASS：22 pytest、typed baseline pin/source inventory |
| prepared/snapshot/base focused race | PASS：source266186b、全対象testでSKIP/FAILなし。下記receipt参照 |
| 製品化候補のcanonical check/integration | PASS：source890f770、run39000948512の両OS。下記CI証拠参照 |
| 性能の再測定 | SKIP：追加Snapshot高速化は行わず、既存証拠を参照 |
| main統合・リリース | 未承認・未実施 |

ローカル検証の[receipt/原出力](snapshot-owned-root-productization-evidence)と
[hash/集計](snapshot-owned-root-productization-evidence/summary.json)は、実装commit266186bに対する結果。
その後の証拠・文書commitを新しい実装の検証結果とは呼ばない。
CI候補890f770では通常Goソースが266186bと同一であることを確認した。

## 両OSの製品化CI結果

[run39000948512](https://github.com/masahitojp/mariamem/actions/runs/39000948512)の全体と両jobがsuccess。
[macOS job117303546037](https://github.com/masahitojp/mariamem/actions/runs/39000948512/job/117303546037)、
[Ubuntu job117303546255](https://github.com/masahitojp/mariamem/actions/runs/39000948512/job/117303546255)。
head_sha、両artifactのsource.json、ローカルGitのcommit identityは
`890f770eee36c004036826104229f9269138775b`に一致した。
[原出力とhash集計](snapshot-owned-root-productization-evidence/ci/summary.json)を保存した。

| 正規検証の内容 | macOS15 arm64 | Ubuntu24.04 x86_64 |
| --- | --- | --- |
| version・canonical source/inventory・ライセンス | PASS：source pytest22件 | PASS：source pytest22件 |
| `go test ./...` と既存規則のvet | PASS | PASS |
| 通常Python check | PASS607 / SKIP27 / subtest PASS12 | PASS607 / SKIP27 / subtest PASS12 |
| handwritten/runtime/API所有元のrace対象package | PASS | PASS |
| 実guest Go integration / default / memory trap | PASS：3 suite | PASS：3 suite |
| Python通常Close / 複数接続 / wire / owned Snapshot | PASS18、追加mapped派生testを含む | PASS18、追加mapped派生testを含む |
| 既存Snapshot scenario | PASS33 checks | PASS33 checks |

通常checkの27 SKIPをPASSとは扱わない。ordinary checkではreal-host pytestをopt-inにしており、
integration側では明示hostを指定して上記18件を実行した。全てのSKIPがintegrationで消えた、という主張ではない。
強制timeout回収の別診断は正規integrationの対象外で、既存の観測限界も変えていない。
race報告ゼロからmmap/全guestの正確性を推論しない。

実環境：Go1.26.8、Python3.14.7（macOS）/3.14.8（Ubuntu）。これは開発検証で、最終Qualification、
新しい性能測定、公開済みartifactの受け入れではない。

この結果記録は`experiment/snapshot-owned-root-adoption-review`上の文書・小さな証拠だけのcommit。
CIで検証した実装は`experiment/snapshot-owned-root-productization`の890f770に保持する。
統合対象はmain7a82f33からの製品化2commitとこの結果記録で、元の探索commit群を取り込まない。
