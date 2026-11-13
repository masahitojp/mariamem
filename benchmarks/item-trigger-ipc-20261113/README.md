# 明細INSERT: 合計triggerと内部通信の切り分け

結論: このモデルケースの明細INSERTでは、内部通信よりtriggerを含むguest側処理が大きい。次の調査対象は注文合計triggerのUPDATEとSUM再計算を推奨する。製品やアプリケーションSQLの変更は今回採用しない。加算更新は有効な対照だが、既存合計値への依存など意味の差があり、一般的な置換の可否は別途判断が必要である。

## 結果

単位は1DBの明細100 INSERT当たりms。各条件16ロードを1プロセスで測定し、3プロセスの平均を等重みで平均した。中央値の足し算を避けるため、以下は加法性のある平均値である。複数DBの時間は重複するためsuite wallに足さない。

| 並列度・trigger | INSERT全体 | guest処理 | 内部通信 | 通信前後のdriver等 | サンプル投入全体 |
|---|---:|---:|---:|---:|---:|
| P8 元のSUM | 38.066 | 30.950 | 4.166 | 2.951 | 71.900 |
| P8 加算更新 | 27.955 | 21.637 | 3.432 | 2.886 | 61.775 |
| P8 INSERT合計triggerなし | 17.634 | 9.121 | 4.530 | 3.982 | 56.792 |
| P1 元のSUM | 22.863 | 19.918 | 1.286 | 1.659 | 39.869 |
| P1 加算更新 | 17.327 | 14.354 | 1.289 | 1.684 | 34.753 |
| P1 INSERT合計triggerなし | 8.012 | 5.218 | 1.207 | 1.587 | 24.552 |

P8の元のtriggerではguest処理81.3%、通信10.9%、通信前後7.8%。対照との差で推定すると:

| guest処理の差 | P8 | P1 |
|---|---:|---:|
| 元のSUM − 加算更新: SUM副問い合わせ追加分 | 9.313 | 5.564 |
| 加算更新 − triggerなし: 注文UPDATE等の残り | 12.516 | 9.136 |
| 元のSUM − triggerなし: 合計trigger全体の追加分 | 21.829 | 14.700 |

P8ではtrigger全体の追加分は元のINSERT時間の約57%、SUM追加分だけなら約24%に相当する。直接観測した通信は約11%。これらのSQL内訳は対照差であり、trigger内部へ時計を入れた実測ではない。guest処理にはresident dispatch、待機、SQL、trigger、応答JSON構築も含む。純粋なSQL CPU時間とは呼べない。通信もCPUではなくOS待機・起床を含む経過時間である。

3ラウンドすべてでguest処理の差は同方向。P8のSUM追加分は7.854/10.557/9.529ms、trigger全体は18.606/24.249/22.632ms。遅いnone初回も除外していない。詳細は[加法平均と各ラウンド差](additive-summary.json)、[各プロセス](summary.json)。

## 対照と正しさ

- full: 元のAFTER INSERTで、その注文の明細SUMを計算しorders.total_centsとupdated_atをUPDATE。
- incremental: 同じUPDATEをtotal_cents + NEW.quantity * NEW.unit_price_centsに変更。orders側のaudit triggerも残す。
- none: INSERTの合計triggerだけを削除。UPDATE/DELETE用の合計triggerは残す。

全条件で同じ100回の明細INSERT・4パラメータ・再利用prepared statementを使用した。noneの合計補修、元triggerの復元、検証は計測区間外。各波8DBのForkを全て終えてから投入し、全投入を終えてから補修・復元・検証・Closeする。別DBのDDLや補修が投入に重ならない設計である。noneの補修を無視したアプリ全体の高速化は主張しない。

最終状態は40注文・100明細・40audit・合計不一致ゼロ・500商品の在庫を検証。pilotではINSERTごとの途中合計も確認し、復元後に元の70テストを実行した。33プロセス全成功。pilotとanchorの元テストは計630件成功。追加の最終状態oracleは447ロード成功。

## 時計と照合

