# v0.4.3 Human Review

## Executive summary

- 共通 baseline は `fa6ef5355ecb93f7e1cabbedf5caa74fe4210870`。A/B は独立し、main へ未統合。
- A は Wasmer の実行・取得・キャッシュ・旧専用 gate を退役。生成 guest と memory32/mmap は変更しない。
- 歴史資料、互換エラー用の引数、生成に必要な WASIX/toolchain は残す。Wasmer エンジンは製品依存から外す。
- B は macOS arm64 の 56 ケースを実測。既存 prepared files は既に `MAP_PRIVATE`。
- virtual/RSS は増えるが、準備済み全データの子ごとの eager private copy は支持されない。
- minimal Fork 115 ms のうち integrity validation が 61 ms。InnoDB open/recovery は別診断で約 7 ms。
- 合成 fixture の crossover は 10 MiB で N2–N4 の間、100 MiB で N1–N2 の間。軽いテストは Fresh が有利。
- 推薦は A の退役、既存共有の維持、fixture に応じた Fresh/Fork の選択。新 CoW や v0.4.4 は今は設けない。

## Human Review

### Decision 1 -- Track A を merge してよいか？

Recommended decision: 通常の PR CI 通過を条件に Track A の Wasmer 退役を merge する。

Why: 現行の Go/Python 製品経路の Wasmer engine 依存はゼロ。生成 guest・WASM identity・canonical pins・memory32/mmap 実装は byte-identical。Go tests/vet、Python285件、SQL/session/Snapshot/Fork/ownership/race、installed wheel、SQLAlchemy44件・GORM32件が通過。各3試行の sanity 中央値は Start 53.05→53.80 ms、Fork 118.71→121.75 ms。

Alternative: 明示的 Wasmer fallback を次の guest upgrade まで維持する。

What we lose if we choose the recommendation: NativeDir や Python runtime/module/wasmer_dir を指定する利用者は、その指定を除くか旧リリースに固定する必要がある。現行ブランチで旧エンジンを比較実行する経路もなくなる。

Human needs to decide: この legacy-only 入力の退役を受け入れ、通常 CI 成功後に A を merge するか？ Yes / No。

### Decision 2 -- prepared-state 共有のために新 CoW が必要か？

Recommended decision: 現在の file-backed `MAP_PRIVATE` 共有を維持し、新 CoW/MAP_PRIVATE 改造へ投資しない。

Why: 実 prepared size 138/157/262 MiB に対し、16 children の live Go heap はいずれも約 198 MiB。snapshot 後の physical delta は約 1188–1261 MiB で、全 prepared bytes × children の private copy を支持しない。100 MiB の全 payload CRC scan も成功し、FD は Close 後に 6 へ戻った。virtual/RSS の増幅は実在し、100 MiB ×16 の RSS delta は約 3180 MiB（minimal 約 1319 MiB）。

Alternative: 重い書き込み・ファイル capacity 超過を対象に、限定した追加 resource-scaling 調査を先に行う。

What we lose if we choose the recommendation: capacity 超過時の `make + copy` と、各 MariaDB の private buffer pool/dirty pages の費用は残る。今回の少量更新だけでは、巨大更新や無制限 concurrency の資源保証は得られない。

Human needs to decide: 今回の用途範囲では共有は十分と判断し、新 CoW を見送るか？ Yes / No。

### Decision 3 -- Fork latency を今すぐ最適化するか？

Recommended decision: 今は最適化せず、将来の候補を integrity-preserving validation の改善に絞って記録する。

Why: minimal ready 115.10 ms 中、snapshot validation は 61.18 ms（約 53%）、prepared mapping と linear setup は計 2.33 ms。100 MiB では validation 126.39/202.30 ms（約 62%）で size dependence がある。ゲスト全体は minimal 約 34–35 ms、別診断の InnoDB open/recovery は 6.8–7.1 ms。「安全に除去可能な割合」は未証明であり、必須検証を削れば速くなるという提案ではない。

Alternative: integrity/ownership 契約を保つ検証設計を先に立証する、小さい Fork-latency 作業を v0.4.4 に設定する。

