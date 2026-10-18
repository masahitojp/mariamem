# macOS OS確認結果の再利用：設計とHuman Review

## 今回の判断

**推薦：対応macOSの確認成功だけをGoプロセス内で再利用する最小実装へ進む。**
毎回の外部コマンド実行を省き、DB内部や隔離・終了処理に触れずに後続起動の待ち時間を減らす。
今回Humanに求める判断は、この設計と下記の有限な実装・検証範囲の承認。
実装・性能確認・main統合・リリースの完了を意味しない。

**最も強い反論：一度確認した後の環境変化を再検出しなくなり、同時初回起動では他の呼び出しが確認完了を待つ。**
受け入れる前提は「対応OS判定は実行中Goプロセスの環境属性」。通常のOS更新後の新プロセスでは必ず再確認する。
実行中にsw_versやその返答を差し替えたことの検出は、この成功キャッシュでは約束しない。
DBファイル・wheel・バイナリの内容検証をキャッシュする提案ではない。
確認は呼び出し元のcontextに従い、待機者は独立してキャンセルできる設計とする。
この前提を認めない場合は方式を再検討する。速度のために未確認環境を受理しない。

## 基点と確認済みの根拠

source_commit: `a43960b110a739a3c87b4a25757bb0f106464041`（main、設計開始時clean）。
既存の費用帰属と0.5.x/0.7.xの区切りは
[承認済み状態](../project-status.md)と
[固定された費用帰属資料](https://github.com/masahitojp/mariamem/blob/bbf5d1c27f3cea3e2135e8fae053f875ceb234b5/docs/reviews/child-lifecycle-attribution.md)を参照。
最新mainのHuman決定どおりmacOS側を先行する。Ubuntu並列調査の状態や範囲を変更しない。

- `mariamem.go:100` と `internal/host/server.go:50` が `artifacts.ValidatePlatform` を呼ぶ。
  Go Start/Forkでは双方を通る。外側確認は一時ディレクトリ作成前、内側はguest起動前。
- `internal/control/shared.go:133` のPython共有hostと `cmd/mariamem-host/main.go:87` の起動も
  同じhost入口を通る。Pythonの別root lineageは別hostプロセスなので成功結果を共有しない。
- `internal/artifacts/artifacts.go:27–49` はmacOS arm64で毎回
  `/usr/bin/sw_vers -productVersion` を `exec.CommandContext` で実行し、majorを解析。
  major 15未満は `unsupported_platform` / `platform` で拒否する。
- 同ファイルのLinux経路は `/etc/os-release` を読み、Ubuntu24.04 x86_64を検査する。
- 計測済みmacOS Go LightはFork全体54.16ms（control）、確認区間17.49ms（観測あり・2回）。
  Python共有hostの確認区間は約9ms。別cohortなので引き算で製品速度を予言しない。
  Ubuntu確認区間は約0.04msで、本件の性能対象ではない。

## 方式比較

| 方式 | 利点 | 問題・判断 |
| --- | --- | --- |
| 外側のGo確認だけ削除 | 小差分 | Goの2回が1回になるだけで各Forkの反復とPython費用が残る。早期拒否の位置も変わるため不採用 |
| sync.Once / OnceValuesで全結果を保持 | 実装が短い | 最初のキャンセル・一時エラーが後続全呼び出しへ固定されるため不採用 |
| 成功のみ保存、同時確認を無制限に許す | キャンセルが単純 | 並列初回に同じ外部commandを複数実行する。比較可能な代案だが今回の推薦ではない |
| **成功のみ保存、同時確認は1件** | 各入口を保ち、反復と同時重複を減らす | 待機とキャンセルの状態遷移をunit testで検証する。推薦 |

## キャッシュの契約と状態遷移

キャッシュは `internal/artifacts` に閉じたprivateなcheckerとし、productionでは1個を利用する。
状態はmutexで保護した「対応確認済み」フラグと「確認中」の完了channel。
外部コマンドの実行中はmutexを保持しない。公開API、設定、TTL、依存ライブラリは追加しない。
GoとPython hostの呼び出し箇所を削らず、darwin-arm64の内部経路だけを変更する。

1. 入口でcontextを確認する。キャンセル済みならキャッシュ済みでも成功を返さない。
2. 確認成功済みならcontextを再確認して成功を返す。
3. 他の呼び出しが確認中なら、その完了channelと自分のcontextをselectで待つ。
   完了通知後は自分のcontextと状態を再確認する。
4. 確認中でなければ当該呼び出しが担当になり、自分のcontextで既存の絶対path commandを実行する。
   出力解析、macOS15+の判定まで成功し、contextも有効な場合だけ成功を保存する。
5. 成否にかかわらず確認中状態を解除して全待機者に通知する。
   command失敗・解析失敗・未対応OS・キャンセルは保存しない。
   担当者は自分のエラーを返し、待機者は再評価して必要なら新しい確認を担当する。

先行呼び出しのキャンセルを、別の呼び出しの失敗として配布しない。
待機者のキャンセルは実行中の担当者を止めない。成功後も戻る直前に自分のcontextを確認する。
戻り直前の確認後にcontextがcancelされる通常の競合までは排除する契約にしない。
context由来エラーは既存の `unsupported_platform` / `platform` のwrapperと原因チェーンを維持する。

初回確認が繰り返し失敗する環境では、待機者が順に再確認し得る。
無制限のバックグラウンドretry、独自timeout、contextを切り離した確認goroutineは作らない。
待機は各callerのdeadline/cancelに従う。呼び出し元にdeadlineがない場合の確認時間上限は新設しない。

## 保証と変更の境界

- 対応OS/archとmacOS minimum、Linuxの検査方法は維持する。
- 変更される観測は、成功後にcommandの削除・出力変更・実行不能が起きても後続起動で再検出しないこと。
  再試行は成功前の失敗についてのみ。再起動したGoプロセスでは成功状態を引き継がない。
- Python側の `_artifacts` のplatform/wheel/hash検証は対象外。同じGo hostを使う後続DBで利益が見込める。
  毎回新しいroot hostを作る利用では、Go hostの初回確認費用は残る。
- guest、Generated Go、converter、HANDWRITTEN_FILES、生成入力inventoryを変更する必要はない。
  実装対象は `internal/artifacts` の通常Goソースとtests。実装時にdiff/inventoryでこの所有境界を確認する。
- 成功キャッシュは数個の同期用フィールドのみ。DBやSnapshot、context、失敗内容を永続保持しない。

## 実装後の有限な検証計画

今回は設計のみ。以下は未実施であり、PASSではない。

### 決定的なunit test

private checkerごとにprobe関数を注入し、test間でproductionグローバルをresetしない。

- 対応majorの成功は何度呼んでもprobe1回。実commandの解析を別の表形式testで検査。
- major14、空/不正出力、command失敗は拒否し、次回の成功で回復する。
- 成功前後のキャンセル、担当者の途中キャンセル、待機者の独立キャンセル。
- 有効な別contextが、先行担当者のキャンセル後に再試行して成功できる。
- 同時呼び出しでも確認中probeは最大1、成功後の全callerが完了。
- channelの取り残し・deadlockなし。sleepで順序を推測せずbarrier/channelを使う。
- `go test -race ./internal/artifacts` と既存Ubuntu parser test。
  `TestUbuntuPlatform` はLinux拒否の既存oracleだが、macOS成功キャッシュ・並列性は検出しない。
  Python diagnosticsの未対応OS拒否testはPython側のoracleであり、Goの新状態機械の代用にはならない。

### 実guest回帰と性能

変更境界は全Start/Fork前の対応環境確認であり、失敗とキャンセルが起動へ伝播するため、
既存Goの起動失敗oracle、直列/並列のStart/Fork、SQL/transaction・独立子・CloseとPython共有host smokeを選ぶ。
広いguest意味論調査、ORM全探索、独立再生成は本変更の開発検証に含めない。
通常のsource/license/public boundary checkは変更の所有境界に従って実施する。

性能はmacOS arm64で、source_commitを `scripts/git_identity.py` で確定したcleanなcontrol/candidateを交互実行する。
既存失敗oracleを使うLight・4子のGo/Pythonを各5対直列、各3対4並列（計32プロセス実行）。
準備・初回・後続Fork・4子全体・Closeを分ける。実行順は交互反転し全試行を保存する。
同時初回のprobe重複抑止はunit testで検査し、通常性能に観測hookを混ぜない。
既存attribution harnessの診断runtimeは取り込まない。新しいprofile・tail頻度推定は不要。

期待するのはGo初回の二重確認削減、同一プロセスの後続Go ForkとPython共有hostの後続Forkの改善。
17.5ms/9msを確約値にしない。全体時間、初回待機、外れ値も提示する。
Ubuntuは既存platform/起動のfocused回帰をnative CIで確認し、性能改善は要求しない。
実行できないplatformはSKIPで記録し、採用のための必要条件を満たした扱いにしない。

### 終了条件と反証

- 全失敗・キャンセル・並列unit oracleが成功し、通常API/SQL/隔離/終了の回帰がない。
- 同一processで成功後の再probeがなく、macOSの後続Forkに計測上の改善がある。
- 全体で明確な悪化がある、改善が不明瞭、または契約を保つ実装が過大になる場合は採用を推薦せず、結果を返す。
- この範囲の実装・検証結果をHuman Reviewへ返して止める。main統合・リリースは別判断。

## 今回のレビュー結果と未完了

設計の根拠は上記source anchorsと既存両OS証拠。追加guest実行やCI再実行は行っていない。
実装・新oracle・実guest回帰・性能差・native Ubuntu確認は全て未完了。
現行公開ガイドに変更済み挙動との矛盾はない（runtimeは未変更）。実装時はarchitectureに
process内成功キャッシュと再確認しない境界を記載する。公開APIや製品の隔離契約の変更は不要。

今回承認するなら、この有限な実装・検証へ進む。Ubuntu並列起動調査と0.7.xのguest改善選定は別範囲のまま。

## 実装前レビューへの対応（2026-10-18）

- 最新main a43960bへrebaseし、macOS先行の順序を維持。source_commitも更新。
- 失敗する同時N呼び出しは最大N probe（callerごと最大1回）、同時実行最大1とし、N=32で固定。
- 注入testはcheckerを個別所有。production globalは専用subprocessでのみ検査しresetしない。
- native macOS CIでartifacts packageをrace付き実行し、production Darwin分岐も専用testで確認。
- probe担当者のpanicでもdeferで完了通知と確認中状態解除を保証し、panic自体は伝播する。
