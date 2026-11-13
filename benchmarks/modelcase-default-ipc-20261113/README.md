# 通常設定のmodelcase再比較と内部IPC観測 — 2026-11-13

## 結論・次の判断

mariamemの通常DSN設定（interpolateParams=true）を継承して公式pgmemと取り直した。固定5組のprocess wall中央値はpgmem392.983ms、mariamem477.628ms、mariamemが約21.5%長い。両製品70テスト全件PASS、全5組でpgmemが短い。前回の補間を無効化した比較は通常設定の代表値ではなく、この比較を現在の基準にする。別cohortなので前回との差を補間だけの因果効果とはしない。

内部IPCは、1スイート約5,800要求、host→guest約0.44MB、guest→host約1.59MB。**guest側Writeの約半分、約5,800回が0 byte書き込み**だった。生成WASIのwriteVecが空iovecにもos.File.Writeを呼ぶ実装と一致する。次に推薦する小試作は、通信方式全体の交換より先に、この空iovecを安全に省略できるかを比較すること。省略後の性能利益は未計測であり、半数のWriteを減らせば全体が半分になるとは言わない。

最も強い留保は、観測はRead/Writeメソッド境界の回数で、直接のkernel tracingではないこと。短いCPU profileもSQL本体・fixture・起動を含む。WASIのFD検証、short write、error、EOF・shutdown・cancelの契約を保つ確認が次の条件。今回transport/buffer/guestを変更した実装候補は作っていない。

## 1. 比較を通常設定へ修正

maria-harness/store/fixture_test.goはmysql.ParseDSN(s.DSN())後のInterpolateParams=falseを除去し、継承値がtrueであることをassertする。MultiStatements/ClientFoundRows/in-process Dialは前回と同じ。明示Prepareするsample3 statementsは引き続きpreparedのまま。pgmemは公式v1.18.2 modelcaseのpgx設定（自動statement cache、in-process Dial）を維持する。二つのprotocolが同じという比較ではなく、両製品の通常利用設定の比較。

|5本の中央値 ms|pgmem|mariamem|
|---|---:|---:|
|process開始前〜終了|392.983|477.628|
|公式recorder elapsed|346.873|468.709|
|boot|50.921|44.484|
|import|65.504|27.756|
|Snapshot|16.554|4.650|
|各process内Fork中央値の中央値|25.845|25.557|
|sample中央値の中央値|34.550|80.706|
|test中央値の中央値|0.712|2.320|

外側wall範囲はpgmem370.650–412.320ms、mariamem469.439–515.370ms。1warmup/製品＋交互5pair。70leaf×12プロセス=840 PASS（本測定700、warmup140）。段階中央値を足してwall差を作らない。mariamemには消費型Snapshot後の読取用1 Forkがあり、元のmigration5→1ファイル等の移植差も維持。importの速さは同一DDL batchingの速度差ではない。Docker/devbox/Testcontainersは実行していない。

## 2. 内部IPCの回数とサイズ

製品internal/guest/linked.goの二つのos.Pipeをそのまま残し、同じRead/Writeへ渡す薄いobserverをGo overlayで追加した。host write/readとguest write/readの4方向を集計し、DB/テストlabelをcontextで伝える。SQL文字列を記録せず、framed payloadのサイズとrequest opcodeだけ数える。初期ready/停止も含む。各guest executionと全workerの終了後にDB別JSONを保存してから元の完了channelへ結果を渡す。host EOF/Closeは終了中の場合があるため、EOF回数を完全な後処理の数には使わない。

観測on3プロセスは各22 DB（root1、reader1、writer20）がjoined終了、全exit_error空。各DBでhost write bytes/frames = guest read、guest write bytes/frames = host readを照合した。保存時点で全データbytes/frameを捕捉できている。

|1スイートの観測範囲|3回の範囲|
|---|---:|
|通常要求frame|5,759–5,794|
|停止frame|22|
|応答frame（ready含む）|5,781–5,816|
|host Write呼出|5,781–5,816|
|guest Read呼出|11,500–11,524|
|guest Write呼出|11,562–11,632|
|うち0 byte Write|5,752–5,787|
|host Read呼出|11,562–11,632|
|host→guest bytes|441,382–442,067|
|guest→host bytes|1,584,579–1,590,988|

通常の応答は既にheader+bodyを一緒に書くことが多い。主なguest Writeサイズは219/220/218bytesで、単純にheader4bytesとbodyの二つへ分割しているという仮説ではなかった。2回のWriteの片方が0 byteとなるケースがほぼ毎応答にある。host側は明示的に4byte headerとbodyをio.ReadFullで読む。guest側Readには3byteの小さい読みが各約5,750回あり、WASI readVecが複数iovecを個別Readへ展開する実装との対応が調査候補。ただし、readvのshort read/blocking/EOFを同義に維持する設計が必要で、今回は変更しない。

### 空書き込みの根拠

