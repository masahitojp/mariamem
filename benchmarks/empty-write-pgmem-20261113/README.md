# 空Write省略後のpgmem同条件比較 — 2026-11-13

## 結論

同じ公式modelcase70テストを同じhost・toolchain・通常設定で比較すると、process wall中央値はpgmem388.716ms、mariamem通常471.461ms、空Write省略453.305ms。省略版はpgmemより**約16.6%長い（中央値差64.589ms）**。通常版とpgmemの中央値差82.745msからは縮んだが、逆転していない。

通常版に対して省略版のwallは4/5組で短縮、ペア変化中央値−2.58%。総CPUは5/5組で増加、ペア変化中央値+0.19%。総CPU中央値はpgmem1.381秒、通常2.426秒、省略2.455秒で、省略版はpgmemの約1.78倍。空Write除去は小さなwall改善候補だが、CPU差の解消策ではない。前回の別cohort値をこの比較へ足し合わせない。

**推奨:** この結果だけで本体への採用を急がず、latencyとCPUの交換条件を維持して候補を保存する。差の大きいsample/SQLの既存調査は別の改善軸。最も強い採用側の根拠は前回5/5・今回4/5のwall短縮と機構上の空Write除去、反対材料はCPU改善が無く、共有hostの小さい比較であること。大きなIPC方式変更を本結果で正当化しない。

## 固定条件と結果

公式pgmem v1.18.2 / PostgreSQL18のmodelcase（カテゴリ20、商品500、ユーザー1000、sample注文40、読取50/更新20 tests）。mariamemはDSNのinterpolateParams=trueを継承・assertし、sampleの明示Prepared statementsはそのまま。両方ともin-process client dialer。通常mariamemと省略版は**同じbinary**のpackage初期化時スイッチで選ぶ。IPC observer/profilerは全primaryで無効。

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、test.parallel8。各arm1 warmupを除き、3者の順序を回ごとに回転・反転する固定5組。全18プロセスで70 assertions PASS（1260 leaf tests、primary1050、warmup210）。failure/retry/除外なし。前後disk/free-space guardはtimer/getrusage差分の外、timed process130秒timeout。専用静穏hostではなく背景負荷/温度を統制した保証ではない。

|5回の中央値|pgmem|mariamem通常|空Write省略|
|---|---:|---:|---:|
|process wall ms|388.716|471.461|453.305|
|process wall範囲 ms|376.659–407.034|460.603–482.255|445.699–480.132|
|総CPU ms|1381.412|2425.700|2455.483|
|user CPU ms|975.368|2081.325|2111.026|
|system CPU ms|396.212|339.350|336.062|
|公式recorder elapsed ms|337.342|462.367|444.594|

CPUは全thread合計のgetrusage user+systemで、wallより長くなり得る。各指標を独立に中央値化しているため、user中央値+system中央値は総CPU中央値と必ずしも一致しない。recording区間外のpackage初期化/process開始終了があるので、process wallと公式elapsedを混ぜない。

|round|省略版のwall / pgmem|省略版wall変化 / 通常版|省略版総CPU変化 / 通常版|
|---|---:|---:|---:|
|0|+10.35%|−3.24%|+3.45%|
|1|+9.53%|−7.56%|+1.97%|
|2|+20.55%|−2.58%|+0.15%|
|3|+16.62%|−2.40%|+0.19%|
|4|+27.47%|+1.84%|+0.18%|
|ペア中央値|+16.62%|−2.58%|+0.19%|

同じroundの比較でも実行は順番に行う。loadの揺らぎを完全に消した対照ではない。今回の候補/通常版の中央値比は−3.85%だが、ペア判定は−2.58%を優先する。CPU増加の因果・普遍性をこの5組で確定しない。

## 段階値の位置づけ

以下は各process内の段階中央値をさらに5回で中央値化した補助値。重なる段階/各子を足してwall差を作らない。

|ms|pgmem|通常|省略|
|---|---:|---:|---:|
|boot|50.905|43.859|44.257|
|import|64.329|26.975|27.275|
|Snapshot|16.266|5.011|4.879|
|Fork|22.567|25.596|27.779|
|sample投入|33.241|75.733|79.296|
|test本体|0.702|1.974|1.989|

wallが短くても各段階の独立中央値がすべて短くなるわけではない。critical path/overlap/schedulingを今回別途分離しておらず、どの区間が何ms分wall差を生んだと推測しない。sample/SQLに残る差は大きいが、SQL移植・driver/protocolも異なる。

## 同じ比較としての限界

- schema/triggerはMariaDB方言へ移植、migrationは公式5ファイルから1ファイルへまとめたまま。DDL transaction/batchingやindex表現の差を維持するのでimport差をengine性能だけへ帰属しない。
- mariamemのSnapshotは元DBを消費するため、読取共有用に1 Forkを追加する。費用を含む。
- pgmemはClose後にmodule/segment解放を続ける。mariamemの同期完了条件と一致する資源解放完了時刻を比較しているわけではない。今回は公式APIのtest process終了までの比較。
- 元fixtureのClose返却errorを全て個別assertする追加oracleは入れていない。70 SQL/independence/trigger assertionsとprocess exitを維持し、前回の132 joined DB観測およびFD/transport/error-focused testsをexact同一source overlayとして再利用する。今回新しいcleanup/tail保証を主張しない。
- RSS、別platform、純粋engine CPU、Docker/devbox/Testcontainersは未測定。

## source identity / 再利用

製品source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`、pgmem source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`。build前にscripts/git_identity.pyで各identityを確認。省略helperは前回の[有限試作](https://github.com/masahitojp/mariamem/blob/c2cadc50d10b3d885d665437c9d3be4ea7ee3e0b/benchmarks/skip-empty-write-20261113/README.md)とSHA256完全一致をbuild前に確認した。新しいruntime挙動は追加せず、以前のunit境界検証を再実行していない。

省略はmixed vectors内の空要素だけ、all-emptyは従来のWriter呼出/エラーを維持。canonical guest/runtime sourceを変更せず実験Go overlayで選択する。入力SHA・binary hashes・run plan・source/harnessを保存。正式な生成postprocessorへ導入したcandidate、main採用、CI/releaseではない。

再現: 新managed workspaceのworktreeを製品pinへ、temp/pgmemへ公式v1.18.2をclone。harnessをtemp/mariaへ配置し、go.modの../../worktreeを維持。prepare.pyでhelper/observer overlayを生成し、experiment_empty_write_test.go.txtをtemp/experiment_empty_write_test.goへ配置する。build.pyがprivate cache/Go1.27.4で両binaryをbuild、measure.pyが固定順序・前後guardで18 processを実行する。10GiB/空き12GiB、build1800秒、各process130秒。analyze.pyで保存データから5triplets/1260 assertionsと中央値を検算する。再計測は新cohortとして保存する。
