# Go レイヤーの要求別計時

固定製品 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c を専用作業領域の worktree/ に checkout する。temp/ と evidence/published/ を用意し、後者にこの recipe/ を置く。7c5893b3d5198d2c5087dbb100e631dfe63a58bb と 706072d8dbfa76acb23d302d6bfaa08b91c444b5 の既存ハーネスを同じリポジトリの履歴から復元する。Apple M1・Go 1.27.4・Python 3・固定 go.sum のモジュールで実行し、ローカルのループバック接続を許可する。

作業領域直下で次を実行する。各ビルドで入力コミットをチェックする。base は通常の製品と同じコードで raw 窓を測る。on だけに Go overlay を適用する。

```sh
python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . base
python3 evidence/published/recipe/guard.py . 1200 python3 evidence/published/recipe/build.py . on
(cd temp/harness && GOTOOLCHAIN=local GOWORK=off GOPROXY=off CGO_ENABLED=0 GOCACHE="$PWD/../gocache" TMPDIR="$PWD/../gotmp" go test -trimpath -count=1 -v ./timeline)
python3 evidence/published/recipe/guard.py . 900 python3 evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
```

## 再生条件と分母

各プロセスは P1（同時に1 DB、その DB で同時に1要求）、GOMAXPROCS=8、GOGC=100。事前検査は各バイナリ・各 SQL 条件で1 DB。本計測では ABC / BCA / CAB の3組で、各組・条件ごとに base と on を別プロセスとして実行する。第1・3組は base が先、第2組は on が先。各プロセスで12 DB に各100明細を投入し、先頭2 DB を固定ウォームアップとして保存、後続10 DB を集計する。親注文、PREPARE、COMMIT、チェック、Close は raw 窓の外。変換は go shim、マーカー、入力フレームの観測に限り、ゲストソースや SQL 本文には加えない。

各ファイル名は組（0は事前検査）・SQL 条件・計測モード。JSONL は登録トリガーとループ時間・DB 検査。json.gz は全100要求の単調時計の生時刻（ns）、DB・投入番号・ホストが割り当てた ID/slot、入出力バイト数、SQL 内のトリガー時間を持つ。T[0] から T[20] は timeline.go.txt の Client から ClientEnd。入力フレームの ID/slot/サイズ、worker ID、出力生成時の ID/slot、受信 Process・応答 ID/サイズを照合する。Fn5581 の対象 SQL への対応は P1 の有効要求に限定し、同じ Module の最外トリガーの経過時間を再帰で二重加算しない。

連続時刻の差20区間の和は各 Exec と ns 単位で一致する。100件の個別 Exec の総時間と、ループ全体の raw 計時に挟まる観測処理などは observer-cost.csv に別記。各組の表はウォームアップ後1,000件を100件に正規化した算術平均。stages.csv の先頭20行だけが排他的で、以降は内訳・小計・全体。異なる goroutine の同時実行は直列の CPU 時間に換算しない。

`python3 -B evidence/published/recipe/verify.py evidence/published` は事前検査を含む全記録を読み直し、要求欠落・重複 ID・逆順タイムスタンプ・不可能なトリガー時間を作った負例を確認する。grouped.csv は同じ20区間を読みやすくまとめ、SQL 区間を最外トリガー内とそれ以外に分けた排他的な表。
