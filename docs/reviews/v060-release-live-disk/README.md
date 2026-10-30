# 0.6.0 Release CI — Ubuntu Live disk guard

[Run41126040340, job124308433546](https://github.com/masahitojp/mariamem/actions/runs/41126040340/job/124308433546)
at source `0ec2d3fde83f4fbee53ce7611b3546d027392498` stopped before the first
G1 campaign case: free disk was 11,256,389,632 bytes (about10.5GiB), below the
unchanged 17,179,869,184-byte (16GiB) admission threshold. The campaign reported
STOP and cleanup_complete=true, with zero children/baselines. The guide's
first/second tests had passed. This is not a reproduced SQL/guest failure or
G1 acceptance PASS; later Live/P1/E2E steps in that job did not run.

The [saved assessment](ci-41126040340-ubuntu/assessment.json) identifies the run,
job, source and artifact. All8 original member hashes were checked before saving.
`original-SHA256SUMS.json` retains that manifest; `host.sanitized.json` removes
the runner home prefix for the public source boundary. The original host.json
remains in the GitHub artifact. The new SHA256SUMS.json covers the saved receipt. The ZIP digest is upload-log metadata, not an independently verified
downloaded ZIP hash; the receipt is retained under its original source.

The proposed workflow repair removes only the unused preinstalled Android SDK
from the disposable Ubuntu Live runner, before dependencies/artifacts are
installed. The job consumes Go/Python/Chromium, not Android. `df` records free
space before/after. No project artifact or compiler cache is removed, no guard
is lowered, and macOS setup/feature oracles remain unchanged. This is runner
provisioning, not a new resource model or0.7.x campaign.

Unknown: actual space recovered and whether the full new candidate passes.
Those require hosted execution; local workflow checks cannot prove either.
The existing guard must still reject insufficient capacity. No retry or new
Release dispatch is part of this fix PR. Qualification/publication stays stopped
by the failed feature gate; the failure diagnosis does not claim the other jobs
or the whole run have completed.
