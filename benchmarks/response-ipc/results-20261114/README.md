# 内部応答I/Oの現行対応づけ — 2026-11-14

**結論:** 応答の非空Writeは既にほぼ1回/frame。空Writeは既知の未採用候補と同じ構造であり、新しい改善として再発見したものではない。別の局所候補としてhost応答受信の4KiB程度の固定バッファを小試作する価値はある。現行ではヘッダ4byteと本文がそれぞれ別のReadになっている。実装・性能利益は未検証で、約44ms短縮の証拠にはしない。

最も強い留保: 前回の投入CPU profileで大きかったのはguestの応答Writeであり、host Readを減らしてもその書込自体は残る。バッファcopyや保持メモリも増える。I/O回数減少だけで製品採用を勧めない。

## Source・範囲

製品source_commit `bb1e937ae75b5788c8548a52987d9d42f78292d5`、guest `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`。build前にgit_identity.pyでworktree HEADのcommit型とSHAを確認（source.json）。製品は変更せず、linked.goの既存os.Pipe両端へ旧observerを再適用したGo overlayのみ。source/overlayの実物を保存。

ハーネスはf26e31542c15587a59b83b8c48d73c2610a7adcfの保存済みmaria-suite。Human決定に従いREVENUE_PREAGG=1。通常DSN補間、UPDATE OF status監査、元SUM trigger、既定16MiBを維持。macOS arm64、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、P8、共有Mac。比較対象エンジンの追加測定はしていない。

観測on3/off3を交互順に固定。build終了後に測定し、測定中の再帰容量走査は行わない。予算8GiB・空き8GiB、build1200秒/process180秒。全6process/420 test body PASS。観測onの各22 DB、計66 DBでguest終了errorなし、要求・応答両端のbyte/frame数一致。onの全processで70 bodyをtraceから確認した。

observerはメソッド境界のRead/Writeを数える。kernel syscallを直接traceした値ではない。guest終了後の保存時点ではhost側EOF/Closeの計数が終わっていない可能性があるため、終了時のRead回数・解放完了の証明に使わない。

## 現行の回数・サイズ

| 1 suite・3processの範囲 | 値 |
|---|---:|
| 応答frame | 5,753–5,809 |
| guest Write呼出し | 11,506–11,618 |
| うち0byte Write | 5,724–5,780 |
| guest非空Write | 5,782–5,838 |
| host Read呼出し | 11,506–11,618 |
| うち4byte Read | 5,753–5,809 |
| host Write呼出し | 5,753–5,809 |
| guest Read呼出し | 11,486–11,526 |
| うち3byte Read | 5,742–5,762 |
| 応答bytes | 約1.58–1.59MB |
| 要求bytes | 約0.440–0.441MB |

応答frame当たりguest非空Writeは約1.005回、host Readはちょうど2回（保存時点）。非空Writeのサイズ上位は219/220/218byte、host本文Readは対応する215/216/214byte。つまり小さい通常応答は既にheader+bodyを一度に書いているが、受信側が二度に分けて読む。非空Writeのうち4KiB以下は5,777/5,798/5,833回、4KiB超は各5回、最大6,641byte。ただしWriteサイズ分布はframe長分布そのものではない。

通常要求frameは5,731–5,787、停止zero frameは22。prepared opcode5は全3回で5,166件。21 LoadSample×(240 EXECUTE+3 PREPARE+3 CLOSE)=5,166と一致する。全suiteのCPU/通信を明細INSERT100件だけの費用へ帰属させない。

## ソースとの対応

- `guest/resident.inc:multi_reply`はstdioへ4byte header、JSON bodyをfwriteし、multi_output mutexを保持してfflushする。Cのfwrite回数とOS Write回数は同じではない。
- `internal/generatedgo/code/base/base.go:writeVec`は全iovecでWriter.Writeを呼び、混在列の空要素も渡す。非空Write約1回＋空Write約1回/frameという既知のmusl/WASI経路が現在も残る。
- `internal/guest/guest.go:Process.read`はp.outへio.ReadFull(header4byte)、次にio.ReadFull(body)を直接行う。今回の4byte Read数がframe数と一致するのはこの境界に対応する。
- guest要求受信はresident.incでheader/prefix/bodyをfreadし、WASI readVecもiovecを個別Readへ展開する。3byte Readが多数ある事実は確認したが、musl内の各iovecとの完全な対応は今回分類していない。短いread/EOFの意味を変えるreadVec改変には進まない。

## 過去の空Write省略との違い

[旧有限試作](https://github.com/masahitojp/mariamem/blob/c2cadc50d10b3d885d665437c9d3be4ea7ee3e0b/benchmarks/skip-empty-write-20261113/README.md)は混在iovecの空要素だけを省き、all-emptyのFD/error契約を保つもの。固定5組でwallのpaired中央値-1.63%、総CPU+1.68%。別cohortでもCPU削減は確認されず、main未採用。現在のwriteVecにもその省略は入っていない。

今回の大きいCPU書込経路にはこの既知の費用が含まれる。新しい書込分割を見つけたとは言わず、同じ省略実験を繰り返していない。空Write約半数の除去を全体半減へ換算しない。

## 観測負荷・限界

off wallは1997.85/459.62/451.95ms、onは569.53/503.96/503.58ms。最初のoffも除外していない。warmupなしの診断で、初回や共有host変動を分離しておらず、on/off差から観測負荷や性能改善を確定しない。全値・CPU・binary hashをrecords.jsonへ保存。今回の目的は回数・サイズ・source対応であり、採用前後の速度比較ではない。

前回のCPU profileは別の逐次LoadSample cohort。今回はP8 suiteのI/O回数。異なるcohort・時計を合成して削減時間を算出しない。

## 次の有限試作案

1. host側Process.readだけへ固定4KiBのbufio.Readerを1個置く。header/bodyのio.ReadFullの読取元を揃える。p.outのClose所有権、32MiB frame上限、ID検査、decode/failure/終了順序は維持する。guest/WASI/worker/protocolは変更しない。
2. 分割header/body、連続frame、4KiB超応答、切断、invalid length/ID、blocked ReadのAbort/cancel、ready/停止を既存transport fixtureで確認する。必要な境界にだけテストを追加する。
3. 同じ事前集約SQL・同じbinaryの対照で、observerありは両端byte/frame一致とunderlying Read数、observerなしはP1/P8 suite wall/CPUを固定回数比較する。buffer fillがshort readする場合もあるため、「必ず1Read/frame」とはしない。
4. 追加copy/保持メモリ、CPU/wallの交換条件を記録する。機構だけ改善・全体利益不明なら見送りで終了する。反復数・予算は試作開始時に固定し、今回の診断を再試行で置き換えない。

これは新しい改善候補の選定まで。上記小試作・製品実装・採用・CI/releaseは今回行っていない。#119/#143/#162や#167を再開しない。

## 保存・再現

harness/、linked_overlay.go.txt、ipc_overlay.py、overlay.json、build.py、measure.py、analyze.py、全6 trace/log、66 DB ledger、source/plan/binary hashを保存。sourceとharnessを復元し、製品replaceとoverlay絶対パスだけ調整してbuild→measure→analyze。保存済み集計はanalyze.pyで再計算できる。SHA256SUMS.jsonで保存ファイルを検証する。
