# 子Fork起動・Closeの費用帰属

## 現時点の結論

**macOSの計測・原因帰属は完了。Ubuntuの同じ内訳はCIへ引き継ぎ、残件#2全体はまだ完了扱いにしない。**
子を用意する待ちの中心は、基準DBファイルのコピーではなく、MariaDBを毎回開き直す処理だった。
macOSにはOSバージョン確認の外部commandもあり、Go経路では1回のForkに2回実行される。
DB自体のCloseは約2–3msで、従来GoのClose区間に含まれていたSQL切断待ちとは分ける必要がある。

**推薦は、Ubuntuの内訳照合まで済ませて費用帰属を閉じ、その結果で最適化対象をHuman Reviewすること。**
今回、最適化・接続数変更・main統合・Qualification・公開は行わない。
最も強い留保は、観測がCloseに約0.5ms以上の費用を加えていることと、macOS固有のOS確認費用を
Ubuntuへ移せないこと。通常値はcontrolで示し、観測値をそのまま製品の速度とはしない。

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
- Ubuntu内訳は結果未取得。既存のUbuntu性能246実行は外側の費用を裏付けるが、この内訳の代用にはしない。

## 検証と状態

| 項目 | 状態 | 証拠 |
| --- | --- | --- |
| clean cloneと4 binaryのexact commit/hash | PASS | builds.json、campaign/receipt.json |
| 固定40実行・SQL/transaction/子独立性・協調cleanup | PASS（このfixture） | 全40 JSON、Pythonの既存結果/Goの全operation |
| startup/instance/closeとguest診断の件数・境界照合 | PASS | reduce.pyとanalysis.json。parallelは同一scope内だけ |
| identity/trace失敗oracle | PASS | test_tools.py（誤刻印・欠損・dirty・非単調traceを拒否） |
| focused host/artifacts/timing/API tests | PASS | focused-host-tests.txt |
| controlled guest trap/joinとmemory failure cleanup | PASS | focused-runtime-tests.txt |
| Ubuntu nativeの内訳確認 | 未完了 | 専用CIへ引継ぎ。PASS/SKIPに置き換えない |
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
Ubuntuも同じpin/SQL/終了条件で実行し、結果が揃ってからHuman Reviewする。

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
