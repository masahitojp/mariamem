# 明細INSERTのguest内部区間 — Issue186、2026-11-14

**結論: この明細INSERTではworker内の約95%が `mysql_stmt_execute` 内だった。入力decode/bind、結果構築、応答出力を先に削っても得られる余地は小さい。次はSQL実行内のtrigger（order UPDATE/SUM）と、その外側のINSERTを分ける有限観測を推奨する。** 今回はその追加観測や製品パッチを実行していない。

これはSQL実行の中に改善可能な局所箇所がある証明ではない。`mysql_stmt_execute` は組込みAPIの状態リセットや内部パラメータ処理も含むinclusive区間で、InnoDBだけの時間ではない。具体的な最適化の採用判断には、この区間の内訳がまだ不足している。

親 [#182](https://github.com/masahitojp/mariamem/issues/182)。[有限計画 #186](https://github.com/masahitojp/mariamem/issues/186)。直前のhost受信バッファ試作 [#185](https://github.com/masahitojp/mariamem/issues/185) は試作完了・採用見送りでclose済み。

## 結果

観測onのprimary 3 process × 8 DB = 24 DB、各DB100件の値を平均した表。各PのDB投入spanは並行し得るため、suite全体への短縮量へ加算しない。

| 100件あたり、ms | P1 | P8 |
|---|---:|---:|
| INSERT呼出ループ全体 | 19.684 | 32.245 |
| worker受取後の入力処理・bind・旧パラメータ解放 | 0.212 | 0.336 |
| `mysql_stmt_execute` | **15.659** | **23.971** |
| SQL終了後の結果構築・応答直前まで | 0.304 | 0.422 |
| `multi_reply`（応答frame構築・mutex・stdio/出力・後片付け） | 0.383 | 0.473 |
| 上記worker区間の合計 | 16.557 | 25.202 |
| 呼出ループ全体とworker合計の差 | 3.127 | 7.043 |
| 応答内の`Fd_write`（上のreplyに**内包**、加算不可） | 0.264 | 0.307 |

`mysql_stmt_execute` / worker合計は P1 **94.57%**、P8 **95.12%**。P8各processでも95.02–95.23%。SQL実行のprocess内平均の中央値は24.381ms、範囲22.935–24.597ms。全体呼出ループにはdriver/host処理、入力通信、dispatch/スケジューリング、ループ間処理などが残り、最後の応答後片付けはclientの戻りと重なる可能性がある。最後の差分7.043msを「純粋な通信時間」と解釈しない。最初の受信からworker受取までの区間も今回未分離。

### 観測負荷

同一binaryで `INSERT_STAGES=0/1`。各arm1 warmupと交互順3組。raw100件のDB中央値をprocessごとに求めて比較。

| | offの中央値 | onの中央値 | 同じ組の変化率 |
|---|---:|---:|---|
| P1 | 19.458ms | 19.696ms | +3.73%, +1.34%, -3.02% |
| P8 | 31.483ms | 32.977ms | +1.17%, +4.74%, +1.42% |

P8では観測onが3/3組で遅く、対応変化率中央値+1.42%。軽微だがゼロではないので補正せず、そのまま提示する。両armとも未実行のhook分岐や追加Moduleフィールドを持つため、offも完全な無変更binaryではない。host共有環境・macOS arm64だけの有限観測。P8最後のon process wallは333.410msと遅かった（対応off290.778ms、+14.66%）が、そのINSERT区間は他のonより短かった。除外や都合のよい再計測はしていない。

16成功process、128 DB、12,800件のraw INSERTを検査。観測on64 DB/6,400件（うちprimary48 DB/4,800件）は、各DB100件・各7マーカーが正順に一度ずつ、stdout `Fd_write` が各1回、すべて成功。全128 DBでorders40/items100/audit40、合計値、500商品のstock、FK/CHECK拒否を検査しPASS。公開DB/statement/transaction/SnapshotのClose errorも検査した。起動時sandboxのlisten拒否は別途保存し、性能標本へ含めない。

## 区間とソースの対応

- product source_commit `bb1e937ae75b5788c8548a52987d9d42f78292d5`。
- canonical guest SHA256 `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`、Go1.27.4/darwin/arm64、GOMAXPROCS8、GOGC100。
- `git_identity.py` の `source.json` と、provenance内の変更対象生成ファイルhashを照合した `identity-check.json` を保存。canonical guestやCパッチは変更していない。観測は診断専用の生成Go overlay。overlay binary hashは `binary.json`。
- 関数mapは当該sourceの `benchmarks/forkcost/buffer-zero-candidate/validation/function-map.txt`。Fn267=`multi_worker`、Fn5766=`mysql_stmt_bind_param`、Fn265=`multi_reply`。
- `ps_execute` と `mysql_stmt_execute` はFn267にinlineされている。worker mutexを解放した直後（v169/Fn130）をT0、bind直前/直後をT1/T2、`e->parameters=params` 直後（v3152）をT3、native executeがreturnした合流点L651をT4、Fn265直前/直後をT5/T6とした。全callsiteは `bindings.json`、`source-anchors.txt`、`observer.patch` に固定。
- `mysql_stmt_execute` の原定義は [MariaDB固定commit libmysqld/libmysql.c](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L2588)。取得全文SHA256はguest/input.jsonのbefore hashに一致。状態リセット→method stmt_execute→結果状態更新→returnが生成コードのT3–T4へ対応する。取得bindingは `upstream-binding.json`。他のSQLへの一般化はしない。
- `WasiStubs.Fd_write` のfd1をnestedに計測。workerごとのrecordを使い、各マーカーでglobal mutexを取らない。初回登録/配列確保と時計読取りの負荷はon側に含む。
- すべてのFork・親注文INSERT・BEGIN/PREPAREはraw投入前。8 DBのraw投入を終えてからstatement Close/COMMIT/oracleを実施。on/offとも同じSQL。監査status限定発火、SUM再計算トリガー5個、constraints/indexを保持。TRIGGERS_OFF=0。売上SQLはREVENUE_PREAGG=1を保持するが、この専用probeで売上queryを実行していない。

## 過去の結果との整合と次の判断

以前のCPU profileはLoadSample全体、今回のelapsedはprepared明細INSERT専用で、分母・計測法が異なる。syscallのCPU比率約60%から「このINSERTのwallの60%が応答Write」とは言えない。一方、今回小さかったのはworkerが応答を作り書く側で、host/guest間の全通信・待ちを否定するものでもない。

入力処理+結果構築+replyはP8で平均1.231ms/100件（workerの約4.9%）。全廃できる前提でもこの範囲の時間しかなく、host受信バッファのサイズ探索や入力再利用 #167 を優先する根拠は弱い。既存SUM→差分やno-trigger対照は有用だが、別cohortとの差し引きで今回の24msを分解しない。

**次に一つだけ調べるなら、SQL実行内でtriggerのUPDATE/SUMが占める経過時間を直接分ける。** 同じsource・SQLのままtrigger関数の最外層時間（入れ子の二重加算を避ける）とnative executeの残りを測る。その後、UPDATE/SUM内の実行計画/解釈費用か、INSERT本体の行・索引処理かを選ぶ。これは最適化採用ではなく不足証拠の取得で、追加overlayの1回build（上限20分）と同じ16process（計測上限15分）が見積り。承認なしにその先の候補実装へ拡大しない。

## 再現・検証

1. 上記product sourceから `experiment/<purpose>` を作り、experiment-workspace helperで8GiB予算/最低空き8GiBのworkspaceをprepare。
2. 本結果bundleをその `evidence/` にコピーし、`python3 evidence/restore.py`。固定source identityを検査し、保存harnessと完全一致hashのoverlayを `temp/` へ再作成する。
3. `python3 evidence/build.py`。依存取得とlocal listen可能な実行環境が必要。
4. 他のbuild/再帰容量走査を重ねず `python3 evidence/measure.py`（固定16process）。`python3 evidence/analyze.py` で集計と7マーカー/件数の検査を再現。
5. 結果保持後、専用temp/cache/worktreeをfinalize/cleanupする。

初回buildはsandboxの依存取得拒否後に同じレシピを再実行。helperはfailed workspaceの再runを許さないため、20分timeout付きbuildを手動監督した。初回実行はlocal listen拒否（`sandbox-failure/`）、許可された環境の固定campaignは全成功。runtimeの製品変更・main統合・releaseはない。診断境界のoracle/観測検査を行い、無変更の製品全体CIは再実行していない。
