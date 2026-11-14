# 明細INSERTのtrigger経路 — Issue186追加計測

結論: SQL実行内の約67%がtrigger処理経路。次の優先対象をtrigger内の注文UPDATE/SUMに絞る。ただしSUM単独やInnoDBだけの費用は未分離で、具体的な最適化の採用判断はまだできない。

| 100件あたり、primary24 DB平均 | P1 | P8 |
|---|---:|---:|
| mysql_stmt_execute |15.340ms|23.254ms|
| process_triggers最外層inclusive |10.271ms|15.585ms|
| SQL実行から最外層を引いた残り |5.068ms|7.669ms|
| trigger経路の比率 |66.96%|67.02%|

Fn15540=Table_triggers_list::process_triggers。固定関数mapで確認し、関数entry/returnをGo overlayで計時。深さカウンタで入れ子を二重加算しない。呼出しは100 INSERTにつき400回（入れ子を含む全entry）。これはSQL trigger本体の実行400回を意味しない。発火条件判定・呼出し管理・注文UPDATE・その配下のSUM/索引/行処理等を含むinclusive値。残りにもSQL実行共通処理が含まれる。SUMそのものが67%とは結論しない。

source_commit bb1e937ae75b5788c8548a52987d9d42f78292d5、guest SHA256 77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450、Go1.27.4 macOS arm64。前回と同じharness/SQL/監査status限定/合計再計算trigger/制約。Fork、親注文準備、PREPARE、COMMIT、oracleはraw投入の外。売上SQL設定はREVENUE_PREAGG=1（このprobeは売上query未実行）。

同一binary off/on、P1/P8各arm warmup1＋交互3組。16process/128DB/12,800 INSERTと既存oracle/Close成功。観測onの6,400件すべてで7境界、一回性、stdout Fd_write一回、trigger呼出あり、深さ0への復帰、trigger時間がSQL区間内に収まることを検査。P8 raw100件p50 off/on中央値30.963/30.463ms、対応変化率+2.89/-1.67/+0.22%。P1は+2.41/-5.50/-0.05%。観測負荷とhost変動を補正せず全標本保存。offにもhook分岐が残る。前回cohortとの時間差を性能改善としない。

次はtrigger内の注文UPDATEを、SUMの読み取りとUPDATEの行・索引処理に分ける観測が有用。これまでの差分更新/no-trigger実験とも方向は整合するが、別cohortを差し引いて今回を分解しない。製品変更・採用・main統合・releaseは実施していない。

再現: 固定sourceのworkspaceをprepareし本bundleをevidenceへ配置、restore.py、extend.py、build.py、measure.py、analyze.py、trigger-analyze.pyの順に実行。ビルド上限20分・計測15分、予算8GiB/最低空き8GiB。結果保存後は専用cache/worktreeをcleanupする。restore.pyは前回overlayの完全一致を検査し、extend.pyが今回の追加hookを重ねる。observer.patchに最終差分を保存。
