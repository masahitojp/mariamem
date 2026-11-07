# Issue126: prepared lexer-map prototype

**Recommend a canonical guest implementation candidate.** Exact-map, SQL,
fallback and cleanup controls pass. Sequential Fork improves in all5pairs:
median paired API change−2.199ms, full48-child suite−9.58%, CPU−7.08%.
This passes the predeclared screen of at least0.5ms and4/5 improving pairs.

The strongest objection is production readiness: this single-Mac Go overlay
uses prior observed bytes and exact-build descriptor offsets, allocating/copying
one blob into each guest arena. It is not an independent native C producer,
canonical patch, C-static layout or supported-platform qualification. The
result justifies that next engineering step; it does not authorize adoption
or merging the overlay. Parallel suites retain ~800ms SELECT tails on both arms.

[Graph](report.html) · [Summary](summary.json) · [Every child](children.csv)

## Identity and changed boundary

- Product source_commit:3d8b2201c1f36fa5b7264e0450104055f3822272, adopted CRC main.
- Measurement/build source:fad2eba2 (full SHA and binary VCS stamps in inputs.json).
- Guest SHA256:6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe.
- Producer input: checksum-pinned Issue126 inventory858b4973,638bindings/28unique512-byte pairs. tables.json is checked against that inventory; actual runtime equality against the original algorithm is a separate control.
- Go1.27.3, CGO0, GOMAXPROCS8, GOGC100, Pipe, AppleM1/16GiB; exact OS in host.json. Local desktop, not an isolated host or Ubuntu measurement.
- Before external overlays, product bytes equal main. Only benchmark files change in Git.

Only the compiled-registration call in p1.Fn961, before XML loading, is
replaced. Original p4.Fn955 and all3dynamic-loader callsites remain unchanged
in the normal overlay. Exact-build descriptor address, collation number and
compiled flag are checked; unknown/mismatched/noncompiled inputs use original.
Source/config/input drift fails the pinned producer/overlay.

Some admitted descriptors are constructed during compiled registration and
have high guest heap offsets. They are not all static C objects; this offset
allowlist is an experimental binding, not a portable production key.

14336prepared bytes are copied once into each guest's my_once arena.
state/ident pointers use only that guest's allocation; mutable registries stay
per-instance. No host pointer/live state is shared between DBs. No ordinary
writer was found in source review; the prototype adds no write protection.
Allocation failure/guest exceptions return through the ordinary failure route,
not suppressed. One14336-byte allocation differs from638512-byte allocations;
a future C-static route must explicitly account for its allocation/failure change.

## Fixed campaign and correctness

56processes:4original/verify SQL controls,2wrong-seed negatives,8warmups,
40primary and2separate UNDO diagnostic runs. Primary:Fresh/Fork×P1/P4,
48children,5alternating adjacent pairs/cell.1000seed rows. All1920primary
children/tails retained; no measured replacements or extra repetitions.

Both arms use the same binary/Close contract. Original retains a small wrapper
and counters; both decode the host table blob at process initialization outside
the suite clock. Prepared guest allocation/copy/selection is inside Start/Fork.
This is a prototype comparison, not absolute timings of untouched main.

Verify mode checks638×5=3190 full512-byte maps against the original algorithm.
Each initialization also clones one descriptor to an unknown address, actually
invokes original fallback and compares its map. Dynamic XML loading itself is
not exercised; untouched dynamic callsites still need canonical acceptance.

Original and verify controls pass ordinary/prepared SQL:Unicode, quoted/national/
hex/binary literals, comments, parameters with NUL/quotes/backslashes, and
ANSI_QUOTES/NO_BACKSLASH_ESCAPES. This is parity with the existing guest and
known expected values, not external native-server parity.
All child pristine/update oracles, connection retirement, Close, owned scratch
and mapping/reserved/RW/release-failure counters pass. Every prepared
initialization has638hits, one copy and no unexpected fallback.

Units cover unknown/mismatched/noncompiled descriptors, OOM/guest exceptions,
bad data/pair indexes, one-copy behavior and cross-instance independence.
Four producer mutations reject byte/binding/input-identity/generated-source drift.
Initial tooling failures (a synthetic32MiB fixture choosing a high descriptor,
then overlay basename collision) were fixed before measurements. Two final
binaries succeeded after one failed normal compilation. A literal trailing
backslash-n in inputs.json was normalized with before/after hashes and no binary
change. The collector newline fix in the report commit is postmeasurement only.

## Whole48-child suites, medians of5processes

|Mode|Original wall ms|Prepared wall ms|Median paired wall change|Median paired CPU change|
|---|---:|---:|---:|---:|
|Fresh P1|1673.5|1578.2|−5.95%|−3.87%|
|Fresh P4|602.7|578.3|−5.17%|−3.96%|
|Fork P1|1276.5|1148.5|−9.58%|−7.08%|
|Fork P4|482.8|464.7|−3.76%|−3.90%|

|Start/Fork phase|Original median ms|Prepared median ms|Median paired delta ms|Improving pairs|
|---|---:|---:|---:|---:|
|Fresh P1|22.754|20.557|−2.197|5/5|
|Fresh P4|28.683|25.467|−2.613|5/5|
|Fork P1|21.252|18.819|−2.199|5/5|
|Fork P4|26.861|24.127|−3.845|4/5|

Phase columns are medians of per-process child medians. Paired deltas are
computed inside pairs; subtracting aggregate columns need not match them.
P1 paired reductions range1.912–2.654ms. Prior function attribution was1.968ms:
removing allocation/classification plausibly explains most of this scale,
but cache/allocator/scheduling contributions are not separately identified.

ForkP4 has2SQL spans>100ms per arm, all count_sum:
original802.27/788.89ms, prepared798.89/798.57ms.
Suite ranges465.9–1076.5ms versus460.4–1029.7ms. One pair increases105.3%
with a prepared-only tail; another decreases50.5% with an original-only tail.
Those are not lexer-map effect estimates. No tail is removed and Issue68 is
not resolved.

## Separate UNDO diagnostic and limits

96untruncated child traces:24960purge scopes,0purge aborts,0query rseg waits,
0background page waits,0linked chains; maximum2449events/child.
UPDATE maxima2.549/1.935ms (original/prepared). These separate runs cannot
identify ownership of the ordinary campaign's SELECT tails and are excluded
from performance estimates.

No RSS campaign was done.319KiB generated map payload versus14KiB unique copied
content does not prove305KiB less RSS: arenas/page touching/lifetimes differ.

## Next step and replay

Build a reproducible source/config-bound producer and canonical guest patch.
Preserve unknown/XML fallback; do not ship the Go-offset allowlist or prototype
Module fields. Validate independently generated bytes/bindings, ordinary/prepared
native SQL parity, child isolation/cleanup, macOS/Ubuntu acceptance and a finite
performance screen on that actual candidate. Static-layout/failure-semantic
differences belong in adoption review. No product, version or release changes
are made here; this experiment branch is not merge-ready.

    python3 analyze.py --check
    python3 -m unittest test_analysis test_undo
    python3 render.py

Text observations reproduce all timing summaries/CSV after workspace cleanup.
Records add variant=arm for the analyzer, which validates equality. Original
reports/consoles are retained byte-for-byte in a local compressed archive.

    python3 diagnose.py --check --archive /path/to/undo-traces.tar.gz

The checksum-pinned trace archive stays in owned local evidence/published,
not Git (public-source policy excludes binary archives). A clone can replay
timings but cannot independently replay raw UNDO traces; diagnostics.json
retains their analyzed output. Checksums pin published text evidence.
