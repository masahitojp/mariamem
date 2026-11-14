# Daily image-fixture repair after43459032237

The normal source suite passed. Go tests then detected the old constructor-init
flag address in image/image_test.go. The actual generated Fn67 uses27744624,
not27745648. The test-only flag and segment-boundary sample addresses now match
the installed constructor. Full-memory hash/global equality, sibling isolation,
page-only completeness and all negative-oracle assertions are unchanged.

Normal daily Go package tests pass locally after this repair. No production or
generated body, image manifest or accepted behavior changed. CI must confirm on
the pinned Go toolchain and both product platforms. Old failure is not a runtime
corruption result and is not relabeled into a PASS.
