;; A reduced page-cleaner-style work unit, not the MariaDB worker body.
;; Persistent target/result in linear memory; explicit completion is the safepoint.
(module
 (import "wasi" "thread-spawn" (func $spawn (param i32) (result i32)))
 (memory (export "memory") 1 2 shared)
 (global $tls (mut i32) (i32.const 0))
 (func (export "wasi_thread_start") (param $tid i32) (param i32)
  local.get $tid i32.const 100 i32.add global.set $tls
  i32.const 4 i32.const 0 i32.atomic.load i32.atomic.rmw.add drop
  i32.const 8 local.get $tid i32.atomic.store
  i32.const 1024 local.get $tid i32.const 16 i32.mul i32.add global.get $tls i32.atomic.store
  i32.const 12 i32.const 1 i32.atomic.store
  i32.const 12 i32.const 1 memory.atomic.notify drop)
 (func (export "begin") (param $work i32) (result i32)
  i32.const 99 global.set $tls
  i32.const 0 local.get $work i32.atomic.store
  i32.const 12 i32.const 0 i32.atomic.store
  i32.const 0 call $spawn)
 (func (export "main_tls") (result i32) global.get $tls)
)
