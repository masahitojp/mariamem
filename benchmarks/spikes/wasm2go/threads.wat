(module
  (import "wasi" "thread-spawn" (func $spawn (param i32) (result i32)))
  (memory (export "memory") 1 2 shared)
  (func (export "wasi_thread_start") (param i32 i32)
    i32.const 0 i32.const 42 i32.atomic.store
    i32.const 0 i32.const 1 memory.atomic.notify drop)
  (func (export "run") (result i32)
    i32.const 0 call $spawn drop
    (block $done
      (loop $wait
        i32.const 0 i32.atomic.load i32.const 42 i32.eq br_if $done
        i32.const 0 i32.const 0 i64.const 100000000 memory.atomic.wait32 drop
        br $wait))
    i32.const 0 i32.atomic.load))
