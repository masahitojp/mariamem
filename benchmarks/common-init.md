# Fork common initialization: Issue100

The early common interval is dominated by **init_common_variables(): 15.232ms**. Timer calibration is 1.721ms, not the whole earlier ~17ms. This narrows #100 to a concrete next function. It does not establish that its work can safely be omitted, cached or cloned.

Recommendation: split that function into a few major calls in a separate bounded observation before designing reusable initialized state (#103). #84 prewarming moves individual child work ahead of demand; #103 would attempt to remove repeated work. Neither is implemented here. #101 parallel-stage attribution remains separate.

## Fixed inputs and method

- Product source_commit `bc00b8e66e5fd57bc9b2127001faf8e05952b417`, same as the preceding full-suite/deep-init reports. This is a historical measurement pin, not latest-main identity.
- Actual clean harness/binary source_commit `9c601ab7e15920048ac3db5ce4ab9840397c001b`. Commit-object/clean-tree checks precede build; binary VCS stamp checked afterward.
- Guest SHA256 `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`, identical between modes. No guest rebuild, engine/configuration or product patch.
- M1/16GiB/macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,TCP,1000 integer rows, explicit cap1. Root captured/closed before four sequential children; each verifies seed and independent mutation, then retires/closes.
- Three alternating fresh-process pairs (off/on,on/off,off/on), four children/process. Separate one warmup process/mode, positive four-child pilot and wrong-seed one-child negative. No primary exclusion or extra repeat.
- Same binary, existing startup AND full guest initialization diagnostics enabled in both modes; five new Go boundary callbacks off/on. The legacy runner field `init_diagnostics` misleadingly follows the off/on label: here it denotes new callbacks, not actual guest diagnostics. The reducer checks actual arrays in both modes; original flags remain preserved and disclosed in publication.json.

## Results

Values are medians of three process medians, each over four children. Guest/host monotonic origins differ: only subtract within a clock. Separately aggregated medians need not sum exactly.

| Host-observed interval, callbacks on | ms |
| --- | ---: |
| Preparation before timer | 0.216 |
| my_timer_init (inlined) | 1.721 |
| init_common_variables (inlined) | 15.232 |
| Trailing data-home/TMPDIR setup | 0.001 |
| Common total | 17.184 |

| Calibration/enclosing interval | Callbacks off | Callbacks on |
| --- | ---: | ---: |
| Guest common, ms | 17.349 | 17.186 |
| Guest server_init, ms | 33.147 | 32.486 |
| Public Fork wall, ms | 38.009 | 36.915 |
| Public Fork process CPU, ms | 51.986 | 51.384 |

Paired Fork-wall changes: +6.72%, -8.03%, -2.88%. Sometimes-faster callbacks reflect scheduling/cohort variability, not optimization or negative overhead. Guest stage CPU counters are unavailable (`null`): this does not isolate CPU from waits, predict removable time, measure P4 inflation or establish suite speedup. No RSS/resource qualification is claimed.

## Boundary correspondence

Exact generated function `p0.Fn5572` contains the inlined C work. This is not a function-name/DWARF lookup. Decoding committed static bytes and checking the8388608 initialization base places embedded_begin at175269+8388608 and embedded_options_complete at231433+8388608; both marker calls occur in this function.

L64 starts timer-info initialization at23871104. L1466 restores its stack and zeroes the six connection-error counters, followed by decimal/type setup, matching init_common_variables. L1826 is its successful completion before mysql_data_home and TMPDIR getenv. Five conditional observer calls are inserted only into that function, with exact replacement-count assertions and before/after hashes. Existing control flow and guest writes are preserved.

See [mapping](commoninit/results/mapping.json), [selected generated spans](commoninit/results/generated-mapping-spans.json), [overlay](commoninit/overlay.py), [source hashes](commoninit/results/source-audit.json):

- [init_embedded_server](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L532)
- [my_timer_init](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/my_rdtsc.c#L363)
- [init_common_variables](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/mysqld.cc#L4097)

Common-variable setup includes thread/global variables, locale, option handling, status/SQL registrations and other setup. No individual call inside its15ms is measured. Neither timer calibration as main cause nor safe reuse of all common state is established.

## Controls and retained evidence

All24 primary,8 warmup and4 positive-pilot children passed SQL/isolation/cleanup. Negative detects wrong seed and cleans up. All37 children have complete expected observations and zero dropped init records. All10 processes finish with zero active mapping/RW/reserve and release failures. Reducer mutations reject missing boundary, dropped observation and hidden cleanup leak.

Initial sandbox network/TCP failures preceded primary measurement; failed TCP pilot created no child. Compact failures and other setup corrections are in [assessment](commoninit/results/assessment.json). Permission waits are outside measurement; no guest rebuild/CI used.

Read-only recheck after deleting all temp/build output:

```sh
python3 benchmarks/commoninit/analyze.py benchmarks/commoninit/results --check benchmarks/commoninit/results/summary.json
```

[compact.json](commoninit/results/compact.json) losslessly retains all child/process records and6216 initialization events (column encoding). Decoded equality to all10 original JSONs was checked. [Summary](commoninit/results/summary.json) keeps each child interval and process median. [Inputs](commoninit/results/inputs.json) pin source/binary/guest/toolchain/overlay; [publication](commoninit/results/publication.json) records original/published input hashes and workspace-prefix normalization. SHA256SUMS.json binds result files.

To re-execute, check out the pinned product source; copy and commit this benchmarks/commoninit harness; set MARIAMEM_EXPERIMENT_TEMP to a disposable workspace temp directory containing a clean source clone and sibling evidence directory. Run its run.py --phase build, then pilot, then measure. Go1.27.3 and the committed overlay generator are used. New execution records its own harness/binary stamp instead of relabelling historical evidence. Existing full init diagnostics intentionally remain enabled in both modes.

No optimization, initialized-state clone, main integration or release is adopted. Next question: which calls inside init_common_variables dominate, and do they admit a safe local change?
