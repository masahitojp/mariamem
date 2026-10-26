# Browser-driven guest/live experiment

The Human authorized continuing from executable native controls and implementing
live behavior where the E2E use case needs it. This bounded experiment compares
the unchanged order apps/browser cases against existing mariamem Snapshot/Fork.
No product API, canonical guest/generated input or main integration is selected.

Go gets one prepared baseline and an independent child/DSN per case. Python keeps
one app and one relay endpoint; after all physical SQL connections close, a
new child replaces the backend. Active/idle sessions and open transactions block
reset. New handshakes are refused while draining/replacing/failed. A failed Fork
never admits the next browser test; explicit retry may recover. Startup and close
have their SDK deadlines; the relay timeout bounds drain only.

The Django input already uses normal CONN_MAX_AGE=0 request-boundary connection
closure, exactly as native3446b5c. Retaining physical sessions/temporary tables/
prepared handles, startup capture and background jobs are separate future cells.
The relay forwards bytes without protocol parsing, SQL rewriting or replay.

Required executable evidence: same native UI/rows/error cases, same Python PID/
HTTP/DB endpoint, distinct new backend generations, consumed source and immutable
baseline, child/app/host/relay cleanup. Retain skipped-reset and restarted-app
mutations. Add held SQL transaction/busy refusal, refused new handshakes during
drain, failed replacement/no admission, explicit retry and closed old-backend
checks. Native schemas must not be described as guest Forks, and guest disposal
must not be recorded as native DROP DATABASE.

Use disposable workspace e2e-guest-live:6GiB budget,8GiB minimum free,1800s local
campaign ceiling. Source identity is checked before builds; an independent clean
checkout avoids the known linked-worktree VCS-stamping issue. Browser/client
inputs and apps remain pinned to native3446b5c, with normal mysqlclient2.2.7,
Django5.2.8, Playwright1.56.0/Chromium1194 and Go1.26.10. Native input equivalence
and package/host source hashes are admission checks. Mac arm64 local execution
and both-OS/Python3.11/3.14 CI are distinct receipts, never relabeled.
