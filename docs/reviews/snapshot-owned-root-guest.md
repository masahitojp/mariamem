# Snapshot所有権 — 実guest接続spike

2026-10-17。部品spikeの後、Humanが「制限事項で良い気もする」「spikeは進めて」と承認した限定接続。
製品への採用、検出契約の変更、main統合、リリースの承認ではない。

## Human Review — 製品化候補へ進む方針を確認済み

Humanは2026-10-17に「進める（製品化候補）。検出能力の差を限定契約として認める判断とUbuntu確認を採用条件に置く」とする整理を支持した。
この支持を、検出契約の変更自体やmain採用の承認には読み替えない。
次はUbuntuの限定確認をCIに提出し、その結果と契約文案を揃えて採用判断へ返す。

以下は方針確認時の推薦と根拠。Ubuntuの結果は未取得であり、提出をPASSと扱わない。

**判断依頼：所有権方式を、Ubuntu確認と契約文の確定を含む製品化候補として進めるか。私は進めることを推薦する。**
macOSの実MariaDBで、通常heapのSnapshot固定・取得に内容の再読み取りを不要にできた。
軽い準備を4子で再利用する全体は、直列572→364ms、4並列378→172ms（各中央値）。
SQL、世代間隔離、終了、Python共有hostと明示的な別hostへの転送を確認した。
利益はSnapshotだけでなく利用全体に出ており、子の起動を速くした結果とは区別できる。

**最も強い反論：取得前の内部byte破壊を取得時に検出する能力は減る。**
実guestのInnoDBページを1 byte壊した例では、所有権取得は通過し、後のSELECTが破損エラー1877で拒否された。
従来のstrict verifierは同じ破損を取得前に拒否する。この例で黙った値変更は起きなかったが、
全ファイルや他の破壊にもMariaDBの検出が効くという証拠ではない。
この差を限定された契約として認める判断と、未実施のUbuntu確認が、採用には必要。
今回の結果だけでmain採用やリリースへ進めない。

## 1. 元の問いと結論

問いは「保証を残したまま、毎回読み直す必要をなくせるか」。通常APIによる変更防止、
同一実体の受け渡し、親子隔離を支える構造は実guestに接続できた。
**任意の内部byte破壊の実行時検出まで同等、という答えではない。**

元storageと固定後readerが共通の`rootFileData`/`rootRead`を使う。
Snapshot専用descriptorへの内容再構成をなくし、writer停止後にsealして同じ実体を受け渡す。
通常heapは内容read/copy/hash/zero展開0。namespace、size、block範囲・参照・有効長、seal、
source/capture/guest identityは実行時にも確認する。現在のmetadata検査は**O(files + materialized blocks)**。
O(files)だけではなく、内容byte数の走査と区別する。

[部品spike](snapshot-owned-root-component.md)と[5条件/当初設計](snapshot-ownership-contracts.md)を継承。
これらの歴史的測定を今回の実guest測定に読み替えない。

## 2. 検出と防止：レビューのL1〜L3への回答

| 区分 | 現行の検出 | 候補の違いと残る保証 |
| --- | --- | --- |
| L1：pass2の転送先写像検査 | 元storage readerのdigestと、再構成後readerのdigestを照合する一方向の自己検査。外部の真値ではないが、実行ごとの具体的な誤写像を検出できる | 内容再構成そのものをなくす。共通reader、所有層の差分test、拒否oracle、実行時metadata検査へ役割を分ける。開発時testが全ての実行時故障を代替したとはしない |
| L2：freezeからOwnHeap内容検査まで | 先に得た期待digestと後の全量走査の間に生じた変更を検出する | 同じ実体のprivate bytesだけを直接壊した場合、metadataが同じなら受理する。ここは検出能力の差として残る |
| L3：取得後の内部byte破壊 | Forkごとに全量再検証しておらず、網羅的検出の契約は元からない | この検出を新たに約束しない。L2の差と混同しない |

「fail-closedを維持」は、未固定・別root・別source・別guest・metadata差し替え・放棄・再使用等の
**状態/構造の拒否に限定**する。内容破壊全般の拒否には拡張しない。
通常APIのpreventerが、ルールを破った内部変更のdetectorと同等になったとは記さない。
一方、再構成をなくすことで不要になった検査理由は、単に検査を省いた場合と区別する。

### L2の時間幅

以前の約193msは`snapshot_capture`全体であり、byte変更検出の窓の実測ではない。
各byteを前後の走査で読む時点に依存するため、freeze/Ownの間の空白時間だけでも定義できない。
**「ごく一部の数十ms」は未確認の推測として採用しない。**
今回の故障注入は`TakeRoot`成功後・`OwnRoot`直前・公開Snapshot取得完了前に限定した。
取得後に壊してL2を確認したことにはしていない。自然発生率の測定でもない。

