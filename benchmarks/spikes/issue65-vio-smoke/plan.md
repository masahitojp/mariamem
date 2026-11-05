# Issue65 ultra-light NET/Vio seam probe

Human authorization2026-11-05: ultra-light experiment after source-only review.
Question: can the pinned upstream NET writer send framed bytes through a memory-backed Vio callback without an OS socket?
Exit: compile/run an isolated source-extraction harness using upstream NET/Vio declarations and unmodified packet writer functions; assert exact bytes, short writes, callback read/EOF, sequence and failure. This does NOT prove embedded integration or the native decoder.
Budget: active15 minutes including at most5 minutes harness tooling; one small native compile with bounded fixes, timeout30s compile/10s run, no server/guest build, SQL, CI or performance measurement. Disposable1GiB/free8GiB. Stop on substantial dependency work.
Source: MariaDB12.3.3 commit83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e; product baseline47121e1be0b399ba4e2270ce3e25c411ade0e2eb. Existing user changes untouched. Preserve script/results/hashes, then remove owned source/compiler output and worktree.
