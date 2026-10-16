# D heap＋Python共有host：製品化の設計案

2026-10-16。HumanはD＋共有hostの実装を承認。その後、保存・load APIを廃止する方針を指定。以下の旧案との差は本追記を優先する。製品採用・main統合・リリース承認とは別。

## Human Review

**今決めるのは、Dのメモリ内Snapshotと、準備系統ごとの自動管理hostを正式実装する範囲として承認するかです。推薦は、この資料の範囲で実装へ進むことです。** Pythonの既存の使い方で、準備1回＋子2個の全体時間は小規模31.3%、中規模13.5%短縮しました。利用者によるサーバー管理を増やさず、独立DB・通常のcommit/rollback・親と兄弟の隔離を保つ実現性を確認しています。性能の主な利益はSnapshot作成で、子のMariaDB起動そのものはほぼ同じです。

**最も強い反論は、同じhostが停止すると、その基準を使う複数テストがまとめて続行不能になることです。** 現行Pythonでは子ごとにhostが分かれ、取得済み基準もPython側に残ります。候補では基準まで同じhostにあるため、host停止時は準備からやり直します。実験でこの影響範囲を確認済みです。一方、通常のSQLエラーや子のCloseで兄弟が止まる結果は出ていません。担当者としては、この障害範囲を受け入れ、通常のtimeoutをhost全体の停止に拡大しない設計を条件に進めることを勧めます。**個々のDBを強制停止しても兄弟と基準を必ず残すことが必要なら、この共有host案は採用しません。**

今回の資料作成は完了です。以下は未実装の提案であり、spikeのPASSを製品実装のPASSとして扱いません。承認後も最終成果をHuman Reviewへ戻し、採用・リリースを自動実行しません。

## 承認後の範囲変更

Human指定により、Go/Pythonの保存・読み込みの公開入口を廃止する。Pythonの`db.snapshot(path)`など保存先を受け取る形、`Database.snapshot_to`、`load_snapshot`、`Snapshot.open(path)`、pathによるSnapshot取得、Goの`LoadSnapshot`と`SnapshotOptions.Destination`を除く。`snapshot()`と`fork()`のメモリ内再利用、完全検証、消費型Snapshotと子の独立性は維持する。旧保存artifactの読み込み互換性は今回維持しない。必要なmigration/seedを再実行して基準を作る。

下記§4の保存・import維持案と§6の保存/importケースはこの決定で置換する。保存形式の維持・external path変更試験は製品機能の対象から外し、既存の破損・identity拒否oracleをメモリ内の同等境界へ移す。歴史資料は当時の契約として残す。別binaryを明示したForkに必要な内部受け渡しがある場合も、利用者向け保存APIは導入しない。

保存/importとその製品ガイド・受入検証の維持が不要になるため、旧見積もり8〜12人日を**7〜10人日程度**へ更新する。API削除に伴うテスト・consumer・ガイドの更新は必要で、この削減を実測済みの所要時間としては扱わない。接続上限はDBごとに16を維持し、接続数最適化は別件とする。

## 1. 根拠と判断の更新

