# MemoryFill code generation check

PASS: the existing zero range loop calls runtime.memclrNoHeapPointers.
Replacing only that loop with clear(b) yields identical 368 instruction bytes
and identical relocation records for MemoryFill. Debug source line numbers differ.
This is optimized compiler output for the exact base package, not disassembly of
a previously published linked executable. No Go 1.26.10 or Linux claim is made.

Source: b3b3b46a8807482ad3f96725af86e031fe369b01 (v0.6.0).
Toolchain: go1.27.3 darwin/arm64, CGO_ENABLED=0, -trimpath, no -N/-l flags.
The local toolchain has no objdump tool, so go build -gcflags=PACKAGE=-S was used.
The source checkout was clean and verified with scripts/git_identity.py.

Conclusion: a clear(b) rewrite alone is not a performance candidate on this input.
Zeroing volume, necessary buffer clearing and first-touch/page work remain separate
questions; neither their duration nor safely avoidable bytes were measured here.
No product file changed and no runtime benchmark or broad acceptance ran.

Reproduce in a clean checkout of the pinned source with the recorded Go version:
1. Build ./internal/generatedgo/code/base with -trimpath and package-specific -S;
   save stderr to a temporary file and the archive outside the source tree.
2. Copy base.go to scratch; replace exactly the zero branch range loop with clear(b).
3. Build the same package with a Go overlay mapping base.go to the scratch copy,
   using the same flags.
4. Extract the MemoryFill STEXT block. Compare its emitted hex instruction bytes
   and all relocation records, excluding source line/debug metadata.

inputs.json records the two source hashes. original.asm.txt and clear.asm.txt
retain the complete function listings; comparison.json records the comparison.
Compiled archives and the dedicated compiler cache were disposable and removed.
