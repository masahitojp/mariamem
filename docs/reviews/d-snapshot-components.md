# D1・D2 Snapshot部品spike：実プロセス間の所有と測定

2026-10-16。macOS arm64。承認された部品spikeは完了。
MariaDB・Wasmランタイムへの接続、製品採用、main統合は未実施。

## Human Review

**今決めたいのは、D2を実guestへ接続する次の限定spikeへ進むかです。**
推薦はD2を第一候補として接続可否を検討し、D1を比較候補として残すことです。
今回、両案で独立した子・派生基準の所有が成立し、D2はSnapshot時のpayload転送を省けました。
転送先を揃えた比較でも、64 MiBの密なデータでは部品全体が233.5→203.2 ms、約13%短縮し、
同じ巡の5組すべてでD2が速い結果でした。

**最も強い反論は、小規模・疎なデータでは全体利益がなく、OS間の不安にもまだ答えていないことです。**
8 MiBの密なデータはほぼ同じ、疎な条件はD2が中央値で約0.5〜1.4 ms長くなりました。
Ubuntu x86_64はSKIPです。D2は依然として共有mappingを使い、OS依存の解消とは言えません。
ここから製品採用やEより高速と判断せず、実guestの準備・停止・検査を含む利益を次の判断対象にします。

今回の答えは「Dの所有形式は限定した部品で成立し、D2の転送削減は確認できた。
ただし、それが全ケースの全体高速化につながるわけではない」です。
[設計](d-snapshot-design.md)の4終了条件ごとの判定を下記に示します。

## 比較条件：SQLテストの時間ではない

Go producerで決定的なfile内容を作り、Python ownerが検証・所有し、独立したGo consumerを
順番に2個起動して、小変更後に終了します。実際の別プロセス・FD継承・readonly mappingを使います。
MariaDBのmigration、SQL、commit/rollback、整合停止、guest worker joinは含みません。
「実DBテストが13%速くなった」という結果ではありません。

- macOS 27.0.1 arm64、Go 1.26.8、Python 3.9.6。共通binaryを引数でD1/D2切替。
- blockは16 KiB。data fileは8 MiB／64 MiB。密な条件は全blockへ内容を書き、
  疎な条件は16 blockごとに1 blockを書く。同じ論理サイズを比較する。
- さらに両条件共通で約16 KiBの境界file、2 MiBのzero file、空fileを持つ。
  全検証対象は約10.016／66.016 MiB。実guestのfile分布の再現ではない。
- 子は境界をまたぐ33 bytesの更新等を4箇所、shrink/regrow、新file作成を行う。
  block内容の独立性を見るfixtureであり、実FSのrename/open-FDやSQL意味論の代用ではない。
- 各条件5組、D1/D2の順序を巡ごとに反転。計40 workflow／80子。
  pilotは別保存し、主集計に含めない。最初の比較と後述の条件統一後の比較を混ぜない。
- 部品全体は準備、元hash、引き渡し、Python取得、2子の起動・小変更・終了、基準Closeと一時資源削除。
  子終了後の追加全量hash auditだけを別計時して除く。audit自体は全runで成功。

両案とも元の論理内容から期待hashを生成し、受け手が保持する実体の全論理内容を検証します。
zero領域もhash対象です。Fork時は取得済みFDの構造・寿命確認だけにし、全hashを繰り返しません。
guest identity検査のfixtureには専用文字列を使用し、実guest互換性を検証したとは言いません。

## 転送先を揃えた最終比較

最初のD1は16 KiBごとにfile writeしていたため、コピー時期以外に出力方法の差がありました。
その[初回結果](d-snapshot-components-evidence/initial/summary.json)も保存しています。
初回64 MiB密の220.6→200.2 msは、その実装同士の結果です。

最終比較ではD1も共有mappingへまとめ、heap→mappingへcopy後にwriterを閉じます。
D2は準備時から共有mappingへ書き、停止時はcopyせずwriterを閉じます。
reader、配置表、hash、Python取得、子の操作は共通です。
いずれも保存用fsyncの耐久性を測るものではなく、一時基準としての受け渡しです。

中央値、単位ms。割合は中央値どうしの差。区間中央値の和は全体中央値とは一致しません。

| data file／配置 | 部品全体 D1 | 部品全体 D2 | D2の差 | D2が速い組 | 凍結・転送 D1→D2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 MiB／密 | 39.47 | 39.49 | +0.04% | 3/5 | 2.00→0.59 |
| 8 MiB／疎 | 25.65 | 26.15 | +1.98% | 1/5 | 0.26→0.10 |
| 64 MiB／密 | 233.47 | 203.18 | −12.97% | 5/5 | 42.79→19.54 |
| 64 MiB／疎 | 93.82 | 95.19 | +1.46% | 2/5 | 0.83→0.20 |

