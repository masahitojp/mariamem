# Direct-linked mariamem: ordinary Go consumer experience

## Scope / source / environment

2026-10-03、`v0.4/generated-go-integration`、source
`c751746c42ac50045ee1ff7a60491b0344d3231c`。
MacBook Air M1、16 GiB RAM、macOS 27.0、darwin/arm64、16 KiB pages。
CGO disabled、Go default parallelism。`-p 1`、compiler workaround、generator変更、
MariaDB build変更は使用していない。測定は順次実行し、別のcompiler buildを重ねていない。
少数の独立clean-cache測定であり、時間のpercentileやCI全機種の保証は目的にしない。

目的は **generated sourceを普通のGo依存として利用する実際の負担**。
one/sequential/concurrent DBの正常動作は前のdirect-link実験で確認済み。
今回のexternal consumerでもStart、SQL、Closeを確認した。
非協調/hung executionの強制回収とfailure containmentは別のarchitecture decisionとして残る。
production runtime/public API/配布物を変更していない。配布方式の選択は保留する。

機械可読結果:
[`results/direct-link-consumer-experience.json`](results/direct-link-consumer-experience.json)。
再現手順・隔離したfixture:
[`spikes/distribution/README.md`](spikes/distribution/README.md)。

## External consumer

OS temporary directoryの独立project、module名
`example.com/mariamem-direct-consumer`。consumerは以下だけを利用する:

```go
db, err := mariamem.Start(context.Background(), mariamem.Options{})
// database/sql + go-sql-driver/mysql, db.DSN()
// SELECT 1; CREATE InnoDB TABLE; INSERT; UPDATE; SELECT; DELETE
// connection close; db.Close()
```

`go.mod`は通常の`require`、**`replace`なし**、`GOWORK=off`。
まだ公開direct-link版がないため、private file GOPROXYから
`github.com/masahitojp/mariamem@v0.4.0-direct-consumer-probe`を取得した。
これはローカルfixture versionでありtag/releaseを作っていない。
Goはmodule zipをcacheに展開し、consumerはcheckoutを直接importしない。
unpublished fixtureに限り`GOSUMDB=off`、module content hashは
`h1:wYLBdcTmkbO71ugLq7keaXUo6f2ngoKZf2UrLKEBp1s=`。

fixture-only execution adapterは3ファイルに限定:
`internal/generatedgo/consumer_fixture.go`、`internal/guest/guest.go`、
`internal/builtinruntime/runtime.go`。canonical generated functions/data/assemblyと
public host/API/MySQL wireは同じsourceを使用する。コピーした98 inputのうち、
予定したadapter以外のchecksum変更は0。
各Startはfresh Module/WASI/Threads/FD/MemFS、OS pipeによる既存guest protocolを利用。
native executableのdecode/materialize/execは行わない。
正常Closeを確認する小さなadapterであり、forced cancellation/異常worker回収、
optional feature全体をproductionizeしたものではない。

canonical generated provenance SHA-256:
`99092e99f196253f7b0f0c18a5ef9b90734a670e8ae1676161c38953fed9af7e`。
guest SHA-256:
`5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`。
全Go versionで同じfixture zipを使用した。

## Acquisition / cache size

| Item | Bytes | MiB |
|---|---:|---:|
| canonical generated source/shims in fixture | 205,683,700 | 196.16 |
| buildable fixture source + licenses/locks | 211,789,207 | 201.98 |
| module zip | 29,926,089 | 28.54 |
| mariamem extracted source + download-cache records | 241,715,592 | 230.52 |
| module cache including MySQL/edwards25519 dependencies | 242,517,884 | 231.28 |
| Go 1.26.8 build cache after build/test/link variants | 557,548,180 | 531.72 |

local file proxy → fresh module cache: **1.337 s wall / 1.210 CPU-sec**。
これはnetwork download速度の測定ではない。ネットワークで転送するfixture zipは28.54 MiB。
zip SHA-256:
`daf666e56fea80311ad2f2394423a330bc125d8cb52f724b3cd54931d4fb6f8b`。
module取得とbuild cacheを分離し、build測定前に依存は取得済み。

