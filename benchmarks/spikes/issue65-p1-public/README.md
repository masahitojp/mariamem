# Issue65 P1-c / C2: public native wiring

**公開Go/Python APIからnative coreへの接続と、既存の基本Snapshot/Fork/Live consumerがmacOS arm64で通った。**
次はC3の設定継承の精密確認・実failure/永久debt・元oracles再bind・Linux受入れへ進むことを推奨する。
公開入口と実engineを結び付ける証拠を得た一方、C3全体の安全性・全互換性をこの結果からは判断できない。
[P1-c全体](../../../docs/design/issue65-native-protocol/public-backend.md)の完了、main採用、性能比較、releaseは未実施。

## 固定入力

| 入力 | identity |
| --- | --- |
| base | `30910a0952314b0125358615bb76269c1701c0a4` |
| 実public artifactのhost source_commit | `3602b186f309eb3af349df494470d28b8bb800c2` |
| 主consumer/負例のobserver | `af42349d368e281f530935c33d620af3b6ebf7e1` |
| 追加の既存lifecycle consumer observer | `545ca1f83e7749d59556edfbab2c4f9bee36b45e` |
| guest/installer origin source_commit | `be244a0bdb510a22417241c2aa2f76a9093aac1b` |
| guest SHA256 | `d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481`、UNQUALIFIED |

[まとめ](evidence/receipt.json)、[public結果](evidence/public-result.json)、
[基本lifecycle結果](evidence/public-lifecycle-result.json)、[全staged source inventory](evidence/public-source.json)。
Go1.26.10、実artifactはCGO_ENABLED=0。Python/PyMySQLの実profileはreceiptに記録した。
後続observerは測定fixtureを追加し、実artifactのGo production sourceを変更していない。

## 実装

`internal/host.Service`とfactoryへ公開Go Start、Python shared/control、standalone hostを接続した。
rootの既存private backendは狭いまま保ち、具体的なGuest.Done/PIDへの依存をserviceへ移した。
canonical factoryは既存StartGeneratedを呼ぶ。固定UNQUALIFIED staged module/wheel/hostは、明示的な
factory overlayでStartNativeを既定にする。新しい公開Options/runtime名/環境toggleは追加していない。

Native adapterはC1 coreを既存ownerへ接続し、次を保つ。

- TCP/Pipeの共有16枠。公開Dialは受付時ErrCapacity、TCPは既存bounded pre-login1040 helper。
- 即時Failureと全execution/reader/accept/relay join後のDone。owner first causeとtyped disposalを保持。
- restore借用はREADY、起動失敗時はretained cleanupの完了まで保護。READY直後の取消でもlistenerを公開しない。
- native拒否を既存busy/transaction/closed/capacityへ写し、CaptureDebtをGo/controlの既存親lease所有へ伝える。
- Snapshot/forklimit/Liveの既存ownerを使う。prototypeのpoolや固定5000ms forkは移植しない。

C1 coreには、起動時にcompletion/ctxとfailureが同時にreadyでも最初のruntime原因を返す修正を追加した。
100回のcompleted-before-READY検査とraceで確認した。実worker joinを早める変更ではない。

## 実際に確認したこと

[Go log](evidence/public-go.txt)の4 top-level casesを厳密に選択・集計し、SKIPを認めていない。

| 経路 | 確認 |
| --- | --- |
| 公開Go TCP/Pipe | prepared `SELECT ? + ?`、同じ物理sessionで通常SQL error→following query、owner健康性 |
| 共有容量 | TCP/Pipe混在16、公開Dial17件目ErrCapacity、TCP17件目1040、pre-canceled Dial |
| fatal | 実query deadlineでEOF/connection loss、ErrUnusable＋context.DeadlineExceeded、独立DB継続 |
| 公開既定timeout | 30sの公開設定経路でDO SLEEP(10.2)完了（10.23s）。最大durationの実時間待機とはしない |
| installed Python | checkout外、PYTHONPATHなし、wheelの通常start()/shared-control。SQL error後の継続、fatal EOF、ownerのdeadline原因、独立DB、host/temp回収 |
| standalone host | 同じinstalled binaryのready/runtime PID/capacity、SQL、status、close/終了 |
| 既存Go consumer | 公開Snapshot/Fork/Live、data reset、交換枠不足、保持connectionのdrain拒否、閉じた親、Fork limit/取消の元assertions |
| 既存installed Python consumer | child独立性、max_forks=2、capacity timeout、Live spare予約、stable endpoint/reset、host/temp回収 |

