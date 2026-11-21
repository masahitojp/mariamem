# 要求・応答ストリームの再現

固定製品 `5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c` を専用の worktree/ に checkout し、隣に temp/ と evidence/published/recipe/ を置く。各ビルドは最初に git_identity.py で commit 型と source_commit を照合する。SQL の種・検証は 706072d8dbfa76acb23d302d6bfaa08b91c444b5、3条件のハーネスは 7c5893b3d5198d2c5087dbb100e631dfe63a58bb、診断タイムラインは a81baaef944c69f67666277ae189422ef76d2c47 の履歴を使用する。Go モジュールキャッシュ・Go 1.27.4、macOS arm64、Python 3 が必要。Go ビルドは CGO=0 かつオフライン。通常の DB 作成ではローカルリスナーも開く。実測の接続は Database.DialContext 経由の net.Pipe で、今回切り替えるリンク済みゲストの内部入出力とは別の経路。

~~~sh
for mode in raw trace; do
    python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . "$mode" || exit 1
done
mkdir -p temp/pipe-tests
cp evidence/published/recipe/pipe.go.txt temp/pipe-tests/pipe.go
cp evidence/published/recipe/pipe_test.go.txt temp/pipe-tests/pipe_test.go
(cd temp/pipe-tests && GO111MODULE=off go test -race -count=5 -timeout=60s -v .)
python3 evidence/published/recipe/guard.py . 900 python3 evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
~~~

raw は要求ごとの時計を含まない同一バイナリ、trace は既存のフレーム・要求 ID 照合と21時点を加えた同一バイナリ。各プロセス開始時に MARIAMEM_BENCH_STREAM で、両方向 OS パイプ、要求だけ・応答だけ・両方向を16 KiBリングにする各設定を選ぶ。選択時の分岐は DB 作成時。フレーム形式・JSON・キュー・監視は同じ。リングはバイトをコピーし、満杯時は書き手、空のときは読み手が条件変数で待つ。空 Write はデータを送らず完了する。OS パイプ側とリング側の違いはコピー、カーネル呼び出し、バッファ容量、起床・スケジューリングを含むので、機構別の時間は分離していない。リング2本の場合は生存中のリンク1つにつき固定バッファ計32 KiB（OS側にもカーネルバッファがある）。本文全体をリングに収める条件は不要。

各 DB の40注文に100明細を1トランザクションで逐次 prepared INSERT。各設定で注文別合計・明細・監査・在庫・FK/CHECK・Close、登録トリガー、本数をハーネスで検査する。A=元 SUM、B=差分加算、C=明細 INSERT トリガーだけ削除。raw の時計は100回の Exec ループ。準備・COMMIT・検証は窓外。CPU は同じ区間を囲む Getrusage のプロセス user+system、他の goroutine を含む。GOMAXPROCS=8、GOGC=100、同時に1 DB。ビルドとテストの終了後に計測する。

各バイナリ×設定×SQL で1 DBの事前検査。以降は各プロセス12 DBの先頭2 DBをウォームアップとして保存し、残り10 DBで ms/100 INSERT を求める。raw は各 SQL 6組、候補の順序は全6順列、各組の前後に同一設定の OS 対照。各候補の短縮は（前後OS平均−候補）、短縮率はそれを同じ組の前後OS平均で割る。6組の中央値、範囲、正の組数、同一OS間の絶対差の中央値を示す。試行前に定めた判定は各条件で正の組が5以上、かつ短縮中央値が OS 間の揺れの中央値を上回ること。信頼区間は算出していない。trace は3組の SQL 順を回し、4設定をそれぞれ実行、対応区間の差を等重みで平均する。異なるバイナリ同士から短縮を引き算しない。各要求で順序・ID・slot・フレーム長・区間の和を検証し、全要求の trace を圧縮保存する。外れ値は削除しない。
