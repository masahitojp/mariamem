# D heap Snapshot＋Python共有host：実装とHuman Review

2026-10-17更新。検証元は`experiment/d-heap-shared-host`。以下のHuman Reviewは採用前の判断資料。

## Human決定：main採用

2026-10-17、Humanは候補`f55bd3a91073e9f80b8a816055acf0983b8b2e79`のmain採用を承認した。
両OSの関連検証、今回の利用条件での利益、明示した契約変更を根拠とする。
未解明の遅い資源計測1試行も判断材料に含めた上で、採用後の最終リリース検証へ引き継ぐ。
共有hostの故障範囲と公開保存／load APIの廃止も、この判断の対象。
採用はリリース承認ではなく、今回リリース準備・最終Qualification・公開は開始しない。

採用時に変更するのは承認記録と現在の製品契約の状態だけで、runtime・生成物・toolchain・
既存oracleは検証済み候補と同一。macOSの実装・計測入力`a6df1c8`とUbuntu入力`4282cba`を
新しい採用commitの検証結果として付け替えない。

最終リリース検証へ渡す確認点は、準備→Snapshot→子→全Closeの全体時間と各区間、
通常計測と資源計測の区別、遅い試行の頻度・区間、両OSでのSQL／隔離／回収。
既存の生データを対照として使い、原因未確定のまま「解消済み」「単なるばらつき」としない。
新たなcorrectness欠陥が見つかれば、その影響と修正範囲を別途判断する。

## Human Review

**今回Humanに判断してほしいのは、この候補をmainへ採用するか。推薦は採用。**
承認済みの実装・限定検証を完了した。macOS arm64に加え、Ubuntu x86_64でも所有・I/O・
SQL・隔離・終了・consumer検証がPASSした。通常のライブラリ利用と独立DBを維持し、
Snapshotの保存・再読込を取り除ける。macOSの限定比較ではSnapshotが約45〜49%短縮し、
準備から全Closeまでは小規模30.8%・中規模6.5%短縮した。Ubuntuの速度は測っていない。

**最も強い反論は、host crashで同じ準備系統の基準と子をまとめて失う点。**
従来は子のhostが別で基準はPython側に残った。host kill試験でも、同じ系統は失効し、
別startのDBは継続した。再準備を許容するテスト用DBとして、この故障範囲は妥当と評価する。
通常SQLエラー・子のClose・個別要求timeoutは、使用中の系統全体のkillへ拡大しない。
子単位のprocess障害隔離が必要な利用には、この候補を推薦しない。