What we lose if we choose the recommendation: 少量 fixture の Fork は Fresh より遅いままで、parallel Fork の read/hash CPU も残る。測定された host 費用を減らせる可能性をすぐには追わない。

Human needs to decide: 現時点では Fork 最適化を延期するか？ Yes / No。

### Decision 4 -- Fresh と Snapshot/Fork をどう位置づけるか？

Recommended decision: 軽いテストは Fresh、繰り返す重い準備は Snapshot/Fork と案内し、fixture の準備コストで選ぶ。

Why: minimal は N16 でも Fresh 1.196 s / Fork 2.476 s。10 MiB は N2 で Fresh 優位、N4 で Fork 優位、N16 は 10.271 / 3.755 s。100 MiB は N2 から Fork 優位、N16 は 96.036 / 14.274 s（約 6.7 倍）。いずれも prepare/Snapshot/test/Close を含む実スイートで、準備費用を除いた microbenchmark ではない。

Alternative: Fresh のみを基本導線にし、Snapshot/Fork は大きい fixture の上級機能に留める。

What we lose if we choose the recommendation: 利用者には二つの lifecycle と Snapshot handle の管理を理解する負担が残る。合成 fixture の MiB や N を実アプリの普遍的な閾値として使うことはできない。

Human needs to decide: fixture 準備の amortization を Snapshot/Fork の主な価値として案内するか？ Yes / No。

### Decision 5 -- v0.4.4 を設けるか？

Recommended decision: no 0.4.4; proceed to v0.5。A の consolidation 後に stable guest へ進む。

Why: 既存共有には新 CoW を必要とする eager-copy の根拠がなく、56 ケースは予算内で正常終了した。重い準備では現状でも N16 の suite が約 2.7–6.7 倍改善する。Fork の主な追加費用は必須 validation で、一般的な安全な削減方法は今回立証していない。

Alternative: 0.4.4 Fork-latency work を設け、validation identity/ownership の成立性だけを bounded に調べる。

What we lose if we choose the recommendation: 現 guest で Fork の latency/CPU をさらに下げる機会は後回しになり、guest upgrade 後には性能の再測定が必要になる。

Human needs to decide: A の統合後は v0.4.4 を設けず v0.5 へ進むか？ Yes / No。

## Appendix A — Track identities / merge safety

| Item | Identity / state |
| --- | --- |
| Common baseline | `fa6ef5355ecb93f7e1cabbedf5caa74fe4210870` — updated origin/main |
| Track A | `experiment/v043-wasmer-retirement` — `6ea2bcf0d0106b6f821109c50b417b819b65f1b6` |
| Track B branch | `experiment/v043-snapshot-characterization` — 後続の doc-only commit にこの packet を収録 |
| Track B measurement commit | `cc24747bac4a1e2b9d05dd008bf76d1e987749ec` |
| Main | 未変更。A/B 未統合、tag/publication なし |

両ブランチに既知の merge-blocking 不具合は見つかっていない。A の legacy-only
入力廃止は明示的な互換性判断であり、通常 PR CI と Human Review を残す。
検証結果は Release READY と区別する。今回、新しい Ubuntu/macOS immutable
artifacts の Release CI acceptance と fresh GPL source closure rebuild は実行しておらず、
後のリリースでは必須。
B は opt-in handwritten instrumentation、benchmark、evidence/report の変更であり、
Fork/Snapshot/memory architecture を変える候補ではない。

A の実装は core product +85/-1073行、rename-aware 全体127 files +1193/-3806行。
15 Python fixture files/2 Go fixtures と3旧workflowを現行 gate から外し、共有 provenance・
module/artifact/hash・publication の deterministic gates は現行に残す。
local wheel の hash/Mach-O/20 distributed notice texts と root license files が検証済み。
sanity CPU 中央値は Start 61.84→67.28 ms、Fork 136.97→138.93 ms。
初回 Start 66.61→87.82 ms を含む3試行であり、性能同等性や tail 改善は主張しない。

