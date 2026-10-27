# First candidate CI results and Django definition correction

PR head `63e896a3e86858cef344c9652f2c2f403f99cd9d` passed
[Development checks](https://github.com/masahitojp/mariamem/actions/runs/40470869868)
and [Live E2E](https://github.com/masahitojp/mariamem/actions/runs/40470869902).
The actual PR CI source_commit was
`6084ec76173d701861925181ae72dbdaec2780b6`, whose tree
`b140e74bc764559591251dbd986cd87c256f94a9` matches that head. Receipts keep
the actual CI source rather than substituting the head or correction SHA.

Both host jobs executed the new public documentation examples. Downloaded
artifacts confirm `PASS_PUBLIC_EXAMPLES`, with both Go HTTP and Python browser
routes PASS, on macOS15/Ubuntu24.04 and Python3.11/3.14. The
[assessment](ci-40470869902/assessment.json) records each artifact and original
result hash; raw downloaded artifacts remain under the coordinator's ignored
build directory. Native references, installed consumers and the Live required
gate also succeeded. This is not an actual guide-only skip observation.

However, the [Django workflow definition failed](https://github.com/masahitojp/mariamem/actions/runs/40470823631)
before any job started. Its three job-level `env` values referenced
`runner.temp`, a context unavailable there. The PR's successful existing check
contexts did not detect this missing Django campaign. Django's fresh native and
guest functional matrix remains **NOT RUN**, and adoption remains premature.

The correction moves job-owned cache exports into an initial shell step using
`RUNNER_TEMP` and `GITHUB_ENV`. Paths, source gates, matrix, native pins and
cleanup policy are unchanged. actionlint1.7.12 on macOS arm64 reproduced the
original three context errors and passed the corrected workflow with
`-shellcheck=` (shellcheck was not run). Its official downloaded archive SHA256
was `aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f`.
YAML parsing alone in the original preparation checks did not validate GitHub's
expression-context rules; actionlint supplied the missing check.

The correction is submitted on the existing draft PR for fresh exact-source CI.
Old successful runs do not qualify that new source. No main adoption,
Qualification or release is performed.
