# purge head／view：元Wasm命令とGoの限定比較

## Human Review

**判断は、この限定比較を完了として、今回の観測を理由としたGo変換の修正には進まないことを受け入れるか。推薦は受け入れること。**
元の問い「Wasmが要求する挙動を維持できるか」に対し、今回のhead／viewアクセスでは
Wasmが禁止する値や、同期後の値の不一致は観測しなかった。
Goでは新旧のheadの混在を実際に観測したが、対象のWasm命令は16-byteのatomicコピーを要求していない。
ここを変換の欠陥と判定して全面的なmemory model修正へ進む根拠は得られていない。

**最も強い反論は、参照Wasmでは出なかった混在がGoでは出ており、MariaDBが暗黙に期待する性質を失う可能性。**
この反論は残る。混在した回収位置を実guestが使えば、必要な更新履歴を早く捨てる可能性がある。
ただし今回再現したのは小fixtureの混在であり、実guestでの混在・誤回収・SQL失敗ではない。
したがって「利用者への影響なし」とも「DB破損を再現」とも判定しない。
purge固有の保護前提は未確認の個別項目として残す。追加実行・修正を自動で開始する判断ではない。

## 承認範囲と完了の意味

起点は[静的照合](shared-memory-scalar-simd-reassessment.md)と、その後のHumanによる
上限2時間の限定比較の承認。対象はpurgeのhead／view、そのアクセス幅・lock・実行順序。
[実行前のprotocol](../../benchmarks/spikes/purge-wasm-go/protocol.md)で判定条件を固定した。
上限到達を完了理由にはしていない。定義したfixture比較、保護／順序の対照、判定器の正負対照を実施した。

**完了は小fixtureの比較に対してであり、実guestのpurge経路の同期証明に対してではない。**
既存36署名の全PC確定、149署名の再census、一般shared-memory modelの確立、
観測限界の包括的なHuman受容、Qualification／リリース判断は含まない。

## 入力と再現

- 製品source_commit：`47f297cc7498625e076abb93322eb616c9560bb8`（公開v0.5.2）。
  `scripts/git_identity.py`でcommit型を解決した。
- 実験ブランチの基点：`29e4d0b1865b96178de1f0f4cce40e0250b881b3`。
  関連するruntime／guest／生成入力は上の製品commitと差分なし。
  importするbase packageの全ファイルを製品commitのGit blobとbyte照合した。
- fixture Wasm SHA256：`98d57cf0a4f7be97e2bf50065f6f07634d1a3c1bba783e49119b1186154b6fde`、243 bytes。
  [hex記録](purge-wasm-go-evidence/fixture-hex.txt)と生成scriptから再構成できる。
- 最終campaignの実行環境：macOS arm64、Go1.26.8、Node v26.11.1（同梱V8をWasm参照に使用）。
  初期campaignのNode v18.18.2とは区別する。強化前campaignもNode v26.11.1。
  各記録は[最終](purge-wasm-go-evidence/results.json)、
  [初期](purge-wasm-go-evidence/initial-results.json)、
  [強化前](purge-wasm-go-evidence/pre-witness-results.json)の`node_version`を参照。
  Ubuntu x86_64はSKIP（今回ローカル限定比較では実行していない）。
- 入力hash、54回の通常実行・10回のrace診断、コマンド・版情報は
  [results.json](purge-wasm-go-evidence/results.json)に固定。

実験用の空領域を指定して、このブランチから実行する：

```sh
python3 benchmarks/spikes/purge-wasm-go/run.py \
  --temp /tmp/purge-comparison-temp --evidence /tmp/purge-comparison-evidence
```

通常の実験実行では[workspace手順](../experiment-workspace.md)のdisk guardを併用する。
製品baseが固定入力と異なればscriptは停止する。フルguestやconverterは再buildしていない。
既存の[real-opcode fixture方式](../../scripts/runtime_correctness/narrow_fixture.py)と同じbinary組立を使い、
今回のWasm exportsをNode worker_threads上で実行した。Go側はfixtureを新規変換したものではなく、
**製品が実際に呼ぶ未変更のhelperを直接使う**。完全な変換パイプラインの再検証ではない。

## 実guestとの対応条件

