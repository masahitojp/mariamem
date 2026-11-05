#!/bin/sh
set -eu
cd /exp
wasixcc --version
/root/.wasixcc/llvm/bin/clang --version
/root/.wasixcc/binaryen/bin/wasm-opt --version
wasixccenv -sWASM_EXCEPTIONS=legacy print-sysroot
wasixcc++ -sWASM_EXCEPTIONS=legacy -sRUN_WASM_OPT=no -O2 -pthread -Wall -Wextra -Werror \
 worktree/benchmarks/spikes/issue65-wasix-preflight/primitives.cc -o temp/primitives.wasm
/root/.wasixcc/binaryen/bin/wasm-opt temp/primitives.wasm --enable-threads --enable-exception-handling --enable-bulk-memory --enable-mutable-globals -o temp/validated.wasm
/root/.wasixcc/binaryen/bin/wasm-dis temp/primitives.wasm -o temp/primitives.wat
