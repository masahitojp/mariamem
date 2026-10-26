# Local candidate evidence

Source: df3e68393ca5734cfc73e1837013d30bb620e7d1, macOS arm64.
assessment.json separates PASS, original failures, deliberately rejected mutations
and the local Python3.14/OpenSSL4 environment blocker. It is not a CI receipt.

SHA256SUMS.json covers every receipt file except itself. logs.zip.base64 losslessly
preserves53 original text/JSON/XML members, including failed initial check,
partial integration, both routing attempts and standalone environment probes.
Decode it into disposable scratch, verify assessment.json's decoded_sha256,
then verify archive-members.json against each uncompressed member. The buildinfo
header in assessment.json is normalized; raw headers remain in archived routing
inputs.json. No binary host or build cache is retained as product evidence.
