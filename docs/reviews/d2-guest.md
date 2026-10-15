# D2を実guestへ接続した限定spike

2026-10-16。macOS arm64。依頼された実guest接続・小中規模の比較は完了。
製品採用、main統合、リリース準備は行っていない。

## Human Review

**今の判断は、D2の子起動の追加費用を限定して確認するかです。推薦は、採用を保留し、そこを次の確認対象として残すことです。**
実MariaDBで独立した子と派生Snapshotを作れましたが、「準備して2子でテストする時間」は
Eより小規模で約12%、中規模で約6%長く、各5組すべてで遅くなりました。
Snapshot単体はほぼ変わらず、主な追加時間は子の起動です。
速度改善を確認できた候補として採用する根拠はありません。

**最も強い反論は、準備hostの最大RSSが約134／131 MiB減り、D2をここで捨てると
この利益も失うことです。** このため方式を棄却せず、次に進むなら子起動の内訳だけを
確認することを勧めます。配置表の複製・転送・decode・guest起動を分け、追加時間が
試作の受け渡しに偏るか、D2のI/Oまで含むかを判断する範囲です。追加作業は未着手です。
既存の全量検査を減らして速度を出すことは、この推薦に含みません。

元の問いへの答えは「**実guestに接続でき、限定した所有・隔離の検証は通った。
期待したテスト全体の高速化は出ず、準備側のメモリには利益が出た**」です。
OS間の性能差への懸念は今回も未解決です。D2は共有mappingを使うため、OS非依存にはなっていません。

## 範囲と比較

[D1/D2部品spike](d-snapshot-components.md)の後、Humanが実guestへの接続を承認。
MariaDB 12.3.3の既存Generated Goへ、実験専用overlayを適用した。
guest Wasm、converter、正式な生成物、公開APIの製品実装は変更していない。
overlayは試作のテンプレートから生成し、測定後はすべて元に戻した。

対照は以前の**E直接引渡し候補**。現行mainそのものとの比較ではない。
同じhost binary・同じPython harnessで環境変数を切り替えた。
EはFreshファイルを共有mappingへ置き、停止後に同じ実体を取得する。子は従来のprivate mapping。
D2はFreshも子も16 KiB blockを4 MiB segmentへ置き、配置表で論理fileを表現する。
親segmentはreadonly、子の変更はその子専用segmentへ置く。
新しく書かれていない論理zero領域を実体化しない。

通常例は `start → migration/seed → snapshot → fork/CRUD/close を2回 → baseline.close`。
users/ordersの2表、unique index・外部キーを使い、次を同じSQLで確認した。

- 小規模：各100行、users payload 256 bytes。Snapshot論理file合計は約138.24 MiB。
- 中規模：各10,000行、users payload 1,024 bytes。論理file合計は約158.58 MiB。
- 第1子はinsert/commit、第2子はupdate/commit、delete/rollback、delete/commit。
  第1子の変更が第2子に現れないこと、両子終了後の基準全量hash不変も確認。
- 各条件5組、E/D2の実行順を巡ごとに反転。計20 workflow、40子。
  pilot・既存Export比較・資源計測・境界検証は主計測と分離。
- 全体時間にStart、準備、Snapshot、2子の接続/SQL/切断/Close、基準Closeを含む。
  最後の追加全量auditだけ計時から除く。Snapshot取得に必要な検査は含む。
- 元内容hash、Go側受渡し後の全論理hash、Python取得時の全論理hashの3回を維持。
  zero領域もhash対象。Forkごとの全hashは、従来の所有契約どおり行わない。

## 速度：利益は確認できなかった

中央値、ms。各区間の中央値の和は全体の中央値にはならない。
全値は[plain/raw.json](d2-guest-evidence/plain/raw.json)、
対応差と範囲は[summary.json](d2-guest-evidence/summary.json)。

| 区間 | 小 E | 小 D2 | 中 E | 中 D2 |
| --- | ---: | ---: | ---: | ---: |
| 準備DBのStart | 46.53 | 44.70 | 45.83 | 45.03 |
| migration/seed | 18.36 | 17.35 | 786.54 | 779.49 |
| Snapshot取得 | 232.00 | 229.56 | 268.51 | 272.47 |
| 子の起動：1子あたり | 51.13 | 78.54 | 51.32 | 84.57 |
| CRUD：1子あたり | 2.82 | 2.80 | 19.67 | 19.76 |
| Close：1子あたり | 4.49 | 6.53 | 4.66 | 6.61 |
| 2子の全処理 | 126.21 | 186.17 | 159.51 | 231.40 |
| **テスト全体** | **430.35** | **483.79** | **1,266.82** | **1,337.96** |

