# Buffer-zero canonical candidate CI — PASS

[Run43569024494](https://github.com/masahitojp/mariamem/actions/runs/43569024494)
passed for exact source_commit `2e1ecd315e4f85d5a7112112ad0858e8dc6765de`, operation
`canonical`. Guest, native reference, macOS15 arm64 and Ubuntu24.04 x86_64 jobs
succeeded. The installed-distribution and public-only operation jobs were
inapplicable and skipped; this is not release Qualification.

Both native receipts record two matching independent C builds of guest
`77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`, linked guest
`267763a3a8fab4896a77cc15d3006318b5a61fc49f403d2d3c6c2109852545fc`.
All120 generated inventory files match each other and the checked-in candidate.
Source/translation/input/build-guard and negative controls passed, as did full
CRC validation, actual dictionary/UCA/lexer/worker regressions and worker
ownership controls. Native normal/binary SQL, SQL timer, Snapshot and cleanup
controls passed.

Normal check and full integration passed on both platforms with Go1.26.10.
Each check reports1915 Python tests plus119 subtests and8 native-C tests.
Integration retains exact accepted consumer failures as tripwires rather than
turning them into unconditional functional PASS.

Basic, 32MiB normal/COMPRESSED tables, resize9→11→16MiB, two isolated Forks,
EIO and clean/dirty redo all passed on both OSes. The repaired fault fixture
exceeds the16MiB pool and checks full payload CRC. Both paths hit exactly once;
`.ibd` hits at Ready0, `ibdata1` hits at Ready1, correct recovered data, healthy
siblings and Close all pass. Redo observer counts are clean0/0 and dirty1/1.
The previous macOS hits0 failure remains in its original report.

`assessment.json` records original ZIP digests. Each platform's
`normalization.json` binds original and saved file hashes: CI runner-home
prefixes are replaced with `${CI_HOME}`, `.log` files are saved as `.txt`, and trailing line whitespace is stripped.
The source archive's SHA256SUMS was verified before normalization. These are
historical receipts, not inputs relabeled to the later integration branch.
No new runtime build, benchmark, main merge, issue closure or release follows
from saving these results. See the [integration review](../buffer-zero-main-review.md).
