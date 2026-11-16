# 空Write省略と応答transportの対照 — 2026-11-16

## 結論と推奨

**空Writeと追加handoffの除去には成功したが、安定した全体高速化は未確認。今回は製品採用を見送る。**
特に「io.Pipeの空Writeを消せば、前回残ったwakeups負荷を解消できる」という期待を
今回の結果は支持しない。省略後もGetOrder単体が速くなる傾向はなく、Go pipe側の
全suite総CPUは5組すべて増えた。空Writeが唯一の主因とは言えない。

採用側の根拠はOS pipe全suiteの対応中央値−2.276%、Go pipe側−7.276%である。
しかし短縮は両者とも3/5組で、同時のAA変動と分離できず、Go側はCPU増加を伴う。
中央値の良い値だけを選んで速度改善としない。AA中央値をABから差し引かない。
OS pipeでの小さな効果の可能性は否定しないが、採用価値の確立には不足する。
今回の有限実験は完了し、同じ条件の追加反復、buffer設計、main統合、releaseは行わない。

## 過去との関係と固定入力

- 旧空Write試作 `c2cadc50d10b3d885d665437c9d3be4ea7ee3e0b` はOS pipeの
  wall−1.63%/CPU+1.68%で未採用。今回は同じmixed-vectorアルゴリズムを再利用した。
- 前回response-only対照 `10665616ba6f00d72b5563158a50bfb7cb2305d2` は
  syscall減少とthread wakeups増加を観測し、Go pipeで空Writeに対応する0byte Readが増えた。
  今回はその空Writeを独立要因として調べた。
- 製品基準source_commit `6558ee8fb2211313a8aa0ea6070ac5256767811a`。
- 今回の測定source_commit `aa2cfda3ca9d265a996bd5a2398b659ccab769fe`。
  初回build前と補正計測前にgit_identity.pyとclean状態を確認。
- Go1.27.4/macOS27.2.1 arm64、CGO0/GOMAXPROCS8/GOGC100、P8、MaxForks16、
  同期Close、UPDATE OF status＋SUM/audit、パラメータ補間、事前集約SQLを固定。
  元の70 assertionsを実行し、読取省略はしていない。
- 同一binaryの2×2: OS/Go応答pipe × 空Write省略off/on。
  要求側OS pipeは維持。binary、overlayのhashはJSONに記録。
- 一時Go overlayでwriteVecを変更。全て空の場合は元のWriteを維持し、混在時だけ空要素を省く。
  このhelperは全WASI writeVec呼出に影響し、stdoutだけに限定した変更ではない。
  guest C/Wasm、canonical生成コード、generatorは未変更。任意Writerの空Write副作用まで
  同値とは主張しない。製品化する場合はscripts/runtime_write.pyと正規生成への反映が必要。

## 計測方法の訂正（重要）

最初の固定88 timing processの終了後、experiment_workspaceのrun_guardedが
デフォルト0.5秒間隔でos.walkによる容量走査を行い、計測と並走することを確認した。
前回10665616の時間値にも同じ留保が必要。走査が変動の唯一の原因とは未確定。

そのため、元の全観測をscanning-guard-cohort/へ残し、**同一binary/順序/88processを
一度だけ再測定**した。容量走査を各プロセス前後、計時区間の外へ移し、900秒の有限予算と
各プロセス180秒timeoutを維持した。補正結果を見る前にこの手順を固定し、良い結果までの
反復はしていない。method-correction.md / timing-method.jsonに記録。
補正後もAA変動が残った。旧cohortと新cohortの差を容量監視の因果効果にはしない。

以下の性能判断は補正後cohortのみ。診断counter/profileは初回の別枠を保持し、時間値へ
混ぜない。短いprofileには監視並走の留保があり、kernelの直接計数でもwall分解でもない。

## 通信回数の診断

各4条件、fixture準備後のGetOrder4000を別processで実行。
各条件SELECT8000＋prepared制御opcode5が1回、8001応答frame。
要求722229bytes、応答6271607bytesで、各armの両端・全4arm間とも一致。

| 応答方式・省略 | guest Write | うち空Write | host Read | うち0byte Read |
|---|---:|---:|---:|---:|
| OS・off |16002|8001|16002|0|
| OS・on |8001|0|16002|0|
| Go・off |16002|8001|24003|8001|
| Go・on |8001|0|16002|0|

