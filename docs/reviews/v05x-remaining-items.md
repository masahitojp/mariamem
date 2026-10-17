# v0.5.x 残件リスト（2026-10-17 時点）

v0.5.2 公開と関連する Human 決定を反映した残件のスナップショット。
新しい計測や runtime 変更は行っていない。個々の決定は
[project-status](../project-status.md) が所有し、本書は「現在アクティブな残件」と
「次の判断」を一覧するために置く。

## アクティブ（判断・作業が残る）

| # | 残件 | 現状 | 次の判断／作業 |
| --- | --- | --- | --- |
| 1 | 共有メモリ | R1–R5 と T1/T2/J1 修復は完了。一般 Wasm→Go 共有メモリの正しさは未確立 | 次の Human Review で範囲を決める: 旧 remaining groups（scalar 34 / wide SIMD 2 / subword 1）を現行 guest へ再対応づけするか、new full census か、general design か |
| 2 | Ubuntu 性能 | 未計測のまま。「PASS に数えない」 | 承認済み 0.5.x 作業として起動するか、documented gap のまま残すかを決める |
| 3 | 16 接続/DB の接続数調整 | 0.5.x スコープに追加済み | 実需要と資源効果を確認してから上限変更を検討する |
| 4 | 信頼スコープ再設計 | 未着手 | 着手前に別 Human Review（dependency closure と negative proof）が必要 |

## クローズ / 0.5.x 対象外

| # | 残件 | 扱い |
| --- | --- | --- |
| 1 | 100 MiB Go Fresh | 条件付きクローズ。同様の悪化が再発した場合のみ、保存証拠と突き合わせて再開する |
| 2 | FD/リソースモデル | 0.5.x 外。v0.6.0 dogfood に観測を統合し、圧迫が示された時のみ resource model を再開する |
| 3 | 強制タイムアウト閉じ込め | 作業ではなく製品限界（documented limitation）として維持する |
| 4 | v0.5.2 の公開反映 | 完了。source `47f297cc…` / tag object `2e98dee0…`、typed pin を追加し、current published release に更新済み |
| 5 | v0.6.x serial/parallel 利用ガイド | v0.6.0 節に documentation backlog として記録済み（実装は v0.6.x） |
| 6 | startup tail の記述 | 整合済み。v0.5.1 Release CI（`7a82f338…`）が page-cleaner 修正を含む最終 source を両 native で検証済み |

## 実質残るもの

- **共有メモリ** — 次の Human Review（最重要）。
- **Ubuntu 性能** — 0.5.x 作業に入れるかどうかの判断のみ。
- **16 接続調整** — 0.5.x 入りしたので需要・資源効果の確認。
- **信頼スコープ再設計** — 着手ゲートのまま。

## 並行成果物（未コミットのローカル成果物）

以下は v0.5.x 共有メモリ（上表 #1）に関連する、現時点で未コミットのローカル
成果物。本コミットには含めず、次回 Review で採用/破棄を判断する対象であり、
本書は内容を評価しない。

- `shared-memory-post-v05-evidence/`
- `shared-memory-scalar-simd-reassessment.md`

## 根拠

- [post-v0.5 共有メモリ照合](shared-memory-post-v05-reassessment.md)
- [main Product Verification](main-product-verification.md)
- [Fast architecture review](../benchmarks/fast-architecture-review.md)
- [verification-economics の deferred 変更](v045-verification-economics.md)
- [project-status](../project-status.md) / [releasing](../releasing.md)
