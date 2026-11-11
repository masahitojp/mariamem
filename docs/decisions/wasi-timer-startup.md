# WASI SQL timing and startup calibration

On 2026-11-11 the Human approved the adoption recommendation for reviewed
evidence `d24087eedd21c6384c231fb119c8e98da7b370aa`.
Assemble a minimal product candidate from main, with two separable changes:

1. For WASI SQL execution tracking, use the existing microsecond read and its
   matching frequency together. The prior generated cycle path reported zero
   time for delayed ANALYZE queries. Do not change global cycle selection,
   random generation, the Go clock shim or InnoDB timekeeping.
2. Only for WASI/no-PFS/monotonic-clock_gettime/no-runtime-cycles, omit the
   millisecond-resolution busy probe and record nominal1ms resolution. This is
   an integer unit, not a host/scheduler precision guarantee. Preserve discovery,
   initial-zero behavior, frequencies, overhead, actual reads and other profiles.

Evidence: [Mac paired startup and whole-suite comparison](https://github.com/masahitojp/mariamem/blob/d24087eedd21c6384c231fb119c8e98da7b370aa/docs/reviews/timer-calibration-measure/README.md),
[Ubuntu/native receipt](https://github.com/masahitojp/mariamem/blob/d24087eedd21c6384c231fb119c8e98da7b370aa/docs/reviews/timer-calibration-measure/ci-42940198738/README.md).
The observed Mac Fresh/Fork medians improve20.794→18.847ms and18.555→16.776ms
in all six pairs. Whole-shop acceleration and regression-free behavior remain
unestablished: P4 median+1.13%, P8+16.39%, with all slow samples retained.
The Human accepts this limitation when proceeding with the startup candidate;
do not claim an end-to-end improvement. Ubuntu evidence establishes bounded
correctness, not a paired performance gain.

Implementation must move the source patch to its canonical owner, preserve
source-unit mutation controls and real SQL time-reporting oracles in normal
verification, and regenerate/bind the resulting runtime and provenance.
Experimental history and development-only binding exceptions are not merged.
UCA/collation work stays separate.

Candidate implementation is authorized. Main integration, Qualification,
version changes and publication remain separate decisions. Successful prototype
receipts retain their original sources and do not certify the new candidate.
