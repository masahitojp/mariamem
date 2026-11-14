# Buffer-pool descriptor-only zeroing candidate

Human authorized minimal product-candidate preparation and re-evaluation on 2026-11-14, following [the bounded spike](https://github.com/masahitojp/mariamem/blob/4082856a92be350d34283a47be72fa90ec2af7ed/benchmarks/forkcost/buffer-zero-spike/README.md).

Base: current main, including prepared output adoption. Scope: WASIX/Emscripten buffer-pool allocation alone; retain extent alignment, original-pointer free, allocation failure behavior, valid descriptor range and initialization ordering. Retain common allocator zero contract, default 16MiB and grow behavior. No experiment mode/env/poison/abort in product code. Canonical source patch owns the candidate; release inputs are not silently updated.

Verify focused source/input/host contract controls before one fresh UNQUALIFIED C build. Review exact new generated worker/CRC bindings, regenerate and execute correctness before a fixed paired current-main comparison (P1/P8, three repetitions, warmup; retain failures/outliers). Existing large/compressed/resize/fault/recovery controls must be explicitly mapped to this exact candidate. Both supported platforms, independent reproduction and normal gates remain adoption conditions. Do not integrate or release this prototype automatically. CI submission, if used, is a handoff: return run URL/SHA/operation and stop without polling.

Workspace budget20GiB, minimum free8GiB. Retain compact source identities, commands, raw measurements and checksums; remove recreatable SDK/source/generated/binary/cache/worktree state when the task ends. Main/user checkout remains untouched.