製品の基準は[Product contract](../project-status.md#product-contract)と[承認済みSnapshot契約](../decisions/snapshot-product-contract.md)。main参照は`a8137b8b444f86068d3128a291e3a848adfdfd56`。作業ツリーの既存project-status／設計・投資資料は変更していません。

| 根拠 | 今回の判断に使う範囲 |
| --- | --- |
| [Python同一host比較・pgmem裏取り](https://github.com/masahitojp/mariamem/blob/6988fa575d025dbddd99a53220a3aa5261c32268/docs/reviews/python-heap-snapshot.md) | 小・中規模、子2個。通常36試行、別資源計測18試行。所有・停止・fixtureの限定確認。macOS arm64のみ |
| [C対D、同じGoプロセス・payload一時fileなし](https://github.com/masahitojp/mariamem/blob/c129476de5cf41f74abc387274fe0e28034d5fda/docs/reviews/cd-heap-snapshot.md) | DはCより全体約11.2%／6.2%短縮。Cの初回変更時の全ファイルコピーがMariaDBの利用で実際に発生。Dを主候補にする根拠 |
| [Go heap実guest](https://github.com/masahitojp/mariamem/blob/72400d1196c94e7372bb28af328f9fc2132a4416/docs/reviews/go-heap-snapshot.md) | Go APIでメモリ内の所有・子・派生基準を構成できる根拠。Pythonの数値と直接引き算しない |

Pythonの同一条件内の中央値（ms）：

| 準備＋子2個＋全Close | 現行Python | 同一host＋従来file | 同一host＋D heap |
| --- | ---: | ---: | ---: |
| 小規模 | 585.29 | 584.02 | 402.28 |
| 中規模 | 1401.91 | 1379.72 | 1212.41 |

host数だけを減らす案よりD heapの利益が大きい。ただしfile対照は所有・検証もGoへ移すため、純粋なプロセス生成費用の比較ではありません。別計測のhost個別最大RSSの最大値は、小527.42→124.31 MiB、中601.50→157.09 MiB。これは同時刻のプロセスツリー全体のピークではありません。Go累積割当、RSS、保持block量は元資料で分離しています。

以前の直接コピーの大規模・多数Forkでの混在結果は未解決のままです。今回の小・中規模の結果から、直接コピーの悪化原因やDの大規模性能は判定しません。Dは新しい所有方式の候補として評価します。pgmemは固定commitで同一host内の複数DB／Forkとメモリ共有を確認しましたが、その障害・ライフサイクル契約をそのまま採用するものではありません。

## 2. 提案する構成と利用者に見える違い

通常のPythonは従来どおり`start() → snapshot() → fork()`とcontext managerを使います。各子に実MariaDB runtimeとSQL endpointを作り、実行中のheap・thread・lockを複製しません。

| 境界 | 提案 |
| --- | --- |
| 準備 | 独立した`start()`ごとに自動管理hostを1個起動。Go利用は従来どおり呼出し元process内 |
| Snapshot | guestの整合化・停止とworker完了を待ち、停止後のファイル状態を不変16 KiB blockの基準として所有。通常経路はSnapshot内容の一時fileを作らない |
| Fork | 基準blockを共有し、子が変更するblockだけ私有化。各DBのmetadataと実行状態は独立 |
| 派生Snapshot | 子の固定時点の内容を新たな不変基準にする。親・兄弟を変更しない。祖先のmutable objectへの参照連鎖を作らない |
| Pythonの寿命 | 内部SessionをDB／Snapshot／処理中要求が保持。元DBが消費されてもhostは残る。最後の所有handleと処理が終了したらhostを終了・回収 |
| Snapshot Close | 新しいForkを拒否し、既に受理したForkの所有移行を待つ。開始済みの子はそのまま使える |
| pytest | session準備・function子の既存構成。xdistではworkerごとに所有し、worker間共有や新たなdaemonを導入しない |

「一時fileなし」はSnapshot payloadについてです。管理directory、log、SQL socket、guestのlinear-memory mappingまでなくす提案ではありません。

取得時はinventory・全内容・guest identityを検証し、検証した正確なbackingを所有します。**元・固定後・所有取得の3回の論理内容走査をまず維持**します。暗黙のゼロもhash対象です。高速化と検査回数削減を同時に行いません。Forkは所有済みbackingの構造・寿命・identity確認で開始し、毎回の全量hashを追加しません。

## 3. 終了と故障：試作から必ず直す点

host全体で制御要求を直列化せず、request IDによる応答対応とDB単位の操作制御に変えます。registryのlockはhandle取得／状態遷移に限定し、SQL待ち・起動・終了中は保持しません。同じDBの競合操作は順序付け、別DBのCloseやstatusを待たせないことを検証します。Forkと基準Closeの競合では、受理済み要求がbackingをpinし、成功した子だけ所有を引き継ぎます。

以下は**製品化目標**であり、全行が試作で実証済みという意味ではありません。

| 事象 | 利用者への扱い／必要な実装 | 既存証拠 |
| --- | --- | --- |
| SQLの制約違反、通常rollback | その接続／transactionの結果として返す。他DBと基準は維持 | duplicate-keyと兄弟継続を確認 |
| Snapshotのbusy／transaction拒否 | 型・codeを維持し、元DBを使用可能のまま返す | transaction拒否は確認済み。正式経路で双方を再検証 |
| 受理後のSnapshot失敗 | consumed状態を正確に返す。公開していない基準・部分成果を回収 | freeze／破損oracleあり |
| 1要求のdeadline超過 | 対象要求をcancelし、遅れて届く応答を別要求へ誤配しない。Fork等が後から成功した場合も未返却handleを回収。単なる待ち時間超過ではhostをkillしない | 試作はhost全体dispose。未実装 |
| DB終了が協調完了しない | 対象DBを再利用不能にし、参照中の資源を保持して終了待ち。他の所有者がいる間はhostをkillしない | 共有hostでの製品経路は未確認。強制停止改善は範囲外 |
| 最後の所有者のClose／Python owner EOF | 全資源へ協調終了要求。Pythonが生存していれば期限後のhost terminate/killとwaitを実施可能。他の利用中DBを巻き込む通常Closeとは分離 | 協調EOFは確認。正式なdeadline・回収制御は未実装 |
| host crash／制御pipe喪失・回復不能なprotocol破損 | 系統内handleを失効し、全pending要求へ明確なエラー。自動再起動で状態喪失を隠さない。別startは継続 | SIGKILLで確認。protocol破損は追加対象 |

非協調DBが残る間は、そのメモリ・workerが他の子の利用期間中残る可能性があります。対象を閉じたと表示することと、実資源の回収完了を区別します。Python親も強制終了した場合の無条件回収は保証しません。試作でhost SIGKILL後に残った空directory4個は製品cleanup成功ではなく、Pythonが生存する場合に所有directoryのみ回収する実装・検証の対象です。

この分離で通常のtimeoutによる巻き添えは減らせますが、process全体のOOM・fatal errorから兄弟を隔離することはできません。発生率を測った証拠はなく、日常的にテストが壊れると主張するものではありません。共有hostの有限な故障契約としてHumanが判断する点です。

## 4. APIと保存の境界

**推薦案は、通常の`snapshot()`をメモリ内にし、明示的保存APIは維持することです。** 保存を不要とした実験の利益を通常利用へ持ち込み、既存利用者の実行間再利用を残します。保存APIを廃止する承認は得ていません。この提案の保存・importは未検証です。

| 操作 | 内部経路の案 | 維持する契約／費用 |
| --- | --- | --- |
| `snapshot()`／Go Destination空 | D heap基準 | source消費、完全検証、子の独立性。payload file転送を省く |
| `snapshot_to(path)`／Go Destinationあり | 既存の保存形式・検証・所有取得へ接続。返す基準はfile backingでもよい | ファイル化費用は払う。Closeで明示保存先を消さない |
| `load_snapshot(path)`／既存open入口 | 新しい所有Sessionへ既存import経路で検証済み独立backingを取得。MariaDBはまだ起動しない | 元pathの変更・削除から独立。Pythonではhostがimport時点から存在する違いを記載 |
| 保存／import基準からFork | 同Session内でfile backingを利用し、子の変更はDで分離する案 | 両backingの派生Snapshot・Closeを検証。保存経路まで同じ速度とは約束しない |

後からsaveする新API、保存format変更、自動cacheは追加しません。内部backingの選択を通常利用者へ要求しません。

正式Python対応はconstructor／start／Snapshot.open／load、Fork option継承、timeout、status、connection_info、id、capabilities、diagnostics、logs／log_path、例外型とcode・stage・closed、Close／context managerを現行コード・テストと対応づけます。共有hostでもlogをDB単位に区別し、process共通障害の記録を別途関連づけます。既存の無効・廃止optionの拒否も維持します。

**Forkの`host_binary`上書きは特別な境界です。** 現行Pythonは子ごとのbinary指定を受け付けます。同じhostでは異なる実行fileを選べません。互換性維持案は、この明示指定で別binaryが必要な場合だけ、基準を検証可能なfile表現で別hostへ渡すことです。通常heap経路とは別で、速度利益の対象外です。guest identity不一致は従来どおり拒否します。この例外経路も作業範囲に含めますが、実装費用が下記枠に収まらなければ差分を報告し、黙ってoptionを無視・削除しません。

## 5. 変更の所有元と作業規模

実験overlayをそのままmergeせず、以下を独立レビューできる差分にします。guest／converterの更新は不要という設計前提です。生成物を手編集せず、生成recipe・正式な手書き所有元へ変更を置きます。

| 作業 | 主な所有元／成果 | 概算の実作業量 |
| --- | --- | ---: |
| D storageと基準所有 | MemFSのread/write/resize/allocate、`internal/prepared`、`internal/snapshot`、runtime接続。公開mutable slice、実験registry・環境変数による切替を正式な所有表現へ置換 | 2〜3人日 |
| host制御と寿命 | `cmd/mariamem-host`とPython内部Session。request対応、個別cancel、handle pin、失敗回収、DB単位log、最終host回収 | 2〜3人日 |
| API・保存との接続 | `snapshot.go`、`python/mariamem/__init__.py`／`snapshot.py`、保存/import、option・例外互換、別binary例外経路 | 2〜3人日 |
| 正式生成・検証・資料 | `scripts/generate_runtime.py`等のcanonical経路と手書きinventory、独立再生成、両native platform、限定比較、利用ガイドとHuman Review | 2〜3人日 |

**合計8〜12人日程度という設計段階の見積もり**です。1人日を約6時間の集中した作業とし、CI待ち・Human待ちを除きます。実行時間の実測や完了保証ではありません。プロトタイプの速度測定を再開する予算ではなく、二つのbacking、Python制御、既存APIを製品品質へそろえる費用です。最大の不確実性は個別cancelと既存option／保存経路の接続です。

保存廃止や別binary対応削除を選べば範囲は減らせますが、その合意を前提に見積もりを小さくしません。12人日相当に達して未完なら完了とせず、成果・不足・追加費用を提示して停止します。各差分で実費を更新し、超過が見えた時点で早めに相談します。

## 6. 完了条件と停止条件

正式実装の完了判定は次の固定集合で行います。新しい論点を無制限に追加しません。既存失敗oracleを弱めず、具体的な欠陥が見つかれば該当範囲と影響を報告します。

1. **所有とI/O：** block境界、ゼロ長、穴、truncate縮小→再拡張、allocate、同一fileの並行I/O、rename/unlink・open handleを既存MemFSの参照動作と比較。親・兄弟・派生基準の内容を検査。freeze／target破損／owner破損／guest identity不一致oracleを維持。
2. **制御と失敗：** 同時Fork、ForkとClose、別DBの長い要求とClose、deadline後の遅延成功、EOF、host kill、protocol異常を決定的な注入で確認。別DBの通常操作継続、失効範囲、未返却handle回収、最後のwaitをassert。任意のguestを強制停止できることは完了条件にしない。
3. **APIと保存：** 上記API対応表の全項目に実装・検査先を付ける。通常メモリ基準、保存からの基準、import、異なるbinary指定の対象経路で隔離・派生・Close・外部元path変更を確認。既存consumerとpytest fixture／xdist worker所有を確認。
4. **規模：** 小・中の準備＋子2個に加え、従来の100 MiB／16 Forkシナリオ、同時子4個、派生10世代、同Session内100回のFork/Closeを固定ケースにする。機能assertと所有数・FD・process・directory残留を確認。heapのGC後到達性とRSSは分け、即時RSS低下を解放の条件にしない。
5. **正式な生成と対象platform：** source identityを確認し、canonical生成・独立再生成・provenanceと手書き包含検査、現行のcheck／関連integrationを実行。macOS arm64とUbuntu x86_64で変更境界を確認。CIへ渡したらrun URLとSHAを報告して停止し、結果未取得をPASSとしない。
6. **利益の再確認と報告：** correctness通過後、正式候補対mainで小・中・100 MiB／16 Forkの全体時間とSnapshot・子・Closeを分ける。通常計測は各6対、資源計測は別各3対に固定し、全試行を保存。測定順・同時実行・toolchainを固定。改善しない／混在する結果でも測定完了とし、採用推薦への影響を報告する。小・中の利益が失われる、または大規模で一貫した悪化が出る場合は自動採用せず原因と選択肢を提示。

この集合を満たした時点で「実装・限定検証完了」としてHuman Reviewへ戻ります。platform未実行はSKIPであり、両platform完了には数えません。待ちや予算上限を達成扱いしません。最終Release Qualification、広範なProduct Validation、全guestのrace census、一般Wasm互換性の再調査はこの設計の作業範囲に含めません。

## 7. 今回の保存・確認範囲

この資料だけを追加しました。製品契約・project-statusの承認済み方針、runtime、生成物、実験証拠は変更していません。参照したローカル実装と固定commitの資料、文書リンク、diff／statusを確認しました。文書のみの変更なので、新しいビルド・測定・runtime検証は実施していません。
