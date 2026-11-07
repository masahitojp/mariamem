# Issue65 P1-c — public native backend plan

状態: 設計・source照合。runtime未変更。HumanのP1-c継続依頼を具体化する。
本taskで1回取得したP1-b CI42353912021 metadataはin_progress / conclusion=null、
head source_commit f6888cca1f1aa800b0d80ccc3fcb1a40b8dc5dfdだった。以後はpollしない。
P1-bのguest再現・291-file比較・241観測照合の成功は、まだ確認できていない。
その成功確認を、native public artifactのbuild/実行開始の前提に残す。

## 固定入力と完了範囲

- 設計/source base: f6888cca1f1aa800b0d80ccc3fcb1a40b8dc5dfd。
- P1-a成功候補:738bbbe58674f097161a1db2c1eda91536e416fe / CI42346396518。
- P1-b guest/checked host origin:be244a0bdb510a22417241c2aa2f76a9093aac1b。
- UNQUALIFIED guest SHA256:d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481。
- [P1計画](productization.md)、[責務表](contracts.md)、
  [D1–D3](../../decisions/issue65-native-wire-contract.md)とP1-a/P1-bの元oraclesを維持。

P1-c全体の出口は、同一のnative backendで公開Go Start/TCP/DialContext/Snapshot/Fork/Live、
Pythonのmanaged host/control/Snapshot/Fork/Liveを動かし、owner error/cleanupと設定継承を
検査すること。内部抽出だけ、Goだけ、専用cmdのPASSだけではP1-c完了としない。
consumer全profile/性能はP2、canonical生成物・常設CI・main候補整理はP1-e、
残るqueue/transport/watchdog policyの移設はP1-d。main採用・releaseは別のHuman判断。

## Sourceから確認した接続点

以下のfile:lineは固定baseの位置。

| 現状 | 接続方針 |
| --- | --- |
| `mariamem.go:65` のprivate backendは既にDial/Close/Snapshot/Active/Capacity/Failureを持つが、startupは`:128`の具体的host.StartGeneratedと`:135`のs.Guest.Doneへ依存 | 既存の狭いprivate interfaceを保ち、factoryの内部service契約にPort/Done等を揃える。fakeへ不要な全methodを強制しない |
| `connection.go:33` のDialContextはendpoint/contextを検査してbackendへ委譲。`internal/host/server.go:154`はcapacity errorをworker開始前に返す | native backendも同じ確定受付境界を使う。prototype pipeのwire ERR返却を公開Dialへ持ち込まない |
| `internal/control/shared.go:48`は*host.Server。`:150`付近はbaselineからquery/startup/shutdownを継承 | 共通serviceへ変更し、既存Go/PythonのOptions/lease/late-response所有を維持 |
| `internal/host/disposal.go:23`のdisposerと`internal/disposal/disposal.go:102`のRetain/Continueがlate join・削除を所有 | native backendも同じtyped ownerへ合流。plain join errorだけでStart/Closeから返さない |
| `snapshot.go:127`のForkはs.optsを渡し、`:69`以降のcaptureDebtは永久debtを保護 | prototypeの固定5000ms forkや独自poolを移植しない。既存Snapshot/forklimitが唯一の親lease所有者 |
| `internal/live/endpoint.go:17`のChildは既にbyte relay用の抽象。physical drain→child disposal→replacement commitを持つ | endpointの世代・予約・retry・tombstoneを作り直さずnative childへつなぐ |
| `cmd/mariamem-host/main.go:120`付近はGuest.PID/Doneへ直接依存 | shared controlに加えてstandalone host metadata/終了待ちもserviceへ移す。PIDは`internal/guest/guest.go:121`のos.Getpid()という既存意味を維持 |

## 共通backendと依存方向

`internal/nativewire`へhost controllerを抽出する。既存owner/timeoutと同じinstance lifecycle lockで
予約/受付停止/capture開始を直列化し、I/O・joinはlockの外で行う。
このcoreはgeneratedgoを直接importせず、instanceごとのruntime runnerを受け取る。
runnerは現在のStartWireInstance相当のI/O、prepared entries、epoch、capture/approval、
failure callbackとexecution終了を接続する。グローバルな差替え変数は使わない。

依存方向:
`Go API / Python control → host service/factory → nativewire core → prepared/snapshot/disposal`。
`host native runner adapter → generatedgo → base/prepared`。
nativewireからgeneratedgoへ逆向きの依存を作らず、canonical checkoutでもcoreのunit/fault検査を可能にする。

