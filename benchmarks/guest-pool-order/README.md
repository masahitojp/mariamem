# 実guestの起動順序・pending・待機通知の照合 — 2026-11-17

## 結論と推奨

**実guestでpendingによるworker追加見送りは確認したが、縮小実験と同じ400ms停滞は確認できなかった。** 固定8process・560ケース全PASS。112,673件のglobal pool enqueue/dequeueを同instance/pool/taskで照合し、未対応enqueue0、100ms以上のqueue滞留0、page_wait>=100msも0。

通常観測4回と、最初のworkerがpendingをclearする直前に20ms待たせる対照4回の双方で、workerは起動しqueueが進んだ。buffer-loadのI/O完了待ち181件のうち180件は同workerのwait_beginによる待機数更新を確認した。残り1件も1.618msで復帰し、poolのlong countが1だった。対象worker自身のLONG_TASK bitは未記録なので、通知省略理由までは確定しない。

**「追加見送り＋未通知待ち」が過去の394msの原因だという採用根拠にはならない。** pending見送りは正常な短い経路にも多く現れる。timer短縮・worker無制限化・worker開始時のbacklog再評価は採用しない。本キャンペーンはここで終了し、追加の同型samplingを行わない。

最大の反論は、詳細traceとmutex内のログがscheduleを変えて長い待ちを隠した可能性。これは否定できないため、「修正済み」「原因ではない」とも結論しない。次に進むなら低負荷の有限event buffer等で、実際に長いケースのtask/通知条件を保存する設計が必要。今回未観測のtask-group内部queueやwait_beginの早期return理由を、global pool queueと混同しない。

## 入力・観測器

- 計測source_commit: `252ce7be506f3d2d48fbaf5e895aa6e0cb233090`。製品runtimeは6558ee8fb2211313a8aa0ea6070ac5256767811aと同じで、親branchの追加は過去のharness・証跡のみ。
- Guest:77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450。前回のSHA付きsymbol mapを使用。C guestの再ビルドはしない。
- Go1.27.4 / macOS arm64 / GOMAXPROCS8 / GOGC100 / CGO0。SQL、SUM/audit、UPDATE OF status、revenue事前集約、sync Closeを前回から維持。
- generated Goにoverlayのみ。元runtimeファイルは変更しない。関数原文・overlayのhash、binary/buildinfo、run scriptを保存。
- Fn16602のenqueue完了、Fn16591のdequeue完了、Fn16594の実際のreject_pending/max/throttle分岐、Fn16593のconcurrency拒否、Fn16592のpending clearとtask実行、Fn16603/16604の待機数更新、maintenance/page待ち、worker futex開始/終了を記録。

構造体offsetはsource-layout.jsonと関数原文で対応付けた。queue/counter snapshotはguestが既にpool mutexを保持している点に限定。pending clear地点ではshared counterを読まずidentityのみ。futexでは同thread専用TLSのpool/workerを読む。instanceはbase.ThreadPool pointerを使い、同じguest addressが別instanceで再利用されても区別する。page_wait/page_completeのPoolMarkのpoolフィールドは**page pointer**であり、pool集計からはevent種別で区別する。

## 固定条件と結果

naturalはobserverのみ。hold20は各instance/poolの最初のworkerだけ、初期化callbackの後・pending clearの直前にtime.Sleep(20ms)を挿入する。pool mutexは保持しない。実際の再開時刻はschedulerにも依存する。全4対照で80回のholdを記録。人工的なschedule変更であり、自然再現/高速化対照ではない。管理timer・resource値は変えない。

| run | mode | pending拒否件数 | 最大global queue待ちms | 最大page_wait ms |
|---|---|---:|---:|---:|
| 0 | natural | 13056 | 16.477 | 13.267 |
| 1 | hold20 | 13303 | 31.820 | 12.855 |
| 2 | natural | 12644 | 17.160 | 22.448 |
| 3 | hold20 | 13062 | 36.441 | 15.982 |
| 4 | natural | 12235 | 37.553 | 15.765 |
| 5 | hold20 | 12988 | 34.995 | 13.568 |
| 6 | natural | 11974 | 13.851 | 17.525 |
| 7 | hold20 | 13353 | 40.815 | 12.366 |

