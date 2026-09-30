(module
  (import "env" "memory" (memory 1 2 shared))
  (func (export "run") (result i32)
    i32.const 0 i32.const 42 i32.store
    i32.const 0 i32.load))
