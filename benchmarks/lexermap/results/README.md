# Issue126: lexer-map generation cost

**Recommend one bounded prepared-map prototype.** Every observed Fresh/Fork
initialization generates638 map pairs, but their full512-byte contents form
only28 unique pairs. Summed function elapsed per Fork is1.968ms median
(20Forks,1.896–2.056ms), above the predeclared1ms investigation threshold.
This identifies repeated work worth trying to remove; it is not a measured
speedup or adoption of a new implementation.

The strongest objection is the limited headroom: even eliminating this function
entirely cannot plausibly remove most Fork startup. A prepared route must still
select/assign valid instance-local pointers and preserve dynamic fallback.
Do not equate1.968ms with guaranteed savings or319KiB with RSS reduction.

## Fixed boundary and identities

- Product source_commit: 3d8b2201c1f36fa5b7264e0450104055f3822272, adopted CRC main.
- Diagnostic source_commit: fe96aaff (full SHA in inputs.json); all product bytes remain equal to the product source before applying the diagnostic overlay.
- Guest SHA256: 6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe.
- MariaDB source_commit: 83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e, mysys/charset.c:60–119 and include/m_ctype.h. Source hashes and original generated function/file hashes in ../source-proof.json.
- Original init_state_maps structurally corresponds to p4.Fn955:512-byte my_once_alloc with flag16; state/ident pointers at72/76; ctype at40; charlen handler104+88;256 classifications; punctuation constants; ident SIMD projection; final x/b/n overrides. The optimized WASM has no function names; this identification is structural, not a recovered debug-symbol claim.
- The original generated function body is byte-preserved except renaming it for a wrapper. Hash drift aborts overlay creation. No guest build, SQL semantics/default changes, public API or product source edits. Observation files exist only in an external Go overlay.
- Go1.27.3, CGO0, GOMAXPROCS8, GOGC100, Pipe, AppleM1/16GiB. Exact OS and binary/build identities are retained.

## Finite experiment

Five alternating off/timed process pairs, plus one separate inventory process.
Each process creates one Fresh root, seeds1000rows, captures a cap1 baseline,
then runs4 sequential Forks. Total11processes/55initializations. There were
no discarded or replacement runs. This is P1 attribution, not a P4/P8 throughput
campaign or a new pgmem comparison.

The timed wrapper brackets only the original function, including its allocator
and character-handler callees. Recording/drain, descriptor reads, hashes and
map copies are outside that interval. Thus this is *elapsed time attributed to
the function*, not exclusive CPU self-time. The inventory run does not record
function timings. The off/timed arms use the same diagnostic binary; even off
retains the extra wrapper dispatch and is not an unmodified-product benchmark.

The empty timer-pair mean is18.14ns (median over timed processes). Multiplying
by638 gives0.0116ms, about0.6% of observed function sum. This is an overhead
scale, not a subtraction or exact bias correction. Across the five paired
process medians the observed Fork API change is+1.08% median
(range−0.25% to+1.50%). No materially large observer disturbance appeared in
this small sequential cohort; cache/scheduling effects cannot be ruled out.

SQL row counts/sums and independent committed UPDATEs pass on every child;
Unicode literal/arithmetic/comment smoke passes. Child connections retire,
all Close calls succeed, owned scratch is empty, and mapping/reserved/RW/
release-failure counters return to zero. No extra map generation appeared
during the tested child SQL. This does not cover arbitrary dynamic charsets.

## Results

|Quantity|Observed|
|---|---:|
|Calls per Fresh and per Fork|638|
|Map pair size|512 bytes (state256 + ident256)|
|Bytes generated per initialization|326656 bytes =319KiB|
|Full-byte unique map pairs|28|
|Unique content total|14336 bytes =14KiB|
|Fork function-sum elapsed median|1.968ms|
|Fork function-sum range,20children|1.896–2.056ms|
|Fresh function-sum elapsed median|1.971ms|
|Off-arm Fork API median|21.051ms|
|Timed-arm Fork API median|21.132ms|

All25timed initializations and5inventory initializations have the same638
descriptor/collation bindings and call sequence. All5inventory initializations
have identical maps. Unique-pair dedup uses the full512bytes with hashes checked;
no charset-name or numeric-ID-only equivalence is assumed. Prefix and punctuation
states plus ident-map invariants are checked in the inventory path. The generated
table's consumers and exact broad SQL/native parity still need validation if a
prototype is proposed for adoption.

The function accounts for roughly9% of sequential Fork elapsed in this cohort.
It cannot explain the whole remaining16ms P4 difference against pgmem from the
previous campaign: different parallelism/cohorts must not be arithmetically
combined. No new internal attribution of that P4 gap is claimed.

## Next bounded prototype, not implemented

Prepare the28 unique byte pairs as static guest data, and associate the admitted
compiled descriptors with those pairs. Keep per-instance CHARSET_INFO, registry,
locks, XML/unknown descriptor generation and failure handling. Do not copy live
registries or another instance's offsets. Prepared byte arrays are immutable;
field pointers are assigned for the current guest through normal relocation.

The first prototype should prove512-byte equality for all638 observed bindings,
detect source/config drift, preserve the original fallback, and run the same
normal/prepared SQL and cleanup checks before interpreting timing. Compare
unchanged versus prepared route with a finite paired Fork measurement; only
then decide whether the saved time is worth maintaining a producer/header.
This task does not authorize productization, main integration or release.
Do not silently broaden to other common-initialization structures.

## Reproduction and retained data

From this directory, without the build workspace:

    python3 analyze.py --check
    python3 -m unittest test_analysis

observations.json is a lossless dictionary encoding of all11 raw process
reports: repeated row identities and map bytes are interned, while every call
duration, result/exception and initialization is retained. compact.py roundtrips
to the original reports exactly. summary.json includes all638 bindings and28
complete byte pairs, plus each process/initialization statistic. Checksums pin
the text evidence. Raw consoles are also retained outside the repository in a
small local archive; no analysis depends on them. Eight negative mutations reject
missing calls/children, failed cleanup, wrong results/exceptions, bad timing and
corrupted map bytes.

The original premeasurement plan, harness and overlay are in the parent
directory. Build/run require the pinned source, documented Go toolchain and
disk budget; new observations will not reproduce timings byte for byte.
