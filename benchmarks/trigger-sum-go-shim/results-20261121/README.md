# #233　MariaDB を変更しない Go 側の高速化

**SUM 対策として、この変換の製品化は保留を勧める。** MariaDB と guest を固定し、生成 Go の通常のメモリアクセスで上限を確認する計算だけを変えた。P1 の SUM で100明細の INSERT は6組すべてで速くなり、対応短縮率の中央値は **1.09%**、プロセス CPU は **0.78%** 減った。同じ変換で実験用バイナリも **2,972,080 B（2.70%）** 小さくなった。一方、SUM の事前目安2%には届かず、差分加算・トリガーなしでも同等以上の短縮が出た。SUM 固有の費用を大きく減らす候補としての根拠は弱い。[事前条件](recipe/protocol.md) · [全18組](pairs.csv) · [バイナリの記録](environment.json)

| 明細 INSERT の条件 | 基準版 → 変換版（ms/100件） | 対応する経過時間の短縮率 | 短縮した組 | CPU の短縮率 | p95 の短縮率 |
|---|---:|---:|---:|---:|---:|
| A　元の SUM | 16.935 → 16.743 | 1.09% | 6/6 | 0.78% | 0.94% |
| B　差分加算 | 12.061 → 11.886 | 1.40% | 6/6 | 1.25% | −3.94% |
| C　明細 INSERT トリガーだけを削除 | 6.943 → 6.839 | 1.68% | 5/6 | 1.83% | 5.63% |

時間の列は各プロセス内中央値の6組での中央値。短縮率は各組の基準版に対する変化率の中央値なので、表の時間同士の比とは厳密には一致しない。SUM の経過時間短縮は組別で 0.12〜3.05%。p95 は6組中3組で悪化し、差分加算の p95 は5組で悪化した。共用 Apple M1 / macOS 27.2.1・Go 1.27.4 での結果で、Linux、高並列、出荷ツールチェーンでの効果は今回測っていない。[集計](summary.csv) · [ウォームアップと全 DB の生値](observations.jsonl)

両バイナリを交互順序で実行し、事前検査600件、ウォームアップ10,800件、本比較144,000件、計155,400件の INSERT が成功した。1,554 DB のすべてで実登録トリガーの本文、40注文の明細と合計、在庫、監査40件、FK/CHECK、Close を検査した。測定時の作業領域は8 GiBの上限内。変更は実験用 overlay に限定した。[再現手順](recipe/REPRODUCE.md) · [ソースの固定コミット](source.json)

## 候補の絞り込み

