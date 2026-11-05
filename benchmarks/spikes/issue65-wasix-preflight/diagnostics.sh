#!/bin/sh
# Diagnostic portability control: a failure is retained, never hidden as success.
cd /exp
wasixcc++ -sWASM_EXCEPTIONS=legacy -sRUN_WASM_OPT=no -pthread -fsyntax-only worktree/benchmarks/spikes/issue65-wasix-preflight/linux_diagnostics.cc
rc=$?
echo "diagnostics_compile_exit_code=$rc"
sha256sum /root/.wasixcc/bin/wasixccenv /root/.wasixcc/llvm/bin/clang /root/.wasixcc/sysroot/sysroot-eh/lib/wasm32-wasi/libc.a /root/.wasixcc/sysroot/sysroot-eh/lib/wasm32-wasi/libc++.a
