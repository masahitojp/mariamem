# Issue145 validation follow-up

The missing macOS/profile condition is satisfied by
[CI42670536897](https://github.com/masahitojp/mariamem/actions/runs/42670536897),
source_commit `401def4e1b80852eedd58efaf615b3019a36d92a`, job129345604583.
The [receipt](issue145-shutdown-macos-ci.json) retains exact source identity and
artifact digest. It does not relabel the earlier incomplete local result.

The job uses Go1.26.10/macOS arm64 and matches the recorded Python3.14.8 /
OpenSSL3.5.9 / connector26.7.0 source, ABI and extension hashes before compilation.
It builds the existing canonical guest host once and verifies its clean-source
binary stamp. Host mode/setting-failure/export/disposal controls, public
reSnapshot with rollback, multiple-client shutdown, and parallel owned-child
cleanup all pass. The parallel test reports35 mutating children plus a child
surviving baseline Close; fd9→9 and goroutines2→2.

Prepared/native and edge matching PASS with no different cases or edge modes.
The existing functional FAIL and ACCEPTED_BOUNDED_EXCEPTIONS remain explicit;
no new exception, fixture, profile waiver, guest or generated-source change is
introduced. The old local Python3.11 mismatch is historical, not a passing run.

Normal Ubuntu CI42664665273 already passes at e671f66a with the same runtime and
public regression bodies. The workflow-only addition at401def4e caused normal
CI42670550618 to stop on its new-workflow inventory test: shutdown-candidate.yml
was missing from WORKFLOW_SCOPES. The follow-up adds its reviewed `python`
classification alongside the other CI workflows; unknown workflows and mixed
runtime diffs still select full checks. It does not bypass that inventory oracle.
This metadata fix and these evidence records do not change the tested runtime,
guest, regression bodies or the successful macOS job definition. A new macOS
build is not needed for this boundary; normal PR CI must pass on the final head.

After that normal-CI repair passes, the recommendation is main adoption of the
bounded shutdown-purpose implementation. The strongest remaining limitation is
that the six-pair ~1MiB/macOS measurement demonstrates write-heavy Close benefit,
not a universal benefit for light/read-only workloads or stable tail/RSS gains.
Original performance and local evidence retain their own identities in the
[implementation report](issue145-shutdown.md). No release is approved here.
