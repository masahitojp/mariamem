# 再現

macOS arm64、Go 1.27.4、Python 3.9以降。必要なGoモジュールをローカルキャッシュに準備する。W直下の worktree は a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb のクリーンなmariamem、temp/gotmp はビルド用、evidence/published/recipe にこのディレクトリを配置する。履歴にはハーネス10665616、ベースbe12aeb6、関数表7c5893b3の実験refも含める。以下はWから実行する。

~~~sh
mkdir -p temp/gotmp
for kind in raw diag
do
  python3 -B evidence/published/recipe/guard.py . 1200 python3 -B evidence/published/recipe/build.py . "$kind" || exit 1
done
python3 -B evidence/published/recipe/campaign.py . pilot
python3 -B evidence/published/recipe/campaign.py .
python3 -B evidence/published/recipe/reduce.py evidence/published
python3 -B evidence/published/recipe/scheduler.py .
~~~

rawのOS対照はlinked.goをベース版に置換する。diagは同じ2条件で共通の時計とフレーム観測点を持ち、Goの-test.traceでGoスケジューラ状態を記録する。Goコードのworker/response地点は以前の固定ゲスト検証と同じFn267/Fn265。OSの同一タイマーやネットワーク遅延を呼び時間へ二重に足さないよう、主表は単調時刻の境界で分割する。クライアントのDB名はFork作成時のコンテキストから継承し、共有readerだけは共有sampleレーン名に対応させる。スパンの重なり・呼び出しの外は独立した列。各レーンはbegin、3 prepare、40注文、100明細、100在庫更新、commitの完了とSQLのテスト結果を検証する。

主比較は条件インデックスをraw-os/raw-ring/diag-os/diag-ringとして、0132, 1203, 2310, 3021を6巡する。実行トレース原本は400 ms超を含んだ診断プロセスを保持する。追加判定は両方式合わせて診断付きの閾値越えがゼロの場合のみ。閾値を満たした1件以上の生トレースを解析する場合には、temp に <run>.trace として展開する。scheduler.py が go tool trace -d=parsed を用い、同じDBと要求IDに対応したworkerとreplyログのgoroutineを照合し、遷移時刻の差分・待機スタック・起床させた側のスタックと生成履歴を取り出す。

保存された実測値だけを再集計する場合は、この証跡のルートで以下を実行する。verify.pyにはこの固定データに固有の検算も含む。

~~~sh
shasum -a 256 -c SHA256SUMS
python3 -B recipe/reduce.py .
python3 -B recipe/verify.py .
shasum -a 256 -c SHA256SUMS
~~~
