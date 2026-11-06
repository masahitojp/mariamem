# #65 native互換性の残件と製品化の境界

2026-11-07。今の判断は、**次をprepared入力境界の小さい検証（G1）にするか**です。
G1を先に行うことを推奨します。EXECUTEのcursor flag／iterationについて、旧経路の
明示的な制約とnative側の処理が一致しておらず、今回通ったCIはその値を変えていません。
一方、主要な往復・寿命が両OSで通ったので製品化を始めたい、という反論には理由があります。
ただ、この有限な差分を先に確定すれば、後の責務移設とSQL意味論の問題を切り分けられます。
製品化の設計用の棚卸しは進められますが、今回の整理だけではpublic実装・main採用を承認しません。

これは126観測のPASSを取り消す判断ではありません。**その範囲は完了、全互換性の受入れは未完了**です。
全opcode・全driver・全metadataの網羅的captureを新しい条件にはしません。
既存の[0.6.0受入れ方針][contract]どおり、固定した対応表、native／guestと宣言clientの根拠、
承認済み例外を区別し、未観測をUNVERIFIEDのまま残します。新しい具体的な差だけを有限に開きます。

## 対象を固定

Humanから今回指定がなかった項目は、会話と履歴から次のように復元しました。

| 項目 | 固定した対象 |
| --- | --- |
| レビュー対象文書 | `benchmarks/spikes/issue65-policy-fix/README.md` at candidate（digestは[E1]） |
| candidate | `ba3e092eced56ca67a5cf5a16e7e3a84a96df752` |
| 差分のbase | `ecfa4b15c6f634356f0634aa467bdc7d39306d53`（最後のNOT_READY観測） |
| guest／checked host source | `8f3e440ab78af570e489dd8d463cab1ed4c5aed8` |
| guest SHA256 | `4caa85d299410467f2656d6611df5dbeb518351927ac30b0216e516d277bf094`、UNQUALIFIED |
| macOS実行tooling | `5b4f5f49b35fc364128d94cde1f30c5e33742c4d` |
| 基準にしたmain | `61973daa19b6f665d7342338c3252dd7af61fc90`、現在のlatestとは主張しない |
| branch／証跡 | `experiment/issue65-policy-fix`、[CI42289241674][ci]、[保存した照合記録][E1] |
| 今回決めないこと | profileの緩和、実装採用、controller移設、main integration、version／release |

Git object typeを含むsource identity、CI head SHA／全3 jobs、保存済みruntime結果を照合しました。
このレビューでbuild・実験・CI再投入はしていません。旧guestのPASSを新guestへ移していません。

## すでに閉じた範囲

[E1]は22 lifecycle、88互換性＋38 limit観測、不一致0、既存FOUND_ROWS／UCAの2 controlsと
新しい3 controls、supporting checks／canonical installer22 testsを記録します。
macOSの固定参照とLinuxの281 Go/assembly/data filesが一致します。全ファイルを両OSで
compileしたという意味ではなく、staged source inventoryの一致です。両方のnative実行は別にあります。
localとCIで同じguest hashを再buildした事実は有効ですが、canonical release qualificationではありません。

| 確認済み | 代表oracle／範囲 |
| --- | --- |
| OUT command拒否・TLS／必須PROTOCOL_41拒否 | `TestLimitsCommands`／`TestLimitsCapabilities`、ERR／following PING。compression／DEPRECATE_EOFの非広告・maskも確認 |
| 個別packet上限・D3の代表経路 | `TestLimitsOutputPacket`のtext／binary exact0xfffffeとmax+1、`TestLimitsAggregate`の各40MiB・全value／row・EOF・peer PING・native queue peak65536 |
| 容量・入力・切断 | `TestCompatCapacity`／`LiveCapacity`、TCP／Pipeの満杯overflow・EOF、cold／warm header拒否 |
| preparedの代表状態・D2 | `TestCompatPreparedState`の5 subcases：type reuse、alias、LONG_DATA／RESET、名前付きmalformed string、CLOSE／unknown RESET |
| 拒否の副作用 | `TestPolicyRejectedResetPreservesPreparedSession`、login ERR→EOF→join、oversized-row ERR後の同一stream／peer継続 |
| Snapshot/Fork/Live | 既存14＋8の実験を新guestでも実行。model faultはmodelの帰属を維持 |
| D1の代表経路 | `TestCompatFatalEOF`の実deadline、idle peer切断、owner／cleanup原因保持、独立instance継続。partial input／slow outputのdeadline controlsも別に存在 |
| 保存・廃棄 | builder／runtime cleanup debt0。転送削除の確認は元のassessmentに保持 |

