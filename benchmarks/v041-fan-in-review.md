# Post-v0.4.0 independent investigations: fan-in review

## Boundary

共通 baseline は公開済み **`v0.4.0` / 39537e9bb2fbbc28315e1ff672960ad734a9e399**。
5 lane とこの review branch はその同一 SHA から分岐した。相互 merge/cherry-pick、
main/integration への統合、製品 runtime 変更、v0.5 作業はない。

Apple M1 / 16 GiB / macOS27.0.1 arm64 / Go1.26.8。
解析と harness 作成は並行し、重い build と全計測は同一 exclusive lock で直列化した。
[manifest](v041-fanout-manifest.json) は全 branch SHA、証拠 checksum、非重複 lock
session、共通 guest identity と diagnostic-only diff を記録する。
canonical performance campaign は再実行していない。known full-guest race、forced
reclamation、macOS accounting limitation は変更も解消もしていない。

## Fan-in

| Lane | Finding | Product impact | Fix cost | Dependency | Recommendation |
| --- | --- | --- | --- | --- | --- |
| A Disposable soak | 16×50 は達成できず。独立2試行が3/2世代で事前の12GiB footprint-accounting予算に達した。計80DBはSQL/rollback/Close成功、FD7/goroutine1で一定。ready/CPUは両方悪化。 | この参照環境・予算では Cheap to reclaim / 世代plateauをまだ主張できない。 | 未確定。次は限定した原因 attribution、修正選択はその後。 | 同一consumerの allocator/guest reservation とOS accounting。storage案は未選択。 | 資源問題を次のbounded investigationにする。CoW/mmap等へ飛ばない。 |
| B Fixture crossover | 実在する小さいGo fixture/GORM準備では全18組でFreshが安価。重い準備は未測定。 | 現在のGo2 workloadではFork短縮がDisposable採用の前提ではない。 | 修正不要。実利用の重いmigration/fixture収集が必要。 | preparation・言語/host・長寿命consumer boundary。 | まずFreshも含めてproduct validation。広いFork最適化は保留。 |
| C Consumer cost | cold build96–100秒、cold test134秒。warm build0.21–0.38秒。public zip144MiBの77.2%がunused images。 | warm/editは実用的。初回/CI/binary費用と不要な取得物は現実の負担。 | dead image関連のbounded cleanupはsmall–medium。生成source縮小やmodule分割は未選択。 | Eのcaller/provenance audit。 | 不要配布物のcleanupをhuman selection候補にする。 |
| D RSA startup | production sourceとgenerated initial dataの両方で既にOFF。actual plugin callbackと30回public auth/reconnect smoke成功。 | OFFを新たに設定するv0.4.1 benefitはない。 | なし。既存test-key/plugin契約は保持。 | 公開v0.4.0に既に実装済み。 | 新しいruntime変更は不要。stale候補の記述だけ整理する。 |
| E Migration debt | unused encoded-image専用処理、old alpha.2必須CI、重複verification、version固定runner、guard-only temporary-root issueを識別。 | 取得負担とmaintainer/release toilの限定的な削減候補。 | 項目別small–medium。fallback/trust/source coverageを保持。 | caller auditと同等のacceptance/provenance coverage。 | 個別に選択。generic spawn/native resolver/fallbackは削除しない。 |

### Key measurements and applicability

**A:** first valid attempt ready **1.261→5.935 s**, CPU **1.237→6.509 CPU-sec**;
independent repeat **2.059→5.098 s**, CPU **1.780→5.348 CPU-sec**。
最大Close後footprintは **41,419.9 MiB**、同時RSSは **2,702.0 MiB**。
logical HeapAllocは約35,179MiBでほぼ一定、automatic GCは動作。
この2/3世代の結果は実用予算の失敗と初期の実行cost悪化を示すが、無限増加、live
Go leak、OOM、最終的なplateau不存在を証明しない。50世代は未成立。
12GiBは事前設定したaccounting予算でありresident RAMの閾値ではない。
`OS PHYSICAL ACCOUNTING DOMINATES`という既存lifetime findingを維持し、
そのchargeを無害・即回収可能とは主張しない。初回observer-only FD列挙エラーは
DB作成前のtooling failureとして別のraw evidenceに残した。

**B:** 各条件3回、独立suite process。実際の100-test total medianは
1,000-row **Fresh35.136 / Fork41.616 s**、GORM User/Address
**Fresh30.487 / Fork38.336 s**。Snapshot一回準備と最終cleanupも含む。
10/50/100すべてでFreshが安価、1,920 casesがfixture/commit/rollback/isolation/
shutdownに成功。preparation自体は約3–5msで、観測範囲に有限crossoverはない。
同じconsumer内で反復した後のStart/Forkは単発fresh-processより遅い。
このsuite値をcanonical独立startup中央値やSnapshot regressionに置き換えない。
既存installed-Python SQLAlchemy100 **Start34.025 / Fork20.430 s** の価値も保持する。
重いconsumer準備がないため、一般のFork不要という結論にはしない。

**C:** public proxy/sum確認済みの本物のv0.4.0、replaceなし。
zip **143.99 MiB**、展開 **328.15 MiB**、generated source **196.19 MiB**、
module cache logical **472.14 MiB**。cold build独立2回 **96.26/99.85 s**、
independent cold test **133.50 s**。consumer変更build/test **1.44/1.54 s**。
reported maximum process RSS **2.44–2.76 GiB** は同時compiler合計ではない。
binary normal/stripped **81.25/54.47 MiB**、stripped追加分約 **49.84 MiB**。
旧synthetic consumerとのcompile/cache/binary分類は同じで、source sizeだけが
直接リンクを否定する理由にはならない。actual zip中 **111.17 MiB** がunused images。

