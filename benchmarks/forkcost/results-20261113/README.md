# Fork / cleanup attribution versus pgmem — 2026-11-13

**結論:** mariamemのForkはMariaDB初期化区間が主で、観測した平均Fork時間の約86% / 84% / 73%をP1 / P4 / P8で占める。準備ファイルの復元・ハンドル構築は小さい。Closeは主にguest memoryの同期解放とエンジン停止に時間を使う。一方pgmemは強制終了を使い、moduleと共有領域の解放をAPI終了後も続ける。以前の公開Close時間差を、同じ資源解放完了条件の速度差とは解釈できない。

**推奨:** 次の改善候補はserver_init内のメモリ確保・初期化・ページ読み出しに絞って評価する。今回の調査は局所化までで完了。共有イメージやファイル復元の全面変更、終了保証を弱める非同期化をこの証拠だけで採用しない。最も強い留保は、server_init区間にhost importsとスケジューリングも含まれ、観測器自身が特にpgmemの並列Closeを変えること。C関数ごとのCPU原因・削減可能量は未確定である。

[集計](summary.json) / [全子CSV](children.csv) / [各プロセスCSV](processes.csv) / [固定計画](plan.json) / [入力・overlay hash](inputs.json)

## Forkの内訳

下表は**計測ありの各P・144子の平均ms**。中央値同士の加算を避け、各子で段階の和が実測Fork時間に一致することを検証してから平均した。これを前回の計測なしp50と混ぜない。

| mariamem段階 | P1 | P4 | P8 |
|---|---:|---:|---:|
| ホスト受付・開始準備 | 0.188 | 0.212 | 0.366 |
| FS・prepared handles | 0.056 | 0.073 | 0.128 |
| 初期メモリimage取得・module準備 | 0.403 | 0.932 | 3.317 |
| MariaDB server_init | 13.756 | 18.608 | 24.105 |
| bootstrap接続 | 0.114 | 0.184 | 0.132 |
| routine schema | 0.954 | 1.272 | 1.630 |
| その他guest起動 | 0.028 | 0.035 | 0.077 |
| 実行開始〜readyの残差 | 0.343 | 0.641 | 2.889 |
| ready後のlistener等 | 0.061 | 0.100 | 0.164 |
| 合計Fork | 15.904 | 22.057 | 32.808 |

初期メモリ区間は現行のimage.Acquireをそのまま包んでいる。古いNewWithMemoryへの置換は行わない。P8の約3.3msにはimage factoryのロック取得、mapping、module構築が含まれ、その内訳までは分けていない。FS区間には最初の構造準備も含む。guest時計とhost時計は時刻を直接接続せず、同じ時計内の経過時間だけを差し引く。実行残差はpre-main・観測・framing・スケジューリングを含み、純粋な待機時間ではない。

| pgmem段階 | P1 | P4 | P8 |
|---|---:|---:|---:|
| 受付・wrapper | 0.002 | 0.004 | 0.038 |
| VFS Clone | 0.252 | 0.668 | 1.374 |
| boot wrapper | 0.002 | 0.003 | 0.008 |
| cluster host準備 | 0.005 | 0.006 | 0.005 |
| postmaster起動〜ready | 5.143 | 12.183 | 16.478 |
| listener・return | 0.055 | 0.079 | 0.132 |
| 合計Fork | 5.459 | 12.943 | 18.034 |

pgmemのpostmaster起動〜readyは複数内部processの生成・実行を含む区間で、MariaDBのserver_initと内部処理が同一ではない。pgmemのVFS Cloneよりmariamemの復元FS準備が大幅に遅い、という結果ではない。

## Closeで待っているもの

同じく観測ありの平均ms。接続のCloseからDBのCloseまでを含む、前回のcleanup区間の加算内訳。

