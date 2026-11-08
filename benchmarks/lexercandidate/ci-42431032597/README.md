# WASIX C compile failure: const-qualified initializer argument

[Run42431032597](https://github.com/masahitojp/mariamem/actions/runs/42431032597)
binds original source_commit `b3d3c7faffc063b993fd87acd90b79eef09982ee`.
The HOME repair worked: configuration passed and WASIX C compilation started.
The initializer failed to compile because MariaDB defines `CHARSET_INFO` as
`const struct charset_info_st`. The initializer needs a mutable struct pointer,
as the original `init_state_maps` uses. No const cast is introduced.

The old standalone component replay PASS covered the algorithm with captured
handler inputs, but its mutable mock typedef did not model production's const
alias. It therefore missed this source integration error. That prior PASS is not
rewritten or promoted to type compatibility/actual guest acceptance.

The correction imports the exact typedef from pinned `include/my_global.h`
(SHA256 in local-const-fixed/c-source-check.json), uses mutable struct fixtures,
and tests both the working initializer and the original wrong signature. With
`-std=gnu99 -Wall -Wextra -Werror`, all638 full512-byte map and existing
fallback/OOM/corruption checks pass; the wrong signature must fail compilation.
These component checks run before the expensive full guest build in CI.

Only the experimental initializer signature changes in C. Prepared table bytes,
canonical guest patch, generated runtime and performance results remain unchanged.
Actual WASIX rebuild and translation still need a new CI result; no adoption or
Qualification is claimed. The downloaded build ZIP digest was verified before
extraction. This compact receipt keeps the relevant error excerpt and the full
original build-log checksum; raw fetched files are retained locally.
