## 現在地・Solへの実行指示

計画作成済み、計測未着手。実行担当は **gpt-6.1-sol**。Humanの次の実行指示で、以下の有限調査を実行する。今回の依頼は結果整理・Issue整理・実行計画まで。親 #182、完了した区間計測/SUM対照 #186 を引き継ぐ。

**判断する問い:** 明細INSERTの要求受け渡し、またはSQL実行中のGo runtime/WASIヘルパーに、SQL・公開契約を変えずに減らせる具体的な費用があるか。結論は「局所試作一案を推奨／有望な候補なし／証拠不足」の一つ。計測の細分化自体を成果の終点にしない。

## 既知の結果と解釈

[SUM対照の固定証跡](https://github.com/masahitojp/mariamem/blob/706072d8dbfa76acb23d302d6bfaa08b91c444b5/benchmarks/insert-trigger-stages/results-20261114/sum-control/README.md)。P8・差分加算・観測onの同じprimary標本から:

| 100件、24 DB平均 | ms |
|---|---:|
| client呼出ループ |21.871458|
| worker内合計 |16.122561|
| mysql_stmt_execute |14.876417|
| worker内のSQL以外 |1.246144|
| clientループとworker合計との差 |5.748897|

5.75msは純通信時間ではない。client呼出ループとworker区間の端点も同一ではなく、driver・入力通信・dispatch・スケジューリング等を含む差。SQL時間にも生成Go、WASI、atomic/待機ヘルパーが含まれる。95%がSQL区間という観測は「95%がMariaDB固有で改善不能」の証明ではない。

具体的な仮説: 測定sourceの `internal/guest/guest.go` `Process.write` は要求ごとに送信channel/goroutineを作り、`Call` は応答channel/pending登録を行う。guest `resident.inc` はworkerを通知する。これらの頻度・費用は未帰属であり、常駐sender等の採用を先に決めない。

## 固定入力 — latestへ置換しない

- product `source_commit=bb1e937ae75b5788c8548a52987d9d42f78292d5`。
- guest SHA256 `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`。
- harness/observer継承元 `706072d8dbfa76acb23d302d6bfaa08b91c444b5`、`benchmarks/insert-trigger-stages/results-20261114/sum-control/`。再現順は restore.py→extend.py。付属hashとgit_identity.pyで照合する。
- Go1.27.4/macOS arm64、CGO0、GOMAXPROCS8/GOGC100。同条件が用意できなければ旧値と直接比較せず、差分と判断への影響を明記する。
- 差分加算版を診断の主対象にする。これは採用済みSQL基準への変更ではない。監査status限定、注文行UPDATE、5 trigger、制約/index、時刻更新を保持。実登録trigger本文とSUM不存在を検査する。
- 100件prepared明細INSERT、8 DB/process。Fork・親40注文・BEGIN/PREPAREは前、全DBのraw投入完了後にCOMMIT/oracle/Close。各DB逐次100 Exec、DB間並列P1/P8。
- 売上SQL設定はREVENUE_PREAGG=1を保持するが、このprobeでは売上queryを実行しない。SUM版/他エンジン/full suiteは今回の新しい比較対象ではない。
- root checkoutの既存dirty状態を保持し、experiment/<purpose>の専用workspaceで作業する。mainが進んでいてもこの診断途中にsourceを混ぜない。後の製品候補化では現行mainとの差分を改めて確認する。

## 実行順序

### 1. 境界と対応IDを先に設計する

既存request IDだけはDB間で重複する。必ず `(process, DB instance, connection/slot, request ID)` で対応させ、client Execとの対応も明示する。同一プロセスのmonotonic clockを共有する。

最低限、次のイベントと実source位置を一覧にしてから計測を開始する:

1. client Exec入口/出口
2. host Call入口、送信キュー待ち前/後、実write開始/終了
3. guestの要求frame読取完了（kernel Read終了と混同しない）
4. 対象worker処理開始、SQL開始/終了
5. reply構築開始、実出力開始/終了、worker終了
6. host応答frame完了、decode完了、待機clientへの通知

host writeとguest read、reply writeとhost readは重なる。逐次直列のように足し合わせない。イベントの因果関係を図または表で示し、排他的に定義できる区間だけ加算する。定義不能な残差はそのまま残す。ID不一致・欠落・重複は性能標本から黙って捨てず失敗として保存する。

### 2. 軽量timeline計測の妥当性を先に確認する

観測コードはSQLや同期方式を変えないoverlay。測定中のファイル出力、global mutexによる全DB直列化、高頻度メモリアクセス/atomicごとの時計計測を避ける。データは終了後に出力。

観測parser/ID照合には、小さい固定fixtureで分割frame、連続frame、同じrequest IDを持つ異なるDB、欠落/重複を含めて検出を確認する。これは観測器の検査であり、製品全受入れの代用ではない。

初回warmupで各DB100 Execが全境界に対応すること、SQL oracle/Closeを確認。失敗時はcampaignを止める。観測器の明確な不具合は最大1回修正してwarmupからやり直し、失敗ログを保存する。期待結果を緩めて通さない。

### 3. 固定したtimeline off/on対照

- P1/P8、同じbinary・同じSQLで timeline off/on。
- 各arm各Pで1 warmup＋交互順3組 = **16 process**。
- cpu/profile/Go traceはこのcampaignで無効。
- offにも残るhook/フィールドを記録し、完全無加工binaryとの差ではないと明記。
- raw100件wall、process wall/user/system CPU、区間/回数、paired差、全標本範囲を保存。観測による遅延をゼロと仮定した補正は禁止。
- 小さい候補の費用が観測の揺れと区別できなければ「未判定」。自動的に反復数を増やさない。

### 4. CPUスタックは別の固定診断campaign

- timeline計測と同時にCPU profilerを有効化しない。
- P8、差分加算のみ、**3 process**。各process最大8 wave、各wave 8 DB×100 INSERT。8 DBを準備後にraw phaseのみprofile取得し、各wave終了後にoracle/Close。
- profiler開始/停止、raw phaseの時刻を記録。profiler停止のtailや背景threadも含まれ得る。Fork/COMMIT/CloseをSQL CPUへ集計しない。
- 生成関数は固定guest function-mapへ照合。呼出stackで「host受け渡し」「SQL配下のruntime/atomic/memory」「guest SQL本体」「背景/未分類」を区別する。累積親子を二重加算しない。inlineされたhelperが見えないことを費用ゼロとしない。
- `mysql_stmt_execute` 配下にあることはCPUの帰属であり、wallの割合ではない。syscallサンプル比率もwall通信時間へ換算しない。
- samplesが乏しい／帰属不能なら不足を報告して終了。Go execution trace、block/mutex profileの追加キャンペーンや全メモリアクセスの計測を自動追加しない。

## 事前に固定する結果表

| P / 観測mode | raw100件wall | 送信キュー/実write | frame受信→worker開始 | SQL | reply/host decode/復帰 | 未分離/重なり | 整合性 |
|---|---:|---:|---:|---:|---:|---|---|
| P1 off/on |未測定|未測定|未測定|未測定|未測定|未測定|未検証|
| P8 off/on |未測定|未測定|未測定|未測定|未測定|未測定|未検証|

別表: CPU診断のstack分類、flat/cumulative sample数、分母、関数map、未分類。offでは未観測の区間を0と書かない。

集計: process内のDB平均/中央値を明記し、主比較は3組のpaired値とその中央値。各P・各mode・各cohortを混ぜない。profile値をprimary性能表へ入れない。256/320 DB等の件数は実際に実施したwaveとログから集計し、予定件数をPASSと書かない。

## 維持する検査と範囲

orders40/items100/audit40/合計値/500商品のstock/FK/CHECK拒否、実登録trigger本文、DB/statement/transaction/Snapshotの公開Close error。観測ID・境界順・回数を同時に確認。consumer APIやキャンセル/Closeの製品挙動を変える試作は今回行わない。

送信のgoroutine削減が有望でも、現在のcancel時Abort・blocked write解除・worker failure・pending応答処理を維持できるかを候補の条件として示す。通常1 DBに1 active clientであってもMariaDB背景threadがあるため、atomic/lockを「単一thread」として省略しない。境界検査や失敗oracleを外す案は対象外。

## 判断・停止条件

- host受け渡しが具体的区間として目立つ: source位置、頻度、保持するcancel/Close契約を示し、sender再利用等**一案だけ**の局所試作計画を推奨。
- SQL配下のruntime helperが明確に目立つ: 該当helper、呼出stack、維持するWASM/並行性契約を示し、一案だけ推奨。
- どちらも小さい／主にMariaDB SQL処理: 「有望なhost/shim局所候補なし」で今回を完了できる。
- 観測の揺れや対応不能で判断できない: 不足証拠と最小取得費用を返し、終了。改善率の目標に達するまで自動継続しない。

次の候補実装、観測なしcandidate A/B、SUM版での再確認、70テスト全suiteとP1/P4/P8、両OS受入れは後続の候補に応じた別段階。今回のPASSで採用・統合・releaseを承認しない。元の全体差10%目標は方向であり今回のclose条件ではない。

## 資源と成果物

experiment-workspaceスキルを使用。最大active作業2時間、Go build1回上限20分（観測器修正時の再build最大1回）、全計測上限20分、profile込み上記固定回数。8GiB予算/最低空き8GiB。準備時の容量監査、build前identity、計測時は軽量容量検査のみ。build/再帰duを性能計測に重ねない。上限・失敗・不足で止める場合は完了範囲と残作業を明記する。

結果は一つの固定refのbundleにまとめる: source/guest/toolchain、hook位置とpatch/hash、plan、全raw/失敗ログ、profile、再計算script、README、SHA256SUMS。既存と同じ再現レシピを使い、使わなかった古いraw結果を新campaignへコピーして混在させない。集計をrawから再生成し、push確認後にcache/temp/worktreeをcleanupして確認する。#182の冒頭と本Issueを更新し、完了した調査を再び未完に戻さない。

## 関連・今回変更しない判断

#185はhost受信4KiBバッファを試作完了・見送り。#167は入力上流再利用の保守性検討で着手未承認。#143は保留。#140/#156の長い待ち、#119/#162のClose、既知Connector/Python/OpenSSL4、MDEV-42129をこの通常INSERT調査で再開しない。新たな明確な関連証拠が出たら既存Issueへ参照を付けて報告する。