| mariamem段階 | P1 | P4 | P8 |
|---|---:|---:|---:|
| driver接続Close | 0.0069 | 0.0118 | 0.0108 |
| WaitDisconnected | 0.0431 | 0.0860 | 0.2402 |
| shutdown設定 | 0.1214 | 0.2358 | 0.5771 |
| エンジン停止・transport残差 | 0.6924 | 1.7705 | 2.5122 |
| runtime thread join | 0.0009 | 0.0017 | 0.0289 |
| guest memory解放 | 0.8289 | 1.5917 | 2.7378 |
| descriptor・prepared map解放 | 0.0013 | 0.0016 | 0.0020 |
| host transfer等の後処理 | 0.1416 | 0.1250 | 0.2252 |
| その他API・受付・wrapper | 0.1033 | 0.1130 | 0.1607 |
| 合計cleanup | 1.9399 | 3.9372 | 6.4949 |

P8のguest memory解放2.738msのうち、release呼出自体が2.735ms。prepared fileのmapping解放は約0.0005msで、ここを混同しない。エンジン停止・transport残差には設定後の終了要求からroot復帰までと観測callbackのserialization等を含む。guest Cのshutdown時間だけではない。

pgmemはServer.Close→Cluster.Kill→KillAll(SIGKILL)を使う。各guest processはp.Exitを先に公開し、その後mod.Closeでmoduleを解放する。Cluster.Killも共有segmentのCloseを別goroutineで開始して戻る。mariamemはguest/runtimeのjoinとmemory releaseを終えてからDone/Closeが完了する。

| pgmem観測値 | P1 | P4 | P8 |
|---|---:|---:|---:|
| 公開cleanup平均 | 0.094 | 0.227 | 1.694 |
| 公開cleanup p50 | 0.090 | 0.160 | 0.857 |
| Close終了直前のmarkerから最後の観測対象解放まで・平均 | 4.517 | 18.361 | 28.227 |
| 同・p50 | 4.496 | 14.610 | 25.940 |
| 同・p95 | 4.951 | 60.707 | 56.293 |

全Pで144/144子に、Close終了直前のmarkerより後の解放完了が記録された。対象はmodule.Closeとcluster共有segment.Closeであり、Go heapのGC完了やRSSの減少までを意味しない。この処理は後続子と重なるため、上の非同期時間を子のAPI時間やbatch wallへ単純加算してはいけない。最後の観測対象解放を待つdrainはbatch timer外で実施し、traced全試行で完了を確認した。plainは従来どおり公開APIのcleanup成功を検証する。

## 観測器の影響と通常値

以下は今回の新しいcohort。Fork/cleanupは各cellの144子をまとめたp50、batchは3プロセスの中央値。全条件で同じ観測コード入りバイナリを使い、plainでは記録を無効化する。従来バイナリとの厳密な無摂動証明ではない。

| 対象 | P | mode | Fork p50 ms | cleanup p50 ms | batch中央値 ms |
|---|---:|---|---:|---:|---:|
| maria | 1 | plain | 15.731 | 1.904 | 938.23 |
| maria | 1 | traced | 15.875 | 1.922 | 945.65 |
| maria | 4 | plain | 22.660 | 3.284 | 345.54 |
| maria | 4 | traced | 22.322 | 3.678 | 350.39 |
| maria | 8 | plain | 33.147 | 5.377 | 310.22 |
| maria | 8 | traced | 32.213 | 5.570 | 301.16 |
| pgmem | 1 | plain | 4.959 | 0.087 | 524.50 |
| pgmem | 1 | traced | 4.953 | 0.090 | 540.95 |
| pgmem | 4 | plain | 9.106 | 0.150 | 234.98 |
| pgmem | 4 | traced | 9.100 | 0.160 | 282.27 |
| pgmem | 8 | plain | 15.457 | 0.272 | 225.28 |
| pgmem | 8 | traced | 16.143 | 0.857 | 233.22 |

pgmem P8のcleanup p50はplain0.272→traced0.857ms、P4 batch中央値は234.98→282.27ms。forkの中央値は比較的近くても、並列cleanupの観測影響は無視できない。非同期解放の機構・API終了後にも続く事実はsourceと全traceで確認できるが、観測値をそのまま無計測製品の追加時間と断定しない。mariamem P8 plainにも長いSQL区間が残り、今回の辞書修正で自然tailが全滅したとは主張しない。#143は保留継続。

