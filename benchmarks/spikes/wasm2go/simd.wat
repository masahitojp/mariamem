(module
  (memory 1)
  (func (export "run") (result i32)
    v128.const i32x4 40 0 0 0
    v128.const i32x4 2 0 0 0
    i32x4.add
    i32x4.extract_lane 0))
