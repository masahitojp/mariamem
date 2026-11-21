# 応答リング満杯から書き手再開までのGo実行トレース

**長い満杯待ちを追う次の対象は、ホストの応答読取ループが次の読み取りに戻るまでの処理。** 書き手が実際に停止した9,372回すべてで、ホストの応答読み手が byteReader.Read の Broadcast から書き手を実行可能にし、同じ書き手の再開まで追跡できた。全3試行で通知から再開までの中央値は0.192 µs。今回の観測だけではリングに伴うCPU増の原因や容量変更の効果は確定しない。[事前条件](protocol.md) · [前回の通常ビルドCPU比較](https://github.com/masahitojp/mariamem/blob/4224fa1062fcc481c1fb07e969cda5bee16151fc/benchmarks/response-size-cpu/results-20261121/README.md)

| 試行 | 停止を照合した件数 | 停止→通知 p50 / p99 | 通知→再開 p50 / p99 | 通知→再開の最大 |
|---|---:|---:|---:|---:|
| 1 | 3,122 | 0.704 µs / 1.542 ms | 0.192 µs / 63.36 µs | 2.138 ms |
| 2 | 3,114 | 0.640 µs / 1.402 ms | 0.192 µs / 38.27 µs | 1.875 ms |
| 3 | 3,136 | 0.768 µs / 2.169 ms | 0.192 µs / 70.59 µs | 1.182 ms |

停止から通知まで1 ms以上の184回（61 / 50 / 73件）を抽出した。通知した読み手の状態を停止区間と重ねると、延べ待ち時間の96.3%がRunning、2.7%がRunnable、1.0%がWaiting。これは読み手がGoランタイム上で実行中だったことを示す。読み手がリング内コピー、フレームのJSON復号、呼出元への結果配送のどこを実行していたかは、状態イベントだけでは区別できない。同じデータ経路をさらに調べる場合は、Process.readのフレーム読取・復号・配送を分ける。[読み手の状態](reader-long-parks.csv)

通知から書き手が再開するまで、9,215/9,372件は通知と再開のGoプロセッサ（P）が同じだった。再開先Pの時間を全件で積算すると、ホストの読み手に23.4%、応答書き手のgoroutineに16.8%、GCワーカーに0.8%、その他の既知・未分類goroutineに5.6%が重なった。残り53.3%にはスケジューラ実行・アイドル・トレース境界などgoroutine実行区間へ割り当てられない時間を含む。役割は当該goroutineの観測スタックから分類したもので、その瞬間の命令やCPU消費を表さない。異なる待ちが重なるため、合計はプロセスの経過時間とは異なる。[再開先Pの内訳](resume-p.csv) · [試行別の分位点](summary.csv)

OSパイプ対照でもゲストの応答書き込みがWaitingになった区間は各777 / 770 / 772件あり、待ちの中央値20.9〜23.0 µs、p95は2.08〜2.21 ms。OS側ではファイル書込の待機状態が終了するまでを数えており、リング側のCond待ちと件数や時間の意味は異なる。[OS書き込み](os.csv)

## 再現と境界

macOS arm64、Go 1.27.4、GOMAXPROCS=8、GOGC=100、通常周期400 ms。既存のBenchmarkLargeResponseBatch（8接続×12回、256 KiB値＋要求固有接頭辞を全件照合）を各3プロセス、OS→リング・リング→OS・OS→リングの順で実行した。全576応答の検査が通った。ベンチの準備後から応答検査完了までruntime/traceを有効にし、製品のリング・読み手にはフックを追加していない。トレースには開始・終了処理の一部も含まれ、非常に短い区間は時計と計測負荷の影響を受ける。前回のCPU差は診断なしの6組の結果を使う。

専用worktreeをring.jsonのコミットに固定し、隣にtemp/gotmpとevidence/recipeを置く。空の出力先で以下を実行する。親のOSパイプ版はlinked.goを固定コミットから復元してoverlayする。

```sh
python3 -B evidence/recipe/guard.py . 1200 python3 -B evidence/recipe/study.py build
python3 -B evidence/recipe/guard.py . 300 python3 -B evidence/recipe/study.py run
python3 -B evidence/recipe/analyze.py
```

保存済みの6トレースだけを再解析する場合はGo 1.27.4の go tool trace -d=parsed で各トレースをtemp/に同じ基底名の.parsedとして展開してからanalyze.pyを実行する。抽出はFd_write配下でbyte_pipe.goの満杯分岐からRunning→Waitingになったgoroutineに限定し、そのIDのWaiting→Runnable、Runnable→Runningを結合した。停止しなかった満杯チェックは対象外。時刻は単調時計のナノ秒。[全待ちの対応表](waits.csv.gz)