全体の中央値は小+53.44 ms（+12.42%）、中+71.14 ms（+5.62%）。
同じ巡の差は小+43.54〜57.04 ms、中+37.10〜92.28 ms。D2が速かった組は両規模0/5。
少数試行・単一環境だが、今回は「全体の差がばらつきに埋もれて分からない」という結果ではない。
この条件のD2候補は一貫して遅い。他環境・大規模・多数子への一般化はしない。

D2のfreeze/moveは小0.82 ms、中2.04 ms。Eの8.47／22.98 msより短い。
しかしテスト全体の利益にはならなかった。D2も元hash約62／72 ms、受渡し後hash約62／77 msが残り、
Python取得、配置表、終了処理等も含む。これらを個別に十分分解した計測ではない。
子起動には約255／305 KiBの配置表のclone、JSON転送・decode、新しいreaderとguest起動が入る。
**配置表が遅延の原因だと確定したわけではない。** 現時点で確定したのは、追加時間が現れる区間まで。

部品spikeの64 MiB密データでの約13%短縮は、D1との比較だった。
今回は実DB、もともと転送を省いているEとの比較であり、前回結果と矛盾しない。

## メモリと保持量：得られた利益と代償

別campaign各3組。runtime.MemStatsとprocess自身のgetrusageを終了時に取得。
macOSのMaxrss bytesをMiBへ換算。主計測へ混ぜない。
[resources/raw.json](d2-guest-evidence/resources/raw.json)。

| 指標（中央値） | 小 E | 小 D2 | 中 E | 中 D2 |
| --- | ---: | ---: | ---: | ---: |
| 準備host最大RSS MiB | 251.98 | 117.77 | 280.08 | 148.84 |
| 子host最大RSS MiB | 120.85 | 119.98 | 122.94 | 121.95 |
| 準備host Go累積割当 MiB | 1.16 | 2.74 | 22.92 | 25.37 |
| 子host Go累積割当 MiB | 12.86 | 2.85 | 12.89 | 2.99 |

準備host最大RSSには大きな利益、子の最大RSSには大きな差なし。
子Go割当は減ったが、mmap領域はGo heapの外なので総メモリ削減と同一視しない。
Python owner、OS cache、共有pageの重複を調整したシステム全体のメモリは未測定。
資源計測つき全体時間も小437.18→487.70 ms、中1,268.78→1,341.30 msで、各0/3組の改善。

D2の初回取得は小2 segment／約5.17 MiB、中8 segment／約29.38 MiB。
論理file合計とは区別する。OSの実disk allocationを測った値ではない。
Snapshot payload転送は0だが、SQL write・部分block copy・hash用read・OS内部copyまで0ではない。
各子のslot確保は約2.55 MiB、親からの部分copyは約48.05 KiB。EのOS CoWコピー量は未計測。
EのD用counterが0なのは未使用であり、「Eは確保もコピーもしない」の証拠ではない。

試作はslot再利用・不要segmentの選別をしない。削除済み一時fileのslotもpool終了まで保持し、
派生基準は親segmentすべてをpinする。世代を重ねた保持量・FD数の上限処理は製品化の残件。
4 MiB segment・16 KiB blockは試作値で、最適値を選んだものではない。

## 正しさと所有境界

| 確認 | 判定・証拠 |
| --- | --- |
| 実guestの既存ExportとD2対象file・内容の全一致 | PASS、小規模の分離audit。[結果](d2-guest-evidence/audit/raw.json)。全規模への証明ではない |
| 小中のSQL、commit/rollback、兄弟隔離、基準hash不変 | PASS、主計測20 workflowと資源計測12 workflowの全run |
| active transaction拒否後、元DBの継続使用 | PASS、[D2境界](d2-guest-evidence/boundaries-d2/result.json) |
| 親Close後も2子が生存・隔離 | PASS、同上。2子同時生存の機能確認で、並列性能測定ではない |
| 子から派生Snapshot、そこから第3子、兄弟は元内容維持 | PASS、同上。[handoff](d2-guest-evidence/boundaries-d2/handoffs.json)は親2＋新1 segment、親内容をcopyせず保持 |
| `snapshot_to`従来形式の取得・Fork | PASS、D2でも保存は既存Exportへfallback。保存形式は変更なし |
| 移管前・移管後・publish後の失敗 | PASS、元DB終了・成功Snapshotなし・一時資源回収。拒否理由もassert |
| 元hash固定後の破損／Python取得前の破損 | PASS、`D2 target hash mismatch`／`D2 content mismatch`をそれぞれ確認 |
| guest identity・配置範囲・inventory・親不足・segment size・内容の拒否 | PASS、[receiver fixture](d2-guest-evidence/receiver-checks.json) |
| block EOF、shrink/regrow、部分write、既存FS/Owned境界 | PASS、[unit記録](d2-guest-evidence/unit.txt)。試作D2専用freeze/restore/破損fixtureも含む |
| overlayの独立再適用・全postimage一致・canonicalへの復元 | PASS、[記録](d2-guest-evidence/overlay-replay.json)。独立binary再ビルドの主張ではない |
| Ubuntu x86_64 | SKIP、今回利用可能なnative対象環境なし |
| 公開Go APIへのD2統合、長い派生世代、大規模・高並列・強制終了、全面Qualification | 今回の限定spikeの対象外、未実施 |