[Track A inventory / acceptance / sanity report](https://github.com/masahitojp/mariamem/blob/6ea2bcf0d0106b6f821109c50b417b819b65f1b6/benchmarks/v043-wasmer-retirement.md)
と [compact Track A evidence](https://github.com/masahitojp/mariamem/tree/6ea2bcf0d0106b6f821109c50b417b819b65f1b6/benchmarks/v043-retirement-evidence)
が詳細を保持する。Source/build/release dry-run は現行 deterministic guard tests、public-source
check、local wheel build/notices の範囲であり、新しい両 platform の immutable artifact READY ではない。

### Wasmer inventory の要約

| Category | Treatment | Current runtime dependency? |
| --- | --- | --- |
| NativeDir selection / resolver / bundle cache | 実行経路を除去。Go field は deprecated error tombstone | No |
| Wasmer executable startup / subprocess kill | 除去 | No |
| Legacy native/AOT packaging / dedicated CI | 退役。現行 CLI は拒否、workflow は旧タグに保存 | No |
| Legacy tests / reports / license texts / pins | historical/reference。通常 gate から除外 | No |
| WASIX libc/sysroot / LLVM runtime / GPL guest source / converter | 生成とライセンスのため保持 | Yes — generated-Go tooling、Wasmer engine ではない |
| Current consumer / source / artifact/hash / release guards | 保持、共有 helper は現行へ分離 | Yes |

## Appendix B — Supporting measurements

| Additional payload | Actual prepared | Single Fork ready | Validation | Guest enter → ready |
| --- | --- | --- | --- | --- |
| minimal | 138.08 MiB | 115.10 ms | 61.18 ms | 33.65 ms |
| 10 MiB | 157.02 MiB | 125.22 ms | 70.19 ms | 35.74 ms |
| 100 MiB | 262.02 MiB | 202.30 ms | 126.39 ms | 49.83 ms |

| Fixture | Suite N | Fresh | Snapshot/Fork |
| --- | --- | --- | --- |
| minimal | 16 | 1.196 s | 2.476 s |
| 10 MiB | 2 / 4 / 16 | 1.275 / 2.539 / 10.271 s | 1.356 / 1.742 / 3.755 s |
| 100 MiB | 2 / 4 / 16 | 11.495 / 23.364 / 96.036 s | 7.193 / 8.198 / 14.274 s |

Source trace: Snapshot は guest MemFS から disk prepared files へコピーし、Fork は
inventory/hash validation の後に file-backed private mappings と独立した runtime を作る。
既存 capacity 内の writes は private pages、capacity 超過はそのファイルの Go copy。
新しい CoW、mapping flag 変更、ready-heap/runtime snapshotting は行っていない。

全表・CPU/Close/heap/OS/FD/goroutine 値は
[Track B report](../benchmarks/v043-snapshot-characterization.md)、
[compact measurements](../benchmarks/v043-snapshot-characterization-values.json)、
[raw checksums](../benchmarks/v043-snapshot-characterization-checksums.txt)、
[reusable harness](../benchmarks/snapshotcharacterization/README.md) を参照。

## Appendix C — Limits / experiment ownership

測定環境は macOS 27.0.1 arm64 / Go1.26.8、16 GiB RAM。Linux の性能は未測定。
1 cell / combination と少数 replica の bounded characterization であり、canonical
benchmark、実アプリ一般の crossover、大規模更新の保証ではない。
Fresh→Fork の固定測定順、診断 GC、OS allocator/page-cache 履歴も比較の限界。
physical delta は各 process の post-prepare checkpoint 差で、専有 DB bytes ではない。

各 track disk budget は 4 GiB、minimum free は 12 GiB。B は RSS/physical 8 GiB
ceiling を 250 ms ごとに監視し、違反なし。最大 checkpoint は RSS 4.09 GiB /
physical 2.11 GiB。continuous peak は未保存で、kernel hard cap ではない。
性能測定は一方だけが実行し、他方の compile/tests を停止した。
reports/compact JSON/checksums/unique traces は保持し、成功した temp binaries と
owned worktrees は終了後に Git worktree commands で整理する。共有 cache と未知の旧残骸は保持。
レビュー用の原本コピーと final branch identities/cleanup receipt は
`publish/mariamem/build/v043-review/` に保持する。

memory64、非協調 root/worker の強制終了、全 guest race、MariaDB upgrade は今回の対象外。
AI/review 効率の改善は、今回の性能数値だけでは実証していない。
