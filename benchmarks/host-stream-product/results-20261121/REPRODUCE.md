# 製品候補の比較手順

候補は candidate.json、ベースは baseline.json の source_commit。両者を同じバージョンの Go で比較する。計測には Go 1.27.4/macOS arm64、通常の製品検査には CI の Go 1.26.11 を使用した。

候補のクリーンな worktree の親を W とし、その直下に worktree、temp、evidence を置く。measure.py を evidence に配置する。GOMAXPROCS=8、GOGC=100。計測バイナリはすべて go test -c -p 1 -vet=off -trimpath -buildvcs=false で作る。デフォルト CGO、モジュールは製品の go.mod/go.sum を使用。コミットは scripts/git_identity.py --root . inspect HEAD でビルド前に確認する。

1. worktree で git show be12aeb6ebed61f291d98ffa08b872a03695900b:internal/guest/linked.go を temp/baseline-linked.go に保存する。temp/baseline.json は Replace に候補の internal/guest/linked.go の絶対パスからこのファイルへの対応1件を持つ Go overlay。親と候補間の実行時変更はこのファイルと新しい内部リング。対照ではリングを呼ぶ経路がない。
2. worktree から -tags=integration ./tests/gointegration を2回ビルドし、製品を temp/candidate.test、上記 -overlay を加えた対照を temp/baseline.test とする。両方とも同じ新規 BenchmarkLargeResponseBatch。1回は8接続×12クエリ、毎回スロット・反復固有の接頭辞と256 KiB全バイトを検査する。計測窓は接続と期待値の準備後から全応答の検査まで。CPUはプロセスの getrusage の user+system 差分。
3. 10665616ba6f00d72b5563158a50bfb7cb2305d2 の benchmarks/read-transport/harness を temp/model に置く。対象外の store/read_profile_test.go を除く。go.mod の置換先を worktree の絶対パスにし、mysql と edwards25519 を製品と同じ v1.10.1 と v1.2.0 にして、製品の go.sum をコピーする。ここから -mod=readonly ./store を手順2と同じ overlay の有無でビルドし、temp/model-candidate.test と temp/model-baseline.test とする。
4. 全ビルドと他の検査が終了してから python3 evidence/measure.py "$W" を実行。各条件で事前意味検証とウォームアップを行い、large/P1/P8 を6ブロック実行。OS先行と候補先行を交互にする。modelcase は起動・サンプル投入・50読取・20更新・同期Closeまでの TestMain 内時間とプロセス全体のCPU。強制GCや診断フックは挿入しない。SQLベンチの1回は96件、modelcase の1回は70ケースで、表の単位は各バッチ全体。
5. 恒久的な回帰テストは ./internal/guest の TestFullLinkedStreamLifecycle と同パッケージのリングの検査。race はリングソースと単体テストを -race -count=15 で実行した。
6. 実ホストの追加故障検査には 25c654c72a27fa24c127953aa92c52209f029189 の benchmarks/host-stream-qualification/results-20261121/recipe から prepare_fault.py、fault_test.go.txt、extra_test.go.txt を使う。prepare_fault.py 内の experiment_stream.go を byte_pipe.go に置き換え、初期 overlay.json の Replace に今回の byte_pipe.go の絶対パスから同じパスへの1件を入れて実行する。生成された fault-overlay.json に extra_test.go.txt から TestQualificationClientDrain とその使用importのみを追加し、internal/host/qual_extra_test.go に割り当てる。go test -p 1 -vet=off -trimpath -overlay=<fault-overlay.json> ./internal/host -run 'TestQualification(FullStream|ClientDrain)' -count=6 -v。書込側が本当に満杯を待つ分岐に入ってから操作する。この観測フックは性能計測・製品ビルドの対象外。

厳密な故障試験で入力の途中送信と内部 Shutdown が重なって EOF となったケースも全件保存する。OS 対照との比較は同じ履歴の extra_build.py の qualWrite と extra_test.go.txt の TestQualificationPartialControl を使用する。ビルド前の固定SHAの期待値を candidate.json に合わせ、fault-overlay.json に qualWrite の置換と extra_test.go.txt を追加する。候補はこの overlay、対照には baseline.json の linked.go 置換も加える。両方で -run '^TestQualificationPartialControl$' -count=6 -v を実行し、接続・Shutdownの結果と disposed を検査する。厳密な試験の失敗と、この対照による互換性の確認はそれぞれ記録する。

初回P8のsampleで450 msを観測したため、測定前に親IssueでP8限定の6組再検を宣言した。python3 evidence/measure.py "$W" p8-tail でウォームアップを除き、初回と逆に候補先行からAB/BAを交互にする。P8個別ランのsampleスパンが400 ms以上となった回数・最大値を照合し、初回と再検を別々に報告する。*_cpu_ms のうちスイートはプロセス全体、largeは96応答のSQL区間。CPUにはカーネル時間を含む。
