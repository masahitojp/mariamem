#!/bin/sh
set -eu
ulimit -c 0
c++ -std=c++17 -O0 -g -DEMBEDDED_LIBRARY \
 -I/exp/temp/source/include -I/exp/temp/native/include \
 /exp/worktree/benchmarks/spikes/issue65-prepared-native/probe.cc \
 /exp/temp/native/libmysqld/libmariadbd.a /exp/temp/native/tpool/libtpool.a \
 -lpcre2-8 -lz -lssl -lcrypto -lcrypt -lpthread -ldl -lm \
 -o /exp/temp/probe
mkdir -p /exp/temp/data
cd /exp/temp/data
/exp/temp/probe
