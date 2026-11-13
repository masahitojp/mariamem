# pgmem公式 model-case とmariamem — 2026-11-13

結論: 公式ショップの70テストを両製品で通した。固定5回のprocess wall中央値はpgmem405.879ms、mariamem523.895ms（+29.08%）。範囲は377.673–423.358ms / 462.646–575.093ms。今回の移植条件ではpgmemが全5組で短い。製品一般の優劣や元サイトのM3数値の再現ではない。

基準は [公式modelcase README](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/bench/modelcase/README.md)。20カテゴリ/500商品/1000ユーザー、40 sample orders、読取50件と更新20件、読取は共有DB、更新は独立Fork。公式のwarmup1回＋本計測5回。各製品の実行順を交互にし、全本計測700 leaf tests PASS、warmup140件もPASS。並列度8、GOMAXPROCS8/GOGC100、CGO0。テスト期待値は維持し、SQLのplaceholder等だけ移植した。

## 結果

|指標 ms|pgmem|mariamem|
|---|---:|---:|
|process wall中央値（起動前〜process終了）|405.879|523.895|
|公式recorder elapsed中央値|331.934|515.149|
|boot中央値|51.085|44.865|
|import中央値|64.855|29.729|
|snapshot中央値|15.992|5.019|
|読取共有用の追加Fork中央値|不要|16.254|
|更新用Fork: 各process内中央値の中央値|23.813|28.881|
|sample投入: 各process内中央値の中央値|32.028|80.838|
|test本体: 各process内中央値の中央値|0.855|3.412|

重なるspanや中央値を加算して全体差を説明しない。sample/testは読取・更新の混在であり工程別CPUではない。process wallはpackage初期化とprocess終了も含み、recorderの外にあるpgmem初期化等がある。公式Web timelineと対応するのはrecorder elapsedで、こちらではmariamemは約55%長い。全試行はruns.jsonとtrace/logに保持。Closeの個別時間は公式spanにないが、fixture closeとt.Cleanupはelapsed/process wallに含む。pgmemの非同期資源解放を独自drainで待つ変更はしておらず、同じ解放完了条件の比較ではない。

## 移植差分と限界

- SQL/driver: pgxからgo-sql-driver/mysql、$nから?（引数順も調整）、concat/cast/generate_seriesはMariaDBのCONCAT/seq tables、UPDATE FROMはJOIN UPDATE、整数除算はFLOOR。INSERT RETURNINGとprepared statementsは維持。ClientFoundRows=trueでPostgreSQLと同じ更新対象件数を返す。
- schema: serial→AUTO_INCREMENT、text keys→VARCHAR、timestamp/ENUM、PostgreSQL trigger functionsをMariaDBのevent別triggerへ移植。商品名lower式indexは通常name indexへ変更。case-insensitive collationとの実装差が残る。
- PostgreSQLの5 migration filesはMariaDBで1ファイルへまとめており、migration bookkeeping件数/DDL transaction/statement batchingは同一ではない。MariaDBのDDLは暗黙commit。importの短さをエンジン単独の性能差と解釈しない。
- mariamem Snapshotはroot DBを消費する。読取共有DBを追加1 Forkして公式と同じ読取50件共有/更新20件独立を成立させ、その費用をreader_forkに含めた。pgmemは元serverを再利用する。
- 両方ともin-process wire dialer。mariamemのSQL protocol/driverとPostgreSQLのpgx protocol/driverは異なる。テスト本体差を純粋なengine CPU差とはしない。
- Docker/Testcontainers/devboxは今回実行していない。公式の同じテストスイートをpgmem/mariamemへ適用した比較であり、公式の全backend一覧の再計測ではない。
- shared M1/16GiB/macOS27.2.1/Go1.27.4、専用静穏hostやM3ではない。5回のみでtail/RSS/CPU保証なし。今回はメモリを計測していない。

## 対象・保存・再現

inputs.jsonとbinary buildinfoにsource/guestではなく製品source identityとbinary hashを記録。mariamem source_commit 0f5b26f370875d26bd337031f48856d8f57c10db、pgmem v1.18.2 source_commit a61005d37d01e6671f814fe8ca828222e8147df4、tag_object_sha 145e5d2fc70983b89a4bdd8438e547fcd60244ed。両checkoutはbuild前にgit_identity.py inspect HEADでcommit確認。mariamem製品のruntime/guestは変更していない。

maria-harness/は実測した最終移植source（UPSTREAM-LICENSE付き）。公式原本は上記immutable ref。fresh managed workspaceでtemp/pgmemに公式ref、worktreeに製品ref、evidenceへ本ディレクトリを置く。prepare.pyが移植を生成し、build.pyがGo1.27.4で両バイナリをbuild、measure.pyが1warmup+5交互pairを実行する。10GiB/空き12GiB、build1800秒、計測900秒、各process130秒。失敗すれば止まり、サンプルを除外しない。

最初のpilotはpgmem70件PASS、mariamemはSnapshot前の接続退役待ち不足で停止（pilot1/）。WaitDisconnectedをSnapshot span内に追加してから全cohortを開始した。このharnessエラーを製品の失敗・計測値とは数えない。初回workspace runnerはnested history guardで停止し、source bundle保存後もfailed receiptを改変せず、以後standalone disk guardで監督した。依存downloadのsandbox DNS失敗はescalated buildで解消。CI/engine再生成/製品変更は実施していない。

推奨: この公式workloadでも差は残る。次の調査はサンプル投入とテスト本体のsource対応が対象候補だが、移植差とprotocol差を含む。Fork初期化だけを全体差の原因とはしない。追加試作はこの計測から自動開始しない。
