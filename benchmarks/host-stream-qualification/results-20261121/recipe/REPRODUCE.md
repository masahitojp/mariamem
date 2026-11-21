# P8 と終了時の検証を再現する

固定製品 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c を worktree/ に checkout し、隣に temp/ と evidence/published/recipe/ を置く。Go 1.27.4、macOS arm64、固定モジュールキャッシュ、Python 3、現在のプロセスRSSを取得できる /bin/ps が必要。SQL ハーネスは履歴 7c5893b3d5198d2c5087dbb100e631dfe63a58bb から復元する。通常バイナリのホスト・ストリーム実装と起動用の overlay は de04aaa7aaf2b8d67c764012111feed6b3d34bac のファイルとバイト比較してビルドする。各ビルドで scripts/git_identity.py がソース commit を検査する。性能用バイナリには診断用の停止点を入れない。

~~~sh
mkdir -p temp evidence/published
r=evidence/published/recipe
python3 "$r/guard.py" . 1200 python3 "$r/build_qual.py" . perf
python3 "$r/guard.py" . 400 python3 "$r/campaign.py" . pre
python3 "$r/guard.py" . 1200 python3 "$r/campaign.py" . main
python3 -B "$r/reduce.py" evidence/published

python3 "$r/guard.py" . 1200 python3 "$r/build_qual.py" . fault
export MARIAMEM_BENCH_STREAM=both GOMAXPROCS=8 TMPDIR="$PWD/temp/gotmp"
./temp/fault.test -test.run '^TestQualificationFullStream$' -test.count=1 -test.timeout=90s -test.v > evidence/published/fault-first.txt 2>&1
./temp/fault.test -test.run '^TestQualificationFullStream$' -test.count=5 -test.timeout=150s -test.v > evidence/published/fault-repeats.txt 2>&1
echo $? > evidence/published/fault-repeats.exit
~~~

上の2つの故障試験の終了コードは今回1。入力満杯の途中で内部 Shutdown を呼ぶケースが EOF を返したためで、厳密な試験を失敗として保存している。後続の試験は失敗原因を比較する独立の対照。リソースの解放を確認してから次のプロセスへ進む。

~~~sh
python3 "$r/guard.py" . 1200 python3 "$r/extra_build.py" .
for mode in os both; do
  MARIAMEM_BENCH_STREAM="$mode" ./temp/extra.test -test.run '^TestQualificationPartialControl$' -test.count=6 -test.timeout=90s -test.v > "evidence/published/control-$mode.txt" 2>&1
done
./temp/extra.test -test.run '^TestQualificationClientDrain$' -test.count=6 -test.timeout=90s -test.v > evidence/published/public-drain.txt 2>&1

python3 "$r/guard.py" . 1200 python3 "$r/memory.py" . build
python3 "$r/guard.py" . 400 python3 "$r/memory.py" . run
mkdir -p temp/pipe-tests
cp "$r/pipe.go.txt" temp/pipe-tests/pipe.go
cp "$r/pipe_test.go.txt" temp/pipe-tests/pipe_test.go
(cd temp/pipe-tests && GO111MODULE=off go test -race -timeout=90s -count=10 -v .) > evidence/published/pipe-race.txt 2>&1
python3 -B "$r/check_diagnostics.py" evidence/published
~~~

- 各負荷は新規プロセス。設定 os と both を6組で交互順にする。各プロセスの6波のうち先頭1波をウォームアップで除き、残り5波の平均で同じ組の短縮率を計算する。主表はその6組の中央値。OS・候補の時間は6組の算術平均。ピークRSSはプロセス内各波の終了時までの Getrusage.Maxrss の最大値（macOS ではバイト）を使う。プロセスCPUは P8 の全実行スレッドの user+system。負荷ウィンドウは全8 worker の準備完了後から、全 worker が処理完了するまで。検査・Close を待つ。大きな応答の検査と混在負荷の read-after-write は timed interval に含まれる。全体の検証でローカル TCP リスナーが必要。クライアントの計測経路は Database.DialContext の net.Pipe。
- INSERT は同じスナップショットから8個の DB を用意し、それぞれ40注文100明細を1トランザクションで投入。トリガー本文、注文別集計、監査、在庫、FK・CHECK、Close を照合。混在は1 DB・8同時接続で別々の行をそれぞれ50回更新し、その都度 SELECT で値を検査する。大きな応答は同じ1 DBに8接続、各12回の SELECT で接続と順番を示すプレフィックスに256 KiBを連結し、96件すべての全バイトを照合する。したがって1波あたり約24 MiBのアプリケーション応答になる。
- 初回の高水位検査を補う C 限定の再測定では、全8 DBの準備後・SQL完了直後・Closeと GC 後で ps の現在RSSを読む。1組6波を新規プロセスで各モード6組。前回と異なる同期とサンプリングがあるため、元のRSS結果をこの追加実行で置き換えない。
- 故障診断は実ゲスト・実ホストを起動する。読み手を一時停止し、16 KiBを使い切って書き手に未送信部分が残った条件分岐でのみ合図を出す。キャンセルとクライアント切断では読み手を人為的に再開する前に、ゲストの終了・サーバー処分・転送ディレクトリ消失を検査する。通常の排出、未完の直接 Call に重ねる Shutdown、通信中の Server.Close は別ケース。OSとの部分送信対照はカーネル容量に依存しないよう両者とも16 KiB送信済みで次の書き込みを止める。
