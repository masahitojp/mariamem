# v0.5.x follow-up after v0.5.1

2026-10-17。既存の採用・検証・公開・調査終了判断を照合した残件整理。
新しい計測やruntime変更は行っていない。

## Human Review

**次の判断は、任意の改善としてSnapshotのhash走査削減の設計検討へ進むか。
私は、既存の3回走査のうち重複を安全に統合できるか、設計に絞って検討することを推薦する。**
利用者のmigration／seed後のSnapshot取得を短くする目的に直結し、前段のD採用で
保存・コピー方式の変更は完了している。残る全量走査は現行コードで確認できる。
ただし新構成での削減可能時間はまだ確定しておらず、旧file-backed測定のms値を転用しない。

**最も強い反論は、この走査が破損検出と実際にForkするbackingの検証を支えている点。**
チェックを単に外すのでは採用しない。検証済みの不変backingと所有取得を結ぶ方法、
producerの可変aliasが残らない条件、失敗oracleを維持できることを先に示す。
設計レビューまでを次の境界とし、今回の整理だけで実装・追加計測を始めない。

## Completed and deferred work

| 項目 | 状態と扱い |
| --- | --- |
| MariaDB 12.3.3、bounded correctness、起動tail修正 | 採用・公開済み。一般論だけで未完了へ戻さない |
| D block backing、Python共有host、保存/load API削除 | v0.5.1で公開済み。承認済み契約を維持 |
| 最終構成Qualification、Product Verification、Release CI | 完了。各source identity／SKIPを維持し、後続docs commitの結果へ付け替えない |
| 100 MiB Go Fresh | Humanが調査終了を決定。同様の悪化が再現した場合に再調査。元の32.6秒と再利用CPUの割当元は未解明 |
| 追加Snapshot hash削減 | 未実装。任意の次候補であり、v0.5.1の必須残件ではない |
| 16接続/DBの調整 | 保留。需要と資源効果を確認して別途判断 |
| 広い共有メモリ保証、非協調guest強制停止 | 別設計テーマ。今回発見した新しい欠陥として扱わない |
| framework dogfood／fixture ergonomics | 既存のv0.6.0方向。0.5.xへ自動追加しない |

v0.5.1はsource_commit `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、
tag_object_sha `089b32e09608902f6d46e7ab9527d09922dcf065`。
[公開Release](https://github.com/masahitojp/mariamem/releases/tag/v0.5.1)と
[Release CI](https://github.com/masahitojp/mariamem/actions/runs/38959312232)を参照。
最新remote mainもこのsourceを指していることを今回確認した。

## Current code boundary for the next candidate

通常のheap Snapshotの論理内容走査は現在も3回ある：

1. [`freezeHeap`](../../internal/generatedgo/code/base/heap_snapshot.go)が停止後のMemFSを読み、
   digestを作り、不変block descriptorsへ移す。
2. 同関数末尾の`h.Verify(build)`が、移した正確な対象descriptorから全内容を再検証する。
3. [`OwnHeap`](../../internal/snapshot/heap.go)が所有取得時に再度`h.Verify(build)`を行う。

[`Heap.Verify`](../../internal/prepared/heap.go)は論理長全体を読み、暗黙ゼロを含めた内容hashと
期待digestを照合する。一方、Fork側の構造・identity確認は全量再hashではない。
private handoffは別の境界なので、通常経路の結論を流用しない。
この確認は静的な経路確認で、走査ごとの新しい時間計測ではない。

設計で決める対象は、検証した正確な不変backingを所有取得へ渡せるかと、重複走査を
統合する際に失われる検出能力があるか。単なるunchecked flagや期待digestの無検査な信頼へ
置き換えない。元の破損・identity・失敗時処理・子の独立性oracleを採用条件として維持する。
設計が成立しない場合は現行を維持し、成立した場合も実装と限定検証は別の合意範囲とする。

## Existing evidence

- [採用契約](../decisions/snapshot-product-contract.md)、[D採用報告](d-heap-shared-host.md)、[製品化設計](d-heap-productization-design.md)。
- [最終構成Qualification](main-storage-qualification.md)、[Product Verification](main-product-verification.md)。
- [Fresh追加調査と終了判断](https://github.com/masahitojp/mariamem/blob/7068dd045f10c2772535fccca73c040c387e5b0b/docs/reviews/go-heap-reuse-attribution.md)。調査source／raw dataは専用branchに保持し、今回まとめて取り込まない。

公開済み状態と保留判断の文書更新のみ。main統合や新しいリリース承認は含めない。