fixture zipはbuildable source/licenses/locksに限定し、embedded platform images、
repository docs/diagnostics、dependency testsを含めていない。
現在のpublic module全体のdownload sizeを測った値ではない。
現HEADのtracked約326 MiBには約112 MiBのencoded executableも含まれる
（[前の内訳](direct-link-architecture-investigation.md#6-326-mibの内訳)）。
今回のfixture packagingはdirect source依存の測定境界であり、production moduleを
分割/削減したり、最終release layoutを決めたりしていない。

## Cold / warm / incremental build

空の`GOCACHE`を独立に用意し、通常の`go build` / `go test ./...`を実行した。
Go build cacheのcoldを意味し、OS page cacheはflushしていない。
`/usr/bin/time -l`のmaximum RSSはbytesで収集。
**同時に存在する全compilerのRSS合計/機械全体のpeakではない**。
以下のRAMはそのreported maximum。CPUは子プロセスを含むCPU時間。

| Boundary | Go 1.26.8 wall | CPU | Reported max RSS |
|---|---:|---:|---:|
| independent cold `go build` | 109.34 s | 302.62 s | 2.37 GiB |
| first `go test` after that build | 46.52 s | 96.60 s | 2.53 GiB |
| independent empty-cache CI `go test` | 128.97 s | 425.23 s | 2.47 GiB |
| `go build` after CI test | 2.63 s | 2.36 s | 0.70 GiB |
| warm `go build`, immediate repeats | 0.19–0.42 s | 0.40–0.44 s | 32–35 MiB |
| warm `go test` | 0.24–0.30 s | 0.53–0.62 s | 35–38 MiB |
| warm `go test -count=1` | 1.33–2.46 s | 1.29–1.32 s | 0.53–0.56 GiB |
| consumer-only edit `go build` | 1.43 s | 2.28 s | 0.70 GiB |
| consumer-only edit `go test` | 1.61 s | 1.31 s | 0.55 GiB |

CI trialのconsumer-only editは`smoke`が参照するmarker文字列を変更し、
test結果がcachedでないことを確認した。初回trialの未参照marker編集ではtest結果がcached
だったため、incremental testの根拠にはCI trialを使う。
warm forced testはSQLを実行する。上の範囲には観測されたwall時間をすべて含める。
test bodyのSQL/Closeとtest executable起動も含むため、compilerだけの時間ではない。

first testの追加46.5 sはtesting/vet/link用cacheの初回準備も含む。
各工程の精密配賦は今回実施していない。
空cacheからtestを最初に実行した129 sは、cold build + first-test時間を
単純に足した予測とは異なる独立測定。

同じconsumerのGo 1.26.0による独立cold buildは**92.60 s / 278.70 CPU-sec**、
reported max RSS **2.58 GiB**。first test after buildは45.53 s、最大2.76 GiB。
これらと1.26.8の結果から、初回は概ね1.5–2分のcompile、fresh CIのtestは約2分、
compiler/test setupが2.4–2.8 GiB級のプロセスを必要とすることが分かる。
通常の編集で毎回この費用を払う動作は観測していない。
RAMの少ないCIでOOMする境界やLinuxの性能は測っていないので、最小RAM保証はできない。

## Final binary

Go 1.26.8、通常linkと一般的な`-ldflags='-s -w'`を比較。
baselineは同じ`database/sql`/MySQL driver、SQL/CRUD、JSON/time/error処理を持ち、
mariamemのimport/Start/Closeのみを除いたcompile-only program。
baselineに外部DBを用意して実行する必要はない。

| Binary | Default | `-s -w` |
|---|---:|---:|
| MySQL driver baseline | 7.18 MiB | 4.87 MiB |
| mariamem direct-linked consumer | 81.25 MiB | 54.47 MiB |
| approximate mariamem contribution | **74.07 MiB** | **49.60 MiB** |

test binaryは81.86 MiB。196 MiBのGo sourceがそのままexecutableに残る形ではない。
ただし約50 MiBのstripped追加分は、配布binaryやtest binaryに対する実際のコスト。
debug/symbol strippingとの差約27 MiBを確認した範囲で、細かなsize最適化は行っていない。

## Compiler compatibility and upstream fix

`go.mod`のminimumは1.26.0、従来のacceptanceは1.26.8。
`GOTOOLCHAIN=local`は各versionを確実に検証するために使い、compiler回避設定は加えていない。

| Compiler, darwin/arm64 | Real consumer build | SQL / CRUD / Close | Cold build / RSS |
|---|---|---|---|
| Go 1.26.0 | PASS | PASS | 92.60 s / 2.58 GiB |
| Go 1.26.8 | PASS | PASS | 109.34 s / 2.37 GiB |
| Go 1.27.1 | FAIL in generated `p6` | buildで停止 | 86.78 s / 2.15 GiB |
| upstream master `ff48d740`, Go 1.28 devel | PASS | PASS | 88.36 s / 2.04 GiB |

1.27.1は`Fn8139`/`Fn8150`付近の`LDPSW 23997552(R4)`等で
`constant is not in pool`。OOM/compiler crashではなくarm64 assembler diagnostic。
1.27のcross-block load pairingが、生成コード中の16 MiBを超えるoffsetを持つ
signed-int32読み出しをpair instructionにして、literal-pool不足を露呈する。
小さなreproducerでも同じ差が出た:

```go
//go:noinline
func Pair(p unsafe.Pointer) int32 {
    a := *(*int32)(unsafe.Add(p, 23997552))
    if a == 0 { return *(*int32)(unsafe.Add(p, 23997556)) }
    return a
}
```

1.26.8は別々の`MOVW`を生成してPASS、1.27.1は`LDPSW`にしてFAIL。
upstream masterは`LDPSW` + `WORD $23997552`のpool entryを生成してPASS。
packageサイズが小さくても再現するため、**196 MiBのpackageの大きさが原因という説明は不正確**。
大offsetのpaired loadを扱うGo backendのgapであり、生成コードのメモリアクセス形状が
それを露呈している。

関連upstream [issue #81036](https://github.com/golang/go/issues/81036)、
[修正CL 819901](https://go-review.googlesource.com/c/go/+/819901)。
Gerrit APIでmerge済み完全SHA
`b3f5034b15a7a6f065e92d0617f7a473d5d9dcfa`と、LDPSWを含むpair opcode認識の修正を確認。
固定master SHA **`ff48d740d5e6dcf01cb1023b382a858a493c5f69`**はこのfixの子孫
（compare: ahead 422、behind 0）。source archive SHA-256:
`ee9847b992729a6500fdd54703aa4a041c51028516df23ff064e1acfdf01a207`。

Go 1.26.8でmaster SDKをbootstrapし、archiveのVERSION metadataを
`go1.28-devel_ff48d740`に固定した。compiler sourceへのlocal patchは0。
同じmodule zipについて最小reproducerだけでなく、実際のconsumerのbuild、
通常/強制再実行のtest、consumer編集後testもすべてPASS。
masterのfirst testは45.49 s、warm build 0.23–0.42 s、warm test 0.30 s、
編集後build/test 1.20 / 1.47 s。極端なmemory増加も観測していない。

これはupstreamで原因が解消する強い実証。
**通常release済み1.27.1での失敗は残る**。Go masterをconsumerに要求する形は
release acceptanceの代替にしない。修正入りrelease/backport toolchainの再検証が必要。
1.26系では正常に利用できるが、現在の1.27系consumerにはversion制約が生じる。
Linux x86_64のconsumer/version matrixはこのlocal調査で実行していない。

## pgmem reality check

実際の公開module **`github.com/shibukawa/pgmem@v1.18.1`**、source
`ed2c23f79a93feb267070784576dd2eedb6cdef2`。
同じM1/Go1.26.8/CGO0/default parallelism、独立external project/cache、
通常`Start` → loopback TCP → `database/sql` + pgx → 同等SQL/CRUD → `Close`。
default optionsを使いbuffer設定を変更しない。custom in-process dialerを使わない。
実際のpublic moduleをchecksum database付きで取得し、`replace`なし。

| Metric | mariamem direct fixture | pgmem public module |
|---|---:|---:|
| module source/extracted tree | 201.98 MiB | 116.91 MiB |
| module zip | 28.54 MiB | 24.40 MiB |
| cold build | 109.34 s | 67.43 s |
| cold build CPU | 302.62 s | 182.48 s |
| cold build reported max RSS | 2.37 GiB | 2.05 GiB |
| first test after build | 46.52 s | 25.58 s |
| warm build | 0.19–0.42 s | 0.21–0.61 s |
| warm test | 0.24–0.30 s | 0.28 s |
| consumer edit build / test | 1.43 / 1.61 s | 1.11 / 1.40 s |
| default / stripped binary | 81.25 / 54.47 MiB | 62.07 / 40.54 MiB |
| build cache after campaign | 531.72 MiB | 410.32 MiB |

pgmem module取得は実networkで5.66 s、1.57 CPU-sec。mariamemのlocal-proxy時間と
速度比較しない。pgmemのmodule自身のcache約141.31 MiB、全dependency cache345.49 MiB。
pgmem側のSQL smokeはPASS。fresh-cache CI testの追加比較やGo version matrixは
pgmemでは行っていない。

mariamemの初回compileはこのtrialで約1.6倍、stripped consumer binaryは約1.34倍。
両者とも初回は大きなAOT sourceをcompileし、warm/incrementalは約秒以下〜数秒という
**同じ大分類**。database実装/driver/module内容は異なるため細かな優劣は結論にしない。

## Interpretation / remaining gates

- **Source size:** 196 MiBはrepository上では大きいが、今回のcompressed転送量は28.54 MiB。
  その数字だけで普通のGo依存として不適切とは判断しない。
- **First build / CI:** 実コストは約1.5–2分、数GiB級のcompiler/test setup、
  build cache約532 MiB。極小CIや多数のcacheなしjobでは無視できない。
  このM1/16 GiBでは正常終了し、pgmemと質的に異なるresource要求は示していない。
- **Normal development:** 通常の`go test`が毎回生成コードcompileを払う動作ではない。
  warm build/testは約0.2–0.4秒、consumer編集は約1.4–1.6秒。
- **Binary:** stripped追加約49.6 MiBは現実の配布コスト。source196 MiBがbinary196 MiBになる
  状況ではない。
- **Toolchain:** 最も具体的な現時点の障害はGo1.27.1/arm64のcompiler gap。
  upstream fix入りmasterでreal consumerまで成功し、generator変更が不要な修正経路を実証。
  通常releaseされた修正toolchainでの再確認が残る。

普通のGo配布モデルとして検討を進めるための未完了項目:

1. Go1.27/arm64でupstream修正を含むrelease/backportのreal consumer acceptance。
   未修正compilerを無条件にサポートできるとは記載しない。
2. Ubuntu x86_64でもpublic-consumer/version/cache境界を確認し、支持するGo versionsと
   CI memory budgetを明記する。macOSの2.8 GiB値を全環境の上限とはしない。
3. 正式なdirect-link adapterと全public behaviorの受入れは別のproduct integration work。
   failure containment/非協調実行の回収は別のarchitecture decision。
   本taskではproductionizeも配布architecture選択も行わない。

検証: external-consumer smoke tests（1.26.0/1.26.8/master）、pgmem smoke、
compile-only reduced reproduction、canonical generated source/guest/image provenance verifier、
隔離したPython harnessの構文確認、`git diff --check`。
production sourceに変更がないため、SQLAlchemy/GORMや全production regressionの
再実行は今回のbuild/distribution調査に追加していない。

source/distribution costはdirect-linkを断念する実証的理由になっていない。
現時点のdefault consumerが通常のGo1.27.1でbuildできない点をrelease gateとして扱う。
この一時的なtoolchain blockerを、in-process MariaDBが本質的に不可能という判断にしない。

## Verdict

**`DIRECT-LINK TOOLCHAIN BLOCKED`**

対象は現在release済みの通常toolchainを含む無指定consumer体験。
Go1.26では実用的なcache挙動を確認し、修正入りmasterでもreal consumer/SQLは成功した。
残るblockerはreleased Go1.27.1/arm64互換性。cold-build/CI/binaryの測定コストは
明示すべき懸念だが、196 MiB source自体を不採用の根拠にはしない。
