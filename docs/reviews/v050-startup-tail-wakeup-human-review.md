# Human Review — v0.5.0 startup-tail wakeup spike

**Decision now:** authorize a production-quality guest-source correction and
canonical rebuild, or retain the characterized startup tail. **I recommend
the correction work.** The question about this tail's mechanism is substantially
settled: three current-guest slow Starts directly showed the cleaner read
target zero, the main thread signal an empty waiter list, then the cleaner
register and time out about one second later. A bounded translated-code
prototype reduced four-parallel tail suites from 18/30 to 0/30 in Go and
26/30 to 1/30 in Python while all existing SQL/transaction oracles passed.

**Strongest objection:** the prototype skips a MariaDB condition wait through
a disposable Generated Go change. It has not been built from patched guest
source or reviewed across other flush, checkpoint, and shutdown states. The
single remaining Python candidate tail is unclassified. These are reasons
not to merge the experiment branch or promise elimination of every tail;
they are not reasons to keep an observed, apparently correctable one-second
mode without testing the source-level correction.

The [spike report](../../benchmarks/v050-startup-tail-wakeup-spike.md) links
the exact v0.5.0/guest identities, raw event order, excluded overflow pilot,
source patch, binary hashes and paired Go/Python records. The preceding
[frequency study](../../benchmarks/v050-startup-tail.md) used unchanged release
binaries. Together they support this narrow mechanism in 12.3.3; neither
establishes a version-to-version rate change or general startup-tail absence.

If approved, the next task is finite: review the post-lock target check in
MariaDB source; apply the smallest reviewed change to the 12.3.3 guest owner;
rebuild the guest through the canonical Linux path; regenerate Go independently
and verify identities/provenance; then exercise flush/checkpoint/shutdown,
Start/Close, SQL/transactions and the same paired Go/Python Fresh workload on
supported platforms. Report any differing tail, failed oracle, or semantic
conflict before asking to integrate. The experiment's `guest/experimental.patch`
is an input to review, not an adopted `guest/source.patch` change. Final
qualification and release decisions remain separate.
