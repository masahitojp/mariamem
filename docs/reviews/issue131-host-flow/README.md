# #65/#131: host出力credit移設と更新負担の判断

2026-11-10。**今の判断は、出力queue/creditのhost移設を製品候補へ載せるか。推奨は見送り。上流NET/Protocol/preparedの再利用と自前glueの分離を土台にし、controller移設を拡大しない。** 実コントローラとの限定試験では成立したが、MariaDBへのpatch・内部型依存は一つも消えず、grant通知と両側の状態が増えた。更新費用を下げる理由としては弱い。

最大の反対材料は、hostでbyte数を管理すれば細切れ出力を扱いやすく、将来の総pending制御にも役立つこと。ただし今回の固定windowで、上流追従負担の削減や性能改善は観測していない。必要なら独立した輸送改善として扱う。hostが接続・資源・寿命の方針を持つ既定方針を撤回する判断ではない。

**本来の目的への回答：版別入力と共通準備の整理は更新作業を減らしている。一方、native化が旧方式より総更新費用を下げた、とはまだ言えない。今回の同一上流差分ではpatch本文の修正は両方式とも0で、native固有の優位は出なかった。** これは追加実験を無期限に続ける理由ではなく、「host移設を広げれば改善する」という案に区切りを付ける材料である。製品受入れの完了と総費用改善の認定は別で、前者のPASSだけで後者を認定しない。

## 固定した対象と範囲

- 比較元source_commit: `54860bfe69c2e7cc0479ac451d8b1905b9edefb8`。自前glue5ファイルの分離後。
- 最終候補source_commit: **`fdc12e2314853d3ab03d0d7e96efef66d4e43b0c`**。
- runtime検証対象: `8ef2f667f333a4df6951aa9cb0193840616cb070`。最終候補との差は合成receipt fixtureの4行だけ。
- branch: `experiment/issue131-host-flow`。main採用・release・#138再開はしていない。
- MariaDB比較: 13.0.2 source_commit `620a4b5624222048fece7fe1789978ae0675cae2` → 13.2 Preview source_commit `c9f28ba0afec6d29e4688255dce8caaf7e91233d`。13.3 LTSの結果ではない。
- 出力のみ。input/timerの移設、全controller再設計、cgo/direct importは対象外。6GiB/空き12GiB、guest build0、CI提出0。

対象と条件は直前のHuman指示、#65/#131本文、project-statusの固定出口から復元した。Git commit型を `scripts/git_identity.py` で確認した。[機械結果](result.json)に環境・失敗・検証範囲を保存。

## 試作で確認したこと

hostに64KiBのbyte ringと累積grantを持たせ、guestの出力dequeは最大4KiBにした。guestはhostから許可された範囲だけ生成し、peer書込みの完了後にhostがACKと次のgrantを送る。private lifecycle profileは3→4。元のdelivery ACK、guest側のcommand完了・capture gate・deadline・kill/joinは残る。

実際の `guest/native/wasm/issue65_control.cc` とGo `internal/nativewire` を接続した。MariaDB sessionだけを短いcallback刺激へ置換し、次を確認した。

| 検証 | 結果と限界 |
| --- | --- |
| readerが止まった262144-byte出力 | outstandingは65536で停止、guest queue peakは4096以下。制御STATSは応答し、busy captureは拒否 |
| 同一接続の次command | 出力ACK前に次commandを受付けず、読取り再開後に2応答を順番に取得、最後にidle fence成功 |
| 70000回の1-byte callback write | 同一byte列を取得。Go側はframe数ではなくbyte数を制限 |
| stale generation / grant巻戻し | staleは無視され、生きたsessionは変化しない。正しいidentityでgrantを戻すと原因を保持して失敗 |
| 停止・切断・deadline | blocked outputからjoin、peer断は原因を保持、別instanceは応答継続、既存local deadlineは発火 |

[全29 Go tests](final-race.txt)はrace付きPASS（このうち実C++ component6件）。[入力境界66 tests/59 subtests](boundary-tests.txt)もPASS。Go raceはC++のdata race検査ではない。callback刺激はSQL・THD・本物のrollbackを実行せず、idle fenceはSnapshot artifact/restoreの証拠ではない。macOS arm64のnative processでありWASIX/wasm2go/Linuxの検証ではない。

