(module
  (import "env" "memory" (memory 1 2))
  (import "wasi_snapshot_preview1" "fd_prestat_get" (func $get (param i32 i32) (result i32)))
  (import "wasi_snapshot_preview1" "fd_prestat_dir_name" (func $name (param i32 i32 i32) (result i32)))
  (func (export "run") (result i32)
    i32.const 3 i32.const 32 call $get
    i32.const 3 i32.const 64 i32.const 1 call $name
    i32.add
    i32.const 64 i32.load8_u i32.const 47 i32.ne
    i32.add))
