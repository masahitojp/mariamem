# 子Fork起動・Closeの費用帰属

## 現時点の結論

**Human Reviewで求める判断は、残件#2「子Fork起動・Closeの計測→原因特定」を完了として受理すること。推薦は受理。**
両native OSの固定40実行ずつを照合し、Forkの主な費用がMariaDB再初期化、DB Closeの主な費用がguest終了とlinear memory解放であるところまで特定した。
基準DBファイルの全量コピーや最終worker joinが主因だった、という結果ではない。
macOSのGo経路には約17msのOS確認もあるが、Ubuntuでは約0.04msで、この費用を横展開しない。

**最も強い留保は、細分化した観測そのものの費用と少数試行により、内訳を削った場合の改善量までは確定できないこと。**
ただし終了条件は費用帰属までで、修正候補の効果実証ではない。通常値/観測値を分け、個別関数のwall比率・tail確率の保証をせずに今回の調査を閉じる推薦は変わらない。
Human受理はまだ記録していない。最適化候補を選ぶ場合は別の判断とする。

DB自体のCloseとSQL切断待ちを分ける必要がある。macOSのDB Closeは約2–3ms、UbuntuはGo約4–5ms・Python約5–6msだった。
今回、最適化・接続数変更・main統合・Qualification・公開は行わない。

## Human決定：次の最適化範囲（2026-10-18）

この費用帰属を起点とする0.5.xの作業は、以下の順序・範囲とする。

1. **Ubuntu・10MiBの並列起動を限定調査**。起動同士の競合と他の子のSQL/終了との重なりを
   区別し、主要な伸長要因を特定する。1子の待ち時間と4子全体の実経過時間を共に扱う。
2. **macOSのOS確認結果を再利用する小修正と効果確認**。DB内部を変更せず、対応OS拒否、
   キャンセル・失敗処理、並列起動時の正しさを維持する。

**guest初期化の改善候補選定は0.7.xへ延期**する。0.5.xの原因調査で得た証拠を引き継ぎ、
メモリ確保・拡張、照合順序情報などの方式選定・改善実装へ自動的に進まない。
この決定は実施範囲の承認であり、いずれもまだ未着手。main統合・リリース承認ではない。
下記の「候補登録のみ」はこの承認前の経緯として残す。

## 追加した最適化調査候補（2026-10-18）

Humanの指示により、**Ubuntuの4並列時にguest初期化が伸びる原因**を候補へ追加した。
候補登録であり、追加実験や修正の開始を意味しない。

- 観測ありの `l4m_open→ready準備` は、Light直列60.62ms、10MiB直列65.84ms、10MiB4並列133.95ms。
  「61→134ms」はデータ規模が異なる。並列化の比較には同じ10MiBの **65.84→133.95ms** を使う。
- 通常実行の同じ10MiBでは、1子のFork中央値70.47→139.77ms。一方、4子の起動・SQL・切断・Closeの
  実経過時間は989→538ms（各3試行の中央値、親準備とSnapshot作成を除く）。1子の遅延とスイート全体の利益を分ける。
- 現行harnessは各workerがFork→SQL→切断→Closeを進め、全子readyのbarrierを設けていない。
  他の子のSQL/終了と初期化が重なり得る。CPU/scheduler、メモリ帯域/GC、内部同期、他段階の重なりの寄与は未特定。
  テスト不具合または不可避な競合と断定しない。
- 選定時に閉じる問いは、起動だけの競合とスイート中の他段階との競合を区別し、主要な伸長要因と
  対応候補を示せるか。1子のFork時間だけでなく4子全体の実経過時間も評価する。
  この候補の存在を、完了済みの費用帰属調査を未完了へ戻す理由にはしない。

根拠は下記Ubuntu集計と、同evidenceの `campaign/go-medium-{0,1,2}-control.json`、
`campaign/go-parallel-{0,1,2}-control.json` の `instance_suite_wall_seconds`、
および `benchmarks/child-lifecycle/main.go` のworker loop。

## 入力と方法

