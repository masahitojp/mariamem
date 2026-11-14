# Buffer-zero candidate EIO fixture correction

[Run43562441277](https://github.com/masahitojp/mariamem/actions/runs/43562441277)
on source_commit `f8df7a0d10bee4a34010851828ff0dd487bdbaf0` passed standard check
and full integration on both native platforms. Ubuntu passed the complete job,
including EIO and clean/dirty redo controls. macOS passed basic SQL, large normal
and compressed tables, resize and Fork controls, then failed the EIO fixture:
`fault path not exercised /faultprobe.ibd hits0`. Its redo controls did not run.
The [receipt](buffer-zero-ci-43562441277.json) records both artifact ZIP hashes.

The archived fixture seeds 2MiB of payload into a 16MiB buffer pool, and arms
`.ibd` EIO after Fork reports Ready. Startup read-ahead can leave that entire
working set cached; the query then need not reach the injected filesystem read.
The failed coverage assertion reports no corruption. Related-issue search found
no dedicated EIO-fixture issue. This correction does not reopen the known
Connector/Python or MariaDB trigger issues.

The maintained CI fixture now seeds 32MiB and asserts the default 16MiB pool.
Its query reads every payload through `CRC32`, checking both byte count and the
full expected checksum sum. This prevents a length-only scan from avoiding
externally stored payload reads. `.ibd` injection remains after Ready;
`ibdata1` injection remains before Fork. Exactly one injected error, correct
recovered results (or an explicit error), an independently healthy sibling and
successful Close remain required. A startup-only arming alternative was rejected
because it changes the intended query-stage boundary.

The workflow uses `scripts/check_buffer_pool_controls.py`, which reuses the
archived overlay/build recipe and unchanged basic/large/redo controls, replacing
only the scratch fault fixture. Historical harnesses, measurement matrices and
checksums remain unchanged. No guest, host runtime, generated source, allocator
or performance binary changes are made.

Focused local verification passed on macOS with Go1.27.4, using the unchanged
canonical generated runtime and the same test-only filesystem overlay. Both
paths injected exactly once and recovered correct byte/CRC results; both healthy
siblings and all Close calls passed. `.ibd` hits at Ready were zero, confirming
that its injection happened after startup; `ibdata1` hits at Ready were one.
The receipt binds the changed fixture and local binary SHA256. This is a focused
regression result, not a replacement for CI's Go1.26.10 two-platform execution.
Python syntax/CLI, Go formatting, public-source and diff checks passed. Saved
historical evidence verification also passed all64 processes and both matrices.
No new engine build or benchmark is performed locally. Canonical CI is resubmitted
for the new exact candidate rather than relabeling old producer receipts.
