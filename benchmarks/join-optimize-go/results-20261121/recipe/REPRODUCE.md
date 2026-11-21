# JOIN::optimize の呼び出し単位の計時

macOS arm64 で worktree/ に製品 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c を checkout し、隣に temp/ と evidence/published/recipe/ を用意する。ここにあるレシピと既存の固定 Go モジュールキャッシュを用いる。ソース確認には scripts/git_identity.py を使い、機械的な検証を有効にした通常の Python 3 で実行する。Go のバージョンと実行環境は runs/environment.json に保存する。Go ビルド時のネットワーク利用は無効、SQL 比較はループバックを使用する。

作業領域直下から以下を実行する。

~~~sh
for mode in base parent branch deep; do
    python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . "$mode" || exit 1
done
python3 evidence/published/recipe/guard.py . 900 python3 evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
~~~

SQL 入力は 706072d8dbfa76acb23d302d6bfaa08b91c444b5、比較ハーネスと関数表は 7c5893b3d5198d2c5087dbb100e631dfe63a58bb、要求 ID・応答フレーム・SQL・トリガーの帰属は a81baaef944c69f67666277ae189422ef76d2c47 から復元する。ビルドごとに固定製品の commit 型と SHA を検証する。生成 Go の名前・引数・戻り値は固定ソースから読み取り、ゲスト関数表の件数 21,791 と展開済み SHA-256 を照合する。

## 計測境界

base は無計測。parent は対象 DB の最外トリガー配下で実行される Fn14986（JOIN::optimize）への出入りを記録。branch は Fn14986 と Fn15000（JOIN::optimize_inner）に書かれた生成 Go の直接呼び出しと関数表による間接呼び出しを計時する。deep は JOIN::build_explain、optimize_cond、make_join_statistics、JOIN::optimize_stage2、SQL_SELECT::test_quick_select、choose_plan、JOIN::prepare_stage2 の本体の呼び出しにも同じ計時を加える。呼び先だけを横断的に計時すると別経路の値が混ざるため、対象の呼び出し元に型付きラッパーを挿入する。関数表の検索と引数の評価はラッパーに入る前に行われる。間接呼び出しは呼び出し元関数先頭からの相対行番号で識別し、同じ場所で取り得る実際の転送先はまとめる。

親、子ともに同じ単調時計を使い、スタックの切り替えで直前の区間を計上する。exclusive は現在最も内側にある計測対象に割り当てた ns で、全行の合計が親の inclusive に等しい。inclusive はその呼び出し配下で、同じ辺が再帰的に登場しても重なる時間は一度だけ数える。親の exclusive は計装した子の外であった時間で、インライン展開された計算、メモリアクセス、Go のランタイム処理、時計を読む負荷を含み得る。生成 Go の直接呼び出しは同じ呼び出し元・呼び先をまとめて集計する。枝番号は全モードで固定。edges.json は静的に存在する辺、ranked.csv は定常区間で実行された辺のみ。edges-by-block.csv は対応する4組の各値。

## SQL と実験順序

A は明細 INSERT で元の SUM、B は差分加算、C は明細 INSERT トリガーだけを削除する。親注文の監査トリガーを含むそれ以外の条件を揃える。P1・各 DB 40注文100明細、同一準備済み SQL で測り、前後に登録本文・注文別合計・監査・在庫・制約・Close を検査する。各モード×条件で検証用1 DB、続いて4組、各組の各プロセスで新規12 DB の先頭2件をウォームアップとして除外する。順序はキャンペーンに固定した4種類の SQL 順と、各モードが各位置に1回ずつ出る4種類のモード順。組ごとに残り10 DB の時間を合計して10で割り、ms/100 INSERT とする。欠測補完、外れ値除去、観測負荷の差し引きは行わない。

## 低負荷での再確認

初回試行の SUM の第1組で計測点の多い版の親時間が延び、最長の下位呼び出しが get_key_scans_params だった。固定した上位2経路、その統計作成から索引範囲評価へ降りる2辺の合計4辺だけを残した focus と parent を、A の4組で順を交互にして再測定する。B/C は各1 DB の事前検査。追加計時版での全過程と、対照との親時間・区間の数値を分けて保存する。

~~~sh
python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . focus
python3 -B evidence/published/recipe/guard.py . 900 python3 -B evidence/published/recipe/focus.py run .
python3 -B evidence/published/recipe/focus.py reduce evidence/published
~~~

first-attempt/ は初回に終了できなかった実行の記録。無効な入力や SQL エラーは見つからず、C の親だけを測る版の DB 11・ordinal 39 のトリガー空チェック2回の合計が 0 ns で、旧検査の厳密な正値条件に触れた。失敗したプロセスのトレースとログ、およびそれまでに保存できたデータを含む。C だけは 0 ns を受け入れ、フレーム・回数・順序・SQL 上限・最適化内の事象0を引き続き検査する。主集計は修正後に全条件を初めから実行した runs/ だけを使う。