### 契約案（まだ製品への変更決定ではない）

停止時点の内容を保持する同一実体を固定し、通常APIによる以後の変更を防ぐ。
Forkの変更は親・兄弟へ伝播しない。取得時に状態・構造・identityを検査する。
プロセス内でprivate bytesを直接破壊する故障の、全量走査による事後検出は約束しない。
明示的な別host転送や借用mappingからの所有取得では、copyと内容検査を継続する。

これは開発上の境界の記録。利用を禁じる位置づけでも、利用者に未確定な懸念を列挙する提案でもない。

## 3. 実guestの1 byte注入

[fixture](../../tests/gointegration/owned_root_corruption_spike_test.go)、[private注入helper](../../internal/prepared/root_corruption_spike.go)、
[overlay runner](../../benchmarks/spikes/ownedroot-guest/corruption.py)、
[正常結果](../../benchmarks/spikes/ownedroot-guest/evidence/corruption/healthy.json)、
[破損結果](../../benchmarks/spikes/ownedroot-guest/evidence/corruption/corrupt.json)。

- 同じSQL準備の正常/破損を別OSプロセスで実行。上限50秒、内部context35秒。
- InnoDBテーブルの既知payloadを`.ibd`から一意に同定し、16KiB page 3、file offset49373を117→116へ変更。
  header/キー/checksumのbyteは触らない。page type生値17855を記録。
- 実設定：`innodb_checksum_algorithm=full_crc32`、doublewrite=ON、file_per_table=ON、force_recovery=0、page_size=16384。
  `innodb_log_checksums`はSHOW結果になく、この変数やredoの保護状態を確認したとはしない。
- 正常：metadata受理、strict受理、子のSELECTで元の値。
- 破損：metadata受理、破壊前digestを使った既存`Heap.Verify`は拒否、子の起動は成功、
  対象SELECTは**Error1877 / table corrupted**。guest logにもpage3の破損を記録。誤った値の返却は未再現。

これはstrict検査の「即時拒否」が、今回のInnoDBページでは「対象を利用した時のエラー」に変わる証拠。
利用者の不利益は、準備段階では成功して後のテストSQLがエラーになること。
エラーがテスト途中まで遅れる点は残る。「MariaDBが検出するから同じ保証」にはならない。

