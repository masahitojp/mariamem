# dbt Ubuntu replay submission — experiment only

2026-10-31 JST. Human explicitly requested Ubuntu execution after the saved local
macOS1.7 replay and optional1.8 investigation. This authorizes one bounded
standalone replay of Issue19's original1.7 workload; no1.8 adapter work, release
transaction, adoption or ongoing CI policy change follows.

GitHub requires workflow_dispatch to use a workflow registered on the default
branch. The experiment branch therefore temporarily replaces the existing manual
`.github/workflows/v044-product-validation.yml` with **only** the fixed dbt job.
Its name/run-name explicitly identify the dbt experiment. It runs no Runtime
qualification or release code. **Never merge this workflow override into main.**
Default-branch workflow, protection, Release-only policy and Development checks
are unchanged. After successful dispatch, hand off the URL/source and stop;
receipt collection follows a Human status request.

Ubuntu24.04 x86_64/Python3.11/Go1.26.10 and the original fixed dependency pins.
The exact12.3.3 image digest, amd64 architecture, container binding, host OS and
source/workflow SHA are asserted. The existing runner checks actual Go build
identity and complete native/guest × threads1/4 results, TEXT DISTINCT, application
row parity, expected uniqueness failure, subsequent SELECT and final cleanup.
Generated snapshot timestamps/IDs remain excluded from row comparison. The
runner/project/dependency pins are unchanged from local source f37b2a7b.

Limits: job40min, replay1200s, owned output4GiB/free reserve4GiB; job timeout and
runner cleanup own the disposable service. Compiler cache is permitted, but a
fresh exact-source host is built and its actual identity checked; no cached test
PASS is used. Artifact retains dependency resolution, actual source/build/image
metadata, original dbt outputs and file checksums, including failure evidence.
Neither a pending submission nor a successful dispatch is a runtime PASS.

This consumes the first of at most2 authorized heavy replay submissions for the
original repair investigation. The1.8 probe used zero heavy CI and remains paused.
