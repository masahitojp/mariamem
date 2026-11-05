# Issue 65: native embedded prepared input spike

Authorized scope: step 2 only. Reuse upstream COM_STMT_EXECUTE parameter decoding in a coherent native embedded build, with THD::client_params null, and verify real SQL results. No handshake, native output, WASIX build, product adoption or performance claim.

Budget: 2 hours active work including 30 minutes tooling; heavy CI 0; owned disk 6 GiB; minimum free space 8 GiB. Existing Linux ARM64 build image only. Stop with concrete missing evidence if the bounded build cannot establish the result.

Source: MariaDB 12.3.3 source_commit 83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e; archive and Connector/C checked against release/inputs.lock.json. Experiment baseline source_commit a796ea01cef3950d9835d001ef40d20b0a93020f. Keep EMBEDDED_LIBRARY coherent throughout; do not mix native and embedded class layouts. Minimal arithmetic/temporary MEMORY SQL is sufficient to test the decoder; no storage acceptance claim.

Positive: numeric/string/null arguments, type reuse if feasible. Negative: truncated arguments rejected without crashing. Witness null client_params and native decode entry. Preserve patch, reproduction commands, checksums, build configuration and results. Delete owned downloads/build/container/worktree after committing compact evidence on experiment/issue65-native-packet.
