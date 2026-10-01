# v0.4 wasm2go feasibility spike

2026-10-01、固定ローカル M1 / 16 GiB / macOS 27.0 arm64、Go 1.26.8。
ベース: `e3224817ccfe28add8e386f7d56d425898bf644a`、ブランチ: `v0.4/wasm2go-spike`。
製品コード、guest、runtime 設定、public API、Snapshot/Fork、cache、検証・trust は変更していない。
実験は [spikes/wasm2go](spikes/wasm2go/README.md) と ignored build/results に隔離した。

**初回実験では無改変の現行 guest は変換段階で停止し、生成 Go での MariaDB-ready / SQL は未達だった。**
一方、共有メモリ、WASI thread-spawn、thread ごとの globals、atomic wait/notify、memory.grow、MemFS の最小実験は動いた。
この結果から「Wasmer を除けば即動く」とも「pthread のため原理的に不可能」とも判断できない。

**追試の現状: legacy EH guest は生成 Go で MariaDB-ready、通常 SQL、transaction、認証鍵 self-test、正常終了に到達。
overall verdict は GREEN CANDIDATE。** [末尾の追試](#legacy-eh-generated-go-execution) に局所修正、性能の尾部、残る契約と測定境界を記録した。
前節までの YELLOW と Wasmer validation 不可は当時の証拠として保持する。

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
初回 spike は feasibility の測定であり、これらを更新する性能測定ではない。末尾の探索的測定も既存 baseline の置換ではない。

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


## Legacy EH generated-Go execution

2026-10-01、開始 HEAD `fbe9ff4e4beac00ad33b64ca8cfb78a7029a6048`、同じ M1/16 GiB/macOS 27.0、Go 1.26.8。
今回の指示では Wasmer validation を前提にせず、既存の legacy artifact を同じ pinned converter へ直接渡した。
前回の `LEGACY-EH BUILD NOT PRACTICAL` は **Wasmer 7.4.2 上の validation を必須とした前回の条件**での分類であり、
legacy guest 自体の無効性を示していない。production/new EH/Wasmer と experimental/legacy EH/Go を分けた。
原 guest/source/build の対応、66 imports/signatures 一致、cross-runtime validation 不可の事実は前節のまま。
今回も製品・guest source・cache・MaxSessions・Snapshot/Fork・trust の変更はない。

再現手順は [isolated experiments](spikes/wasm2go/README.md#legacy-eh-generated-go-execution)、
raw trials/SQL/stack/回帰結果は [wasm2go-execution-evidence.json](wasm2go-execution-evidence.json)。
生成物・独立 `go.mod`・バイナリは ignored results 内のみ。通常 package には `.go.txt` のテンプレートを含めていない。
開始時に tracked tree は clean、既存 untracked npm 2ファイルは保持した。通常 check の allowlist 用に一時退避し、内容 SHA を確認して戻した。

### 変換・コンパイル・実行の到達点

入力は前回の **18,613,516 bytes / `6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3`**。
`try_table=0` / `throw_ref=0` のまま、追加 guest build・source 改変はしていない。

| 試行 | 変換結果 | 生成量 | 最初の compile failure |
|---|---|---|---|
| unchanged pinned converter | 成功、57.4 s、21,861関数 | 45 files、184,700,184 bytes | imported memory の `MemSize/Memory/MemMu` 等が未生成 |
| 既存 imported-memory patch | 成功、55.6 s | 48 files、184,760,140 bytes | `Fd_pread` へ2引数、`Fd_prestat_get` へ3引数を誤接続 |
| 上記 + import function-index patch | 成功、56.0 s | 48 files、184,761,664 bytes | generated packages と診断 host の compile/link 成功 |

後者の不具合は function index と import section index の混同だった。`env.memory` を先頭に含む場合、
SSA emitter が次ではなく前の import を参照していた。**関数 import だけを数えて解決する局所 patch**を追加。
2つの異なる signature を持つ WASI imports + imported memory の縮小例は修正前 compile failure、修正後実行0を確認。
既存 memory/thread/TLS の縮小例も再確認した。converter を別実装には切り替えていない。

235件の `SSA fixpoint cap` warning は全試行で残った。upstream emitter はこれを最適化反復の収束警告と説明している。
警告を無効化せず、選択した SQL/認証/終了の動作を実行で確認した。全 code path の正しさを保証する証拠ではない。
初回 compile の約77 sは log timestamp による概算のみ。最終 cached rebuild は0.298 s、同一 SHA の binary を再現した。
clean compiler/linker の個別 benchmark は取っていない。

| 段階 | 結果 |
|---|---|
| Go translation / compile / link | 成功。binary 77,848,546 bytes = 74.2 MiB |
| module instantiation / start function | 成功。shared memory、data/table/globals 初期化 |
| guest startup | 成功。private MemFS 内の認証鍵を準備 |
| MariaDB initialization | 成功。InnoDB data/undo/log/temporary files を作成、WASI workers 起動 |
| mariamem protocol ready | `ready=true, api_version=2, max_sessions=16, snapshot_version=1` |
| ordinary SQL | `SELECT 1`、CRUD、COMMIT/ROLLBACK、2 sessions、制約/構文エラー成功 |
| normal lifecycle | session close → zero-length shutdown frame → guest return → 全 generated workers join → exit 0 |

binary SHA は `cd02482c3700f5f953856cad6e29610de27f44bb18627b1ebfe449adf22ffb30`。
`otool -L` の依存は libSystem/libresolv。Wasmer link/子 process はなく、**1 DB = 1 Go process** + 共通 Python supervisor。
同一 Go process 内に複数 DB を作る設計には変更していない。
Wasmerへの依存は除去したが、host/guest の process boundary は今回残した。pgmem型のin-process embedding自体は未検証。

### 観測した不足と限定した対応

全28 WASIX imports のうち13をこの host で扱い、残る15は呼ばれた時点で panic する。
全 import を偽の成功で埋めていない。`Fd_dup/Fd_dup2`、`Thread_signal`、`Proc_exit2`、socket/resolve 系は未実装。

| 分類 | 実際の最初の failure / 対応 | 限界 |
|---|---|---|
| LOCAL | imported-memory metadata / function import index の2 patch | 汎用的な外部所有 memory linker の完成ではない |
| LOCAL | root `getcwd`、process ID、実 host CPU 数の adapter | この artifact に chdir/process creation import はない |
| RUNTIME CONTRACT | signal inherited-disposition count と callback registration | 新規 process の継承 count=0、`__wasm_signal` 登録のみ。配送/割り込みは未実装 |
| RUNTIME CONTRACT | `path_open2`、CLOEXEC get/set、descriptor close | flags=0/1だけを保持。exec/fork、dup の一般契約は未実装 |
| RUNTIME CONTRACT | blocking `futex_wait/wake/wake_all` | 既存 shared-memory atomic wait/notify queue に mapping。OptionTimestamp、mismatch/timeout/wake の ABI を確認。signal/cancellation は未対応 |
| RUNTIME CONTRACT | `thread_exit(0)` と worker wait | 既存 Goexit shim + wait hook。異常 exit/process termination は別契約 |
| RUNTIME CONTRACT | 明示的 MemFS + entropy devices | `/dev/random` / `/dev/urandom` だけを読み取り専用 OS device として追加。host-root FS は公開しない |
| ARCHITECTURAL | **今回の正常 SQL path では観測なし** | in-process cancellation/import ownership/full lifecycle の設計を完了したという意味ではない |

実行順の failure は signal inheritance → getcwd → proc ID → CLOEXEC → futex → CPU count → fd flags → entropy/worker exit。
最初の entropy 未対応では `caching_sha2_password` の key read が失敗し、**ready を成功扱いしなかった**。
本物の OS entropy device を追加すると鍵の読込・RSA callback self-test も成功した。
例外/認証/エラーを abort や成功に置換していない。timed blocking wait、changed-value、wake の縮小 check も成功。

**残る最初の課題:** 正常 SQL に未解決の hard failure はない。InnoDB 初期化の約1 s wait tail と、
未対応 signal/forced process-exit/cancellation の **RUNTIME CONTRACT** が次の検証対象。
診断10試行の遅い3件は file initialization 中、`ibdata1` open の直前に1.001–1.003 sの空白を持った。
別の遅い boot に SIGQUIT を送り、main の indefinite `AtomicWait32At` と worker の約1 s timed wait を捕捉した。
これは意図的に止めた診断で、成功試行・benchmark には数えていない。wait/wake の correctness、tail の原因は未確定。
登録順・通知・timer/scheduling を調べる必要がある。最適化や大きな runtime 実装は始めていない。

### Observable correctness の対照

公開 v0.3.0 `.wasmu` と今回の Go binary に **同じ既存 guest framing / SQL / assertions** を適用した。
ready、open、`SELECT 1`、CREATE/INSERT/SELECT/UPDATE/DELETE、COMMIT、ROLLBACK、
1062 duplicate key、1048 NOT NULL、1146 missing table、1064 syntax error、2 session の未 commit 行不可視、close/exit を確認。
columns/rows/status/error を含む記録22件が一致した。Go 側の full workload をさらに10回繰り返し、全て対照と一致、worker join/exit 0。
既存の `--check-auth-keys` も `PASS, generated=false, actual_callback=true`。

これは **観測した behavior の equivalence evidence**。byte-identical guest や same-runtime validation ではない。
legacy artifact は Wasmer 7.4.2 で依然 validation 不可。full MySQL-wire/public Go host は生成 Go へ接続していない。
SQL script は既存 resident protocol と通常 SQL期待値を使い、特殊な SQL/弱い correctness に変更していない。

### Exploratory performance / resource

最初の10 independent trials は全て SQL/normal shutdown 成功だが tail があったため、追加30試行で分布を保持した。
30件全て成功、4件でready >500 ms。除外・warmup差引・MariaDB tuning はしていない。
全測定は診断/timing OFF。開始は process launch 前、ready は既存 ready frame、first SQL は session open + `SELECT 1` の応答。
ready 後の OS counter 読取時間も first-SQL latency に入る。同じ procedure で production Wasmer control も30試行測定。

| single DB / 30 trials | min | p50 | p95 | max |
|---|---:|---:|---:|---:|
| Go start→ready ms | 22.5 | 42.5 | 1040.6 | 1045.1 |
| Go start→first SQL ms | 26.5 | 47.8 | 1052.4 | 1056.2 |
| Go ready RSS MiB | 106.9 | 107.3 | 107.8 | 108.0 |
| Go ready physical footprint MiB | 87.0 | 87.4 | 87.9 | 88.1 |
| Go CPU at ready sample, CPU-sec | 0.0314 | 0.0525 | 0.0686 | 0.0703 |
| Wasmer control start→ready ms | 238.5 | 252.4 | 271.5 | 281.4 |
| Wasmer control start→first SQL ms | 247.6 | 262.1 | 281.0 | 289.6 |
| Wasmer control ready RSS MiB | 373.0 | 379.8 | 397.8 | 405.7 |
| Wasmer control footprint MiB | 301.8 | 308.6 | 326.7 | 334.5 |
| Wasmer control CPU at ready, CPU-sec | 0.2440 | 0.2582 | 0.2893 | 0.3014 |

CPU は既存 `process_cost.c` の OS counters を ready frame の直後に取得。厳密な ready 瞬間の CPU ではなく、
background work と counter collection delay を含む。raw JSON に collection interval、RSS/footprint両方を保持。
RSS は shared code/圧縮の影響があり、281 MiB/DB baseline と直接比較する主 counter は **physical footprint**。

自然な isolation は独立 process のまま ×1/4/8/16、各3 independent group trials。CoW/runtime sharing を追加していない。
表は p50。3件なので scaling p95 の強い結論は出さず、全 trials/distributions を evidence に残した。

| DB数 | Go group-ready / first SQL ms | Go RSS total MiB | Go footprint total / DB MiB | Go CPU-sec total | Wasmer control ready ms | control footprint/DB MiB | control CPU-sec |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 29.5 / 33.7 | 107.6 | 87.7 / 87.7 | 0.0393 | 246.0 | 307.4 | 0.2534 |
| 4 | 1057.1 / 1063.5 | 431.6 | 351.8 / 88.0 | 0.2268 | 300.9 | 318.6 | 1.1968 |
| 8 | 1079.7 / 1088.2 | 863.4 | 704.3 / 88.0 | 0.4908 | 567.5 | 334.9 | 3.2609 |
| 16 | 1130.7 / 1144.6 | 1722.5 | 1404.3 / 87.8 | 0.8097 | 1184.8 | 334.7 | 6.6980 |

×16 ready footprint は約1.37 GiB、RSS 約1.68 GiB / 107.7 MiB/DB。
全 group の SQL/close は成功し、全 child は exit 0で reap、close後 guest RSS=0。
これは process teardown の結果であり、long-lived Go process 内の Close/GC/allocator reclamation の証明ではない。
Python supervisor 自身の memory/CPU は除外している。peak memory や大量 SQL 後の保持量は未測定。

### v0.4 baseline と解釈

既存 baseline は **public Start→first SQL 308.5 / 335.3 ms**、1,000-row ready 312.2 / 342.9 ms、
Fork→COUNT 288.7 / 349.2 ms、×16 memory/DB 280.8 MiB、ready total 4501.3 MiB、CPU 9.463 s。
今回の direct guest は public host、MySQL-wire、per-Start trust verification、1,000-row fixture setup を含まない。
同じ直接境界の Wasmer control を併記する理由は、この差を generated-Go の勝利に数えないため。
control footprint/DB 334.7 MiB は歴史 baseline 280.8 MiB と一致せず、差の内訳は未帰属。baseline値を置き換えない。

- **fixed runtime/lifecycle cost は materially 減ったか:** 観測した fresh direct path の p50 と CPU は明確に低下。
  first SQL p50 は control 262.1→47.8 ms。ただし Wasmer setup 除去、generated-Go execution、MemFS の効果は個別に分離できない。
  p95 は 281.0→1052.4 msに悪化し、public baseline 335.3 msにも未達。速い中央値だけで startup KPI 達成とはしない。
- **per-DB memory は materially 減ったか:** この ready state の physical footprint は対照で334.7→87.8 MiB/DB、
  歴史281 MiB/DBに対しても大きく小さい。runtime/allocator の backing、Go/Wasmer metadata、guest heap、FSの内訳は未分離。
  guest の min 256 MiB/max 2 GiBは変更なし。生成 constructor は安定 shared pointer のため **2 GiB/DBを予約**するが、
  全ページがresidentになるわけではない。virtual/Go heap accounting と resident footprint を混同しない。
  FS/stateの共有はなく、SQLによる成長・memory pressure・長時間後の効果は未確認。
- **scaling/cleanup:** ×16 CPU/ready footprintは低下する証拠がある一方、約1 sのtailがgroup-readyにも現れた。
  process終了は機能した。同一 process内の isolation、fault containment、キャンセル、memory返却を解決したとは言えない。
- **測っていないもの:** prepared Fork、snapshot/restore、ORM 100 tests、public API startup。これらの baseline の改善は未証明。

### Decision inputs / maintenance

| 問い | 今回の証拠 / 残る判断 |
|---|---|
| external runtime boundary removable? | この SQL実行binaryは Wasmer不要。ただし既存 public hostとの接続/embedding方式は未設計 |
| WASIX dependency removable? | Wasmer implementation は外せたが、guest の WASIX imports/意味は残る。build SDKも残る |
| pthread compatible? | real MariaDB workers、2 sessions/TLS、wait/wake、normal join成功。signal/異常exit/futex stress未完 |
| FS compatible? | private MemFS + entropy + bounded flagsでSQL/rollback成功。全 FS edge casesやdurabilityではない |
| startup benefit? | p50/CPUに大きな改善候補。p95の約1 s waitは次の要検証事項 |
| memory benefit? | ready footprint減少を実測。2 GiB reservation、長時間/大きなDB/in-process GCは要調査 |
| distribution benefit? | AOT+WasmerをGo executable/linked generated codeへ置換できる可能性。今回binaryは74.2 MiB、圧縮releaseサイズ未測定 |
| Go/Python packaging? | Goへの組込ならnative download不要の可能性。現在のprocess方式ならplatform binary配布は残る。Pythonもnative executable/bridge選択が必要 |
| portability? | darwin/arm64のみ実行。upstream SIMD helpers/unsafe、entropy devices、Go/OS依存を他platformでも確認する必要 |
| maintenance? | compiler optionは既存 supported legacy mode。WASIXCC 0.4.7/LLVM21/Binaryen133 pin、legacy-compatible postopt、2 converter patchesを再現管理。deprecated encodingへの依存は残る |
| implementation complexity / correctness risk? | 変換器2局所patchと限定hostでSQLまで来た。full WASIX hostへの拡大、EH全経路、timer/atomic ordering、signals/exit/cancellation/FS差は未検証 |
| notices/licensing? | Wasmerを実際の配布物から外す場合のみruntime noticesの対象が変わり得る。converter/Go/WASIX/libc/wolfSSL等のreviewは必要。MariaDB/lite4mariadb GPL-derived obligationsは独立して残る |

次に決めるべき質問は、1 s waitの通知順/タイムアウトが正しいか、未対応 signal/exit をどの境界で保証するか、
2 GiB reservationとGo memory accountingが大きなDB/同一processでどう効くか、legacy pinを継続できるか、
full public host/wireと既存integration期待値を接続できるか。Snapshot/Fork設計や別architectureの優劣は選んでいない。

### Regression / verdict

`go test ./...` / `go vet ./...`、Python **368 passed / 3 skipped**、public-source check成功。
通常 Wasmer integration: Go race integration成功（9.276 s）、Python timeout/multiclient **3 passed**。
追加ファイルを含めた最終通常チェックと `git diff --check` を commit 前に再実行した。
製品/runtimeへのdiffはない。生成codeの独立 `go.mod` が通常 package discovery を遮断している。

**GREEN CANDIDATE — legacy guest は生成 Go で MariaDB-ready と普通の SQLに到達した。**
SELECT 1のみでなく、CRUD/transactions/errors/2 sessions/認証self-test/normal shutdownと対照一致がある。
ただし production-ready GREENではない。残るbounded compatibility work、wait/wake tail、未検証runtime契約、
full API/wire/長時間/cancellation/platform検証を終えたという判断はしていない。原 YELLOW evidenceは上に保存した。

## Generated-Go tail latency investigation

開始点は `c63f81e099dbe4417aa42fb925cadb40af7a7fd3`、branch は `v0.4/wasm2go-spike`。
同じ固定参照環境、legacy guest `6a2e1a8c…`、計測 binary `cd02482c…` を継続使用。
**runtime fix は適用していない。** 以下の再計測は同一 binary の再現確認であり、改善後の値ではない。
生成 code、trace、exec adapter、Go test は ignored directory の独立 module 内だけに置いた。
通常 runtime、MariaDB 設定、API、Snapshot/Fork、thread/shared-memory model は変更していない。
全試行・CPU/memory counters・重要 trace・source/hash・check 結果は
[tail evidence](wasm2go-tail-evidence.json)、再現方法は [spike README](spikes/wasm2go/README.md)。

### 100-run distribution：変更前 / 調査後の無変更再計測

各100回は独立 process。trace/guest diagnostics は off、SELECT 1 と正常終了は全て成功。
起点は process launch 前、ready は framing の ready 応答、SQL は最初の SELECT 1 応答。
CPU は ready 直後の OS sample。counter 取得時間が first-SQL に含まれる。
quantile は sorted samples の線形補間、単位は ms。平均で二峰性をまとめない。

| series / metric | min | p50 | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 変更前 ready | 23.6 | 39.6 | 46.0 | 52.8 | 1053.8 | 1055.4 |
| 変更前 SELECT 1 | 28.0 | 44.7 | 51.5 | 61.0 | 1067.5 | 1068.8 |
| 変更前 CPU | 33.4 | 51.7 | 58.6 | 64.6 | 79.5 | 94.2 |
| 無変更再計測 ready | 25.5 | 40.3 | 53.7 | 1042.3 | 1054.1 | 1055.6 |
| 無変更再計測 SELECT 1 | 29.9 | 45.5 | 59.3 | 1046.7 | 1065.6 | 1068.0 |
| 無変更再計測 CPU | 35.0 | 52.1 | 60.8 | 69.8 | 74.9 | 78.8 |

slow 判定は ready ≥500 ms。変更前 **4/100 (4%)**、再計測 **6/100 (6%)**。
変更前 p95 が速い群に収まったのは件数による。tail 消失の証拠にはならない。
以前の30回は4/30、今回の wire prototype は32/100であり、頻度は起動順序・計測境界に依存する。

| cluster | n | ready min / p50 / p95 / max (ms) | SELECT 1 p50 / p95 (ms) |
| --- | ---: | --- | --- |
| 変更前 fast | 96 | 23.6 / 39.3 / 46.3 / 55.4 | 44.6 / 52.2 |
| 変更前約1秒の群 | 3 | 1037.9 / 1053.8 / 1055.2 / 1055.4 | 1067.5 / 1068.6 |
| 変更前の初回、別の中間値 | 1 | 613.8 | 619.8 |
| 無変更再計測 fast | 94 | 25.5 / 40.1 / 50.1 / 58.2 | 45.2 / 55.4 |
| 無変更再計測 slow | 6 | 1042.1 / 1050.3 / 1055.2 / 1055.6 | 1061.2 / 1067.4 |

初回613.8 msは未計装のため帰属できない。別の計装 binary の初回にも外側1.124 sに対し
全 guest trace が52.6 ms以内に終わる例があった。process launch / Go初期化前 / observer scheduling の
未帰属区間であり、これを page-cleaner の1秒 wait と同一原因とは断定しない。全値は除外せず保持した。

### Direct trace と原因

`trace_waits.py` は AtomicWait の expected/current、queue registration/token、notify count/対象、
timeout/return、thread spawn/start/exit、TLS、guest start/return を記録する。
少数の caller frame と、問題の guest target read/cond signal も記録。最大10,000 eventsをmemoryに保持し、
正常終了後にJSON出力する。対象 trace は dropped=0。計装は scheduling を変えるため性能値・頻度に使わない。
event timestamp は Go package initialization からの monotonic time。queue mutation は同じ park lock 内で記録した。
wait-entry timestamp は lock 前なので JSON の列挙順と時刻順が一部異なる。

Binaryen133の同じ-O2に `--symbolmap` だけを追加した解析用再生成は、**元 guest とSHA256完全一致**。
関数名は推測ではなく、このmapから得た：
`Fn18158=buf_flush_wait`、`Fn18163=buf_flush_page_cleaner`、`Fn18169=log_make_checkpoint`、
`Fn18170=buf_flush_sync_batch`、`Fn17976=create_log_file`。

guest source の `storage/innobase/buf/buf0flu.cc`：

- `buf_flush_wait()` (2321–2350付近) は mutex を保持して target を設定し、`do_flush_list` をsignal、`done_flush_list` をwait。
- page cleaner (2804–2841付近) は **target を読む→mutexを取る→idle/dirty状態からwaitを決める**。
  mutex取得直後にはtargetを読み直さない。timed waitのdeadlineは `set_timespec(abstime,1)`。
- wait終了後に target を読み直し、flush完了時に `done_flush_list` をbroadcastする。

slow trace #3では、ワーカーが先にtarget=0を読んでmutex待ちに入り、主スレッドの要求とsignalを挟んで
mutexを取得した。live target は12288だが、ワーカーはそのまま約1秒のtimed waitに入った。
signal時の musl private-cond waiter list は空。futexへのnotify自体が発行されていない。

| fast trace #1 (ms) | slow trace #3 (ms) | operation |
| ---: | ---: | --- |
| 14.514 | 13.194 | worker tid2 reads target `0xf04248` =0 |
| — | 13.194–13.680 | worker waits for mutex futex `0x68fb44`, main tid0 wakes exactly one |
| 14.514 | 13.680 | worker obtains mutex; live target fast=0 / slow=12288 |
| 14.533 | 13.775 | worker barrier `0x1aa18694`, expected=2, registers wait; timeout fast=1s / slow=999.513ms |
| 14.964 | 13.647 (**registration前**) | main signals cond `0x68fb88`; fast waiter=0x1aa18688 / slow waiter=0 |
| 15.046 | **発行なし** | main futex wake of worker barrier |
| 15.048–15.118 | 13.738–1015.488 | main waits on barrier `0x1721374`, expected=2, timeout=none |
| — | 1015.351 | worker timer expires; atomic wait returns2 → WASIX woken=false |
| 15.085 | 1015.38付近 | worker broadcasts done cond `0x68fbe8`; tid2→tid0 barrier wake |
| 15.118 | 1015.488 | main resumes; fast returns not-equal1 because its barrier already changed, slow returns wake0 |

slow trace #11 repeats target0→mutex wait→live12288→empty cond signal→999.509ms timeout→done notification。
main TLS=1024、worker TLS=446793504で、wait/wake token・thread identityも対応する。
並行するtid1の400ms maintenance timerは主スレッドを再開させない。

**分類：InnoDB behavior / guest-level notification-before-registration + timer fallback。**
この順序はmusl/WASIX shimの契約に違反するlost wakeを示していない。
mutexのwakeは届き、比較/queue登録のraceではchanged-valueの即時復帰も機能している。
通知が待ち手の存在前に発生する条件変数は、後から来る待ち手用に通知を保存しない。
MariaDB source が設定した約1秒のdeadlineを消費してから、flush要求を処理して正しく起動している。

### Contract / minimal reproducer / fix 判断

WASIX libc `v2026-07-03.1` の `pthread_cond_timedwait.c` / `pthread_cond_signal.c` は private waiter listを
mutex解放前に登録し、signalはその時点のlistだけを処理する。
`__timedwait.c` は absolute pthread deadlineからclockの現在値を引き、相対nsをWASIXへ渡す。
実際のimportには約999.5msが渡されており、relative/absolute取り違えや秒への丸めではない。
Wasmer7.4.2 `futex_wait.rs` の実装は値不一致でsuccess/woken=true、timeoutでfalse。
既存shimは atomic wait rc1→true / rc2→false。queue lockはcompareと登録を保護し、wakeも同じlockを取る。
generatorの timer に既存の+1msがあるが、約1秒の起源はguest deadline。この+1msは今回変更していない。

隔離した [wait-contract-test.go.txt](spikes/wasm2go/wait-contract-test.go.txt) は実際のgenerated/base primitiveを使用。
`TestPageCleanerOrdering` はsourceの対象read/mutex/signal順序とprivate-condの非蓄積性だけを縮小したmodelで、
MariaDBやmusl全体を再実装・検証したものではない。
gateで順序を固定した早いsignalでは **1.001324 s / timeout2**、登録後signalでは **15.792µs / wake0**。
`TestWaitContract` は expected mismatch、通知の非蓄積、count0/1、compare→registrationに競合する100 wakesを確認。
全て `go test -race` 成功。queue登録のraceをタイムアウトで救う必要はなかった。

**修正なし。** guest側の待機判断を変えること、shimに架空のsticky signalを入れること、timeoutを短縮することは、
今回の契約を超える。正当なMariaDB待機の最適化をここで停止した。旧fallbackを失敗扱いにするtestも追加しない。
reductionのrace成功は、unsafe shared-memoryを使うfull generated guestのrace/correctness監査完了を意味しない。

### Resources / scaling 再計測

同一binary、cache/MaxSessions変更なし、RSSとphysical footprintを別々に記録する。

| metric (p50) | 変更前100 | 無変更再計測100 | 前回spike |
| --- | ---: | ---: | ---: |
| ready RSS / DB | 107.5 MiB | 107.4 MiB | 約107 MiB |
| ready physical footprint / DB | 87.6 MiB | 87.5 MiB | 約88 MiB |
| CPU to ready | 0.0517 CPU-s | 0.0521 CPU-s | 0.0525 CPU-s |

各scale3回（分位数は探索値）。process/DB、shared-state/CoWは無し。

| DBs | group-ready p50 / max (ms) | RSS total / DB (MiB) | footprint / DB (MiB) | CPU total (s) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 34.0 / 1035.0 | 107.5 / 107.5 | 87.6 | 0.044 |
| 4 | 1072.4 / 1077.9 | 432.4 / 108.1 | 88.2 | 0.285 |
| 8 | 1075.4 / 1139.1 | 863.2 / 107.9 | 88.0 | 0.395 |
| 16 | 1122.8 / 1261.8 | 1725.6 / 107.8 | 88.0 | 0.881 |

×16 footprint total p50 **1407.9 MiB (1.375 GiB)**、最大1434.2 MiB。
前回の×16 107.7 MiB RSS/DB・87.8 MiB footprint/DB・0.810 CPU-sと同程度。
全child正常終了・reap、after-close active=0 / guest RSS=0。
in-process thread cleanup、Go GCによるDB単位の回収を測ったものではない。

### MySQL-wire comparable boundary

**既存 host とMySQL-wireを接続できた。** `setup_wire.py` が別moduleを作り、既存 `host` / `guest` / `mysqlwire`
を変更せずimportする。小さなexec adapterはWasmer用argvを既存 `probe measure` に変えるだけ。
actual legacy WASMのsidecarを使い、generated executable/adapter/WASMのdigestを毎回確認してから `host.Start()`。
対照は同じdriverでrelease bundleの既存 `artifacts.Resolve()` / `host.StartVerified()` を実行する。
productionのtrustチェックを変更・無効化していない。

時刻の起点はfresh Go hostのmain内の **start-like call前**。artifact digest、guest process/init、ready frame decode、
wire listener、MySQL handshake、最初のSELECT 1を含む。build/transpilationは含まない。
hostのOS launch/Go初期化はwall timer外（public Go APIの呼び出し元は既に実行中）。CPUは両processの累積counter。
ready後のcounter取得もSQL時間に含む。

| boundary / metric | n | min | p50 | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| generated wire-ready (ms) | 100 | 84.1 | 94.7 | 1105.8 | 1113.2 | 1119.4 | 1127.4 |
| generated SELECT 1 (ms) | 100 | 88.3 | 99.3 | 1117.5 | 1122.4 | 1131.0 | 1136.7 |
| released Wasmer wire-ready (ms) | 30 | 278.1 | 289.9 | 304.0 | 314.5 | 332.6 | 339.1 |
| released Wasmer SELECT 1 (ms) | 30 | 288.0 | 300.2 | 312.2 | 323.5 | 341.7 | 348.4 |

generated slow **32/100**、対照0/30。同じguestの中央値の利点と、tailの悪化が両方残った。
per-row stage delta p50：generated verification48.5ms、host.Start39.5ms、ready→SQL4.3ms。
最後の4.3msにはcounter取得3.2msを含む。各stageのmedianの合計はtotal medianと一致するとは限らない。
対照 verification42.7ms / host.Start246.8ms / ready→SQL9.7ms。

| at wire-ready (p50) | generated | released control |
| --- | ---: | ---: |
| guest RSS | 107.6 MiB | 380.5 MiB |
| guest footprint | 87.7 MiB | 309.4 MiB |
| host + guest RSS | 118.5 MiB | 391.7 MiB |
| host + guest footprint | 92.1 MiB | 313.9 MiB |
| host + guest CPU | **0.1092 CPU-s** | **0.3016 CPU-s** |

generated host digest作業が約0.0658 CPU-s、guest約0.0383 CPU-s（各median）。検証を含めてもtotal CPUは約64%低い。
ただし実験のlocal digest pinはrelease trust/distribution設計の代用ではない。
generatedはWASMのprovenance hashとhost.Start内のsidecar hashを重ねて読み、対照は既存verified identityを使う。
本番のbinary/manifest/signature/source対応、path ownership/TOCTOU検証、download/resolution/cacheを決めたものではない。
public Go Startのenvelope/resolver、Python包装・host launch、1,000-row fixture、Snapshot/Fork/ORMは未接続。
v0.4 baselineのStart→SQL **308.5/335.3ms** とprototype **99.3/1122.4ms** は近い境界の参考比較で、同じpublic APIの測定ではない。
baseline **約281 MiB/DB** はphysical incremental memoryの値。RSS108MiBと直接割らず、今回のfootprint88MiB/DBと比べる。
×16 baseline約4.5GiB / 9.46 CPU-sに対しdirect guest約1.375GiB / 0.881 CPU-sだが、fixture/host境界差も残る。

### Correctness / architecture signal / remaining work

既存22-record SQL workloadをgeneratedで10回再実行し、release controlの全recordと一致。
ready、SELECT 1、CRUD、COMMIT/ROLLBACK、constraints/errors、2 sessions、正常終了を含む。
認証RSA self-testも再成功。legacy artifactをWasmer7.4.2で検証できない事実は維持し、これはobservable behaviorの比較。

- **Startup:** 40–50ms direct-guest medianは再現し、架空の同期省略で得た値という証拠はない。
  host/wire/digestsを含むmedianは約99ms。外部Wasmer setup/executionを除いた固定cost低下のsignalはあるが、component別の因果割合は分離していない。
- **Tail:** 約1秒の反復waitは理解できた。bounded shim bug修正で消せる根拠はなく、guest semanticsを維持して残す。
  schedulerが発生頻度を変えるのでp95の保証には使えない。初回の別未帰属区間も残る。
- **Memory:** 正常機能と同じbinaryで約108MiB RSS / 88MiB footprint/DBは維持。
  linear memory、MariaDB heap、MemFS、Go metadataは存在し、2GiB virtual reservationも残る。
  誤ったtimeoutや共有stateによる見かけの削減ではないが、埋め込み・大きなDBのmemory ownershipは未検証。
- **CPU:** 同じwire hostの探索比較でもtotal CPUは低い。full public API/fixture/ORMの同等比較は次の測定課題。
- **Productionization:** signal delivery、abnormal thread/process exit、panic/EH propagation、cancellation、timeoutとwakeの同時発生、
  spawn failure、thread join/detach/TLS destruction、shutdown中のpending SQL、host kill/EOF/backpressureを設計・検証する必要がある。
  15 fail-closed WASIX imports、timerの+1ms/zero-timeout境界、filesystem全契約、unsafe-memory/atomic ordering、Snapshot/Fork、
  platform/long-run/security/trust/release packagingは完成していない。正常全worker joinとprocess reapは強制終了/埋め込みcleanupの保証ではない。

通常チェック：Go unit / vet成功、Python **368 passed / 3 skipped**、public source check成功。
通常WasmerのGo race integration成功（9.050s）、Python timeout/multiclient **3 passed**（2.39s）。
既存未追跡npm filesはcheck中だけ退避し、同じSHA256で復元。`git diff --check` を実行。
製品runtime差分なし。生成 `.go` は独立 go.mod 内、tracked template は `.go.txt` のまま。

### Updated verdict

**GREEN CANDIDATE — TAIL UNDERSTOOD**

MariaDBのpage-cleaner待機順序と1秒timerで反復tailを説明でき、bounded queue/clock shimの誤動作は今回の原因として確認されなかった。
ゲストの意味を変えるtail削減は行わない。wire/verificationを含むmedian・CPU・memory低下のsignalと、tailの不利を両方記録した。
production-readyではなく、残るruntime-contract監査・trust/lifecycle設計が必要。CoW/runtime-sharingとの順位や次のarchitectureは選んでいない。

## Lost-wake semantics validation

基点 `e2a7e66344123a8c51a173d84c29e7866cb50936`。今回の分類は **GUEST-SIDE BEHAVIOR**、
tail-specific result は **TAIL GUEST-SIDE — NO FIX**。観測された通知は条件変数への登録より前であり、
futex queueのwakeをshimが失ったものではない。guestの既存1秒deadlineで復帰することは契約上許される。
このraceがMariaDB作者の意図した最適動作であるとは主張しない。明示された周期timeoutと、実際のsource orderingの結果である。
同期shim、生成器、guest、製品runtimeには修正を加えず、分離した再現テストと記録だけ追加した。
原データ・実行結果・source/binary hashは [semantics evidence](wasm2go-lost-wake-evidence.json)。

### Exact call path / expected semantics

同じlegacy guest sourceの `storage/innobase/buf/buf0flu.cc`：

1. 起動時のcheckpoint/flush経路は `buf_flush_wait()` (2321–2350) に到達。
   呼び出し側は `flush_list_mutex` を保持し、`buf_flush_sync_lsn` を更新、
   `pthread_cond_signal(&do_flush_list)`、`my_cond_wait(&done_flush_list, mutex)` を実行する。
2. `buf_flush_page_cleaner()` は2804行で `Atomic_relaxed<lsn_t>` のtargetを読み、2816行でmutexを取得する。
   この間にtargetが変わっても、待機前にはtargetを再確認しない。
   `page_cleaner_idle` / dirty stateがtimed branchを選ぶと2835行の `my_cond_timedwait()` へ進む。
   deadlineは `set_timespec(abstime, 1)`、復帰後2841行でtargetを再度読む。
3. 非SAFE_MUTEXの `include/my_pthread.h:417–418` はpthread waitへ直接展開する。
   WASIX libc `v2026-07-03.1` のmusl `src/thread/pthread_cond_timedwait.c` はprivate condition用に
   **新しいstack waiterの `barrier=2`** を作り、condition listへ登録してからapplication mutexを解放する。
4. `__timedwait_cp()` (`src/thread/__timedwait.c`) はconditionのabsolute CLOCK_REALTIME deadlineから
   現在時刻を引きrelative nanosecondsへ変換。
   `libc-bottom-half/sources/__wasilibc_futex.c::__wasilibc_futex_wait_wasix()` がwordを予備比較してから
   **`wasix_32v1.futex_wait(addr, expected=2, OptionTimestamp::Some(relative_ns), result)`** を呼ぶ。
   観測workerのtimeoutは約999.5ms、mainのdone waitは `None`。
5. private `pthread_cond_signal()` は同じmuslファイルの `__private_cond_signal(c,1)` へ進む。
   現在のwaiter listだけを走査し、対象nodeがあればbarrierを2→0にして
   `__wake()` → `__wasilibc_futex_wake_wasix()` → `wasix_32v1.futex_wake`。
   **listが空ならfuture waiter用のbarrierやpermitを保存せず、対象barrierへのfutex wakeも発行しない。**

したがって質問への答えは、**futexが比較するwordが変わったなら後続waitは即時復帰する必要があるが、
application targetだけが変わった今回の順序ではtimeoutまでの待機が有効**、である。
target `0xf04248` の0→12288はworker stack barrier `0x1aa18694` の変更ではない。
通知時にまだ存在しなかったbarrierは後から2で初期化され、expectedも2になる。
condition signalは現在のwaiter向け通知であり、sticky eventではない。
waiter登録とmutex解放のatomicityは、**mutex取得前のpredicate読取り**を保護しない。

前節のguest trace #3/#11はempty condition listを直接記録している。
slow #3では13.194msにtarget読取り、13.647msにempty-list signal、13.775msにworker登録、
1015.351msにtimeout、1015.383–1015.488msにdone wake/main復帰。
fast #1では14.533msにworker登録、14.964msにnonempty-list signal、15.046msにwake、15.082msに復帰。
さらにmain側ではsignal後・futex登録前のbarrier変更をexpected比較で検出し、即時復帰した。
sourceと同一SHAのsymbolmap、時系列、addressesは前節と既存 [tail evidence](wasm2go-tail-evidence.json) を維持した。

### Native / current Wasmer comparison

[pthread-signal-order.c](spikes/wasm2go/pthread-signal-order.c) は実際のpthreadを使った決定的な順序縮約。
mutexと別control conditionで「target読取り→先行signal→wait」と「登録→signal」を強制する。
timeoutはguestと同じ1秒で、短縮せず、pollや強制wakeは使わない。
実際のMariaDBをnativeへ再ビルドしたものではなく、sourceから抽出した順序を検証するもの。

同じCをnative macOS pthreadと、既存WASIXCC0.4.7 / WASIX libcの**new-EH** build→Wasmer7.4.2で各5回実行：

| implementation | signal before registration | signal after registration |
| --- | ---: | ---: |
| native macOS pthread | 5/5 timeout、1000.082–1005.039ms | 5/5 signal復帰、0.006–4.082ms |
| pinned WASIX libc + Wasmer7.4.2 | 5/5 timeout、1001.509–1007.173ms | 5/5 signal復帰、0.016–3.840ms |

Wasmer縮約のimportsに `futex_wait/wake/wake_all`、`wasi.thread-spawn`、`clock_time_get`、shared memoryを確認。
nativeでも「stale targetを再確認せずwait」なら同じtimeout経路を取る。
conditionはspurious wakeを許すため、すべての合法実装で必ず1秒になるという一般保証ではない。
既存production MariaDBのwire対照30回は500ms超0/30だったが、同じraceが不可能な証拠にはならない。
Wasmer production MariaDB内のpage-cleaner traceやnative MariaDB全体の発生率比較は行っていない。
実装sourceとこの縮約は、Wasmerにfuture notificationを保持する別契約がないことを支持する。
**legacy MariaDB artifactそのもののWasmer7.4.2 cross-runtime検証不可という制限は維持**した。
縮約のnew EHを製品・legacy guestのbuild設定へ反映していない。

### Shim audit / deterministic checks

監査対象は既存 `execution-driver.go.txt` のhost adapterと、同じgenerated moduleの `base.AtomicWait/AtomicNotify`。
productionと同じWasmer7.4.2 `lib/wasix/src/syscalls/wasix/futex_wait.rs` / `futex_wake.rs` の実コードも確認した。
Wasmerはpollerをqueueに登録してからwordを比較し、mismatchは `Success + woken=true`、timeoutはfalse。
empty wakeの返却boolはdoc commentと異なり実コードではtrueだが、未来へのwake保存はしない。

| check | generated-Go behavior / finding |
| --- | --- |
| compare timing / registration | `parkMu` 保持中にatomic loadでexpected比較し、同じcritical sectionでqueueへ登録。wakeも同じlockを取得し、比較→登録間のwake消失を防ぐ |
| wake-before-wait | empty notifyはqueueを変えずpermitなし。word変更後のwaitはrc=1で即時復帰、WASIX adapterはwoken=trueへ変換 |
| count | wakeは最大count個のchannelを閉じてqueueから除去。WASIX wake=1、wake_all=全対象、count=0はqueueを変えない |
| timeout | relative nsをGo durationへ渡し、rc=2をwoken=falseへ変換。timeout時は同じlockでqueueから除去。既存generatorの+1msは残るが約1秒を作る原因ではない |
| lock order / visibility | predicate loadはGo atomic、parking queueは共通mutex。guestのsignal側barrier更新はwakeに先行する。対象traceと縮約で値変更の即時検出を確認 |

新しい [actual-host test](spikes/wasm2go/futex-host-contract-test.go.txt) はfull-guestの独立moduleで
**実際のhost methods**を呼び、empty wake→未変更barrierの合法timeoutと、barrier変更→wake→後続waitの即時復帰を決定的に検証した。現行shimのままPASS。
既存base縮約も未計装moduleで `go test -race` 再実行しPASS：100回の比較/登録boundary順序、mismatch、wake-count、
condition先行signal（1.001531s timeout）/登録後signal（4.042µs復帰）。
これはfaulty shimに対するbefore-fail/after-pass testではない。**bugを発見しなかったためfixを作っていない。**
race detector成功は縮約の範囲だけであり、full guestのunsafe-memory concurrency全体の正当性証明ではない。
zero-timeout、timerの+1ms、同時timeout/wake、signals/cancellation、異常終了等の未監査契約は残る。
その不確実性を今回のempty-list signalの原因と混同しない。

### Latency / correctness / result

同期変更なしのため、200回の「修正後」startupやmemory/CPU再benchmarkは実施していない。
従来の全sampleを残し、改善前後と呼び替えない。直近の既存100回測定値：

| boundary / metric | min | p50 | p90 | p95 | p99 | max | ≥500ms / ≥900ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| direct ready (ms) | 25.5 | 40.3 | 53.7 | 1042.3 | 1054.1 | 1055.6 | 6/100 / 6/100 |
| direct first SQL (ms) | 29.9 | 45.5 | 59.3 | 1046.7 | 1065.6 | 1068.0 | 6/100 / 6/100 |
| wire + verification ready (ms) | 84.1 | 94.7 | 1105.8 | 1113.2 | 1119.4 | 1127.4 | 32/100 / 32/100 |
| wire + verification SQL (ms) | 88.3 | 99.3 | 1117.5 | 1122.4 | 1131.0 | 1136.7 | 32/100 / 32/100 |

direct最初の100回は≥500ms 4/100、≥900ms 3/100。別の613.8ms初回と、計装初回の外側1.124s/trace内52.6msは
未帰属のまま維持。上表の高quantileは反復するpage-cleaner群の影響を受けるが、全tailを同一原因と断定しない。
新しいstartup sampleを追加しておらず、これらを改善・除外・再分類していない。
既存direct ready RSS約107.4MiB、×16 RSS107.8MiB/DB / footprint88.0MiB/DB、wire total CPU0.1092s
（Wasmer対照0.3016s）は前節の探索値を参照する。今回のnative reductionの1秒はperformance比較値ではない。

今回も生成Goのready/SELECT 1、CRUD、COMMIT/ROLLBACK、4種errors/constraints、2 sessions、正常終了の
22-record workloadを再実行して成功、auth self-test成功。
通常checkはGo unit/vet、Python **368 passed / 3 skipped**、public source **349 files**成功。
通常Wasmer integrationは最初sandboxのlocalhost bindで失敗し、制限外で同じコマンドを再実行して
Go race integration **9.022s**、Python **3 passed (2.33s)** 成功。
利用者の未追跡npm filesはsource check中だけ退避し、元SHA256で復元。
生成/test `.go` は独立go.mod内、tracked Go templateは `.go.txt`、Cもspike内に分離。`git diff --check` 成功。

**Tail result: TAIL GUEST-SIDE — NO FIX**。観測順序ではtimeoutが合法であり、shim bugは見つからなかった。
sticky wake、timeout短縮、InnoDB patchを導入しない。
**Overall feasibility: GREEN CANDIDATE — TAIL UNDERSTOOD** を維持する。
median/CPU/memoryのarchitecture signalは残るが、tailは残り、production-readyでもp95改善達成でもない。
残るruntime-contract/trust/lifecycle課題、CoW/runtime-sharingとの比較未実施という範囲も変わらない。
