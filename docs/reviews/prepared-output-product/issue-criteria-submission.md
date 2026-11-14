# Issueの評価観点を含むHuman Review提出（2026-11-14）

**判断は、Issue128の保守性評価とIssue132の検査適用案を含め、output限定候補をmainへ統合するか。Codexは統合を推奨する。** 本来の目的「MariaDB更新の負担を下げ早く追従する」に対して、自前の出力変換を退役し、限定した上流接点へ置換する構造的改善は確認できた。最大の反論は、A/B対称な版更新の作業量・提供速度・復旧費用を実測しておらず、総費用の改善は判定できないこと。それでも、調べたLTS間で直接接点が安定し、追加engine patch・系列別変換・host/controller変更を要せず成立したため、限定採用を推奨する。工数や提供速度の実測改善をこの時点で必須とするなら、その条件は未充足である。

今回の依頼は評価観点を含めたレビュー提出。統合・公開・新実験の承認ではない。既存の5指標はIssue上の指標案であり、今回独断で数値閾値や回収回数を確定しない。

## 固定対象と評価元

- runtime候補：`ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e`。
- 対称な現行比較基準：`eb175ae23292c1c40cfbeb4b9b73132873c4cc6f`。
- 先行提出記録：`5a1c139075a1162b9272e034c958eee192a182ce`。runtime候補以後の差分はdocs/evidenceのみ。
- 作業branch：`experiment/prepared-output-product`。
- 観点の出典：[Issue128の5指標・対照表・判定案](https://github.com/masahitojp/mariamem/issues/128)、[保守対応表](https://github.com/masahitojp/mariamem/issues/128#issuecomment-6818963730)、[実際に必要だった負担](https://github.com/masahitojp/mariamem/issues/128#issuecomment-6868338587)。方式制約の正本は[Issue65](https://github.com/masahitojp/mariamem/issues/65)、公開受入れは[Issue132](https://github.com/masahitojp/mariamem/issues/132)。先行報告の旧試作SHAとは区別する。
- 技術受入れと検出網：[先行レビュー](adoption-review.md)、[元条件の適用表](acceptance-map.md)、[CI証跡](final-ci.json)。本提出はこれらに費用評価5指標への回答を補う。

## Issue128の5指標への回答

| 指標 | 今回の評価 | A→Bの具体的な変化・根拠 | 不明点／判断への影響 |
| --- | --- | --- | --- |
| **1. 新版ごとに人が判断する保守項目（主指標）** | **構造的改善の根拠あり。総負担減少は未確定** | Aの出力bindの型/サイズ/寿命、truncation/refetch、数値/endian/MYSQL_TIME再変換を製品経路から削除。Bはcached rowのlayout/length/list/所有権とraw validator確認を追加。既存patch・入力・metadata/status/OUT・生成binding・各系列受入れは共通で残る。Cの直接参照は`guest/prepared_api.inc:224`以降に局所化し、Goは既存のvalueShape/validValueを共有。詳細は[責務対照表](../issue128-output-maintenance-matrix-20261112.md)。 | 「項目数が少ないから時間も短い」とはしない。6タグ×5ファイルの固定LTS標本では直接接点は安定（lts-source-recheck.json）。allocator等の推移的依存、将来の全版、各項目の実作業難度までは未評価。 |
| **2. 調査・修正の実作業量と波及範囲** | **比較人時は不明。今回の実作業は記録済み** | 正式化ではworker/CRC/dictionary等の配置・関数番号の審査、fixture、registry、12 component familyのlicense記録の整合が実際に必要だった。host JSON二重解析の修正も発生。今回のC出力adapterは23追加/103削除行、raw validatorは55行だが、人時へ換算しない。[負担引渡し](https://github.com/masahitojp/mariamem/issues/128#issuecomment-6868338587)と各失敗/修正証跡を参照。 | 同じ旧版→新版をA/B両方で仕上げた更新試行ではない。過去FLOAT等の上流変更について、Bでmariamem修正を回避できた実績は未確認。初回移行、共通更新、検証整備ミスを分け、架空の節約人時を置かない。 |
| **3. 変更・破損を見つける容易さ** | **変更した境界の検出網あり。一部は手動実行** | raw header/bitmap/型/長さ/末尾、混在版、隠れOUT/chain全体検査、copy/free/OOMのGo/C検査とcanonical binding/build guardを接続。通常/public CIが検査する範囲は先行レビューと適用表に対応。71 native-reference scenarioは保存probeによる実guest確認。[性能/実guest証跡](performance-20261114/README.md)。 | 性能退行は通常CIで検出できず、明示A/B測定で発見。71ケースの全体とframe近傍probeが通常CIで毎回自動実行されるとは主張しない。内部layout全依存や将来の全SQL型も自動保証しない。検出率の分母・数値は未設定。 |
| **4. 新版を利用可能にするまでの時間** | **時間短縮は未判定** | 同一最終hostの通常・両OS公開・配布物CIは成功。生成・独立再現・公開回帰・配布はA/B共通で必要で、省略できたとはしていない。CI/jobの開始終了時刻・再試行・失敗理由はfinal-ci.jsonと保存証跡で追える。 | 人の実作業時間と機械時間/queue待ちを対称条件で計測していない。今回の長い移行campaign、別runnerの時間、CIの緑や件数を新版提供速度の改善へ換算しない。 |
| **5. 採用までの残投資と故障時の復旧負担** | **予定した正式化・有限な実検証は実施済み。統合判断と復旧費用は残る** | private v2、正式入力/生成、binding、両OS公開・installed/ORM、有限性能比較、証拠保存/owned scratch清掃を実施。#134は正式化・引渡し完了。残るのは#132の旧native条件の適用確認とmain統合判断、統合時の文書整合。releaseは別。 | 実行時に旧経路へ自動切替する仕組みはない。cached row変更時はC adapter/validatorでの局所修正を評価し、追加hook/系列別変換/契約弱化が必要なら価値判断へ戻る。A方式へ戻す場合もC・private版・Go・生成guestを整合させて検証する必要があり、即時fallbackや復旧時間は未検証。過去投資を今後の費用へ二重計上しない。 |

**総合判定：構造的な保守責務削減の根拠あり。更新全体の人時・提供速度・回収時期の改善は未判定。** CI成功と性能改善は独立した受入れ材料で、保守費用の不足を相殺する点数ではない。#150の共通準備はAにも使えるため、Bだけの利益に含めない。

## LTS提供方針を反映した評価

当面12.3 LTSだけ。将来は直近2つ程度のLTSを系列別提供し、利用者が対象系列を選ぶ。`0.7.1-12`等は意図の例で、正式版/tag/package構文やrelease指定ではない。各提供系列はその上流LTS期間に沿って保守し、2系列という計画値だけで打ち切らない。

- **新LTS追加費用**：既存patch、raw直接接点、metadata/入力、生成binding、公開受入れを確認する。Bは出力変換の確認を退役する一方、cached rowの確認を追加する。今回13.3への更新人時やruntimeは未確認。
- **併存の増分費用**：共通修正と系列固有修正を分ける。AもBもhost/adapterの共通化は可能。Bの効果を系列数倍にせず、各系列の生成・binding・CI・配布が残ることを費用へ含める。
- **今回の証拠の限界**：11.4→11.8→12.3のsource標本は直接接点の安定性を支持するが、2系列runtime/配布や将来LTSを受け入れた証拠ではない。旧LTSの追加buildを今回の新しい必須条件にはしない。

## Issue65/132の採用条件との照合

| 条件 | 状態と提出時の扱い |
| --- | --- |
| embedded継続、input/session/状態・流量制御をhostに保持 | 固定diffで確認。追加engine patch/controllerなし。 |
| 追加hook・系列別変換・公開契約弱化なら再判断 | 維持。今の候補では導入せず、将来の自動拡張を承認しない。 |
| raw所有権・破損拒否・公開互換性・consumer・生成再現 | 先行レビューの有限範囲で確認。engine mockと実guest、旧sourceと最終host、functional FAILと承認済み例外を区別。 |
| 旧native固有のA/B observer・factory・G1/G2等 | **Humanの適用判断待ち**。現行hostの製品oracle＋変更outputのraw検査を使う提案。元campaignのPASS件数を流用せず、非適用を黙認扱いにしない。 |
| 性能・資源 | 固定Macの5組×101回で1行0.987、1,000行0.827、64KiB0.998の中央値比。64KiB組別0.950–1.140、Linux性能・peak RSSは未確認。普遍的な高速化の主張なし。 |
| 実験後始末とlocal folder依存 | owned測定tree/cache/host/venvを清掃。source refs・結果・hash・portable probeを保存。原本のdirty checkoutは維持。 |
| #138・main採用・release | #138の旧FAIL/未確認・停止を維持。main/releaseは未承認で、本提出は承認を代行しない。 |

## 次の判断と未測定項目の扱い

今は「構造的改善を根拠に、この限定候補と検査適用案をmainへ統合するか」を判断できる。更新時間の実測改善まで必須なら、指標2/4/復旧時間が不足するため、その条件では判定できない。

時間効果の材料を得るなら、次に実際に提供するLTS更新で、調査・修正・レビューの実作業、共通/系列固有の修正先、CI機械時間/queue待ち/再試行を分けて記録する。対称なA/B更新費用を求める場合は両案の更新・受入れが必要で、対象版・予算・停止条件のHuman判断なしには開始しない。既存の時間記録がないため、工数見積を捏造しない。今回追加の旧LTS buildや#138再開を提案・実行していない。
