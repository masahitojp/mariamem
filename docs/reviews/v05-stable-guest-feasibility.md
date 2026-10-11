# MariaDB stable guest feasibility — Track B

結論: **FEASIBLE WITH PATCHES**。MariaDB **12.3.3 LTS** は現行converterを
固定したまま、単発Wasm build → Go変換 → native host → 実SQL / transaction /
Snapshot / Fork / LoadSnapshotまで成立した。正式採用・release適格性の判断は別である。
Track Aのconverterや生成物は使っていない。全成果物は **UNQUALIFIED**。

## Human Review

- 推奨: 12.3.3をv0.5.0正式候補として進める。移植は18-file portability patchと
  既存lite4 recipe/API 6ファイルに限定でき、host例外は承認済みhandshake version 1行のみ。
- 最も強い証拠: 実際の `SELECT VERSION()` が `12.3.3-MariaDB-embedded`。
  Fresh/commit/rollback、persist/load/source削除、新baseline、sibling isolation/
  growth/並列/35世代/Closeと失敗cleanupの既存focused checksが通った。
- 最も強い反対材料: WASIX移植は機械的なsource差し替えではない。12.3のvirtual-memory
  契約への適応とpage protection制約があり、両OSの正式runtime qualificationは未実施。
- 具体的な残リスク: InnoDBの未通過経路、decommit/recommitとメモリaccounting、
  thread/futex/atomicの広い組合せ、旧guest基準のpersisted baseline互換性。
- Human判断: **MariaDB12.3.3を、必要なproduction化と正式qualificationへ進める候補にしますか？**

## 固定入力と同一性

| Input | Identity |
| --- | --- |
| actual main base | `386a62c3669e37bb8aaad58cd0aca8da893b3d80` |
| v0.4.6 source commit | `b56be17206b6beef18f55c8ea39b254638da8590` |
| v0.4.6 tag object | `09d7b82e1900318dde45d08bebd9328ea35e6ef7` |
| experimental guest/native source | `334fb2670e3f86f1a5c8be5dbe770330f3ccddcc` |
| stable source commit | `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` |
| stable tag object | `bd852bcd567fedc89ad4521e2f1a64c7a1e0d0f0` (`mariadb-12.3.3`) |
| stable source archive SHA256 | `36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845` |
| lite4 recipe source | `24be9371a2f6c71250a2356631ad6feab2280b02` |
| original lite4 portability base | `b2a8c2234dbc276fe3947633c9ffea454badf48f` |
| converter | `ac98bcf00c17d8531f0c071a9836d0b50975e7ff` + unchanged 7 mariamem patches |
| Go | `go1.26.8` |
| WASIX tools | wasixcc0.4.7 / LLVM23.1.0 / sysroot2026-07-03.1 / Binaryen133 |
| experimental.patch SHA256 | `ab093eda151087978d850f094abe69db990e6bc24fe4eff323e00f28b8a11b88` |

Workspace receiptのbase_shaはprepare呼出元の資料branch `40b7f17`を記録している。
実際の実験branchの祖先は上表のmain386a62c。receiptの読み替えや改変はしていない。
固定入力、Git commit/tag distinction、canonical hashは
[shared-preflight](v05-stable-guest-feasibility-evidence/shared-preflight.json)と
[stable-input-preflight](v05-stable-guest-feasibility-evidence/stable-input-preflight.json)を参照。

## 候補選定

