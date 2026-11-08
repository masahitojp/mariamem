# First C-input acquisition: configuration failure

Run [42428352206](https://github.com/masahitojp/mariamem/actions/runs/42428352206)
keeps original source_commit `86edd6cd2da3cb80e9e37334b30698b470a57999`.
The standalone C producer replay (all638 full512-byte maps) and native MariaDB
SQL reference passed. Host-native generator compilation succeeded, but WASIX
CMake configuration could not find `<CI_HOME>/.wasixcc/bin/wasixcc` or
`wasixcc++`: the accepted installer had placed the SDK in `/root/.wasixcc`.
Translations were skipped because their guest dependency failed.

The repair sets the build step's HOME to `/root`, matching the already accepted
`uca-canonical.yml` builder. Missing-HOME and wrong-HOME negative contract cases
are added; a HOME setting on another step cannot satisfy the check. Guest C
patch, canonical runtime and release bytes do not change. A new CI run must
establish the corrected result; these receipts are never relabelled.

`<CI_HOME>` denotes the GitHub container HOME, `/github/home`. Original/published
file hashes are recorded in path-normalization.json; raw fetched files remain in
the local receipt.

Both downloaded artifact ZIP SHA256 values were checked against GitHub's
published digests before extraction; assessment.json records IDs and digests.
SHA256SUMS.json covers saved receipt files. The later README is explanatory.