内部serviceで必要な能力はStartの戻り値を通じて揃える:
Port、DialContext、Close(ctx)、SnapshotHeap、Active、Capacity、Failure、Busy、Done、
SnapshotCapable、DisposalComplete、必要な既存CLIのsnapshot/metadata能力。
名前や配置の機械的調整は実装時に行うが、下記の状態の意味を潰さない。

- Failure():最初のfatal原因を即座に返す。後続のEOF/cleanup errorで上書きしない。
- Done():native execution、共有reader、受付/session relaysのjoinが確定した時点。
  fatal通知やSQL transport EOFだけではcloseしない。private execution-doneとは別。
- DisposalComplete():joinと依存資源のcleanup完了。単なるoperation成功/失敗やsource消費とは別。
- CaptureDebt():backend内で発生した永久capture debtを既存公開ownerへ伝えるprivate能力。
  public APIを増やさず、Snapshot/Control側の既存captureDebtへ取り込む。physical cleanup成功でも消さない。

## 公開経路・実験artifact・生成物所有

P1-cでは新しい公開backend選択Optionsやruntime名を追加しない。
reusable coreとservice境界は通常のGo sourceとして整理し、native runner/factoryとRuntimeWire adapterは
既存のchecked staging機構で明示的に投入する。staged module/wheel/host artifactの公開入口はnativeを
既定として使う。callerは通常の公開Go/Python APIを呼び、SQLは一つのnative coreへ届く。

canonical factory/guest/generated-Goの製品切替はP1-eに残す。staging投入したfactory/adapter/worker binding、
Go/assembly/dataの全inventory、compiler/guest hashを記録し、canonical sourceを偽装しない。
新しいbuild-tagや恒久的なユーザー設定の二系統は導入しない。
P1-cで公開経路が動くという主張は、この固定UNQUALIFIED artifactに限定する。

## 受付・停止・owner診断

1. TCPとDialはP1-aの一つの16-slot ownerへ予約する。retiring workerや未join relayも数える。
   TCP17接続目は既存のbounded pre-login ERR1040、公開DialはErrCapacityを返しworkerを作らない。
   Dialはhandshake完了待ちではない。返したconnはcaller所有で、ctxを接続後のDB lifetimeへ流用しない。
2. Activeはhost session lease数で、Reserved/Opening/Uncertain/Retiringを含む。
   WaitDisconnectedはtransport数だけを見ず、native退役＋両relay完了まで待つ。
3. native failureはbackend自身が新規受付を止め全clientを閉じる。wireはD1のEOF/connection loss。
   Failureは即時、Doneは全join後なので、DB.watchのauto-closeがheld worker待ちでDB.muを占有しない。
   pending native RPC/capture waitsも即座に起こす。停止要求は一度発行し、非協調workerを強制回収しない。
4. GoのErr/ErrUnusable/HostErrorとPythonのmanagement error/closed/logsを同じfirst causeへつなぐ。
   native deadlineの既知causeはowner側でcontext.DeadlineExceededへunwrap可能にする。
   元のGo worker errorは既存wireGuestFailureの%wを保つ。通常SQL ERRはowner故障にしない。
5. Start失敗・Close timeout・listener failureの時点で一つのdisposal.Ownerを保持し、
   execution/read/relay joins→backing/descriptor cleanup→親temp/log削除を順に完了する。
   公開Closeのstored resultは変えず、Liveのprivate retryは同じownerを使う。
   cleanup継続をtyped errorへ付け、呼出側がerrorを捨ててもrunning memoryを失わない。

## Snapshot/Fork/Liveと状態の権限

SnapshotはP1-aのReserved/Opening/Uncertain検査→guestの最終SQL/capture fence→consuming stop→
全join→freeze/OwnRootの順を維持する。busy/transaction rejectionはsource非消費、受理後の失敗は消費を伝える。
nativeの拒否を既存Rejected/ErrBusy/ErrTransactionActive/closed mappingへ結ぶ。
post-consume失敗とcaptureDebtを同じ単純なClose errorへ畳まない。

公開Snapshotとcontrol baselineに保持されたquery/startup/shutdown、MaxForks、reservationを継承し、
Go/PythonともFork/Live Resetでtyped duration constructorを使う。prototype makeBaseline/fork/live helpersは
reusable coreから外す。coreは一つのinstanceだけを所有する。

Busy()は現在のnative STATE通知から得る診断用cacheで、unknownはbusyとする。
通知の遅延があるため、Busy/Active cacheをSQL/capture許可の証拠にしない。MySQL packetは解析しない。
古いtupleのSTATEで新sessionを書き換えない。最終判定は必ずguest fenceへ問い合わせる。

## 実装順と検出条件

