# Adopted main: final configuration Qualification

2026-10-17。**Final Qualification PASS** for source_commit
`c97e55fc065f6ee7b560325077726da53e5d95d7`。
[Run 38935990860](https://github.com/masahitojp/mariamem/actions/runs/38935990860)
は`operation=verify`、full qualification。両platformとaggregate guardは`READY`。

## Human Review

**次の判断は、残る最終構成の利用・性能確認へ進むか。推薦は進むこと。**
採用した起動順序修正・D block storage・Python共有host・保存／load API廃止を含む
同じsourceで、独立生成、両OSのruntime／配布物／外部consumer検証が通った。
このQualificationから新たなcorrectness blockerは報告されていない。

**最も強い反論は、以前の資源計測で遅かった1試行の原因・頻度が未解明な点。**
今回のCIは性能比較ではなく、それを解消した証拠にはならない。
次の利用・性能確認で、準備→Snapshot→子→全Closeの区間と資源を既存harnessで確認する。
機能と配布物のQualificationは完了とし、未測定の性能判断を混ぜずに次の工程へ渡す。
新しい計測はこの結果報告では開始しない。公開・タグ作成も行っていない。

## Identity and evidence

| 項目 | identity／扱い |
| --- | --- |
| candidate source_commit | `c97e55fc065f6ee7b560325077726da53e5d95d7`。workflow sourceも同じ |
| operation／mode | `verify`／`full`。旧READYの流用ではなくguest／candidate jobsを実行 |
| guest | MariaDB12.3.3、Wasm `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09` |
| package metadata | Go/Pythonは0.5.0表記のまま。公開済みtag source `44100ec676c8c9064f32f3a01bd9a990d487bb61`とは別のprivate candidate |
| macOS | 15.7.9 arm64、canonical Go1.26.8、external Go1.27.2もPASS |
| Ubuntu | 24.04 x86_64、canonical Go1.26.8、external Go1.27.2もPASS |

[receipt check](main-storage-qualification-evidence/receipt-check.json)は、3つの小さな証拠artifactの
ZIP hashをGitHub APIと照合し、元READY・両受入JSON・wheel・installed fixtureのidentityを
照合した記録。両Go consumer／wheelの全2,586 source file hashは、対象commitのGit blobと一致。
CI build／guardをローカルで再実行した結果ではない。

[READY](main-storage-qualification-evidence/ci-ready.json)、
[qualification references](main-storage-qualification-evidence/qualification.json)、
[macOS acceptance](main-storage-qualification-evidence/darwin-acceptance.json)、
[Ubuntu acceptance](main-storage-qualification-evidence/ubuntu-acceptance.json)を保存。
READY内のrunner home prefixだけを公開用に正規化し、元／保存hashをreceiptに残した。
受入JSONは元bytesのまま。後続の資料commitへexact-SHA READYを付け替えない。

## Results

| 境界 | 判定 | 証拠／範囲 |
| --- | --- | --- |
| 独立source→Wasm build 2回 | PASS | [guest job](https://github.com/masahitojp/mariamem/actions/runs/38935990860/job/117091776043) |
| Go独立再生成・offline GPL source closure | PASS | 同guest job。provenance／source guardも通過 |
| canonical check／integration・wheel build | PASS・両OS | [macOS candidate](https://github.com/masahitojp/mariamem/actions/runs/38935990860/job/117099973288)、[Ubuntu candidate](https://github.com/masahitojp/mariamem/actions/runs/38935990860/job/117099973448)。source/license/mirror22成功、Python607成功・26 SKIP、integration17成功・Snapshot33項目、Go test/vetとfocused race |
| 外部Go・installed Python・所有／失敗cleanup | PASS・両OS | [macOS verification](https://github.com/masahitojp/mariamem/actions/runs/38935990860/job/117113034523)、[Ubuntu verification](https://github.com/masahitojp/mariamem/actions/runs/38935990860/job/117113034528)。runtime overrideなし、実source inventory一致 |
| GORM／SQLAlchemy | PASS・両OS | それぞれ32／44 cases。元acceptance receiptを参照 |
| 外部Go1.27.2 consumer | PASS・両OS | 同sourceのin-memory Snapshot lifecycle／candidate smoke。minimum Goは変更なし |
| platform／aggregate source・license・artifact guard | READY | [aggregate](https://github.com/masahitojp/mariamem/actions/runs/38935990860/job/117120062448)と保存READY |
| 最終構成の新しい性能・資源比較 | NOT RUN | 遅い1試行の原因・頻度の判断も残る |
| publication／post-publication smoke／recovery | SKIP | `verify`による意図した非実行。公開はされていない |

checkの26 SKIPは両OSで同じ集計。real-host opt-in 23件と固定MariaDB archiveを要求する
native認証ソース比較3 modeに対応する。うち17件はintegrationで別実行して成功した。
残るガイド3件・開発専用経路・型probe・強制timeout診断とnative認証3 modeを、このrunで
PASSしたとは数えない。ガイドは以前の限定native検証で通過している。
checkは`-q`で個別SKIP理由を記録しないため、内訳は固定source／workflow選択からの対応づけ。
[macOS集計](main-storage-qualification-evidence/darwin-check-integration-excerpt.txt)、
[Ubuntu集計](main-storage-qualification-evidence/ubuntu-check-integration-excerpt.txt)を保存した。

installed fixtureのassertion failure1件・setup error1件は意図したcleanup試験であり、
全fixture disposalと最終host reapが成功した。実行していない項目や期待失敗を隠すために
既存oracle／guardを変更したものではない。

## Remaining boundary

Qualification PASSは上記exact sourceの技術的なguard結果。公開済みv0.5.0の差し替えや
新しい版のリリース承認ではない。次版のversion metadata／notesと最終sourceが変われば、
公開時のexact-source／artifact guardが改めて必要。

今回のguestの調査済みcorrectness修正を再び未完了へ戻さず、一般共有メモリの保証拡張や
追加hash削減を必須残件に加えない。残る利用・性能確認とHuman Reviewを経て公開を判断する。