64 MiB密の全体範囲はD1 213.7〜242.8 ms、D2 198.4〜204.7 ms。
同じ巡の短縮は13.1〜38.1 ms。疎な64 MiBではD2−D1が−0.57〜+2.74 msで、
普遍的な悪化とも改善とも断定しません。小差を同等性の証明にはしません。
[全値](d-snapshot-components-evidence/aligned/raw.json)と
[中央値・範囲・対応差](d-snapshot-components-evidence/aligned/summary.json)。

64 MiB密の主な内訳は次のとおりです。

| 区間 | D1 | D2 |
| --- | ---: | ---: |
| 準備：決定的なデータ生成・配置 | 82.74 | 80.58 |
| 元内容の全hash | 32.38 | 29.95 |
| 凍結・転送・writer Close | 42.79 | 19.54 |
| Python所有取得・全検証 | 47.18 | 46.64 |
| 2子の起動・小変更・終了 | 13.53 | 13.65 |
| 最後のClose・一時資源削除 | 1.61 | 1.46 |

process起動、JSON転送・decode等も全体には含みます。上表だけで全体を再構成しません。
D2の転送payloadは0でも、unmap・size確定・Close等には約19.5 ms残りました。
個別OS処理の寄与は未分解で、特定のsyscallやdisk flushの時間と断定しません。
疎な条件でも論理内容の全hashは残るため、copy削減の影響は小さくなります。
子2個の区間はD2が中央値で約0.1〜0.8 ms長く、子の起動高速化は確認していません。

## コピー・確保・所有の実体

両案の初回基準はsegment 1個、Python ownerの保持FD 1個です。
配置表でzeroを表現し、zero領域のpayloadを保存しません。

| data file／配置 | 両案の実体化slot bytes | D1のSnapshot payload copy | D2のSnapshot payload copy |
| --- | ---: | ---: | ---: |
| 8 MiB／密 | 8,421,376 | 8,421,376 | 0 |
| 8 MiB／疎 | 557,056 | 557,056 | 0 |
| 64 MiB／密 | 67,141,632 | 67,141,632 | 0 |
| 64 MiB／疎 | 4,227,072 | 4,227,072 | 0 |

copy 0はSnapshot用payload転送の話です。seedのwrite、親blockの部分copy、hash用bufferへの
read、OS内部copyが0という意味ではありません。各子は両案とも96 KiBのslotを実体化し、
親からの部分copyは密80 KiB／疎32 KiB。D1はheap、D2は子専用segmentです。

64 MiB密のproducer Go累積割当はD1約64.9 MiB、D2約0.49 MiB、GCは5→0でした。
D2はpayloadをmmapへ置くためで、OSも含むメモリ使用量の削減を示しません。
**RSS・物理I/Oは今回未測定**です。

D2の初期mapping予約は実体化slotより14 block（224 KiB）多く、freeze時に未使用末尾を縮めます。
子は1 MiBを予約して96 KiBを使う固定上限の試作です。
D1の同じ`reserved_capacity_bytes`はallocatorの許容上限であり、全容量をheap確保した値ではありません。
`materialized_bytes`もslot bytesで、物理resident page量ではありません。
削除済みslotの再利用やsegment内部の詰め直しは実装していません。

## 終了条件ごとの判定

| 承認範囲 | 判定 | 確認した根拠と限界 |
| --- | --- | --- |
| 初回Snapshot→2子の内容・EOF・隔離 | 成立（部品範囲） | D1/D2各2,000操作を連続byteモデルと照合。EOF・負範囲・上限・zero write・shrink/regrow・全block上書きを確認。Pythonの独立モデルとも派生内容一致 |
| 親Close後の子・派生Q、途中失敗と回収 | 成立（限定ケース） | 開始済み2子を止めて親をCloseし、その後再開。Qが親FDを独立保持し、P Close後にQ→子が利用可能。終了後FD数が元に戻りscratch空 |
| 元期待値固定後の破損・配置異常拒否 | 成立（fixture） | 同size内容破損、配置swap、参照欠落、範囲外/overflow/負offset、identity不一致、余分/欠落file・segmentを拒否。元期待値を変更しない |
| copy量・実体化量・segment/FD数・検査量を区別 | 成立 | [生データ](d-snapshot-components-evidence/aligned/raw.json)。D2のpack bytesは全runで0。両案の全検証対象量は同じ |

新部品の[Go試験](d-snapshot-components-evidence/build-tests.txt)と
[プロセス境界38項目](d-snapshot-components-evidence/aligned/boundaries.json)がPASS。
producerの転送途中・freeze後の失敗、deferを通らないexit 42、receiverのopen後・unlink後・hash後失敗を注入。
私有stagingは呼出し側が回収します。OSを強制終了する全故障モデルを検証したわけではありません。

