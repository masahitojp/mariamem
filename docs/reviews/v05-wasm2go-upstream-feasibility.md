# v0.5.x Track A — goccy upstream feasibility

**結論: FEASIBLE WITH ADDITIONAL PATCHES（macOS arm64）。**
固定した現行guestに対し、本家＋9パッチからnative hostを作成し、Go 51 tests／Python 27 testsが
PASSした。小fixtureだけでなくSQL、transaction、Snapshot／Fork／LoadSnapshot、concurrent
sessions、Close／cleanupを確認した。mainへの統合・Ubuntu確認・Release Qualificationは未実施。

Humanへの推奨は、本家＋管理パッチへの移行を次の採用候補として進めること。fork依存は
解消できるが、上流追従時に2つのcontext portとexport命名契約を保守する責任は残る。
**判断事項: この9パッチ構成を移行候補として採用し、両OS／Release検証へ進めるか。**

この実験は本家converter移行だけを扱う。MariaDB guest更新を扱うTrack Bと生成物・cache・
結論を共有しない。main、v0.4.6 tag、canonical inputs、Release guardは変更していない。
結果はUNQUALIFIEDであり、採用・Release Qualificationとは別の判断である。

## Fixed inputs

- main: `386a62c3669e37bb8aaad58cd0aca8da893b3d80`。
- v0.4.6 source: `b56be17206b6beef18f55c8ea39b254638da8590`。
- v0.4.6 annotated tag object: `09d7b82e1900318dde45d08bebd9328ea35e6ef7`。
- current guest: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`。
- current converter fork: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`。
- upstream source commit: `730057c146463f663e8774587bc96fb2bea91af8`。
- upstream archive SHA256: `1adc74bb1594ed1d300d9382b9da27402728939fc021024d977e9c98afd2467f`。
- 実runtime入力source: `c06e908aef1055ca718b6da0212bb578c51a1a48`。
- 実converter binary: `c5a19963e22dcbda06035b2da7252030f54c384e7a2456192dacdf87045e74df`。
- 実host binary: `13a39938b12ff67ee37729559e9ab7e2ccee35bf407f917c394b67b25dec3c65`。
- Go: 1.26.8、`-pure`、Host/Wireとruntime設定はmainと同じ。generated Goは候補converterから再生成。
- 最新forkのGo1.27 experimental SIMD、gcasm body conversion、layout optionsは採用しない。

Git identity helperでmain/releaseのtag-objectとsource-commitを区別し、本家commitも実体を
取得してcommit objectとして検証した。Fast Feedback／single-pass dev buildのmain統合は
共通preflightで確認した。詳細は最終compact evidenceに保存する。

## Smallest patch series

1. `upstream-imported-memory.patch` — metadata追加の位置を本家CLIへcontext付きでport。
2. `import-function-index.patch` — unchanged。
3. `relaxed-madd.patch` — unchanged。
4. `upstream-pure-memory32.patch` — canonical pure-memory32のhelper contextだけを本家へport。
5. `controlled-thread-traps.patch` — unchanged。
6. `host-logical-memory.patch` — unchanged。
7. `linear-memory-owner.patch` — unchanged。
8. `upstream-helper-bridge.patch` — host logical boundと既存Wait fixture能力。
9. `upstream-export-collision.patch` — forkと同じsuffixで両exportを保持。

