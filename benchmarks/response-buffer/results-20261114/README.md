# Host応答受信4KiBバッファ — 有限試作結果

**結論・推奨: 今回の4KiB受信バッファは製品候補化を見送る。** underlying Read回数はほぼ半減し機構は確認できたが、P1の全体時間はほぼ不変、P8のprocess wallは5組中4組で増加した。P8 CPUには小幅改善が見えるものの、目的の全体時間短縮を支持しない。固定計測で終了し、追加反復・サイズ探索・別transportへ自動展開しない。

最大の反対材料は、I/O削減が明確でP8総CPUも4/5組で減ったこと。しかしRead数を性能の代用にはできず、単一共有Macの有限結果から更なるチューニングを正当化しない。別案を選ぶ場合は新しい仮説と有限計画が必要。

## 問い・固定条件

#185 のHuman承認に基づく局所試作。#182の内部応答I/O調査を継承する。

- baseline source_commit: `bb1e937ae75b5788c8548a52987d9d42f78292d5`。build前にgit_identity.pyでworktree HEADのcommit型/SHAを確認（source.json）。
- guest SHA256: `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`。guest/WASI/空Write/パイプ構造は変更なし。
- Go1.27.4/macOS arm64/CGO0/GOMAXPROCS8/GOGC100、共有Mac。別OS・専用静穏hostは未測定。
- ハーネスは918fb708の保存済みmaria-suite。通常DSN、元SUM trigger、UPDATE OF status監査、16MiBを維持。Human決定に従い事前集約SQL `REVENUE_PREAGG=1`。公開DB/Snapshot/接続のClose errorを集約し、非nilならprocessを失敗させる検査を追加。
- 同一binaryのpackage初期化時フラグ `MARIAMEM_EXPERIMENT_READ_BUFFER=0/1` で対照。binary SHAは全recordsで同じ。baselineも観測用linked.go overlayを含み、primaryではobserverを無効化。無加工canonical binaryそのものとの比較ではない。
- baseline/candidateとも同じsource/guest/workload。P1/P8各arm1warmup＋交互順5組。observerありはP8各arm3process。計30process、順序・予算はplan.json。
- 作業領域予算8GiB・空き8GiB、build各1200秒/process180秒。全build後に計測し、実行中は軽量free-space検査のみ。再帰容量走査を重ねていない。

## 変更の実物

`Process.read` の入力だけを切り替えるGo overlay。experiment.patchに全文差分を保存。

```go
var input io.Reader = p.out
if experimentReadBuffer {
    input = bufio.NewReaderSize(p.out, 4096)
}
// 同じinputをheaderとbodyの両方で使用
io.ReadFull(input, h[:])
io.ReadFull(input, b)
```

Close/Abortは元のp.outを所有し続ける。32MiB frame上限、ゼロ長拒否、ID/decode検査、ready・終了経路は元のまま。追加約4KiB/Processのbufferとcopyの費用をcandidateへ含める。保持bufferの設計量であり、peak RSS改善の実測ではない。

製品sourceへの実装・main統合・releaseは行っていない。実験フラグは製品APIの提案ではない。

## 正しさ

両armでinternal/guestの全focused package testsがPASS（各15 top-level tests、subtestsを含む）。追加3テストは以下を確認:

- 1/3byte単位の分割入力、連続2frame、6,600byte文字列を含む4KiB超応答で結果一致。
- ゼロ長/32MiB超、不完全header/body、不正JSON、未知request IDを拒否。
- blocked pipe Readに対するAbortで読取goroutineが終了。

既存ready opt-in timing、worker failureによるpending失敗とowner join、disposal等も両armで成功。unit-arm0/1.txtに全結果。

全30 suite process PASS、全2,100 test body spanを確認。追加した公開Close error検査も成功。observer6processの132 DBすべてでguest終了errorなし。各DBの要求/応答byte・frameを両端で照合した。これは有限fixtureの検証で、全故障・全platformへの製品受入れではない。

