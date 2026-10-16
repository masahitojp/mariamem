# Pythonから同一host内のD基準を利用する限定spike

2026-10-16。macOS arm64。実guestの小・中規模、準備1回・子2個、所有と終了の限定検証。

## Human Review

**今の判断は、「一つの準備系統を一つの自動管理hostに置くD方式」をPythonの製品化設計の前提候補にするかです。推薦は進めることです。** 既存の`start → snapshot → fork`の使い方で、テスト全体は現行Pythonより小規模31.3%、中規模13.5%短くなりました。同じhostにまとめても従来ファイル方式を使う対照より31.1%／12.1%短く、hostを減らしただけの成果ではありません。隔離・通常Close・派生Snapshot・既存fixtureの限定検証も通過しました。

**最も強い反論は、同じhostが停止するとその準備系統の全DBとSnapshotを失うことです。** 実際に停止させ、待機中要求のエラー化、子と基準の利用不能、別`start()`の継続を確認しました。通常のSQLエラーや一つのDBのCloseでは兄弟は止まりません。この共有する障害範囲を明示して設計を進める価値がある、と判断します。host故障率や任意のguest障害を測った結論ではありません。現在の「DBごとに別host」という分離も必要なら、この方式の採用条件が変わります。

承認されたspikeは完了。**試作の製品採用、公開API変更、main統合、リリースは未実施**です。次の実装を自動開始せず、ここでHuman Reviewへ戻ります。

## pgmemの裏取りと、今回の対応

Human指定の短縮SHA `a61005d`をGitHub commit APIで`a61005d37d01e6671f814fe8ca828222e8147df4`へ解決し、同commitのソースを確認しました。pgmem自体のビルドや速度比較はしていません。[取得先・ファイルSHA256](python-heap-snapshot-evidence/pgmem-inputs.json)。