一時D2形式はPython ownerの内部拡張から利用する。共有対象のwriter mapping/FDを停止後に閉じ、
Pythonがreadonly FDを取得・unlinkし、完全検証してから返す。
子の起動と派生Snapshot中は独立したFD保持権をpinする。Fork時の内容再hash省略は既存契約と同じ。
取得後の媒体破損再検出、同一UIDの任意操作に対する保護を新たに保証しない。
従来形式から読み込んだ基準は、派生時も従来Export経路を使う。全面的な形式変換実装ではない。

### 最初に見つけた検査の欠陥

初回 `TestD2FaultHash` はFAIL。受渡し後の期待値照合にreadonly MAP_PRIVATEを使う試作で、
注入したfile byte変更（120→135）が既に作ったmappingには反映せず120のまま読めた。
その結果、古い内容同士のhash一致で破損を見逃した。
[初回失敗](d2-guest-evidence/first-unit-failure.txt)と[観測](d2-guest-evidence/first-validator-observation.txt)。
これはローカルmacOSの観測であり、OS全般のmmap仕様の断定ではない。

受渡し後は保持したreadonly FDのReadAt、Python取得はpreadから検査するよう修正。
同じ破損oracleはPASSし、実guestでも期待した拒否理由を確認した。期待hashは置換していない。
既存製品の検査を書き換えた修正ではなく、今回の試作内の欠陥と修正である。

## 入力・再現・保存

- mainのruntime基点：`a8137b8b444f86068d3128a291e3a848adfdfd56`。
- 実験branch開始：`f0dac5fb1fa03ad5ea991ecb52e2bfd89161cebb`（D1/D2部品報告）。
- E対照の由来：`3ce25c29ebceb2bdfb6b430391f400ad3d8d90e0`。
  block/接続の由来：`c1875fa9e68d8588514cc1380d0ed3dc7d64409f`。
- `git_identity.py inspect`でcommit型を確認してからbuild/計測。
  **計測対象は開始commit＋記録済みoverlay**。開始commitそのままを測ったとはしない。
- guest `12.3.3-MariaDB-embedded`、Wasm SHA256
  `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- host SHA256 `7ddff2e9d6654dc09f13048045ef30f096cb929dbf89fc2d48b411c27dacca9f`。
- macOS 27.0.1 arm64、Go1.26.8、Python3.9.6、PyMySQL1.2.3。
  [環境](d2-guest-evidence/environment.json)、[build入力・overlay hash](d2-guest-evidence/build-input.json)、
  [最終harness hash](d2-guest-evidence/final-harness-sha256.json)。
  run.pyとd2_python.pyは計測時build入力のhashと一致。後から境界assert・集計・保存scriptを補強した。

[再現用コード](../../benchmarks/spikes/d2-guest/README.md)はexperiment branchだけに保存。
生成コードへ製品変更を持ち込まず、overlayの適用前後hashを照合して復元する。
[証拠checksum](d2-guest-evidence/checksums.json)。binary/cacheは再生成可能なため保持しない。
mainの既存ユーザー変更（project-statusと設計・投資判断資料2件）は未変更のまま残した。

製品化には正式所有元への実装、Go/Python双方の所有境界、資源回収・容量上限、
対応OSの検証が必要。今回のPASSはその代わりではない。
追加したPython scriptの構文、資料リンク、差分整形、追加ファイル集合への公開source検査はPASS。
全体の公開source検査は、基点から存在するstartup-tail報告の`measurement.log`で停止する。
今回そのguardや既存資料は変更せず、追加集合の検査と区別した。リリース検証PASSとは扱わない。

次の作業を自動開始せず、この結果でHuman Reviewへ戻す。
