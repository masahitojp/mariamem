# v0.4 wasm2go feasibility spike

2026-10-01、固定ローカル M1 / 16 GiB / macOS 27.0 arm64、Go 1.26.8。
ベース: `e3224817ccfe28add8e386f7d56d425898bf644a`、ブランチ: `v0.4/wasm2go-spike`。
製品コード、guest、runtime 設定、public API、Snapshot/Fork、cache、検証・trust は変更していない。
実験は [spikes/wasm2go](spikes/wasm2go/README.md) と ignored build/results に隔離した。

**無改変の現行 guest は変換段階で停止し、生成 Go での MariaDB-ready / SQL は未達。**
一方、共有メモリ、WASI thread-spawn、thread ごとの globals、atomic wait/notify、memory.grow、MemFS の最小実験は動いた。
この結果から「Wasmer を除けば即動く」とも「pthread のため原理的に不可能」とも判断できない。

## 1. 対象の同一性と比較基準

公開 `.wasmu` は Wasmer AOT で、wasm2go の入力形式ではない。
[公開 v0.3.0](https://github.com/masahitojp/mariamem/releases/tag/v0.3.0) の sidecar が指定する元 WASM を
[release run 36685140023](https://github.com/masahitojp/mariamem/actions/runs/36685140023) の
`release-guest-wasm-400b7f564277b0627c3f0400c3e07e18fa0598d8` から取得した。
sidecar、CI provenance、WASM 実ファイルの SHA256 が一致する。手元の古い build guest は使用していない。

| 対象 | 固定値 |
|---|---|
| guest source | `400b7f564277b0627c3f0400c3e07e18fa0598d8` |
| unchanged WASM | 18,802,825 bytes; `d49402efec834414527537f639c9a11e5709bf8642357d34d33c7cfa471322d3` |
| released macOS AOT | `f8b46a3f6f47dde36f90f518c4edee180713027b1311a178adb0aa46fa5a7c72` |
| wasm2go | `shibukawa/wasm2go-fork@ac98bcf00c17d8531f0c071a9836d0b50975e7ff`, v0.5.15-fork.7 |
| converter binary SHA256 | `3192dc8455d17c2f9c6a8671359c01267680707f30c304b1de4c8e4182369741` |
| inspection | wasm-tools 1.259.0; actual guest validates successfully |

変換器は [pgmem の lock](https://github.com/shibukawa/pgmem/blob/b3ce3c3da194928e8b8b1d9f0f244c33fc179857/wasm/wasm2go.lock)
と同じ固定コミットを取得して再ビルド。現行 pgmem lock も同じ pin と照合した。
pgmem は専用 guest build と host を持ち、[gen-aot.sh](https://github.com/shibukawa/pgmem/blob/b3ce3c3da194928e8b8b1d9f0f244c33fc179857/wasm/gen-aot.sh)
は生成 Go に legacy EH 側を使い、exnref 側は別用途に分けている。この設計を MariaDB の互換性証明として扱わない。

比較元は [v0.4 baseline](v04-baseline.md): Start→SQL 308.5/335.3 ms、Fork→COUNT 288.7/349.2 ms (p50/p95)、
×16 は約281 MiB/DB、ready 約4.5 GiB、CPU 約9.46 CPU-sec。
SQLAlchemy 100 tests は Start 約39.0 s、Fork 約43.1 s。
本 spike は feasibility の測定であり、これらを更新する性能測定ではない。

## 2. 現行 guest の依存 inventory

全 import の signature、静的 direct-call 数、opcode 数、provenance は
[wasm2go-feasibility-evidence.json](wasm2go-feasibility-evidence.json) に保持。
静的 call site / import は動的実行・必須性の証明ではない。特に socket/signal の全経路は未実行。

### Artifact と build に存在する要求

| 項目 | 実ファイル / 現行 source の証拠 | generated-Go への意味 |
|---|---|---|
| WASI/WASIX | 関数65 import: WASI preview1 36、`wasix_32v1` 28、`wasi.thread-spawn` 1。別に `env.memory` 1 | WASI-only host では不足。独自 WASIX import interface が必要 |
| memory32/shared | imported shared memory min 4,096/max 32,768 pages = 256 MiB/2 GiB | host memory の所有・初期化・growth・thread 間共有を維持する必要 |
| atomics | 4,233静的命令。wait32 1、notify 1を含む | 基盤の縮小実験は通過。すべての実命令の変換は EH 後まで未確認 |
| modern EH | `try_table` 12,747、`throw_ref` 3,746、tag 2。最初の失敗は `__wasm_call_ctors` (fn65) | tested converter の命令 decoder / lowering が未対応 |
| pthread/TLS | `wasi_thread_start`、`__wasm_init_tls`、`__tls_base/size/align`、`__stack_pointer`。mutable globals 4 | agent ごとの stack/TLS/globals、共有 memory、futex、終了・join が必要 |
| filesystem | fd read/write/pread/pwrite/seek/readdir/stat/allocate/datasync、mkdir/rename/unlink/readlink、WASIX `path_open2`/dup/fdflags/getcwd | datadir、metadata、errno、FD、mount、並行I/Oを実装・検証する必要 |
| mmap | guest sysroot に `libwasi-emulated-mman.a`、現行 link に mmap/mmap64/munmap wrapper | mmap import がなくても不要ではない。guest 内の emulation と linear-memory allocation が残る |
| clocks/timers | WASI clock_time_get/poll_oneoff/sched_yield、WASIX futex の timeout | monotonic/realtime/process/thread clock と timeout の意味を保つ必要 |
| signals/process | callback_signal/thread_signal/thread_exit/proc_exit2/proc_id/proc_signals_get/sizes_get、`__wasm_signal`/`__wasm_sigaction` export | registration/delivery/exit と agent・instance の扱いは追加作業。fork/exec の import はない |
| socket imports | WASI sock_recv/send/shutdown、WASIX sock_open/bind/connect/options/address/resolve 等 | artifact に存在する。通常 MySQL TCP は Go host 側なので全 socket 機能を即 blocker としない |
| host communication | guest は stdin/stdout の4-byte length付き API v2 frame。Go host が loopback MySQL wire を提供 | fd stream と framing は再利用候補。in-process 接続には内部 transport/ownership の変更が必要 |
| dynamic growth | memory.grow 1、memory.size 2、memory.init 4、data.drop 2、copy 3,794、fill 2,710 | fixed-size byte slice のみでは不足。grow後も他 agent の address が正しいことが必要 |
| SIMD / table | SIMD系29,634命令、funcref table 17,204 entries、21,757 defined funcs | 大きい変換・compile surface。SIMDの代表命令は縮小実験成功 |
| initialization | start section fn67、constructor fn65、data segments 3、exports 5,022 | data init、constructor、main、thread entry の順序を省略できない |
| Emscripten | `env` function import は0、JS pthread/invoke/mmap glue の import なし。現行 build は `wasm32/WASIX` | source の Emscripten 分岐を現行 artifact の依存として数えない |

現行 build provenance は WASIXCC 0.4.7、LLVM 21.1.206、Binaryen 133、sysroot `v2026-07-03.1` /
`sysroot-exnref-eh`。WASIX executable は embedded MariaDB + resident API、`-pthread -fexceptions`、
initial memory 256 MiB / max 2 GiB / stack 8 MiB。MariaDB の別 build は行っていない。

### 実際に観測した要求と runtime の一般機能の区別

同一公開 AOT の既存 `--init-diagnostics` 対照実行で Start/SELECT、1,000行 seed、Snapshot/Fork/COUNT が成功。
ready までの成功した pthread_create は Start **10**、Fork **7**。thread が単に未使用で linked されているケースではない。
ready の linear-memory capacity は Start **670,433,280 bytes**、Fork **656,343,040 bytes**。
wrapped mmap balance は双方 **254,006,272 bytes**。これは allocator/mmap の既存診断値で、RSS/footprint や排他的所有量ではない。
従来の約281 MiB/DBと足し合わせず、guest の予約・増加要求が runtime 除去後にも残る根拠として読む。

Wasmer が一般に持つ process fork/exec、network、journal 等を MariaDB の必須依存には追加しない。
逆に、import名に mmap/pthread_mutex が見えないことを、その機能が不要な証拠にも使わない。

## 3. 無改変 conversion と最初の失敗

固定変換器の pure-Go backend に現行 WASM を入力した。

```text
wasm2go -pure -i mariamem.wasm -out-dir generated \
  -pkg generated -import example.com/mariamem-spike/generated
wasm2go: translate: call graph: fn65: unknown opcode 0x1f
```

| Attempt | 結果 | wall time | full guest code size / compile |
|---|---|---:|---|
| unchanged WASM / unpatched converter | exit 1、fn65 / 0x1f | 初回0.467 s、再実行0.045 s | 0 files emitted。生成なし、Go compile/link 未到達 |
| `_start,l4m_open,l4m_query_v2,wasi_thread_start` を entry roots 指定 | 同じ失敗 | 0.051 s | 未到達 |
| imported-memory metadata の小 patch を施した converter | 同じ失敗 | 0.025 s | 未到達 |

fn65 は実 artifact の `__wasm_call_ctors`。`0x1f` は `try_table`。
constructor を除外したり、例外命令を nop 化したり、未実装 syscall に無条件 success を返したりして緑の結果を作っていない。
entry root の指定だけでは call-graph decoding の障害を回避できなかった。
この時点で全 guest の instantiate / MariaDB init に進めない。

## 4. 縮小実験と限定 shim

すべての WAT は wasm-tools で validate 後に変換。compile と実行を別に記録した。
小モジュールの成功は MariaDB 互換性・完全な WASIX実装・SQL性能の証明ではない。

| 実験 | conversion / Go compile / execute | 証明できたこと |
|---|---|---|
| modern `try_table` | conversion fails `fn0 / 0x1f` | MariaDB規模ではなく、その命令が直接未対応 |
| `throw_ref` / exnref param | conversion fails `fn0 / 0x0a` | try_table の byte decodeだけを足しても不足 |
| legacy try/catch | compile/run、結果7 | legacy EH は利用できる。現行 exnref encoding と混同しない |
| defined shared memory load/store | compile/run、結果42 | shared memory の基本コード生成は成立 |
| imported shared memory | conversion成功、compile失敗 `m.M undefined` | imported-memory metadata が emitter に届かない局所問題 |
| imported-memory patch | compile/run、結果42 | 小 patch で当該不足を解消。外部 memory ownership の完全実装ではない |
| memory.grow / size | compile/run、結果3 (old pages 1 + current pages 2) | 小さい shared memory の growth 基盤は成立 |
| WASI spawn + atomic wait/notify | compile/run、結果42 | goroutine agent、shared memory、基本wait/wakeが成立 |
| agent-local global | compile/run、結果116 (main99 + worker17) | globals はagentごとに分離、memoryは共有される |
| SIMD with defined memory | compile/run、結果42 | i32x4 add/extract の代表命令は成立 |
| WASI filesystem | デフォルト host はerrno46、明示MemFSでmkdir/stat/remove成功 | default hostは実host rootを開く設定。MemFSを明示する必要がある |
| WASIX futex_wait | custom importを未実装ならpanic。限定shim成功 | changed-value経路のABIを接続可能。blocking経路は明示的panicで未実装を維持 |
| WASIX worker exit | 未実装hostでworker trap。限定Goexit + wait hookで終了・join成功 | 正常worker終了の基盤は作れる。process/main exitやsignalは未実装 |
| WASIX path_open2 | 未実装hostでpanic。限定bridgeでMemFS create/close成功 | extflags=0のsubsetはWASIへ接続可能。unsupported extflagsはENOSYSとして拒否 |

SIMD最初のmemoryなしfixtureも `m.M undefined` でcompile失敗したが、現行guestにはmemoryがある。
その補助コードの問題を現行guestの独立したSIMD blockerと数えず、memory付きcontrolで再確認した。
thread終了の wait hook は生成packageに1関数を追加する実験で、既存public APIには追加していない。

代表的な小モジュールは生成Goが約0.9–113 KiB、binaryが約2.48–2.93 MB。
限定shimのcompile/linkはcacheを含む0.23–0.85 s程度の例がある。
**これは現行guestの生成量・compile時間・配布sizeの推定には使えない。** 完全guestのGo code/binaryサイズは未取得。
各試行の時間、compile error、出力、生成サイズは比較JSONに保持。16 GiBでfull guestをcompileできるかも未回答。

## 5. Blocker の分類

| 要求 | 分類 | 根拠と必要な作業 |
|---|---|---|
| imported memory codegen | Local | 小patchでreductionのcompile/run成功。外部shared memory所有とdata/initの監査はまだ必要 |
| missing importの単純binding | Local (subsetのみ) | path_open2・futex changed-value・通常worker exitを小shimで接続できた |
| modern EH/exnref | Architectural adaptation | 現行guestは直接未対応。semantics-preservingなconverterのEH対応、またはguest/sysrootの例外build model変更が必要。try_table/throw_ref/longjmp/C++unwindを削除して済ませられない |
| 完全なWASIX pthread/TLS/exit | Architectural adaptation | spawn/atomic/global分離は成立するが、libcのblocking futex、TLS、thread signal、proc_exit2、join、failure/cancellationを同一instance契約に統合していない |
| filesystem/mountモデル | Architectural adaptation | MemFSとopen subsetは成立するが、WASIXのvirtual-root/FD拡張、InnoDB並行I/O、Snapshot入出力mountとnamespace、error semanticsを保持するadapter/runtimeが必要 |
| in-process host/guest境界 | Architectural adaptation | 現行hostはexec/pipe/PIDとguest全体のabortを所有する。生成Goのgoroutineをプロセス終了同様に回収する仕組みは未設計 |
| clocks/socket/signalの全経路 | 未確定 | importsとsourceは確認。実guest未実行なので、必要subsetや正しい代替をこのspikeでは確定しない |

modern EH が解ければさらにdecoder/SSA/codegenの障害が現れる可能性がある。
現行guestの全命令を通していないため、「上記だけ直せばSQLが動く」とは結論しない。
legacy EH の別sysrootで同じMariaDBが動くかは未実験。これは小さなflag変更で成立するという証拠もない。

## 6. Minimal execution / performance 到達点

| 段階 | current guest as generated Go |
|---|---|
| instantiate / initialize | 未到達 (conversionで停止) |
| basic filesystem | guest全体は未到達。reduction + explicit MemFSのみ成功 |
| MariaDB initialization | 未到達 |
| mariamem API v2 ready | 未到達 |
| SELECT 1 | 未到達 |
| existing Go host / MySQL-wire | generated-Goでは未到達。公開Wasmer対照経路のみ成功 |

MariaDB-ready / SQL-capable の generated-Go 経路がないため、startup/process count/memory/CPU の比較計測は実施しない。
縮小モジュールは1 Go processで動くが、mariamemのruntime countや約281 MiB/DBが同様に減る証拠ではない。

## 7. Distribution と運用への含意

以下は成功時の可能性であり、実装済みの変更ではない。

- **Wasmer/native bundle:** generated engineをGo binaryに組み込めればWasmer executableとplatform AOTをruntime配布から外せる。WASIXサービスをGo側が担う必要は残る。
- **Go zero-setup:** moduleにgenerated source/dataを同梱できればnative bundleのstartup downloadを減らせる。代わりにGo module取得量・consumer compile負担・build cacheが増える。既存のartifact identity/verificationをどう置換するかは別のtrust設計で、検証を省略する承認ではない。
- **Python:** Go engineだけでPython in-process化はできない。現行Python wrapper + Go host binaryを残す案ではWasmer childは減らせてもplatform wheel/binaryは必要。FFI化なら別のABI・lifecycle設計になる。
- **artifact size:** Wasmer/AOT assets削減とgenerated source/binary増加の双方があり、現行guest全体が未生成なのでnet sizeは不明。
- **notices/license:** tested wasm2go forkはMIT。生成helper/runtime codeを同梱する場合はそのnoticeと依存確認が加わる。MariaDB/lite4mariadbのGPL由来の対応ソース・ライセンス義務は独立して残る。Wasmerを実配布から外せた範囲だけreview対象が変わり、義務が全体として消えるわけではない。
- **portability:** Go生成物でWasmer/AOTのplatform依存を減らせる可能性はあるが、memory/atomic/unsafe/OS FS/clock/exit実装を各platformで確認する必要がある。このspikeはmacOS arm64のみで、Windows/Linuxへの対応を宣言しない。

## 8. Architecture decision inputs

| 質問 | このspikeの事実 / baselineとの関係 |
|---|---|
| runtime boundary removable? | 小モジュールではexternal runtime不要。現行MariaDBは未達。internal transportとabort ownershipの変更が必要 |
| WASIX dependency removable? | Wasmer実装は置換候補だが、現行artifactの28 WASIX importsのABI依存は残る。guest無改変のままWASIX契約自体を消せない |
| pthread compatible? | spawn/shared memory/agent-local globals/正常worker exitは直接成功。full libc/TLS/futex/signal/teardownの互換性は未確認 |
| filesystem compatible? | MemFSとWASIX openの限定subsetは直接成功。InnoDB/Snapshot/mount semanticsは未確認 |
| likely startup benefit | baselineのruntime/ready residual約40 msとspawn約1 msに削減機会。native検証約44 msの配布方式差も検討対象だが、削減値ではない。StartのMariaDB init約211 ms、Forkのrestore約75 ms/検証約62 msは変換だけで消える証拠がない |
| likely memory benefit | external runtime固有の保持量は削減候補。guest memory/fs/engineは残る。×16約4.5 GiBがどれだけ減るかは未測定。shared helperはmax reservationを使い、Go GCへの影響も未評価 |
| distribution benefit | Wasmer/AOTのplatform assetsとGo runtime downloadを減らせる可能性。Python host binaryやgenerated source/compile負担は残り得る |
| complexity | 小patchだけの差し替えには収まらない。EH/build、WASIX adapter、thread/FS/host lifecycleの複数boundaryに作業がある |
| correctness risk | unwind/longjmp、TLS/stack、futex race・timeout、thread/process abort、FD/namespace isolation、Snapshot export/restore、instance回収のsemantic差 |

CoW/runtime-sharingとの比較順位は付けない。

## 9. 残る設計上の質問

- 現行exnref EHを変換器で実装するか、legacy EHを使う互換guest buildを検証するか。後者でもWASIX libcとC++ unwinding/longjmpの契約を保てるか。
- WASIX compatibility hostに必要な最小subsetを実guestでどう確定するか。blocking futex、signal、process/thread exitとTLSをどこが所有するか。
- 全guestの変換とGo compileが通るか。生成size・compiler peak・binary sizeは許容範囲か。
- 現行のguest-wide invalidation/timeoutを、in-processで他DBに波及させず、全workerを回収するには何が必要か。
- 同じInnoDB/1,000行fixture、Snapshot/Fork、ordinary pools、SQLAlchemy suitesで性能・cleanup・trustを検証できるか。

## 10. 回帰確認

通常経路を変更するGo/C/runtimeコードはない。実行済みの結果は以下。

- **real-guest integration: 成功。** 既存Wasmer経路のGo race integration (9.086 s) とPython timeout/multiclient 3 tests (2.40 s) が通過。
- **normal `check`: 完走せず。** `go test ./...` がignored実験出力に残った変換失敗時の空 `module.go` を拾い、`expected 'package', found 'EOF'` で失敗した。表示された通常製品packageは通過したが、後続のvet/Python/public-source検査には到達していない。
- 出力rootにも変換前に独立 `go.mod` を作るよう実験driverを修正し、失敗出力を通常moduleから隔離した。現行guestの変換自体は失敗・ビルド未到達のため、ユーザーの追加指示に従いcheckの再実行・追加回帰テストは省略。この隔離修正も再テストしていない。
- **`git diff --check`: 成功。**

実験の変換器patchはbuild用コピーのみ、生成Go・実行binary・raw logsはignoredディレクトリのみ。
既存の未追跡npmファイルはチェック実行中のみ退避して復元済み。コミットには含めない。

### YELLOW

生成Go実行に必要な基盤の複数部分は直接成立したため、技術的可能性は残る。
ただし**現行guestをそのまま、少量のglueだけでWasmerから置き換える経路は成立していない**。
modern EH/exnrefの変換またはguest buildの互換化、WASIX thread/TLS/futex/exitとfilesystemのadapter、
hostのtransport/abort/cleanup ownershipに意味のあるarchitectural adaptationが必要。
full guestの変換・MariaDB-ready・SQL・全semantic互換性は未解決であり、性能改善の見込み値を採用判断には使えない。
次に進む境界と必要な互換性を設計で決める必要がある。別architectureを自動選択しない。

## Legacy EH guest experiment

2026-10-01。開始HEADは `05d0aa8230564649df9a80a0f94ff66515b6aeb5`。
前節の事実・original YELLOW evidenceを保持する。追加の [比較証拠](wasm2go-legacy-eh-evidence.json) と
[再現手順](spikes/wasm2go/README.md#legacy-eh-toolchain-experiment) を参照。

### 開始前の branch health

既存の未追跡 `package.json` / `package-lock.json` を内容そのままignored buildに退避し、
`git status --porcelain` が空、HEADが指定SHAであることを確認した。
生成結果rootの独立 `go.mod` により、`go list ./...` は通常14 packageのみを列挙した。
**guest buildを開始する前に**以下が完走。隔離修正の追加コミットは不要だった。

- normal `scripts/verify.py check`: Go test/vet成功、Python **368 passed / 3 skipped** (8.97 s)、public-source検査324 files成功。
- released Wasmer `scripts/verify.py integration`: Go race **8.933 s**、Python timeout/multiclient **3 passed** (2.42 s)。最初のsandbox実行はloopback bind拒否で失敗し、同一チェックの承認済み制限外実行が成功。
- `git diff --check`: 成功。

### 新 EH の起源

production経路は `prepare_guest.py` → `build_guest_wasm.py` → upstream `wasm/build-wasix.sh` →
CMake `wasix-toolchain.cmake` / `cmake/os/WASIX.cmake` / `wasm/CMakeLists.txt` → WASIXCC → wasm-ld → wasm-opt。
CMakeは `-pthread -fexceptions -fno-strict-aliasing`、Release compile `-O3 -DNDEBUG`、
final link `-O2 -pthread -fexceptions` と既存wrap/export/256 MiB initial・2 GiB max・8 MiB stackを指定する。
公開lock/provenanceは WASIXCC **0.4.7**、LLVM配布tag **21.1.206**、sysroot **v2026-07-03.1 / sysroot-exnref-eh**、Binaryen **133**。
実験の同じtagの実binaryは **WASIX clang 21.1.2 / WASIX LLD 21.1.2 / wasm-opt 133** と報告した。
実行hostは既存Linux arm64 Docker image `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`。
canonical releaseのLinux x86_64 hostとは異なる。exnref sysrootのlibc/libc++/libc++abi/libunwind SHA256は公開provenanceと一致した。

実際の0.4.7 `help-config`、`-###`、assembly、object、link前後の成果物で確認した。
[WASIXCC](https://github.com/wasix-org/wasixcc/tree/v0.4.7) の既定 `WASM_EXCEPTIONS=yes` はexnrefを選び、
compiler/backendとlinkerへ `--wasm-enable-eh`、`--wasm-enable-sjlj`、`--wasm-use-legacy-eh=false` を渡す。
legacy指定は `true` と `sysroot-eh` に切り替える。LLVM backend optionの存在も実binaryの `--help-hidden` で確認した。
post-linkの既定wasm-optは **`--emit-exnref`** を付けるため、legacyでcompileしても最終出力は新EHになる。

| 実C++ catch/rethrow + setjmp/longjmp対照 | try_table / throw_ref | legacy命令 |
|---|---:|---|
| exnref compiler object | 7 / 5 | なし |
| exnref linked・post-opt前 | 43 / 9 | なし |
| legacy compiler object | 0 / 0 | try 7、rethrow 3、delegate 3 |
| legacy linked・post-opt前 | 0 / 0 | try 43、rethrow 6 |
| legacy + default post-opt | 38 / 8 | なし |
| legacy + emit-exnrefを省いた -O2 | 0 / 0 | try 38、rethrow 6 |

公開prepared sourceと一致する既存local MariaDB objectにも新EHがある：`sql_parse.cc.o` は89/14、
`sql_class.cc.o` は232/58、`item.cc.o` は381/61。これらはCI objectではなくlocal実測である。
**新EHはcompiler objectの時点で現れる。link/post-linkだけが起源ではない。**
MariaDBや依存が例外・SjLjを必要とすることと、exnref表現を必要とすることは別である。
今回、同一sourceをlegacy表現でcompile/linkできた。新表現の選択はwrapper/backend/sysroot/post-link設定による。

### 隔離 build と成果物

pinned archivesからfresh sourceを再準備し、prepared manifestが公開版と完全一致
(`8a46305159195504a08562aab33cb0438b6ca813f830b8aef541c28de1eb1747`) することを確認した。
MariaDB/lite4mariadb revision、mariamem overlays、例外、pthread、shared memory、sessionsは変更しない。
既存local default buildとlegacy buildの `my_config.h` もbyte一致した。

1. `WASIXCC_WASM_EXCEPTIONS=legacy`、`WASIXCC_WASM_OPT_SUPPRESS_DEFAULT=yes`、`WASIXCC_WASM_OPT_FLAGS=-O2` を試したが、CMake `CHECK_FUNCTION_EXISTS(pthread_rwlock_rdlock)` の不正prototypeの検出用binaryをwasm-optが型エラーで拒否しconfigure停止。
2. fresh build directoryで **`WASIXCC_WASM_EXCEPTIONS=legacy` / `WASIXCC_RUN_WASM_OPT=no`** を設定すると全体compile/link成功。例外を無効化せず、CMake検出結果を手動上書きせず、compiler最適化も通常のまま。
3. valid full guestに既存Binaryen **-O2** を別段階で適用し、既存wrapperと同じenabled feature familyを指定、`--emit-exnref` を省いた。これは既存build処理の再現であり性能tuningではない。

raw legacyは22,164,434 bytes、WASIX importが4増えた。通常-O2を再現すると追加importは消える。
途中の `--all-features` 試行は意図しない**compact imports**を生成し、Wasmerもそれを拒否した。
最終比較対象はその試行を採用せず、既存feature familyのみの成果物とした。

| 最終比較 | released guest | legacy + existing -O2 |
|---|---:|---:|
| WASM bytes | 18,802,825 | **18,613,516** |
| try_table / throw_ref | 12,747 / 3,746 | **0 / 0** |
| try / catch / catch_all | 0 / 0 / 0 | **12,749 / 101 / 11,630** |
| rethrow / delegate | 0 / 0 | **3,327 / 1,018** |
| import names/signatures | 66 imports | **全て一致** |
| shared memory min / max | 256 MiB / 2 GiB | **一致** |
| atomics / memory.grow | 4,233 / 1 | **一致** |
| funcref table / tags / mutable globals | 17,204 / 2 / 4 | **一致** |
| data segments / exports / start fn | 3 / 5,022 / 67 | **一致** |
| defined functions / SIMD命令 | 21,757 / 29,634 | **21,861 / 29,603** |

最終SHA256: `6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3`。
bulk-memoryのinit/drop/copy/fill数も一致。func/SIMD数の差は残り、EH/SDK/backendとlocal build hostの影響を完全分離していない。
WASM validation (`wasm-tools --features=all`) は成功したが、これらの静的比較だけでは実SQLの同等性を証明しない。

### 現行 Wasmer validation と continuation の停止

通常のmacOS AOTコマンドで、raw版と最終-O2版の双方が **Wasmer 7.4.2 / cranelift-opts** のvalidationで停止。
最終版のエラーは `legacy_exceptions feature required for try instruction (at offset 0x3e68b)`。
小さなlegacy対照も同じ拒否。`--enable-all` でも通らず、単純なfeature flagでの解決は確認できなかった。
[7.4.2 compilerのvalidator](https://github.com/wasmerio/wasmer/blob/v7.4.2/lib/compiler/src/compiler.rs) はlegacy flagを設定せず、
[Cranelift translator](https://github.com/wasmerio/wasmer/blob/v7.4.2/lib/compiler-cranelift/src/translator/code_translator.rs) はlegacy Try/Catch/Rethrow/Delegateを明示的にunsupportedとする。
runtimeへのpatchやbackend変更は行っていない。

対照のexnref版、およびlegacy compile後に既定post-linkでexnrefへ変換した小プログラムは、同じ現行headless binaryで
`C++ unwind=7 setjmp=9`、exit 0。これは新EHが動く対照であり、legacy MariaDBのruntime検証を代用しない。

**legacy guestはAOT生成前で停止した。** guest initialization、MariaDB ready、SELECT 1、CREATE/INSERT/SELECT、
実guestのthread動作・clean shutdownはいずれも未到達。指定のWasmer検証ゲートを通過しなかったため、
**wasm2goへの再投入、生成Go compile/instantiate、追加WASIX shim実装は行わない。**
新しいwasm2go側blockerは未観測。今回の次のblockerは**現行Wasmerのlegacy EH validation/codegen契約**であり、
bounded generator patchやWASIX shimの問題とは区別する。
分類は **Runtime contract work（検証用runtime経路）**。guest/build自体のarchitectural mismatchを示す結果ではない。

### Maintenance と明示的な回答

- **build changeの大きさ:** source patchなし。2つのsupported wrapper設定、legacy sysroot選択、既存-O2を別段階に置く小さなbuild分岐。configureとpost-linkの扱いを記録する必要がある。
- **reproducibility/pinning:** 同一input archives/overlays、SDK version、legacy sysroot、compiler/linker/Binaryenとfeature listを固定する必要がある。今回のlocal image ID/成果物/library hashesを保持。canonical x86_64再現は未実施。
- **obsolete compilerへの依存:** 古いcompilerへのdowngradeは不要で、現行21系/0.4.7が明示的に提供するmodeを使用。ただし[legacy EH](https://webassembly.github.io/exception-handling/legacy/exceptions/core/_download/WebAssembly-Legacy-Exceptions.pdf)は現行standardized EHとは別の旧proposalで、今後のSDK/tool対応継続は保証できない。
- **MariaDB/WASIX compatibility:** current sourceのcompile/linkと静的ABI保持は成立。実guestのunwind/SjLj/TLS/threads/SQL同等性は未確認。
- **Wasmer compatibility:** 現行runtimeは直接実行不可。legacyからexnrefへの変換版を動かしても、legacy成果物そのものの検証にはならない。
- **wasm2go advancement/next blocker:** 新命令を除去したartifactは得たが、必須ゲート未通過のためconverterを再試行していない。次のgenerator failureは不明。
- **bridgeかmaintainableか:** build上の実験bridgeは成立する。production adoptionを維持できるという証拠はない。current Wasmerとの同等性検証方法、例外/SjLj ABI、将来SDKのlegacy維持を先に設計する必要がある。

### 実験後の通常回帰確認

normal `scripts/verify.py check` はGo test/vet成功、Python **368 passed / 3 skipped** (9.15 s)。
既存released Wasmer integrationはGo race **9.045 s**、Python **3 passed** (2.40 s)。
最終report/evidenceを含むpublic-source検査と `git diff --check` も成功。
更新したinspectorで公開guestを再採取し、以前のinventoryとの完全一致を確認した。
追加したbuild/result rootにも独立 `go.mod` を置き、通常package discoveryから隔離した。
既存の未追跡npmファイルは退避時のSHA256を照合して復元し、コミットに含めない。

### LEGACY-EH BUILD NOT PRACTICAL

**この分類は「現行Wasmerで同等性を確認してからwasm2goへ進む」という今回の必須条件に限定する。**
legacy guestの生成自体は成功しており、sourceの大幅な書き換えやold compilerが必要だったという結論ではない。
現行Wasmerのruntime契約を変えずに要求された同等性確認済みguestを成立させられず、continuationを停止した。
二重encodingの検証関係やruntime対応を別の設計判断なしに追加しない。
**overall wasm2go verdictは YELLOW のまま。** SQL-capable経路と性能/resource改善の証拠は追加されていない。
