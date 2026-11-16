# Matched official modelcase after async Close adoption

Product6558ee8fb2211313a8aa0ea6070ac5256767811a (PR217 merge).
PG official main3433a40bd4167daea2d8e364666bd5fcf18ef654.
Official70tests,50sharedread/20writerFork,40sampleorders,20categories/500products/
1000users. Prior matched harness from experiment/modelcase-post-memoryea.
Official PG read/write tests byte-identical; store.go differs only revenue selector.
Both readers use a post-Snapshot Fork. Maria default interpolation/inprocess,
PG pgx/nativewire. Both SUM triggers and audit retained. Maria UPDATE OF status,
REVENUE_PREAGG=1 both, semantic control before timings. MaxForks16 both; shared
reader consumes1, leaving spare capacity at P1/P4/P8. Modes maria-sync,
maria-async (public CloseAsync, final allhandle Wait/Disposed included),pg.
One Maria binary for both modes. SQL disconnect awaited in both Maria modes.
One warmup+5measured runs/arm/P, cyclically rotate3armorder each repetition.
54suiteprocesses,3,780testbodies,1,080writerForks. Semantics are separate smoke.
Go1.27.4 both (same as prior matched campaign; not product compiler acceptance).
GOMAXPROCS8/GOGC100/CGO0. Builds finish before timings. No concurrent benchmark.
Suite elapsed trace includes final drain; external process wall also reported.
Preserve perphase p50/sums, CPU and process peakRSS, all raw spans/logs. No
repetitions added/excluded. SharedMac finite cohort, not website-number rerun.
Prior69second observation remains unresolved; recurrence triggers Issue recording.
14GiB budget/free14GiB timeout2400. Build/source identity before compilation;
full raw evidence separate experimentref, main gets compact approved state only.
