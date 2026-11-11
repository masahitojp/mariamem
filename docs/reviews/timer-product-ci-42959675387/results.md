# Canonical candidate result summary

This summary reduces the verified artifact outputs at source
`370231520c373fae05378bddb791c9b6d7fdf84f`. [assessment.json](assessment.json)
retains each host, job, artifact digest, host hash and cleanup outcome.

## Native comparison and disposal

Native `12.3.3-MariaDB-ubu2404`: `PASS_NATIVE`. Both host results were
`PASS_GUEST`, matched the following native outputs exactly, used two pristine
children and had no cleanup errors. Both ended with refs=0, process_exit=0,
reaped=true and root_exists=false. No native timing comparison was performed.

| Oracle | Native and both guest outputs |
| --- | --- |
| literals | `[["日本語","0041",5,"word","a'b"]]` |
| comments | `[[5]]` |
| identifier | `[[1,1],[2,2]]` |
| nul | `[["610062"]]` |
| modes | `[[2,"a\\b"]]` |
| prepared | `{"protocol":"COM_STMT_PREPARE/EXECUTE","text_hex":"4100275ce697a5e69cace8aa9e","number":7}` |

## Installed test outcomes

All following named Go tests/subtests passed on both hosts:

- `TestAnalyzeTimerFreshAndFork`
- `TestAnalyzeTimerFreshAndFork/TCP`
- `TestAnalyzeTimerFreshAndFork/Pipe`
- `TestPreparedLexerTablesActualGuest`
- `TestPreparedLexerTablesActualGuest/normal_ambient_ignored`
- `TestPreparedLexerTablesActualGuest/profiling_does_not_verify`
- `TestPreparedLexerTablesActualGuest/all_638_compiled_descriptors`
- `TestPreparedLexerTablesActualGuest/corrupt_table_rejected`
- `TestPreparedUCATablesActualGuest`
- `TestPreparedUCATablesActualGuest/normal_ambient_ignored`
- `TestPreparedUCATablesActualGuest/profiling_does_not_verify`
- `TestPreparedUCATablesActualGuest/six_resolved_tables`
- `TestPreparedUCATablesActualGuest/corrupt_table_rejected`
- `TestWorkerTrapActualGuestNotifiesAndIsolatesPeer`
- `TestCRC32CEquivalence`
- `TestCRC32CPageValidation`

Source timer controls: 3 passed per host. Snapshot smoke: 1 passed per host.
CRC controls cover 832 lengths/alignment cases plus independent/known-vector
checks, and 80 actual page validation/corruption/LSN cases.

`TestAnalyzeTimerFreshAndFork` covers TCP/Pipe, Fresh and two children, three
ordinary/delayed query pairs per database, two rows/one loop, delayed reported
time in [18, client wall+5] ms, subsequent SUM=3, isolation and checked disposal.
These are the assertions in `tests/gointegration/timer_test.go` at the source
above; the console did not emit per-query elapsed samples. No new performance
measurement is inferred from test runner duration.

## Evidence mutation controls

The two host records were exactly equal. Positive control: PASS. Each of the
following 20 mutations was rejected on both hosts:

| Mutation | Reported rejection |
| --- | --- |
| contract | wrong build contract |
| source | build source differs |
| guest | guest identity differs |
| linked | linked guest differs |
| one-build | independent rebuild evidence missing/different |
| different-builds | independent rebuild evidence missing/different |
| experimental | experimental guest patch |
| source-file | modified guest source differs |
| lexer-input | prepared lexer source-input provenance differs |
| startup-missing | canonical startup concurrency inputs differ |
| startup-input | canonical startup concurrency inputs differ |
| overlay | source overlays differ |
| toolchain | toolchain archives differ |
| regen-source | build source differs |
| regen-result | generation inputs differ |
| inventory | generated source inventory differs |
| provenance | generated provenance differs |
| converter | converter identity/output differs: converter_commit |
| patch | converter identity/output differs: patches_sha256 |
| translation | converter identity/output differs: files_sha256 |

## J1 worker controls

The two host records were exactly equal; all six outcomes matched expectations.

| Case | Exit | Expected failure |
| --- | ---: | --- |
| heap-0 | 1 | true |
| heap-1 | 0 | false |
| heap-1-race | 0 | false |
| mmap-0 | 1 | true |
| mmap-1 | 0 | false |
| mmap-1-race | 0 | false |

Routine console transcripts, full REST responses and duplicated source/host
result payloads were removed. Original hashes and the inspected record commit
are in [reduction.json](reduction.json); the full original artifact inventory
remains in [artifact-file-sha256.json](artifact-file-sha256.json).