新core単体と既存disposalはrace PASS。公開owner/host/controlの重点検査もrace PASS、focused vet PASS。
backend debtをphysical cleanupで許さない親lease伝播、借用baselineと遅い起動cleanupはfakeで検査し、
実guestのfailure/永久debt注入済みとは扱わない。C1由来の5 source-overlay負例も全検出。

public artifact内の旧mysqlwire.Serveには常時panicのtripwireを置き、全positiveで未発火。
[Go](evidence/public-go-factory-control.txt)と[Python](evidence/public-python-factory-control.txt)は、
同じguest/runtime/fixtureのままnative factoryだけを無効化すると失敗した。
source IDや専用cmdの成功だけをnative public到達の証拠にしていない。

## provenanceと残条件

固定originからguestを1回再buildし、P1-bのguest SHAを再現した。installerはそのoriginのclean checkoutで
実行し、今回のhost sourceは別入力としてinventoryへ結び付けた。既存guardを緩めていない。
[runtime比較](evidence/native-runtime-comparison.json)では、P1-bのproduction Go/assembly/data全79ファイルが
同じ。旧test fixturesはこの比較から明示的に除いた。worker bindingとABI16/40/44を変えていない。
全staged source、binary、wheelのhashを保存した。binary buildinfoのartifact位置だけを
[明示的に正規化](evidence/public-binaries-normalized.json)し、raw receipt SHAも保存している。

初回にはdirty tooling/canonical-path/出力namespaceのpreflight停止があった。SDK cleanupで消したtracked
build/go.modは元commitの内容へ戻し、clean sourceを再確認してからinstallerを再実行した。
実SQLの期待値変更・SKIP・oracle削除は無い。SDK/生成物/cache/wheel/worktreeは保存知識へ縮約して清掃する。

[public-source全体](evidence/source-boundary.json)は旧証跡6ファイルのlocal pathでFAILのまま。
追加・変更sourceは同じpatternで確認し、guardを弱めていない。公開前の残件として保持する。

C3には、nondefault/fractional設定のStart→Fork→Live Resetでの正確な観測、実worker/relay holdと
永久capture debt・late cleanup、元22 lifecycle/88 compat/38 limits/G1 234/G2 241等の同core/public経路への
再bind、Linuxでの受入れが残る。通常CIにはまだnative public選択の検出網を常設していない。
P1-d残るhost policy、P1-e canonical生成物/常設CI/main候補、P2 consumers/性能は後続。

## 再現

owned workspaceのfixed-origin guestを既存P1-b手順でbuildし、clean host sourceから次を順に実行する。
各段階をexperiment_disk.py/runで容量・時間を監視し、tempのGo/Python環境を使う。

```sh
python3 scripts/git_identity.py inspect HEAD
python3 benchmarks/spikes/issue65-p1-public/assemble.py --workspace "$TASK_PUBLIC_WORK" --guest-workspace "$TASK_GUEST_WORK" --stage translate
python3 benchmarks/spikes/issue65-p1-public/assemble.py --workspace "$TASK_PUBLIC_WORK" --guest-workspace "$TASK_GUEST_WORK" --stage install
python3 benchmarks/spikes/issue65-p1-public/assemble.py --workspace "$TASK_PUBLIC_WORK" --guest-workspace "$TASK_GUEST_WORK" --stage compile
python3 benchmarks/spikes/issue65-p1-public/qualify.py --workspace "$TASK_PUBLIC_WORK"
python3 benchmarks/spikes/issue65-p1-public/lifecycle.py --workspace "$TASK_PUBLIC_WORK"
```

qualifyは新しいpackage/wheel出力を作る初回実行用。失敗時は元log/hashを保持して対象owned出力を整理する。
このtaskで新CIは投入していない。両OS qualificationやpublicationをこのローカル結果で代替しない。