| 論点 | 固定commitで確認した実装 | mariamem試作との対応 |
| --- | --- | --- |
| Pythonの開始単位 | `start()`でPopenを1回。返すPgmemはhostとdefault templateを持つ。[client L250](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/_client.py#L250) | `mariamem.start()`ごとにhost1個。戻り値は従来どおりDB |
| 追加DB・Fork | `start_server()`/`Snapshot.fork()`は同じclientの制御要求。controllerがGo APIを呼び、mapにserverを保持。[client L62](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/_client.py#L62)、[controller L367](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/cmd/pgmem/control.go#L367) | 同じhostがGoのSnapshot/Forkを呼ぶ。子ごとに独立したMariaDB runtime/SQL endpoint |
| SQL backendの「process」 | host.ClusterのStart/spawnはProcessを作ってExecを呼び、engineのExecはgoroutineでguest instanceを実行。[host L129](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/host/cluster.go#L129)、[engine L100](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/engine/cluster.go#L100) | MariaDB側の既存runtime/worker/session実装は維持。PostgreSQLのbackend実装を移植しない |
| 内容共有 | Snapshot.Forkは`sn.fs.Clone()`を使い、VFS Cloneはmetadataを複製してfile dataを共有、書込時に私有化。[Snapshot L73](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/snapshot.go#L73)、[VFS L1612](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/vfs/vfs.go#L1612) | Goメモリを同hostに置く考え方を使用。分離単位は既存比較で有力だったDの16 KiB block |
| pytest | sessionのprocess/server/SnapshotからfunctionのForkを生成。[fixture L29](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/pytest_plugin.py#L29) | mariamemの既存session Snapshot/function Fork fixture形で2テストを実行 |
| host終了 | reader EOFで全pending waiterを起こし、要求側がServerExited。この経路に自動再起動/状態復旧なし。[client L91](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/_client.py#L91) | host停止は関連handleの失効として返す。自動復旧なし |

従って「接続やForkごとにOS hostを起動するpgmem」という説明はこのcommitには当てはまりません。一方、pgmemのguest trapはengine内でprocess終了として処理する経路もあります。**hostプロセス全体の停止と、通常のSQLエラー・個別guest終了は別の事象**です。「hostが死んだらそこまで」は上記の確認済み経路の要約であり、作者の一般的な設計宣言として引用しません。

mariamemはSnapshot成功で元DBを消費する契約を維持します。pgmemのSnapshot後に元serverを再起動する実装や、公開Pgmem管理オブジェクト、class/shared/live fixtureを今回持ち込みません。

## 構成と比較条件

| 項目 | 現行Python（control） | 同一host＋従来file（file） | 同一host＋D heap（heap） |
| --- | --- | --- | --- |
| host | 準備DB/子DBごと | 一つの準備系統で1個 | 同左 |
| 基準の所有 | Pythonが検証済みFDを保持 | host内Goが従来の検証済みFDを保持 | host内Goが不変heap blockを保持 |
| 子へ渡すもの | FDと配置記述 | 同hostの所有handle | 同hostのblock参照 |
| Snapshot payload一時file | 作成後unlinkしてFD保持 | 従来ファイル経路 | 作らない |
| 内容検査 | 元・受渡し後・所有取得の3回 | 同じ目的の3回をGoで実施 | 3回の全論理内容走査。ゼロも検査 |
| 子の実行 | 独立runtime、別SQL endpoint | 同じ契約 | 同じ契約 |

`file`対照は純粋なOSプロセス生成だけの比較ではありません。所有と最終検査をPythonからGoへ移し、制御処理も変えています。`heap`と`file`は同じadapter/controllerです。従来hostも同じ固定ソースからビルドし、資源報告hookは通常計測で無効です。

同一host化は、マシン全体やPython全体で一つにまとめる意味ではありません。独立した`start()`は別hostです。成功Snapshotがsource DB handleを消費してもhostは基準/子を保持し、最後のhandleのCloseで終了・waitします。利用者によるdaemon管理や新たな管理オブジェクトは不要です。prototypeのhandle registryは制御要求を直列化し、SQLは各DBのendpointへ直接届きます。

今回のPython adapterは実験ディレクトリ内から差し替えています。公開packageの実装は編集せず、全部のAPIを実装したdrop-in候補とは呼びません。公開呼出しの形を保った限定経路の実証です。[adapter](../../benchmarks/spikes/python-heap-snapshot/adapter.py)、[controller](../../benchmarks/spikes/python-heap-snapshot/broker/main.go)。

## 時間の結果

macOS27.0.1 arm64、Go1.26.8、Python3.9.6、PyMySQL1.2.3、guest MariaDB12.3.3。users/orders各100行・payload256 bytes、または各10,000行・payload1,024 bytes。unique index/外部キー、insert/update/delete、commit/rollback、兄弟隔離を確認。各回Python processを新しくし、同じdriver・batch500で準備し直します。

全体は準備Start・migration/seed・Snapshot・子2個を順番に接続/CRUD/切断/Close・基準Close（broker exit/wait含む）。必要な3回検査は含み、診断用scratch走査/資源採取/最後のheap全量hashは除外。各規模6巡、3方式の全6順列を使用。pilotは別保存し、主計測の試行は除外していません。

中央値、ms。区間中央値の和は全体中央値とは一致しません。

| 指標 | 小 現行 | 小 file | 小 heap | 中 現行 | 中 file | 中 heap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **テスト全体** | **585.29** | **584.02** | **402.28** | **1401.91** | **1379.72** | **1212.41** |
| 準備Start | 47.90 | 54.81 | 53.22 | 46.19 | 55.19 | 54.41 |
| migration/seed | 21.90 | 20.62 | 20.65 | 773.70 | 777.81 | 766.55 |
| Snapshot | 380.24 | 359.76 | 190.80 | 404.67 | 364.73 | 218.46 |
| 子1個の起動 | 50.39 | 54.44 | 51.55 | 50.51 | 54.71 | 52.48 |
| 子1個のCRUD | 2.97 | 3.07 | 2.83 | 19.66 | 19.77 | 20.08 |
| 子1個のClose | 4.47 | 2.67 | 2.54 | 4.56 | 2.78 | 2.63 |
| 基準Close/最後のhost回収 | 1.52 | 9.16 | 1.64 | 1.66 | 13.13 | 1.65 |

heapは現行・fileのどちらに対しても各規模6/6巡で速くなりました。現行比の全体短縮は183.02 / 189.51 ms、31.3% / 13.5%。file比は31.1% / 12.1%です。fileだけでは現行比−0.2% / −1.6%で、小規模の全体時間は近い値です。**主な利益はSnapshotであり、子のMariaDB起動を大幅に速めた成果ではありません。**

全体範囲は、小が現行573.38〜716.56 / file557.75〜652.73 / heap397.45〜413.85 ms、中が現行1388.29〜1445.18 / file1369.05〜1418.14 / heap1205.79〜1215.66 ms。最初のpilotは現行1691.44 / file1533.67 / heap401.80 msで、最初の2方式に約1秒の待ちがありました。原因は今回追跡しておらず、主計測へ混ぜて利得を増やしていません。主計測内の遅い試行は全て含めています。

[全試行](python-heap-snapshot-evidence/plain.json)、[集計・対応差](python-heap-snapshot-evidence/summary.json)、[pilot](python-heap-snapshot-evidence/pilot.json)。以前のGoやPython E/D2の値とは直接引き算しません。今回の同一条件内の比較です。

## メモリと保持

別campaignで各3巡、実行順を回転。以下は中央値、MiB。

| 指標 | 小 現行 | 小 file | 小 heap | 中 現行 | 中 file | 中 heap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| host個別最大RSSのうち最大 | 527.42 | 543.41 | 124.31 | 601.50 | 614.88 | 157.09 |
| 全hostのGo累積割当合計 | 455.69 | 455.61 | 14.25 | 629.56 | 629.42 | 60.57 |
| Python自身の最大RSS | 21.13 | 19.08 | 19.13 | 21.95 | 21.81 | 21.86 |

現行のhost報告は準備/2子/identity照会helperの4process、同一hostは1processです。RSSは各processの高水位の**最大**を取り、和にはしていません。Pythonとhostを合算した同時刻のピークや、OS file cacheを含むシステム全体の物理メモリではありません。Go割当は全host分を足し、Python分は含めません。mmapはGo heapの外です。[資源生データ](python-heap-snapshot-evidence/resources.json)。

heap基準の保持blockは約3.02 / 27.27 MiB、論理file内容は約138 / 159 MiB。未書込ゼロを実体化しないこと、guest Exportやホストfile転送を通らないことを含む候補全体の利益です。「一時fileなし」だけの寄与や、GC/OSへの即時返却を証明していません。

資源採取つき全体も現行618.12 / 1394.31 ms、file621.15 / 1385.01 ms、heap407.19 / 1215.65 ms。heapは両対照に全3/3巡で速く、通常計測とは混ぜません。資源報告の終了時JSON書き出し等の小さな費用はこの別campaignに含まれます。

## 所有・隔離・停止の確認

| 確認 | 結果 |
| --- | --- |
| 小/中、3方式の通常CRUD・commit/rollback・兄弟の初期値 | 全plain36 / resource18 workflow PASS |
| 元DBの消費、transaction拒否後の継続、閉じた/不正handle拒否 | PASS |
| 親Snapshot Close後の2子、派生SnapshotとそのClose後の子 | PASS |
| 同じhostの別DBは別endpoint、1DBに2SQL接続、duplicate-keyエラー後も他接続/兄弟継続 | PASS |
| 2子で同時更新、同時Fork要求（制御は直列処理） | PASS。並列性能ではない |
| 一つの子をCloseしても兄弟継続 | PASS |
| freeze failure / target corruption / owner corruption | 既存oracleをPython制御経路から実行してPASS。各拒否理由とsource消費をassert |
| guestの従来Exportとの全inventory/content一致 | 小規模の別audit PASS、両経路ともメモリ内で比較 |
| 既存pytest fixture形（session基準、function子） | 2テストPASS。製品側fixture実装は変更なし |
| Python ownerの制御pipe EOF | hostが生存2子/基準を協調終了し、exit0・scratch残留0 |
| host全体のSIGKILL | 同系統の子/基準が利用不能。待機中要求はHostError/unusable。別startのDBは継続 |
| SIGKILL後の後片付け | payload fileは0、**空の管理dir4個が残存**。harnessが記録後に所有scratch内の空dirだけ除去。ライブラリcleanup成功とは扱わない |
| 通常Close/検査失敗後 | file/dir残留0、全host終了/reapをassert。資源採取時のowner数とcapture registry0を保存データでも確認 |

[境界の詳細・拒否理由・host停止結果](python-heap-snapshot-evidence/verify/boundaries.json)、[fixture](python-heap-snapshot-evidence/verify/fixture.txt)、[Export audit](python-heap-snapshot-evidence/verify/audit.json)、[base/snapshot unit](python-heap-snapshot-evidence/unit.txt)。heap payloadなしは経路とexport guardで確認しており、scratchのfile0だけから推論していません。現行でも内容fileはunlink後FDで保持するため、Snapshot後のfile0は「作らなかった」の証拠になりません。

このspikeは全guestのrace評価や一般的なWasm正確性の再調査ではありません。既存のguest/runtime/converter修正は変更せず、今回の所有・接続境界を検証しました。

## 製品化前に残る具体的な差

1. **同一host内の制御の直列化。** 長い一つの制御要求は別DBのClose等を待たせます。SQL自体は並行して通過済みですが、同時Forkの並列性能・要求の個別cancelは未実装です。Python側の制御応答timeoutは現在host全体をdisposeするため、関連DBへ影響します。製品化設計で独立した要求/エラーの扱いを決める必要があります。
2. **実験adapterを正式な所有実装へ移す作業。** timeout/binary、connection_info、closed、wait_disconnected、snapshot rollback、fork、Close/contextの範囲を実装しました。status、per-DB log、全option、保存/importなどの同等性は未実装。保存APIの削除は決めていません。異常host終了後の空dir回収もここで扱う対象です。
3. **対象規模とplatform。** native Ubuntu x86_64、長期反復/多数派生/多数同時DB、xdist、非協調workerの終了、最終QualificationはSKIP/対象外です。今回の完了をその完了としません。

これらは今回の性能利益を否定する結果ではなく、製品化へ持ち込む境界が具体化されたものです。次の判断を「Pythonでは使えないかもしれない」という抽象的な懸念へ戻す必要はありません。**Pythonから使えて、対象用途で利益が出るところまでは実証済み**です。共有hostという障害範囲を選ぶかをHumanが判断し、その後に正式実装の範囲を決めます。

## 入力・再現・保存

- source_commit: `c129476de5cf41f74abc387274fe0e28034d5fda`。runtime preimage: main `a8137b8b444f86068d3128a291e3a848adfdfd56`。ビルド前にgit_identity.pyで確認。
- 計測対象は上記commit＋記録済みoverlay、新しいbroker/adapter/harness。未変更commit単体の計測ではありません。
- guest SHA256: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- control host SHA256: `94e260e11049ee21427ece8354f40fa9edb7751bd395b8eee7881946b98a05a4`。
- broker SHA256: `da6bd94b9927bf86106077a7d1d4b19013e338e6d2df66d76790f1dcaf14fa53`。
- [build入力](python-heap-snapshot-evidence/build-input.json)、[harness/最終source](python-heap-snapshot-evidence/final-source-sha256.json)、[環境](python-heap-snapshot-evidence/environment.json)、[Python固定依存](python-heap-snapshot-evidence/python-packages.txt)。
- [overlay独立再適用](python-heap-snapshot-evidence/overlay-replay.json)は全postimage一致。canonicalファイルへ復元済み。独立binary再ビルドや正式生成provenance更新の主張ではない。
- [再現README](../../benchmarks/spikes/python-heap-snapshot/README.md)。source/hash/集計/生JSONを保存し、binary/cache/worktreeは削除する。
- Go vet（broker/metrics）、Python構文、追加公開source、証拠checksum、文書リンク、diffを確認。全体の公開source検査は既存tracked `docs/reviews/v050-startup-tail-source-fix-evidence/ubuntu/measurement.log`でFAIL。guardや既存資料は変更せず、追加集合のPASSと区別。[検査記録](python-heap-snapshot-evidence/checks.json)。最初のvetはoverlay復元と重なり無効となったため破棄し、正しいoverlayを固定して再実行した。

mainの既存変更（project-statusと設計/投資資料2件）は保持。本報告は実験ブランチに保存し、製品方向の承認やmain統合とは分離しています。