- 製品code/base/base.goのwriteVecは、各bufに対し無条件にdst.Write(buf)を行う。
- guest stdoutはlinked.goのchildOut（os.File）へ接続される。
- observerはその同じWriterを委譲し、約半数で0byte・errorなしを記録。nonzeroのshort writeによる0ではない（os.Fileはその場合errorを返す）。
- 実際のGo1.27.4 os.File.Write→internal/poll.FD.Writeはlen0を先に除外せずsyscall.Writeへ進む。従って空iovecを下へ流さないことは、空のOS Write呼出を減らす具体的候補。

これはkernel tracingで空writeの実時間を独立測定したものではない。空iovecの発生元を未検証のC関数名へ置き換えたり、Write回数とCPU時間を同一視したりしない。

### どの要求が多いか

prepared API opcode5は全3回で5,166 frame、約89%。21回のLoadSampleがそれぞれ240 EXECUTE＋3 PREPARE＋3 CLOSEを行う21×246と一致する。通常の単発parameter SQLの補間を有効にしても、明示statementを使うsample投入が多数の往復を作る。残りはtext query、session open/close、option設定。frame総数の小変動はdatabase/sqlの接続生成・pool利用の違いを含む。

従って通信方式の局所改善のほか、アプリfixtureとして共通sampleもSnapshot前に準備する案に効果余地がある。ただしそれは公式workloadの実行モデルを変更する別比較であり、今回の結果はそのまま保持する。

## 観測負荷とCPU profile

同じoverlay binaryでoff/on各3回、順序交互。process wall中央値はoff499.380ms、on502.631ms。個々のpairはonが−15.9/+11.7/+13.9msで、観測影響は一定ではない。baseline比較の477.628msと別cohortなのでobserver費用をその差で求めない。counterの各Read/Write elapsedには待機・idleを含む。DB間で重なるためsumをwallへ加算しない。ledger保存IOはonの終了時間に含まれる。

通常設定・observer offの別profile:

- GetOrder: 20反復/200 leaf、500ms CPU sample。rawsyscall330ms/66%、guest Fd_write→writeVec→os.File.Write経路220ms/44%。
- Revenue: 20反復/200 leaf、2.10 CPU秒。rawsyscall760ms/36.2%、MemoryEA累積590ms/28.1%（MemoryInBoundsを包含）。
- CreateOrder: 20反復/80 leaf。top/caller treeを保存。SQL/trigger/sample投入と複数Forkを含む。

起動・共有sample準備・background・テスト出力もprofileに入り、短いmacOS samplingのsyscall帰属には限界がある。rawsyscall割合をそのまま削減可能なwall割合へ変換しない。Read/Write時間からSQL実行時間を差し引くこともできない。#65/#131のprepared出力再利用による性能利益は依然未測定。

## 次の有限試作の条件

推奨: まず空iovecを下のWriterへ渡さない最小候補を、元のfd_writeと内容・返却bytes・errorで比較する。FD検証、zero/all-empty/mixed vectors、partial write、write failure/閉鎖、並列応答のframing、shutdown/cancelを対象にする。その後、通常設定の同じ70テストでWrite回数と全体wall/CPUを固定回数比較する。改善が無い場合も終了可能。同期完了保証を弱めない。

空iovec省略はまだ製品実装・性能評価していない。transport全体をio.Pipe等へ替える広い案、WASI readVecのreadv相当化、#119 cleanup設計、#162 Close tail、#143 UPDATE待ちを同じ変更へ混ぜない。新C/WASM生成・設定既定変更・CI/releaseは今回実施していない。

## identity・再現・保存

製品source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`、pgmem v1.18.2 source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`。build前にgit_identity.pyでsource/tagを確認。Go1.27.4 darwin/arm64、M1/16GiB/macOS27.2.1、CGO0/GOMAXPROCS8/GOGC100、test.parallel8、共有host。binary hashとoverlay sourceを保存。guest/engine/runtime正規sourceは不変。

比較12＋IPC off/on8（warmup2含む）＋profile3、計23process、成功1,880 leaf tests。IPC on4回は全88DBのguest joined完了を確認（primaryは66DB）。独立性・trigger等の元の70 assertionsを維持し、counterのbyte/frame両端一致を検査。analyze.pyで保存データだけから再計算できる。trace/log、IPC原記録、top/caller tree、harnessとoverlayを保存。完全pprofはローカルevidenceにも保持。

新しいmanaged workspaceでtemp/pgmemへ公式tagをclone、worktreeを製品pinへ合わせ、temp/mariaへmaria-harnessを配置する。go.modのreplaceは../../worktree、build.pyで比較binaryをbuildし、measure.pyで1warmup＋交互5pair。ipc_overlay.pyは新worktreeからlinked overlayと絶対パスmapを生成、build_ipc.pyで観測binaryをbuild、measure_ipc.pyでoff/on各3回と別profileを実行する。prepare.pyは前回artifactから元ハーネスを復元する参考スクリプトで、最終label付きsourceはmaria-harnessが正本。10GiB/空き12GiB、build1800秒、各process130秒、計測900秒のguard。再計測は別cohortとして保存する。
