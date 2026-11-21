# P8のサンプル投入で発生する400 ms超の待ち（2026-11-21）

**この遅延はOSパイプでも発生する。** 要求IDまで追えたOS側の1件は、注文INSERT文をprepareするときのInnoDBの待ちだった。全451.889 msの投入に対し、そのprepareのワーカーは392.167 ms連続でfutexにブロックしていた。リング側も診断なしで435.806 msを再現したが、診断ありの24回では発生しなかった。リング側の過去・今回の遅延について原因を同一とする根拠はまだない。

PR #235の既定化判断は引き続き保留を推奨する。今回の結果で、400 ms級の遅延がリングに固有という判断材料はなくなった。一方で両方式の発生率の差は判定できず、大応答CPUの先行実測（+8.45%）も残る。次に必要な証拠はリング側の遅延回の待機先。Goのfutex shimで長い待ちだけを記録し、待機したアドレス、通知・timeoutの区別、通知元、write I/Oコールバックがキューに入ってから実行されるまでを同じDBで照合する方が、リング容量を変えるより直接的である。[製品候補](https://github.com/masahitojp/mariamem/pull/235) · [前回の製品比較](https://github.com/masahitojp/mariamem/tree/073f514fe0c2dc7c0d1496a9beafab69abf2f62b/benchmarks/host-stream-product/results-20261121)

## 発生条件

macOS arm64、Apple M1、Go 1.27.4。P8、GOMAXPROCS=8、GOGC=100。各プロセスはpgmem由来の50読取・20更新、21回の40注文投入、同期Closeを完走した。各条件24プロセス・504投入。4条件を4通りの実行順で6巡し、各条件が各順番に6回ずつ入るようにした。別に各条件の意味検証とウォームアップを1回ずつ行った。400 msの閾値は前回と共通で、測定開始前に固定した。

| 方式 | 診断 | 400 ms以上の投入があったスイート | 最長の投入 | スイート経過中央値 |
|---|---|---:|---:|---:|
| OSパイプ | なし | 2/24 | 475.634 ms | 400.6 ms |
| 16 KiBリング | なし | 1/24 | 435.806 ms | 371.9 ms |
| OSパイプ | 要求ID＋Go実行トレース | 1/24 | 451.889 ms | 473.7 ms |
| 16 KiBリング | 要求ID＋Go実行トレース | 0/24 | 122.795 ms | 447.4 ms |

閾値を超えた4スイートは各1投入のみ。診断なしOSはDeleteUserとApplyDiscount、リングはCreateOrderの準備。診断ありOSはCreateOrderの準備で再現した。診断を入れるとスイート経過中央値は両方式とも長くなった。未計測の回の内部区間や真の発生率は推定しない。事前に定めた「診断ありの両条件で未再現」の場合のみの追加16組には該当しなかった。[96スイートとウォームアップ](suites.csv) · [全投入](samples.csv)

## 要求ID 8の内訳

ブロック14のOS、TestCreateOrder/one_line のFork、スロット0。451.889 msの投入と重なる内部要求は253件。長かったのは orders へのINSERT文のprepareで、そのCallの合計は393.261 msだった。

| 同じ要求の境界 | 経過 |
|---|---:|
| ホストのCall開始 → ゲスト側入力フレーム読取り完了 | 0.0069 ms |
| 入力完了 → ワーカーが要求を取得 | 0.0024 ms |
| ワーカー取得 → 応答生成開始 | 393.1784 ms |
| 応答生成開始 → ホストの呼び出し元復帰 | 0.0738 ms |

ワーカーと応答生成のGoログは同じgoroutine（G427）。この間のGo実行トレースではWaitingが392.178 ms、Runningが0.951 ms、Runnableが0.043 ms、Syscallが0.009 msだった。RunningはGoスケジューラ上の状態で、CPU使用時間の独立計測ではない。最長の連続待ちは392.167 ms。スイートの他のDBと混同しないよう、各要求をDB名・要求ID・スロット・opcode・入力バイト数、各応答をDB内の順序・長さと復号した要求IDで照合した。[時刻とクライアント操作](tails.json) · [Go状態遷移・スタック](scheduler.json)

固定ゲストのBinaryen関数表を監査ハッシュで照合した。待つ側はテーブルopen時の ha_innobase::statistics_init → dict_stats_update_transient → fseg_n_reserved_pages → buf_page_get_gen → srw_mutex_impl::wait_and_lock → Futex_wait → GoのAtomicWait。通知側G17484は write_io_callback → srw_mutex_impl::wake → Futex_wake → AtomicNotify でG427を実行可能にした。要求ワーカーは期限なしの待機分岐に入り、通知で起床した。

通知側のgoroutineの生成を逆にたどると、timer_handlerのG270が起床し、tpoolのタイマー実行経路から4段の生成を経てG17484が起動していた。G270自体の期限付きAtomicWaitは403.022 ms続いている。これは要求ワーカーとは別の待ちで、一部が重なるため加算しない。書込がいつキューに入ったか、timer_handlerの選択分岐、およびその期間ずっと通知可能だったかは今回の計測対象外。[固定関数表の来歴](https://github.com/masahitojp/mariamem/tree/7c5893b3d5198d2c5087dbb100e631dfe63a58bb/benchmarks/trigger-sum-bottleneck/results-20261121) · [Goトレース原本](primary-14-1-diag-os.trace.gz)

## 証跡

計測は専用のGo overlayとハーネスで行い、製品候補a1ce4a7dとOS対照be12aeb6を固定した。observations.tar.xzにはウォームアップを含むすべてのスイートスパン、診断時の全21レーンのクライアント操作、要求ごとの境界時刻を保存した。ゲスト起動用rootの要求は実行中に照合しており、保存対象はサンプル投入に使ったFork。SQLペイロードは収集していない。[再現と解析](recipe/REPRODUCE.md) · [集計](summary.csv)
