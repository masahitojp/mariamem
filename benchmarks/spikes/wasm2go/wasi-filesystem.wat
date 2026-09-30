(module
  (import "wasi_snapshot_preview1" "path_create_directory" (func $mkdir (param i32 i32 i32) (result i32)))
  (import "wasi_snapshot_preview1" "path_filestat_get" (func $stat (param i32 i32 i32 i32 i32) (result i32)))
  (import "wasi_snapshot_preview1" "path_remove_directory" (func $rmdir (param i32 i32 i32) (result i32)))
  (memory 1)
  (data (i32.const 0) "proof")
  (func (export "run") (result i32)
    i32.const 3 i32.const 0 i32.const 5 call $mkdir
    i32.const 3 i32.const 0 i32.const 0 i32.const 5 i32.const 64 call $stat i32.or
    i32.const 3 i32.const 0 i32.const 5 call $rmdir i32.or))