## 別枠CPUプロファイル

各製品P1/P8で96子の別プロセスを1回ずつ採取。通常・traced計測ではprofilerを無効化。profileはForkだけでなくSQL・終了・背景処理を含むbatch全体で、終了時のprofiler drainもある。時間区間の内訳へCPU割合をそのまま割り当てない。

mariamem P8（総sample3.88 CPU秒）では、MemoryMapping.Grow→syscallの経路に0.47秒（12.1%）、memclrに0.50秒（12.9%）。memclrの呼出元はguest MemoryFill0.30秒、prepared.Block.ReadAt0.16秒、rootRead0.04秒。MemoryMapping.Close→syscallにも0.12秒（3.1%）。これらは具体的なメモリ処理の調査先を与えるが、全てを消せる余分な処理とは言えない。Fn番号を未検証のC名へ置き換えていない。

pgmem P8（総sample2.25 CPU秒）にはmemmove0.68秒（30.2%）があり、FSを含むコピー処理のコストがゼロという比較でもない。macOSの短いCPU samplingにはsyscall/runtime帰属の限界がある。top、memclr、mapping caller treeと完全なprofileを保存した。

## 検証・範囲・再現

固定36通常プロセス・1,728子、warmup12、正負pilot4、profile4の計56プロセスを完了。通常/warmup/profileのSQL値、独立性、公開API cleanupとtemporary directory除去は全てPASS。negative seed2件は意図したoracleで失敗しcleanup成功。traceは子IDとcontext/callbackで結び、global current-childは使わない。通常traced全子でFork/cleanupの加算一致とPG非同期解放完了を検証。再集計と5つの破損証拠拒否対照PASS。

同じ1,000行/48子/Pipe/cap=P、GOMAXPROCS8/GOGC100。Apple M1・16GiB・macOS27.2.1、Go1.27.4、CGO0。バッテリー92%放電中、開始時の背景VM約33%CPU。専用静穏ホストではなく、温度・電源・背景負荷を統制した性能保証ではない。mode/製品/Pの順を交互にし、遅い観測も全て保持した。

製品 source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`、guest `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`。pgmem v1.18.2 source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`。測定harness source_commit `6211dc9ef5f2e8c3a4ce367e3462c1c604ef228b`。Git identity helperとclean checkoutをbuild前に検証し、生成ソースやguestは変更していない。Goの観測overlayの前後hashとbinary buildinfoをinputs.jsonへ保持。harnessに残る以前のsource-pins.jsonは今回の入力ではなく、今回のplan.jsonとinputs.jsonが使用した入力を示す。

`python3 analyze.py --check` で保存データだけから検証できる。完全CPU profileは `.pprof.b64`。base64 decode後に `go tool pprof -top <profile>` で読める。プロフィールのprotobuf string table中の個人パスだけを正規化し、numeric fieldsとstring indicesを保持。元と公開版のhashをnormalization.jsonに記録。raw trace JSONの空白を圧縮したが、数値や観測を除外していない。SHA256SUMS.jsonが公開内容を固定する。

再計測は新しいmanaged workspaceへmeasured harnessとpgmem pinをclean cloneし、temp/source・temp/pgmem、evidenceへ保存したbuild/overlay/measure/planを配置。build.pyはexact Go1.27.4を要求。helperのrunでbuildし、監視プロセス終了後にmeasure.pyを手動のexclusive lock下で実行する。12GiB上限・空き12GiB、各build1200秒、各process120秒、計測全体900秒。フルディスク走査は試行前後のみ。結果は新しいcohortとして保存する。

この調査から追加実験・性能修正・main統合・Qualification・releaseは開始しない。次に進む条件はserver_init内の候補処理と有限の対照を定義し、正しさと終了保証を維持できること。改善効果はまだ未測定。後片付けはcleanup.jsonに記録する。
