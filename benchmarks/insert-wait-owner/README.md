# INSERTの長い待機：ページ読み込みとタスク実行の照合（2026-11-17）

## 結論

前回の394.119ms待機は、注文INSERTの外部キー検査からテーブル定義を読み込む際の **InnoDBページ読み込み完了待ち**。通知元はread_io_callback → buf_page_t::read_complete。Go schedulerの実行待ちや通信自体を主因とは扱わない。

保存トレースでは400ms周期のthread-pool maintenanceからworkerが追加され、その子孫がsimulated AIOとread completionを実行し、待機を解除する系列まで確認できた。ただし **当該I/Oタスクの投入時刻、当時のqueue/worker状態は未記録**。394ms全体をqueue滞留と断定したり、creation_pending・concurrency・read groupのどれかを原因認定するには不足する。

同じページ・task・futexを結ぶ観測器で固定8回を実行したが、100ms以上のpage_waitは0回、最大25.192ms。今回の詳細診断は **NOT_REPRODUCED**。長いケースのowner/queue遅延は未解決だが、調査対象と観測方法は具体化できた。追加sampling・製品変更は行わない。

## Identityと対応表

測定製品source_commitは6558ee8fb2211313a8aa0ea6070ac5256767811a、harness/evidence source_commitはdc2dbf37ff5b70104d3c434cdfda612a0654ae9b。git_identity.pyでcommit objectを確認した。追加観測はGo overlayのみで、元worktreeの製品ソースは変更しない。

Guest SHA256 `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450` をCI artifact14103568702のmariamem.wasmから再検証。Wasm自体はname sectionがなく、初回の直接抽出は空だった。旧buffer-zero-spikeのmapは別guestなので使用しない。

正しいmapはperf/buffer-pool-zeroingのbuffer-zero-candidate/validation/function-map.txt。SHA256 `ad4c0607efcb95328ebf49a21c09d5b3d4ff7c40c4fc2b9f1aa31fbed6c6704e` が、同guestの既存binding-review.jsonと一致する。元refのfull SHAと取得物hashはsymbol-binding.jsonに保存。新規にguestを再ビルドしたという主張ではない。

| 前回のframe | 対応する処理 |
|---|---|
| Fn17028 | row_ins_check_foreign_constraints |
| Fn17736 / Fn17707 / Fn17708 | dict_table_open_on_name / dict_sys_t::load_table / dict_load_table_one |
| Fn18161 | buf_page_get_gen |
| Fn16784 | buf_page_t::read_wait |
| Fn16621 | ssux_lock_impl<true>::rd_lock_nospin |
| Fn18277 / Fn18171 | read_io_callback / buf_page_t::read_complete |
| Fn16600 / Fn16594 | thread_pool_generic::maintenance_func / add_thread |
| Fn18239 | simulated_aio::simulated_aio_callback |

これはページの読み込み保護用待機であり、「他のユーザートランザクションの行ロック競合」とは判定していない。どのspace/page番号かは今回の観測にも含めていない。

## 保存済みの長いケースの系列

前回run7のG192はprepared INSERT INTO orders ... RETURNING idの結果を398.107ms待った。guest側G8817は394.119ms待ち、通知後19.136µsで実行再開した。

追加の保存トレース解析で次を確認した（時刻はGo traceのns）：

1. G8817が323443543983936からpage read_wait経由で待機。
2. G8432がmaintenance_func → maybe_wake_or_create_thread → add_threadからG17593を323443931875712に生成。
3. G17593がsrv_master_callback → dict_sys_t::evict_table_LRU → tpool_wait_begin → wait_beginからG17594を323443932319872に生成。
4. G17594がsimulated_aio_callback → submit_taskからG17595/G17598を生成（後者323443933101760）。
5. G17598のread_io_callback → read_complete → wakeがG8817を323443938102656に起床。

同時間帯にはbuf_loadがpending reads、page cleanerがpending writes、purgeがtable-open待ちで止まっていた。これは停滞が1つのSQL呼出しだけに閉じていない手掛かり。ただしこれらを同じwait objectのownerと同一視しない。

