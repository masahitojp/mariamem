# #65 P1-a計画の技術確認

**今の判断は、P1-aを「hostの接続枠・session identity・退役所有」に絞って実装するかです。
この計画で進めることを推奨します。** hostの予約とC++のidentity発行を同じownerへ揃え、公開経路に
接続する前に寿命の境界を明確にできるためです。最大の懸念は、OPEN応答喪失や早いRETIREDによる
誤った枠の再利用です。計画はその失敗を明示的な保留・join条件とnegative controlsに落としています。
既存PASSが新経路を証明するとは扱わず、下記条件を実装の完了条件にして進める判断です。
これはmain採用・製品出荷の判断ではありません。

公開backendを先につなぎ、C++ controllerの整理を後回しにする方が早く使える、という反論はあります。
ただし現在はpublic routeと専用cmdが別で、public側もslotを管理しています。二重の責務をそのまま
製品経路へ固定するより、承認済みのhost所有方針に沿って小さい境界を先に揃える案を採ります。
根拠は調査baseの `mariamem.go:128`、`internal/host/server.go:169` と
`benchmarks/spikes/issue65-compat-fixes/main.go.txt:283`,`:395`,`:437`。

## 対象の固定

Humanの「P1を進める」という依頼と履歴から、未指定のreview入力を次のように復元しました。

