# worker起動順序の制御再現 — 2026-11-17

## 結論

**thread creation pendingによる追加要求のまとめ込み後、先行taskが未通知の依存待ちに入ると、空きconcurrencyがあっても後続taskがmaintenanceまで滞留する経路を縮小実験で再現した。** 固定4条件×3回、12ケース全PASS。これは実SQL/guestの394ms事象の原因確定ではない。

次は実guestで同じtask投入順序・pendingによる拒否・worker開始後のqueue・未通知待ちが成立したかを確認することを推奨。randomな追加スイートやtimer短縮を先に行わない。既存のwait_begin通知がこの縮小例では十分な対照となるため、実際の待機箇所と通知対象poolをまず確認する。

最大の反論は「依存taskを人工的に作れば停滞するのは当然」という点。この実験は依存関係自体を発見したものではない。一方で、単に上限不足という説明ではなく、**concurrency16・active1・queued1で、pending gateが追加を見送り、その後pending解除だけでは再評価されない**という具体的な起動順序を、同じMariaDBメソッドで検証した点に意味がある。実事象との結び付けはなお必要。

## 固定入力と実装範囲

計測source_commitはevidence/inputs.jsonのsource_identity（c772f7d78e09f6b9c30cd4d3799cb23e1bbb6b89）。前回guestのMariaDB source commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` のtpool_generic.ccを、前回保存物から使用。製品基点6558ee8、guest77b2ab49の前回traceとの対応は親レポートに保持。

run.pyが以下9メソッドを名前＋brace範囲で原文から抽出する：throttling_interval_ms、maybe_wake_or_create_thread、add_thread、submit_task、worker_main、maintenance、set_concurrency、wait_begin、wait_end。add_threadだけにpending/max/throttle拒否回数のcounterを加える。分岐条件やreturnは変えない。各原文/観測付きbodyのhash、生成C++とbinary hashを保存。

native C++17、Apple clang21、macOS arm64。Go/WASM・SQL・InnoDB自体は実行しない。support.cppは小さいadapterであり、完全なupstream poolではない：

- taskをcallback、worker cache/listを標準コンテナに置換。
- get_taskはmutex下のFIFO取得・state/count更新を保持する小型実装。idleは単純condition variable、shutdownは全worker終了待ち。standby wake経路は本実験で未使用かつassertする。
- TLS pool設定callbackは空。実際のworker_data TLSはworker_mainで設定され、wait_beginは同じworkerに適用される。
- 初回workerのinit callbackをbarrierで止める。これは本来のinit callback呼出位置を利用し、pending clear前の順序を制御する。
- 自動timerを置かず、mainが指定時点で同じmaintenance本体を呼ぶ。400/40msは**実験者が与えた時刻**であり、自然発生遅延を測り当てた値ではない。
- 初期concurrency16・min1・max64。実guestでこの設定値だった証明ではない。cap不足を避けた機構対照として固定した。
- AはBの完了を待つsynthetic task。未通知待ちの条件ではwait_beginを意図的に呼ばない。実際のbuf_loadがその条件を満たしたと断定しない。

## 条件と結果

Aのsubmitで最初のworkerを作り、init barrierで停止する。pending条件ではその間にBをsubmitし、pending拒否が1回発生したことを確認する。barrierを解放するとworker_mainはpendingをclearしてAを実行。AはBに依存して待機する。

| 条件（各3回） | A待機時間の範囲 | pending拒否 | 結果 |
|---|---:|---:|---|
| pending中にB投入、400ms後maintenance | 400.154〜405.178ms | 全回1 | tick前queued1/active1/waiting0、tick後B開始 |
| Aの開始確認後にB投入 | 0.039〜0.090ms | 全回0 | maintenanceなしで完了 |
| pending中にB投入、Aがwait_beginを通知 | 0.030〜0.041ms | 全回1 | maintenanceなしで完了 |
| pending中にB投入、40ms後maintenance | 45.058〜45.167ms | 全回1 | tick前queued1/active1/waiting0、tick後B開始 |

40ms指定の実呼出しが約45msになったのは、このホストでのwait_until復帰時刻であり、guest周期ではない。これらの短縮率を製品改善率には使わない。4条件ともmax/throttle拒否0、最終worker2、全task完了、queue空・全worker停止を確認。ログ中のcontrolのqueue_before_tick等の0は、tickがないための初期値であり、実測snapshotではない。

## どこまで説明できたか

順序を変えるだけでpending拒否がなくなる対照と、pending拒否を残したままwait_beginで進行する対照が成立した。したがってpendingフラグ自体が永続的に立ちっぱなしなのではなく、**pending中に追加要求をまとめた後、最初のworkerが依存待ちに入るまでにbacklog再評価がなく、待機通知もない**ことが縮小例の条件。

保存SQL traceのmaintenance→worker追加→simulated AIO→completionと整合する機構候補だが、実事象の最初のsubmit/pending拒否は未観測。前回の394ms全体がこの経路だった、もしくは修正できた、とは主張しない。#140/#143の原因との同一視も行わない。

## 推奨する次の確認

実guestの同poolについて、mutex下でtask enqueue/dequeue、creation_pending拒否とclear、active/waiting/long・concurrency、依存I/O task identityを記録するか、同じbarrier順序を実guest内の対象poolに限定して再現する。待ちを通知する箇所が欠けているなら、適切なpoolへのwait_begin/end対照が候補。worker開始時のbacklog再評価は別候補だが、worker増加/終了の意味を変えるため現時点では実装・採用しない。timer短縮は原因の解消とは別である。

## 再現・検証・保持

PLAN.mdの12ケースのみ。run.py <workspace>がsource identityとclean statusを検査し、生成・clang build・5s/processの固定試験を実行する。実験用ブランチを使い、result追加前の計測SHAをcheckoutする。実行時のSDK pathとcompiler versionはinputs.jsonに記録。

最初はローカルclangがC++標準ヘッダatomicを見つけられず、ケース未実行で終了。initial-build-failure.txtと入力を保持し、xcrunで選択したSDKのisysroot/isystemを指定する変更だけを別commitで固定した。失敗したworkspace runnerは再利用せず、同じ2GiB/空き8GiB/120sのstandalone guardで実行。これはベンチマークではなく、timerとgateを制御した機構試験。絶対時間の性能主張をしない。

製品runtime/guest/APIは変更なし。ケースassertionと終了確認、12結果の再集計、source/diff/hash確認を実施。広範な製品受入れ・CI・releaseは対象外。raw resultは全保持し、生成C++/binary/worktreeのみ削除する。
