(module
  (func (export "run") (param exnref)
    local.get 0
    throw_ref))
