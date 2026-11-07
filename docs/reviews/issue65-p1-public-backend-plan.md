# #65 P1-c公開backend計画の技術確認

**次の作業は、既存の公開ownerとnative backendを接続するP1-cです。この計画に沿って進めることを推奨します。**
既存のSnapshot/forklimit/Live/disposalを再利用すれば、世代・予約・後片付けの二重実装を避けられます。
最大の懸念は、専用cmdでは問題にならなかった終了通知やplain errorが、公開APIでは原因観測の遅延や
早い親lease解放につながることです。計画はこの差を具体的なservice契約とnegative controlsにしています。
P1-b成功の確認は実行開始の前提として残します。継続依頼への具体化であり、追加の承認ゲートや
main採用・releaseの判断ではありません。

## 対象の固定

Humanの継続依頼と直前のP1段階表から、未指定のartifact・範囲を復元しました。

| 入力 | 固定値 |
| --- | --- |
| artifact/candidate | `docs/design/issue65-native-protocol/public-backend.md` at `3ad978a2d43316cb5aa8212add91d6454d21e8f0` |
| artifact SHA256 | `95c17bf22165159386375351ff151d99a20c8cd787df7cdb41e06d775cdf9a91` |
| 調査base / P1-b候補 | `f6888cca1f1aa800b0d80ccc3fcb1a40b8dc5dfd` |
| branch | `experiment/issue65-p1-public-plan` |
| P1-b checked origin | `be244a0bdb510a22417241c2aa2f76a9093aac1b` |
| guest SHA256 | `d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481`、UNQUALIFIED |
| 今回の出口 | source照合済み計画・検出条件。runtime実装、build、benchmark、新CIは0回 |

作業branchとcommit identityを確認。P1-b [CI42353912021](https://github.com/masahitojp/mariamem/actions/runs/42353912021)
のmetadataを本taskで1回取得し、head一致、in_progress / conclusion=nullを確認しました。
それ以降は未確認です。過去のP1-a結果は保存receiptを参照し、今回再取得・再実行していません。

## 以前の条件と検出網

照合対象は[P1計画](../design/issue65-native-protocol/productization.md)、
[P1-a review](issue65-p1-host-ownership-plan.md)、[責務表](../design/issue65-native-protocol/contracts.md)、
[D1–D3](../decisions/issue65-native-wire-contract.md)、[status](../project-status.md)、
[P1-a receipt](../../benchmarks/spikes/issue65-p1-owner/evidence/ci42346396518.json)、
[P1-b Mac証跡](../../benchmarks/spikes/issue65-p1-timeout/README.md)です。

| 条件/gap | 判定とsource evidence | 検出網・次の条件 |
| --- | --- | --- |
| host接続枠・identity・退役 | P1-a限定範囲は保存receiptで充足。公開routeへの到達は未充足 | 既存owner9ケースを抽出coreへ再bindし、mixed TCP/Dial16/17を公開入口で実行 |
| 30sと全正のduration | P1-b Mac限定確認。Linux再現・291-file/241観測比較は未確認 | 成功receipt確認後に実行開始。既存timeout8ケースを保全 |
| 公開native選択 | 未実装。base `mariamem.go:128`、`internal/control/shared.go:180`はhost.StartGenerated | 現専用cmd CIでは不可視。public factory無効化でFAIL、legacy Serve tripwire未発火の両方が必要 |
| 公開Dialの受付契約 | `internal/host/server.go:154`は容量不足をworker開始前に返す。prototype pipeはwire ERR接続を返すため単純移植不可 | actual DialContextのErrCapacity、取消前受付ゼロ、TCPとの共有枠を検査 |
| 原因観測と終了 | `mariamem.go:135`のwatchはGuest.Doneに依存。watchのdb.mu保持中closeは早いDoneと相性が悪いというsource推論。被害の再現はしていない | native worker/relay hold下でFailure/Errを先に観測。Doneは全join後。早いDone mutationでFAIL |
| typed disposalと永久debt | `internal/host/disposal.go:23`、`internal/disposal/disposal.go:102`、`mariamem.go:213`、`snapshot.go:73`が既存所有。prototypeのplain join errorだけでは不足 | 公開Start/Close失敗＋遅いjoin＋削除失敗。owner削除mutation、CaptureDebt伝播、cleanup後も永久親lease保持を検査 |
| Snapshot/Fork/Liveと設定継承 | `snapshot.go:127`はs.opts、control shared:152はbaseline設定を継承。prototype固定5000ms forkは移植しない | fractional設定の実guest inspection/expiry。既存Live endpointへ再bindし、取消・tombstone・drain・親Closeを公開Go/Pythonで検査 |
| Busyとcaptureの権限 | cached STATEは遅延しうる。公開Snapshotの最終判定をcacheへ置換する根拠はない | 遅延/古tuple STATEとguest fence省略mutationでFAIL。新host MySQL decoder不要 |
| SQL/wire互換 | 既存G1/G2・compat/limitsは足場であり新public backendの証明ではない | 抽出後の同一coreとpublic TCP/Dialへ再bind。既承認D1/1043以外のoracle変更は別判断 |

## Missing-things scan

- 未充足条件は上表とartifactに列挙済み。内部抽出だけ・Goだけで完了とする範囲縮小や、再承認を必要とする新条件は見つからなかった。
- README/go/python/releasingの公開usageは変更していない。現公開routeの動作を変更しない計画なので、新たなusage矛盾は見つからなかった。
- generated-source ownership、HANDWRITTEN_FILES、release inputs/baselines/notes、canonical patchは未変更。staged factory/source inventoryとcanonical切替を分離し、後者はP1-eに残す。
- 未到達境界は抽出後の実runtime、公開Go/control/Python、失敗とjoinの合成、両OS。現CIが検出できない点は上表に明記。cold/warm性能は未測定。
- 独立生成・両OS受入れ・P2 consumer/performance・qualificationを完了と記載していない。P1-bのLinux成功も未確認扱い。
- main統合・製品採用・releaseを今回の判断へ混ぜていない。新public flagや別Live世代controllerを追加しない。
- runtime変更は無く、削除動作を説明する新たなstale in-code commentは見つからなかった。既存prototypeを製品化済みとは記載しない。

## 次の作業と限界

P1-b成功確認後、C1のcore抽出とfake runner/disposal fault検査から実装します。
C2公開Go/control/Python接続、C3 Snapshot/Fork/Liveと両OS受入れまでがP1-c全体です。
最初のsession目安は2h active/30min tooling、重いCI0。全P1-cの費用は未計測で、安定差分後に
固定guest再生成・Mac・Linux1 cohortを計画します。今回のsource reviewは新経路の安全性・性能PASSではありません。
