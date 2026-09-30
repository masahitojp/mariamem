(module
  (tag $e (param i32))
  (func (export "run") (result i32)
    try (result i32)
      i32.const 7
      throw $e
    catch $e
    end))