一つのmonotonic clockで以下を測る。実際のDBラベルとrequest IDで対応させ、各item Exec内にop5/command23の要求がちょうど1つあることを検証した。

1. client開始 → host raw Write開始: driver、外側wire、host encode等
2. host Write開始 → guestが要求frameを受信完了: inbound通信
3. guest受信完了 → 最初の非空応答Write開始: guest処理
4. 応答Write開始 → host応答frame受信完了: outbound通信
5. host受信完了 → client Exec終了: decode、driver等

2+4が表の内部通信、1+5が通信前後。各INSERTで五区間の和が元のExec時間に完全一致すること、因果順序、100件/ロードを検証した。観測510ロード・51,000 INSERT、564 guestの終了を確認し、parse/exit errorなし。primary比較は288ロード・28,800 INSERT。

[parserテスト](parser-tests.txt)は分割frame、空chunk、ID、制御frame、壊れたframeを確認。[負の対照](negative-controls.json)では応答境界欠損・時刻逆転・ラベル不一致を解析が拒否した。

既存os.Pipeを包むGo overlayで測定。通信方式は変更していない。rootへの一時API橋渡しは測定専用で公開API提案ではない。canonical guestではENABLED_PROFILING OFFが強制されているためSQL profilingや推測したC関数indexは使わず、guestも再ビルドしていない。

## 元ベンチマークとの関係・限界

元の70テストP8にもfull条件でobserver off/onを3組実行した。onの明細guest比率は78–82%で、guest側が大きい方向は共通。ただしsample平均は75.2/151.5/102.8msと変動した。off wallは523/820/768ms、onは511/923/639msで、観測負荷の上限をこの比較から確定できない。今回の絶対値は観測付き推定である。

71.9msはFork等から投入を隔離した条件。過去の約80msとの直接差引きや、pgmem約33msとの差が何ms解消するとの解釈はできない。pgmemは今回再測定していない。明細以外の注文INSERT、在庫UPDATE、prepare/commit等の残り約33.8msは今回の分解対象外。注文取得でのsyscall CPU比率を明細INSERTへ流用していない。

次へ進む条件: triggerのSQL改善を検討する場合は、合計の途中状態、既存値が不正な場合、数値境界、UPDATE/DELETEとの整合性を先に決める。汎用mariamem改善とアプリSQL改善を区別し、同じpgmem比較条件で再測定する。内部通信の置換を先に進める根拠にはしない。既存の保留issueやClose等の問題の解消も主張しない。

## 出自・再現

- 製品source_commit: `0f5b26f370875d26bd337031f48856d8f57c10db`。[identity](source-identity.json)参照。計測前にもgit_identity.pyで確認済み。
- canonical guest SHA256: `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`。
- 元harness記録: `d73acc145acfdd8a0f1303d82cc03e78bfffb0f1`。normal DSN、interpolateParams=true、16MiB、元writeVec。空write省略候補は使っていない。
- Go1.27.4、CGO_ENABLED=0、GOMAXPROCS=8。固定回数、回転順、予算は[plan](plan.json)と[runner](run.py)。

解析の再確認: このディレクトリで `python3 analyze.py --check`。eventsは元JSONをgzip+base64にしたテキストで、解析が直接読める。[event-hashes.json](event-hashes.json)は展開後JSONのSHA256。`summary.json`のgroupsは成分別中央値であり、上表の平均は`additive-summary.json`を使う。

再実行には新しい使い捨てworkspaceにpinned sourceのworktreeを用意し、このディレクトリをevidenceへ、harnessをtemp/mariaへコピーする。`overlay.py`で絶対パスを再生成し、`build.py`、`run.py`、`analyze.py`を実行する。overlayの完成形も*.go.txtに保存した。`check_parser.py`用の追加testはprobe_test.go.txtをvirtual guest testとしてoverlayへ追加する。保存済みoverlay.json中の<WORKSPACE>は過去実行の説明用で直接実行しない。再実行はこの調査の完了条件ではなく、元の観測を保存済み。
