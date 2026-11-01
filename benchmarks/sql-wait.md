# Issue68：未実装panicによる消失ではなく、生きたworkerの待機を観測

**今回の遅いCOUNT/SUMでは、要求の送信後、guest側のSQL workerが実装済みの
`Futex_wait → AtomicWait` で通知を待っていた。**
クライアントは最初の応答packetを待ち、応答後の行読取りはすぐ終わった。
前のIssue5の「Fd_dupの未実装panicでworkerが消え、応答しない」形を今回の観測は支持しない。
ただし未実装errno/no-opを含む全syscallの正しさや、待機・通知実装に欠陥がないことを証明はしていない。

次に絞る候補は **InnoDBページ読込み完了とthread-poolの仕事の開始・通知**。
ソースに400ms周期のthread-pool maintenanceがあり、今回の385/387/800msと整合する。
これは因果関係の証明ではない。タイマーを短くして症状を隠す前に、読込みtaskの
enqueue/start/completion、wait_begin、wake/maintenanceの対応を1つの診断で確認するのを推奨する。
追加guest/host instrumentation・修正は未実施。今回の固定6processでこのcheckpointを閉じる。

## 過去の未実装syscallとの照合

[Issue5の元の記録](../docs/reviews/issue5-text-dedup.md)ではTEXT/BLOBのtemporary-table mmapが
`Fd_dup` を呼び、host overrideのpanicでworkerが終了した。panic通知がjoinまで遅れ、
SQL timeoutに見えていた。

今回も同じpublished v0.6.0 source_commit
`b3b3b46a8807482ad3f96725af86e031fe369b01`、
tag_object_sha `b57183b08d48884840111e8b53daa500734337f0`を使った。
この版ではFd_dupをWasiStubsへ委譲し、ThreadLaunchのfatal trapをNotifyWorkerFailure→
ConnectWithFailure→Abortへ通知する経路がある。
残る14個の明示panic import名と、上記source/hashを
[syscall inventory](forkcompare/results/syscall-inventory.json)へ固定した。
未変更の修正済みruntime testを再実行したという主張ではない。

今回のSQLは整数表のCOUNT/SUMで、最終的に正しい値を返した。
後続UPDATE・検証SELECT・cleanupも成功し、当該processのstderrは空。
捕捉中にquery経路のworker自体が生きていたことが、旧症状との最も直接的な違い。

## 診断条件と結果

