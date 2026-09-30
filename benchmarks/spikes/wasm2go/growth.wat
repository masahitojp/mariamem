(module
  (memory 1 2 shared)
  (func (export "run") (result i32)
    i32.const 1 memory.grow
    memory.size i32.add))
