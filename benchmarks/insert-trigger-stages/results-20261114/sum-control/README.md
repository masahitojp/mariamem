# SUM対差分加算 — Issue186追加対照、2026-11-14

結論: triggerと注文行UPDATEを保持してSUM再集計を差分加算へ置き換えると、P8のtrigger経路は約半分に減り、観測なしraw100 INSERTも3/3組で短縮した。SUM再集計を含む式の評価経路が、このworkloadの大きな費用である。一方、加算でもtrigger時間は約7.74ms残る。SUMだけが全費用の原因ではない。

| 100 INSERTあたり | P1 SUM | P1 加算 | P8 SUM | P8 加算 |
|---|---:|---:|---:|---:|
| 観測off raw p50の3process中央値 ms |18.073|13.020|31.638|21.597|
| 観測on SQL実行平均 ms |14.741|9.510|23.053|14.876|
| 観測on trigger最外層平均 ms |9.907|5.018|15.407|7.737|
| 観測on SQLからtriggerを引いた残り ms |4.834|4.492|7.647|7.140|

onの各セルはprimary3process×8 DB、各DB100件の平均。offの行は各processのDB中央値を3processで中央値化したもので、onの平均値と加算・差分比較しない。

P8 offの対応短縮量は9.264/8.888/11.670ms（中央値9.264ms）。独立中央値の差10.041msと区別する。P1は5.054/5.065/6.371ms短縮。観測on P8のtrigger短縮量は7.565/7.818/7.627ms、SQL全体短縮は8.196/8.325/8.010ms。残りも約0.4–0.6ms減っているため、差をSUM内部だけの直接計時とは呼ばない。計画・式評価・スケジューリングなどの変化を含むnet対照。

## 固定条件と検査

source_commit bb1e937ae75b5788c8548a52987d9d42f78292d5、guest SHA256 77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450。前回の49877dd09673b25329744d4bfdcc9a151ac4804dの観測器をそのまま使用。Go1.27.4/macOS arm64、GOMAXPROCS8/GOGC100。reproduction-source.jsonでcommit identityを確認。

同一binary、SUM/加算×observer off/on×P1/P8。各セルwarmup1＋交互順3組、32process。監査status限定、5 triggers、制約・索引・時刻更新・注文UPDATEを維持。INSERT triggerだけ下記へ置換し、UPDATE/DELETE triggerは元のSUMを保持。

```sql
UPDATE orders
SET total_cents=total_cents+NEW.quantity*NEW.unit_price_cents,
    updated_at=CURRENT_TIMESTAMP(6)
WHERE id=NEW.order_id;
```

information_schema.TRIGGERSの実登録本文を全DBで読み、SUMの有無がarmに一致することを確認しログへ保存。置換箇所は一意一致をassert。256 DB/25,600 raw INSERT、orders40/items100/audit40/合計/stock500/FK/CHECK、公開Closeは全成功。観測on128 DB/12,800件で7境界・ID一意・stdout Write一回・trigger深さ0復帰・時間包含を検査。呼出回数はいずれも400 entry/100 INSERTで、実際のtrigger本体400回を意味しない。Fork・親注文準備・PREPARE・COMMIT・oracleはraw区間外。

## 観測負荷と限界

raw p50のon/off対応変化率はP8 SUM -5.14/+4.26/-6.20%、加算 -0.55/+3.38/+5.14%。P1 SUM -0.56/+3.59/-8.28%、加算 -0.75/+1.78/-2.92%。共有hostの変動込みであり負の値は負荷ゼロの証明ではない。全標本を保持し補正・追加反復なし。性能の方向はobserver offだけでも全組で一致する。

このprobeは100明細INSERT専用で、サンプル投入全体・70テストsuite全体・他エンジンとの新しい比較ではない。前回cohortの15.58msから引くのではなく、今回同時計測したSUM15.407msを対照とする。並列DBの差をsuite全体短縮量へ換算しない。

推奨: SUMを省く効果と残費用を判定する今回の切り分けは完了。アプリ側の差分更新案には根拠があるが、任意ユーザーSQLを書き換えるmariamem製品最適化の根拠とは別。採用を検討する場合は対象アプリのUPDATE/DELETE/NULL/丸め/overflow等の意味と全suite利益を別途評価する。今回のfixtureで合計一致したことを一般的な同値性とはしない。残るtrigger経路の詳細を調べるなら、注文UPDATE/trigger実行共通費用に問いを絞る。

## 再現

固定sourceからworktreeをprepare（8GiB予算/最低空き8GiB）。本bundleをevidenceへ配置し、restore.py→extend.py→build.py→measure.py→sum-analyze.pyを実行。restore.pyは前回と同一の基本overlay hashを照合し、extend.pyがtrigger深さ観測を追加する。harnessは今回のSQL切替と実登録本文検査込み。build上限20分、campaign15分。結果保存後に専用cache/worktreeをcleanup。製品source変更・main統合・releaseなし。
