# A2: discard停止内訳の有限診断

**結論:** 設定3往復は約0.16〜0.18ms/子で、停止前半約0.94〜0.96msの2割弱。主な残りは終了要求後の約0.73〜0.75msだが、guest Cのshutdown単独とは分離できていない。RPC統合で消えるのは設定区間の一部であり、全額削減を見込んでguest変更・再ビルドへ進む根拠は弱い。推奨は本診断を完了し、RPC統合は候補として保持、次の大きな変更前にBのリセット・所有権契約を設計して判断すること。エンジン停止省略は成立性を別に示す必要がある。

最も強い継続理由は3往復と専用接続の反復費用が実在する点。ただし接続・SET・closeはguest内の実処理で、終了フレームへ移しても自動的に消えない。全体速度改善や実装採用の判断は今回の診断に含まれない。

## 固定入力・範囲

Measured source_commit `daa76b2913965f314d8d5c7de29332aad3f4b27f`、base `c680bfe9ccbf80b012fce897c151fe5a7e42d1e3`、接続済みproduct `f563128520fc49097ac83ef47cdea2dee21ff62a`。診断clock/callbackのみ追加、終了方式やguestは不変。Go1.26.10 darwin/arm64、CGO0、GOMAXPROCS8/GOGC100。sourceはgit_identityで確認、clean before build。binary buildinfo/hashはbinary.json。

1,000行Snapshot、48子/実行、元#206のSQL・隔離・WaitDisconnected・同期Close・最終drainを使用。P/cap=1/2,2/4、warmup各1回＋診断各3回、合計8実行384子。全実行成功、lease/Disposed検査成功、mapping count/reserved/RWは基準復帰。前回のsandbox bind失敗は計測開始前の別試行であり、今回cohortには混ぜていない。停止指示後は再開指示まで実行しなかった。

## 結果

単位ms/子。各run48子の算術平均を算出し、その3run中央値を掲載。子のp50でも主計測のwall改善率でもない。各行の中央値を加算して合計に一致させない。

|区間|P1/cap2|P2/cap4|
|---|---:|---:|
|Close開始→受付停止|0.0309|0.0264|
|受付停止→session join観測|0.0033|0.0048|
|設定用open RPC|0.0823|0.0872|
|SET GLOBAL RPC|0.0517|0.0537|
|設定用close RPC|0.0271|0.0346|
|設定3往復全体|0.1634|0.1771|
|終了要求開始→transport/worker停止観測|0.7270|0.7486|
|Close開始→transport/worker停止観測|0.9357|0.9642|
|停止観測→backend cleanup完了|0.9076|1.4936|

設定3往復のrun平均範囲はP1 0.1435〜0.1662ms、P2 0.1731〜0.2072ms。終了要求後はP1 0.6966〜0.7415ms、P2 0.7270〜0.7751ms。48子の設定区間延べ時間は中央値約7.84/8.50msだが、P2はworker延べ時間でありそのままwall短縮へ換算しない。

## 解釈・限界

- セッションはSQL pool.Close/WaitDisconnected済み。session joinの小ささをbusy SQLや未完了transactionを持つCloseへ一般化しない。
- 終了要求後にはroot/guest engine終了、全generated worker join、pipe/reader join、host通知goroutineの起床・観測待ちが含まれる。runtimeはstoppedイベント後にメモリ解放を開始するため、hostの停止通知観測とcleanupは時間的に重なることがある。cleanup_tailはmunmap単独ではない。
- 計時callbackはmutexとmapping counter読取りを使う。clock取得・observer・scheduler費用を含み、無観測時の純粋なエンジン/RPC費用ではない。A/Aや無観測対照は今回追加していない。旧Go1.27.4/P4/P8 cohortと混ぜない。
- 通常Close=2/Snapshot=1を終了時に確定する#145条件を維持。起動時へ設定を移すだけの案は、利用者変更・再Snapshotと費用移動を解決しない。
- 実guest 8回の既存ワークロード検証まで。新しい停止方式・race再実行・全suite・別OS・製品採用・main統合・releaseは実施していない。A1aの変更も混ぜていない。

## 再現・終了条件

PLAN.mdとrun.pyで固定した8実行のみ。guardは5400秒、12GiB scratch、12GiB free reserve。再開時はsandboxのlocalhost bind制限を解消し、experiment_disk.pyで同じ作業場所をguardした（失敗済みworkspace receiptを偽装せず手動監督）。TMPDIR/GOTMPDIRはworkspace/temp。run.py <workspace>はclean measured SHAからbuildしraw eventsを出力する。analyze.pyは同ディレクトリruns.jsonlからsummaryを再計算する。全数・順序・資源復帰は記録時に追加検算済み。必要な知識はこの小bundleとpush済み履歴へ縮約し、再生成可能なbuild/cache/worktreeを完了時にcleanupする。