| 入力 | 固定値 |
| --- | --- |
| 設計artifact | `docs/design/issue65-native-protocol/productization.md` at `9f4977135941acff010987e49ff0cad9221b2734` |
| 計画candidate | `9f4977135941acff010987e49ff0cad9221b2734`（runtime候補ではない） |
| 調査/差分base | `781fa29926be06856728741df96a1a4713e93af3` |
| 直前の実行候補 | `f3fe907ac238e738c94b684426e6230b23a3c163` |
| guest/checked host source | `76abfed4b5f920c79efd5fef33c848c21ac040c9` |
| guest SHA256 | `242f5cfd446ac65dc3d7322ead668cd2ec5473193cf4bb58b69c7c5b3cfe6e87`、UNQUALIFIED |
| branch | `experiment/issue65-p1-design` |
| 実行証跡 | [CI42338117054](https://github.com/masahitojp/mariamem/actions/runs/42338117054)、[保存receipt](../../benchmarks/spikes/issue65-g2-repair/evidence/ci42338117054.json) |
| 今回決めないこと | public default切替、canonical guest生成物の採用、main integration、P2性能判定、release |

artifact SHA256: `f4fd5a53d259e0ee1ef78eb8b41ace6585ef3d88fe7188b0c19e12d9c13ca5ca`。
現worktreeが上記branchであることとsource object typeを確認し、artifactをSHA指定で読みました。
CI metadataは1回取得しhead SHA一致・全3 jobs successを照合。新しいbuild/runtime/CIは実行していません。

## 以前の条件と検出網の照合

prior inputsは[責務表](../design/issue65-native-protocol/contracts.md#state-belongs-with-the-authority-that-can-make-it-true)、
[D1–D3](../decisions/issue65-native-wire-contract.md)、
[scope review](issue65-native-compatibility-scope.md#以前の受入れ条件との照合)、
[現status](../project-status.md)、[G2成功receipt](../../benchmarks/spikes/issue65-g2-repair/evidence/ci42338117054.json)。

| 条件・gap | 判定と根拠 | 検出/必要作業 |
| --- | --- | --- |
| G1/G2の有限な意味論確認 | **今回の範囲で充足**。Linux G1 234/G2 241、283-file比較、guest再現とcleanupをreceiptで確認。Macの1043は保存実測の契約再評価 | 新routeで同じoraclesを再実行。P1-aでSQL/profileを広げない |
| hostがidentityを一意に発行 | **未実装**。Cpp `Manager::open`がslot検索・generation増加（base `guest/experimental.patch:1419`） | 現CIはhost指定を無視するguestを検出できない。profile2一致、指定tuple一致、guest無視mutationを追加 |
| TCP/Pipe共有容量と退役 | **基本は確認済み、移設後は未検証**。`TestCompatCapacity`/`TestCompatLiveCapacity`とnative22 casesが存在 | nativeとrelayの完了を別々に遅らせる16/17境界試験。現在の正常retirement試験だけでは早期解放は検出できない |
| native joinと最後のアクセス | **既存の足場あり、新routeの合成は未検証**。`ThreadLifetime.complete`/foreign free（base `thread_lifetime.go:90`,`:113`）、J1/P6のjoin/free調査、242f bindingの全3本文一致 | native supporting selectionは`runtime_tests.py:8`の単一capture testで、base lifetime testsの実行証明ではない。新guestのbinding/closure照合、leaf tests選択、実route barrierと早期解放mutationが必要 |
| root disposalは全worker/reader join後 | **維持必須**。`runtime_wire.go.txt:111`以降のWaitThreads、main.goのawaitJoined。session lease解放と別条件 | `TestCaptureJoinCancellationRetainsLease`を移設routeへ結び直す。instance稼働中のWaitThreadsをsession joinへ流用しない |
| OPEN不確実性とcapture | **設計に具体化、未実装**。計画はReserved/Opening/Uncertainをhost fence前にbusy/failed扱い。現在のattachはlost OPENでfail（base main.go`:502`） | OPENED喪失、pre-send取消、captureとOPEN競合の専用oracleは現CIに無い。guest fenceだけでなくhost予約段階も検査 |
| identity exhaustion | **新ownerで必要**。現prototypeのAddは0検出のみ（base main.go`:174`,`:313`） | 既存ThreadPool IDの枯渇試験は別namespace。epoch/request/sessionそれぞれ飽和・次々回失敗・並行発行を追加。source上の差であり、通常利用での枯渇被害を再現したという主張ではない |
| D1と公開owner診断 | **private代表状態は確認、publicは未充足** | P1-cでErr/ErrUnusable、first cause/cleanup debtとwire EOFをpublic routeへ接続。native無効化negative controlが選択suiteを落とすこと |
| 30sと既存timeout設定 | **未充足、P1-bに明示**。公開Optionsは30s、prototype OPENは100..10000ms（base `mariamem.go:47`,guest patch`:1419`） | 現native fixturesは10s以内であり既定30sを検出しない。丸め/新上限/first-byteずれを検査 |
| 宣言consumer/accepted exceptions/性能 | **未充足、P2に明示** | 現raw/Go driver PASSを全Go/Python/ORMへ拡張しない。同engine/UCAで比較し、SKIPをPASSにしない |
| generated ownership/canonical/release | **未実施、P1-e以降** | HANDWRITTEN_FILES、source provenance、public native検出CIを結び直す。計画承認をadoption/release承認としない |

## Missing-things scan

- 未充足の条件は上表と計画に列挙済み。今回の範囲で、未記載の新しいproduct adoption条件は見つからなかった。
- 公開usage文書（README/go/python/releasing）の変更は無い。公開routeを切り替えていないため、今回の
  計画による現usageとの新たな矛盾は見つからなかった。nativeの予定動作をshippedと記載していない。
- canonical source.patch、generated-Go、HANDWRITTEN_FILES、release inputs/baselines/notesは変更していない。
  これらの製品化作業は未実施として明記。実験historyの一括mergeを予定していない。
- 未到達境界はpublic route、移設したsession所有、timeout domain、新identity ABIのlost/stale/retirement。
  既存CIに不可視な行は上表と計画の検出表に分離済み。
- 新guest独立生成、新route両OS実行、consumer/performance、Qualification等を完了扱いにしていない。
- current in-code commentを変更していない。削除した動作を説明する新たなstale commentは見つからなかった。
  既存prototypeのC++管理を「移設済み」とは記載していない。
- 今回のruntime/build/benchmark実行は無い。cold/warm性能やC++削減量の数値的主張も無い。

## 次の実装taskと限界

判断対象はP1-aの実装範囲。host unit/fault検査→新private profile2 guest/host→binding review→
既存native suite＋新しい所有権oraclesの順に進める。runtime移設をまだ実装・検証していないため、
本reviewをruntime安全性のPASSとは扱わない。失敗時に必要なのは該当境界の観測/修正であり、
一般の全Wasm安全性証明や別socket/cgo方式の再調査ではない。
