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
