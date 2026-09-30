(module
  (import "wasi_snapshot_preview1" "fd_close" (func $close (param i32) (result i32)))
  (import "wasix_32v1" "path_open2" (func $open (param i32 i32 i32 i32 i32 i64 i64 i32 i32 i32) (result i32)))
  (memory 1)
  (data (i32.const 64) "proof")
  (func (export "run") (result i32)
    i32.const 3 i32.const 1 i32.const 64 i32.const 5 i32.const 1
    i64.const 66 i64.const 0 i32.const 0 i32.const 0 i32.const 32 call $open
    i32.const 32 i32.load call $close i32.or))
