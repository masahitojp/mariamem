# MariaDB 13.2.0 Preview feasibility / guest patch management

## Human Review / decision

**FEASIBLE WITH PATCHES**。現行shibukawa converter＋既存7パッチで13.2.0をbuild/変換し、
新生成Hostの実SQLとfocused acceptanceが成立した。Wireのhardcoded version表示は不整合が残る。 正式採用・複数系列の製品サポート・Release qualificationではない。
12.3.3 LTSをv0.5.0の本命として維持する。13.2.0の価値は新系列への移植性を
検証することであり、Previewの成熟度をLTSと同一視しない。

パッチ管理は **B: common + small series-specific application hunks** を推奨する。
今回、新しいmajor別ディレクトリやpatch managerは実装していない。
移植の意味論はほぼ共通だが、同じdiff bytesが全系列へ適用できるとは限らない。
exact source archive/hashとordered patch/hashの小さなmanifestを基準にし、
実際に異なるhunkだけ分ける。patch適用成功は実行correctnessの証明ではない。

## Fixed inputs / scope

- main: `386a62c3669e37bb8aaad58cd0aca8da893b3d80`。main・release tags不変更。
- 12.3.3比較実験: `5f14221463b6400e72e72a115bd1cc1a3acee88d`
  ([元報告書](https://github.com/masahitojp/mariamem/blob/5f14221463b6400e72e72a115bd1cc1a3acee88d/docs/reviews/v05-stable-guest-feasibility.md))。
- 実build source: `3ecdf2d4f27be6c983a648088d2ee6a5d0ad86bf`。
- 13.2.0: [公式配布一覧](https://mariadb.org/mariadb/all-releases/)の2026-09-23 **Preview**。
  tarball `VERSION` は `13.2.0`, `SERVER_MATURITY=alpha`。
- [公式source archive](https://archive.mariadb.org/mariadb-13.2.0/source/mariadb-13.2.0.tar.gz):
  SHA256 `5b6a588e86f1169fef44760846b6e9e96b08d7a7e52fb4b887c5feb06ca39f3a`。
  [公開checksums](https://archive.mariadb.org/mariadb-13.2.0/source/sha256sums.txt)と取得bytes一致。
  調査時GitHub `MariaDB/server` は13.2.0 tag/13.2 branchをadvertiseしなかった。
  Git commit/tagを推定せず、公式tarball identityを使用。署名検証は未実施。
- lite4 recipe/API 6ファイル: `24be9371a2f6c71250a2356631ad6feab2280b02`、12.3.3と同じ各hash。
- shibukawa wasm2go: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`。
  imported-memory / import-function-index / relaxed-madd / pure-memory32 /
  controlled-thread-traps / host-logical-memory / linear-memory-ownerの既存7patch不変更。
- wasixcc0.4.7 / LLVM23.1.0 / sysroot2026-07-03.1 / Binaryen133 / Go1.26.8。
- Host/Wire/SDKのsource不変更。新guest hashへのdev compatibility bindingのみ既存dev routeが行う。
  canonical `guest/source.patch`、generated code、accepted guest/translation/toolchain receipts不変更。
- Linux arm64 Dockerでguest build、macOS arm64で新生成Go/native実行。
  native Ubuntu x86_64 acceptanceではない。Go public APIの独立consumer一式も未実施。Track Aのconverter・patch・成果物は使用しない。

[fixed inputs](v05-mariadb-132-feasibility-evidence/fixed-inputs.json)に実ファイルhashを保存。
workspace helper receiptのbase_shaは呼出元資料branch40b7f17を示すが、実branchは上記mainから作成。
receiptを改変せず、actual branch ancestryを区別して記録した。

## Source construction / patch comparison

13.2.0公式tarballはdependency sourceを同梱するため、既知の`libmariadb`と
`extra/wolfssl/wolfssl`の2か所のみ、12.3.3と同じ固定依存へ置換した。
その他の上流sourceは13.2.0のまま。checksum-bound lite4 recipe 6ファイルをコピーし、
experimental portability patch → unchanged canonical source.patch → unchanged init/auth hooksを適用。
実験descriptorは既存12.3.3の`guest/stable-input.json`名を流用しているが、内容はPreviewと明記。
これは13.2をStableと宣言する名前ではない。

| Patch/file | 解決する問題 / 層 | 12.3.3 → 13.2.0 | 破損リスク / upstream性 |
| --- | --- | --- | --- |
| CMakeLists.txt | embedded/WASIX以外のclient/tests/packageを除外しwasm target追加 | 同一patch | 中: target構成変更。汎用cross-build部分は提案可能 |
| cmake/os/Emscripten.cmake | lite4由来の別platform profile | 同一、新規ファイル。WASIX buildでは未使用 | 低。ただしproduction化時に不要scopeを除く候補 |
| cmake/os/WASIX.cmake | thread/simulated-AIO、host専用機能/PMEM等の無効化 | 同一、新規ファイル | 中: MariaDBのfeature options。WASIX portとして提案可能 |
| cmake/pcre.cmake | 子buildへのtoolchain伝播 | 同一 | 低〜中。一般的cross-build改善 |
| configure.cmake | compile-only probesが誤検出するfork/dlopen/fcntl等を無効化 | 追加内容同一、hunk行番号調整のみ | 中: feature probe変更。platform別に提案可能 |
| include/my_global.h | WASIX lock定数とDl_infoの競合回避 | 同一 | 中: libc headers。platform適応 |
| include/my_stacktrace.h | WASIXでcrash-resolver forkを無効化 | 同一 | 低。platform適応 |
| libmysqld/libmysql.c | 宣言のみで未実装のgetlogin回避 | 同一 | 低。libc capability依存 |
| mysys/CMakeLists.txt | wasmでhost CRC assemblyを選択しない | 同一 | 低。cross-build適応 |
| mysys/my_largepage.c | guest内PROT_NONE予約の代わりに4096-aligned allocation+zero-fill | 同一 | **高**: VM契約。単純なnative向け改善ではない |
| mysys/my_lock.c | WASIX未実装file lockをembedded isolated DB前提でno-op | 同一 | **高**: 複数プロセス共有datadirには使えない |
| mysys/my_timezone.cc | tzname不在時UTC | 同一 | 中: timezone前提。platform適応 |
| mysys/my_virtual_mem.c | NULL commit確保、decommit accounting、free、protect no-op | 実装同一、コメントから12.3限定表現を除去。上流file bytesも同一 | **高**: reclaim/zeroing/protection/accountingを別途検証すべき |
| sql/sql_plugin.cc | dynamic-loader無効経路のLEX_CSTRING型整合 | 同一 | 低。汎用修正としてupstream候補 |
| storage/innobase/fil/fil0fil.cc | absolute datadirの二重prefixを回避 | 同一 | 中〜高: recovery/path semantics。縮小native再現がupstream提案条件 |
| storage/innobase/log/log0log.cc | WASIXのredo mapping mprotect不可をguard | **適用位置・indent変更**。上流はPMEM条件内から成功mapping全体へ移動 | **高**: redoの再編。PMEM=OFFだけでは13.2の到達不能を証明できない |
| storage/innobase/os/os0file.cc | WASIX file lock不可 | 同一 | **高**: isolated backing所有権が前提 |
| storage/maria/ma_loghandler.c | directory fsyncがEISDIRになる制約 | 同一 | 中: durability契約。通常native filesystem向けには不適切 |

[比較JSON](v05-mariadb-132-feasibility-evidence/patch-comparison.json)はpatch bytesと変更行を区別する。
18-file patchの15file分はdiff bytesまで一致。configureは位置のみ、virtual_memはコメントのみ、
log0logはhunk移動とindent/コメント。
重要な系列差は上流の制御フロー: 12.3ではmprotectは`HAVE_PMEM && is_pmem`内、
13.2では成功したlog mapping全体が対象。移植方針は共通でも適用範囲は拡大している。
PMEM=OFFだけで13.2の全mapping経路が未使用とは判断しない。通常read-writeでは
非PMEMのlog_mmapはMAP_FAILEDを返すが、read-only/backup/archive経路は別に確認が必要。
12.3.3のpatchを13.2へ直接試した結果は17file成功、log0logのみ失敗。
canonical mariamem wrapper/source.patchは変更不要だった。適用後wrapper
`wasm/lite4mariadb.c`は12.3.3と同じSHA256
`d2b1a3c65b1f6a0b46de37221507b80150626c58eaa61d6033038ace46c40df9`。12.3.3同様のcanonical hunk fuzzは
実際のGNU patchログに記録し、新port側のfuzz0と混同しない。

共通patch候補もsource-onlyで検証した。PMEM hunkのcontextを狭めても12.3.3ではindent差で
fuzz0適用に失敗し、13.2では成功。この失敗を隠してfuzzやignore-whitespaceで通す方針は採らない。
続いてcommon 17ファイル＋redoだけの2variantをGNU patch fuzz0で両系列へ適用し、
両方PASSした。各系列のfull patch出力と、version名コメント正規化後に全18file一致
([source-only layout proof](v05-mariadb-132-feasibility-evidence/split-layout-result.json))。
この検証はコンパイル追加なし。実験成果物は既存同様1つの`experimental.patch`で再現可能に保ち、
管理方式のproduction化はHuman判断とする。

## Patch management decision

| 方式 | 重複/更新箇所 | 検出/意味論/再現性 | 検証・個人保守コスト | 判断 |
| --- | --- | --- | --- | --- |
| A Single | 最小、共通修正1箇所 | exact inputsなら再現可。ただしcontext差を吸収しようとすると適用条件が曖昧になりやすい | sourceapplyは安いが各guest実行検証は省略不可 | 共通部分の方針として有効、全hunk共用は今のdiffのままでは不可 |
| B Common + variant | 大部分1箇所、差分hunkだけ小さなvariant | exact series/release manifestがordered hashesを選択、未登録input拒否。意味論差も明示できる | 共通修正とvariant各1か所、対象guestごとのfocused検証 | **推奨** |
| C Independent | 18file全体を二重保守しdriftしやすい | 各々pin可能だが同じ修正の伝播漏れが起きる | 重複review/検証が大きい | 現差分では不採用 |

12.3実験で追加されたNULL commit / protect適応は、今回13.2にも同じ形で必要だった。
両archiveの`mysys/my_virtual_mem.c`はbyte-identical。一方、現行lite4 recipe元の同fileは
commit冒頭に`DBUG_ASSERT(ptr)`がありprotect関数はない。12専用patchと分類するのは誤りで、
番号ではなく実際のAPI契約に紐付けるべき共通適応である。

最小将来構造は共通portability patch、必要なredo-guard hunkの2variant、exact source/hashから
ordered patch/hashへ対応するmanifest。major12/13だけで意味論を選ばない。
12.3/13.2は説明上の系列名、実際の選択キーはpatch release + source digest。
次のpatch releaseでdiffがなければ同一variantを再利用し、変更がある場合だけ増やす。
canonical wrapper/init/auth overlayとtranslator7patchは別責務として管理する。
当面18file monolithic experiment patchを保存することと、将来のproduction管理方式は別である。

## Execution / correctness

| Gate | Result |
| --- | --- |
| Source/guest build | PASS、C/Wasm build 1回。準備後sourceはmacOS preflightとLinuxで同一hash |
| Translation / Generated Go / actual host | PASS、Go1.26.8、旧generated runtimeは使用せず |
| SQL actual version | **13.2.0-MariaDB-embedded** |
| Fresh / commit / rollback / Snapshot / Fork / Python LoadSnapshot | 初回dev smoke **2 PASS / 2.04 s**。persist後source削除、childからnewbaseline、sibling隔離も確認 |
| Owned snapshot / wire / multiple clients / idempotent Close | **27 PASS / 50.84 s**。ケース一覧はvalidation-results.json |
| Dev input/identity/failure helper tests | **21 PASS / 0.70 s** |
| Actual dev artifacts → existing Release guard | **拒否PASS**: wrong build contract。実guest.json/development.jsonを変更せず投入 |
| Canonical version/public-source/docs check | PASS、verify.py check --scope docs |
| Wire handshake version consistency | **FAIL**: actual SQL13.2.0に対しhandshake13.1.0。Host/Wire固定条件のため未修正 |
| Native Ubuntu / broad trap-thread-race / Release qualification | NOT RUN、今回のfeasibility完了条件外 |

[validation results](v05-mariadb-132-feasibility-evidence/validation-results.json) /
[SQL version](v05-mariadb-132-feasibility-evidence/sql-version-original-host.json)。
Owned suiteはmutation/growth/schema/commit/rollback、35childrenを含む世代・順序・並列、
import corruption/missing/extra/truncation/guest/format/symlink、source削除、FD handoff、
partial import/startup failureとCloseを検証する。Python reader threads、host processes/FDの
cleanupが通ったという範囲であり、全guest race freedomやnon-cooperative terminationの証明ではない。

**確認された不整合**: `internal/mysqlwire/wire.go` のhandshake literalが旧13.1.0に固定されている。
SQL実行guestは13.2.0だがclientのget_server_infoは旧版を返す。これは正常な版表示ではなく、
正式採用前にguest-bound metadataと整合させる必要がある。既存Host固定で実行可能性を
切り分けた結果であり、「全correctness PASS」やそのままproduction採用可とはしない。
今回のfocused suiteでSQL/transaction/所有権の回帰は検出されなかった。

ConverterはSSA fixpoint cap warningsと未証明f16 table rewrite OFFを出した。
新たなfunction/address patchは加えていない。変換成功を全命令/全経路の正しさへ一般化しない。

Guest内virtual memory移植は、Go hostのmmap linear-memory ownerとは別層である。
このpatchのdecommitはphysical releaseではなくaccountingのみ、nonnull recommitはzero-fillしない。
protect no-opはguest page protectionを提供しない。Wasm logical bounds/trapsを弱める変更ではないが、
MariaDB側がそれらのVM機能に依存する未通過経路の正しさを証明してはいない。
既存lite4/12.3port由来という理由だけで安全性を保証しない。
file-lock no-opも、Forkごとにowned backing/metadata/runtimeが独立する既存契約の範囲に限定する。
同じnative datadirを複数processで共有するサポートを主張しない。

## Build cost / resource evidence

| Phase | 12.3.3 wall s | 13.2.0 wall s | 13.2 user/system CPU s | 13.2 peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| guest:llvm-prepare | 154.01 | 147.07 | 135.51 / 3.93 | 105.9 |
| guest:prepare:0 | 60.98 | 76.07 | 21.57 / 12.32 | 73.0 |
| guest:compile-link:0 | 612.16 | 467.63 | 533.55 / 170.44 | 234.2 |
| guest:wasm-postopt:0 | 16.81 | 13.83 | 63.22 / 3.14 | 532.6 |
| translate:converter-build | 11.75 | 7.14 | 14.65 / 2.06 | 296.2 |
| translate:wasm2go | 99.88 | 74.98 | 80.29 / 17.04 | 2963.9 |
| dev:translation | 124.10 | 82.59 | 95.19 / 19.29 | 2963.9 |
| dev:source-adapter | 20.55 | 16.06 | 18.44 / 0.35 | 859.8 |
| dev:installation | 22.57 | 17.72 | 20.33 / 0.50 | 858.1 |
| dev:generated-go-compilation | 162.45 | 132.33 | 203.89 / 4.29 | 2454.8 |
| dev:sql-smoke | 3.42 | 2.28 | 1.41 / 0.77 | 525.3 |

Raw linked Wasm: 22,125,195 B / `cc7828309b715024a8a7a66237150d7aa59a450dcb5e02eed315d474618ae533`。
Postopt Wasm: 18,618,084 B / `285f2be34cdf768d3c8ed06d96e347ceb7a0b13e8bdd6a43bdfd37ebdd8cc097`。
Host binary: 101,522,738 B / `9615870ea0f1b9d9d86caf7e6f6460edb0df391e3fdde6e5236235a29918c5fa`。
12.3.3はraw 21,816,229 B / postopt 18,367,999 B。SQL性能の比較は行っていない。
Guest route全体1044.20 s、native route255.95 s。前者はdownload/extract/mount間source移動を含む。
[CSV](v05-mariadb-132-feasibility-evidence/timings.csv)とphase JSONLにactual tool/version/CPU/RSS/exitを保存。

guest containerは`mariamem-wasix-build:0.4.7`
(`sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`)、
`JOBS=3`、Docker memory cap6GiB。nativeはGo1.26.8 / GOMAXPROCS2 / `-p1`、
新規task cacheを使用。disk budget24GiB / minimum free20GiB / 各stage40分timeout
(focused acceptance5分)を適用した。

各1回。12.3.3はGitHub core archive、13.2.0は公式source distributionという違いもある。
macOS arm64 nativeとLinux arm64 builderのwait4 high-water RSSは、全process treeの同時RSS合計ではない。
nested phaseを加算しない。build wall差はSQL性能差ではない。

## Human decision points / remaining work

1. **12.3.3 LTSをv0.5.0本命に維持する**。Preview feasibilityはLTS採用を覆す理由にならない。
2. **共通portability差分を中心に、小さい適用hunk variantだけ分離する方針を採るか**。
   独立patch set全体の二重保守やmajor別ディレクトリは不要。
3. **13.0.2 Stableの追加buildは今は保留**。13系Stableを製品候補にしたい、または13.2との差分で
   採用判断に必要な具体的な未解決経路が生じたときに価値がある。今回追加buildはしていない。

正式採用時にはsource/notices/provenance、guest-bound Snapshot互換性、SQL実バージョンと
wire handshake表示の整合、両supported OS acceptance、広いthread/trap/race census、
Release独立再生成/qualificationが別途必要。12.3.3と13.2.0のSnapshot相互互換性は約束しない。

## Reproduction / cleanup

1. exact source `3ecdf2d4f27be6c983a648088d2ee6a5d0ad86bf`からclean experiment worktreeを作る。
   workspace prepareでmin-free20GiB / budget24GiBを指定する。receiptと実branch baseを確認する。
2. [guest launcher](v05-mariadb-132-feasibility-evidence/guest-command.sh)の専用mountを用意し、
   tracked `build/go.mod`をbuilder-buildへ元bytesのままコピーする。空のlinux-root/linux-workを使う。
   [stage guard](v05-mariadb-132-feasibility-evidence/run-stage.py)でguestを実行する。
   source archive/recipe/SDKはlock内のURL+hashで取得・検証される。
3. task venvにpytest9.1.1/PyMySQL1.2.3を入れ、Go1.26.8を用意し、
   [native launcher](v05-mariadb-132-feasibility-evidence/native-command.sh)でnative stageを実行する。
   Go実versionと新binaryのbuildinfo/guest hashを検証する。macOS arm64の実パスは環境に合わせる。evidenceの公開用pathは
   `/workspace/mariamem`・`/toolchains/go1.26.8`に正規化した。元receipt/log hashは元bytesのhashを保持し、
   normalized JSONをRelease receiptとして扱わない。
4. [focused acceptance](v05-mariadb-132-feasibility-evidence/acceptance-command.sh)を同じstage guardで実行する。
   別guestやcanonical hostへ環境変数を付け替えて成功扱いしない。
5. source-only patch layoutは[再現script](v05-mariadb-132-feasibility-evidence/patch-layout-reproduce.py)で、
   固定archiveのpristine root2つとfresh出力先を指定する。GNU patchを使用、guest再buildなし。
6. Release negative checkはactual guest.jsonとdevelopment.jsonを専用negative directoryの
   guest.json/regeneration.jsonへbytes変更なしでcopyし、既存generated_release.verify_buildを呼ぶ。
   `ValueError: wrong build contract`を厳密に確認する。

[guard receipts](v05-mariadb-132-feasibility-evidence/guest-guard.json)にdisk peak/min-freeを保存。
最大ownedはacceptance stageの7.54GiB、全stageの最小空きは79.56GiB。予算違反・timeoutなし。
Docker clientだけで停止しないよう、guard runnerは失敗時にも同名owned containerの終了を確認する。
ソース準備/patch適用の失敗probeはbuild前に切り分けた。実C buildもnative generationも成功は各1回、
原因のないguest rebuildは行っていない。

測定後、所有・Git状態・ignored files・scratch内Git historyを確認し、unique user changesなし。
7.17GiBのtask-owned tempを削除した。SDK/LLVM/ダウンロード、guest/build、
Wasm、converter/generated/product/native copies、Go cache、venv、probe copiesは再生成可能。
compact JSON/CSV、checksums、選択log excerpt、再現手順と実験patch/commitだけ保持する。
[cleanup receipt](v05-mariadb-132-feasibility-evidence/cleanup-temp.json)に実測bytesを保存。
残るworktreeは報告書commit/pushとdocs check後にGit-aware removalで削除する。
この時点でtask-owned >1GiB pathなし。他taskのworkspace・global Docker/Go SDKは変更していない。
