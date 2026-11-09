# Process-local static initialization cache

On 2026-11-10 the Human accepted process-lifetime retention to prioritize total
execution time for Issue123. This authorizes preparing the minimal product
candidate; it is not approval to merge, release, or claim new performance.

Create the immutable initial image lazily, once per compiled engine per host
process. Retain one readonly, unlinked backing file until process termination.
The measured static-page payload is about 8.5 MiB on the Mac prototype; the file's
2GiB logical length is sparse, not 2 GiB of physical storage or a fixed RSS promise.
OS page size can change mapped/allocated bytes. DB count does not multiply the
image. The initial builder mapping is disposed before children are admitted.

Every DB keeps private writable mappings, runtime owners, TLS, connections and
workers. DB Close still joins workers and disposes those per-instance resources.
It intentionally does not dispose the shared immutable cache. No public cache
shutdown/reset API, background reclamation, timer eviction, user-data cache,
engine template or asynchronous DB Close is added. Existing Snapshots remain
independent; no tables, rows or live InnoDB state are shared through this image.

Go reuses it across independent DBs in the same Go process. Python reuses it
inside its managed Go host; independent starts/pytest workers may have separate
hosts and separate images. The image disappears when that host exits. Fresh
and Fork both use the same initialization boundary.

Initialization failures are latched without hidden rebuild/fallback. Unpublished
resources are disposed immediately when possible; unresolved cleanup ownership
is retained and retried on a later failed acquisition. Admission stays stopped
for that cache even after cleanup succeeds; restarting the host/process provides
a new owner. Existing successfully admitted child mappings remain independent.
A failed per-child map with confirmed rollback may be retried; uncertain rollback
latches admission so repeated requests cannot accumulate unowned reservations.

A generated manifest records all initial bytes, globals, segment state and the
nonzero envelope. Canonical generation computes it from the selected installed
runtime, not the old checkout. Source drift is a normal verification failure;
whole-memory equality and omission controls remain mandatory. The public API
is unchanged. Diagnostics distinguish retained image FD/pages from active child
mapping counters; neither is an RSS measurement.

Evidence keeps original scope: [bounded prototype CI 42657516361](https://github.com/masahitojp/mariamem/actions/runs/42657516361)
passed both OSes at 378f8490. The prior single-Mac scan optimization reduced cold
image preparation about37→12ms. That does not establish performance of this
product candidate, Ubuntu performance, or universal memory/CPU improvement.
Candidate source/ownership/real-DB checks precede adoption review. Canonical
regeneration and product packaging must carry the manifest and ownership files.

The historical linked-library attribution keeps its original source and host
identity. Only `image/layout.json` is added to the generated provenance; the
license check reconstructs the old provenance byte-for-byte after removing that
one derived metadata entry. Changes to any old generated source/input identity
remain failures. This is explicit reuse of unchanged-code attribution, not a new
symbol audit or release qualification.
