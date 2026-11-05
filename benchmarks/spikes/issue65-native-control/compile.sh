#!/bin/sh
set -eu
c++ -std=c++17 -O0 -g -rdynamic -Wall -Wextra -Werror -Wno-unused-function -DEMBEDDED_LIBRARY -DMARIAMEM_NATIVE_WIRE \
 -I/exp/temp/source/wasm -I/exp/temp/source/include -I/exp/temp/native/include \
 -I/exp/worktree/guest -I/exp/worktree/benchmarks/spikes/issue65-native-control \
 /exp/worktree/benchmarks/spikes/issue65-native-control/control.cc \
 /exp/temp/native/libmysqld/libmariadbd.a /exp/temp/native/tpool/libtpool.a \
 -lpcre2-8 -lz -lssl -lcrypto -lcrypt -lpthread -ldl -lm -o /exp/temp/control