移設前後で [native upstream patch、Vio/session glue、policy、deadline](boundary-comparison.json) のbytesは一致。engine内部12ファイルへの接点、prepared回復、Protocol分岐はそのまま。C++のproduced/sent/ackedにgrantedが加わり、hostにもreceived/written/grantedが必要になった。状態を移すだけでguest同期をなくせる構成ではなかった。

## 移設とは独立して見つかった停止時の問題

host Closeがpeerを閉じてwriterを起こすと、STOPがguestへ届く前にwriterがpeer-output-errorを送ってしまう。結果、正常な停止要求に通信障害の原因が付く。[最初の候補FAIL](initial-race.txt)と[変更前baselineの再現](baseline-race.txt)を保存した。baselineの停止10回中8回で再現し、移設による新しい故障ではない。

停止開始後のlocal closeをpeer faultとして送らない小修正を独立commit `8ef2f667f333a4df6951aa9cb0193840616cb070` に分けた。元配置へ適用できる [stop-only.patch](stop-only.patch) も保存。元配置と候補で各10回PASS（[元配置](baseline-stop-fixed.txt)、[候補](candidate-stop-fixed.txt)）。停止前の実peer断の原因保持もcomponent testで確認した。生成guestの公開Closeに対する確認は未実施なので、本番修正完了とは扱わない。

## 同じ上流差分での更新作業

[maintenance_probe.py](../../../benchmarks/spikes/issue131-host-flow/maintenance_probe.py) はhash固定の13.2 archiveとrecipeを取得し、13.0登録済みの旧/native patchをそれぞれfuzz=0で適用した。旧13.0期待hashは書き換えず、変化を記録した。旧方式の13.2 profileを製品登録したわけではなく、build/意味上の同等性までは比較していない。

| 観測 | 旧方式 | native |
| --- | ---: | ---: |
| 適用したstage | 6 | 7 |
| 適用のための本文修正 | 0 | 0 |
| 前版から完全preimageが変わった接点ファイル | 8 | 14 |

[全patch hash・適用log・前後image](maintenance.json)。nativeだけの追加6ファイルは `include/violite.h`, `sql/item.h`, `sql/sql_acl.cc`, `sql/sql_class.cc`, `sql/sql_class.h`, `sql/sql_parse.cc`。これは意味レビューの対象数であり、6件の不具合や工数倍率を意味しない。13.0 nativeの歴史的full overlayを比較に使い、現在の分離後の同じupstream sectionsはboundary-comparisonで照合した。

| 費用 | 判断 |
| --- | --- |
| 版追加の準備script変更・local入力復元 | 共通resolverと保持された版別入力で削減。これは旧方式にも利用できる改善。前段の完全source一致を維持 |
| legacy parameter/result adapterとhost wire互換性の保守 | nativeは上流の実装を再利用し、legacy adapter修正面を外せる。構造上の利点はあるが、今回の更新で省けた修正件数は観測していない |
| 上流の意味・内部layoutレビュー | 残る。今回nativeの追加接点に本文修正は不要だったが、Item_param回復等のレビューは省けない |
| generated worker/TLS/ABI・binding | 既存13.2比較ではyield同一、free/entryは静的配置差。固定入力と拒否検査で確認できるが、毎版の新しい本文・配置の審査は必要 |
| 生成・公開受入れ | 必要な費用。既存producer/public CIは成功しているが、両OSの全設定・実fault/join・元oracle・wheelは未完 |
| 今回のhost credit移設 | 上流依存の削減0。新しい通知/profileと状態の検証が追加される。更新費用削減策として見送り推奨 |

既存の比較済み生成・public結果は [共通準備レビュー](../../design/issue134-preparation-results.md)、[binding比較](../../design/issue134-binding/comparison.json)、[public CI receipt](../../design/issue134-binding/ci42666454893.json) を参照。CI42657118990/42666454893のstatus/conclusion/headShaを各1回照合した（ともにsuccess）。今回のprofile4への結果転用はしない。過去の機械待ち条件は対称でなく、人時も正規化されていないので、速度比・工数削減率は提示しない。

## 既存条件・検出網・次の扱い

