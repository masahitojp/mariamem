# Issue65 P1-c / C1: reusable instance core

状態: **共通coreの抽出候補とfake-runner検査。公開native接続・実guestでの再検証は未実施。**
[P1-c計画](../../../docs/design/issue65-native-protocol/public-backend.md)のC1を進めた。
C2公開Go/control/Python接続、C3 Snapshot/Fork/Live・失敗契約・両OS受入れまでがP1-c全体であり、
この単体PASSをP1-c完了、main採用、製品化完了やreleaseと扱わない。

## 入力と変更

- source base: `68881baf5a417454d03ee0bb74d273df092550eb`。
- core implementation source_commit: `f0008bb41828f7d9f728b3e1ffbb9367b704f1fb`。
- [P1-b成功receipt](../issue65-p1-timeout/evidence/ci42353912021.json):
  CI42353912021、候補 `f6888cca1f1aa800b0d80ccc3fcb1a40b8dc5dfd`、guest/linux/discard-transit全job成功。
  guest d4f30818の再現、291-file比較、全241観測照合をdownloadした証跡で確認した。
- 抽出元: 固定baseの `benchmarks/spikes/issue65-p1-timeout/main.go.txt`。

`internal/nativewire`に、private frame、opaque relay、instance lifecycle、受付とcaptureを抽出した。
instanceごとのRunnerがI/O、restore entries、epoch、capture/approval、早いfailureと実行終了を接続する。
coreからgeneratedgo/mysqlwire/forklimitへの依存は無い。公開factoryもcanonical guest/生成物も未変更。
実験専用cmdは歴史的oracleとして残し、まだ抽出coreへ結び直していない。

| 境界 | 抽出候補の扱い |
| --- | --- |
| TCP/Dial | 同じ16枠owner。Dialは受付時ErrCapacity/取消を返し、handshake完了は待たない。TCP拒否は既存bounded helperをadapterから注入する設計。単体ではcallbackの受付/終了を検査し、ERR1040 packetは未検証 |
| instance寿命 | Failureはfirst causeを即時保持。Doneはexecution、control reader、accept、両session relayのjoin後。transport EOFやworker通知だけでは閉じない |
| 後片付け | Start失敗・Close期限切れはdisposal.Ownerをtyped errorへ付け、errorを捨てても継続所有。親temp削除はそのownerの完了後 |
| control待ち | fatalでpending OPEN/capture RPCを起こす。native deadlineはcontext.DeadlineExceededへunwrap可能。buffered native原因をgeneric終了で先に上書きしない |
| capture | host予約検査とguest最終fenceを維持。Busy cacheは診断用。busy/transaction rejectionは非消費、それ以降の失敗は消費。captured-root ownership error用のCaptureDebt能力を用意 |
| Fork/Live | coreは1 instanceのみ。独自baseline/poolや固定5000ms forkは持ち込まない。公開ownerへの設定/永久debtの伝播はC2/C3に残す |

prepared/snapshot型を使ったcapture成功・拒否の単体確認は行ったが、engineのatomic fence、rollback、
freezeやnative joinをこのfake peerで証明したわけではない。permanent capture debtの実失敗注入と
公開parent leaseの保持も未検証。既存22 lifecycle/88 compat/38 limits/G1/G2の再bindは次工程。
runnerは「全worker・descriptor・mapping終了後に1回completion」を守る必要がある。
completion=nilの契約違反では終了を捏造せず資源を保持するため、回収不能になりうる。
非協調workerを強制停止する保証は追加していない。

## 確認結果

[receipt](evidence/receipt.json)、[race](evidence/core-race-final.txt)、[mutations](evidence/mutations.json)。
macOS arm64 / Go1.27.3で新backend10 testsと既存owner/timeout/disposalをrace有効、10回反復でPASS。
fake peerはprivate envelopeだけを扱い、実MariaDBやMySQL parserではない。

- 不正MySQL相当のbytesもそのまま往復し、typed timeoutのOPEN値を保持。
- TCP相当listenerとDialを混在させ16/17を確認。取消/容量拒否ではOPEN workerを追加しない。
- native worker holdとhost writer holdを別々に使い、Failure先行、Done/枠/物理cleanup保留、遅いjoin後の回収を確認。
- 起動取消→typed owner→親directory削除、OPEN中capture拒否、first cause保持、古世代STATE無視、capture fence拒否/所有権を確認。
- 5負例: 早いDone、startup owner脱落、固定5s、capture拒否無視、first cause上書きをそれぞれ検出。
  Go overlayを使う再現scriptはcheckoutを変更しない。
- focused vet、Python script AST、dependency boundary、diffチェックPASS。
- [公開source検査](evidence/public-source-boundary.json)全体は**FAIL**。
  baseから不変の実験証跡6ファイルにmachine-local pathがあり、今回のruntime変更と無関係。
  検査を弱めず、追加ファイルの境界確認と分けた。製品公開前に既存違反の整理が必要。

新guest build、実guest runtime、新CI、benchmarkは0回。
初回の検査では定数名と既存test helperの衝突を修正した。最初の負例scriptはgofmtの空白で停止し、
その後Go overlay版へ変更して全5負例を実行した。最終sourceを復元した状態でrace/vetを確認済み。

## 再現と次工程

workspaceのtempへGOCACHE/GOMODCACHEを向け、source identityを確認して実行する。

```sh
python3 scripts/git_identity.py inspect HEAD
go test -race -count=10 ./internal/nativewire ./internal/disposal
go vet ./internal/nativewire ./internal/disposal
python3 benchmarks/spikes/issue65-p1-core/mutations.py --evidence "$MARIAMEM_EXPERIMENT_EVIDENCE/core-controls"
```

次はC2。既存private backendを保ったままhost service/factoryとstaged native runnerを結び、
公開Go Start/Dial/TCPとPython managed/controlの実際の入口でlegacy fallbackを検出する。
その後C3でSnapshot/Fork/Live、Options継承、typed cleanup/永久debt、元oraclesを同じcoreへ再bindする。
P1-d残るhost coordination、P1-e canonical生成/常設CI/main候補、P2 consumer/performanceは未実施。
EOF/owner原因という承認済みD1以外の新たな契約差が見つかれば別判断へ戻す。