前の[クエリ別観測](https://github.com/masahitojp/mariamem/blob/2cb902610b1a5b423a71a59222e5ff793d81dfd8/benchmarks/sql-tail.md)
と同じM1/16GiB/macOS27.2、Go1.27.3、CGO0、GOMAXPROCS8、TCP、1,000整数行、48子/回。
P4/P8各3 fresh processes、別warmup各1。順序はP4→P8、P8→P4、P4→P8。
通常のdesktopで背景処理は停止していない。

変更はbenchmark harnessだけ：

- COUNT/SUMをQueryContext、Next+Scan、残り読切り/Closeへ分ける。SQL自体は同じ。
- MySQL driverのDialFuncでnet.Connを包み、COUNT中のWrite/Readの開始・終了を記録。
  byte数のみでSQL結果payloadは記録しない。TCP_NODELAY等の接続設定は変更しない。
- child labelをGo goroutineへ付け、COUNTが100msを超えた時のみ全goroutine stackを採取。
  process当たり最大2回、各1MiBまで。全captured stackにtruncated=false。
- QueryContextは最初のpacketとcolumn metadataを読む区間を含む。
  net.Connの最初のRead完了はOSで受信した瞬間そのものではなく、Go呼出しが戻った時刻。
- 150msの人工待ちpilotで遅延トリガ・stack採取を確認。人工待ちは本測定には使っていない。

診断の観測コストがあるため、このturnのwall/CPUを最適化の速度証拠として使わない。

正常測定288子中、100ms超は3process/3子。以下はすべてms。
Wire列はCOUNT開始からのoffsetで、read列は最初のReadが戻った時点。

| round / P / child | COUNT全体 | Write完了 | 最初のRead完了 | Next+Scan | 残り読切り |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 / 8 / 21 | 800.094 | 0.045 | 800.041 | 0.011 | 0.010 |
| 1 / 4 / 26 | 385.489 | 0.008 | 385.455 | 0.004 | 0.023 |
| 2 / 8 / 16 | 387.092 | 0.040 | 387.075 | 0.006 | 0.003 |

各要求は43bytesを1回Write、応答は合計105bytes。送信待ちや結果の反復読取りが長い形ではない。
この表は頻度推定ではなく、固定6process内で捕まえた事例の一覧。

## スタックで分かった待ちの連鎖

[3つのlabel付き抜粋と元stack hash](forkcompare/results/selected-stacks.json)を保存。
clientのchild labelと同じlabelのguest workerを照合している。単に別DBのidle workerを拾ったものではない。

```text
Go MySQL client: readResultSetHeaderPacket → TCP Read待ち
  mariamem wire: callGuest → Process.Callの応答待ち
    guest query worker: 生成SQL実行経路 → Futex_wait → AtomicWait
```

3件ともquery経路に対応するlive worker stackを捕捉した。
AtomicWaitの観測位置はbase.go:1946（timeout<0のselect）で、当該worker自身の
「400msのfutexタイマー待ち」ではない。workerは通知またはfatal-failure通知を待っている。
スタック採取はCOUNT開始約100.6–112.1ms時点、採取費用は約2.8–9.1msだった。
一瞬のstackなので、そのまま全遅延時間の状態だったとは断定しない。

sourceとの対応は以下。完全なWASM symbol mapを再取得していないため、生成関数の命名は
signature・埋め込み文字列・call chainによる対応であり、全関数の確定命名とは区別する。

- Fn17738の3引数と2つのtable error文字列は `dict_table_open_on_name` に対応する。
  round2/P8ではその経路でFutex_waitに入り、同じchildの別workerには
  `dict_sys.latch` の警告文字列を持つFn17732の待ちも見える。
- 他の2つのquery chainはFn18163→Fn16786→Fn16623→pthread/futex待ちに入る。
  `buf_page_get_gen` のread-fix判定→`buf_page_t::read_wait(trx)`、
  trxのTHD_WAIT_DISKIO通知/ページ統計更新→`lock.s_lock_nospin()`の構造に整合する。
- guest query経路と別のbackground workerも同じread-wait候補の経路で待っていた。
  async readのI/O自体が遅いのか、taskが開始されないのか、完了通知が届かないのかは未分離。

[固定上流sourceと生成fragment hash](forkcompare/results/source-correspondence.json)を保存。
ファイルI/Oやメモリ容量の枯渇、TCPの欠陥、futexの実装バグをこの段階で確定しない。

## 400ms周期という次の具体的な候補

固定MariaDB commitの `tpool/tpool_generic.cc:762` はmaintenance intervalを400msに設定する。
`maintenance()` はqueueが空でなければ `maybe_wake_or_create_thread()` を呼び、
進捗がなければ追加thread作成を試みる。
`wait_begin()` も待機中task数を更新して仕事を進める経路を持つ。

従って「通常の仕事投入/通知では進まず、maintenanceで再開している」は今回の証拠に沿う仮説。
しかしqueue/wakeイベントもタイマー発火時刻もまだ測っておらず、約400/800msの一致だけでは
原因とは言えない。ホストのfutex通知、guestのwait accounting、task投入順序を切り分ける必要がある。
未実装syscall一覧を無差別に実装したり、maintenanceを短くする変更には進まない。

## 検証・保存・再現

measured harness source_commit `5c56a151b26b5086bb35490f36510dc7985c4733`。
固定productのclean checkoutとtyped release identityをbuild前に検査。
[compact observations](forkcompare/results/compact.json)はbinary hash/build infoを含む。
正例pilot8子・人工待ちpilot1子・破損seed負例1子、測定288子、warmup96子は期待どおり終了。
全正常oracle、独立更新、admission上限、cleanup、owned scratch空を確認。
破損seedは期待したエラーで終了。100ms遅延triggersは人工pilotと自然遅延の両方で観測。
前の一斉キャンセルcleanup失敗は今回の対象外で、解決済みとはしていない。

[source inventory](forkcompare/results/syscall-inventory.json)、
[summary](forkcompare/results/summary.json)、[raw reference](forkcompare/results/raw-reference.json)。
全stack・全時系列・upstream sourceは専用ref `evidence/sql-wait-20261102` の
[`raw.tar.gz`](https://github.com/masahitojp/mariamem/blob/b5da85e6749d0fd1314933b693e89c99ead7eb6e/raw.tar.gz)。
196,877bytes、SHA256 `a89ac8f3b8cb1641a56cd8ec51206d1247e9fc2ad857c3794b74cafdedfc7311`。
workspace prefixを正規化し、original/published member hashesを保存。

scratch削除後の再集計：

```sh
python3 benchmarks/forkcompare/analyze.py --results benchmarks/forkcompare/results --check
```

実行再現はmeasured harnessの使い捨てworkspaceでbudget8GiB/free reserve16GiBを設定し、
`temp/product`へpin済みv0.6.0をcheckoutする。run.pyをevidenceへコピーして
`--phase build`、`--phase pilot`、`--phase measure`を順に実行する。
6回で再現しなくても無制限に反復しない。report refのanalyze.pyで
`--evidence <new-evidence> --results <new-results>`として還元する。
製品/guest/API/生成コード変更、CI実行、main採用、releaseはない。