| 条件 | 状態／検出網 |
| --- | --- |
| source/receipt混在の拒否 | 維持。resolver/native-glue/selected-guest tests。今回合成receiptの古いpostimageを実際に拒否した。fixtureのみ実staging hashへ直し、歴史的receiptやverifierは緩めていない |
| exact generated bindingと実13.2公開経路 | 過去候補では初期PASS。今回のprofile4は未生成・未bindingなので古いproducerを使えない。既存selected installerが入力の混在を拒否 |
| blocked outputのlocal Close競合 | 今回のcomponentで検出。既存fake runtimeはguestのpoison判定を持たず、通常CIはこのC++ harnessを起動しないため従来網では見えにくい。元配置へ修正を持ち帰り、#130の公開停止検査で確認する対象 |
| #132両OSの全公開受入れ | 未完。設定、実fault/join、22/88/38/G1/G2/P1、installed wheelの既存条件を保持。今回の限定PASSで代替しない |
| #135 consumer/性能・#133最終監査・#138 | 未完。#138は停止/未免除。新規調査の自動追加も条件の免除もしない |
| 更新費用の優劣 | CIでは判定不能。今回source適用は同等、host移設に上流依存削減なし。総費用改善の認定はしない |

今回、公開README/Go/Python/releasing、stable入力、canonical generated ledgerへ新たな変更はない。公開source検査もPASS。candidateは未採用の実験なので、それらをprofile4の利用案内へ書き換えない。Linux、cold guest生成、full SQL/rollback/capture、性能は検証していない。

**これで今回の配置試行は終了する。** 推奨を採る場合、出力credit移設のbranchは証跡として残し、移設前のglue分離候補を基準に、独立した停止修正を既存の#130/#132受入れへ渡す。入力queue/timer/全controller移設を次の必須実験にしない。既定の製品受入れを続ける場合も、費用を記録して判断し、受入れPASSを「総費用改善」と読み替えない。main統合とreleaseは別判断。

## 再現と後始末

候補commitのclean checkoutと新しい使い捨て領域を用意する。C++17 compiler、Go1.27.3、Python3.14/pytest9.2.0を使用（製品のcanonical Go受入れではない）。`scripts/git_identity.py inspect HEAD` を先に実行する。

```sh
clang++ -std=c++17 -O0 -g -pthread \
  -I benchmarks/spikes/issue131-host-flow/stubs -I guest/native/libmysqld \
  guest/native/wasm/issue65_control.cc \
  benchmarks/spikes/issue131-host-flow/engine_stub.cc -o "$TRIAL_TEMP/controller"
MARIAMEM_FLOW_COMPONENT="$TRIAL_TEMP/controller" GOTOOLCHAIN=local \
  GOCACHE="$TRIAL_TEMP/go-cache" GOMODCACHE="$TRIAL_TEMP/go-mod" \
  GOTMPDIR="$TRIAL_TEMP/go-tmp" \
  go test -race -count=1 -timeout=90s -v ./internal/nativewire
python3 benchmarks/spikes/issue131-host-flow/maintenance_probe.py \
  --scratch "$TRIAL_TEMP/maintenance" --output "$TRIAL_EVIDENCE/maintenance.json"
python3 -m pytest -q tests/test_guest_native_glue.py \
  tests/test_guest_input_resolver.py tests/test_selected_guest.py
```

`TRIAL_TEMP/go-tmp` は事前に作成し、各commandはworkspaceのdisk/time guard配下で実行する。このmacOS環境ではclangの標準C++ include探索が失敗したため、`xcrun --show-sdk-path` の `usr/include/c++/v1` を `-isystem` に明示した。
元配置の再現はbaselineのcontrollerを同じstubとcompileし、Goのbackend.go/backend_test.go/relay.go/frame.goをbaseline bytesへ `go test -overlay` で置換する。新grant testのcompile用に定数14の宣言だけを加え、実行対象は `TestFlowComponentStopBlockedOutput` に限定。修正比較は `stop-only.patch` だけをrelayへ適用し、`-count=10` を使う。

機械結果・patch・検証logはこのdirectoryへ保存し、branchをpushする。試作binary、Go cache、venv、取得archive、コピーsource、使い捨てworktreeは削除対象。過去のlocalフォルダを再現条件にしない。
