(module
  (memory 1)
  (func (export "calc") (param v128 v128 v128) (result v128)
    local.get 0
    local.get 1
    local.get 2
    f64x2.relaxed_madd))
