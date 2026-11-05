# Issue65 step3A — coherent native login/output with embedded bootstrap

Human authorized continuation after design source_commit429ce325f0449674968c98f9c264999cafa708fc.
Budget: 2 active hours starting 2026-11-05 05:15 UTC, tooling30min, CI0,
owned6GiB, free8GiB. No stage3B/C/D, WASIX build or production adoption.
Use pinned MariaDB12.3.3 and the existing Linux/arm64 image. Keep EMBEDDED_LIBRARY
and one header layout across all translation units. This experiment patch requires
MARIAMEM_NATIVE_WIRE; a macro-off patched build is not a deliverable.

Prove real embedded C API initialization and product routine bootstrap still work;
preserve MYSQL_BIND execution. Then native greeting/login, text metadata/NULL/error,
wire PREPARE/EXECUTE/CLOSE with native output, QUIT and a second sequential session.
Use bounded memory queues behind Vio, not an OS socket listener; the client fixture
may construct/inspect packets but engine output must use upstream Protocol/NET.
Wire sessions must have null client_params and per-THD fixed mode. No global raw
packet or mode switch. Preserve patch/inputs/commands/results; stop at budget if
coherent output/login is too broad rather than writing replacement encoders.
Full authentication/profile/lifecycle/16-session/Snapshot/Fork/Live acceptance is
later work. Step2 malformed-string behavior stays unchanged. Clean owned build,
source, container and worktree after preserving compact evidence and Git history.
