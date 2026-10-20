# SDK path reproduction

Run from the candidate checkout, with the already available local builder image:

```sh
docker run --rm --network none -e HOME=/github/home \
  -v "$PWD:/candidate:ro" \
  sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f \
  python3 /candidate/docs/reviews/v06x-routine-bootstrap-ci-sdk-fix/verify.py
```

This is a disposable path/configuration probe, not a fresh pinned-toolchain
build or functional acceptance. The image supplies CMake and an existing SDK;
it does not prove the corrected CI guest hash. It mutates only the disposable
container's global Git config. No network or guest compilation is used.
`wasix-toolchain.cmake` is an unchanged copy from shyim/lite4mariadb commit
24be9371a2f6c71250a2356631ad6feab2280b02, `wasm/wasix-toolchain.cmake`.
Its SHA256 is checked against the existing recipe pin before probing.
`source.json` and losslessly compressed `guest-build.log.gz` are original
artifacts from failed run 39378516288 (candidate 63733ea103f9c5940912a8fa9f26e456c74a6961).