MariaDBの[公式innochecksum説明](https://mariadb.com/docs/server/clients-and-utilities/administrative-tools/innochecksum)も
InnoDB tablespaceのpage単位のchecksumを説明しているが、これは全Snapshotファイルの保護ではない。
redo、system table、metadata、別のbyte位置・設定、checksumとデータが同時に変わる故障は今回対象外。
heap上であることは通常のファイル媒体破損をこの経路の前提から外すが、「全ての故障はソフトウェアだけ」
「L2の実害は全てエラーに限定」とは結論しない。MariaDB自身の検出器は現行にも存在する。

通常runtimeには注入hookを入れていない。`ownedroot_probe` build tagと保存した1箇所のoverlayだけで接続し、
contextに結びつけた1captureを対象とする。生成Goの手編集、global破損スイッチ、期待値の緩和はしていない。
probeのPASSは観測とoracleの成立であり、破損を受理して安全という意味ではない。

## 4. 5条件・所有境界の結果

| 条件/境界 | 結果 |
| --- | --- |
| strict oracleの棲み先 | 既存`TestHeapTargetCorruptionOracle`等を残し、prepared/snapshot/baseの全testをrace付きでPASS。新Rootの差し替え拒否と、直接bytes破壊ではstrictだけが拒否するtestを追加 |
| dirty/inherited/zero | unitで独立byte参照モデル、境界、穴、truncate/regrow、固定後writer拒否、COWを確認。実guestでSQLと派生baselineの親/兄弟隔離をPASS |
| 経路別ゼロ | 実guestの診断2回（直列/4並列）でfreeze/acquireのpayload read/copy/hash/zero=0。準備writeの正のcounterも確認。metadata走査は残る |
| mapped | 明示handoffで得たmapped子を変更→再Snapshot→孫/兄弟で確認。寿命切断に144,491,518 bytesをcopyし、source/target各144,786,482 bytes hash。ゼロを主張しない |
| handoff | 別binaryへのprivate path/FD転送、受信のstrict検査、cleanupをPython実guestでPASS。転送自体の出力/hashは残す |
| G0/G1/G2 | 今回は共通表現を固定するG1＋heap/zero統一のG2候補。G0単独の利益・以前の2pass案の利益とは合算しない。mapping境界のcopyは残る |
| HeapFile digest | 既存strict形式は変更せず必須。新Rootは別のprivateな型/入口。raw HeapからRootへの移入はprivate copy＋元digest検査を行う |
| metadata検査 | `Root.Check`とcapture bindingで実行時拒否。別source/root/guest、seal、inventory/size/block参照・有効長を確認。byte内容検査ではない |

実guestの診断counterはhelperが扱った論理byte数で、CPU命令数/bus trafficではない。
通常比較46回と診断4回を分け、counter有効時の数字を通常比較へ混ぜない。
全経路のcounterが一律ゼロとはしていない。mapped/転送を含む「読み直しゼロ」は不成立であり、不要でもある。

## 5. 利用全体の時間

Apple M1 / macOS27.0.1 arm64、Go1.26.8、CGO0。baseline/candidateを交互に同一harnessで実行。
移行/seed相当の準備、Snapshot、4子のSQL（commit/rollbackと隔離のassert）、Closeを含む。
Lightは1table/1row/1024B。10MiBは同じharnessのpayload指定。各試行は独立プロセス。

| 区分・各候補の回数 | Snapshot中央値：v0.5.1→候補 | 全体中央値：v0.5.1→候補 | 全体変化 |
| --- | ---: | ---: | ---: |
| Light直列・各10 | 204.8→2.9ms | 572.3→364.0ms | −36.4% |
| Light4並列・各10 | 205.4→2.5ms | 377.6→172.0ms | −54.5% |
| 10MiB直列・各3 | 222.5→4.1ms | 1614.4→1376.0ms | −14.8% |

同じtrial番号の23対すべてで全体が短縮。子loopのwall中央値は305.0→300.8ms、112.5→107.4ms、
699.4→689.7ms。**主な改善はSnapshot。Fork起動自体の大幅改善とは言わない。**
区間中央値を足して全体中央値と一致させない。並列の子の所要時間合計とwallも別物。

baseline並列は10回中2回で全体1163/1187ms。削除せず全データを保存した。
原因は未確認で、noiseとも候補がtailを解消したとも判定しない。候補の全体範囲は166〜191ms。
この2回を含む中央値だけでなく、[全試行/対ごとの差](../../benchmarks/spikes/ownedroot-guest/evidence/summary.json)も参照。
100MiB、大量table、長時間/多数世代の性能、Ubuntu性能は未測定。

累積Go allocation中央値はLight直列20.56→19.05MiB、並列20.61→19.00MiB、10MiBでは115.19→115.30MiB。
一律のメモリ改善とはしない。並列はbefore/afterのみで同時ピークを捕捉せず、RSS比較でもない。
全46試行でWasm mapping作成/解放各5、終了時のactive/reserved/RW/release_failureは0。

## 6. 入力同一性と生成の所有元

- main/比較baseline：`7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`。
  [v0.5.1 typed pin](../../release/baselines/v0.5.1.json)のsource_commitとtag_object_shaを`git_identity.py`で別々に検査。
- 部品起点：`39b394b29d82d6ec450ba4fed667e46bf3bd9aa7`。
- 最後の通常Go runtime変更：`5ca4f16964e415baa988d927ff87e64578ee359c`。
- 交互比較/独立再生成/Python：`11fa56bd8f7c7180299d3235b586a0bc18004768`。通常runtimeは5caと同一。
- mapped再Snapshot test追加：`7954d47151a37e18bd40f089fcfed22276202988`。
- 限定注入：初回観測`7994db2`、配置修正後を含む正確なsource_commitとoverlay SHAは[receipt](../../benchmarks/spikes/ownedroot-guest/evidence/corruption/receipt.json)。通常buildからprobeは除外。
- guest：MariaDB12.3.3、Wasm SHA256 `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
  既存CI artifactを固定記録と照合して再利用。guestの新規source buildではない。

変更所有元は`internal/prepared`、`internal/snapshot`、既存handwritten base/adapter。
`HANDWRITTEN_FILES`に既登録のbaseファイルを変更し、新Root型はgenerated tree外に置く。
`runtime_memfs.py`のpinned preimage、converter SHA/patch、guest、provenanceは変更なし。
`release/generated-go-inputs.json`への新たなinventory登録も不要だった（新型がtree外、既存ownerは登録済み）。
これらの費用が常に不要という意味ではなく、今回の配置で再pinが発生しなかったという結論。

正規`regenerate_release_guest.py`で独立出力を生成し、handwrittenを含む99fileのidentity一致を確認。
[生成proof](../../benchmarks/spikes/ownedroot-guest/evidence/canonical-regeneration.json)のsource_commitは再利用guestのsourceで、
変更したownerのsourceは[実行receipt](../../benchmarks/spikes/ownedroot-guest/evidence/regenerate-receipt.json)。混同しない。
ベンチbinaryにはbuildvcsを付け、revision/modified=falseを検査。同じharness observerを両方にoverlayした。

## 7. 検証・失敗・未完了

各実行SHA/引数/終了値は[receipt一式](../../benchmarks/spikes/ownedroot-guest/evidence)を正本とする。

| 確認 | 判定・範囲 |
| --- | --- |
| prepared/snapshot/base全unit・既存strict oracle・race | PASS。独立byteモデル3seed×500、拒否、境界、10世代実FD、mappingを含む。raceゼロを全体保証にしない |
| public lifecycle / 35 mutating children / fork-close / modified-child baseline | PASS。FD4→4、goroutine2→2を含むbounded acceptance |
| guest/host/control/public Go | PASS |
| Python共有host・別host handoff・fork-close | PASS、既存3test |
| mapped子からの再Snapshot | PASS、専用実guest test |
| canonical source/license/mirror | PASS、22testとgenerated source checker |
| 独立再生成 | PASS、99file一致 |
| 46通常＋4診断workflow | PASS、SQL/assert/cleanup込み |
| 故障注入 | 観測PASS：strict拒否/metadata受理/SELECT破損エラー。安全性同等のPASSではない |
| Ubuntu x86_64 | SKIP：今回未実行 |
| 最終Qualification・広いProduct Validation・ORM | SKIP：今回の限定spike外 |

最初のsandbox実行はlocalhost bind拒否でFAIL→許可された環境で再実行PASS。
派生baseline testは内容成立後、旧診断名が消えたことによるassertでFAIL→実際のfreeze/own区間に
診断を復元し、testは緩めずPASS。Python3.9で再生成はtar API不一致によりFAIL→3.14でPASS。
注入fixtureは最初に公開APIの引数不一致でbuild FAIL→fixtureを現行APIに合わせてPASS。
これらを破棄せず保存し、runtime意味論の失敗と混同しない。

残件：Ubuntu、採用時の契約文、製品化の差分整理、採用後の最終検証。
今回のmac結果は上記の利用条件に限る。追加の全面共有メモリ調査や任意破壊の完全証明を要求する結論ではない。

## 8. 再現・証拠

[再現README](../../benchmarks/spikes/ownedroot-guest/README.md)、
[check runner](../../benchmarks/spikes/ownedroot-guest/check.py)、
[交互比較runner](../../benchmarks/spikes/ownedroot-guest/measure.py)、
[証拠集計](../../benchmarks/spikes/ownedroot-guest/analyze.py)。
`files.json`は原本/保存後hashを記録し、個人path置換を明示する。全数値/失敗/外れ値を保持する。
通常runtimeにfault hookを残さず、探索branchから必要な最小差分を別途製品化する。

## 9. 方針確認後の製品化差分と採用条件

1. **Ubuntu条件**：新しい`owned-root-native.yml`で既存の所有層/strict oracle、Go SQL・隔離・終了競合、
   Python共有host・handoff・mapped再Snapshot、限定破損注入を同じ候補SHAで確認する。
   source/license確認を含む。性能再測定や全量QualificationはこのCIには含めない。
   CI artifactのsource_commitとstage receiptで判断し、未実行/失敗をPASSへ読み替えない。
2. **契約条件**：§2の契約案について、即時の内容破損拒否との差をHumanが受け入れる判断が必要。
   今回の「製品化候補として進める」支持は、この条件自体の受け入れとは別。
3. **採用時の最小差分**：通常runtimeのFileStore/Root/capture bindingと既存adapter、および独立byte参照・
   差し替え拒否・寿命/派生世代testを取り出す。実験履歴全体はmergeしない。
   strict Heap/転送検証、mapped寿命切断、生成所有元の分類を維持する。
4. **文書/診断の整合**：採用契約に合わせてSnapshotの「verified」の意味、開発用の内容検出境界、
   実際のfreeze/own診断を揃える。通常runtimeにfault hookを追加しない。
   unit/限定guest受け入れ、source/canonical identityの確認を差分へ対応させる。

Ubuntuへ出す変更はCI・検証helperの環境可搬化・判断記録だけ。通常Go runtimeはmacOS検証候補と同一。
公開API、guest/converter、生成物を変更せず、main統合やリリース準備を開始するものではない。
