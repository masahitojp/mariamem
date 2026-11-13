# 別MySQLクライアントでtriggerなしINSERTを比較 — 2026-11-13

結論: go-mysqlのdatabase/sql経由・直接APIを試しても、現在のgo-sql-driver/mysqlから大きなINSERT改善は確認できなかった。直接APIはP8でペア中央値−0.189ms（−1.44%）、P1では+0.045ms（+0.63%）。現在のMySQLドライバだけがpgmemとの残差の主因という仮説を支持しない。

ただし素のgo-mysql v1.16.0はprepared実行の0x08 flagでmariamemに拒否されたため、下記の計測は**クライアント側の互換正規化を加えた診断値**。そのままライブラリを交換して同じ速度が出るとの主張ではない。推奨は現行ドライバを維持し、製品のprotocol互換対応や第三者ライブラリ変更の採用は別判断にすること。今回、製品修正・issue起票・一般driver適合試験は行っていない。

## 比較条件

全ユーザーtriggerなし、FK/CHECK/既存索引あり。前回f697c1aace4429163d76d27abd49953416856ab6のraw100明細INSERT probeを使用。親注文40件・入力配列・接続・BEGIN・PREPARE・COMMIT・検証を計測外にし、100回の再利用prepared INSERTとloopだけを計測する。

1. standard: go-sql-driver/mysql v1.9.3 + database/sql（従来）
2. stdlib: go-mysql v1.16.0の公式driver + database/sql（診断互換変更あり）
3. native: 同じgo-mysql/clientの直接API（診断互換変更あり）
4. pg: pgx/stdlib + database/sqlの参照値

親準備と全oracleは従来driver。全経路で親準備後に新しい測定接続を作り、1 transaction/1 statement/100 INSERTを実行。4個の入力はint64、各INSERTのaffected rows=1をassert。Mariaの3経路は同じbinary・同じmodule graph・同じcallback形式を使う。nativeではResult.Closeによる返却も含む。

Maria測定接続のcharacter_set_client/collation_connection/autocommitは全3経路で`utf8mb4 / utf8mb4_uca1400_ai_ci / 1`と一致した。client側のfound-rows/multi-statements/collation指定も合わせたが、全capabilityや全型の一般的な意味一致を保証する試験ではない。nativeにはdatabase/sqlの引数変換や同じcontext監視がなく、その差も含む。キャンセル・timeout等の機能同等性は未評価。

各processで8DBを保持。全Fork・親準備・測定接続/BEGIN/PREPAREが終わってからraw計測し、全8バッチが終わるまでCOMMIT・検証・Closeしない。parallel=1または8をsemaphoreで制限。GOMAXPROCSは両方8。productのSnapshot後共有用Forkは作るが使わない。元の70アプリテストの全体wall比較ではない。

## 素のライブラリで分かった互換性

Go-mysql v1.16.0はパラメータのあるCOM_STMT_EXECUTEにPARAMETER_COUNT_AVAILABLE（0x08）を付ける。現在のmariamem hostは非zero execute flagをcursor指定として拒否するため、公式driverと直接APIの両方でERROR1235「prepared server-side cursors are not supported」を再現した。

[stdlibの未変更flag失敗](pilot-stdlib-flag-failure.txt)、[直接APIの失敗](pilot-native-stock-flag.txt)を保存。これは速度の失敗ではなく、本計測前の相互運用失敗。製品側のprepared decoderは変更していない。

