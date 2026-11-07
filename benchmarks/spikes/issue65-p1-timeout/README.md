# Issue65 P1-b: native timeout domain

The Human requested continuing after P1-a passed both platforms at candidate
738bbbe58674f097161a1db2c1eda91536e416fe (CI42346396518).
Scope:preserve the public Go QueryTimeout domain in the private native route,
including zero/default30s,positive nanoseconds and MaxInt64 nanoseconds.
Negative durations and overflowing historical millisecond fixture values fail
before starting an instance. Existing SQL/capture admission and guest timer
placement remain unchanged. Public backend wiring remains P1-c.

Private lifecycle profile3 keeps the33-byte header but OPEN.value now carries
positive nanoseconds,not the earlier profile2 integer milliseconds. No fallback.
Guest validates1..MaxInt64 without narrowing. Deadline arithmetic uses unsigned
elapsed nanosecond ticks instead of adding the duration to a signed clock.
The pinned steady clock representation is checked at compile time. A5ms timer
poll remains;nanosecond configuration does not promise nanosecond scheduling.
Historical fixture wrappers explicitly convert milliseconds with overflow checks;
the typed duration constructor uses public defaults and preserves exact values.

Budget:active3h/tooling45min,owned builder/runtime12GiB each,free floor12GiB.
Cheap Go/source mutation tests first,one new guest build and exact worker binding
review,Mac native timeout/ownership and original regressions,then at most one
Linux CI cohort. Preserve original expectations and approved1043 G2 adaptation.
Mac native runtime checks pass;Linux repetition is pending. No public route,canonical generated
source,consumer/performance or release change is included.


Light checks pass:eight host owner/timeout unit tests under the race detector,
four detected Go timeout mutations and nine detected C++ source mutations with
undefined-behavior sanitizer. C++ checks run both on the extracted source and
again on the actual prepared guest files. Existing ten observation/source guard
commands pass. The first local helper read failed before engine compilation;
the original error is retained and an exact Git-archive tooling snapshot is
used to resume with the same guest source and already verified archives.

Native tests distinguish exact configuration from scheduling accuracy:
real INSPECT values are decimal strings to avoid float64 precision loss;
MaxInt64 acceptance and PING are checked without claiming a292-year wait.
The first-byte/idle and stale/current command-token cases exercise existing
guest gates. The public Options-default comparison is a focused unit check;
public native backend wiring and inherited Options for Fork/Live remain P1-c.

Zero/default30s here follows Go Options. Existing control-string and Python
option validation are unchanged;no new Python zero-duration acceptance is added.


## macOS results — Linux repetition pending

Guest/checked host origin:be244a0bdb510a22417241c2aa2f76a9093aac1b.
UNQUALIFIED guest SHA256:
`d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481`.
Complete worker bodies Fn151/free,Fn129/yield,Fn211/entry match after recorded
relocation;ABI offsets16/40/44 remain unchanged.

Eight native timeout cases pass:exact default/submillisecond/fractional/MaxInt64
values;SLEEP(10.2) completes under default30s;1ns handshake expiry stays local;
idle followed by partial-header first-byte expiry;stale/current command tokens;
invalid config rejection and unchanged native watermark;startup cancellation;
profile2 rejection. Three native timeout fault binaries fail the original
assertions. The actual public Options default/range comparison passes.

Existing P1-a nine native cases/three fault controls,ten lifetime leaves,
22 lifecycle/Live,88 compat,38 limits,G1 234,G2 241 and supporting checks pass.
No original assertion or comparison rule changes. Baseline291 selected
Go/assembly/data files;G2 adds exactly one approved fixture for292.
The two fault runners originally shared a JSON destination;the output paths
are now separate and the six affected controls were rerun. Runtime source and
positive binaries remain unchanged;original expected-failure logs are retained.

The [summary](evidence/macos-summary.json),[timeout cases](evidence/macos-timeout-native.json),
[fault cases](evidence/macos-timeout-native-controls.json),[source reference](evidence/macos-reference.json)
and [G2 reference](evidence/macos-g2-result.json) bind this cohort. Linux must
reproduce this guest,all291 selected source files and all241 G2 observations.
The existing comparison exception is only the validated nonnegative mid-output
byte count. P1-c public integration and inherited Fork/Live options remain open.

## Linux確認完了

[CI42353912021](https://github.com/masahitojp/mariamem/actions/runs/42353912021)は候補
`f6888cca1f1aa800b0d80ccc3fcb1a40b8dc5dfd`で全3 jobs成功。
[保存receipt](evidence/ci42353912021.json)でguest d4f30818の再現、291-file比較、
241観測照合、専用timeout8 cases、builder/runtime cleanup debt0を確認した。
P1-bの両native平台での限定検証を完了。公開API接続とFork/Live設定継承はP1-cに残る。
