# Issue100: common-variable initialization calls

**The final charset/collation and remaining setup interval dominates: 14.923ms of common-variable initialization 15.587ms.** Options/version/UID handling (0.096ms) and SQL/JSON registration (0.275ms) are small in this fixed profile.

Recommendation: next separate charset lookup/one-time charset registration from the rest of this tail. Do not yet change charset support, cache or clone initialized state. This result narrows the next observation; it does not identify a removable15ms function. The strongest limitation is that the final interval includes filesystem case probing, path/log defaults and other setup as well as charsets. Those must be separated before assigning the time to charset tables.

## Inputs and fixed plan

- Product source_commit `bc00b8e66e5fd57bc9b2127001faf8e05952b417`, same historical product pin as [the preceding split](https://github.com/masahitojp/mariamem/blob/dfc84f98c31e7584d2c43bcd923af691f993d60c/benchmarks/common-init.md). Not latest-main identity.
- Actual binary harness source_commit `91009bc6e4572993eeded2672dc1b2ae5312da49`. Commit-object and clean-tree checks precede build; VCS stamp checked after build. Only benchmarks/commoncalls files differ from the product base when built.
- Guest SHA256 `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`; no guest rebuild, configuration/control-flow or product/API change.
- M1/16GiB/macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,TCP,1000 integer rows, explicit cap1. Root captured and closed before four sequential children/process. Seed COUNT/SUM, independent updates, subsequent SELECT and cleanup checked.
- Three alternating fresh-process pairs: callbacks off/on,on/off,off/on. Four children/process; separate one warmup process/mode, four-child positive pilot and one-child wrong-seed negative. No extra primary repeats or exclusions.
- Same binary, full existing guest initialization diagnostics on in both modes; eleven conditional Go callbacks off/on (the previous five plus six new). Explicit init_diagnostics=true and common_init_marks distinguish these controls.

## Measured intervals

Medians of three process medians, each over four children. These are host-monotonic wall intervals in the generated guest execution. Guest timing has a separate origin; subtract only within one clock. Separately aggregated medians need not sum exactly.

| Common-variable stage, callbacks on | ms |
| --- | ---: |
| Global/thread/locale setup | 0.258 |
| Status registration | 0.003 |
| Options + server version/UID | 0.096 |
| Limits/autosize + locale lookup | 0.014 |
| Error messages | 0.018 |
| Client/SQL/JSON registration | 0.275 |
| Charset/collation and remaining tail | 14.923 |
| Common-variable total | 15.587 |

The final interval's three process medians are 14.640, 15.083, 14.923ms. It is consistently the largest in this small cohort. Timer calibration outside common-variable initialization is 0.771ms; common total 16.660ms. Do not combine this cohort with earlier medians into a new total.

| Enclosing/calibration metric | Callbacks off | Callbacks on |
| --- | ---: | ---: |
| Guest common interval, ms | 16.479 | 16.661 |
| Guest server_init, ms | 31.832 | 32.812 |
| Public Fork wall, ms | 36.242 | 37.779 |
| Public Fork process CPU, ms | 49.310 | 51.144 |

Paired Fork-wall differences -2.31%, +5.30%, +4.50% show measurement/scheduling variability. This is not a speedup/regression experiment. Stage CPU counters remain unavailable (`null`), not zero. RSS, P4 inflation and full-suite speedup are unmeasured.

## Exact mapping and remaining cause

The previous static marker/data-base mapping identifies `p0.Fn5572`; C calls are inlined, so this is generated-block/source correspondence rather than DWARF symbol resolution. Six new exact sites:

| Callback | Generated boundary | Scope |
| --- | --- | --- |
| status_begin | before Fn15260(status_vars) | end globals/thread/locale defaults |
| options_begin | L2004 | status success before get_options all_options setup |
| options_version_uid_end | L2487 | after options/version/UID, before unknown fallback store |
| error_messages_begin | L2675 | after locale lookup, before init_errmessage work |
| sql_registration_begin | before Fn5810 | errors assigned, before init_client_errs |
| charset_begin | L2833 | after SQL/JSON registration, before old-mode warnings/charset work |

Each match must occur exactly once inside this function; before/after hashes and actual edits are in [inputs](commoncalls/results/inputs.json), with [selected spans and mapping scope](commoncalls/results/mapping.json). No guest branches, memory writes, result handling or options are changed. The options bin includes version/UID work, not just parsing; the limits bin includes autosizing/unireg/locale lookup.

[init_common_variables source](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/mysqld.cc#L4097) shows that the last interval also contains default charset/collation/filesystem charset/time locale, log/path defaults, DB-options-cache initialization and a filesystem case-sensitivity probe. It cannot be called pure charset initialization time.

A source-level candidate exists: [get_charset_by_csname](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L1029) reaches my_charset_get_by_name, which invokes once(init_available_charsets). [That initializer](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L704) registers compiled charsets, initializes state maps and reads the charset index. These are source facts, not measured attribution: this cohort does not prove the initializer is first triggered there, takes14.9ms, or is safely reusable. See [source hashes](commoncalls/results/source-audit.json).

## Controls, reproduction and lifecycle

All24 primary,8 warmup and4 positive-pilot children pass SQL/isolation/cleanup. Negative detects the wrong seed and cleans up. All37 children have zero dropped init records and complete expected callback sequences. All10 processes finish with zero active mappings/RW/reserve and release failures. Three reducer mutations reject missing boundary, dropped record and hidden cleanup leak. A sandbox dependency-download failure occurred before build/pilot; no primary trial was discarded.

Read-only recheck after deleting all temp/build output:

```sh
python3 benchmarks/commoncalls/analyze.py benchmarks/commoncalls/results --check benchmarks/commoncalls/results/summary.json
```

The check also verifies SHA256SUMS.json and the three rejection controls. [compact.json](commoncalls/results/compact.json) losslessly preserves all10 process records and6216 initialization events; decode equality to each original JSON was checked. [Summary](commoncalls/results/summary.json) retains per-child intervals, process medians and aggregate medians. [Publication](commoncalls/results/publication.json) records raw hashes and normalization of only the workspace prefix in inputs build-info. Timing/identity hashes are not rewritten.

To re-execute: clean clone the product pin into a disposable workspace temp/source; copy and commit benchmarks/commoncalls; set MARIAMEM_EXPERIMENT_TEMP to that workspace temp directory (with sibling evidence); run its run.py --phase build, pilot, measure. The build checks benchmark-only diff, commit identity and Go1.27.3 binary stamp, then records the new harness identity rather than relabelling historical evidence. Source/guest pins and overlay hashes are in inputs.json.

Owned scratch is disposable after preserving this branch, compact evidence and history. The final cleanup receipt and post-cleanup read-only check are recorded in #100. No product adoption, main integration, CI or release is performed. #103 reusable-state design remains unproven; the bounded next question is charset lookup versus remaining tail.