診断用にclient/stmt.goの1条件だけを変更し、QUERY_ATTRIBUTES非対応時には未使用0x08を付けないようにした。[差分](go-mysql-stmt-overlay.patch)。この条件ではparameter_count/nameの追加形式は使われず、4パラメータのlegacy bodyは変更しない。[MySQL protocol reference](https://dev.mysql.com/doc/dev/mysql-server/latest/page_protocol_com_stmt_execute.html)も参照したが、ここでclient/serverのどちらを修正すべきかまでは裁定しない。主測定のgo-mysql値は全てこの互換変更あり。

さらに公式driver.Connectorにはcustom dialerがないため、接続時の1呼出しをConnectWithDialerへ差し替え、従来と同じDatabase.DialContext/net.Pipeを使用。[dial差分](go-mysql-driver-overlay.patch)。SQL実行・結果変換・context watcherは公式driverのまま。直接APIは公開ConnectWithDialerを使用。TCPへ迂回していない。

両driverが標準名mysqlを登録するため、go-mysql側だけlinkerの-Xで登録名をbenchmark-go-mysqlに変更。実行性能を変えるSQL patchではない。GoがGOMODCACHE下へのoverlayを禁止するため、checksum固定moduleをtemp/go-mysqlへコピーし、ローカルreplace＋overlayを使った。コピー自体は変更せず、source hashesとMIT licenseを保存した。

## 計測結果

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、通常Maria16MiB/canonical writeVec。P1/P8それぞれ各arm1 warmup後、順序を回転した固定5組。observer/profilerなし。単位ms/100明細INSERT/DB。各process内8DBの中央値をさらに5processで中央値化。

| 経路 | P1 | P8 |
|---|---:|---:|
| PG参照 pgx/stdlib | 4.098 | 6.486 |
| Maria standard | 7.135 | 13.264 |
| Maria go-mysql stdlib（互換変更あり） | 7.246 | 13.509 |
| Maria go-mysql native（互換変更あり） | 7.257 | 12.960 |

| 同じ組同士の差 | P1中央値 ms / % | P8中央値 ms / % |
|---|---:|---:|
| stdlib − standard | +0.111 / +1.56% | +0.360 / +2.73% |
| native − standard | +0.045 / +0.63% | −0.189 / −1.44% |
| native − stdlib | −0.022 / −0.30% | −0.549 / −4.06% |

stdlibはP1全5組でstandardより長く、P8は4/5組で長い。nativeはstandardよりP1は2/5組、P8は4/5組で短いが、差は小さい。P8 native round2は18.1695ms（他4回12.6255–13.0765ms）だったが除外せず保持。P1 nativeは6.8775–7.5215ms、standardは7.0625–7.5810ms。小さい効果には変動があり、nativeへ替えれば常に速いとは言えない。

PG参照に対する大きな残差を、ライブラリ交換やdatabase/sql省略だけで解消する結果ではない。共通のwire/内部通信やserver側SQL/制約/索引/組込み実行基盤の費用はなお残るため、残差をエンジン単体へ帰属しない。過去の7.18/13.29ms等とは新規測定接続・affected-row check・module graph・cohortが異なるので直接差し引かない。

process全体のCPU/wallも保存したが、初期化・Fork・親作成・oracle等を含むためraw INSERTのCPUや元suiteの全体時間として扱わない。共有hostの温度/負荷統制なし。観測された結果を見てperformance反復を追加していない。

## 正しさ・失敗の扱い

最終pilot4条件は全て8DB成功し、Mariaのsession設定一致を確認。公式flagの互換失敗は別記録として残し、主計測と混ぜていない。

主計測全48process成功、384子DB oracles・38,400 timed INSERT。primary40process、warmup8process。各子DBでuser trigger0、注文40/明細100/監査0/合計0、商品500件の在庫100、FK/CHECK拒否、transaction/statement/connection/serverの終了を検証。補修・trigger復元・アプリテストの期待値変更なし。今回は専用TestInsertOnlyを選択し、元70テストや全consumer適合を実施したものではない。

準備中のdial route指定（仮想ラベルではなく実DSN endpointが必要）による失敗を保存。dependency取得を一度rootで実行したが、初期時点で変更のなかったgo.mod/go.sumをHEADの元内容へ完全復元し、実験module内でやり直した。既存ユーザー変更は触っていない。[修正記録](root-dependency-correction.json)。本計測前に全て修正し、最終sourceをhash固定して両binaryを再buildした。

## 出自・再現

build前にgit_identity.pyでproduct/PG sourceを確認。

- Maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`
- guest SHA256 `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`（再生成なし）
- PG source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`
- go-mysql v1.16.0、module ZIP Sum `h1:odv4Ygtc1WHJv3uUF2aoJdE1RS7tA0sD3ET91ZAWQIg=`。Go module origin Hash `ad661cb5b84f508aa57e25ef78821c89c891e38c`はdownload metadataに保存。Git tag objectとは扱わない。
- donor raw probe `f697c1aace4429163d76d27abd49953416856ab6` / benchmarks/no-trigger-insert-20261113

go-sql-driverはv1.9.3を維持。go-mysql追加でedwards25519はv1.2.0となり、全Maria経路が同じmodule graphを共有する。canonical productのgo.modは変えていない。完成harness、PG fixture/seed/probe、client adapter、dial/flag overlay、module/source/binary hashesと全trace/outputを保存。

新workspaceへproduct pinのworktree、PG pinのtemp/pgmem、この記録をevidence、harnessをtemp/mariaへ配置。PG storeのfixture_test.go/seed.go/insert_probe_test.goへ保存したpg-*.go.txtを置く。go-mysql v1.16.0をchecksum検証して取得し、temp/go-mysqlへコピー（harness/go.modの../go-mysql replace先）。setup.pyでdial overlayとMaria probeを生成し、compatibility_overlay.py、build.py、pilot.py、measure.py、analyze.pyの順。setup.pyの後には必ずcompatibility_overlay.pyを実行する。build.pyはMariaにoverlayとdriver登録名の-Xを指定する。

build1800秒/容量10GiB/空き12GiB。最初のcache buildはworkspace runner、その後の固定source buildと計測は直接監視、計測前後にdisk guard、各process130秒timeout。全計測は同じsandbox外権限。解析だけならこのディレクトリで`python3 analyze.py`。

製品runtime、main、CI、releaseは変更していない。互換patchを製品へ採用する候補やdriver乗換えの受け入れではなく、有限の診断実験である。