| 対象 | fixtureのアクセス | 対応の限界 |
| --- | --- | --- |
| head | 実global `24020976`。Wasmのv128.load/storeと、Goの`Simd_p_v128_load`／`Simd_p_fx262` | 実guestのp8読取とp1書込が呼ぶ同じhelper。MariaDBのtask schedulingは再現しない |
| view | 実global `24020776`、`sees()`が使う`m_up_limit_id`に対応する整列した通常8-byte load/store。Goは対象endpointと同じ`uint64`／`MemoryEA`式 | 実際の`sees`判定や履歴削除を実行せず、読める値と同期後の一致を比較 |
| lock | headの読取latch=`24020736`、書込end_latch=`24020864`。view読取のrseg lockは別scratch領域で代表 | 1 reader＋1 writerの0/1 CAS mutexへ抽象化。srwのreader count・waiter・slow pathの検証ではない |
| 保護対照 | 読取／書込が同じlockを使う。直前に書いたA/Bの識別子も同じlock内で照合 | 製品修正案ではない。Goは検査用heap変数、Wasmはhost control領域を識別子に使う |
| 順序対照 | writerの完了をreaderへ通知してから読取。Go channel／JS Atomics handoff | 実tpoolにこの順序保証があると主張しない |

Goのhelperは16-byteアクセスを8-byte×2で行う。
[macOS arm64 disassembly](purge-wasm-go-evidence/go-disassembly.txt)でも別々の64-bit MOVDを確認した。
Goのlock helperは`ForceContendedAtomics`で既存の並行用経路を選択した。
メモリはGo heapと本番の`NewMemoryMapping`を別々に実行し、headerやmappingを実行中に変更しない。

元ソースのlock・caller・回収位置の用途は[固定抜粋](purge-wasm-go-evidence/protection-anchors.json)に保存した。
元ソースにはreaderの`purge_sys.latch`、writerの`end_latch`、view更新の`latch`、
別rseg lock下の`sees()`がある。今回の抽象化はこの「共通の保護がまだ示されていない」場合を比較するもので、
実guestで共通の順序保証が存在しないと証明するものではない。
protocolの`view.low_limit`というラベルはlow water markの意味で使ったが、
正確なC++ member名は`m_up_limit_id`であり、`m_low_limit_no`等とは別である。
追加照合した固定`read0types.h`の宣言順と`sees()`を同じ抜粋に保存した。
実行したアドレス・幅・判定条件は変えておらず、実行前protocolは元のhashのまま保存する。

## 判定器：Wasm違反と回収位置の不整合を分ける

