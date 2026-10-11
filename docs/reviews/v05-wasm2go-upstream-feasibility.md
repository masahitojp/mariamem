# v0.5.x Track A — goccy upstream feasibility

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
- Go: 1.26.8、`-pure`、runtime/host/wireはmainと同じ。
- 最新forkのGo1.27 experimental SIMD、gcasm body conversion、layout optionsは採用しない。

Git identity helperでmain/releaseのtag-objectとsource-commitを区別し、本家commitも実体を
取得してcommit objectとして検証した。Fast Feedback／single-pass dev buildのmain統合は
共通preflightで確認した。詳細は最終compact evidenceに保存する。

## Smallest patch series

1. `imported-memory.patch` — unchanged。
2. `import-function-index.patch` — unchanged。
3. `relaxed-madd.patch` — unchanged。
4. `upstream-pure-memory32.patch` — canonical pure-memory32のhelper contextだけを本家へport。
5. `controlled-thread-traps.patch` — unchanged。
6. `host-logical-memory.patch` — unchanged。
7. `linear-memory-owner.patch` — unchanged。
8. `upstream-helper-bridge.patch` — host logical boundと既存Wait fixture能力。

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

検証継続中。実guestの変換／native compileはTrack Bの重い工程と競合しないよう順番待ち。
先行した小fixtureの結果は次のとおり。これをMariaDB全体の検証成功として扱わない。

| 検証 | 結果 | 実測境界 |
| --- | --- | --- |
| patch-owned emitter／SSA regressions | PASS | 4 tests、2.082 s |
| memory32 reference | PASS | 2,472 rows（1,693 expected traps）、golden一致 |
| bounds／grow | PASS | scalar／atomic／SIMD、非wrap offset、failed growth、zero fill |
| Wait／PageCleaner ordering | PASS | 2 tests、2 subcases、100回compare-registration通知競合 |

Wait fixtureは同じpatched upstream binaryで既存`threads.wat`を変換し、canonical fixtureの
private field/function名だけを適合した。登録後の通知は2.3 µs、登録前の通知にはpermitが
残らず正当な1.002 s timeoutになった。notifyの0／1 count、2 waiterも確認した。
これは小moduleにおけるfutex publicationの実測であり、実MariaDB WASIX threadについては
この時点ではstatic reasoningのみ。実guestのSQL／Snapshot／Fork／LoadSnapshot／
concurrent sessions／Close／cleanupは最終結果で別々に記録する。

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
  --output /absolute/owned-workspace/temp/upstream-run
```

source checkoutをcommitしてから実行する。Release資格を得る経路ではなく、sourceやartifact
identityを偽装してrelease helperへ渡してはならない。
