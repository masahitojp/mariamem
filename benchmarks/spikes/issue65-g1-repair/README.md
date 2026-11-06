# Issue65 G1 native input repair

Human continuation after CI42303099940,2026-11-07: repair the demonstrated G1
differences, preserving the profile and D2. The prior234 observations completed
on macOS/Linux with the same195 PASS/39 mismatches. The original fixed-guest
receipts remain under ../issue65-prepared-input and are not relabeled.

The experimental guest adds checks to decoded command/EXECUTE entry, checks the
advanced native decoder pointer for surplus input, and restores native conversion
metadata when a fresh-descriptor bind fails. It does not add a host decoder.
Fully decoded overdeclared strings retain D2's empty-string acceptance; their
remaining bytes are consumed by the native string helper. Temporal decoding does
not get that exception. Empty PREPARE still invalidates the last-statement alias.

Only guest/experimental.patch changes engine behavior. Canonical source.patch,
production generated code, controller ownership and public APIs remain unchanged.
Future G2 metadata/result chains and P1/P2/adoption/release remain separate.

Bounded verification:2h active work,30min measurement tooling,local native plus
at most one Linux CI; owned builder/runtime12GiB each,free floor12GiB. New guest
identity and full worker-body binding review precede installation. Repeat22
lifecycle/126 prior observations,existing controls/supporting checks and unchanged
G1 fixture234 observations. Add narrow controls for multi-parameter rollback,
retained charset conversion,first rejected bind and empty-PREPARE alias state.
Save failures,do not refresh expectations to match output. Dispose SDK,converter,
archives,build trees,binaries,caches/worktrees after retaining compact evidence.