Wasmの非atomicアクセスでは、4 bytesを超える読取について、競合する書込の異なるbyteを
組み合わせることが許される。競合があるだけで未定義動作になるわけでもない。
これは参照エンジンの有限実行で一度も出ない場合にも区別が必要である。
[Wasm threads relaxed model](https://webassembly.github.io/threads/core/exec/relaxed.html)と
[Go memory model](https://go.dev/ref/mem)を参照した。両仕様全体の等価性を導いたわけではない。

headにはA=`(100,900)`、B=`(101,0)`を使った。
`(101,900)`は一度も完全なheadとして書いていないが、各fieldは書いた値から来ている。
Wasmの許容集合には含まれる一方、iteratorの順序ではA/B双方より先へ進む。
元ソースの`free_history_rseg()`はheadのtrx_noと一致するundoをundo_noまで切り詰めるため、
**こうした混在を回収限界に使うことは懸念になる**。その分岐をfixtureは実行していない。

ストレスはA/Bを交互に反復する人工条件である。実際のheadが単調に進む条件との差を補うため、
[有限モデル](purge-wasm-go-evidence/model.json)では一度だけのA→Bについて、
2回の書込と2回の読取の順序を保つ6通りを列挙し、同じ混在が可能な順序を示した。
これは語単位のinterleavingの例であり、Wasmの全実行を列挙するformal checkerではない。

viewは各byteが`0x11`／`0x22`のどちらかである値を使い、競合時の混在を許容した。
同期後は完全な値との一致を要求した。headとviewの世代が常に同一である、という未確認の契約は追加していない。
Go／JS双方の実際の分類器で各12個の正負対照を実行し、許容混在・進みすぎるhead・未書込byte・
保護条件下の混在を区別できることを確認した。データraceの報告自体は失敗oracleにしない。

## 観測結果

以下は最終campaign、macOS arm64の**人工競合ケース**。各行30万読取×3試行。
通常利用の発生率やエンジン同士の発生確率の比較には用いない。

| head・別lock | 読取総数 | 新旧混在 | そのうちA/Bより先へ進む値 | Wasm許容集合外 |
| --- | ---: | ---: | ---: | ---: |
| Node/V8・shared Wasm memory | 900,000 | 0 | 0 | 0 |
| Go・heap | 900,000 | 1,383 | 450 | 0 |
| Go・mmap | 900,000 | 5,709 | 3,063 | 0 |

**Goで観測し、参照Wasmでは今回観測しなかった差はある。Wasmの仕様が禁じる差は今回観測していない。**
V8の0件を16-byte atomicityの証明や、他のWasm実装でも0件という証拠にはしない。

| 対照・関連項目 | 結果 | 証拠範囲 |
| --- | --- | --- |
| 共通lock | PASS、全engine/backingで混在0・保護した識別子との不一致0 | head/view各90万読取、各engine/backing。製品srwの証明ではない |
| 完了handoff | PASS、混在0・直前の書込との不一致0 | head/view各3万読取、各engine/backing |
| 別lockの8-byte view | 許容集合外0、byte混在の観測0 | 各90万読取。8-byte Wasm非atomicアクセスの一般的な不可分性は未保証 |
| 正負対照 | PASS、Go12件・JS12件 | 判定器自身の検証。実guestの到達性の検証ではない |
| 通常実行全体 | PASS、54実行、10,980,000読取、定義した禁止観測0 | 新しいSQLテストやQualificationとは別 |
| 実guestの同時実行・SQL被害 | 未実施・未再現 | fixtureの混在をDB破損の再現と数えない |
| Ubuntu／別compiler／別Wasm engine | SKIP | macOS arm64／固定toolchainの限定比較 |

集計は[summary.json](purge-wasm-go-evidence/summary.json)、試行別はresults.json。
初期・強化前の完了campaignも保存し、最終campaignだけ都合よく選び直した扱いにしない。
途中のharness修正・失敗・採用しなかった結果は[campaign notes](purge-wasm-go-evidence/campaign-notes.json)に残した。

## race detector：値の観測と別の軸

各診断は10,000反復、最初の報告で停止する。報告数はcensus件数ではない。

| 診断 | heap backing | mmap backing |
| --- | --- | --- |
| head/view、別lock | 各1報告で停止。targetの通常read/writeを報告 | 各0報告。head混在は観測され、無報告でも問題の有無を判断できない |
| 共通CAS lock＋検査用heap変数 | 各0報告 | 各1報告で停止。対象は検査用heap変数 |
| 共通Go `sync.Mutex`＋同じmmapデータ／heap変数 | 対象外 | 各0報告 |

mmap上のCAS lockが保護するheap変数は、同じfixtureの共通lock下でも報告された。
Goの`sync.Mutex`を使う診断対照では消えた。これは外部領域の同期についての検出器の観測制約を示す材料であり、
通常実行での値の不一致ではない。逆にmmapデータへの無報告も安全性の証拠ではない。
診断停止で最後まで実行できなかった行は意味論PASSに数えず、値の結論は非race実行から取る。
既存のoracleや製品テストを抑制・変更していない。

## 残件と推薦への影響

- **今回の変換修正：推薦しない。** 禁止されたatomicity／orderingの喪失を確認していない。
  参照実装で出なかったことを、Wasmが要求する保証に読み替えない。
- **purge固有の保護前提：未確認。** 実guestで混在が使われるなら、単なる診断制約ではなく
  履歴の早すぎる回収という利用者不利益につながり得る。今回の結果で無害として閉じない。
  既存のリリース承認を変更したり、一般的な共有メモリ保証へ拡張したりしない。
- 実guestへの影響まで判断する必要がある場合、次はこの2アクセスとtask完了の順序だけを
  実guest上で観測する別作業になる。計測あり／なしの対照と、実際のhead遷移を使ったoracleが必要。
  macOS限定で**上限2時間の到達性・順序観測**が小さい次段階であり、実害の非存在の証明は終了条件にしない。
  修正が必要なら、guestのlock／task境界とGo loweringのどちらが所有元かを分けて再提案する。
  この作業は今回の承認には追加せず、Human判断なしに開始しない。

検査用script・fixtureと証拠のみを実験ブランチに保存した。runtime、guest、生成Go、公開API、
既存失敗oracle、main、tag、公開成果物には変更を加えていない。

## 成果物の検査

Python構文、JS構文、Go通常／raceビルド、入力hash、過去campaignの入力復元hash、
Wasm hexのhash、診断ログhash、64行の実行記録、文書参照を照合した。
`python3 scripts/verify.py check --scope docs`と`git diff --check`はPASS。
成果物の[hash一覧](purge-wasm-go-evidence/files.json)を保存する。
変更しない製品runtime全体の試験や独立再生成は再実施していない。
