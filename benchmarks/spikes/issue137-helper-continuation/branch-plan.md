# Positive spare-archive stimulus: source-prepared, not verified

Pinned actual source620a4b5624222048fece7fe1789978ae0675cae2; complete file
identities in evidence/branch-source-identities.json. No engine, hook or branch
condition is changed. Existing hook/pre-postimages remain byte-identical.

Source facts in storage/innobase/buf/buf0flu.cc (unpatched target coordinates):
write_checkpoint1843–2206 initializes archive_header_was_reset0; the archive
rollover path advances first_lsn and assigns first_lsn+capacity at1940, returning
that LSN at2206. log_checkpoint_low2214–2270 carries the returned value; the
checkpoint helpers return it to page_cleaner. buf_flush_archive_create2768–2779
consumes a nonzero request and returns0. The fully-unemployed path2873–2887
consumes the previous request, then can save a newly returned checkpoint request.
At the next iteration, the idle/no-LRU path2835–2841 tests that saved nonzero
value before timed_wait. The shared adapted sync-LSN recheck and both existing
observational markers are retained exactly; these coordinates precede their
small line offsets.

The old extra scenario toggled archiveOFF immediately after the write burst.
That does not establish an archiveON checkpoint→idle window; it is a plausible
reason the nonzero-request idle branch was not observed, not a proven runtime
cause. Merely crossing two log lengths or advancing checkpoint cannot prove
archive_header_was_reset or the page-cleaner branch.

The new finite supplemental case holds archiveON across turnover, uses ordinary
dynamic max_dirty_pages_pct=0/lwm=0 and flush_syncON, closes the SQL connection,
waits for real disconnect, and waits at most5s for the **existing positive
spare_archive marker** while leaving SQL idle. ha_innodb.cc17668–17737 shows the
dirty-threshold callbacks wake the cleaner;19364–19390 registers zero as valid
and flush_sync as dynamic. This drives ordinary flush/checkpoint activity rather
than changing the algorithm. Marker absence or root death fails the case; no
capture attempt is retried. After the marker, restore settings/archiveOFF,
disconnect again, capture once, compare all256 ordered IDs and all64KiB payloads
before/after restore, and verify sibling independence and cleanup.

legacy_spare_archive.py implements this additional case using existing control
logs/status APIs; no decoder is reimplemented. The original paired case remains
unchanged and must run too. The source observer's3 small controls pass, but that
is neither SQL execution nor branch coverage. The native matched case is supplied
in native_spare_archive_test.go.txt (gofmt parse only, not compiled); it reuses the
verified issue138Drain/Observe and original capture helper. A test-owned stderr
pipe observes the existing marker, preserves stderr, and joins its reader after
root cleanup. Run this extra case in its own finite test process, avoiding any
parallel/global-stderr test interference. It needs the existing target fixture
helpers staged alongside it; original79/601 and original extra cases stay intact.

Why a native follow-up could be justified: the helper fix alone needs no native
rebuild, and old4b3954/889f remains the exact logical counterpart for the original
scenario. The **new archiveON→checkpoint→idle runtime stimulus** was not executed
by that old scenario, so its new positive-branch result cannot be borrowed. If
both-path positive coverage is pursued, one additional native execution is
needed for this specific changed runtime input. Its old artifact/binary is gone;
one fresh exact-input producer plus translation/host with the new supplemental
case is the bounded available route, not a throwaway close-observer rebuild.
No changed C++/hook input is currently needed; if later required, pin full images
and explicitly reassess both old/native applicability before using the second
slot. This report is the pre-build dependency justification, not a result.

The stimulus is source-grounded but not guaranteed to hit. One finite failure
must be preserved, not followed by an automatic parameter/workload campaign.
No producer/host/SQL was started: capacity is currently insufficient at floor12.