前回の「UbuntuもPASSした条件で採用」という推薦条件が、
[完了したCI](https://github.com/masahitojp/mariamem/actions/runs/38908979283/job/116999692620)で
満たされた。条件を緩めたものではない。採用と後日のリリース承認は別。
最終Release Qualification／重いProduct Validationは実施していない。
下記の未実行probeと未解明の遅い試行は、今回PASSの意味に含めず残す。

## 入力と変更範囲

| 項目 | identity／扱い |
| --- | --- |
| main baseline | `a8137b8b444f86068d3128a291e3a848adfdfd56` |
| 最終実装・計測入力 | `a6df1c8a396a7b175b634c51295acda724c57444`。後続は資料と証拠の保存 |
| Ubuntu CI入力 | `4282cba73f12c772942b72c2f020b3ec1228be11`。上記との差は資料・証拠のみでruntime差分なし。source commit型もCIで確認 |
| 初回実装保存 | `884f692a3c45de137d5cd6a0be66523df9d0ece1` |
| guest | MariaDB12.3.3、Wasm `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。変更なし |
| Generated Go provenance | `7c7ad7b5a14b55d3d63cb9bc2484e7c93e99860f0a1b0731104d01f8ecc94589` |
| converter | goccy `730057c146463f663e8774587bc96fb2bea91af8`＋現行13パッチ。変更なし |
| toolchain | Go1.26.8、Python3.14.8。既存固定WASIX／LLVM23.1.0／Binaryen133 |

[承認済み設計と保存廃止の範囲変更](d-heap-productization-design.md)に基づく。
過去の[Python試作](https://github.com/masahitojp/mariamem/blob/6988fa575d025dbddd99a53220a3aa5261c32268/docs/reviews/python-heap-snapshot.md)と
[C対D比較](https://github.com/masahitojp/mariamem/blob/c129476de5cf41f74abc387274fe0e28034d5fda/docs/reviews/cd-heap-snapshot.md)は
設計根拠。実験overlay／実験registryを一括取り込みしていない。
mainの未commitのproject-statusと設計・投資資料4件は保持し、専用worktreeで作業した。

- `snapshot()`→`fork()`、消費型Snapshot、busy／transaction拒否時の元DB保持、親・兄弟の隔離を維持。
- Human指定でPythonの`db.snapshot(path)`、`snapshot_to`、`load_snapshot`、`Snapshot.open(path)`、path-based startと、GoのDestination／LoadSnapshotを削除。保存済みartifactの互換性は提供せず、migration／seedで基準を作る。
- Pythonは独立startごとに自動管理hostを1つ作り、基準・子・派生基準が共有。MariaDB実行・SQL endpoint・16接続上限はDB別。Goは呼出し元process内の実行を維持。
- 子は変更blockだけ私有化。通常Snapshotはpayload一時fileを作らない。log・管理directory・socket・linear-memory mmapは引き続き使用する。
- 明示的に異なる開発用host binaryへForkする場合だけ、privateな一時handoffを使用。両binaryはprotocol2と同guest identityが必要。公開の保存APIではない。
- xdist worker間の共有daemon、接続上限調整、任意の非協調guestの個別強制停止は追加していない。

## 所有・生成・失敗oracle

`internal/prepared/heap.go`が不変16 KiB blockとinventoryを所有し、mutable sliceを公開しない。
MemFSのlock／metadata／dirty blockは子ごとに持つ。縮小後の再拡張で切り捨てた内容を
再表示しない。Allocateは論理サイズの拡張で、物理予約の保証ではない。
全guest worker終了後にFreezeし、元・固定target・所有取得の3回の全内容走査を維持。
暗黙のゼロもhash対象。Forkは同じbackingの構造・寿命・identityを確認して開始する。
協調終了を完了したdatadirを固定するため、通常経路ではguest内のsnapshot-outへのコピーと
host側のfile exportを呼ばない。実行中のthread／lock／connectionを保存する意味は追加しない。

| 保証 | 今回の検査先 |
| --- | --- |
| freeze失敗・受理後の消費状態 | `base/heap_snapshot_test.go`、root `mariamem_test.go` |
| target破損拒否 | target blockを変更し、元digestを保持するoracleで固定後Verifyが失敗 |
| owner取得時の破損拒否 | `internal/snapshot/heap_test.go`。意図的な移譲規約違反によるbyte変更を拒否 |
| guest identity拒否 | Heapと既存private file/importの検査を維持 |
| 親・兄弟・派生の独立性 | block境界・sparse・shrink/regrow・並行read/write・SQL変異・10世代 |
| 所有終了 | Capture移譲後／Closed ownerのweak reference、100 Fork後のhost FD／directory、最終reap |
| 保存入力の検査 | 公開入口を廃止。private handoffの独立copy／期待hash／identity検査は維持 |

生成物は手編集していない。`runtime_memfs.py`が固定preimage hashを検査し、MemFSを手書き
所有元へ移す。`HANDWRITTEN_FILES`にblock storage／テストを登録した。生成差分は
`base.go`、`relative.go`、`prepared_files.go`のみ。MariaDBの生成関数・データ・converterパッチは同じ。
license continuityとPython mirrorも対応させた。

正式guest buildの独立2回が採用Wasm／linked hashに一致。古いCI guestは入力hash不一致で
拒否し、host生成へ使わなかった。独立translationからcanonical sourceも一致し、最終所有元
更新後はそのraw candidateからinstallerを再実行して全ファイルを照合した。

```sh
python3 scripts/build_generated_guest.py --repetitions 2
python3 scripts/regenerate_release_guest.py --guest-dir build/generated-release --output ../temp/regeneration-2
python3 scripts/generate_runtime.py --source-module ../temp/regeneration-2/candidate/module --output ../temp/installed-final2
python3 scripts/verify.py check
python3 scripts/verify.py integration
```

guest buildは固定toolchainのcontainerで実行。
[build記録](d-heap-shared-host-evidence/guest-build.json)、
[生成差分](d-heap-shared-host-evidence/generation-delta.json)、
[独立installer inventory](d-heap-shared-host-evidence/final-independent-installation.json)を参照。
guest build receiptのsource_commitは変更のないguest入力を持つbaselineで、最終Release Qualificationではない。

## 検証と完了条件

| 設計§6 | 判定 | 証拠／範囲 |
| --- | --- | --- |
| 所有とI/O | PASS・両native | 3 seed×600操作の参照比較、block境界、穴、zero length、shrink/regrow、Allocate、rename/unlinkとopen handle、並行read/write、破損／identity oracle |
| 制御と失敗 | PASS・両native | out-of-order、個別cancel、遅延DB／Snapshot回収、未返却子、EOF／invalid protocol、実host kill、別DB待機中のClose、Fork／Close競合、最終reap |
| API・consumer | PASS・両native | 指定した削除、option継承、status／connection_info／id／capabilities／diagnostics／logs、起動エラーcode／stage／closed／cause、異binary、外部Go／installed Python／2worker |
| 規模・資源 | PASS・記載範囲 | 小・中、100 MiB／16 Forkの限定比較はmacOS。4並列、10世代、同Session100 Forkは両native。host FD／directory増加なし。weak referenceで到達性を確認 |
| 正式生成 | PASS | 固定guest独立2 build、独立translation／最終installer、generated source／license／mirror |
| canonical check／integration | PASS・macOS | [check](d-heap-shared-host-evidence/check-frozen.txt)：Python610成功・23 SKIP、Go test／vet。[integration](d-heap-shared-host-evidence/integration-frozen.txt)：Python17成功、Snapshot33項目、Go／memory境界 |
| 外部consumer・ORM | PASS・macOS | [ガイド3件](d-heap-shared-host-evidence/guides-consumer-frozen.txt)、Go module実内容一致、installed consumer9件、fixture serial／2worker／migration／失敗cleanup、SQLAlchemy start／fork各11件 |
| 正式候補の利益 | PASS・macOS限定 | 全54試行のSQL／隔離／回収assert成功。各scaleで6通常対・3資源対。下表の範囲で改善 |
| Ubuntu24.04 x86_64 | PASS・限定検証 | [receipt／SKIP内訳](d-heap-shared-host-evidence/ubuntu/receipt.json)。source／license／mirror22成功、Go test／vet、Python607成功・26 SKIP・12 subtests。integration17成功・Snapshot33項目、installed consumer9件、fixture audit、SQLAlchemy start／fork各11件、ガイド3件。全workflow step成功 |
| 最終Qualification／重いProduct Validation | NOT RUN | 今回の範囲外 |

macOSの23 SKIPは通常checkがreal-host等の専用条件を要求するため。Ubuntuも同じ23件に加え、
固定ソースarchiveを取得しないためnative認証ソース比較3 modeがSKIPになった。
うちreal-host 20件はintegration17件とガイド3件で別実行して成功。
残る開発専用経路probe・型比較probe・強制query-timeout診断の3件は今回のUbuntu CIでは
実行していない。強制停止はこの設計の完了条件外であり、通常Closeとは別の診断。
認証ソース比較を含むSKIP6件をPASSへ読み替えない。CIのcheckは`-q`で個別SKIP理由を
保存していないため、この内訳は固定ソースの条件とworkflow入力に基づく対応づけ。
意図的なassertion失敗1件・fixture setup error1件はcleanup試験の期待結果。
初回checkで起動診断4件が失敗したため、code／stage／cause／終了code／stderrを保持するよう修正。
protocolの期待値だけを2へ更新した。追加待機fixtureの二重Closeも修正して再実行した。
起動失敗のclosedフラグと基準継続も確認。
[検証履歴](d-heap-shared-host-evidence/verification.json)へ失敗と修正を分けて残す。

## 最終候補対mainの限定比較

通常計測の中央値、ms。各scaleで順序を交替した6対。子起動は全子サンプルの中央値。

| fixture | 準備〜全Close：main→候補 | 全体短縮 | Snapshot：main→候補 | 子起動：main→候補 |
| --- | ---: | ---: | ---: | ---: |
| 小・子2個 | 619.15 → 428.22 | 30.8% | 373.89 → 189.98 | 51.31 → 44.23 |
| 中・子2個 | 3527.76 → 3297.33 | 6.5% | 407.92 → 219.34 | 51.69 → 43.44 |
| 100 MiB・子16個 | 32963.77 → 32433.04 | 1.6% | 749.33 → 410.95 | 53.09 → 44.38 |

Snapshot自体は約45〜49%短縮。通常計測では全18対で候補の全体時間が短かった。
大規模は約30秒のseed投入が支配的で、Snapshotの約338 ms短縮が全体へ効く割合は小さい。
これはmigrationを高速化した成果ではなく、固定と再利用の費用を減らした成果。
子起動の差は約7〜9 msで、MariaDB起動そのものを省いたものではない。

別の資源計測3対での、生存host群の合計RSSの観測最大（3試行の最大）、MiB：

| fixture | main | 候補 |
| --- | ---: | ---: |
| 小 | 528.52 | 123.95 |
| 中 | 606.80 | 164.73 |
| 100 MiB | 1122.17 | 511.95 |

**資源計測の小規模候補には1540.44 msの全体試行が1件ある。** 他の2件は431.47／430.59 ms、
mainは614.67／620.37／617.82 ms。その遅い試行はprepare/start 891.08 ms、seed 284.88 ms、
Snapshot 223.37 ms。原因は切り分けておらず、候補の影響とも単なるばらつきとも断定しない。
通常計測6対の利益・全資源試行でのSnapshot短縮・中大規模の資源試行での全体短縮を根拠に
推薦するが、「常に全体が速い」「tailがなくなった」とは推薦しない。
以前の直接コピー候補での悪化原因を解明したとも扱わない。

[集計](d-heap-shared-host-evidence/comparison/summary.json)、
[全入力identity](d-heap-shared-host-evidence/comparison/inputs.json)、
[全試行](d-heap-shared-host-evidence/comparison)を保存した。

[harness](../../benchmarks/sharedhost/README.md)はfresh Python processで、準備1回→Snapshot→
子2個（大規模16個）→全Closeを測る。2表・unique／FK・seed、子のcommit／rollback、
exact seed bytes、兄弟隔離、host／scratch回収をassertする。100 MiBはpayload量であり、
index・orders・DB管理fileを含む総量ではない。以前の1表Go測定やPython試作と数値を混ぜない。

通常・資源計測は別試行。資源計測RSSはpsで観測した、生存host群の合計の最大値。
各ps取得後に25 ms待つ（実際の間隔はps実行時間も含む）。
厳密なhigh-water markやGo到達可能heapではない。Python自身・filesystem page cache全体を
含む総メモリでもない。probe込みwall timeは通常計測の中央値に混ぜず、外れ値も保存する。

先行計測は`54fe1ee`入力で完走した。その後の起動失敗フラグ1行補正を含め、最終候補
`a6df1c8`で規定回数を取り直した。先行結果も別に保存し、良い結果だけを採らない。

## 後続と証拠の扱い

Ubuntu nativeの所有・I/O・Go／Python／wheel／ORMは今回のCIで確認済み。
今回の限定比較を全workloadやUbuntuの速度保証には使わない。
接続数調整、さらにhash走査を減らす最適化、強制停止再設計は今回追加していない。

CI結果の取得後は資料・証拠だけを更新した。CI対象SHAを新しい資料commitへ付け替えず、
[run／step結果](d-heap-shared-host-evidence/ubuntu/run.json)、各検証ログと元／公開hashを
[receipt](d-heap-shared-host-evidence/ubuntu/receipt.json)に保存した。
資料だけの保存commitでは`[skip ci]`を指定し、変更していないruntimeのCIを再実行しない。
main採用の承認は冒頭の追記に記録した。Release READYとは判定しない。

既存Ubuntu証拠の`.log`名は公開source guardに反するため`.txt`へ変更し、integration証拠の
CI絶対path1箇所をrepository相対pathへ正規化した。
[元／公開hashと変換理由](d-heap-shared-host-evidence/public-evidence-rename.json)を保存。
元bytesはbaseline commitに残る。guardを緩めて通したものではない。
今回の保存用ログはlocal pathと行末空白を正規化し、元／保存hashをevidence-ledgerへ残した。
build・download・venv・cloneは再作成可能な領域として扱い、compactな証拠と入力identityを保存する。