新しいhost data planeに通常のpacket parser／ERR serializerを戻した箇所は見つかりません。
`main.go.txt`のmysqlwire呼び出しは既知のpre-login `RejectCapacity`のみです。[H1]
C++ Manager全体の削減や性能向上は、この事実からは判定しません。

## 残件・検出網・置く段階

Gは互換性の固定、Pは実際のpublic routeの製品化です。段階の提案であり、新しい実験の承認ではありません。

| 項目 | 現時点の判断と根拠 | 現行CIの検出範囲／追加する有限なoracle | 段階 |
| --- | --- | --- | --- |
| EXECUTE flags／iteration | **source上の具体的な差**。旧`DecodeExecuteLongData`はflags=0、iteration=1を要求。[L1] 固定upstreamはflagsをcursor処理へ渡し、iteration4 bytesを読み捨てる。[N1][N2] candidate patch適用後もこのentryは同じ（[E2]）。実際の新guestでの誤入力結果・ユーザー被害は未再現 | `COM_STMT_EXECUTE(23)`を許可するpolicy単体テストや、FETCH28の拒否では捕まらない。既存raw helperはflags0／iteration1固定。[T1] count0／count1でflags1・その他bit、iteration0／2を送り、errno／following query／状態を確認 | **G1最優先** |
| SQL／command-specific境界 | header max+1は確認済みだが、PREPAREの空／exact1MiB、EXECUTEのbody、SET_OPTIONのexact2-byte body、LONG_DATA短body／chunkの意味論は同じ検査ではない。[L1][L2][T2] 累積long-dataに新たな上限を勝手に追加しない | `TestExecutePacketBudget`等は旧decoderの検査でnative fixtureへ届かない。既存の境界とエラー順序をrawで再使用。sourceの共通NET capと各handlerの制約を区別 | G1 |
| prepared失敗時の状態 | 基本alias／type reuseはPASS。failed PREPARE後のalias、途中までの型更新／truncation、zero-param suffix、short／surplus CLOSE・RESET、NULL／empty LONG_DATAの全既存vectorは未移植 | `TestLastStatementAliasPrepareFailuresDoNotFallBack`、`TestPreparedEveryTruncatedExecuteRetainsOwnedState`、lifetime／long-data testsは旧経路を保護。[L3] 名前付きD2だけを例外にし、他の失敗後の型／値／handle／following PINGを確認 | G1でheaderに直結する状態、残りはG2へ明示 |
| metadata／値のflags・charset | driver経由int／bytes-NUL／NULLと一部metadataは通るが、signed／unsigned、temporal、alias／charset／field flagsの既存paired vectors全体ではない。[T3] | `TestCapturedPreparedMetadataMatchesNativeExactlyAfterWireConversion`等は旧C API変換のtest。新routeにnative metadata/value oracleを付ける。oversized metadataを要求する前に、SQL／identifier制限下の到達可能性と長さをsourceで整理する。未実行を「到達不能」としない | G2 |
| 複数結果・OUT・SET_OPTION | 今回の40MiBは単一SELECT。CALLのnextset、PS_MULTI_RESULTS有無、MORE_RESULTS／PS_OUT_PARAMS、途中SQL error→次query、129結果の旧要件は別。[L4] | 現native13 groupsはそのchainを検査しない。旧chain／capability testsの代表caseを実接続へ移し、packet順序／終端状態とfollowing queryを確認。単packet size predicateのPASSでは検出できない | G2、profile固定前 |
| D1の残るclient状態 | deadline・idle peer・部分header・slow outputの既存controlsは有効。部分body／出力途中／buffered future commandのclient-byteと原因／cleanupの組合せ全体は未確認。[T4] | 既存controlsを土台に代表状態を補う。最終public owner APIではfirst cause・ErrUnusable・debt・wake-upを検査。legacy `TestIdlePingRejectsFailedInstanceWithOriginalCause`は旧ERR契約なので消さず、新D1用oracleを別に置く | G2で不足状態を限定、public wiringはP1 |
| credential／初期DB／charset | placeholder／root identityの代表caseはPASS。初期DB・charset・malformed loginと実driverの全設定ではない | native credentials test＋login error retirement controlは限定的。宣言clientのdefault pathと代表negativeを選び、不要な未知bit拒否など新契約を作らない | G2／P2 |
| 公開timeout・owner API | **製品化で必ず解消する差**。Go／Python既定QueryTimeout30sに対し、private OPENは100..10000ms。[P1][P2][P5] 30s指定での実験失敗は元のCIにも残る。[E3] 現公開経路のregressionとは主張しない | `test_fixture_deadlines_fit_fixed_guest_open_contract`は実験値を10s以内にするだけでpublic defaultを検査しない。P1ではdefault30sと既存受理設定、first-byte基準・古いtimer token拒否・owner causeを実public routeで検査 | P1の必須条件 |
| hostへの状態移設 | 方針は承認済み、実装は未完了。現在のslot／generation、guest timer／queue mechanismsはCpp Managerにある。[P2] Live／Fork resource所有はhostと対応 | 現22 casesを移設したrouteで再使用し、instance/session identity・retirement・総pending所有・capture fenceを保つ。単に既存CPPを削るtestではない。SQL/NET/THD/preparedとatomic gateはguestに残す | P1、1境界ずつ |
| public API／検出CI／生成物 | `mariamem.Start`→`host.StartGenerated`→`mysqlwire.Serve`が現公開route。[P3] 新native実装は専用cmdのfixture。canonical guestは6d7442…、native4caa…ではない | `HANDWRITTEN_FILES`／canonical inputs／owner tests／release provenanceを実装に結び直す。native経路がなくても通るlegacy CIだけでは不可。新routeを止めたnegative controlが選択suiteを落とすことを確認 | P1、採用前に両OS |
| 宣言consumer・例外・性能 | Go raw／driverの実験PASSは全Go/Python／ORMの受入れではない。既存Oracle26.7.0の2例外も新guestへ自動転用しない。[exceptions] | 既存要求profileを実public native routeに再bind。元のfunctional FAILとnative matchingを分け、OpenSSL環境SKIPをPASSにしない。性能は同じengine／UCAでlegacy/native、公開0.6.2との差は別要因を明記 | P2。性能／採用／Release CIはその後 |