- main基点: `df90c096a269d448a50ac44ac92f88e47619d58e`。
- control: `9cedaa76720336ec8304b9db7f28d6b1174b13b6`。mainのruntimeを変えず、既存ownedpreparedから同じSQL oracleを使うobserverを追加。disconnectとDB Closeを分離。
- observed: `0a36f304b5b4c940f15359ce9e35a97db9512869`。手書きadapter/hostとtimingの時刻観測のみ。
- macOS campaign harness: `6cb4d76`。4バイナリのcommit刻印・clean状態・Go1.26.8・CGO無効を実行前に検査し、終了後のbinary hashも一致。
- guest: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`。v0.5.2と同じ。guest・Generated Go・release入力101ファイルのhashを保持し、control/observed間の差分ゼロを確認。
- native macOS27.0.1 arm64 / Apple M1・8 logical CPU・16GiB、Go1.26.8、Python3.14.8、PyMySQL1.2.3。
- Go Light/10MiB/100MiB直列4子、10MiB4並列を各3対。Python sharedhost small/medium各3対、100MiBは1対（16子）。通常/観測の順を交互に反転。
- 以上38実行に、LightのFork/Closeを各24子観測する別CPU-profile実行2件を加え、計40実行。
  profile試行を通常値へ混ぜない。Go/Pythonはschemaが異なり、言語間の速度順位は比較しない。
- 全て実guestの接続・読み取り・独立した子のcommit/rollback・SQL pool切断・Snapshot/DB終了とscratch cleanupを通過。
  Pythonでは同一host再利用と最終host回収も既存oracleで確認。接続poolを切断済みの通常Closeが対象で、実行中queryを伴うClose全般を測ったものではない。

[入力・observer差分](child-lifecycle-attribution-evidence/macos/inputs.json)、
[4 build receipts](child-lifecycle-attribution-evidence/macos/builds.json)、
[40実行のreceipt](child-lifecycle-attribution-evidence/macos/campaign/receipt.json)、
[全集計と範囲](child-lifecycle-attribution-evidence/macos/campaign/analysis.json)、
[保存時の原本/保存後hash](child-lifecycle-attribution-evidence/macos/preservation.json)。
区間medianの合計と全体medianは一致しない。子の観測件数は独立したプロセス試行数ではない。

## 通常の利用者時間

観測を無効にしたcontrol。Go各行は3プロセス×4子の子12件の中央値。
Python small/mediumは3プロセス×2子、100MiBは1プロセス×16子の中央値。
単位ms。Closeにdisconnectを含めない。

| 条件 | Fork | SQL切断＋完了待ち | DB Close |
| --- | ---: | ---: | ---: |
| Go Light / 直列 | 54.16 | 6.26 | 2.46 |
| Go 10MiB / 直列 | 56.70 | 6.25 | 2.09 |
| Go 100MiB / 直列 | 60.08 | 6.26 | 2.12 |
| Go 10MiB / 4並列・1子 | 89.48 | 5.08 | 2.72 |
| Python small | 52.59 | 6.71 | 2.71 |
| Python medium | 47.76 | 0.29 | 2.94 |
| Python 100MiB / 16子 | 54.95 | 7.86 | 3.37 |

従来のGo observerは `disconnect(child,p); child.Close()` を一つのchild_closeとしていた。
Python observerは別区間だった。従来の約10msを全てMariaDB終了の費用と解釈するのは誤り。
Go `WaitDisconnected`、Python `wait_disconnected` はどちらもactive接続を5ms間隔で確認する。
今回の切断待ちの値と整合するが、sleepとguestの接続後始末の厳密な寄与までは分けていない。
これはDB Closeの帰属と区別する。

## Forkで何を繰り返しているか

観測ありGo直列各12子の区間中央値、単位ms。

| 処理 | Light | 10MiB | 100MiB |
| --- | ---: | ---: | ---: |
| OS/platform確認、合計 | 17.49 | 17.39 | 18.36 |
| 基準Rootの取得・構造確認 | 0.027 | 0.124 | 0.973 |
| 子FSのprepared handle接続等 | 0.098 | 0.334 | 2.240 |
| linear memory初期化（mapping＋生成constructor） | 1.559 | 1.521 | 1.544 |
| guest実行開始後〜readyヘッダ受信 | 34.69 | 36.18 | 39.04 |
| ↳ guest内l4m_open開始〜ready準備 | 34.38 | 35.86 | 38.70 |
| ready decode＋listener準備 | 0.099 | 0.104 | 0.155 |
| API側の残り（host外・OS確認外、診断出力を含む） | 0.868 | 1.052 | 1.148 |
| Fork API全体（観測あり） | 55.93 | 57.53 | 63.87 |

- `mariamem.start → artifacts.ValidatePlatform → host.StartGenerated → artifacts.ValidatePlatform` で、
  macOSの `/usr/bin/sw_vers -productVersion` が2回。Python sharedhostはhost側の1回でsmall/medium約9ms。
  外部commandの待ちをhost/startup traceより外側で明示的に捕捉した。Ubuntuは `/etc/os-release` 読み取りで別経路。
- `Owned.Acquire → Root.Check` は所有権・構造の確認。
  `MapPreparedHandles → mapRoot` はCOWの子FileStore/descriptor表現を作る。全内容を読み直すhashではない。
  大規模で増える部分はあるが、Lightでも残る30ms台の主因ではない。
- guest引数は `mariamem`。旧 `--restore-snapshot` のguest内ファイルコピーはこの経路では実行されず、
  guestのrestore_begin→restore_completeはほぼゼロだった。
- guestの区間はguest内monotonic clockのduration。hostとguestの絶対時計を同一と仮定せず、durationのみ比較した。
  memory初期化後〜readyとguest_main〜ready準備の差は直列中央値約0.28–0.30msで、独立の名前付き処理へは割り当てない。
- 10MiB4並列ではguest内open〜ready準備が約54.68msへ伸びた。baseline取得0.174ms、prepared接続0.506ms、
  memory初期化のconstructor約2.01msも観測。並列時はtraceの重なりから親子を推測せず、同一trace内の区間だけを集計。
  CPU競合/スケジューリング/ファイルアクセス等の個別要因をこの差だけで断定しない。

## MariaDB起動の中の根拠

Light・24子の別CPU-profile試行（100Hz）は合計108 samples / 1.08 CPU秒。
[累積](child-lifecycle-attribution-evidence/macos/campaign/profile-fork-cum.txt)、
[flat](child-lifecycle-attribution-evidence/macos/campaign/profile-fork-flat.txt)、
[全merged samples](child-lifecycle-attribution-evidence/macos/campaign/profile-fork-raw.txt)。

| profileで確認したstack | 累積sample CPU | 読めること |
| --- | ---: | --- |
| `Fn244 l4m_open → Fn5726 mysql_server_init → Fn5560 init_embedded_server` | 0.81秒 | guestのserver再初期化がサンプルの中心 |
| `Fn152 dlmalloc` | 0.48秒 | 初期化に伴うguest heap確保が大きい |
| `MemoryGrow → MemoryMapping.Grow → syscall.Mprotect` | 0.35秒 | guest heap拡張がhost側の保護変更を呼ぶ |
| `Fn456 my_uca_info_init`（my_coll_init_uca等から） | 0.28秒 | 文字の照合順序情報の初期化も寄与 |

これらはstackが包含・重複するため合算しない。wall比率でもなく、sw_vers子プロセスのCPUも含めない。
`runtime.memclrNoHeapPointers` のflat 0.19秒も観測したが、別個の19ms処理があるという意味ではない。
時間を要しているのは主に初期化時の仕事であり、DBのファイル内容をhostの保存先へ運んでいる待ちではない。
個別collation/pluginごとのwall時間や、mprotectの回数は今回直接計数していない。

関数名は採用guestに結び付いた既存symbol mapで照合した。
map SHA256 `9072658996738894b86effc9b60911db92b413d35cb3c7863f3851666bb645b6` は
[既存map](v050-ad-integration-evidence/function-map.txt)と `release/generated-license-evidence.json` に一致。
[使用したsymbol対応](child-lifecycle-attribution-evidence/macos/symbols.json)も保存した。

## Closeの帰属

観測ありGo直列の中央値。各列の和はwhole medianと一致しない。単位ms。

| 処理 | Light | 10MiB | 100MiB |
| --- | ---: | ---: | ---: |
| admission停止 | 0.019 | 0.023 | 0.023 |
| host session workerのdrain待ち | 0.002 | 0.002 | 0.002 |
| shutdown要求〜guest rootが戻るまで | 1.283 | 0.842 | 0.934 |
| 最終guest worker join | 0.001 | 0.001 | 0.001 |
| startup診断の回収 | 0.007 | 0.008 | 0.010 |
| linear memory解放（再join確認＋munmap） | 0.930 | 1.031 | 0.995 |
| descriptor/prepared handle解放 | 0.001 | 0.001 | 0.001 |
| 以後のhost側（診断ファイル出力・transport完了・transfer削除等） | 0.444 | 0.472 | 0.500 |
| DB Close API全体（観測あり） | 3.023 | 2.685 | 2.843 |

source経路は `Database.Close → Server.Close/finish → Process.Shutdown/stop → guest mainのslot停止/join・l4m_close → executeGuestのWaitThreads → releaseMemoryModule → CloseDescriptors/PreparedFiles.Close → transport完了 → temp削除`。
slot停止/joinとl4m_closeはguest-root区間として測定し、その中の個別wall時間は分けていない。
CPU-profileは短いClose24回の全てでsampleゼロ。CPU消費ゼロ・安全性の証拠とはしない。
wallの区間帰属は取れているが、Close内部のCPU割合は未判定。

## 観測費用と未確定

- Go直列はcontrol→observedでFork約54.16→55.93ms（Light）、60.08→63.87ms（100MiB）。
  Closeは2.46→3.02ms、2.12→2.84ms。観測によるファイル出力・guest診断・スケジューリング差を含むため、
  本番の内訳をサブmsまで正確に再現したとはしない。各対の値・min/maxも全て保存。
- Python smallのForkは逆に観測側の中央値が小さい。観測が軽量化したとは解釈しない。
  少数対の条件差が混じり、固定の観測税を一律に引くこともできない。
- Python100MiBは1対だけ。16子を16回の独立キャンペーンと数えない。
- 正常なquery、切断、協調終了だけを扱う。非協調worker、異常終了、全guest race censusや一般意味論の再評価は対象外。
- Ubuntu内訳も下記の専用40実行で照合済み。既存Ubuntu性能246実行を今回の内訳証拠へ読み替えていない。

## 検証と状態

| 項目 | 状態 | 証拠 |
| --- | --- | --- |
| clean cloneと4 binaryのexact commit/hash | PASS | builds.json、campaign/receipt.json |
| 固定40実行・SQL/transaction/子独立性・協調cleanup | PASS（このfixture） | 全40 JSON、Pythonの既存結果/Goの全operation |
| startup/instance/closeとguest診断の件数・境界照合 | PASS | reduce.pyとanalysis.json。parallelは同一scope内だけ |
| identity/trace失敗oracle | PASS | test_tools.py（誤刻印・欠損・dirty・非単調traceを拒否） |
| focused host/artifacts/timing/API tests | PASS | focused-host-tests.txt |
| controlled guest trap/joinとmemory failure cleanup | PASS | focused-runtime-tests.txt |
| Ubuntu nativeの内訳確認 | PASS（限定scope） | [CI run 39083277771](https://github.com/masahitojp/mariamem/actions/runs/39083277771)、原本1478ファイルと40実行・全trace/集計を独立照合 |
| 最適化・product candidateの生成guard/独立再生成・最終Qualification | 今回対象外 | guest/Generated Goは不変。診断差分を製品採用しない |

生成所有元のruntime_instance.go/memory_backing_unix.goは実験branchだけで観測変更した。
release inventoryを観測用に再pinしてguardを通した扱いにはしない。将来の製品修正は所有元・inventory・再生成を別途扱う。
公開API/保存契約/strict失敗oracleの変更はない。通常ガイドの保証との新しい矛盾はない。

## 計測環境の失敗と再実行

1. sandboxでTCP listenが拒否された。実行失敗として保存し、権限を得て再実行した。
2. main配下のlinked worktreeでGo1.26.8が外側mainのcommitを刻印した。
   リポジトリ外のlinked worktreeでも刻印が欠落した。toolchainのvcs root判定は `.git` directoryを探索し、
   worktreeの `.git` fileを拾わない。通常cloneから `-buildvcs=true` でビルドし直し、4つの正しい刻印を確認した。
   最初の40実行は時間の良否で選ばず、全体を性能結論から除外。
   [reject台帳と原本hash](child-lifecycle-attribution-evidence/macos/rejected-campaign-summary.json)を残し、compact rawはlocal evidenceに保持。
3. 最初のfocused test中にsource編集とvetが重なりimport不一致を出した。
   編集を終えたclean observed cloneでfocused host/runtime checksを再実行してPASS。初回FAILをPASSへ再ラベルしない。

## 再現と引継ぎ

`benchmarks/child-lifecycle/build.py WORKSPACE --go /exact/Go1.26.8/bin/go` は、固定control/observed commitを
freshな通常cloneへ展開してbuildする。`campaign.py --workspace WORKSPACE` で同じ有限40実行、
`reduce.py WORKSPACE/evidence/campaign` でoffline照合。
macOSのraw source inputs/binary hash/build commands/全試行/全merged profileは上のevidenceにある。
pathと出力の行末空白だけ正規化し、原本と保存後のhashを保存した。per-call protobuf原本48個はcompact local evidence、
公開資料には全merged samplesをtextで保存した。binary/cache/source cloneは再作成可能なので保持しない。
Ubuntuも同じpin/SQL/終了条件で実行し、下記の照合を終えた。今回のHuman Reviewは調査結果の受理で、製品修正の採用判断ではない。

## Ubuntu照合結果（2026-10-18）

### 証拠と入力

- [run 39083277771 / job 117544494198](https://github.com/masahitojp/mariamem/actions/runs/39083277771/job/117544494198)、全step success、cleanup stepもsuccess。
- harness source commit `e4a5522ca475f73b56f23b08a725354eafb81b19`。control/observedの固定commitはmacOSと同一。
- Ubuntu24.04.5 x86_64、kernel6.17.0-1022-azure、runner image `20261012.334.1`、Go1.26.8、Python3.14.8、PyMySQL1.2.3、CGO無効。
  CPU機種・core数はこのcampaignのartifactには記録していない。macOSとの絶対値差をOS単独の効果としない。
- artifact ID `12120345304`、ZIP689255 bytes、SHA256 `a21090cd70cedd4791e5eeedddc75c0f6b813c73453cd7adf2d005e5126a2027`。
  GitHub metadataのdigestと実ZIPを照合し、1478原本ファイル全てをZIP contentsと照合した。
- 40実行のcase名・寸法・operation数、4 buildのsource stamp/hashと実行receiptを照合。
  pinnedなoffline集計を再実行し、保存された全aggregateと一致。
  binary本体はCI cleanup済みでartifactにない。ここで行ったのはCIが記録したpre/post hashとstampの照合であり、ダウンロードしたbinaryの再hashとは主張しない。

[CI receipt](child-lifecycle-attribution-evidence/ubuntu/ci-receipt.json)、
[独立照合結果](child-lifecycle-attribution-evidence/ubuntu/verification.json)、
[build records](child-lifecycle-attribution-evidence/ubuntu/builds.json)、
[40実行receipt](child-lifecycle-attribution-evidence/ubuntu/campaign/receipt.json)、
[全aggregate/min/max](child-lifecycle-attribution-evidence/ubuntu/campaign/analysis.json)、
[CI job log](child-lifecycle-attribution-evidence/ubuntu/ci-job.txt)、
[原本/保存後hash](child-lifecycle-attribution-evidence/ubuntu/preservation.json)。

### 通常値と観測した内訳

通常値はcontrol、単位ms。Go各行3プロセス×4子、Python small/medium各3プロセス×2子、100MiBは1プロセス×16子の子の中央値。

| 条件 | Fork | SQL切断＋待ち | DB Close |
| --- | ---: | ---: | ---: |
| Go Light / 直列 | 65.75 | 5.26 | 4.88 |
| Go 10MiB / 直列 | 70.47 | 5.27 | 4.15 |
| Go 100MiB / 直列 | 72.75 | 5.33 | 4.28 |
| Go 10MiB / 4並列・1子 | 139.77 | 5.22 | 5.04 |
| Python small | 65.70 | 0.46 | 6.02 |
| Python medium | 65.43 | 0.33 | 5.28 |
| Python 100MiB / 16子 | 71.32 | 0.35 | 5.40 |

観測ありGo直列各12子の内訳、単位ms。下位区間の包含とmedianを合算しない。

| 処理 | Light | 10MiB | 100MiB |
| --- | ---: | ---: | ---: |
| OS/platform確認合計 | 0.038 | 0.040 | 0.046 |
| 基準Rootの取得・構造確認 | 0.028 | 0.204 | 1.724 |
| 子FSのprepared handle接続等 | 0.079 | 0.431 | 3.301 |
| linear memory初期化 | 1.713 | 1.767 | 1.797 |
| guest実行開始後〜readyヘッダ受信 | 61.17 | 66.39 | 65.32 |
| ↳ guest内l4m_open開始〜ready準備 | 60.62 | 65.84 | 64.83 |
| ready decode＋listener準備 | 0.105 | 0.107 | 0.109 |
| Fork全体（観測あり） | 63.62 | 69.42 | 72.75 |
| shutdown要求〜guest rootが戻るまで | 2.334 | 1.438 | 1.429 |
| 最終guest worker join | 0.001 | 0.001 | 0.001 |
| linear memory解放（再join確認＋munmap） | 2.170 | 2.300 | 2.638 |
| descriptor/prepared handle解放 | 0.002 | 0.002 | 0.002 |
| resources解放後のhost側 | 0.235 | 0.255 | 0.264 |
| DB Close全体（観測あり） | 5.025 | 4.169 | 4.553 |

4並列ではguest内open〜ready準備が133.95ms、prepared接続0.722ms、constructor2.730ms。
延びる主な観測区間もguest起動側だった。これをCPU競合だけの証明としたり、1子のdurationを4子全体のwall時間へ読み替えたりしない。
Root取得・接続の大規模時の増分も保存し、ゼロとはしない。

### CPU profileと両OSの共通/相違

Ubuntu Fork24子の別profileは205 samples / 2.05 CPU秒。
[累積](child-lifecycle-attribution-evidence/ubuntu/campaign/profile-fork-cum.txt)、
[flat](child-lifecycle-attribution-evidence/ubuntu/campaign/profile-fork-flat.txt)、
[全merged samples](child-lifecycle-attribution-evidence/ubuntu/campaign/profile-fork-raw.txt)。
`l4m_open → mysql_server_init` は累積1.49秒、`init_embedded_server` は1.47秒。
`my_uca_info_init` は0.52秒、`buf_page_is_corrupted` は0.34秒、`MemoryEA` は0.66秒を含む。
これらは包含・重複し、wall比率や独立した削減可能量ではない。
文字照合情報構築、guestメモリアクセス/確保、InnoDBのページ処理という起動時の仕事を示す。
InnoDBのページ処理を、廃止済みのSnapshot全量再走査と混同しない。
macOSで大きかったheap拡張/mprotectの比率を、Ubuntuの比率と同一とはしていない。

Ubuntu Close24子は14 samples / 140 CPU msと少ないが、うち80 CPU msが
`releaseMemoryModule → MemoryMapping.Close → Munmap` stack。
[Close累積](child-lifecycle-attribution-evidence/ubuntu/campaign/profile-close-cum.txt)、
[Close全merged samples](child-lifecycle-attribution-evidence/ubuntu/campaign/profile-close-raw.txt)。
wallでもこの区間は約2.2–2.6msで、メモリ解放が主要部分である裏付けになる。
14 samplesから正確なCPU割合を一般化しない。macOSはsampleゼロのままとし、Ubuntuの結果で補完した扱いにしない。

共通して、**Snapshotのファイル表現を再び高速化するだけでは、Forkの主な時間は消えない。MariaDB再初期化が次の共通の検討対象**になる。
macOSの二重OS確認は別の小さな候補。どちらも今回は修正の方式・費用・効果を決めておらず、自動着手しない。

### 観測費用と調査の終了条件

Ubuntu Lightはcontrol→observedでFork65.75→63.62ms、Close4.88→5.03ms。
4並列はFork139.77→149.89ms、Close5.04→6.31ms。
観測の影響と条件差が混じるため、固定の観測税を引いた推定値は作らない。
Python100MiBが1対、Goが各3対という少数試行の限界もmacOSと同じ。

| 終了条件 | 判定 | 到達点/限界 |
| --- | --- | --- |
| Forkの所有基準取得・host/FS・memory・guest・readyの費用帰属 | 完了 | 両nativeの全trace/件数/集計を照合。guest起動が主で、macOSにはOS確認もある |
| Closeと接続切断を分離し、終了・join・解放・cleanupを帰属 | 完了 | guest root終了とlinear memory解放が主。guest内slot joinとl4m_closeの個別wall割合は未計測 |
| 通常利用のSQL・transaction・子独立性・協調cleanup | 完了（限定fixture） | 両OS40実行ずつの既存oracle。一般的な異常終了の保証にはしない |
| 観測あり/なしとprofileを分離 | 完了 | 全値保存。sample不足と少数対を明示 |
| 追加の原因調査が必要なblocker | なし | 合意scopeに、効果実証・全plugin wall比率・tail確率保証は含まれない |
| 修正候補の選定/実装/採用・最終Qualification | 今回対象外 | Humanの次の判断で扱う |

**今回の調査は完了条件を満たす。受理・クローズのHuman判断は未記録。**
より細かな関数のwall時間がないことを理由に今回の調査を無期限に継続する推薦ではない。

### Reviewの確認範囲

- 採用前提: 同じ固定入力、失敗oracleの維持、有限cohort、両native照合、観測費用の分離は満たす。
  修正の採用・main統合・Release承認とは分ける。
- 検出網: stamp/trace失敗は既存4 unit tests、case/寸法/operation欠損とaggregate差は
  [offline照合recipe](child-lifecycle-ubuntu-verify.py.txt)で検出。観測の代表性や将来のspeedupはCIでは証明しない。
- 公開ガイドの契約/API変更はなし。生成Goとguestは不変、実験の手書き観測差分を製品へ取り込まない。
  inventoryを緩めたり再pinしてQualification済みにした箇所はない。
- 未実施の境界: pool未切断でのClose全般、非協調終了、別Go版、macOS15の最終Qualification。
  今回の費用帰属と、既存製品のサポート/Qualificationは同じ判定ではない。

原本ZIPを1478ファイルへ展開し、`python3 docs/reviews/child-lifecycle-ubuntu-verify.py.txt ZIP EVIDENCE` で同じoffline照合ができる。
保存時のpath/行末空白の変更はmanifestで原本と保存後のhashを別々に記録。
per-call protobuf48個は認証済みZIPへ保持し、公開資料には全merged CPU samplesをtextで残した。
追加のguest実行、main変更、公開は行っていない。

---

## 当初の実施範囲

### 調査範囲と終了条件

Humanが承認した残件#2は、子Fork起動と子Closeを計測し、時間を使う処理を特定すること。
最適化・契約変更・接続数調整・100MiB Go Fresh再調査・リリースは含めない。
基点はmain `df90c096a269d448a50ac44ac92f88e47619d58e`、実guestはv0.5.2と同じidentity。
既存Ubuntu246実行は再実行せず、集計済み区間と今回の内訳を区別する。

最初にmacOS arm64で、同じSQL oracleを使い、次を分ける。

- Fork: 所有基準の取得、host準備、DBファイルの接続、linear memory生成、guest起動、ready応答、wire listener。
- Close: SQL pool切断・WaitDisconnected、listener/session停止、guest shutdown、worker join、linear memory解放、descriptor/prepared handle解放、一時ディレクトリ削除。
- 既存Goのchild_closeにはdisconnectが含まれ、既存Pythonは別区間。比較前に揃える。

通常・観測ありを交互に比較し、観測費用を隠さない。CPU profileは別試行とし、
100Hz samplingの分解能を超えて個別の短いCloseの割合を断定しない。
生成Go・guestは変更せず、実験branchの手書きadapter/hostに時刻観測だけを加える。

有限campaign: Go Light/10MiB/100MiB直列4子と10MiB4並列を各3対、
Python sharedhost small/mediumを各3対・100MiBを1対、Lightのfork/close CPU profileを各24子。
機能oracle/identity/cleanup失敗、区間未取得、容量超過なら停止して未完了を記録する。
上限はbuild込み60分、各command300秒。必要な追加確認は同じ区間の具体的不足に限定する。
Ubuntuへの内訳の一般化はしない。native未実行ならSKIPとする。

終了時は各区間の実測、支配的な処理とCPU/待ちの根拠、未特定残差、観測限界、
次の判断を報告する。時間上限到達を調査完了にはしない。
