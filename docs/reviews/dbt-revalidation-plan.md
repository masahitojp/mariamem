# dbt fixed-workload revalidation — Issue19

Authorized 2026-10-31. Question: does the original dbt TEXT DISTINCT failure
remain after the main Fd_dup/worker-notification repair? No broader dbt support
is implied. Base source_commit: cfc0421dc9b886ea4bf56d5c46083b374c9a2e2d.

Reuse the original project bytes from experiment/dbt-mysql-feasibility
(ab38beb2; the original cc00ccd runtime receipt remains historical). The
customer_names model keeps plain DISTINCT, without CAST or SQL_BIG_RESULT.
Python3.11, dbt-mysql1.7.0/core1.7.20/Connector26.10.0; restore the original
resolved dependency pins before execution. The EOL core line and single minor
remain explicit limits; Python3.14/OpenSSL4 is not part of this profile.

Finite exit: native MariaDB12.3.3 and fresh source-bound guest run debug, seed,
run/repeat, build (generic tests), snapshot twice, docs generation and full
refresh at threads1/4; compare exact sorted application rows and verify a
deliberately failing generic test and final cleanup. Preserve failures. Required
hosts are macOS arm64 and Ubuntu24.04 x86_64; local/emulated observations are
labelled and do not substitute for native Ubuntu. Runtime changes, support
promotion, new protocol commands, detailed resource census and release are
separate decisions.

Budget: 2 hours active work, including <=30 minutes measurement tooling; <=2
heavy CI submissions subject to the current Release-only policy. No standalone
heavy workflow is introduced. If host/CI/dependency inputs prevent completion,
report INCONCLUSIVE with the exact missing input and next action. Collect
wall-clock CLI durations and final host/schema/temp cleanup only. Waiting is
separate; no cold-machine or performance claim.
