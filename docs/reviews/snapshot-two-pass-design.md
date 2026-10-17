# Snapshot two-pass strategy and initial performance targets

2026-10-17。設計・Human Review資料。実装・新しい測定は未実施。
10msへの到達は目的・採用条件にしない。現行の利用者向け保証を維持して重複走査を統合する。

## Human Review

**判断は、通常のin-process Snapshotを3回から2回の全量走査へ統合する候補を実装・限定検証するか。
私は、固定後の再検証を所有取得時へ統合する案Aを推薦する。**
元の期待digest作成と、実際にForkする正確なbackingの最終検証を残せる。
約63msの重複区間を減らす余地があり、検証を終える時点を所有取得より前へ動かさずに済む。

**最も強い反論は、未検証の中間状態が現在より先のinternal境界を通ること。**
その候補をOwned／Fork入力と同じ型で扱わず、最終検証に成功するまで利用不能にする。
内部Freeze関数の失敗検出位置と、public Snapshotでの失敗拒否を分けてレビューする。
現在の破損拒否oracleを削ってテストを通す方法は採用しない。

## 1. Evidence and the unchanged guarantee

[macOS Light計測](https://github.com/masahitojp/mariamem/blob/a8a3ccb42d503234c11447d5a0ee1a63ca06a18c/docs/reviews/light-fork-macos-breakdown.md)：
v0.5.1 source_commit `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、Go1.26.8、
Apple M1／macOS27.0.1、Goの1表1行・4子・app-connections。
通常10回のSnapshot中央値192.86ms、全体517.67ms。
別のtrace10回では、固定/digest作成63.75ms、固定後検証63.33ms、所有取得検証63.31ms、
finishのfreeze外残差2.48ms。これらは区間時間であり、hash CPU単独ではない。

[Product contract](../decisions/snapshot-product-contract.md)を維持する：

- 取得完了前に、inventory・論理内容・guest identityを完全に検証する。
- Forkに使う正確なbackingを所有し、対応する操作から変更できない。
- 子・兄弟・世代の変更が基準に戻らず、基準Close後も開始済みの子は使える。
- busy／transaction拒否は元DBを維持する。停止開始後の失敗は未検証Snapshotを返さず、現行の消費・回収規則を維持する。
- Forkごとの全量再hashは追加しない。取得後の任意の外部破壊を毎回検出する契約へも拡大しない。
- private different-binary handoffは独立copy／検証を維持。通常heap経路の結論を適用しない。

## 2. What each pass protects

| 現行の走査 | 責任 | 案A |
| --- | --- | --- |
| 元内容を読み、digestを作り、blockを固定・移行 | 元の論理内容を期待値として確定する | 残す |
| 固定後の対象を読み直す | descriptor移行や固定後内容が期待値と一致するか | 所有取得時の検証へ統合 |
| 所有取得時に読み直す | 利用者へ返す正確なbackingが期待値と一致するか | 残す。統合した最終判定点 |

期待inventory／論理長／digestを移行元で確定し、移行先から自己申告された値だけで
正しいと判定しない。元と対象の比較を一度は残すので、一回走査への変更ではない。
暗黙ゼロ、truncateした末尾、継承blockのvalid範囲も論理内容に含める。

## 3. Candidate A — final verification at acquisition

状態遷移は次の境界にする。具体的な型名・関数名は実装レビューで決める。

`mutable producer → joined/sealed candidate → final verification → Owned → Fork`

1. 現行どおりrootと全workerの終了を待ち、MemFSをlockしてwriterをsealする。
2. 元内容のdigestと期待metadataを得て、移行したblock群を**未検証候補**として保持する。
3. Captureは未検証候補のみを渡す。候補はOwnedではなく、Fork／Acquireへ直接渡せない。
4. hostが完了したguestから候補を引き取り、期待inventory・identity・論理内容を最終検証する。
5. 検証した同一backingを、差し替えや内容copyを挟まずOwnedにする。ここで初めてpublic Snapshotを返す。
6. 検証失敗・cancel・途中失敗では、Ownedを生成せず候補とCapture参照を解放する。

必要な確認：raw mutable alias、producer node、FD、dirty map、祖先blockへの参照がどこに
残り、どの操作から書き込めるか。seal後にwriterが無いことと、最終検証からOwned化まで
対象が変わらないことをコード経路で確認する。cached booleanやpath名による省略はしない。

現行`FreezeHeap`を直接利用する内部callerには「戻る前に検証済み」という期待がある。
その既存入口を黙って未検証へ変えず、strictなwrapperを残すなどして新しいcandidate経路と区別する。
既存の`OwnHeap`へ未検証Heapを渡した際の破損・identity拒否も保持する。
production候補経路には、移行後から所有取得までに内容／対象を壊す失敗oracleを別途接続する。
既存テストをstrict wrapperで通すだけでは、新経路の検証完了と数えない。

変更候補の所有元は`internal/prepared`（候補・Capture）、手書きMemFSのfreeze処理、
`internal/generatedgo/runtime_instance.go`のcapture接続、`internal/guest`、
`internal/host/heap_snapshot.go`、`internal/snapshot/heap.go`。
生成された関数群を手編集しない。正式owner・生成/provenance手順を維持する。

## 4. Alternative B and excluded shortcuts

案Bは固定後の検証を残し、その正確なverified resourceを証明するhandleで所有取得の再読を省くもの。
これも2回走査だが、検証後の受け渡し期間にmutable aliasが無い証拠がより重要になる。
最終検証を利用者への返却直前に残せる案Aを先に選ぶ。案Aが成立しなければ勝手にBへ切り替えず再レビューする。

今回扱わない：sampling hash、弱いhash、暗黙ゼロの検証除外、uncheckedな検証済みflag、
検証失敗のfallback、GC/block形式変更、InnoDB shutdown変更、Fork起動変更、API変更、
pgmemの10msへの到達。通常処理に全量内容copyを追加して性能を相殺しないことも確認する。

## 5. Initial targets — hypotheses, not measured promises

同じmacOS／Go Light workloadに限る初期目標：

| 指標 | 現在の通常中央値 | 初期の狙い | 採用検討へ進む目安 |
| --- | ---: | ---: | ---: |
| Snapshot | 192.86ms | 約130〜150ms | 中央値150ms以下（約22%以上短縮） |
| 準備→Snapshot→4子SQL→全Close | 517.67ms | 約450〜480ms | 中央値480ms以下（約7%以上短縮） |

根拠は約63msの区間を1つ統合できた場合の費用モデル。中心的な見込みはSnapshot約130ms、
全体約455msで、候補管理・metadata確認等の追加費用とばらつきを見込んで幅を置いた。
区間中央値の算術を、実測した改善結果や必ず回収できる秒数と解釈しない。
この目標をLinux、大規模fixture、Pythonの保証やSLOへ転用しない。

## 6. Implementation acceptance and finite stop

実装承認後に、次の順に一回の候補を評価する：

1. identity・inventory・内容破損（移行時／所有直前）・暗黙ゼロ／tail・失敗／cancelをdeterministic fixtureで確認。失敗側が拒否され、正常側が通ることを示す。
2. 元FD書き込み拒否、子／兄弟／派生世代の独立性、基準Closeと開始済み子、Capture参照解放、失敗時回収を既存資産で確認。
3. 正式な生成・source/provenance保証を変更境界に応じて確認し、固定source／実binary identityを記録。広いRelease Qualificationと公開は別判断。
4. 同じLight workloadでbaselineと候補を交互に各10回、traceなしで比較。全観測を保存。必要な内訳確認は別cohortとし、通常時間へ混ぜない。
5. 10MiBの既存fixtureも通常計測を各3回に限定し、Snapshot以外へ費用を移しただけでないか全体時間を確認。allocation／回収の資源観測は別cohortで各1回とし、通常時間へ混ぜない。新しい全体性能キャンペーンは行わない。

correctness oracleが失敗すれば性能にかかわらず採用しない。目標未達や中規模全体の悪化は
隠さずHumanへ返し、目標を下げたり試行を際限なく追加しない。目標達成でも自動main採用・
releaseではない。より広いVFS変更や製品契約変更が必要になった場合は、そこで範囲を再判断する。

今回完了したのは作戦と目標値の提案。型設計の成立、全alias経路、oracle実証、候補性能は
これからであり、実装済み／保証維持を実証済みとは報告しない。
