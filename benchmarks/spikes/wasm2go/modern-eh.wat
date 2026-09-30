(module
  (tag $e (param i32))
  (func (export "run") (result i32)
    (block $done (result i32)
      (try_table (catch $e $done)
        i32.const 7
        throw $e)
      i32.const 0)))