5パッチはcanonicalとbyte一致、2つはcontext port、2つはforkから必要な能力を保持する。
[保守形式の調査](https://github.com/masahitojp/mariamem/blob/40b7f17/docs/reviews/wasm2go-diff-management.md)
で「必要なら移植」としていたexport衝突を現行guestで実証した。

本家のbulk fill/copyは既に`memSize.Load()`を使用する。forkの非shared memoryについて
backing slice全体をaddressableにする契約は取り込まない。通常load/store、atomic、SIMDは
canonicalのnon-wrapping `memoryInBounds`を維持する。host側の`accessMemory`が呼ぶ
`memBound`はmariamemでは常にguest-visible sizeを返す。shared growthを読む際にも
atomic loadを維持する。

`ForceContendedAtomics`は既存Wait/PageCleaner ordering fixtureが使用する能力を保持する。
production WASIX threadは既存`threadSpawn`のcontention publicationを使う。
新たなthread/futex/race設計ではない。

初回の小fixtureはcompileで`undefined: memBound`を検出した。helper contextのportだけ
ではhost patchの依存を満たさないことを実行で確認し、bridgeへ最小関数を追加した。
変換成功をcorrectness成功とみなさず、この失敗と修正後の検証を区別して保存する。

実guestの初回変換（`16d87ca`／8パッチ）はC++ exportの`__xEv`／`__XEv`が同名Go methodに
mangleされ、fail-closedで停止した。forkと同じ命名hunkを追加し、両exportの返り値1／2を
実generated Goで確認、2回生成のbyte一致も確認した。Wasmのrename／stripは行わない。

次のnative compile（`3f538ea`）はmemory fields欠落で失敗した。context無しのcanonical
imported-memory hunkが、本家ではTranslate後のSidecars loop内へ挿入されていたためだった。
`c06e908`はParse直後へのcontext-bound portに置換し、Translateより前であることをrunnerで
確認する。既存imported-memory fixtureをgrow／size exportで補い、constructor、guest-visible
size、shared copyへのgrowth publication、stable pointer、失敗したgrowthのstate維持をPASS。
これはWasm exported functionの実行であり、SQL検証とは区別する。全patchの静的配置監査も保存した。

## Experiment adapter

[実行script](../../benchmarks/spikes/upstream-feasibility/run.py)は既存のconverter recipe、
memory32 reference fixture、`setup_candidate.py` source adapter、`generate_runtime.py`
installer transformationsとhandwritten overlaysを再利用する。

converter sourceをfresh archiveから展開し順序付きpatchを適用する。canonicalのaccepted
manifestを変更して通す方法は使わない。既存installerの外部copyについて入力取得だけを
実験manifestへ接続し、別product copyへ出力する。実生成source inventory、Wasm、converter
binary、native hostのhashを追跡し、provenanceにUNQUALIFIEDを明記する。

testはそのproduct copy／fresh hostを明示使用する。canonical runtimeの既存成功をこの
candidateの成功として流用しない。full guest race-detector cleanとは主張しない。

## Verification / resource results

| 検証境界 | 結果 | 証拠 |
| --- | --- | --- |
| patch-owned emitter／SSA＋export命名 | PASS | 5 tests、実generated Goで異なる返り値1／2、生成byte一致 |
| memory32 reference | PASS | 2,472 rows、1,693 expected traps、golden一致 |
| 小shared memory／futex | PASS | constructor/grow、logical bound、100回通知競合、Wait/PageCleaner |
| Go base／runtime ownership | PASS | 35 top-level tests、skip 0 |
| 実guest traps／thread／SQL | PASS | 4 tests、root/worker trap、grow、private TLS/stack、CRUD/sessions/auth |
| Go public owned/lifecycle/load | PASS | 12 tests、skip 0 |
| Python explicit fresh host | PASS | 27 tests、skip 0、35.71 s |
| unchanged Release source validator | REJECT as intended | `input manifest changed`、canonical pins／validator byte一致 |

子のINSERT／UPDATE／DELETE、schema変更、8 MiB growth、commit／rollback、順序変更、
繰り返し／parallel siblings、元path削除後のimport ownership、Fork/Close race、startup／partial
failure cleanupを既存testsで確認した。Go failure pathsはFD 6→6／goroutine 2→2、閉じたhandleを
保持した試験もFD 6→6。Python owner EOFがhostをreapし、reader／pipe／logの終了もPASS。

小Wait fixtureでは登録前signalがpermitを残さず正当な約1 s timeout、登録後は約2 µsでwake。
実guestのworker visibility／TLS独立性／memory.grow／trap relayは別のconcrete guest testsで検証。
いずれもfull guest Go race-cleanを証明する試験ではない。

runtime checksはisolated product内のfresh generated sourceとexplicit hostを使用し、binary hash／
Go compiler／host `--snapshot-info`／test input hashesでbindした。検証後のruntime inventoryも
作成直後と一致した。最終report commitはdocs/evidenceのみで、runtime tested sourceは上記
`c06e908`である。初回失敗やsandbox DNS不足によるtest-setup未実行も別receiptへ残した。

## Resource observations

Apple M1、16 GiB RAM、8 CPU、macOS 27.0.1 arm64、GOMAXPROCS=2、専用Go cache。
計測は1回のfeasibility試行で、benchmark比較／高速化率ではない。

| 最終成功工程 | Wall | User / System CPU | Peak RSS |
| --- | ---: | ---: | ---: |
| Wasm→Go | 69.19 s | 77.44 / 10.66 s | 3.94 GB |
| Generated Go→native host | 125.44 s | 193.29 / 4.00 s | 2.50 GB |
| Go base/runtime tests（初回test archive compile込み） | 179.03 s | 259.36 / 7.76 s | 3.45 GB |
| concrete guest tests | 9.44 s | 6.10 / 1.85 s | 0.65 GB |
| Go public lifecycle tests | 18.89 s | 14.55 / 5.25 s | 1.06 GB |

native hostは101,050,242 bytes。Peakはwait4 child high-water markであり、全processの同時RSS合計
ではない。native buildの`-trimpath`と通常Go testの別cache archive生成費を含む。thread fixtureは
軽量先行、guest変換／native compileはTrack B終了後に実行し、競合を避けた。
SSA fixpoint cap warnings、未検証f16 table rewriteがOFFのwarningを保存し、新たな対応成功と
主張しない。本家＋patchはfork削減の保守候補であり、runtime速度改善は測定していない。

## Remaining boundary / recommendation

本家だけでは現行guestを変換できず、export命名追加とimported-memory context portが必要。
既存7パッチの安全目的を保持した9パッチなら、固定guestでcorrectness実証が成立した。
大きなfork全体を保持するより差分の責任を説明しやすいが、patch本数の減少ではない。
upstream source変更時にはcontext port、helper互換性、wrapper命名、同じfixturesの再実行が必要。

Ubuntu x86_64、独立再生成、source/license/provenanceの正式更新、最終artifact qualificationは
移行採用後の別gate。今回はcanonical accepted pins／guest／main／tagを変更せず、unchanged
Release validatorで実験manifestが拒否されることを確認した。Track Bとの組合せは未検証。

既存のbulk zero-length bounds仕様gap、非協調的trap reclaim／full guest Go race既知制約は
今回の移行で解決したとみなさない。macOS arm64実験はUbuntu qualificationの代用ではない。

## Reproduction

独立owned workspace、専用Go cache、Go1.26.8、Python pytest/pymysqlを用意する。
公式WABT1.0.42 macOS arm64を追加WAT fixture用に使う場合、archive hashは
`3f654779b436c628db3ca4323c51538815f5fbc887a6d5f3bb1c18d36281e240`。
既存memory32 fixture生成はWABT不要である。

```sh
env -u GOPATH -u GOCACHE -u GOMODCACHE \
  MARIAMEM_DEV_WORKSPACE=/absolute/owned-workspace \
  MARIAMEM_PHASE_TRACE=/absolute/owned-workspace/evidence/phases.jsonl \
  GOMAXPROCS=2 /absolute/owned-workspace/temp/venv/bin/python \
  benchmarks/spikes/upstream-feasibility/run.py \
  --archive /absolute/owned-workspace/temp/upstream.tar.gz \
  --guest /absolute/owned-workspace/temp/released-guest/mariamem.wasm \
  --output /absolute/owned-workspace/temp/upstream-run3
```

source checkoutをcommitしてから実行する。Release資格を得る経路ではなく、sourceやartifact
identityを偽装してrelease helperへ渡してはならない。


## Evidence / cleanup

[compact evidence](v05-wasm2go-upstream-feasibility-evidence/)にfixed identity、patch manifest、
失敗境界、resource phases、test logs／test input hashes、再現用小fixture commandsを保存した。
raw source／Wasm／Go caches／binary／product copyは再生成可能であり保持対象ではない。
workspace coordinatorがcommit/push後に所有済みtempとworktreeを削除する。
このreport branchへmulti-GiB生成物を含めていない。最終cleanup receiptはcoordinatorが報告する。
