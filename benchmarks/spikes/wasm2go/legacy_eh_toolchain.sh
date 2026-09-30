#!/usr/bin/env bash
# Run only inside the spike's isolated Docker work directory.
set -euo pipefail
cd /work
case "${1:?probe, build, build-no-postopt or postopt}" in
probe)
  mkdir -p probe
  wasixcc --version
  /root/.wasixcc/llvm/bin/wasm-ld --version
  /root/.wasixcc/binaryen/bin/wasm-opt --version
  wasixccenv help-config
  sha256sum /root/.wasixcc/sysroot/sysroot-exnref-eh/lib/wasm32-wasi/{libc.a,libc++.a,libc++abi.a,libunwind.a}
  for mode in exnref legacy; do
    wasixccenv -sWASM_EXCEPTIONS="$mode" print-sysroot
    sysroot=$(wasixccenv -sWASM_EXCEPTIONS="$mode" print-sysroot)
    sha256sum "$sysroot"/lib/wasm32-wasi/{libc.a,libc++.a,libc++abi.a,libunwind.a}
    wasixcc++ -sWASM_EXCEPTIONS="$mode" -sRUN_WASM_OPT=no -O2 -pthread -### -c eh_probe.cpp 2>"probe/$mode-driver.txt"
    wasixcc++ -sWASM_EXCEPTIONS="$mode" -sRUN_WASM_OPT=no -O2 -pthread -S eh_probe.cpp -o "probe/$mode.s"
    wasixcc++ -sWASM_EXCEPTIONS="$mode" -sRUN_WASM_OPT=no -O2 -pthread -c eh_probe.cpp -o "probe/$mode.o"
    wasixcc++ -sWASM_EXCEPTIONS="$mode" -sRUN_WASM_OPT=no -O2 -pthread eh_probe.cpp -o "probe/$mode-preopt.wasm"
    wasixcc++ -sWASM_EXCEPTIONS="$mode" -sWASM_OPT_PRESERVE_UNOPTIMIZED=yes -O2 -pthread eh_probe.cpp -o "probe/$mode-default.wasm"
  done
  wasixcc++ -sWASM_EXCEPTIONS=legacy -sWASM_OPT_SUPPRESS_DEFAULT=yes -sWASM_OPT_FLAGS=-O2 -O2 -pthread eh_probe.cpp -o probe/legacy-preserved.wasm
  /root/.wasixcc/binaryen/bin/wasm-opt --help > probe/wasm-opt-help.txt
  /root/.wasixcc/llvm/bin/clang --target=wasm32-unknown-wasi -mllvm --help-hidden -c -x c /dev/null > probe/llvm-options.txt 2>&1
  ;;
build|build-no-postopt)
  export WASIXCC_WASM_EXCEPTIONS=legacy
  export WASIXCC_WASM_OPT_SUPPRESS_DEFAULT=yes
  export WASIXCC_WASM_OPT_FLAGS=-O2
  export WASIXCC_WASM_OPT_PRESERVE_UNOPTIMIZED=yes
  if [[ "$1" == build-no-postopt ]]; then
    export WASIXCC_RUN_WASM_OPT=no
    export WASIX_BUILD=/work/source/build-legacy-no-postopt
  else
    export WASIX_BUILD=/work/source/build-wasix
  fi
  export JOBS=3
  cd source
  bash wasm/build-wasix.sh
  mkdir -p /work/artifact
  cp wasm/dist/lite4mariadb.wasix.wasm /work/artifact/mariamem-legacy-eh.wasm
  cp "$WASIX_BUILD/wasm/CMakeFiles/lite4mariadb-wasix.dir/link.txt" /work/artifact/link.txt
  cp "$WASIX_BUILD/CMakeCache.txt" /work/artifact/CMakeCache.txt
  cp "$WASIX_BUILD/wasm/CMakeFiles/lite4mariadb-wasix.dir/flags.make" /work/artifact/flags.make
  ;;
postopt)
  # Same enabled feature family as WASIXCC 0.4.7; retain legacy EH.
  # --all-features would also enable compact imports, absent in the release.
  /root/.wasixcc/binaryen/bin/wasm-opt -O2 \
    --enable-threads --enable-mutable-globals --enable-bulk-memory \
    --enable-bulk-memory-opt --enable-exception-handling --enable-simd \
    --enable-relaxed-simd --enable-extended-const \
    artifact/mariamem-legacy-eh.wasm -o artifact/mariamem-legacy-eh-O2-compatible.wasm
  ;;
*) exit 2 ;;
esac