Closeとspawnの同時開始は各8回ともCloseが先行して拒否でした。
開始が先行するケースは上記のready待ち→親Closeで決定的に確認しました。
すべてのthread interleavingを探索したという主張はしません。
本部品は単一writerを前提とし、guest共有メモリのrace検証ではありません。
既存製品のoracle・生成物・source ownershipは変更していません。

## 未完了の範囲と推薦への影響

- **Ubuntu x86_64：SKIP。** 利用可能DockerはLinux aarch64。ネイティブx86_64測定は未実施。
  DでOS差が減るという問いは未解決で、採用前の確認条件として残る。
- **実guest：未接続。** 正常終了後の対象fileと既存Exportの一致、実DBの準備・CRUD・Close、
  実際の汚れ方・更新量・並行FD・worker終了はこのfixtureで代替しない。
- **製品向けallocator／形式：未完成。** 配置表はblockごとのJSONで、zero領域にもentryを持つ。
  大規模でのmetadata費用、成長、FD上限、slot回収、深い世代、OOM/ENOSPC等は未評価。
- **保存/import・Go公開API：未接続。** 今回はPython ownerの内部受渡し部品。
  `snapshot_to`／外部importの契約や耐久性は変更も検証もしていない。
- D2の全体利益は64 MiB密で確認し、普通のCRUD用の実guestにも同じ利益があるかは未確認。
  D1を棄却しない。未使用領域が多ければD1も小さな転送で済むことを今回確認した。

したがって次へ進むなら、D2の有限な実guest接続spikeを設計し、
既存E・D1とのどの境界を比較するかとOS確認の扱いをHuman Reviewで決めます。
今回の結果を理由に全面VFS置換・正式採用・release準備へ進みません。

## 入力・再現・保存

- runtime baseline `source_commit`: `a8137b8b444f86068d3128a291e3a848adfdfd56`。runtime変更なし。
- 最終測定ソース `source_commit`: `d32b4ea9eed0299010dfa25496195b9c1d8ccd75`。
  [git_identity・入力hash・binary hash](d-snapshot-components-evidence/build-input.json)。build前に確認。
- 初回測定ソース `source_commit`: `ba84a3589ad1c64cf4338db3977d26d5ed0b0b79`。
  [初回identity](d-snapshot-components-evidence/initial-build-input.json)と[初回raw](d-snapshot-components-evidence/initial/raw.json)を別保存。
- 最終binary SHA256: `bff953d7c7c4b8853eed5002dd6ab041d2e59655f7585fabb3a13f71159c2209`。
- 所有元：[Go部品](../../benchmarks/spikes/d-snapshot-components/main.go.txt)、
  [モデル試験](../../benchmarks/spikes/d-snapshot-components/main_test.go.txt)、
  [Python owner・fixture・集計](../../benchmarks/spikes/d-snapshot-components/run.py)、
  [build](../../benchmarks/spikes/d-snapshot-components/build.py)。標準ライブラリのみ。

専用worktreeを本branchからprepareし、Go 1.26.8の実行fileを`SPIKE_GO`に設定します。
main checkoutから以下を実行します。workspace名は新しい未使用名へ読み替え可能です。

```sh
python3 scripts/experiment_workspace.py prepare d-snapshot-components --branch experiment/d-snapshot-components --min-free-gib 8 --budget-gib 3
spike_root="$PWD/build/experiment-work/d-snapshot-components"
python3 scripts/experiment_disk.py --work-dir "$spike_root" --min-free-gib 8 --budget-gib 3 --timeout 180 -- python3 "$spike_root/worktree/benchmarks/spikes/d-snapshot-components/build.py"
python3 scripts/experiment_disk.py --work-dir "$spike_root" --min-free-gib 8 --budget-gib 3 --timeout 180 -- python3 "$spike_root/worktree/benchmarks/spikes/d-snapshot-components/run.py" --binary "$spike_root/temp/component" --output "$spike_root/evidence/aligned" --scratch "$spike_root/temp/scratch"
```

buildは`.go.txt`をtempへ配置してgofmt・unit・standalone buildするだけで、生成Goを編集しません。
初回のrunner呼出しは相対pathを誤りbuild前に失敗し、以降はdisk guardで実行しました。
初回campaignはraw保存後の集計でNameErrorがあり、集計だけ修正して同じrawから復元しました。
後の再測定理由はD1の転送先変更であり、集計失敗のためのデータ選び直しではありません。
[時刻の整合・中央値の独立再計算](d-snapshot-components-evidence/audit.json)。
source/binaryを二回独立生成して一致確認したという作業ではありません。

最終の変更範囲public-source検査・Python構文・diff/statusを確認し、証拠はhash一覧とともに保存。
mainの既存未commit資料3件には触れず、実験branchへcommit/pushしてtemp/cache/worktreeをcleanupします。
製品runtimeが不変のため、広いSQL/ORM/Release Qualificationは実行しません。
