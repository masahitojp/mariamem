# 最外トリガー時間の分解

固定製品 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c を専用作業領域の worktree/ に checkout する。temp/ と evidence/published/ を用意し、後者にこの recipe/ を配置する。履歴には a81baaef944c69f67666277ae189422ef76d2c47（要求 ID・worker・SQL・トリガーの外側計時）、7c5893b3d5198d2c5087dbb100e631dfe63a58bb（ハーネスと関数表）、706072d8dbfa76acb23d302d6bfaa08b91c444b5（SQL 入力）が必要。macOS arm64、Go 1.27.4、Python 3、固定 go.sum の Go モジュールを使う。SQL ドライバーはループバックを使用する。

作業領域直下で実行する。

```sh
for mode in base outer phase detail; do
  python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . "$mode" || exit 1
done
python3 evidence/published/recipe/guard.py . 900 python3 evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
python3 -B evidence/published/recipe/verify.py evidence/published
```

各ビルドが最初にソースの commit 型と SHA を確認する。ゲスト関数表は展開後 SHA-256 1f8dcd20057090cde400f1439d0cc9d1c933b16490ba8ecd22269d909f1fe475 に固定し、選んだすべての関数名と生成 Go の定義を検査する。base は動作を変更しない製品、outer は前回と同じ計測点、phase は処理段階の入口・出口、detail は phase に5種類の割り当て関数の入口・出口を追加したバイナリ。phase には割り当て関数の追加プローブが入らない。

P1、GOMAXPROCS 8、GOGC 100で各 DB に40注文・100明細。各モード・各条件を1 DBで事前検査し、次いで4組（ABC / BCA / CAB / CBA）の各条件で独立した4プロセスを実行する。モード順は Williams の4順序で各モードが各位置に1回現れる。1プロセス12 DB の先頭2 DB はウォームアップとして保存し、残り10 DB の1,000要求の和を10で割って ms/100件を得る。計時中の順序の変更、外れ値除去、負荷分の事後補正は行わない。

各 json.gz は DB・明細単位の要求番号、外側の単調時刻21点、TriggerNS と呼び出し回数を含む。phase/detail の Inner.NS は、現在いちばん内側にある処理段階（行）とメモリ関数（列）の ns。行0は指定した処理段階の外、列0は指定したメモリ関数の外。再帰・入れ子・兄弟区間の切り替えを同一時計で課金し、要求ごとの全セルの和が最外 TriggerNS に一致する。メモリ列はすでに各段階の合計に含まれる。phase のメモリ列1〜5は未計測を表す。SubtreeNS は sites.json の段階7〜11（サブクエリ準備・JOIN・評価・SUM加算）、4〜6（UPDATE準備・実行・計画）、および両者が同時にスタック上にある時間の和集合。cleanup や表を開く処理がそのスタック外で行われれば、その分はサブクエリの計時に含めない。

MemCalls はフックした関数の動的呼び出し数。ArenaRefills は alloc_root の動的範囲内で観測した dlmalloc の回数、MallocBytes はその段階の全 dlmalloc 要求バイト数。これらは解放後の残量や Go ヒープの割り当て量を表さない。Item_sum_sum::add_helper の呼び出しが SUM の加算点。fixture の注文 n=1..40 は 1+n%4 明細であり、各注文について現在挿入した明細の位置を ordinal と照合する。item-position.csv の粒度だけは µs/1 INSERT、その他の時間表は ms/100 INSERT。