C1抽出→C2公開Go/control/Python wiring→C3 Snapshot/Fork/Live・失敗契約・両OS受入れ。
この順序は作業分割であり、P1-cの完了範囲を縮めない。

| 壊れ方 | 既存の足場 | P1-cで必要な結び直し/negative control |
| --- | --- | --- |
| 公開入口がlegacyへ戻る | 現P1-b専用cmd suiteでは不可視 | actual public Start/Fork/Live、Python managed/controlを実行。native factory無効化でsuiteがFAIL。staged legacy Serve tripwireが発火しないこと。source/guest IDだけで到達証明にしない |
| Pipeでwire ERRを返す/別の16枠 | host TestRejectedPipeDialsDoNotStartWorkers、公開TestDialContextPreconditions、tests/godefault/pipe_test.go | mixed TCP/Dial16/17、cancel-before-admission、Close/captureとの競合。APIはErrCapacity、TCPは1040、worker/lease増加ゼロを確認 |
| EOFでowner causeが失われる | TestInvalidatedState、TestStartupErrorBoundaryAndLifecycleCause、native timeout cases | public query expiry/worker faultで既存client EOF、ErrUnusable＋original cause、独立DB PING。ordinary SQL error後はErr=nilかつfollowing query成功 |
| 早いDone/auto-closeがErrを塞ぐ | prototype worker barrier、TestWireCaptureWaitsForFailedWorkerPeer | actual public routeでworker/relayを別々にhold。Failure/Err/Statusを先に観測でき、Done/DisposalCompleteとcapacityは未完了。早いDone mutationを検出 |
| join前にtemp/log/親leaseを解放 | internal/disposalの5 unit、TestConsumedFailureKeepsTransferUntilGuestAndWorkersJoin、fork/control debt tests | native Start失敗/Close deadline、遅いworkerとlog removal failureを合成。typed ownerを外すmutationで両owner APIの検査がFAIL。late cleanup後も元operation errorとpublic Close結果を保持 |
| cache idleでcaptureを許す | native22 lifecycle、TestSnapshotPhysicalOwnership | STATEを遅延/古世代へ差し替えてactual public Snapshotを要求。native final fence省略mutationでbusy/transaction/OPEN-race oracleがFAIL |
| permanent capture debtをordinary cleanupで許す | TestConsumedChildCaptureSettlesOnlyItsParentLease、native TestCaptureDebtCannotBeForgiven、control recovery tests | public Go/PythonへCaptureDebtを通し、physical cleanup後も正しい親leaseのみ永久保持。無関連debt/closed親の回復を認めない |
| Fork/Liveが5000ms/defaultへ戻る | Snapshot.Forkはs.opts、control makeDBはbaseline durationsを継承 | nondefault fractional durationでStart→Snapshot→Fork→Live Resetの各childをactual guest INSPECT/timeout behaviorで確認。固定5000ms mutationを検出。JSON float64に頼らない |
| Live generationを早くcommit/取消後に漏らす | internal/live endpoint tests、control late reply/EOF、native Live8 | 新Child adapterとinstalled Python/Go entryでphysical drain、cancel-before/after commit、cleanup-only tombstone、parent Close、ordinary/permanent debtを再bind |
| wire/SQLの回帰 | original G1 234/G2 241、88 compat/38 limits、P1-a9/P1-b8 | 抽出後の同じcoreと公開TCP/Dialへfixtureを向け直す。元expected/actual/passを保存。D1と既承認1043以外のoracle変更は別判断 |

focused unitsはcanonical sourceのfake runner/serviceで先に実行する。runtimeは固定d4f30818の再現/checked
translation/worker bindingから始め、public Go＋Python artifactと元native oraclesを一つのcohortで検証する。
旧legacy固有のpacket assertionsは明示的なlegacy artifactで保全し、一括SKIP/削除や全てEOFへの書換えをしない。
publicで意図的に変わるD1は承認書へ対応付ける。常設consumer全profileや性能をP1-c PASSと読み替えない。

## 今回の出口・次の費用

今回の出口はsourceに結び付いた実装計画と検出網。build/runtime/benchmark/新CIは0回。
P1-bの実行結果は本taskの最初のmetadata確認以降は未確認。実装前提は成功receiptの確認。
最初の実装sessionはC1のsource抽出とfake runner/disposal fault検査を先行し、2h active/30min tooling、重いCI0を目安に
不確実性を減らす。全P1-cの工数は未計測。C2/C3で安定した差分を作ってから固定guest再build・Mac実行・
Linux1 cohortを計画する。範囲/予算の追加判断が必要なら、未確認条件と具体的費用を示す。
