# P8の投入でワーカーを起こした書き込み完了通知

Go側のリングで400 ms以上かかった投入8件は、すべてInnoDBの `write_io_callback` からの通知で進行を再開した。前回のOSパイプでも確認した起床経路である。今回は待機開始から完了コールバックのタスク登録までに377–401 ms、登録から実行開始までは0.26–0.61 msだった。次に調べる区間はページ書き込みの要求・フラッシュ判断から simulated AIO への投入まで。リングの既定化は保留を推奨する。[前回の要求別診断](https://github.com/masahitojp/mariamem/blob/d78ed430ab50ca90cfe38f57ba7bb024a5a95fde/benchmarks/host-stream-p8-attribution/results-20261121/README.md) · [製品候補 #235](https://github.com/masahitojp/mariamem/pull/235)

| Go側の転送 | 400 ms以上の投入があったスイート | 400 ms以上の投入 | 最長投入 | スイート全体の中央値 |
|---|---:|---:|---:|---:|
| OSパイプ | 0/96 | 0/2,016 | 112.9 ms | 404.3 ms |
| リング | 8/96 | 8/2,016 | 484.1 ms | 383.0 ms |

Apple M1、macOS arm64、Go 1.27.4、GOMAXPROCS=8、GOGC=100。同一のpgmem由来modelcaseで50読取・20更新、独立した21回のサンプル投入を各プロセスで検証した。投入は注文40件・明細100件などをまとめた1トランザクション。両方式の意味検証と各1回のウォームアップ後、OS→リングとリング→OSを交互に96組実行した。閾値と組数は親issueに事前記録した。スイート中央値は診断用バイナリでの値。[集計](summary.csv) · [各投入](samples.csv) · [プロセス別の値](suites.csv)

## 8件の待機と通知

- 全8件で投入中の同期要求に100 ms以上のfutex待ちが1回あり、その待ちは378–401 ms、投入時間の81.1–86.7%を占めた。いずれも同じwaiterへの実通知を確認した。対象操作は明細INSERTが4件、注文INSERTが1件、注文INSERTのPREPAREが3件。
- 待機する側は7件が `buf_page_get_gen` 配下の `srw_mutex_impl::wait_and_lock` で、うち3件は前回OSパイプでも見られた `dict_stats_update_transient` 経由。残る1件は行更新中の `btr_cur_t::search_leaf` からのロック待ちだった。
- 起こす側は8件とも `write_io_callback` → futex通知。完了タスクのキュー登録と取り出し時のポインタを同じDB内で一意に対応付け、呼び出し時の引数と実際のコールバック引数の一致を検査した。待機開始から登録が376.97–400.68 ms、登録から実行が0.261–0.606 ms。書き込み要求の発端やフラッシュ判断はこの区間で観測していない。[8件のスタック・タイムスタンプ](tail-details.json) · [要求に対応した待ち](foreground.csv)

今回の診断では長い投入がリング側に偏った。過去の診断なしの比較では両方で発生した（OS 2/24、リング1/24）。同じ通知で解除されたことは確認できたが、転送方式が待ちの発生率にどこまで影響するかは未確定。判定には別途その効果を識別できる比較が必要になる。既定化判断には256 KiB連続応答でのCPU増加も残る。[先行製品評価](https://github.com/masahitojp/mariamem/blob/073f514fe0c2dc7c0d1496a9beafab69abf2f62b/benchmarks/host-stream-product/results-20261121/README.md)

## 観測と検証

Goビルド・オーバーレイで、DB、要求ID、要求と応答のスロット、担当ワーカー、futexアドレスと待機単位のトークン、選択された終了分岐を記録した。待ち時間は登録からselect復帰まで。実通知の時刻は該当チャネルを閉じる直前に取得した。100 ms以上の待ちを保存し、対象要求とクライアント操作の両方で包含を検査した。バックグラウンドの待ちも各回の圧縮JSONに保存した。入力のゲスト・関数表はリポジトリの監査値と照合済み。Go実行トレースは使用していない。[再現手順](recipe/REPRODUCE.md) · [4つの観測器テスト](controls.log) · [保存データ検証](verification.txt)
