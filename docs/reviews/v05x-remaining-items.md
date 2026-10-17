# v0.5.x 残件リスト（2026-10-17 時点）

v0.5.2 公開と関連する Human 決定を反映した残件のスナップショット。
新しい計測や runtime 変更は行っていない。個々の決定は
[project-status](../project-status.md) が所有し、本書は「現在アクティブな残件」と
「次の判断」を一覧するために置く。

本版の基準: main `15b694f`（startup tail、scalar/SIMD、purge 比較、Ubuntu 性能確認の受理と証拠統合まで反映）。
スナップショットのため、各項目の最新状態は [project-status](../project-status.md) を正とする。

2026-10-18追記: Ubuntu性能確認はHuman受理によりクローズ。他項目の基準日は上記のとおり。

## アクティブ（判断・作業が残る）

| # | 残件 | 現状 | 次の判断／作業 |
| --- | --- | --- | --- |
| 2 | 子 Fork 起動と子 Close の費用帰属 | 未着手 | 子の Fork 起動と Close の費用を計測し、時間を使っている処理を特定する。計測と原因特定までをゴールとし、修正・最適化の選定は範囲外 |
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
| 7 | 共有メモリ一般モデル / purge 保護前提 | 未確立の限界として受理。R1–R5・T1/T2/J1・scalar/SIMD 照合・purge 限定比較は完了。一般 Wasm→Go の正しさは未確立、purge 保護前提は未確認の限界 |
| 8 | Ubuntu 性能 | 2026-10-18にHuman受理、完了。[結果Review](ubuntu-product-performance-results.md)。Snapshotの利益と大規模Pythonの混在結果・原因未確定を保存。全workloadの改善を意味しない |

## 実質残るもの

- **子 Fork 起動・Close の費用帰属** — 計測と原因特定（実装は別）。
- **16 接続調整** — 0.5.x 入りしたので需要・資源効果の確認。
- **信頼スコープ再設計** — 着手ゲートのまま。

## 関連する確定済み成果物

以下は v0.5.x 共有メモリ（上表 #1）に関連し、main `9789a1e` で取り込まれた静的照合の
成果物。次回 Review の入力であり、本書は内容を評価しない。

- [scalar/SIMD 照合](shared-memory-scalar-simd-reassessment.md)
- `shared-memory-post-v05-evidence/`（36署名台帳・source anchors・現行アクセス例）

## 決定記録（Human decisions）

| 日付 | 決定 | 記録 |
| --- | --- | --- |
| 2026-10-18 | Ubuntu性能確認の資料・保存証拠・計測ツールのmain統合とpushを別途承認。runtime変更・追加計測・公開は含めない | project-status、[結果Review](ubuntu-product-performance-results.md) |
| 2026-10-18 | Ubuntu性能確認を完了として受理。大規模Pythonの悪化・原因未確定は留保し、追加調査・main統合・リリースは今回の承認に含めない | [結果Review](ubuntu-product-performance-results.md)、本台帳 クローズ #8 |
| 2026-10-17 | 接続数調整より先にUbuntu性能確認を実施する | [固定scope](ubuntu-product-performance.md)、本台帳 クローズ #8 |
| 2026-10-17 | 16 接続/DB の接続数調整を 0.5.x スコープに追加（需要・資源効果の確認が先） | project-status（`ff5d442`）、本台帳 アクティブ #3 |
| 2026-10-17 | purge head/view の限定 Wasm/Go 比較を完了として受理し、Go 変換の修正には進まない | 比較 `424172f`、本台帳 クローズ #7 |
| 2026-10-17 | purge 保護前提を「未確認の限界」として受理。実 guest 順序観測（上限2時間案）は承認しない（無害とはしない） | project-status、本台帳 クローズ #7 |
| 2026-10-17 | FD/リソースモデルを 0.5.x 外とし、観測を v0.6.0 dogfood に統合 | project-status（`ff5d442`）、本台帳 クローズ #2 |

## 根拠

- [post-v0.5 共有メモリ照合](shared-memory-post-v05-reassessment.md)
- [main Product Verification](main-product-verification.md)
- [Fast architecture review](../benchmarks/fast-architecture-review.md)
- [verification-economics の deferred 変更](v045-verification-economics.md)
- [project-status](../project-status.md) / [releasing](../releasing.md)