[N1]のcursor pathは「cursor機能が新guestで動作確認済み」という意味ではありません。
sourceはflagを上流へ渡すこと、iterationをentryで検査しないことまでを示します。
新guestでのwire結果、後続状態、実clientでの到達頻度はG1で確認します。

## 以前の受入れ条件との照合

| 条件 | 判定 |
| --- | --- |
| D1 transport close＋owner cause／cleanup、独立instance | 実験の代表状態で満たす。実public APIの観測は未充足 |
| D2指定されたmalformed stringの空文字受容 | 同じ名前付きcaseを新guestでも確認。一般のmalformed入力への拡張は承認されていない |
| D3旧32MiB envelope除去、packet bound保持 | 両OSの40MiB／text-binary境界で確認。metadata／multi-resultの全意味論やRSS保証への昇格はしない |
| 10 commands／advertised capsと名付き例外 | 代表positive／OUT、handshakeの選択negativeは確認。EXECUTE内部fieldsは別の不足 |
| 原因oracle・既存の失敗を弱めない | 修正前NOT_READYを保存。既存legacy tests・accepted consumer failuresは削除していない |
| Snapshot/Fork/Liveの所有権と両OS | prototype22 casesで確認。public routeの再bind、実装owner変更後の受入れは未充足 |
| C++削減・性能・canonical adoption・release | 未実施。今回のCIの合格条件ではない。採用とreleaseの判断は別 |

根拠は[承認したD1–D3][decisions]と[責務・profile表][profile]です。
同表の43d96a62時点の「具体的gap」は歴史的観測であり、今回直した容量／window／policyを
未修正のままとは扱いません。P6の歴史的な「未完了」見出しも、現在のP6完了を再び開く根拠にはしません。
consumer例外そのものの適用条件は引き続き照合します。

## 次の有限な作業案

1. **G1：prepared入力の差分確認。** 固定guest4caa…を使い、header fields、SQL／PREPAREの空／exact／max+1、SET_OPTION body、
   failed prepare／truncation後の状態を、既存vectorの名前付き集合で観測する。D2は明示的に保持。
   sourceで判明したiteration等を「上流だから同じ」として閉じない。差が出ればその条件だけを
   guest境界の最小修正候補へ戻す。Go decoderや一般のwire fallbackは作らない。
2. **G2：metadata／result chainと残る代表状態。** 既存captured vectorsを使い、到達可能な
   metadata境界、CALL／OUT／terminal error、限定したD1／login状態をまとめる。全組合せの証明は要求しない。
   未観測を残す場合は既存scope内か、新たな明示的なHuman判断が必要かを各項目で区別する。
3. **P1：製品化。** public timeout／Err・cleanup API、host resource ownership、native pathを
   検出するCI、canonical生成物のownerを移す。SQL session／atomic admissionのguest権限を残し、
   C++ Managerを一度に移すのではなく1つの責務ごとに既存の寿命proofを保つ。