MariaDBの固定source `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` のtpool_generic.ccを取得した。maintenance周期は400ms。task queueが非空ならlong task判定後worker補充を試み、無進行時にもadd_threadする。add_threadにはmax threads、throttling、thread_creation_pendingのgateがある。このsourceには当該guestのsource.patchによる変更がない。**周期の一致だけでなく実際のmaintenance stackは確認できたが、どのgateが先行進行を妨げたかは不明**。

## 固定8回の詳細診断

Go1.27.4 / macOS arm64 / GOMAXPROCS8 / GOGC100 / CGO0。前回P8 matched 70 tests、SUM/audit有効、UPDATE OF status、revenue事前集約、sync Closeを維持。8 processes・560 cases全PASS。比較armなし、性能改善率は計算しない。観測負荷でscheduleが変わる可能性がある。

観測点はpage_wait/page_complete/read_callback、task submit/execute、maintenance/add_thread、host Futex_wait/wake。module base＋guest pointerで識別し、goroutineと時刻をGo traceから取得。通知者とlock ownerは同義ではない。全runtime traceを保持。

| Run | 最大page_wait ms | 最大submit入口→task execute入口 ms |
|---|---:|---:|
| 0 | 25.192 | 25.072 |
| 1 | 20.137 | 21.999 |
| 2 | 20.199 | 16.447 |
| 3 | 11.436 | 17.882 |
| 4 | 23.943 | 27.748 |
| 5 | 15.801 | 19.490 |
| 6 | 15.584 | 15.876 |
| 7 | 13.690 | 19.667 |

submit入口→execute入口はenqueue mutex取得なども含み、純粋なqueue滞留時間ではない。task addressの再利用を考慮して同module内で順序照合しているが、task group内の追加queue全体を説明する値ではない。

各runの最大page_wait例では、同module・同pageのpage_completeと、同じfutex addressへのwakeを全8例で結べた。完了workerのtaskと直前submit復帰を結ぶ区間は0.441〜8.265ms（matched-page-examples.json）。これは通常例で観測器の関連付けが機能した証拠であり、過去394msの内訳ではない。

## 次への推奨と終了条件

主候補は「共有thread poolがI/Oを進めるworkerを適時確保できず、maintenanceによって進行を回復する経路」。現時点では原因候補であり修正根拠ではない。io.Pipe、timer短縮、worker無制限化の採用へは進まない。

次に投資するなら、ランダムな実スイートの追加連続計測より **worker開始とタスク投入の順序を制御する小さな再現** を推奨する。creation_pending・active/waiting/long counts・concurrency・queue長と、同taskのenqueue/dequeueをmutex下で記録し、どのgateが補充を止めるかを確認する。これは別の実験設計であり今回未実施。制御reproが成立した場合のみ解除条件を1点変更する対照へ進む。短い通常例だけでは製品修正を正当化できない。

#140の旧PREPARE停滞とはpool/maintenanceという機構の類似があるが、同一原因とは認定しない。#143は旧UPDATE/UNDOページ待ちで、今回のdictionary page readと同一ケースではない。Issueの再開・close・統合・releaseは行わない。

## 再現・証跡・制限

PLAN.mdの固定8回のみ実施。再帰disk guardはビルド時と診断processの前後だけで、計測中には走らせない。最初の観測準備は巨大generated sourceのdifflib計算が長引き手動中断した（まだビルド/計測前）。変更点は再生成script＋入力/出力hashで保存する方式に修正。workspace runnerはfailed後の再実行を拒否したため、standalone disk guard（6GiB、空き8GiB、600s）で初回buildを完了。失敗はconsole.logに保持し、成功した8回をやり直していない。

再現は実験workspace (`worktree`, `temp`, `evidence`) を用意し、測定source dc2dbf37をcheckout。evidence/observe.py --build-only、run.py、analyze.py、correlate.pyの順で実行。Go1.27.4で `go build -o temp/gotrace cmd/trace` が必要。parse_saved.pyは前回run7のtraceを解析する。scriptsは保存場所そのまま実行せずworkspace/evidenceへ配置する。

manifest.jsonは圧縮前後SHA256を記録。全8本trace、observer全event、抽出系列、短い対応例を保存。生成overlay・binary・compiler cache・取得zipは再生成可能なので削除する。生の証跡はexperiment branchでのみ保持し、mainへの直接統合は想定しない。製品を変更していないためrelease acceptanceや広範なruntime testsは実施していない。