queueは同taskのenqueue完了→dequeue完了。前回のsubmit入口→execute入口とは境界が異なる。task_group内のqueueやcallback処理時間はこの数値に含めない。全112,673 enqueueをdequeueと対応付け、未対応0。pending拒否は計102,615回、max/throttle拒否は0。多数の拒否は同時投入をまとめる通常動作でも発生するため、回数だけで不具合と判定しない。

pending拒否がqueue待ち区間にあったtaskも、worker clearとその後のdequeueへ到達した（correlation.json）。通常側最大37.553ms、hold側最大40.815ms。通常の最長例にも、worker起動前に複数taskが並ぶ順序はあるが、その後400msまで停滞していない。

実効concurrencyは観測snapshotで16。20ms保持は20pool/processに作用した。保持がSQL実行中の依存待ちを強制するわけではないため、縮小例の全前提を実guestで強制した実験とも呼ばない。

## 待機通知の確認と1件の留保

固定upstream83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5eのbuf0dump.ccは`os_aio_wait_until_no_pending_reads(true)`を呼ぶ。os0file.ccはdeclareとpending_io_countに応じてtpool_wait_begin/endを呼ぶ。生成Fn18273も同じ条件分岐。したがってbuffer-loadがそもそも通知をしない実装だという説明は成立しない。

traceではbuf_load → os_aio_wait_until_no_pending_reads → condition_variable待ちというframe列に限定した181回のfutex開始を抽出。同goroutineでwait_accountedが立ち、wait_unaccountedで戻る区間内だったのは180回。buf_load内の別のmutex待ちを混ぜない。

run2/G6880の1件は待機数更新を観測せず、1.617728msで復帰。直前snapshotはq19/active9/standby0/long1/waiting1/concurrency16。upstream wait_beginは既にLONG_TASKのworkerには重ねてWAITINGを加算しないが、当該workerのbitを記録していないため、この理由とは断定できない。pending_io_count事前判定とmutex後判定の間の変化も未観測。1件を「通知漏れ」「394ms原因」としない。周辺全eventをunaccounted-read-drain.jsonに保存。

## 原問いへの回答と次に必要な証拠

「縮小例の順序と未通知待ちが実guestの400msを説明するか」に対し、**順序/追加見送りは実在、長い停滞への因果は未確認**。通知は大半の対象待ちで機能している。前回の394ms実測そのものは撤回しないが、本キャンペーンでは再現しなかった。

現状でproduct変更へ進む推奨はしない。再開するなら、実際の長い待ちに対して同taskのglobal/task-group queue、worker状態（LONG_TASK/WAITING）、notify_wait判定前後、pending gateとclearを低負荷で同時保存する小さな計画を先に作る。短い通常例だけでguardの削除/通知追加を正当化しない。元traceのownerやpage番号を今回の別instanceへ読み替えない。#140/#143再開や新しいrelease条件は追加しない。

## 再現・検証・保存

PLAN.mdの8回のみ、全560cases成功。build.py <workspace>、evidence/run.py、analyze.py、correlate.py。workspaceはworktree/temp/evidence構造を使う。source identity/clean statusを検査しGo compilerとcmd/traceを同じ1.27.4でbuild。buildは6GiB/minfree8GiB/600s guard、実行はpre/post disk checkのみで計測中の再帰走査なし。ケース追加・外れ値除外なし。

初回observer buildはimport文字列挿入がコメントにも作用して構文エラーとなり、ケース未実行。最初のimport節だけに限定する修正を別commitで固定し、同じ予算のstandalone guardでbuild完了。初回ログ/inputsも保持。製品ソースの不具合ではない。

全8trace・event・解析JSON・source/overlay hashes・失敗/成功記録をmanifestで圧縮前後SHA256付き保存。生成overlay、binary/cache、worktreeは削除する。実験branchをmainへ直接統合せず、製品runtime/guest/API変更・release qualificationは行わない。
