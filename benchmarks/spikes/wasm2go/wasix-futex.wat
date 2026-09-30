(module
  (import "wasix_32v1" "futex_wait" (func $wait (param i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1 2 shared)
  (func (export "run") (result i32)
    i32.const 0 i32.const 1 i32.const 8 i32.const 16 call $wait))
