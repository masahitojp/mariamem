#!/bin/sh
set -eu
export GOCACHE="$(pwd)/temp/cache"
# Counts use tag filtering followed by the startup function in the stack.
go tool pprof -tags evidence/profiles/*.pprof > evidence/cpu-tags.txt
go tool pprof -tagfocus='fork_phase=early' -focus='\.Fn5583$' -proto evidence/profiles/*.pprof > evidence/cpu-early.pprof
go tool pprof -top -unit=ms -nodecount=30 evidence/cpu-early.pprof > evidence/cpu-top.txt
go tool pprof -top -lines -unit=ms -nodecount=30 evidence/cpu-early.pprof > evidence/cpu-lines.txt
go tool pprof -top -cum -lines -unit=ms -nodecount=40 evidence/cpu-early.pprof > evidence/cpu-cum.txt
go tool pprof -raw evidence/cpu-early.pprof > temp/cpu-early-raw.txt