[MariaDB official release notes](https://mariadb.com/docs/release-notes/community-server/12.3/12.3.3)
は12.3.3を **Stable GA、2026-08-24** としている。12.3LTSは2029年6月までmaintenance。
[Foundation release list](https://mariadb.org/mariadb/all-releases/)の13.0.2はStable rolling、
13.1.1はRC、13.2.0はPreview。最初の1候補は安定版の継続保守に適した12.3LTSを選んだ。
13系の試行や追加guest patch探索は行っていない。

## Source construction / patchの責任

official stable coreを使い、checksum-boundなlite4 recipe/API 6ファイルのみをコピーする。
`guest/stable-input.json` にsource/tag/recipeと各ファイルhashを記録した。
`release/inputs.lock.json` は実験用stable archive入力だけを追加し、accepted guest/
translation/build manifestを変更していない。`scripts/prepare_guest.py` の実験descriptor経路は
stable sourceにexperimental portability patchを適用してから既存canonical source.patchを適用する。
通常のdescriptor無し経路の順序は変えていない。

| Patch scope | Origin / adaptation | Verified boundary |
| --- | --- | --- |
| CMake / WASIX platform / PCRE / CRC / no fork-dlopen / UTC / locks / paths / directory fsync | lite4 forkの18-file C/CMake portability差分。JS/npm/website/CI差分は除外 | 新portは全hunk fuzz0。実guest buildとSQL/ownedfocused PASS |
| NULL `my_virtual_mem_commit` | 12.3はNULL allocationを許す。4096-byte aligned allocationとzero-fillで旧契約を保つ。nonnullは既存lite4同様のaccounting | NULL経路専用計測は未実施。一般InnoDB startup/growth/isolationはPASS |
| `my_virtual_mem_protect` | 12.3に存在、現lite4の新coreでは削除。WASIXではmprotect不可のためno-op | guest内page protection診断は提供しない。Wasm bounds/trapsの保証とは別 |
| decommit / recommit / release | lite4同様、decommitはaccountingのみ、releaseはfree。nonnull recommitをzero-fillしない | 物理page返却や全recommit時zero化を保証しない。広いmemory-pressure検証は未実施 |
| PMEM mprotect | 12.3の異なる位置へlite4 guardを適応 | `WITH_INNODB_PMEM=OFF`。この未実行経路は成功扱いしない |
| canonical `guest/source.patch` | wrapper/startup/init/auth instrumentationを変更なしで再利用 | WASM Cの既存hunk#2はGNU patch fuzz2。全patch fuzz0とは主張しない |

canonical patch適用後の `wasm/lite4mariadb.c` はSHA256
`d2b1a3c65b1f6a0b46de37221507b80150626c58eaa61d6033038ace46c40df9`。
既存current-guest validationの同ファイルと一致する。
[prepared-source](v05-stable-guest-feasibility-evidence/prepared-source.json)に実際の変更ファイルを保存。
新portの必要性はWASIX filesystem/virtual-memory制約への対応であり、native MariaDBの
physical durabilityやmemory protectionと同等とは主張しない。

## 実行結果 / 失敗境界

| Gate | Result / evidence |
| --- | --- |
| single-pass guest Wasm | PASS、実C/Wasm build 1回 |
| raw linked Wasm | 21,816,229B、`3b63079109c895f3e90895f86b57e48d9f8e14f13ce945021c88e20c4f4fd9ba` |
| postopt Wasm | 18,367,999B、`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c` |
| existing converter/adapter/runtime installation/native compilation | PASS、新生成物からのhost。旧generated runtimeを使用せず |
| unchanged-host smoke | 2tests PASS (3.10s)、SQL12.3.3 / handshake13.1.0 |
| separate handshake-only overlay | fresh copyの唯一のsource差分wire.go 1行、warmbuild PASS。SQLとhandshake12.3.3をassert |
| dev + wire + owned focused | 26PASS / 1FAIL (43.79s)。唯一のFAILは歴史的fixtureのSQL13.1.0固定期待値 |
| exact-version wire followup | test-only adapterが実SQL12.3.3を厳密assert。wire7tests PASS (2.23s) |
| dev identity/failure unit gates | 21tests PASS (0.67s) |
| actual dev receipts into existing release guard | `wrong build contract`で拒否。hash/repetition段階より前でfail-closed |

Owned18testsはINSERT/UPDATE/DELETE/schema/growth/commit/rollback、35childrenを含む
世代・順序・並列検証、import corruption/missing/extra/truncation/guest/format/symlink、
source削除、Fork/Close FD handoff、startup/partial-import失敗とresource cleanup、
modified childからnewbaselineを検証する。SQLのerror/recovery、metadata/types、session等はwire suite。
新guestの広いthread/atomic/futex、race/trap fixtures、Go consumer全シナリオ、native両OSqualification
は未実施。既知race detector課題の解消を主張しない。

converterはSSA fixpoint cap warningsと未証明f16 table rewrite OFFを出した。
変換は成功したが、これだけで全Wasm semanticsの証明にはならない。
unchanged-host receiptはsource334fb26に結び付いたまま保管する。
handshake overlayのsource/binary/fixture hashは別
[overlay result](v05-stable-guest-feasibility-evidence/handshake-overlay-result.json)に記録。
元receiptを新版hostへ読み替えていない。

launcherのrelative path、workspace helperのfailed-state、mount時のtracked build/go.mod不足という
guest開始前preflightエラーを解消し、既存DiskGuardによるmanual supervised routeを使った。
C buildを原因なく繰り返していない。guest/nativeそれぞれbudget24GiB/min-free20GiB/timeoutを適用。
Workspace failed receiptは変更せず、親がknowledge preservation後にmanual finalize/cleanupする。

## 時間 / リソース

環境: macOS arm64 native、Apple M1 / 16GiB / 8CPU (sysctl実測)、
Linux aarch64 Docker VM8CPU / 7.75GiB、guest `JOBS=3`、Go `GOMAXPROCS=2`、build `-p1`。
各工程1試行。task専用SDK/source/cacheを使用。cacheは他Trackと共有しない。

| Phase | Wall s |
| --- | ---: |
| LLVM prepare | 154.01 |
| Source prepare | 60.98 |
| Guest compile/link | 612.16 |
| Binaryen postopt | 16.81 |
| Translation total | 124.10 |
| of which converter build / wasm2go | 11.75 / 99.88 |
| Source adapter / installation | 20.55 / 22.57 |
| Generated Go compilation | 162.45 |
| Initial SQL smoke | 3.42 |
| Handshake-only warm host build | 3.92 |

[Timings CSV](v05-stable-guest-feasibility-evidence/timings.csv)にCPU user/system、Peak RSS、exitを保存。
RSSはwait4子rusageのhigh-water mark。全treeの同時RSS合計ではなく、Linux/containerと
macOS/nativeのscopeが異なる。nested translation wallは加算しない。
Guest compile/link user723.38s/system233.86s、rusage Peak RSS264,781,824B。
既存currentguest validationはcompile/link436.09s、postopt12.13s、translation67.98s、
native126.58s
([existing validation](v05-dev-guest-build-validation.md))。異なるguest/環境/SDK準備/cacheの1試行なので改善率や退行率は算出しない。
新guestの単発buildは正式release独立2buildの置換ではない。

## 再現 / trust boundaries

固定source334fb26でguest routeを実行し、同入力のcommitted copyからnative routeを実行する。
[guest command](v05-stable-guest-feasibility-evidence/guest-command.sh) /
[native command](v05-stable-guest-feasibility-evidence/native-command.sh)は専用workspaceの実行例。
tracked `build/go.mod`をbind-mounted builder directoryへ元bytesのまま配置する必要がある。
`MARIAMEM_PHASE_TRACE`はopt-in。cache/task outputは破棄して再現できる。

host source変更後は元dev receiptのsource-origin guardを緩めない。
[overlay command](v05-stable-guest-feasibility-evidence/overlay-command.py)は元productをfreshcopyし、
exact wire source差分を確認して独立buildする経路。
[wire followup](v05-stable-guest-feasibility-evidence/wire-followup-command.py)はfixture修正に依存する
wire suiteのみを再実行し、追加generated Go buildは行わない。

release rejectionの再現は専用negative directoryに、actual guest.jsonをguest.json、
actual development.jsonをregeneration.jsonとしてbytes変更なしで置き、次を呼ぶ:

```python
from generated_release import verify_build
verify_build(root, "334fb2670e3f86f1a5c8be5dbe770330f3ccddcc", negative_directory)
# ValueError: wrong build contract
```

この確認はcontract-stage rejectionでありaccepted hashや2build checksを通ったという意味ではない。
UNQUALIFIED markers、experimental patch、new guest hashはaccepted production pinsと一致しない。
canonical `guest/source.patch`、accepted hashes/receipt、生成runtime、main/v0.4.6tagは変更していない。
[Protection check](v05-stable-guest-feasibility-evidence/main-protection-check.json)はbaseline保護の確認であり
実験commitをruntime-qualifiedとする証拠ではない。

## 正式採用前の作業 / cleanup

1. 12.3.3 source/recipe/portability差分をproduction用最小形に整理し、source/license/provenanceをレビュー。
2. 1-line handshake versionとSQLactual版を整合させ、guest-bound metadataを更新する。
3. 新guestの両OScorrectness / traps / threading / installed Go-Python consumer / 独立再生成性をqualification。
   現guestのqualification証拠は新guestへ再利用不可。
4. 旧13.1準備済みbaselineはguest mismatchで拒否する契約を維持し、新guestで再生成する。
5. Track Aとの組合せは両方のHuman Review後に別候補として判断する。

報告書・small JSON/CSV・failure excerpt・再現コマンドのみ保存する。
C sources / SDK / generated products / native binaries / Go caches / Python venvはtask-ownedで再作成可能。
完了後のworkspace cleanupは親によるfinalization結果を参照。large artifactのKEEP理由はない。
