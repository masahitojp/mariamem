# E方式の限定評価：準備中から共有可能なbackingに保持する

2026-10-16。macOS arm64。限定spikeの評価は完了。**E全体の実装・速度改善・製品採用は未判定**。

## Human Review

今回の判断は、Eを次の具体化の候補に残すか。
**推薦は残す。Cの本格化より先に、EのSnapshot受け渡しを具体化する価値がある。**
実guestで準備中から共有backingを使え、停止後の内容が既存Snapshotと一致した。
小規模・中規模のmigration/seedでは、大きな追加費用は今回観測されなかった。
ただし試行数は少なく、全体速度の改善を証明したものではない。

最も強い反論は、**派生Snapshotには別の仕事が残り、通常時の資源管理も複雑になる**こと。
private mapping内の子の変更は元FDへ反映されない。Eだけで世代を重ねるSnapshotも
無コピーになるとは言えない。OSのfile backingを使うため、Go heap allocationが減っても
メモリ・I/O全体の費用が減った証拠にはならない。

次のHuman判断では「まず最初の準備済み基準を速く作るEを深める」か、
「派生基準も変更部分中心に扱うDを比較する」かを選べる。
EとDは組合せ可能。今回から次の実装・main統合を自動開始しない。

## 1. 問いと実施範囲

[製品契約](../decisions/snapshot-product-contract.md)の独立DB、基準の不変性、
元DB消費、子の独立した寿命、派生Snapshotを判断軸とする。公開保存APIの削除はしていない。

今回のEは一つの実装候補：
**Fresh DBの /mariadb 配下を、初回確保から一時ファイル＋MAP_SHAREDで保持し、
停止後に共有書込みmappingを外し、読み取り専用FDを固定する**。
子の変更分離には既存MAP_PRIVATEを利用する。

実施したこと：
- 隔離したMemFS overlayでFreshの保存backingを変更。guest/WasmとSQL処理は同じ。
- 既存のMemFS lock、ファイルのnode identity、論理サイズと予約容量の区別を維持。
- 新しい領域への拡張は同じファイルを伸ばしてremap。旧内容の明示的な全量copyをしない。
  shrink後の再拡張は古いbytesが見えないようzero化する。
- 子への分離、親Close後の利用、別プロセスへのFD継承を部品テスト。
- 実guest停止後のFDと、既存guestが作ったcold copyのinventory・hashを監査。
- Cと同じPythonの2子CRUDを、control/shared各3巡、2規模で実行。

**実施していないこと：**
公開Snapshot経路をFDの直接受け渡しへ置き換えること、guest cold copyの削除、
新しい取得時検証の設計、派生Snapshotの無コピー化、製品向けエラー処理、全OS検証。
通常計測では既存Snapshot作成・検証・所有取得を全部残した。
子の実guestは既存prepared mappingを使う。実guestが新しいfreeze primitiveのFDから
直接起動した証拠ではない。部品テストと実guestの内容一致監査を分ける。

## 2. ソースと再現identity

- source_commit: `a8137b8b444f86068d3128a291e3a848adfdfd56`。
  [git_identity.pyの記録](shared-backing-evidence/source-identity.json)をbuild前に取得。