**D:** source.patchのOFF optionはgenerated dataにも1 occurrence。
30 independent released-OFF processesのStart→SQL **p50 47.47 / p95 1058.40 ms**、
CPU **p50 0.03435 / p95 0.05512 CPU-sec**、≥900msは8/30。
known tailを除外せず、ON counterfactual savingは推計しない。
plugin actual callback PASS / generated=false。focused Python checksは5pass/3skipで、
skipをpassとは扱わない。追加OFF設定が重複という意味でbenefitはzero。

## Human product decision: six answers

1. **Disposable lifecycleは既にbounded enoughか:** この16×50/参照予算では **まだ否**。
   FD/worker cleanupは正常だが、資源/latency plateauを成立させられなかった。
   短い2回のbudget stopから無制限なleakは断定しない。
2. **Fork≈100msはrealistic workloadをmaterially制限するか:** 今回のcheap Go準備では
   **その証拠なし**。Freshが安価でisolated SQLも通る。重いmigrationsは未測定で、
   Python側の既存Fork benefitは別に実証済み。
3. **generated-Go build costはacceptableか:** supported Goでbuild/runは安定し、
   **warm/editは実用的、cold/CI/distributionはpolishが必要**。数GiB compiler process、
   約2分のcold test、約50MiB stripped追加分を明示し、unused imagesを区別する。
4. **RSA disablingをv0.4.1でshipする価値はあるか:** **新しい変更としてはない**。
   既にreleased OFF。plugin/key semanticsと回帰testを維持する。
5. **low-risk migration/toil cleanupは何か:** unused image専用provisioningとimage-only
   verification整理、default CIとexplicit fallback jobの区別、version-aware benchmark
   runner、同一job重複check、guard-only owned temporary-rootの限定fixを候補にする。
   cleanup dry-run/evidenceルールとbenchmark mechanics/skillsは既存scriptに集約する。
   fallback、対応source/notices、final-artifact acceptance、focused regressionsは残す。
6. **v0.4.2 resource/performance projectの証拠は十分か:** **boundedな資源原因調査を
   優先する証拠はある**。まだ特定fixや広いCoW/mmap/storage projectのROI証拠ではない。
   次の一問は同じ長寿命consumerでのreservation/allocator reuseとOS pressureのcost
   attribution。実workloadのproduct validationも継続候補だが、Cheap to reclaimの成功
   を宣言してv0.5へ進む判断はしない。version/project採否はhumanが決める。

A/Bは独立のharnessだが、両方にsame-process反復costが見えるため結果を加算しない。
C/Eは取得物cleanupの判断を補強する。Dの設定は全laneに共通するreleased baselineで、
後付け変更ではない。どのlaneも他laneのcommitを取り込んでいない。

## Branches and evidence

| Lane | Branch | Exact result SHA | Report |
| --- | --- | --- | --- |
| A | `experiment/v041-disposable-soak` | `2fa63fe03e5275c171106e0a578e63f86dfb3644` | [report](https://github.com/masahitojp/mariamem/blob/2fa63fe03e5275c171106e0a578e63f86dfb3644/benchmarks/v041-disposable-soak.md) |
| B | `experiment/v041-fixture-crossover` | `082fada79193db9a593384883c9efac5dd44519d` | [report](https://github.com/masahitojp/mariamem/blob/082fada79193db9a593384883c9efac5dd44519d/benchmarks/v041-fixture-crossover.md) |
| C | `experiment/v041-consumer-cost` | `f414ff346df8d087d0e6d1e21c52399b03b0d1fb` | [report](https://github.com/masahitojp/mariamem/blob/f414ff346df8d087d0e6d1e21c52399b03b0d1fb/benchmarks/v041-consumer-cost.md) |
| D | `experiment/v041-rsa-startup` | `85f6cfe4b5deeff5601d413123b52e12fca26763` | [report](https://github.com/masahitojp/mariamem/blob/85f6cfe4b5deeff5601d413123b52e12fca26763/benchmarks/v041-rsa-startup.md) |
| E | `experiment/v041-migration-debt-audit` | `4635df3d8a06dacc5542b8fa8aec78f2e9c7fe6a` | [report](https://github.com/masahitojp/mariamem/blob/4635df3d8a06dacc5542b8fa8aec78f2e9c7fe6a/benchmarks/v041-migration-debt-audit.md) |

各reportがsmall JSON/CSV、harness、raw checksumをリンクする。
large raw/cache/binariesはowned work rootの `fanout-v041/evidence/soak-run-01..03/`、
`crossover-raw/`、`consumer-measurement-1/`、`rsa-evidence/` に保持し、Gitには入れない。
このreview branchはreport/manifestだけを追加する。全laneのdiffはdiagnostic
`benchmarks/`配下だけ、共通ancestorとcommit非共有、lock非重複、diff-checkを確認。
BのCSVは計測後にCRLF→LFだけを正規化し、全1,920 parsed rowsが同一であることと
元/新checksumを記録した。計測値やtrial選別は変更していない。
normal production acceptance/canonical benchmarkの代替とはしない。

**Stop at HUMAN DECISION.** 選択したcleanup/fixの実装・統合、v0.4.1/v0.4.2準備、
v0.5、CoW/mmapは開始していない。