固定 CPU プロファイルを各 INSERT の `emb_stmt_execute` を含むスタックに限定して再集計した。表は SUM の3組の標本数。分類は包含関係があり、合計は取らない。名前を識別できた関数とヘルパーに限られ、インライン化されたバイト操作すべての費用を分離するものではない。[A/B/C の全値・SQL 外スタック](screen.csv) · [入力プロファイル](https://github.com/masahitojp/mariamem/tree/7c5893b3d5198d2c5087dbb100e631dfe63a58bb/benchmarks/trigger-sum-bottleneck/results-20261121/cpu)

| SUM の SQL 配下 | ABC | BCA | CAB | 読み取り |
|---|---:|---:|---:|---|
| 全標本 | 376 | 383 | 366 | 既定の各3,000標本には未達 |
| CRC 系 | 0 | 0 | 0 | SQL スタック外では45・37・31。既存の Go CRC32C は全ページの計算に適用済み |
| libc の文字列・バイト列比較／検索 | 0 | 0 | 1 | CRC と同様に個別の純粋関数を書き換える根拠は弱い |
| bulk copy/fill | 0 | 1 | 1 | 通常の Wasm memory.copy はすでに Go の copy を使用 |
| 通常のメモリ境界検査 | 25 | 26 | 20 | 呼び出し元は複数の生成関数に分散 |
| dlmalloc | 322 | 326 | 306 | 前回特定したストアの直接計時は小さく、allocator 全体の Go 化には根拠不足 |

CRC の先例は固定 guest のページ検証器の計算部分を Go の Castagnoli に置き換え、LSN や保存チェックサムの照合を残す方式だった。今回は固定 guest の通常 load/store にある共通の算術を対象とした。過去 #182 で採用済みの「直接 panic・noinline」の MemoryEA が比較の基準である。[CRC 導入時の適用範囲](https://github.com/masahitojp/mariamem/blob/5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c/docs/reviews/crc32c-candidate.md) · [固定版の境界検査](https://github.com/masahitojp/mariamem/blob/5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c/internal/generatedgo/code/base/base.go#L1461-L1474) · [前回の allocator 診断](https://github.com/masahitojp/mariamem/blob/4c3b928869a6ae9a09c52b894bd11d2b140a4c1e/benchmarks/trigger-sum-allocation/results-20261121/README.md)

**ホスト受け渡しと WASI。** 以前の #233 イベント再生から、同じ100明細についてクライアント送出から SQL 開始までと、SQL 終了から応答復帰までを足すと、SUM は3.973〜4.169 ms、差分加算は3.645〜4.644 ms。負荷には計測器、スケジューリング、通信両端が含まれる。ホスト shim は各条件に共通の改善先になり得るが、今回の数値から SUM 固有の増分も、それぞれの経路で短縮できる時間も確定できない。SQL 内の時計呼び出しは SUM と加算がともに10.02回/明細、SUM の計時は0.111〜0.121 ms/100件。先行 #188 の異なる固定版でも、定常 sender 化で対象になる送信窓は P1 で0.230 ms/100件だった。[現在の要求別区間の集計](request-windows.csv) · [現在の WASI 呼び出しと計時](https://github.com/masahitojp/mariamem/blob/7c5893b3d5198d2c5087dbb100e631dfe63a58bb/benchmarks/trigger-sum-bottleneck/results-20261121/T3.csv) · [先行ホスト受け渡し調査](https://github.com/masahitojp/mariamem/blob/03169391e3670922e10c2d3f58950c2aed9567fe/benchmarks/host-shim-cost/results-20261114/README.md)

## 変換と意味の確認

固定 guest の生成 Go には、32 bit の基底アドレスまたは定数に、定数の変位と幅を付けて通常アクセスを検査する箇所が911,337ある。幅は1・2・4・8 B、変位と幅の和は最大27,752,939。変換時にこの和を作り、実行時には64 bit に拡張したアドレスと加算して、アクセスのたびに現在の論理メモリ上限と1回比較する。許可されたときだけ元の変位を付けて同じアドレスにアクセスする。この入力域では和が64 bit であふれず、元の減算による3条件と同値。一般の MemoryEA と atomic/bulk の境界処理は元の実装を利用する。arm64 の生成機械語でも上限の LDAR と panic を残して境界の比較・分岐が3回から1回になった。[全変換先とハッシュ](binding.json) · [比較した機械語](bounds-arm64.asm)

返却アドレスと trap 値の差分検査21,736件、および実際の生成関数を使った境界越え、grow 前後、worker からの参照と trap の伝播を確認した。試験コード作成時にテスト用 Module の共有上限ポインタの初期化漏れがあり、試験用初期化を修正してから両検査を完走した。[検査ログ](checks.txt) · [固定 guest と関数表](guest.json)

## 次に判断を変え得る証拠

CRC 型の置換については、照合順序の名前付き経路が SUM の SQL 内で合計2標本、スクリーニングしたハッシュ・十進算術は各0標本だった。全 SQL の末端別集計でも、SUM 3組合計1,125標本のうち dlmalloc が950、MemoryInBounds と MemoryEA が合わせて70。少ない標本から、別の個別計算を Go 化して目立つ改善が得られるとは判断できない。[SQL 末端の全順位](sql-leaves.csv) · [識別した関数群の定義](recipe/screen.py)

ホスト shim を続けて調べるなら、通常の prepared INSERT 成功応答で、フレーム受信後の JSON 復号・要求 ID への配送・呼出元復帰を個別に測るのが候補となる。現状の約4 msは送受信・待ちを含む合算であり、復号の削減可能量は不明。固定版には rows の存在判定を再走査せずに行う変更もすでにある。最初の出口は、実際の成功応答を使って CPU・割り当て・経過時間を対応づけ、同じ応答意味を保持できる1区間に反復可能な費用があるかを決めること。既存ハーネスで診断ビルド20分、P1 再生15分を測定上限の目安とする。先行の4 KiB受信バッファ試作は別の介入として記録済み。[現行の応答処理](https://github.com/masahitojp/mariamem/blob/5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c/internal/guest/guest.go#L241-L278) · [既存の復号変更](https://github.com/masahitojp/mariamem/commit/ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e) · [過去の受信バッファ試作](https://github.com/masahitojp/mariamem/blob/abfffabf/benchmarks/response-buffer/results-20261114/README.md)