## I/O回数 — 機構は確認

observerをbufioの下、元os.PipeのReadへ置いた。bufioの論理Read数ではない。

| round | baseline Read / 応答frame | candidate Read / 応答frame |
|---|---:|---:|
| 0 | 11,576 / 5,788 = 2.000 | 5,753 / 5,767 = 0.998 |
| 1 | 11,520 / 5,760 = 2.000 | 5,749 / 5,795 = 0.992 |
| 2 | 11,506 / 5,753 = 2.000 | 5,772 / 5,788 = 0.997 |

少数の連続応答も先読みできるため1Read/frameをわずかに下回った。大きい応答・short readでは1frameに複数Readも必要で、必ず1Readとはしない。frame総数のarm間変動はpool接続生成等を含み、arm間の総bytes完全一致を要求しない。同じ通信の両端で一致することを確認した。

メソッド境界のRead回数でありkernel syscallの直接traceではない。observerありの時間はprimary性能比較へ混ぜない。

## 性能 — 全体短縮を支持せず

単位ms。warmupを除く5processの独立中央値。paired%は同じroundのcandidate/baseline変化率を5組で中央値化したもの。独立中央値比と混同しない。

| P / 指標 | baseline | candidate | paired変化中央値 | candidate短縮組 |
|---|---:|---:|---:|---:|
| P1 process wall | 1331.390 | 1333.464 | -0.002% | 3/5 |
| P1 suite elapsed | 1282.070 | 1281.519 | -0.209% | 3/5 |
| P1 total CPU | 1734.806 | 1749.842 | +0.625% | 2/5 |
| P8 process wall | 462.175 | 483.679 | +3.852% | 1/5 |
| P8 suite elapsed | 426.364 | 438.972 | +1.298% | 2/5 |
| P8 total CPU | 2192.398 | 2192.150 | -1.437% | 4/5 |

process wallはbinary起動前→終了、suite elapsedは既存recorderのbootからAPI cleanupまで。CPUはgetrusageのuser+system、全thread合計。各中央値は独立なのでuser中央値とsystem中央値の和がtotal中央値と一致するとは限らない。

サンプル投入のprocess内p50をさらに中央値化すると、P1は36.017→35.920ms、P8は72.232→72.252ms。並列spanは重なり、工程p50を足して全体差へ分解しない。CPU/投入工程だけを選んで採用推奨にしない。

全30観測・warmup・遅い個体を保持し、失敗再試行や事後除外、性能追加反復なし。最初の集計時にtraceのduration_msキーがないことを検出し、end_ms-start_msへ修正して保存データだけを再集計した。計測の取り直しではない。

## 判定と残る条件

原問「Read回数と全体費用を減らせるか」に対し、**Readは減らせたが、今回の対照は全体時間短縮を支持しない**。4KiB案は見送りを推奨し、この有限試作を終了する。

小さいCPU改善とlatency悪化の因果は分離していない。copy/起床/スケジューリング等を原因と確定しない。別OSも未測定。これらは今回の見送りを返す妨げではなく、自動で追加調査しない。製品候補化を後に選ぶ場合のみ、基準sourceの差分・変更境界に応じたcanonical check/両OS受入れを別途判断する。

## 保存・再現

exact harness、guest/linked overlay、仮想追加テスト、experiment.patch、plan/source、全30 trace/log、132 DB ledger、summary/analyze.py、binary-info/hashを保存。sourceを同じcommitへ復元し、harness go.modの製品replace、overlay.jsonの絶対pathを新workspaceへ調整する。build.py→measure.py→analyze.py。解析は保存データだけで再生成できる。

guest_overlay.go.txtとlinked_overlay.go.txtをtempへ戻し、experiment_buffer_test.go.txtを仮想test pathへ接続する。setup.pyは元の保存済みハーネス/observerからの準備手順も残す。SHA256SUMS.jsonで保存ファイルを検証する。