- C参照: [ed78c0e の限定評価](https://github.com/masahitojp/mariamem/blob/ed78c0e901ae864573408d9c8797a5e6bfc1a512/docs/reviews/file-cow-crud-probe.md)。
- MariaDB 12.3.3。guest hash:
  `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。
- macOS 27.0.1 arm64、Go1.26.8、CGO_ENABLED=1、Python3.9.6、PyMySQL1.2.3。
- [binary hash・go version -m・overlay](shared-backing-evidence/build-identity.json)、
  [各変更のpre/post hash](shared-backing-evidence/instrumentation.json)、
  [harness入力](shared-backing-evidence/campaign/inputs.json)。
- controlはbaseline runtimeを先にbuild。実験toolingがあるためvcs.modified=true。
  sharedはexact-preimage overlay適用後の別binary。ラベルだけで同一入力とはしない。

試作の所有元は[適用script](../../benchmarks/spikes/shared-backing/instrument.py)と
[backing template](../../benchmarks/spikes/shared-backing/observer.go.txt)。
generated Goへの一時overlayは復元し、canonical生成物としてcommitしない。
canonical provenance、guest patch、release guardは変更していない。
このbinaryを正式な再生成・release検証済みとは扱わない。

## 3. 小さな実証で確認した性質

[テストと結果](shared-backing-evidence/focused-tests.log)：
E用4テストと既存MemFS/prepared境界6テストがPASS。
穴とAllocate拡張のzeroを追加確認した[最終Eテスト](shared-backing-evidence/focused-tests-final.log)もPASS。

- 拡張で旧内容を保持。shrink→grow、O_TRUNC→grow、穴のzero、Allocateの非縮小・現在位置保持。
- renameしてもbacking identityを維持。unlink後の開いたhandleは使え、削除nodeをfreeze対象にしない。
- 停止したwriterのmappingを外し、余剰容量を切り詰め、読み取り専用FDを取得。
  pathnameと元の書き込みFDを解放する。本文のfreezeはこのquiescent-only primitiveを指す。
- 二つのprivate mappingの一方を変更しても、もう一方と元FDの内容は変わらない。
- 親側のFD・管理資源を閉じても、開始済みの子mappingを読める。
- 別プロセスへ継承したFDからprivate mappingを作り、書いても元FDへ伝わらない。
- 子のprivate viewを拡張する既存経路ではheapへmaterializeする。子の内容は保たれ、
  元・兄弟は変わらない。
- 子の内容を全量materializeして派生基準を作る場合の独立性も確認。
  **このテストは派生Snapshotの無コピー化を確認していない。**

freezeは実行中のwriterと競合させてよいAPIではない。
試作は停止・joinを前提とし、失敗は実験を失敗させる。製品向けのrollback、
部分失敗回復、FD上限、ENOSPCやmapping障害等は未検証。
新しい取得時inventory/content/guest identity検証を満たすpublic protocolも未実装。

## 4. 実guestの内容一致

性能試行と別の小規模auditを1回実行。
既存 `resident.inc` はworker停止→`l4m_close()`→cold copyを行う。
Go側は全generated workerのjoin後、Eのlive fileをfreezeした。

**13ファイル、138.24 MiBのinventoryと全内容hashが既存cold copyと一致。**
[生の結果](shared-backing-evidence/audit/)。
freeze操作だけは13.32 msだったが、単発であり、hash検証時間は含まない。
**これを「新Snapshotが13 msになる」という数字には使わない。**

削除済みnodeはinventoryへ含めない。directory metadataのpublic表現、
guest identityの受け渡し、Pythonへの逆方向FD移譲は、この部品監査では未確認。
全データの確認を省略して採用する意図はない。

## 5. 準備・CRUDへの費用

2表、100行/表（payload256 bytes）と10,000行/表（payload1,024 bytes）。
準備後、first子で1行ずつINSERT/commit、second子でUPDATE/commit、
DELETE/rollbackとDELETE/commit。各子は順次終了。
同じ巡でcontrol/sharedを交互に入れ替え、各3回。別途pilot各1回。

### 各3回の中央値

| 区間 | 小：現行 | 小：E試作 | 中：現行 | 中：E試作 |
| --- | ---: | ---: | ---: | ---: |
| Fresh Start | 55.15 ms | 51.37 ms | 47.42 ms | 54.29 ms |
| migration＋seed | 18.92 ms | 19.06 ms | 837.14 ms | 828.30 ms |
| 既存Snapshot経路 | 418.99 ms | 458.10 ms | 507.23 ms | 476.29 ms |
| 準備＋Snapshot＋2子CRUD/Close＋基準Close | 618.88 ms | 659.62 ms | 1652.90 ms | 1579.88 ms |

全体時間からは最後の検証用baseline再hashを除く。
[全試行・各区間の範囲](shared-backing-evidence/summary.json)を参照。

- migration/seed：小は現行13.23～26.50 ms、E12.58～23.26 ms。
  中は現行791.32～911.12 ms、E817.58～869.81 ms。
  **今回の範囲で大きな追加費用は見えていないが、同等性能の保証ではない。**
- 小の全体は現行613～702 ms、E605～827 ms。
  中は現行1427～1674 ms、E1547～1584 ms。
  正負は規模・試行で異なる。候補由来かばらつきかをこの数で分離しない。
- Eは既存Snapshotのcopyをまだ実行しており、通常時のfile backingの費用に
  既存のファイル化を重ねている。この表を完成Eの優劣・改善率にはしない。
- pilotのFresh Startは両モードとも約1秒だった。pilotも保存し、都合よく破棄していない。
  初回条件・起動tailの原因は今回追跡していない。
- 全12 campaign・24子のSQL/commit/rollback/変更非伝播を確認し、
  12 campaignで子利用後の基準hash一致を確認した。

試作が登録したnodeは16（終了時live13）。終了直前の登録全nodeの論理長合計は
小150.25 MiB／中170.59 MiB、mapping予約長は150.41／174.88 MiB。
mapping作成・成長回数は22／38。削除済みの一時ファイルも終了まで登録に残すため、
これはSnapshotサイズでもRSSでもpeak使用量でもない。
将来はopen handleとunlinkの寿命に沿った回収を設計する必要がある。
OSのpage cache、dirty page、I/O、physical footprint、並列時の圧迫は未測定。

## 6. 省ける処理と残る処理

| 現在の処理 | Eでの見通し | 今回の証拠／未完了 |
| --- | --- | --- |
| preparation中のheap確保・成長copy | file backingの拡張/remapへ変更できる | 実guestで実行。ただし資源費用が消えたとは言わない |
| guestが /mariadb をSnapshot用領域へcold copy | 停止した元backingを固定する設計なら省ける可能性 | 元とcold copyの全内容一致。guestのexport制御変更は未実施 |
| GoがSnapshot領域から一時ディレクトリへ書出し | FDを直接所有・受渡しできれば省ける可能性 | freeze・private mappingは部品確認。正式handoff未実装 |
| 中間ファイル→保存先copyと取得時再取得 | 一時Snapshotを同一backingの所有移譲にすれば減らせる可能性 | 完全性検証・失敗時所有の新protocolが必要 |
| inventory/content/guest identity検証 | 維持が必要 | 今回は既存guardを全部残した。hash走査時間を消える費用に数えない |
| 各ForkのMariaDB起動 | 残る | Eはrunning runtimeの複製ではない |
| 子の小さな変更 | 既存OS page CoWを利用できる | 部品テスト＋既存経路の実CRUD。Cのfile全量copyを導入しない |
| 子の拡張・派生Snapshot | 追加のmaterializationが残る | private変更は元FDにない。無コピー化するならD/F等の設計を別途比較 |

根拠：[guest停止とcopy](../../guest/resident.inc)、
[cold copy](../../guest/snapshot_fs.inc)、
[Go export](../../internal/generatedgo/main.go)、
[worker joinとcleanup](../../internal/generatedgo/runtime_instance.go)、
[private mapping](../../internal/generatedgo/code/base/owned_prepared.go)、
[Pythonの所有取得・FD継承](../../python/mariamem/snapshot.py)。

Pythonの現在のFD継承は「Python→子host」である。
Eが新たに必要とする「終了するsetup host→Python所有者」の受け渡しは別方向。
子プロセス継承テストだけでそのprotocolも完成済みとはしない。
必要ならFD transfer、または保護された一時pathから同じinodeを取得する設計を比較する。

## 7. 判定と次の境界

| 項目 | 判定 |
| --- | --- |
| 最初から共有backingで実guestを準備する | PASS（今回のmacOS・fixture限定） |
| 既存cold copyと固定した内容の一致 | PASS（小規模audit 1回） |
| private子・別プロセス・親Close後の寿命 | PASS（部品テスト） |
| 実guestの通常CRUD・既存Snapshot/Forkの関連動作 | PASS（12 campaign、24子） |
| 準備への費用の軽量比較 | 実施済み。安定した性能同等性・全体改善率は未確定 |
| EによるSnapshot作成全体の高速化 | 未実装・未計測 |
| 派生基準の無コピー化 | 未実装。現在のprivate FDだけでは表現できない |
| Pythonの新handoff、取得時検証・失敗回復 | 未実装 |
| Ubuntu x86_64、macOS15、並列多数子、メモリ/I/O負荷、最終Qualification | SKIP／今回対象外 |

今回の推薦を支えるのは、**独立DBと既存のページ分離を維持する構成要素が成立し、
準備への明確な大幅悪化が今回見えていない**こと。
推薦への最大の留保は、Snapshot全体の利益、派生基準、資源負荷がまだ未評価であること。
限定評価の完了と、製品化の完了を分ける。

## 8. 再現・保存・cleanup

[runner](../../benchmarks/spikes/shared-backing/run.py)、
[summary](../../benchmarks/spikes/shared-backing/summarize.py)、
[部品テスト](../../benchmarks/spikes/shared-backing/observer_test.go.txt)。

1. baseline checkoutを作り `scripts/git_identity.py inspect HEAD` でsource_commitを確認。
2. Go1.26.8、CGO_ENABLED=1、隔離GOCACHEで `go build -p 2 -o <temp>/control-host ./cmd/mariamem-host`。
3. 計測sourceを置き `python3 benchmarks/spikes/shared-backing/instrument.py`。
4. 同じGoで `go build -p 2 -o <temp>/shared-host ./cmd/mariamem-host`。
5. `go test ./internal/generatedgo/code/base -run '^(TestE|TestMemFSGrowth|TestPrepared|TestOwnedMapped)' -count=1 -v`。
6. 専用venvにPyMySQL1.2.3。runnerに `--control <control-host> --observed <shared-host> --output <dir>` を渡す。
   pilotは `--pilot`、監査は `--audit`、本計測は `--repeats 3`。出力先は別々の空directory。
7. `summarize.py <campaign-dir> <summary.json>`。TMPDIRも実験専用。
8. overlayのafter hashを確認してruntimeをbaselineへ復元。小さな結果・sourceのみcommit/push。

専用workspaceのbudget12 GiB/min-free16 GiB、各実行の上限300秒、build上限1200秒。
小さな証拠の[checksums](shared-backing-evidence/checksums.json)を確認し、
tempのbinary/cache/venvと完了worktreeは保存後にcleanupする。
実際のcleanup結果はworkspace receiptと最終報告に残す。
mainの既存未commit設計資料3件には手を加えていない。
