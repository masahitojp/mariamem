## 複数LTS提供を前提にしたoutput部分再利用の評価（2026-11-12）

**判断提案：outputだけの部分再利用を、既存契約を維持した製品化候補として進めることを条件付きで推奨する。** 理由は、複数LTSを保守する間も持ち続ける自前の出力buffer・再fetch・数値/日時再変換を退役でき、代わりに使う直接接点は調べたLTS間で安定していたため。全面nativeへの移行や新たなengine patchを前提にしない。

**最大の反論は、現行方式も同じ実装を複数LTSで共有でき、今回の過去変更からmariamem側の修正削減例は確認できなかったこと。** 短期の更新工数節約や投資回収は実証されていない。それでも、繰返し保守する変換責務そのものを取り除く価値はあると評価する。これは「2系列だから効果が2倍」「CI費用も減る」という推奨ではない。既存の有限な正式化・受入れで成立することが条件で、追加hookや版別変換の再実装が必要ならこの判断へ戻る。

この推奨は新しい前提とsource照合に基づくもので、2026-11-10の見送り推奨を更新する。Humanの採用決定、main統合、release承認ではない。今回実行したのは比較表の作成とsource/既存CIメタデータの確認まで。

### 比較の固定条件

- A（現行方式の固定基準）：`b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`。
- B（output試作）：`73d1dca153348feab07a7638172782056af7897d`。
- 作業中のbranchは `experiment/issue13-detection-net` で比較対象とは別。両SHAのファイルを直接読んだ。現在main全体との差ではない。
- 将来は系列別提供物を利用者が選び、提供系列を上流LTS期間に沿って保守する。当面は12.3だけ。正確な命名・保守区分/終了日は別設計。A/Bとも#150の共通準備を利用する前提。
- 上流は[固定6タグ・5ファイルの調査](https://github.com/masahitojp/mariamem/issues/128#issuecomment-6818523501)。初回GA11.4.2→11.8.2→12.3.2と、同時期保守版11.4.13→11.8.9→12.3.3。両端差分であり全commit履歴ではない。

### 一枚の対応表

| 保守する責務・観測した変更 | A：現行方式 | B：output部分再利用 | LTS併存での評価・必要な対応 |
| --- | --- | --- | --- |
| 出力bufferの型/サイズ/寿命、bindの再設定 | `ps_result_bindings`、結果用`ps_buffers`を保守 | 結果用bindingを退役。入力用bindingは残る | **Aだけの保守を削減**。系列別型表が実在したわけではなく、共通実装の保守責務を削る |
| 可変長値のtruncation・再fetch | 1-byte bufferで長さを取得し、確保して`mysql_stmt_fetch_column`、NULL/error/lengthを確認 | 元のraw行をコピー。列単位の再fetchなし | **Aだけの保守を削減**。Bでも行長・総量・OOM検査は必要で、上限検査を丸ごと削れるわけではない |
| C native数値/日時からwireへの再変換 | `ps_cell`のendian/float bit変換、`ps_time_output`、Goのrow再組立てを保守 | 行のbytesを保持し、Goは構造を検査 | **Aだけの変換責務を削減**。値の意味を二度実装する箇所を減らす。Go型/幅/temporal長のルールはBにも残る |
| 11.4→11.8のFLOAT取得変更 | 上流の変更箇所は`fetch_result_with_conversion`。AはFLOATをFLOATでbindするため、同型なら`fetch_result_float`へ進む | 出力fetch自体を通らない | **この変更ではA側の修正は必要と認められない**。変更行数をBの節約実績に数えない。根拠S3 |
| 同じ差分の`IS_TRUNCATED`変更 | 数値への型変換に使うmacro。Aの通常の数値出力は同型/互換型・同じunsigned指定で取り出す | 当該出力変換を通らない | **Bによる修正削減例は未確認**。全SQL型・metadata変化の到達性を証明したわけではない。現時点は関連sourceの確認だけ |
| 11.8→12.3の負のゼロ正規化 | 上流serializerの正規化後にfetchし、floatのbitを再encodeする。A独自の正規化追加はsource上不要と推定 | 正規化済みのraw bytesをコピー。validatorは固定幅を確認し符号bitを変えない | **両方が上流の変更を受け取る**。Bだけの追従利益とは数えない。共通のnative対照は必要。根拠S4 |
| rawの構造・length・list・所有権 | 行構造を直接辿らずfetch APIを使う | `MYSQL_STMT.result` / `MYSQL_ROWS`、`length-1`、bitmap最小長、行数/next、copy-before-freeを確認 | **Bだけに追加**。直接の定義/producer/移管は比較したLTS間で不変。版別分岐を要する根拠は今回なし。ただしallocator等の推移的依存は未評価 |
| row validatorと不正データ拒否 | cellと型を検査してrowを組み立てる | raw header/bitmap/固定幅/length/temporal/末尾を検査 | **置換される責務**。Bは無検査の素通しではない。新しいwire型/幅なら両案に対応が必要。共有`valueShape`/`validValue`を維持 |
| store/free/reset、metadata、OUT・終端/status | APIと公開契約を確認 | 同じ責務が残る | **共通**。store_resultの未使用変数削除は修正不要と推定。bulk/OUT/終端の意味変更は両案とも確認。Bはrow以外を自動追従する設計ではない |
| 既存engine/WASIX patch、入力/session/停止 | 維持 | 維持 | **共通**。固定差分で`guest/source.patch`/`guest/patches`/`guest/input.json`に変更なし。patch更新負担をBの利益にしない |
| 系列別の生成/binding/公開回帰・配布 | 各系列で必要 | 各系列で必要 | **共通**。host/adapterは両案とも共有可能。Bだから2本の製品を1本の検証で済ませられるわけではない |
| private v2、正式生成・通常CIへの移行 | 今回の移行なし | canonical入力/生成/binding、期限付きartifact参照の解消、受入れと通常CI接続が必要 | **Bだけの初回投資**。各LTSの通常更新費と分ける。配布命名の設計はどちらにも必要 |

### 何が減り、何は減ったと言えないか

- **確認済みの構造的削減**：出力buffer/bind、可変長再fetch、数値・日時再変換。Bは実guestでも限定動作済み。
- **追加の責務**：内部cached-rowの構造/長さ/寿命とraw validator。直接接点は今回の歴史標本では安定しており、毎版の大きな修正を前提にする必要はない。
- **過去の修正工数削減実績**：今回見つかった上流変更について、Aで必要だったmariamem側修正をBで不要にできた具体例は確認できなかった。観測がないことを将来利益ゼロとも、削減実績ありとも扱わない。
- **複数LTSの効果**：共通修正を各系列でレビュー/検証する対象が減る可能性。ただしAも共通コードを共有できるので、版数に比例した削減量を主張しない。新LTS追加と既存LTSの保守更新を分けて記録する。

### 根拠（固定ソース）

- S1 [Aのadapter](https://github.com/masahitojp/mariamem/blob/b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50/guest/prepared_api.inc#L216)：`ps_time_output`、`ps_result_bindings`、`ps_cell`、`ps_capture_result`。buffer_type/unsignedをmetadataに合わせ、数値bitsを再格納する実装を確認。
- S2 [Bのadapter](https://github.com/masahitojp/mariamem/blob/73d1dca153348feab07a7638172782056af7897d/guest/prepared_api.inc#L211)：store→list traversal→hex copy→free。rawアクセスはCに局所化。
- S3 [11.8.2のfetch選択](https://github.com/MariaDB/server/blob/8d36cafe4fc700e6e577d5a36650c58707e76b92/libmysqld/libmysql.c#L3892)：`is_binary_compatible`と`setup_one_fetch_function`。同型なら直接fetch、非互換時のみ`fetch_result_with_conversion`へ差替え。AのFLOAT同型bindと照合。
- S4 [12.3.2のbinary格納](https://github.com/MariaDB/server/blob/9f98f82b14a9b939834281672b6d0cf965db69a3/sql/protocol.cc#L1811)、[B validator](https://github.com/masahitojp/mariamem/blob/73d1dca153348feab07a7638172782056af7897d/internal/preparedproto/binary_row.go)、[共通値ルール](https://github.com/masahitojp/mariamem/blob/73d1dca153348feab07a7638172782056af7897d/internal/preparedproto/values.go#L29)。負のゼロの履歴変更と、固定幅値への検査・符号bit保持を照合。
- S5 [既存native対照test](https://github.com/masahitojp/mariamem/blob/73d1dca153348feab07a7638172782056af7897d/internal/mysqlwire/prepared_execute_test.go#L138)にfloat-negative-zeroを含む。ただしfixture生成時の版の対照であり、全LTSの負のゼロ比較ではない。
- S6 [CI42801293564](https://github.com/masahitojp/mariamem/actions/runs/42801293564)：今回一度メタデータを取得し、head_sha=B・completed/successを確認。12.3.3/macOSの限定実guest記録。過去結果の新規実行や13系/全LTSへの読み替えなし。

### 残条件と検出網

| 条件 | 状態 | 既存の検出手段と不足 |
| --- | --- | --- |
| 追加engine patchなし・output限定 | 固定A→B差分で確認 | Git差分で確認可能。今後hook/版別変換を追加するなら価値判断へ戻る |
| raw構造・隠れOUT・不正chain・copy/free/OOM | focused実装/検査あり。完全な製品受入れは未完 | `TestValidateBinaryRowAgainstEncoder`、`TestPreparedRawRepresentationBoundary`、`TestHiddenRawOUTMalformedPayloadIsRejected`、`TestPreparedChainRejectsMalformedSuffixBeforeSending`、C harness/ASan。mockやcomponentは実guestの全失敗分岐を証明しない |
| 正式生成・混在拒否・再現 | 未完 | v1/v2拒否testはある。[試作workflow](https://github.com/masahitojp/mariamem/blob/73d1dca153348feab07a7638172782056af7897d/.github/workflows/prepared-row-guest.yml#L16)は旧run artifactを参照。canonical生成/所有/provenanceと通常CI配置は#134で必要 |
| 同一候補の両OS/公開契約/consumer/性能 | 未完 | #132の既存条件を維持。限定macOS PASSで代替しない。製品化時に必要な範囲を同じ候補へ結ぶ |
| 複数LTSを同じadapterで運用 | source安定性の材料のみ | 現存CIは11.4/11.8のB動作を検出しない。今すぐ旧LTS提供を追加する必要はなく、次に実際に提供するLTSの受入れで共通化を確認する |
| 総工数・回収時期 | 未測定 | CIでは判定不可。架空の時間や「2倍の効果」を置かない。実際の次LTS作業で変更箇所/レビュー/待ちを記録する |

#138の停止/未確認条件は維持する。今回の比較は再開や契約免除ではない。既存ガイド・release/generated所有を採用可能な状態まで監査/更新したものでもない。試作の正式入力と受入れは未完のまま明示する。

### 次の一つの判断

**自前の出力変換を減らす構造的利益を理由に、既存の#134正式化→#132受入れへ進むか。** 推奨は条件付きで進むこと。削減時間の証明専用に11.4/11.8を新規buildすることや、もう一つの小さな実験を挟むことは勧めない。

進む場合も、入力/session/host状態を維持し、row再利用をC adapterに限定する。新しいengine hook、系列ごとの変換実装、公開契約の弱化が必要なら、自動で作業を広げず費用と理由を提示して再判断する。正式化/受入れは既存残件を一つの計画にまとめ、完了済み実験をやり直す前提にはしない。

今回の依頼範囲（一枚の比較と評価）は完了。実装・build・test・追加CIは実施していない。数値的な更新工数削減、全依存のABI不変、将来全版への適用保証は結論に含めない。
