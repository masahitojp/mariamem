# 検証証拠の再利用範囲 — 着手前 Human Review

## 今回の判断

**推薦：実装前に、計測器変更についてだけ依存関係と再利用条件を限定整理する。**
DBの挙動が変わらない変更でも重い検証が必要になる場合があり、その待ち時間を減らせるか判断する。
一方、入力の見落としで変更後のDBに古い成功証拠を適用するのが最大の反論である。
そのため除外規則はまだ変更せず、影響がないと言える根拠と、誤って再利用してはいけない変更例を先に揃える。

判断対象は下記の限定整理への着手。証拠再利用方式の採用・実装・既存判定の緩和・リリースは別判断。
提案段階でありHuman承認済みとは記録しない。

## 今の規則と既存資料

確認基点 source_commit `1f334030fbc3ce95cbe3f443244e17c47aa10a05`。
既存の[verification economics Appendix D](v045-verification-economics.md#appendix-d--deferred-economics-changes)
はdependency-subset reuseを保留し、dependency closureとnegative proofを着手条件にしている。

- `scripts/validate_product_candidate.py:qualify` は全tracked inputとmodeを記録する。
- `scripts/runtime_validation.py:compare_inventory` は変更ごとに再利用資格を判定する。
  現在もREADMEや一部docs、版定数等の例外があるため「全変更で必ず再検証」という仕組みではない。
- `tests/test_runtime_validation.py:test_unreviewed_source_changes_rejected` は未知file、runtime、依存、
  検証入力の変更/追加/削除を拒否する。
- 同 `test_runtime_reuse_does_not_exempt_recipes_consumers_or_executable_docs` は
  recipe、consumer、workflow、実行可能なdocsを一律除外しないことを検査する。

Development CIの実行範囲選択とReleaseのruntime証拠再利用は別物である。
今回のUbuntu性能CI成功をQualification証拠へ読み替えない。
節約できる時間・頻度はまだ計測しておらず、効果を確約しない。

## 提案する限定範囲と終了条件

対象は今回統合した `benchmarks/ubuntu-startup/` と専用workflowを例にした、計測器変更の扱い。
全リポジトリの依存グラフ構築や証拠schemaの実装は行わない。

1. **依存の整理**：runtime build/生成、qualification harness、source/package/license検査、
   Release guardのどれが対象fileを実際に読む/実行するかを、呼び出し元つきで表にする。
   source inventoryに入ることと、DB挙動への依存を区別する。動的読込等で追い切れない点は未確認とする。
2. **再利用を分ける**：runtime挙動の証拠を再利用できる場合でも、その変更のunit/source検査と
   最終artifact検査が必要かを別々に示す。source/license/公開物の確認は省略前提にしない。
3. **失敗側の条件**：少なくともruntime/guest変更、Go依存変更、recipe変更、検証workflow変更、
   計測器の共有helper化、未知file、追加/削除/rename/mode変更で、何が再利用を止めるべきかを列挙する。
   既存oracleが捕まえるものと、追加oracleが必要なものを区別する。
4. **一つの推薦**：現行維持、計測器だけ限定対応、広い再設計へ進む、のいずれかを理由とともに返す。
   根拠不足なら現行拒否を維持し、不足する具体的な依存経路を残す。

終了は上記4成果の有無で判定する。「影響するものが永久に存在しない」の証明を要求しない。
時間は概算1〜2時間、上限2時間を提案する。上限到達時に未完了なら完了扱いにせず、残項目と推薦への影響を返す。
DBビルド・再計測・全Qualificationは、この依存整理には不要。

## 今回の提出状態

上記ownerと既存negative oracleをソースから確認した。依存経路全体の整理は未実施。
この文書の追加だけで、再利用範囲を変える安全性や費用対効果が成立したとはしない。
接続数の調整は承認済みのv0.6.x dogfood、guest初期化の改善方式選定はv0.7.xのまま。