非空応答の転送回数・バイト数は変わらない。ゼロ長Writeに対する余分な同期をなくせても、
header/bodyの読み取りや非空応答・要求のやり取りは残る。

## 補正後の固定対照結果

各workloadは4warmup＋OS-AA/OS-AB/Go-AA/Go-ABの各5pairs。
block順はseed119でshuffle、pair内順は交互。queryと全suiteで計88process。
AAは同じpipe・省略off同士、ABは同じpipeでoff→on。各値は対応変化率中央値。

| 対象 | OS省略AB | OS AA | Go省略AB | Go AA |
|---|---:|---:|---:|---:|
| GetOrder4000時間 | +2.085% (1/5短縮) | +1.934% (1/5短縮) | +1.134% (2/5短縮) | -3.803% (5/5短縮) |
| 70テストsuite時間 | -2.276% (3/5短縮) | -2.472% (3/5短縮) | -7.276% (3/5短縮) | -6.027% (4/5短縮) |
| suite process wall | +1.410% (2/5短縮) | -8.333% (4/5短縮) | -7.876% (4/5短縮) | -9.353% (4/5短縮) |
| suite process CPU | -0.051% (3/5短縮) | -1.576% (3/5短縮) | +2.485% (0/5短縮) | -3.319% (3/5短縮) |

| suite変化率の全範囲 | OS | Go |
|---|---:|---:|
| 省略AB | -10.940〜+3.705% | -31.963〜+35.451% |
| AA | -12.228〜+33.873% | -14.439〜+10.384% |

独立中央値と対応中央値は別統計: OS suite483.395→464.091ms、Go469.483→470.540ms。
Go suite対応中央値−7.276%と独立中央値の微増を混同しない。
Go側CPUは対応中央値+2.485%、全5pairで+1.894〜+5.911%。
queryのCPUはsetup/cleanupを含むprocess全体であり、SQL単独CPUではない。
前回の比較先製品の時間値を流用せず、差10%達成とは主張しない。

## 補助profileと限界

各条件4000GetOrder、1profileのみ。Go pipeのpthread_cond_signalは省略offで
0.72s/58.06%、onで0.77s/60.16%。OS pipeのrawsyscallnは0.87s/67.44%→0.79s/66.39%。
総sampleはOS1.29→1.19s、Go1.24→1.28s。単発sampleと監視並走のため、正確な削減量の
証明にしない。少なくとも空Writeをなくしても大きなwakeups経路は観測される。

base両armの既存＋mixed/all-empty/partial/error/FD・memory検証、closed OS file、
mixed Go pipeとclosed Go pipe all-empty、新旧guest境界testsがPASS。
実guestの意味確認は4条件PASS。初回88＋補正88の全timing processがPASS、
88回の70-test suiteで6160test bodies、正常Closeのerror検査も維持。
約69秒の尾部再発はなし。過去の原因解消とは扱わない。

Go pipeのbackpressure、closed-pipe error identity、全fault/errno/実guestの
cancel/crash/export interleavingの同等性は未認定。Mac/Go1.27のみで、製品Go1.26.10や
Linux/Windowsの受入れではない。今回の有限な機構調査と製品候補化は別判断。

## 次の判断・再現

空Write単独は小さな改善候補として保留し、io.Pipeへ替える根拠にはしない。
この経路をさらに追うなら、通常の非空応答で残るhandoff/起床を減らす別の設計が必要で、
今回の結果だけでbuffer追加・要求batchingを正当化しない。
同じ共有環境で短い測定を繰り返すだけの継続は推奨しない。

測定sourceのworktreeをmanaged workspaceへ置き、run.pyを兄弟evidence/に配置。
make_overlay.pyがbaseのpreimageを検査しoverlayをtemp/へ生成し、unit/guest/harnessをbuild。
原run.pyは初回cohortを再現する記録。性能を再測定するときはbuildとdiagnostic終了後に
同一binaryに対してtiming_without_scan.pyを実行し、別の再帰監視を並走させない。
analyze.pyが補正cohortを再計算する。全raw trace/log、旧cohortも保持。
SHA256SUMSは相対パスで証跡を検証する。

結果ブランチは実験用。whole-branch merge、canonical/provenance更新、releaseは未実施。