4. **P2：宣言profile・比較・採用。** public native routeで既存consumerと例外を再確認し、
   同条件の保守量／性能を評価する。採用、version、Release CIへの候補提出はそれぞれ後のHuman判断。

G1の提案費用はactive2h以内・tooling30min以内、local nativeとLinux CI最大1回、
builder/runtime各12GiB・free floor12GiB。新しいguest修正はこの「固定guestでの観測」には含めません。
直前CIはguest8分39秒、Linux9分23秒（queue外、[E1]）で、追加CIの待ち時間は約20分を目安にします。
これは測定済みのそのrunの値と次回の見積りであり、性能／完了時間の保証ではありません。
不足が出たら未観測／実行不備／契約差を分け、原本・source identityを保存して次の費用を示します。
**今回承認されたのは整理です。G1、build、追加CIはまだ開始していません。**

## Missing-things scanとレビューの限界

- **条件の抜け:** 上表に未充足／未確認を列挙。新たな例外の承認やmain採用を暗黙に得たとは扱わない。
- **現行usage docs:** 調べたversion-gated README／Go／Python／releasingに、新native routeを
  公開済みとする記載は見つからない。現行legacyのD1文言を先に消さない。実統合時に4文書を更新する。
  statusの古いNOT_READY／Linux pendingを現在地と誤読する箇所は、この整理に合わせて更新する。
  profile表の「multi-statement expansion」は全面禁止と読めるため、[既存の選択済みcapability／SET_OPTIONの契約][protocol]を保つ表現へ明確化する。
- **生成物owner:** frozen mainとの差分にcanonical source.patch／`internal/generatedgo`／`release/`
  の変更なし。新guestはdevelopment専用binding。[P4] nativeをcanonicalにした証拠はない。
  `release/baselines/`に新nativeのrelease pinがないことは、未選択releaseの欠陥ではない。
  将来公開0.6.2を比較baselineに使う際にtyped tag/source pinを作る。
- **未到達の境界:** G1/G2/P1/P2に明記。全client／全failure／public routeが通ったとは主張しない。
- **完了の誤認:** 両OSでのprototype実行・独立guest再build・281-file比較は確認済み。
  canonical qualification／public consumers／性能は別。候補adoptionとreleaseを混ぜた承認は見つからない。
- **コメント:** 当該修正差分・active fixtures・routeの範囲で、削除済みruntime挙動を現行と誤る
  in-code commentは見つからない。歴史資料のpendingを全面修正する作業はしていない。

今回の結論は互換性の残件・検出網・順序です。実際の新しいwire capture、consumer再実行、
metadataの到達可能性証明、controller再設計、全mainとの差分レビューは行っていません。
G1が新たに通ったという証拠にも、全体のGO判定にも使わないでください。

[E1]: issue65-native-compatibility-evidence/ci-42289241674.json
[E2]: issue65-native-compatibility-evidence/prepared-source-review.json
[E3]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/benchmarks/spikes/issue65-native-limits/evidence/ci-42266736265.json
[ci]: https://github.com/masahitojp/mariamem/actions/runs/42289241674
[contract]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/docs/decisions/v060-wire-contract.md
[decisions]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/docs/decisions/issue65-native-wire-contract.md
[profile]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/docs/design/issue65-native-protocol/contracts.md#observable-compatibility-profile
[exceptions]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/docs/decisions/prepared-consumer-exceptions.md
[L1]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/internal/preparedproto/values.go#L166
[L2]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/internal/mysqlwire/prepared_session.go#L96
[L3]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/internal/mysqlwire/prepared_failures_test.go#L15
[L4]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/internal/mysqlwire/prepared_chain_test.go#L70
[N1]: https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L3268
[N2]: https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L3509
[T1]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/benchmarks/spikes/issue65-native-compat/compat_test.go.txt#L189
[T2]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/benchmarks/spikes/issue65-native-limits/limits_test.go.txt#L116
[T3]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/benchmarks/spikes/issue65-native-capture/wire_test.go.txt#L101
[T4]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/benchmarks/spikes/issue65-native-compat/compat_test.go.txt#L403
[P1]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/mariamem.go#L47
[P2]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/guest/experimental.patch#L1419
[P3]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/internal/host/server.go#L207
[P4]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/scripts/generate_runtime.py#L135
[H1]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/benchmarks/spikes/issue65-compat-fixes/main.go.txt#L490

[P5]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/python/mariamem/__init__.py#L39
[protocol]: https://github.com/masahitojp/mariamem/blob/ba3e092eced56ca67a5cf5a16e7e3a84a96df752/docs/mysql-protocol.md#L5
